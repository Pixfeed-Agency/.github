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

"""INTÉRIEURS — plafonds, cloisons, sols

Ce qu'on voit à travers les fenêtres et les portes ouvertes:

- PLAFONDS en plâtre par étage et par volume (fini la vue directe sur
  le dessous de la dalle du toit).
- CLOISONS de distribution avec passages de porte de 0.93m (largeur
  standard française) — le positionnement évite les fenêtres et la
  porte d'entrée (nudge automatique).
- SOLS habillés (parquet) posés sur les dalles.

La distribution est volontairement simple et déterministe:
séjour traversant côté entrée + refend, deux pièces côté opposé.
L'aile (multi-volumes) est une pièce unique (suite) avec son plafond.
"""

import math

import bpy
import bmesh
from mathutils import Vector, Matrix

from .features import _add_box, _new_mesh_obj, _simple_material

# ✅ S8: valeurs canoniques dans norms.py (source unique documentée)
from .norms import (CLOISON_EP as PARTITION_T,
                    PASSAGE_PORTE_L as DOORWAY_W,
                    PASSAGE_PORTE_H as DOORWAY_H,
                    PLAFOND_EP as CEILING_T)
from . import norms


def _plaster():
    try:
        from . import look
        return look.plaster_material("House_Plaster", base=(0.92, 0.91, 0.88))
    except Exception:
        return _simple_material("House_Plaster", (0.92, 0.91, 0.88), roughness=0.9)


def _parquet():
    try:
        from . import look
        return look.wood_material("House_Parquet", base=(0.66, 0.44, 0.24),
                                  rough=0.4, along='X')
    except Exception:
        return _simple_material("House_Parquet", (0.55, 0.38, 0.22), roughness=0.5)


def _avoid(candidate, forbidden, clearance, lo, hi):
    """Nudge la position d'une cloison hors des zones interdites
    (fenêtres/portes du mur qu'elle rencontre)."""
    for _ in range(12):
        ok = True
        for c in forbidden:
            if abs(candidate - c) < clearance:
                candidate = c + clearance if candidate >= c else c - clearance
                ok = False
        if ok:
            break
    return max(lo, min(hi, candidate))


def _partition_with_doorway(bm, axis, at, a0, a1, z0, z1, door_at):
    """Cloison le long de `axis` ('X' = mur à y=at, 'Y' = mur à x=at)
    percée d'un passage de porte centré sur door_at."""
    t = PARTITION_T
    d0 = max(a0 + 0.1, door_at - DOORWAY_W / 2)
    d1 = min(a1 - 0.1, d0 + DOORWAY_W)
    top = min(z1, z0 + DOORWAY_H)

    def seg(s0, s1, zz0, zz1):
        if s1 - s0 < 0.02 or zz1 - zz0 < 0.02:
            return
        if axis == 'X':
            _add_box(bm, s0, at - t / 2, zz0, s1, at + t / 2, zz1)
        else:
            _add_box(bm, at - t / 2, s0, zz0, at + t / 2, s1, zz1)

    seg(a0, d0, z0, z1)          # avant le passage
    seg(d1, a1, z0, z1)          # après le passage
    seg(d0, d1, top, z1)         # imposte au-dessus de la porte


