# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Automatic and Manual House Generation for Blender
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""MULTI-VOLUMES — Aile secondaire (plans en L)

Une aile est un second volume habitable accolé à une façade de la maison
principale. Géométrie EXACTE, pas d'approximation:

- Murs de briques calculés dans le repère LOCAL de l'aile (mêmes
  fonctions que la maison: pignons maçonnés, briques coupées, linteaux)
  puis transformés et FUSIONNÉS dans le même nuage Geometry Nodes.
- Toit GABLE de l'aile dont le faîtage court vers la maison. Deux cas,
  tous deux exacts:
  * NOUE: l'aile s'accroche à un mur d'égout d'une maison de plain-pied
    → les pans de l'aile pénètrent le pan principal et sont coupés par
    les DEUX plans verticaux à 45° (noues réelles: pentes égales →
    noue à 45° en plan). Les tuiles sont ajustées et une bande de noue
    en zinc couvre la coupe, comme sur un vrai toit.
  * APPENTIS-PIGNON: maison à étage(s) ou accroche sur un mur pignon
    → le toit de l'aile se termine PLAT contre le mur (pente réduite si
    nécessaire pour passer sous le rampant du pignon — règle de
    construction affichée dans la console).
- Passage dans le mur mitoyen (ouverture + linteau, briques coupées).
- Les fenêtres de la façade principale masquées par l'aile sont
  supprimées; la porte d'entrée est déplacée si l'aile la couvre.