def interior_layout(props, wall_depth, floor_height_actual, door_center_x,
                    window_xs_back, window_ys_side, attic_rise=None):
    """✅ v1.5: Distribution PARTAGÉE — positions des refends, passage
    aligné sur l'entrée, et ESCALIER DROIT avec trémie si ≥ 2 étages.

    L'escalier court le long du refend transversal, côté séjour. La
    volée: marches de 25cm de giron, hauteur de marche fha/n ≈ 17-18cm
    (norme habitation). Trémie sur les 2/3 hauts de la volée.
    Returns dict {y_refend, door_pass, x_split, stair, tremie}.
    """
    W, L = props.house_width, props.house_length
    t = wall_depth
    y_refend = _avoid(L * 0.55, window_ys_side, 0.75, L * 0.35, L * 0.7)
    door_pass = _avoid(door_center_x, [], 0, t + 0.7, W - t - 0.7)
    # ✅ v1.14: MODE PROGRAMME — le solveur (programme.py) a résolu les
    # largeurs des cellules de la bande arrière (chambres, SdB, WC):
    # elles priment sur le découpage uniforme.
    prog_cells = None
    if getattr(props, 'programme_active', False):
        try:
            prog_cells = [float(v) for v in
                          getattr(props, 'programme_cells', '').split(',')
                          if v.strip()]
        except ValueError:
            prog_cells = None
        if prog_cells and len(prog_cells) < 2:
            prog_cells = None

    if prog_cells:
        inner = W - 2 * t
        scale = inner / sum(prog_cells)   # absorbe les arrondis d'emprise
        n_rooms = len(prog_cells)
        x_splits, acc = [], t
        for cw in prog_cells[:-1]:
            acc += cw * scale
            x_splits.append(_avoid(acc, list(window_xs_back), 0.70,
                                   t + 0.9, W - t - 0.9))
    else:
        # ✅ v1.9: N chambres derrière le refend → N-1 cloisons
        # longitudinales (chambre mini 2.6m — réduit si façade courte)
        n_rooms = max(1, min(int(getattr(props, 'num_bedrooms', 2)),
                             int((W - 2 * t) / 2.6)))
        x_splits = [_avoid(t + (W - 2 * t) * (i + 1) / n_rooms,
                           list(window_xs_back), 0.70,
                           t + 1.2, W - t - 1.2)
                    for i in range(n_rooms - 1)]
    x_split = x_splits[0] if x_splits else W * 0.5  # compat historique

    stair = tremie = None
    # ✅ COMBLES: l'escalier existe aussi en plain-pied + combles
    # aménagés (attic_rise = hauteur sol RDC → plancher des combles)
    rise = attic_rise or floor_height_actual
    if props.num_floors >= 2 or attic_rise:
        going = norms.ESCALIER_GIRON
        n = max(norms.ESCALIER_N_MIN,
                int(math.ceil(rise / norms.ESCALIER_HAUTEUR_MAX)))
        run = n * going
        y1 = y_refend - PARTITION_T / 2 - 0.06
        y0 = y1 - 1.0
        # volée collée au mur DROIT, montée vers +x (départ côté gauche)
        x1 = W - t - 0.25
        x0 = x1 - run
        if x0 >= t + 0.4:
            # le passage du refend ne doit pas déboucher SUR l'escalier
            if x0 - 0.7 < door_pass < x1 + 0.7:
                door_pass = _avoid(max(t + 0.7, x0 - 1.0), [], 0,
                                   t + 0.7, W - t - 0.7)
                if x0 - 0.7 < door_pass < x1 + 0.7:
                    door_pass = t + 0.75
            stair = {'kind': 'straight', 'x0': x0, 'x1': x1, 'y0': y0,
                     'y1': y1, 'n': n, 'going': going, 'run': run,
                     'rise': rise}
            tremie = (x0 + run * 0.35, y0 - 0.02, x1 + 0.15, y1 + 0.02)
        else:
            # ✅ v1.7: VOLÉE EN L (quart tournant à palier) pour les
            # maisons étroites: montée A le long du refend vers +x,
            # palier d'angle, montée B le long du mur droit vers l'avant
            going = norms.ESCALIER_GIRON_QT
            landing = norms.ESCALIER_PALIER
            xA1 = W - t - landing
            xA0 = t + 0.35
            availA = xA1 - xA0
            n_tot = max(norms.ESCALIER_N_MIN,
                        int(math.ceil(rise / norms.ESCALIER_HAUTEUR_MAX)))
            nA = max(3, min(n_tot - 4, int(availA / going)))
            nB = n_tot - nA - 1   # le palier compte pour une hauteur
            runB = nB * going
            yB_end = y0 - runB
            if nB < 3 or yB_end < t + 0.4:
                print("[House] Escalier: ni volée droite ni quart tournant "
                      "ne rentrent — ignoré")
            else:
                xA0 = xA1 - nA * going
                if xA0 - 0.7 < door_pass < W:
                    door_pass = max(t + 0.7, xA0 - 1.0)
                stair = {'kind': 'L', 'xA0': xA0, 'xA1': xA1,
                         'y0': y0, 'y1': y1, 'landing': landing,
                         'nA': nA, 'nB': nB, 'going': going,
                         'n': n_tot, 'yB_end': yB_end, 'rise': rise}
                tremie = (xA1 - 0.35, yB_end - 0.05, W - t, y1 + 0.02)

    return {'y_refend': y_refend, 'door_pass': door_pass,
            'x_split': x_split, 'x_splits': x_splits, 'n_rooms': n_rooms,
            'stair': stair, 'tremie': tremie}


def build_staircase(props, collection, layout, floor_height_actual,
                    slab_top, style_name='TRADITIONAL'):
    # ✅ COMBLES: la volée monte de `rise` (plancher des combles) si
    # le layout l'impose (plain-pied + combles aménagés) — et il faut
    # UNE volée même avec num_floors=1 (la boucle historique en
    # construisait zéro: escalier fantôme)
    n_flights = props.num_floors - 1
    if layout.get('stair') and layout['stair'].get('rise'):
        floor_height_actual = layout['stair']['rise']
        n_flights = max(1, n_flights)
    """✅ v1.5: ESCALIER DROIT entre chaque étage, style selon
    l'architecture: BOIS (limons + contremarches + garde-corps bois) en
    traditionnel/méditerranéen, BÉTON + garde-corps métal fin en
    moderne/contemporain."""
    stair = layout.get('stair')
    if not stair:
        return []
    wood_style = style_name in ('TRADITIONAL', 'MEDITERRANEAN')
    kind = stair.get('kind', 'straight')
    y0, y1 = stair['y0'], stair['y1']
    n, going = stair['n'], stair['going']
    if kind == 'straight':
        x0, x1 = stair['x0'], stair['x1']

    if wood_style:
        step_mat = _parquet()
        struct_mat = _simple_material("House_Stair_Wood", (0.36, 0.24, 0.14),
                                      roughness=0.55)
        rail_mat = struct_mat
    else:
        step_mat = _simple_material("House_Stair_Concrete", (0.60, 0.59, 0.57),
                                    roughness=0.8)
        struct_mat = step_mat
        rail_mat = _simple_material("House_Stair_Metal", (0.20, 0.20, 0.22),
                                    roughness=0.35, metallic=0.85)

    bm_steps = bmesh.new()
    bm_struct = bmesh.new()
    bm_rail = bmesh.new()
    objs = []

    def guard_rail(px0, py0, px1, py1, z, along):
        """Garde-corps de trémie: poteaux + lisse + main courante."""
        length_r = (px1 - px0) if along == 'X' else (py1 - py0)
        n_posts = max(2, int(length_r / 0.8) + 1)
        for k in range(n_posts):
            f = k / (n_posts - 1)
            px = px0 + (px1 - px0) * f
            py = py0 + (py1 - py0) * f
            _add_box(bm_rail, px - 0.02, py - 0.02, z, px + 0.02, py + 0.02,
                     z + 0.92)
        if along == 'X':
            _add_box(bm_rail, px0, py0 - 0.025, z + 0.87, px1, py0 + 0.025,
                     z + 0.92)
            _add_box(bm_rail, px0, py0 - 0.015, z + 0.44, px1, py0 + 0.015,
                     z + 0.48)
        else:
            _add_box(bm_rail, px0 - 0.025, py0, z + 0.87, px0 + 0.025, py1,
                     z + 0.92)
            _add_box(bm_rail, px0 - 0.015, py0, z + 0.44, px0 + 0.015, py1,
                     z + 0.48)

    if kind == 'L':
        xA0, xA1 = stair['xA0'], stair['xA1']
        nA, nB = stair['nA'], stair['nB']
        landing = stair['landing']
        yB_end = stair['yB_end']
        W = props.house_width
        for floor in range(n_flights):
            z_base = slab_top + floor * floor_height_actual
            rise = floor_height_actual / (nA + nB + 1)
            # volée A (monte vers +x, dans la bande du refend)
            for i in range(nA):
                sx0 = xA0 + i * going
                sz1 = z_base + (i + 1) * rise
                if wood_style:
                    _add_box(bm_steps, sx0 - 0.03, y0 + 0.02, sz1 - 0.035,
                             sx0 + going + 0.005, y1 - 0.02, sz1)
                    _add_box(bm_struct, sx0 + going - 0.02, y0 + 0.04,
                             sz1 - rise, sx0 + going, y1 - 0.04, sz1 - 0.035)
                else:
                    _add_box(bm_steps, sx0, y0 + 0.02, z_base,
                             sx0 + going + 0.003, y1 - 0.02, sz1)
            # palier d'angle
            z_pal = z_base + (nA + 1) * rise
            _add_box(bm_steps, xA1, y0 + 0.02, z_pal - 0.05,
                     W - 0.132, y1 - 0.02, z_pal)
            # volée B (monte vers -y le long du mur droit)
            for j in range(nB):
                sy1 = y0 - j * going
                sy0 = sy1 - going
                sz1 = z_pal + (j + 1) * rise
                if wood_style:
                    _add_box(bm_steps, xA1 + 0.02, sy0 - 0.005, sz1 - 0.035,
                             W - 0.132, sy1 + 0.03, sz1)
                    _add_box(bm_struct, xA1 + 0.04, sy0, sz1 - rise,
                             W - 0.152, sy0 + 0.02, sz1 - 0.035)
                else:
                    _add_box(bm_steps, xA1 + 0.02, sy0, z_pal,
                             W - 0.132, sy1 + 0.003, sz1)
            # garde-corps: bord extérieur de A + palier + B
            post_r = 0.03 if wood_style else 0.014
            for i in range(0, nA + 1, 2):
                px = xA0 + i * going
                pz0 = z_base + i * rise
                _add_box(bm_rail, px - post_r, y0 - 0.01, pz0,
                         px + post_r, y0 + 0.05, pz0 + 0.90)
            for i in range(nA):
                px = xA0 + i * going
                pz = z_base + (i + 1) * rise + 0.88
                _add_box(bm_rail, px - 0.005, y0 - 0.005, pz - 0.045,
                         px + going + 0.005, y0 + 0.055, pz)
            # poteau d'angle du palier
            _add_box(bm_rail, xA1 - 0.03, y0 - 0.03, z_pal,
                     xA1 + 0.03, y0 + 0.03, z_pal + 0.92)
            for j in range(0, nB + 1, 2):
                py = y0 - j * going
                pz0 = z_pal + j * rise
                _add_box(bm_rail, xA1 - 0.01, py - post_r, pz0,
                         xA1 + 0.05, py + post_r, pz0 + 0.90)
            # ✅ GARDE-CORPS DE TRÉMIE à l'étage d'arrivée
            z_arr = slab_top + (floor + 1) * floor_height_actual + 0.016
            tr = layout.get('tremie')
            if tr:
                hx0, hy0, hx1, hy1 = tr
                guard_rail(hx0, hy0, hx0, y1, z_arr, 'Y')      # bord gauche
                guard_rail(hx0, hy0, min(hx1, W - 0.132 - 1.0), hy0, z_arr, 'X')
        objs2 = []
        objs2.append(_new_mesh_obj("Stair_Steps", bm_steps, collection,
                                   "interior", step_mat))
        if len(bm_struct.verts):
            objs2.append(_new_mesh_obj("Stair_Structure", bm_struct, collection,
                                       "interior", struct_mat))
        else:
            bm_struct.free()
        objs2.append(_new_mesh_obj("Stair_Rail", bm_rail, collection,
                                   "interior", rail_mat))
        print(f"[House] ✓ Escalier QUART TOURNANT "
              f"{'bois' if wood_style else 'béton/métal'}: {nA}+{nB} marches "
              f"+ palier + garde-corps de trémie")
        return objs2

    for floor in range(n_flights):
        z_base = slab_top + floor * floor_height_actual
        rise = floor_height_actual / n
        for i in range(n):
            sx0 = x0 + i * going
            sz1 = z_base + (i + 1) * rise
            if wood_style:
                # marche (nez débordant 3cm) + contremarche
                _add_box(bm_steps, sx0 - 0.03, y0 + 0.02, sz1 - 0.035,
                         sx0 + going + 0.005, y1 - 0.02, sz1)
                _add_box(bm_struct, sx0 + going - 0.02, y0 + 0.04,
                         sz1 - rise, sx0 + going, y1 - 0.04, sz1 - 0.035)
            else:
                # béton: bloc plein jusqu'au sol de la marche
                _add_box(bm_steps, sx0, y0 + 0.02, z_base,
                         sx0 + going + 0.003, y1 - 0.02, sz1)
        if wood_style:
            # limons latéraux (bandeaux suivant la pente)
            for yy in (y0, y1 - 0.045):
                for i in range(n):
                    sx0 = x0 + i * going
                    sz1 = z_base + (i + 1) * rise
                    _add_box(bm_struct, sx0, yy, sz1 - rise - 0.05,
                             sx0 + going, yy + 0.045, sz1)
        # garde-corps côté séjour (y0): poteaux + main courante
        post_r = 0.03 if wood_style else 0.014
        for i in range(0, n + 1, 2):
            px = x0 + i * going
            pz0 = z_base + i * rise
            _add_box(bm_rail, px - post_r, y0 - 0.01, pz0,
                     px + post_r, y0 + 0.05, pz0 + 0.90)
        for i in range(n):
            px = x0 + i * going
            pz = z_base + (i + 1) * rise + 0.88
            _add_box(bm_rail, px - 0.005, y0 - 0.005, pz - 0.045,
                     px + going + 0.005, y0 + 0.055, pz)
        # ✅ v1.7: GARDE-CORPS DE TRÉMIE à l'arrivée (bords ouverts)
        z_arr = slab_top + (floor + 1) * floor_height_actual + 0.016
        tr = layout.get('tremie')
        if tr:
            hx0, hy0, hx1, hy1 = tr
            guard_rail(hx0, hy0, hx1, hy0, z_arr, 'X')   # long côté séjour
            guard_rail(hx0, hy0, hx0, hy1, z_arr, 'Y')   # petit côté gauche

    objs.append(_new_mesh_obj("Stair_Steps", bm_steps, collection,
                              "interior", step_mat))
    if len(bm_struct.verts):
        objs.append(_new_mesh_obj("Stair_Structure", bm_struct, collection,
                                  "interior", struct_mat))
    else:
        bm_struct.free()
    objs.append(_new_mesh_obj("Stair_Rail", bm_rail, collection,
                              "interior", rail_mat))
    print(f"[House] ✓ Escalier {'bois' if wood_style else 'béton/métal'}: "
          f"{stair['n']} marches × {n_flights} volée(s) + trémie")
    return objs