Contrainte assumée (règle de construction, affichée): l'aile est de
PLAIN-PIED et reprend la pente du toit principal (noues à 45°). Toit
principal GABLE uniquement pour l'instant.
"""

import math
import random

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

from .features import (
    _add_box, _new_mesh_obj, _simple_material, _create_tile_master,
    TILE_W, TILE_L, TILE_OVERLAP,
)

# ✅ S8: valeurs canoniques dans norms.py (source unique documentée)
from .norms import (TOIT_DALLE_RAMPANT_EP as ROOF_T,
                    ZINC_NOUE_LARGEUR as NOUE_WIDTH,
                    PASSAGE_AILE_H as PASSAGE_HEIGHT)
from . import norms


# ============================================================
# REPÈRE DE L'AILE
# ============================================================

def wing_frame(props, effective_pitch, main_wall_height, wing_wall_height=None,
               side=None, wing_width=None, wing_depth=None, wing_offset=None,
               enabled=True):
    """Calcule le repère et les caractéristiques de l'aile, ou None.

    Repère LOCAL de l'aile: x ∈ [0, w] (largeur le long de la façade),
    y ∈ [0, d] (profondeur, y=d = mur mitoyen). Le mur local 'front'
    (y=0) est le pignon extérieur; 'back' (y=d) n'existe pas (mitoyen).

    Returns dict:
        side, w, d, a0 (offset le long de la façade), theta, T, M,
        attached_wall, valley (bool), pitch_deg, h (hauteur murs aile),
        span (a0, a1) sur le mur d'accroche.
    """
    if not enabled:
        return None

    if props.roof_type not in ('GABLE', 'HIP', 'GAMBREL', 'SKELETON'):
        print(f"[House] ⚠️ Aile: toit principal {props.roof_type} non supporté "
              f"(GABLE/croupe/mansarde/squelette) — aile ignorée")
        return None
    # ✅ S2: sous toit SQUELETTE, l'aile n'a NI noue propre NI appentis:
    # le toit unifié (plan2d + skeleton) couvre l'ensemble
    skeleton_roof = props.roof_type == 'SKELETON'

    side = side or props.wing_side  # 'FRONT' / 'BACK' / 'LEFT' / 'RIGHT'
    W, L = props.house_width, props.house_length

    facade = W if side in ('FRONT', 'BACK') else L
    w = max(2.0, min(wing_width if wing_width is not None else props.wing_width,
                     facade - 0.6))
    d = max(1.5, wing_depth if wing_depth is not None else props.wing_depth)
    a0 = wing_offset if wing_offset is not None else props.wing_offset
    a0 = max(0.0, min(a0, facade - w))

    h_main = main_wall_height
    h = wing_wall_height if wing_wall_height is not None else \
        min(h_main, props.floor_height)

    # Faîtage principal le long de la plus grande dimension (convention
    # partagée avec les créateurs de toit et compute_all_brick_positions)
    main_ridge_along_y = L >= W
    main_rt = props.roof_type
    if main_rt == 'HIP':
        # ✅ v1.7: tous les murs d'une croupe sont des murs d'ÉGOUT
        eave_walls = ('front', 'back', 'left', 'right')
    else:
        eave_walls = ('left', 'right') if main_ridge_along_y else ('front', 'back')
    if main_rt == 'GAMBREL':
        # égouts mansarde toujours en ±X → murs left/right; le brisis à 68°
        # interdit une noue → aile sur PIGNONS (front/back) seulement
        eave_walls = ('left', 'right')
    attached_wall = side.lower()

    pitch = effective_pitch
    slope = math.tan(math.radians(pitch))

    # NOUE réelle seulement si: accroche sur un mur d'égout ET égouts à la
    # même hauteur (aile et maison de plain-pied) → pénétration du pan
    valley = (attached_wall in eave_walls) and (abs(h - h_main) < 0.02)
    if skeleton_roof:
        valley = False   # le squelette déduit noues/arêtiers lui-même

    if main_rt == 'GAMBREL' and attached_wall in eave_walls:
        print("[House] ⚠️ Aile: sur une mansarde, l'aile s'accroche aux "
              "PIGNONS (avant/arrière) — le brisis à 68° interdit la noue. "
              "Aile ignorée")
        return None

    if main_rt == 'HIP' and valley:
        # ✅ v1.7: la noue exige que l'emprise pénétrée reste sur le PAN
        # UNIQUE du mur d'accroche: l'aile doit rester entre les arêtiers
        # (retrait de w/2 + marge à chaque bout de façade)
        pen = w / 2 + 0.35
        if a0 < pen or (a0 + w) > facade - pen:
            if h < h_main - 0.02:
                valley = False  # appentis sous l'égout (maison à étages)
            else:
                print("[House] ⚠️ Aile croupe: l'emprise chevauche un "
                      "arêtier (décalez l'aile vers le centre de la façade) "
                      "— aile ignorée")
                return None

    def _pignon_height(center):
        """Hauteur du mur pignon du toit principal à l'abscisse `center`
        le long de la façade (pour caler l'appentis dessous)."""
        half_f = facade / 2
        if main_rt == 'GAMBREL':
            brisis = math.tan(math.radians(68.0))
            bd = (facade / 2) * 0.25
            bh = bd * brisis
            x = center
            if x < bd:
                return h_main + x * brisis
            if x > facade - bd:
                return h_main + (facade - x) * brisis
            return h_main + bh + (min(x, facade - x) - bd) * slope
        if main_rt == 'HIP':
            return h_main  # murs d'égout partout
        return h_main + slope * (half_f - abs(center - half_f))

    if not skeleton_roof and (not valley and attached_wall not in eave_walls or
                              (not valley and main_rt == 'HIP')):
        # APPENTIS: le faîtage de l'aile doit passer sous le mur/rampant
        center = a0 + w / 2
        pignon_z = _pignon_height(center)
        ridge_z = h + slope * (w / 2)
        if ridge_z > pignon_z - 0.05:
            new_slope = max(0.15, (pignon_z - 0.05 - h) / (w / 2))
            pitch = math.degrees(math.atan(new_slope))
            print(f"[House] Aile: pente réduite à {pitch:.0f}° pour passer "
                  f"sous le mur d'accroche (règle appentis)")

    # Transformation locale → monde (rotation z puis translation)
    if side == 'FRONT':
        theta, T = 0.0, Vector((a0, -d, 0))
    elif side == 'BACK':
        theta, T = math.pi, Vector((a0 + w, L + d, 0))
    elif side == 'RIGHT':
        theta, T = math.pi / 2, Vector((W + d, a0, 0))
    else:  # LEFT
        theta, T = -math.pi / 2, Vector((-d, a0 + w, 0))

    M = Matrix.Translation(T) @ Matrix.Rotation(theta, 4, 'Z')

    # Orientation MONDE de chaque mur local (pour fenêtres/volets)
    local_to_world_wall = {
        'FRONT': {'front': 'front', 'left': 'left',  'right': 'right'},
        'BACK':  {'front': 'back',  'left': 'right', 'right': 'left'},
        'RIGHT': {'front': 'right', 'left': 'front', 'right': 'back'},
        'LEFT':  {'front': 'left',  'left': 'back',  'right': 'front'},
    }[side]

    # Emprise MONDE de l'aile (contrôle de chevauchement entre ailes)
    corners = [M @ Vector((0, 0, 0)), M @ Vector((w, d, 0))]
    xs = sorted(c.x for c in corners)
    ys = sorted(c.y for c in corners)

    return {
        'footprint': (xs[0], ys[0], xs[1], ys[1]),
        'side': side, 'w': w, 'd': d, 'a0': a0,
        'theta': theta, 'T': T, 'M': M,
        'attached_wall': attached_wall,
        'valley': valley, 'pitch_deg': pitch, 'h': h, 'h_main': h_main,
        'span': (a0, a0 + w),
        'wall_map': local_to_world_wall,
    }


def passage_opening(frame, props, wall_depth, plinth_z):
    """Ouverture de passage dans le mur mitoyen de la maison principale."""
    w = frame['w']
    pw = min(1.6, max(0.9, w - 1.6))
    a0, a1 = frame['span']
    center = (a0 + a1) / 2
    wall = frame['attached_wall']
    W, L = props.house_width, props.house_length
    o = {'width': pw, 'height': PASSAGE_HEIGHT, 'z': plinth_z,
         'depth': wall_depth, 'wall': wall, 'type': 'door'}
    if wall in ('front', 'back'):
        o['x'] = center - pw / 2
        o['y'] = 0 if wall == 'front' else L
    else:
        o['y'] = center - pw / 2
        o['x'] = 0 if wall == 'left' else W
    return o


def opening_in_span(opening, frame, margin=0.35):
    """True si l'ouverture (dict maison principale) est masquée par l'aile."""
    if opening.get('wall') != frame['attached_wall']:
        return False
    along = opening['x'] if frame['attached_wall'] in ('front', 'back') else opening['y']
    center = along + opening['width'] / 2
    a0, a1 = frame['span']
    return (a0 - margin) < center < (a1 + margin)


# ============================================================
# OUVERTURES ET FENÊTRES DE L'AILE (repère local)
# ============================================================

def wing_openings_local(frame, props, window_layout, window_verticals, wall_depth):
    """Fenêtres de l'aile en coordonnées LOCALES — un jeu PAR ÉTAGE.

    window_verticals: liste [(hauteur, z_bas, z_centre)] par étage de l'aile.
    Returns (openings, specs) comme avant.
    """
    w, d = frame['w'], frame['d']
    ww = window_layout['width']
    if not isinstance(window_verticals, list):
        window_verticals = [window_verticals]

    openings, specs = [], []

    def add(wall_local, along_center, wh, z_bottom, z_center):
        spec = {'wall_local': wall_local, 'along_center': along_center,
                'width': ww, 'height': wh,
                'z_bottom': z_bottom, 'z_center': z_center}
        specs.append(spec)
        o = {'width': ww, 'height': wh, 'z': z_bottom,
             'depth': wall_depth, 'wall': wall_local, 'type': 'window'}
        if wall_local == 'front':
            o['x'] = along_center - ww / 2
            o['y'] = 0
        else:
            o['y'] = along_center - ww / 2
            o['x'] = 0 if wall_local == 'left' else w
        openings.append(o)

    for (wh, z_bottom, z_center) in window_verticals:
        # Pignon extérieur: 2 fenêtres aux QUARTS si les volets ouverts ne
        # se chevauchent pas, sinon 1 centrée
        if w >= 4 * ww + 0.4:
            add('front', w / 4, wh, z_bottom, z_center)
            add('front', 3 * w / 4, wh, z_bottom, z_center)
        elif w >= ww + 1.4:
            add('front', w / 2, wh, z_bottom, z_center)
        # Murs latéraux: 1 fenêtre centrée si la profondeur le permet
        if d >= ww + 1.4:
            add('left', d / 2, wh, z_bottom, z_center)
            add('right', d / 2, wh, z_bottom, z_center)

    return openings, specs


def frames_overlap(f1, f2, margin=0.05):
    """True si les emprises MONDE de deux ailes se chevauchent."""
    a = f1['footprint']; b = f2['footprint']
    return not (a[2] <= b[0] + margin or b[2] <= a[0] + margin or
                a[3] <= b[1] + margin or b[3] <= a[1] + margin)


def garage_openings_local(frame, props, wall_depth):
    """✅ v1.7: ouvertures d'un GARAGE-AILE — une porte sectionnelle sur
    le mur qui fait face à la rue (monde AVANT), pas de fenêtres."""
    w, d = frame['w'], frame['d']
    # mur local orienté vers l'avant (voir wall_map)
    front_local = next((lw for lw, ww in frame['wall_map'].items()
                        if ww == 'front'), 'front')
    span = w if front_local == 'front' else d
    gw = min(2.6, span - 1.0)
    if gw < 1.8:
        print("[House] Garage-aile: façade trop étroite pour la porte")
        return [], front_local, None
    o = {'width': gw, 'height': 2.05, 'z': 0.2, 'depth': wall_depth,
         'wall': front_local, 'type': 'door'}
    if front_local == 'front':
        o['x'] = span / 2 - gw / 2
        o['y'] = 0
    else:
        o['y'] = span / 2 - gw / 2
        o['x'] = 0 if front_local == 'left' else w
    return [o], front_local, o


def build_garage_wing_door(frame, props, collection, opening, front_local):
    """Porte sectionnelle ARTICULÉE du garage-aile (driver 'ouverture'
    qui monte les panneaux), posée dans l'ouverture maçonnée."""
    if opening is None:
        return []
    gw, gh = opening['width'], opening['height']
    z0 = opening['z']
    n_panels = 4
    ph = gh / n_panels
    bm = bmesh.new()
    t0, t1 = 0.035, 0.075
    for i in range(n_panels):
        pz0 = i * ph + 0.008
        pz1 = (i + 1) * ph - 0.008
        if front_local == 'front':
            a = opening['x']
            _add_box(bm, a + 0.02, t0, pz0 - z0, a + gw - 0.02, t1, pz1 - z0)
        elif front_local == 'left':
            a = opening['y']
            _add_box(bm, t0, a + 0.02, pz0 - z0, t1, a + gw - 0.02, pz1 - z0)
        else:  # right
            a = opening['y']
            _add_box(bm, frame['w'] - t1, a + 0.02, pz0 - z0,
                     frame['w'] - t0, a + gw - 0.02, pz1 - z0)
    mat = _simple_material("House_Garage_Door", (0.88, 0.88, 0.86), roughness=0.5)
    obj = _new_mesh_obj("Garage_Door", bm, collection, "garage", mat)
    # origine au bas de la porte (locale), transformée dans le monde
    obj.matrix_world = frame['M'] @ Matrix.Translation(Vector((0, 0, z0)))
    obj["ouverture"] = 0.0
    try:
        ui = obj.id_properties_ui("ouverture")
        ui.update(min=0.0, max=1.0, description="0 = fermée, 1 = ouverte (monte)")
    except Exception:
        pass
    fcu = obj.driver_add('location', 2)
    drv = fcu.driver
    drv.type = 'SCRIPTED'
    var = drv.variables.new()
    var.name = 'o'
    var.type = 'SINGLE_PROP'
    var.targets[0].id = obj
    var.targets[0].data_path = '["ouverture"]'
    drv.expression = f'{z0:.3f} + o * {gh - 0.15:.3f}'
    print("[House] ✓ Garage-aile: porte sectionnelle articulée posée")
    return [obj]


def generate_wing_windows(frame, props, collection, specs, window_gen, wall_depth):
    """Objets fenêtres 3D de l'aile + specs volets (coordonnées MONDE)."""
    M = frame['M']
    w, d = frame['w'], frame['d']
    shutter_specs = []

    for spec in specs:
        wl = spec['wall_local']
        along, zc = spec['along_center'], spec['z_center']
        if wl == 'front':
            local_center = Vector((along, wall_depth / 2, zc))
            local_wall_pt = Vector((along, 0, zc))
        elif wl == 'left':
            local_center = Vector((wall_depth / 2, along, zc))
            local_wall_pt = Vector((0, along, zc))
        else:  # right
            local_center = Vector((w - wall_depth / 2, along, zc))
            local_wall_pt = Vector((w, along, zc))

        world_center = M @ local_center
        world_wall_pt = M @ local_wall_pt
        orientation = frame['wall_map'][wl]

        window_gen.generate_window(
            window_type=props.window_type,
            width=spec['width'], height=spec['height'],
            location=world_center, orientation=orientation,
            collection=collection)

        shutter_specs.append({
            'x': world_wall_pt.x, 'y': world_wall_pt.y,
            'z_center': zc, 'width': spec['width'],
            'height': spec['height'], 'wall': orientation})

    return shutter_specs


# ============================================================
# BRIQUES DE L'AILE (fusionnées dans le nuage principal)
# ============================================================

def compute_wing_brick_positions(frame, props, openings_local):
    """Positions de briques de l'aile, transformées en coordonnées MONDE.

    Réutilise compute_all_brick_positions dans le repère local (pignon
    maçonné, briques coupées, linteaux), SANS le mur mitoyen, faîtage
    forcé le long de la profondeur.
    """
    from .materials import brick_geometry

    positions = brick_geometry.compute_all_brick_positions(
        frame['w'], frame['d'], frame['h'],
        openings=openings_local,
        roof_type='GABLE',
        roof_pitch=frame['pitch_deg'],
        bonding_pattern=props.brick_bonding_pattern,
        skip_walls=('back',),
        force_ridge_along_y=True,
    )

    M = frame['M']
    Rz = Matrix.Rotation(frame['theta'], 3, 'Z')
    out = []
    for item in positions:
        pos, rot = item[0], item[1]
        scl = item[2] if len(item) > 2 else Vector((1.0, 1.0, 1.0))
        world_pos = M @ pos
        world_rot = (Rz @ rot.to_matrix()).to_euler()
        out.append((world_pos, world_rot, scl))
    print(f"[House] Aile: {len(out)} briques fusionnées dans le nuage principal")
    return out


# ============================================================
# MURS SIMPLES DE L'AILE (mode non-briques)
# ============================================================

def build_wing_simple_walls(frame, props, collection, openings_local):
    """Murs pleins de l'aile avec ouvertures EXACTES (trumeaux + linteaux
    + allèges par segments, comme la façade du garage) et pignon
    triangulaire maçonné sur le mur extérieur.
    """
    w, d, h = frame['w'], frame['d'], frame['h']
    t = props.wall_thickness
    pitch_rad = math.radians(frame['pitch_deg'])
    peak = h + (w / 2) * math.tan(pitch_rad)

    bm = bmesh.new()

    def wall_with_openings(along_len, openings, box, top):
        """box(a0, a1, z0, z1) construit un segment dans le mur considéré."""
        ops = sorted(openings, key=lambda o: o['a'])
        cursor = 0.0
        for o in ops:
            if o['a'] > cursor:
                box(cursor, o['a'], 0, top)              # trumeau
            box(o['a'], o['a'] + o['w'], 0, o['z'])      # allège
            if o['z'] + o['h'] < top - 0.02:
                box(o['a'], o['a'] + o['w'], o['z'] + o['h'], top)  # linteau
            cursor = o['a'] + o['w']
        if cursor < along_len:
            box(cursor, along_len, 0, top)

    def ops_for(wall):
        res = []
        for o in openings_local:
            if o['wall'] != wall:
                continue
            a = o['x'] if wall == 'front' else o['y']
            res.append({'a': a, 'w': o['width'], 'z': o['z'], 'h': o['height']})
        return res

    # Murs latéraux (sous égouts — capés sous la dalle)
    cap = ROOF_T / max(0.2, math.cos(pitch_rad)) + 0.05
    hc = h - cap

    # ✅ S2: sous toit SQUELETTE, le bout de l'aile est une CROUPE —
    # pas de pignon maçonné (il transperçait le pan), mur capé à
    # l'égout comme les côtés
    skeleton_roof = props.roof_type == 'SKELETON'

    # Mur extérieur (pignon, y=0)
    wall_with_openings(w, ops_for('front'),
                       lambda a0, a1, z0, z1: _add_box(bm, a0, 0, z0, a1, t, z1),
                       top=hc if skeleton_roof else h)
    if not skeleton_roof:
        # Triangle du pignon (prisme exact) au-dessus de h
        v = [bm.verts.new(p) for p in
             [(0, 0, h), (w, 0, h), (w / 2, 0, peak),
              (0, t, h), (w, t, h), (w / 2, t, peak)]]
        bm.faces.new([v[0], v[1], v[2]])
        bm.faces.new([v[5], v[4], v[3]])
        bm.faces.new([v[0], v[3], v[4], v[1]])
        bm.faces.new([v[1], v[4], v[5], v[2]])
        bm.faces.new([v[2], v[5], v[3], v[0]])
    wall_with_openings(d, ops_for('left'),
                       lambda a0, a1, z0, z1: _add_box(bm, 0, a0, z0, t, a1, z1),
                       top=hc)
    wall_with_openings(d, ops_for('right'),
                       lambda a0, a1, z0, z1: _add_box(bm, w - t, a0, z0, w, a1, z1),
                       top=hc)

    bmesh.ops.transform(bm, verts=bm.verts, matrix=frame['M'])
    try:
        from . import look
        mat = look.wall_material(tuple(props.wall_material_color)[:3],
                                 getattr(props, 'wall_finish', 'AUTO'))
    except Exception:
        mat = _simple_material("House_Wall",
                               tuple(props.wall_material_color)[:3],
                               roughness=0.8)
    obj = _new_mesh_obj("Wing_Walls", bm, collection, "wall", mat)
    # ✅ FIX MAJEUR: ne PAS appliquer le Boolean des ouvertures de la
    # maison à ce mesh (boîtes en recouvrement → le solveur EXACT
    # avalait les trumeaux de la façade du garage!). Les ouvertures de
    # l'aile sont déjà maçonnées par segments.
    obj["no_boolean"] = True
    return [obj]


# ============================================================
# TOIT DE L'AILE — dalles, noues exactes, tuiles, finitions
# ============================================================

def _local_slab(bm, x_eave, x_ridge, y0, y1, z_of_x, t):
    """Dalle à épaisseur VERTICALE entre deux profils x (grille 2 pts)."""
    tf = [bm.verts.new((x, y0, z_of_x(x))) for x in (x_eave, x_ridge)]
    tb = [bm.verts.new((x, y1, z_of_x(x))) for x in (x_eave, x_ridge)]
    bf = [bm.verts.new((x, y0, z_of_x(x) - t)) for x in (x_eave, x_ridge)]
    bb = [bm.verts.new((x, y1, z_of_x(x) - t)) for x in (x_eave, x_ridge)]
    bm.faces.new([tf[0], tf[1], tb[1], tb[0]])   # dessus
    bm.faces.new([bb[0], bb[1], bf[1], bf[0]])   # dessous
    bm.faces.new([tf[0], tb[0], bb[0], bf[0]])   # bord égout
    bm.faces.new([tb[1], tf[1], bf[1], bb[1]])   # bord faîtage
    bm.faces.new([tf[1], tf[0], bf[0], bf[1]])   # bord y0
    bm.faces.new([tb[0], tb[1], bb[1], bb[0]])   # bord y1


def build_wing_roof(props, collection, frame, o_eave, o_rake, tile_color,
                    make_tiles=True):
    """Toit GABLE de l'aile: dalles coupées en noue (45°) ou terminées
    contre le mur, faîtière, tuiles ajustées, bandes de noue zinc,
    planches de rive, tuiles de rive du pignon, gouttières.
    """
    w, d, h = frame['w'], frame['d'], frame['h']
    pitch_rad = math.radians(frame['pitch_deg'])
    slope = math.tan(pitch_rad)
    cosp = math.cos(pitch_rad)
    valley = frame['valley']
    M = frame['M']
    z_eave = h - o_eave * slope
    ridge_z = h + (w / 2) * slope
    objs = []

    # Profondeur de pénétration: jusqu'au sommet de noue (y = d + w/2)
    y_end = d + w / 2 + 0.05 if valley else d

    # --- DALLES (épaisseur verticale, coupes de noue exactes) ---
    bm = bmesh.new()
    _local_slab(bm, -o_eave, w / 2, -o_rake, y_end,
                lambda x: h + slope * x, ROOF_T)                     # pan gauche
    _local_slab(bm, w + o_eave, w / 2, -o_rake, y_end,
                lambda x: h + slope * (w - x), ROOF_T)               # pan droit

    if valley:
        # Noues: plans VERTICAUX à 45° (pentes égales) passant par les
        # coins du mur mitoyen — la géométrie réelle d'une noue.
        for co, no in (((0.0, d, 0.0), (-1.0, 1.0, 0.0)),
                       ((w, d, 0.0), (1.0, 1.0, 0.0))):
            res = bmesh.ops.bisect_plane(
                bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                plane_co=co, plane_no=Vector(no).normalized(),
                clear_outer=True, clear_inner=False)
            # Refermer les coupes
            edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
            if edges:
                try:
                    bmesh.ops.holes_fill(bm, edges=edges)
                except Exception:
                    pass

    bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
    slab_mat = _simple_material("House_Roof_Slab", (0.35, 0.30, 0.28), roughness=0.9)
    objs.append(_new_mesh_obj("Wing_Roof", bm, collection, "roof", slab_mat))

    # --- TUILES (mêmes pas que la couverture principale, coupes de noue) ---
    random.seed(norms.derive_seed(props, 'aile_' + str(frame.get('side'))))  # ✅ S6
    lift = 0.02
    step_v = TILE_L - TILE_OVERLAP
    positions = []
    if not make_tiles:
        positions = None  # dalles nues (couverture désactivée)

    def cover(origin, dir_u, dir_v, len_u, len_v, rot, keep):
        n_u = int(len_u / TILE_W)
        normal = dir_u.cross(dir_v).normalized()
        if normal.z < 0:
            normal = -normal
        # ✅ Inclinaison de pose physique (voir features.cover_slope)
        delta = math.atan2(norms.TUILE_NEZ_H, step_v)
        base_rot = (Matrix.Rotation(-delta, 3, dir_u) @ rot.to_matrix()).to_euler()
        iv = 0
        while iv * step_v + TILE_L <= len_v + 0.03 + 1e-6:
            for iu in range(n_u):
                p = origin + dir_u * (iu * TILE_W) + dir_v * (iv * step_v) \
                    + normal * 0.008
                p_far = p + dir_u * TILE_W
                if not keep(p, p_far):
                    continue
                j = math.radians(0.8)
                r = Euler((base_rot.x + random.uniform(-j, j),
                           base_rot.y + random.uniform(-j, j),
                           base_rot.z + random.uniform(-j, j)), 'XYZ')
                positions.append((p + normal * random.uniform(0, 0.003), r))
            iv += 1

    # ✅ Orientation tuile: longueur vers le faîtage, galbe en travers
    rot_up_x = (Matrix.Rotation(-pitch_rad, 3, 'Y') @
                Matrix.Rotation(math.radians(-90), 3, 'Z')).to_euler()
    rot_down_x = (Matrix.Rotation(pitch_rad, 3, 'Y') @
                  Matrix.Rotation(math.radians(90), 3, 'Z')).to_euler()

    slope_len_full = (w / 2 + o_eave) / cosp
    len_u = (y_end + o_rake)
    if not make_tiles:
        positions = []
        len_u = 0  # aucune tuile posée
    # Pan gauche: v monte de x=-o_eave vers le faîtage, u le long de +y
    cover(Vector((-o_eave, -o_rake, z_eave + lift)),
          Vector((0, 1, 0)),
          Vector((cosp, 0, math.sin(pitch_rad))),
          len_u, slope_len_full, rot_up_x,
          keep=(lambda p, pf: pf.y <= p.x + d + 0.12) if valley
          else (lambda p, pf: pf.y <= d + 0.02))
    # Pan droit: v monte de x=w+o_eave vers le faîtage
    cover(Vector((w + o_eave, -o_rake, z_eave + lift)),
          Vector((0, 1, 0)),
          Vector((-cosp, 0, math.sin(pitch_rad))),
          len_u, slope_len_full, rot_down_x,
          keep=(lambda p, pf: pf.y <= (w - p.x) + d + 0.12) if valley
          else (lambda p, pf: pf.y <= d + 0.02))

    if positions:
        Rz = Matrix.Rotation(frame['theta'], 3, 'Z')
        world_positions = []
        for p, r in positions:
            world_positions.append((M @ p, (Rz @ r.to_matrix()).to_euler()))

        # Master partagé avec la couverture principale si présent
        master = None
        for o in collection.objects:
            if o.name.startswith("Tile_Master"):
                master = o
                break
        if master is None:
            master = _create_tile_master(collection, tile_color)

        mesh = bpy.data.meshes.new("Wing_Tiles_Points")
        mesh.from_pydata([tuple(p) for p, _r in world_positions], [], [])
        mesh.update()
        attr = mesh.attributes.new("tile_rot", 'FLOAT_VECTOR', 'POINT')
        flat = []
        for _p, r in world_positions:
            flat.extend((r.x, r.y, r.z))
        attr.data.foreach_set('vector', flat)
        obj = bpy.data.objects.new("Wing_Tiles", mesh)
        obj["house_part"] = "roof"
        collection.objects.link(obj)

        ng = bpy.data.node_groups.new("House_WingTile_Instancer", 'GeometryNodeTree')
        ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
        n_in = ng.nodes.new('NodeGroupInput')
        n_pts = ng.nodes.new('GeometryNodeMeshToPoints'); n_pts.mode = 'VERTICES'
        n_obj = ng.nodes.new('GeometryNodeObjectInfo')
        n_obj.transform_space = 'ORIGINAL'
        n_obj.inputs['Object'].default_value = master
        if 'As Instance' in n_obj.inputs:
            n_obj.inputs['As Instance'].default_value = True
        n_attr = ng.nodes.new('GeometryNodeInputNamedAttribute')
        n_attr.data_type = 'FLOAT_VECTOR'
        n_attr.inputs['Name'].default_value = "tile_rot"
        n_inst = ng.nodes.new('GeometryNodeInstanceOnPoints')
        n_out = ng.nodes.new('NodeGroupOutput')
        ng.links.new(n_in.outputs['Geometry'], n_pts.inputs['Mesh'])
        ng.links.new(n_pts.outputs['Points'], n_inst.inputs['Points'])
        ng.links.new(n_obj.outputs['Geometry'], n_inst.inputs['Instance'])
        ng.links.new(n_attr.outputs['Attribute'], n_inst.inputs['Rotation'])
        ng.links.new(n_inst.outputs['Instances'], n_out.inputs['Geometry'])
        mod = obj.modifiers.new("TileInstancer", 'NODES')
        mod.node_group = ng
        objs.append(obj)
        print(f"[House] ✓ Aile: {len(world_positions)} tuiles (noues ajustées)")

    from .features import _tile_accessory_material
    tile_mat = _tile_accessory_material(tile_color)

    # --- FAÎTIÈRE de l'aile (jusqu'au sommet de noue) ---
    bm = bmesh.new()
    ridge_y1 = (d + w / 2 - 0.10) if valley else d
    ridge_len = ridge_y1 + o_rake
    seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                radius1=norms.FAITIERE_RAYON_AILE, radius2=norms.FAITIERE_RAYON_AILE, depth=ridge_len)
    bmesh.ops.transform(bm, verts=seg['verts'],
                        matrix=Matrix.Translation(Vector((
                            w / 2, (-o_rake + ridge_y1) / 2, ridge_z + 0.03))) @
                        Matrix.Rotation(math.radians(90), 4, 'X'))
    bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
    objs.append(_new_mesh_obj("Wing_Ridge", bm, collection, "roof", tile_mat))

    # --- BANDES DE NOUE (zinc) le long des coupes ---
    if valley:
        zinc = _simple_material("House_Zinc", (0.62, 0.65, 0.67),
                                roughness=0.35, metallic=0.9)
        bm = bmesh.new()
        for x_wall, sgn in ((0.0, 1), (w, -1)):
            # La noue va du coin des égouts au sommet de noue
            p0 = Vector((x_wall - sgn * o_eave, d - o_eave, z_eave + lift + 0.005))
            p1 = Vector((w / 2, d + w / 2, ridge_z + lift + 0.005))
            axis = (p1 - p0)
            length = axis.length
            quat = axis.normalized().to_track_quat('Z', 'Y')
            box = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.transform(bm, verts=box['verts'],
                                matrix=Matrix.Diagonal((NOUE_WIDTH, 0.012, length, 1.0)))
            center = (p0 + p1) / 2
            bmesh.ops.transform(bm, verts=box['verts'],
                                matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
        bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
        objs.append(_new_mesh_obj("Wing_Valley", bm, collection, "roof", zinc))

    # --- PLANCHES DE RIVE le long des égouts de l'aile ---
    bm = bmesh.new()
    fh, ft = norms.FASCIA_H, norms.FASCIA_EP
    y_f0, y_f1 = -o_rake, (d - o_eave if valley else d)
    _add_box(bm, -o_eave - ft, y_f0, z_eave - ROOF_T - fh + 0.06,
             -o_eave, y_f1, z_eave - ROOF_T + 0.06)
    _add_box(bm, w + o_eave, y_f0, z_eave - ROOF_T - fh + 0.06,
             w + o_eave + ft, y_f1, z_eave - ROOF_T + 0.06)
    bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
    fascia_mat = _simple_material("House_Fascia", (0.92, 0.92, 0.90), roughness=0.5)
    objs.append(_new_mesh_obj("Wing_Fascia", bm, collection, "roof", fascia_mat))

    # --- PLANCHES DE RIVE DE PIGNON (ferment le jeu briques/rampant) ---
    bm = bmesh.new()
    bb_h, bb_t = norms.RIVE_PLANCHE_H, norms.RIVE_PLANCHE_EP
    for x0 in (-o_eave, w + o_eave):
        p0 = Vector((x0, -o_rake, z_eave))
        p1 = Vector((w / 2, -o_rake, ridge_z))
        axis = p1 - p0
        quat = axis.normalized().to_track_quat('Z', 'Y')
        box = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.transform(bm, verts=box['verts'],
                            matrix=Matrix.Diagonal((bb_h, bb_t, axis.length, 1.0)))
        center = (p0 + p1) / 2 + Vector((0, 0, -bb_h * 0.25))
        center.y = -o_rake - bb_t / 2
        bmesh.ops.transform(bm, verts=box['verts'],
                            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
    bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
    objs.append(_new_mesh_obj("Wing_Bargeboard", bm, collection, "roof", fascia_mat))

    # --- TUILES DE RIVE du pignon extérieur ---
    bm = bmesh.new()
    r = 0.07
    half = w / 2
    run = math.sqrt((half + o_eave) ** 2 + (ridge_z - z_eave) ** 2)
    for sgn, x_start in ((1, -o_eave), (-1, w + o_eave)):
        seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=8,
                                    radius1=r, radius2=r, depth=run)
        direction = Vector((sgn * (half + o_eave), 0, ridge_z - z_eave)).normalized()
        quat = direction.to_track_quat('Z', 'Y')
        center = Vector((x_start + sgn * (half + o_eave) / 2, -o_rake,
                         (z_eave + ridge_z) / 2 + 0.06))
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(center) @ quat.to_matrix().to_4x4())
    bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
    objs.append(_new_mesh_obj("Wing_Verge", bm, collection, "roof", tile_mat))

    # --- GOUTTIÈRES des égouts de l'aile + descente au pignon ---
    if getattr(props, 'include_gutters', False):
        zinc = _simple_material("House_Gutter", (0.75, 0.76, 0.78),
                                roughness=0.35, metallic=0.8)
        bm = bmesh.new()
        g_r = norms.GOUTTIERE_RAYON
        g_len = y_f1 - y_f0
        for x_g in (-o_eave - 0.02, w + o_eave + 0.02):
            seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=12,
                                        radius1=g_r, radius2=g_r, depth=g_len)
            bmesh.ops.transform(bm, verts=seg['verts'],
                                matrix=Matrix.Translation(Vector((
                                    x_g, (y_f0 + y_f1) / 2, z_eave - ROOF_T + 0.02))) @
                                Matrix.Rotation(math.radians(90), 4, 'X'))
        # Descentes aux angles du pignon extérieur
        for x_g in (-o_eave - 0.02, w + o_eave + 0.02):
            down_z = z_eave - ROOF_T
            seg = bmesh.ops.create_cone(bm, cap_ends=True, segments=10,
                                        radius1=norms.DESCENTE_RAYON, radius2=norms.DESCENTE_RAYON, depth=down_z)
            bmesh.ops.transform(bm, verts=seg['verts'],
                                matrix=Matrix.Translation(Vector((x_g, -o_rake + 0.10,
                                                                  down_z / 2))))
        bmesh.ops.transform(bm, verts=bm.verts, matrix=M)
        objs.append(_new_mesh_obj("Wing_Gutters", bm, collection, "gutter", zinc))

    kind = "noues 45° exactes" if valley else "appentis-pignon (terminaison au mur)"
    print(f"[House] ✓ Toit de l'aile: {kind}")
    return objs