def build_interior_doors(props, collection, layout, floor_height_actual,
                         slab_top):
    """✅ v1.5: PORTES INTÉRIEURES posées dans les passages des cloisons
    (battant articulé 'ouverture', entrouvert pour la vie du plan)."""
    try:
        from .doors import DoorGenerator
    except Exception as e:
        print(f"[House] Portes intérieures indisponibles: {e}")
        return []
    W, L = props.house_width, props.house_length
    gen = DoorGenerator(quality='MEDIUM')
    made = 0
    for floor in range(props.num_floors):
        z = slab_top + floor * floor_height_actual + 0.016
        dw = DOORWAY_W - 0.05
        # porte du refend transversal (mur X à y=y_refend)
        try:
            gen.generate_door(
                door_type='SINGLE', width=dw, height=DOORWAY_H - 0.06,
                location=Vector((layout['door_pass'] - dw / 2,
                                 layout['y_refend'] - PARTITION_T / 2, z)),
                orientation='front', collection=collection)
            made += 1
        except Exception as e:
            print(f"[House] Porte intérieure (refend) échouée: {e}")
        # portes des cloisons de chambres (une par refend longitudinal)
        for xs in layout.get('x_splits', [layout['x_split']]):
            try:
                y_door = layout['y_refend'] + 0.75
                gen.generate_door(
                    door_type='SINGLE', width=dw, height=DOORWAY_H - 0.06,
                    location=Vector((xs - PARTITION_T / 2,
                                     y_door - dw / 2, z)),
                    orientation='left', collection=collection)
                made += 1
            except Exception as e:
                print(f"[House] Porte intérieure (chambre) échouée: {e}")
    print(f"[House] ✓ {made} porte(s) intérieure(s) posée(s)")
    return []


def build_wall_liners(props, collection, wall_depth, openings,
                      floor_height_actual, top_ceiling_z, slab_top,
                      wing_frames=None):
    """✅ v1.5: DOUBLAGE INTÉRIEUR PEINT des murs extérieurs.

    Panneaux plâtre (3.5cm) plaqués côté intérieur des 4 murs (et des
    murs des ailes), avec RÉSERVATIONS exactes aux fenêtres, portes et
    passages (liste d'ouvertures partagée avec la maçonnerie). Fini la
    brique apparente involontaire à l'intérieur.
    """
    from mathutils import Matrix as _M
    W, L = props.house_width, props.house_length
    t = wall_depth
    lt = 0.035
    color = tuple(getattr(props, 'interior_wall_color', (0.87, 0.85, 0.80)))[:3]
    mat = _simple_material("House_Interior_Paint", color, roughness=0.9)

    def liner_for_wall(bm, wall, span_len, box, wall_openings, n_floors, fh):
        """Segments pleins + allèges + linteaux autour des ouvertures."""
        ops = sorted(wall_openings, key=lambda o: o['a'])
        for floor in range(n_floors):
            z0 = floor * fh + slab_top + 0.017
            z1 = (floor + 1) * fh - CEILING_T - 0.002
            if floor == n_floors - 1 and top_ceiling_z is not None:
                z1 = min(z1, top_ceiling_z - CEILING_T - 0.002)
            cursor = 0.0
            for o in ops:
                oa0, oa1 = o['a'] - 0.02, o['a'] + o['w'] + 0.02
                oz0, oz1 = o['z'] - 0.02, o['z'] + o['h'] + 0.02
                if oz1 <= z0 or oz0 >= z1:
                    continue  # ouverture hors de cet étage
                if oa0 > cursor:
                    box(cursor, oa0, z0, z1)
                if oz0 > z0:
                    box(oa0, oa1, z0, min(oz0, z1))     # allège
                if oz1 < z1:
                    box(oa0, oa1, max(oz1, z0), z1)     # imposte
                cursor = max(cursor, oa1)
            if cursor < span_len:
                box(cursor, span_len, z0, z1)

    def project(openings_list, wall):
        res = []
        for o in openings_list or []:
            if o.get('wall') != wall:
                continue
            a = o['x'] if wall in ('front', 'back') else o['y']
            res.append({'a': a, 'w': o['width'], 'z': o['z'], 'h': o['height']})
        return res

    bm = bmesh.new()
    nf = props.num_floors
    liner_for_wall(bm, 'front', W,
                   lambda a0, a1, z0, z1: _add_box(bm, max(a0, t), t, z0,
                                                   min(a1, W - t), t + lt, z1),
                   project(openings, 'front'), nf, floor_height_actual)
    liner_for_wall(bm, 'back', W,
                   lambda a0, a1, z0, z1: _add_box(bm, max(a0, t), L - t - lt, z0,
                                                   min(a1, W - t), L - t, z1),
                   project(openings, 'back'), nf, floor_height_actual)
    liner_for_wall(bm, 'left', L,
                   lambda a0, a1, z0, z1: _add_box(bm, t, max(a0, t + lt), z0,
                                                   t + lt, min(a1, L - t - lt), z1),
                   project(openings, 'left'), nf, floor_height_actual)
    liner_for_wall(bm, 'right', L,
                   lambda a0, a1, z0, z1: _add_box(bm, W - t - lt, max(a0, t + lt), z0,
                                                   W - t, min(a1, L - t - lt), z1),
                   project(openings, 'right'), nf, floor_height_actual)
    objs = [_new_mesh_obj("Interior_Liners", bm, collection, "interior", mat)]

    # Ailes: doublage des 3 murs (le mitoyen est le doublage du principal)
    # — le garage garde sa brique apparente (réaliste)
    for wf in (wing_frames or []):
        if wf.get('garage'):
            continue
        w, d = wf['w'], wf['d']
        floors = wf.get('floors', 1)
        fh = wf.get('fh', wf['h'])
        wo = wf.get('openings') or []
        bm = bmesh.new()
        saved_top = wf['h'] - 0.32
        liner_for_wall(bm, 'front', w,
                       lambda a0, a1, z0, z1: _add_box(bm, max(a0, t), t, z0,
                                                       min(a1, w - t), t + lt, z1),
                       project(wo, 'front'), floors, fh)
        liner_for_wall(bm, 'left', d,
                       lambda a0, a1, z0, z1: _add_box(bm, t, max(a0, t + lt), z0,
                                                       t + lt, min(a1, d), z1),
                       project(wo, 'left'), floors, fh)
        liner_for_wall(bm, 'right', d,
                       lambda a0, a1, z0, z1: _add_box(bm, w - t - lt, max(a0, t + lt), z0,
                                                       w - t, min(a1, d), z1),
                       project(wo, 'right'), floors, fh)
        bmesh.ops.transform(bm, verts=bm.verts, matrix=wf['M'])
        objs.append(_new_mesh_obj("Wing_Liners", bm, collection, "interior", mat))

    print("[House] ✓ Doublage intérieur peint posé (murs + ailes)")
    return objs