# ============================================================
# FONDATIONS ET PLANCHER DE L'AILE
# ============================================================

def build_wing_foundation(props, collection, frame, visible):
    """Soubassement de l'aile, aligné sur celui de la maison."""
    if props.foundation_height <= 0:
        return []
    w, d = frame['w'], frame['d']
    ov = 0.15
    height = props.foundation_height
    bm = bmesh.new()
    _add_box(bm, -ov, -ov, visible - height, w + ov, d, visible)
    bmesh.ops.transform(bm, verts=bm.verts, matrix=frame['M'])
    mat = bpy.data.materials.get("Foundation_Material") or \
        _simple_material("House_Foundation", (0.62, 0.60, 0.58), roughness=0.9)
    obj = _new_mesh_obj("Wing_Foundation", bm, collection, "foundation", mat)
    return [obj]


def build_wing_floor(props, collection, frame):
    """Dalle de sol de l'aile — même niveau fini que la maison
    (sommet à 0.20 = seuil du passage)."""
    w, d = frame['w'], frame['d']
    bm = bmesh.new()
    _add_box(bm, 0.05, 0.05, 0.0, w - 0.05, d - 0.05, 0.20)
    bmesh.ops.transform(bm, verts=bm.verts, matrix=frame['M'])
    mat = _simple_material("House_Floor", tuple(props.floor_material_color)[:3],
                           roughness=0.6)
    obj = _new_mesh_obj("Wing_Floor", bm, collection, "floor", mat)
    return [obj]