def build_interiors(props, collection, wall_depth, floor_height_actual,
                    door_center_x, window_xs_front, window_xs_back,
                    window_ys_side, wing_frames=None, passage=None,
                    top_ceiling_z=None, slab_top=0.2, layout=None,
                    ceiling_profile=None):
    """Plafonds, cloisons et sols du volume principal (+ aile).

    Args:
        wall_depth: épaisseur du mur extérieur (briques: 0.112)
        floor_height_actual: hauteur réelle d'étage
        door_center_x: centre de la porte d'entrée (peut être déplacé)
        window_xs_front/back: centres X des fenêtres avant/arrière
        window_ys_side: centres Y des fenêtres latérales
        wing_frame: repère de l'aile (volumes.wing_frame) ou None
        passage: ouverture de passage vers l'aile (dict) ou None
    """
    W, L = props.house_width, props.house_length
    t = wall_depth
    if layout is None:
        layout = interior_layout(props, wall_depth, floor_height_actual,
                                 door_center_x, window_xs_back, window_ys_side)
    tremie = layout.get('tremie')
    plaster = _plaster()
    parquet = _parquet()
    objs = []

    def slab_with_hole(bm, x0, y0, z0, x1, y1, z1, hole):
        """Dalle en 4 boîtes autour d'un trou rectangulaire (trémie)."""
        hx0, hy0, hx1, hy1 = hole
        hx0, hx1 = max(x0, hx0), min(x1, hx1)
        hy0, hy1 = max(y0, hy0), min(y1, hy1)
        if hx1 <= hx0 or hy1 <= hy0:
            _add_box(bm, x0, y0, z0, x1, y1, z1)
            return
        if hx0 > x0:
            _add_box(bm, x0, y0, z0, hx0, y1, z1)
        if hx1 < x1:
            _add_box(bm, hx1, y0, z0, x1, y1, z1)
        if hy0 > y0:
            _add_box(bm, hx0, y0, z0, hx1, hy0, z1)
        if hy1 < y1:
            _add_box(bm, hx0, hy1, z0, hx1, y1, z1)

    # --- PLAFONDS + SOLS par étage (volume principal) ---
    # ✅ Le plafond du DERNIER étage passe SOUS le chaperon des murs
    # d'égout (les briques s'arrêtent sous la dalle du toit — sans ce
    # clamp, une fente ouverte sur les combles courait le long des murs)
    bm_c = bmesh.new()
    bm_f = bmesh.new()
    for floor in range(props.num_floors):
        z_top = (floor + 1) * floor_height_actual
        if top_ceiling_z is not None and floor == props.num_floors - 1:
            z_top = min(z_top, top_ceiling_z)
        # ✅ v1.5: trémie d'escalier dans les plafonds intermédiaires
        if tremie is not None and floor < props.num_floors - 1:
            slab_with_hole(bm_c, t, t, z_top - CEILING_T, W - t, L - t, z_top,
                           tremie)
        elif ceiling_profile and floor == props.num_floors - 1:
            # ✅ v1.7: PLAFOND CATHÉDRALE (rampant) au dernier étage —
            # bande suivant la sous-face du toit (monopente / mansarde),
            # au lieu du plafond plat qui gâchait le volume
            pts = [(max(t, min(W - t, x)), z - 0.05) for (x, z) in ceiling_profile]
            for i in range(len(pts) - 1):
                (xa, za), (xb, zb) = pts[i], pts[i + 1]
                if xb - xa < 0.01:
                    continue
                va = [bm_c.verts.new(v) for v in
                      ((xa, t, za), (xb, t, zb), (xb, L - t, zb), (xa, L - t, za))]
                vb = [bm_c.verts.new((v.co.x, v.co.y, v.co.z - CEILING_T))
                      for v in va]
                bm_c.faces.new(va)
                bm_c.faces.new(list(reversed(vb)))
                for k in range(4):
                    m = (k + 1) % 4
                    bm_c.faces.new([va[k], vb[k], vb[m], va[m]])
        else:
            _add_box(bm_c, t, t, z_top - CEILING_T, W - t, L - t, z_top)
        # ✅ Le parquet se pose SUR la dalle de l'opérateur (épaisseur
        # slab_top) — il était enterré 13cm sous elle
        z_floor = floor * floor_height_actual + slab_top
        if tremie is not None and floor >= 1:
            slab_with_hole(bm_f, t, t, z_floor + 0.001, W - t, L - t,
                           z_floor + 0.016, tremie)
        else:
            _add_box(bm_f, t, t, z_floor + 0.001, W - t, L - t, z_floor + 0.016)
    objs.append(_new_mesh_obj("Interior_Ceilings", bm_c, collection,
                              "interior", plaster))
    objs.append(_new_mesh_obj("Interior_Floors", bm_f, collection,
                              "interior", parquet))

    # --- CLOISONS (distribution simple, nudge hors fenêtres) ---
    bm = bmesh.new()
    for floor in range(props.num_floors):
        z0 = floor * floor_height_actual + slab_top + 0.016
        z1 = (floor + 1) * floor_height_actual - CEILING_T
        if top_ceiling_z is not None and floor == props.num_floors - 1:
            z1 = min(z1, top_ceiling_z - CEILING_T)

        # 1. REFEND transversal — positions PARTAGÉES avec l'escalier
        y_refend = layout['y_refend']
        door_pass = layout['door_pass']
        _partition_with_doorway(bm, 'X', y_refend, t, W - t, z0, z1, door_pass)

        # 2. ✅ v1.9: cloisons longitudinales côté arrière (N chambres)
        for xs in layout.get('x_splits', [layout['x_split']]):
            _partition_with_doorway(bm, 'Y', xs, y_refend, L - t,
                                    z0, z1, y_refend + 0.75)

    objs.append(_new_mesh_obj("Interior_Partitions", bm, collection,
                              "interior", plaster))

    # --- AILES: plafonds + sols PAR ÉTAGE (pièce(s) de l'aile) ---
    for wing_frame in (wing_frames or []):
        w, d, h = wing_frame['w'], wing_frame['d'], wing_frame['h']
        floors = wing_frame.get('floors', 1)
        fh = wing_frame.get('fh', h)
        bm = bmesh.new()
        for fl in range(floors):
            z_top = (fl + 1) * fh
            if fl == floors - 1:
                # sous le chaperon des murs d'égout de l'aile (dalle + marge)
                z_top = min(z_top, h - 0.32)
            _add_box(bm, t, t, z_top - CEILING_T, w - t, d, z_top)
            z_floor = fl * fh + (slab_top if fl == 0 else 0.0)
            _add_box(bm, t, t, z_floor + 0.001, w - t, d, z_floor + 0.016)
        bmesh.ops.transform(bm, verts=bm.verts, matrix=wing_frame['M'])
        objs.append(_new_mesh_obj("Wing_Interior", bm, collection,
                                  "interior", plaster))

    print(f"[House] ✓ Intérieurs: plafonds + sols + cloisons "
          f"({props.num_floors} étage(s), {len(wing_frames or [])} aile(s))")
    return objs


# ============================================================
# ✅ ÉLECTRICITÉ — prises et interrupteurs (NF C 15-100)
# ============================================================

def build_electrical(props, collection, layout, wall_depth,
                     floor_height_actual):
    """Prises de courant et interrupteurs sur les parois intérieures.

    NF C 15-100 (repères): axe des prises à 0.25 m du sol fini,
    interrupteur à 1.10 m près de la porte de chaque pièce. Le NOMBRE
    de prises par pièce est réglable (`outlets_per_room`); le séjour
    en reçoit deux de plus (minimum normatif 5 en séjour).
    """
    n_per_room = max(1, int(getattr(props, 'outlets_per_room', 3)))
    W, L = props.house_width, props.house_length
    t = wall_depth
    liner = 0.036                      # nu intérieur (doublage 3.5cm)
    y_refend = layout['y_refend']
    xs = [t] + list(layout.get('x_splits', [])) + [W - t]
    slab_top = norms.DALLE_EP
    z_prise = slab_top + 0.25          # axe prise (NF C 15-100)
    z_inter = slab_top + 1.10          # interrupteur

    mat = _simple_material("House_Socket", (0.96, 0.96, 0.94),
                           roughness=0.4)
    bm = bmesh.new()
    count_p = count_i = 0

    def plaque(cx, cy, cz, wall_axis, sign, switch=False):
        """Plaque 82×82mm + saillie centrale, plaquée sur la paroi.
        wall_axis 'x': paroi ⟂ x (plaque dans le plan yz), sinon ⟂ y."""
        nonlocal count_p, count_i
        s, e = 0.041, 0.012            # demi-plaque, épaisseur
        if wall_axis == 'x':
            _add_box(bm, cx, cy - s, cz - s, cx + sign * e, cy + s, cz + s)
            _add_box(bm, cx + sign * e, cy - s * 0.45, cz - s * 0.45,
                     cx + sign * (e + 0.006), cy + s * 0.45, cz + s * 0.45)
        else:
            _add_box(bm, cx - s, cy, cz - s, cx + s, cy + sign * e, cz + s)
            _add_box(bm, cx - s * 0.45, cy + sign * e, cz - s * 0.45,
                     cx + s * 0.45, cy + sign * (e + 0.006), cz + s * 0.45)
        if switch:
            count_i += 1
        else:
            count_p += 1

    # --- PIÈCES ARRIÈRE (chambres/SdB/WC ou cellules uniformes) ---
    for k in range(len(xs) - 1):
        x0, x1 = xs[k], xs[k + 1]
        if x1 - x0 < 0.6:
            continue
        # prises réparties sur le mur ARRIÈRE de la pièce (nu intérieur)
        y_face = L - t - liner
        for i in range(n_per_room):
            cx = x0 + (x1 - x0) * (i + 1) / (n_per_room + 1)
            plaque(cx, y_face, z_prise, 'y', -1)
        # interrupteur près de la porte (côté pièce du refend)
        door_y = y_refend + PARTITION_T / 2
        plaque(min(x1 - 0.25, x0 + 0.9), door_y, z_inter, 'y', +1,
               switch=True)

    # --- SÉJOUR (devant le refend): n+2 prises + interrupteur entrée ---
    y_face = t + liner
    for i in range(n_per_room + 2):
        cx = t + (W - 2 * t) * (i + 1) / (n_per_room + 3)
        plaque(cx, y_face, z_prise, 'y', +1)
    plaque(min(W - t - 0.3, layout['door_pass'] + 0.35), t + liner,
           z_inter, 'y', +1, switch=True)

    obj = _new_mesh_obj("Electrical_Outlets", bm, collection,
                        "electrical", mat)
    print(f"[House] ✓ Électricité: {count_p} prises + {count_i} "
          f"interrupteurs (NF C 15-100: 0.25m / 1.10m)")
    return [obj]


# ============================================================
# ✅ SECOND ŒUVRE — plinthes et chambranles (niveau rendu client)
# ============================================================

def build_trim(props, collection, wall_depth, floor_height_actual,
               layout, openings_spec):
    """PLINTHES (100×12mm) sur tout le périmètre intérieur et les deux
    faces des cloisons (passages de portes déduits), + CHAMBRANLES
    (habillage 80×12mm) autour de chaque fenêtre côté pièce.

    C'est le second œuvre qui sépare une "maquette" d'un intérieur
    présentable — première chose que l'œil cherche au pied des murs.
    """
    W, L = props.house_width, props.house_length
    t = wall_depth
    liner = 0.036
    ep, hz = 0.012, 0.10          # épaisseur / hauteur de plinthe
    mat = _simple_material("House_Trim", (0.94, 0.94, 0.92),
                           roughness=0.35)
    bm = bmesh.new()
    y_refend = layout['y_refend']
    door_pass = layout['door_pass']

    def _plinth_x(y_face, sgn, x0, x1, z0, gaps):
        """Plinthe le long d'un mur ⟂ y (face à y_face, saillie sgn)."""
        segs = [(x0, x1)]
        for (g0, g1) in gaps:
            segs = [s for seg in segs for s in _cut(seg, g0, g1)]
        for (s0, s1) in segs:
            if s1 - s0 > 0.05:
                _add_box(bm, s0, min(y_face, y_face + sgn * ep), z0,
                         s1, max(y_face, y_face + sgn * ep), z0 + hz)

    def _plinth_y(x_face, sgn, y0, y1, z0, gaps):
        segs = [(y0, y1)]
        for (g0, g1) in gaps:
            segs = [s for seg in segs for s in _cut(seg, g0, g1)]
        for (s0, s1) in segs:
            if s1 - s0 > 0.05:
                _add_box(bm, min(x_face, x_face + sgn * ep), s0, z0,
                         max(x_face, x_face + sgn * ep), s1, z0 + hz)

    def _cut(seg, g0, g1):
        s0, s1 = seg
        if g1 <= s0 or g0 >= s1:
            return [seg]
        out = []
        if g0 > s0:
            out.append((s0, g0))
        if g1 < s1:
            out.append((g1, s1))
        return out

    for floor in range(props.num_floors):
        z0 = floor * floor_height_actual + norms.DALLE_EP + 0.002
        # trous au sol de cet étage (portes/passages de la spec)
        door_gaps_front = [(o['x'] - 0.05, o['x'] + o['width'] + 0.05)
                          for o in openings_spec
                          if o['type'] != 'window' and o['wall'] == 'front'
                          and o.get('floor', 0) == floor]
        gaps_by_wall = {}
        for o in openings_spec:
            if o['type'] == 'window' or o.get('floor', 0) != floor:
                continue
            a = o['x'] if o['wall'] in ('front', 'back') else o['y']
            gaps_by_wall.setdefault(o['wall'], []).append(
                (a - 0.05, a + o['width'] + 0.05))
        # périmètre (nu intérieur)
        _plinth_x(t + liner, +1, t, W - t, z0,
                  gaps_by_wall.get('front', []))
        _plinth_x(L - t - liner, -1, t, W - t, z0,
                  gaps_by_wall.get('back', []))
        _plinth_y(t + liner, +1, t, L - t, z0,
                  gaps_by_wall.get('left', []))
        _plinth_y(W - t - liner, -1, t, L - t, z0,
                  gaps_by_wall.get('right', []))
        # refend transversal (2 faces), passage de porte déduit
        dg = [(door_pass - DOORWAY_W / 2 - 0.05,
               door_pass + DOORWAY_W / 2 + 0.05)]
        _plinth_x(y_refend - PARTITION_T / 2, -1, t, W - t, z0, dg)
        _plinth_x(y_refend + PARTITION_T / 2, +1, t, W - t, z0, dg)
        # cloisons longitudinales (2 faces), porte à y_refend+0.75
        for xs in layout.get('x_splits', []):
            dgx = [(y_refend + 0.75 - DOORWAY_W - 0.05,
                    y_refend + 0.75 + 0.05)]
            _plinth_y(xs - PARTITION_T / 2, -1, y_refend, L - t, z0, dgx)
            _plinth_y(xs + PARTITION_T / 2, +1, y_refend, L - t, z0, dgx)

    # --- CHAMBRANLES de fenêtres (côté pièce) ---
    cb = 0.08
    for o in openings_spec:
        if o['type'] != 'window':
            continue
        z0w, z1w = o['z'] - cb, o['z'] + o['height'] + cb
        if o['wall'] in ('front', 'back'):
            a0, a1 = o['x'] - cb, o['x'] + o['width'] + cb
            yf = t + liner if o['wall'] == 'front' else L - t - liner
            sgn = 1 if o['wall'] == 'front' else -1
            y0f, y1f = sorted((yf, yf + sgn * ep))
            _add_box(bm, a0, y0f, z0w, a1, y1f, z0w + cb)
            _add_box(bm, a0, y0f, z1w - cb, a1, y1f, z1w)
            _add_box(bm, a0, y0f, z0w, a0 + cb, y1f, z1w)
            _add_box(bm, a1 - cb, y0f, z0w, a1, y1f, z1w)
        else:
            a0, a1 = o['y'] - cb, o['y'] + o['width'] + cb
            xf = t + liner if o['wall'] == 'left' else W - t - liner
            sgn = 1 if o['wall'] == 'left' else -1
            x0f, x1f = sorted((xf, xf + sgn * ep))
            _add_box(bm, x0f, a0, z0w, x1f, a1, z0w + cb)
            _add_box(bm, x0f, a0, z1w - cb, x1f, a1, z1w)
            _add_box(bm, x0f, a0, z0w, x1f, a0 + cb, z1w)
            _add_box(bm, x0f, a1 - cb, z0w, x1f, a1, z1w)

    obj = _new_mesh_obj("Interior_Trim", bm, collection, "trim", mat)
    print("[House] ✓ Second œuvre: plinthes + chambranles posés")
    return [obj]
