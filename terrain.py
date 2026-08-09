# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Terrain et implantation (chantier TERRAIN)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""TERRAIN & IMPLANTATION — la maison seule, sur une parcelle générée,
ou sur TON terrain.

Trois modes (philosophie House: procédural en socle, slots pour tes
propres meshes, mélange des deux):
- NONE   : maison seule (comportement historique sans environnement);
- AUTO   : PARCELLE paramétrique — dimensions réelles (ex. 40×60 m),
  angle du NORD, pente (%), côté d'accès (allée), haie en limite,
  herbe, position/rotation de la maison SUR la parcelle. Si la
  parcelle est en pente, la maison pose sur une PLATEFORME de
  terrassement avec talus (règle de construction réelle);
- CUSTOM : ton mesh de terrain (slot `terrain_asset`) remplace le sol
  généré — House garde le soleil, la haie et l'allée si tu les veux,
  ou rien (les toggles décident). L'hybride, c'est AUTO + tes assets
  dans les slots d'éléments.

BOUSSOLE & SOLEIL: le nord est un angle de scène; le soleil se règle à
l'HEURE (course est→ouest, élévation d'été tempéré ~lat. 47°N) — la
"lumière de fin d'après-midi" d'un brief devient `sun_hour = 17.5`.

Convention: la MAISON reste à l'origine, alignée aux axes (tout le
moteur en dépend). La parcelle, le nord et le soleil se placent AUTOUR
d'elle via `house_pos_x/y` (position sur la parcelle) et
`house_rotation` appliqués À LA PARCELLE (inverse) — même résultat
visuel, zéro risque sur la géométrie du bâti.
"""

import math

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

from . import norms
from .features import (_add_box, _new_mesh_obj, _simple_material,
                       _scatter_grass, detail_level)


def _parcel_matrix(props):
    """Matrice monde de la parcelle: la maison étant fixe à l'origine,
    la parcelle se place autour (translation inverse de la position
    maison + rotation inverse de son orientation)."""
    rot = -math.radians(getattr(props, 'house_rotation', 0.0))
    px = getattr(props, 'house_pos_x', 0.0)
    py = getattr(props, 'house_pos_y', 0.0)
    W, L = props.house_width, props.house_length
    # centre maison → point (px, py) de la parcelle (repère parcelle
    # centré): parcelle tournée autour du centre maison
    return (Matrix.Translation((W / 2, L / 2, 0))
            @ Matrix.Rotation(rot, 4, 'Z')
            @ Matrix.Translation((-px, -py, 0)))


def sun_direction(props):
    """Euler du soleil depuis l'heure et le nord (course simplifiée,
    latitude tempérée ~47°N, journée d'été)."""
    hour = max(6.0, min(21.0, getattr(props, 'sun_hour', 15.0)))
    north = math.radians(getattr(props, 'parcel_north', 0.0))
    # azimut: 6h = est (90° du nord), 13.5h = sud (180°), 21h = ouest
    frac = (hour - 6.0) / 15.0
    azimuth = math.radians(90.0 + 180.0 * frac) + north
    # élévation: cloche, max ~62° au midi solaire
    elev = math.radians(max(3.0, 62.0 * math.sin(math.pi * frac)))
    return Euler((math.pi / 2 - elev, 0.0, -azimuth - math.pi / 2), 'XYZ')


def build_sun(props, collection):
    """Soleil positionné par heure + nord; chaud le soir/matin."""
    hour = getattr(props, 'sun_hour', 15.0)
    for o in list(bpy.data.objects):
        if o.name.startswith("House_Sun"):
            bpy.data.objects.remove(o, do_unlink=True)
    sun = bpy.data.lights.new("House_Sun", 'SUN')
    low = min(abs(hour - 13.5) / 7.5, 1.0)      # 0 midi → 1 aube/soir
    sun.energy = 4.2 - 2.2 * low * low
    sun.angle = math.radians(0.9 + 1.2 * low)
    sun.color = (1.0, 1.0 - 0.25 * low, 1.0 - 0.48 * low)
    so = bpy.data.objects.new("House_Sun", sun)
    collection.objects.link(so)
    so.rotation_euler = sun_direction(props)
    return so


def build(props, collection, door_x=None, garage_front=None):
    """Construit le terrain selon `terrain_mode`. Retourne les objets."""
    mode = getattr(props, 'terrain_mode', 'AUTO')
    if mode == 'NONE':
        return []
    objs = []
    M = _parcel_matrix(props)
    pw = max(10.0, getattr(props, 'parcel_width', 40.0))
    pl = max(10.0, getattr(props, 'parcel_length', 60.0))
    slope_pct = getattr(props, 'parcel_slope', 0.0)
    W, L = props.house_width, props.house_length

    # --- SLOT terrain utilisateur (mode CUSTOM ou hybride) ---
    from . import slots
    t_asset = slots.slot_object(props, 'terrain_asset')
    if mode == 'CUSTOM' or t_asset is not None:
        if t_asset is not None:
            obj = t_asset.copy()
            obj.name = "Terrain_Custom"
            obj["house_part"] = "ground"
            collection.objects.link(obj)
            objs.append(obj)
            print("[House] ✓ Terrain: mesh utilisateur "
                  f"'{t_asset.name}' posé (slot)")
        else:
            print("[House] Terrain CUSTOM: slot vide — sol non généré "
                  "(modélisez votre terrain ou remplissez le slot)")
        build_sun(props, collection)
        return objs

    # --- PARCELLE AUTO: sol en grille (pente), plateforme + talus ---
    grass_mat = _simple_material("Env_Ground", (0.118, 0.191, 0.061),
                                 roughness=0.95)
    bm = bmesh.new()
    nx = max(8, int(pw / 2.5))
    ny = max(8, int(pl / 2.5))
    slope = slope_pct / 100.0
    # plateforme plate sous la maison (marge 3m), talus au-delà
    plat = (-3.0, -3.0, W + 3.0, L + 3.0)
    Minv = M.inverted()

    def ground_z(wx, wy):
        """z du terrain FINI au point monde: pente naturelle, aplatie
        en PLATEFORME sous la maison avec talus de raccord sur 4m —
        UNIQUE vérité partagée par le sol, l'allée, la haie et l'herbe
        (l'allée calculée sur la pente nue plongeait sous le plateau)."""
        pp = Minv @ Vector((wx, wy, 0))
        z = (pp.y) * slope
        dx = max(plat[0] - wx, wx - plat[2], 0)
        dy = max(plat[1] - wy, wy - plat[3], 0)
        d = math.hypot(dx, dy)
        if d < 4.0:
            z = z * (d / 4.0)              # talus
        return z

    verts = {}
    for ix in range(nx + 1):
        for iy in range(ny + 1):
            lx = -pw / 2 + pw * ix / nx
            ly = -pl / 2 + pl * iy / ny
            wp = M @ Vector((lx, ly, 0))
            verts[(ix, iy)] = bm.verts.new(
                (wp.x, wp.y, ground_z(wp.x, wp.y) - 0.02))
    for ix in range(nx):
        for iy in range(ny):
            bm.faces.new([verts[(ix, iy)], verts[(ix + 1, iy)],
                          verts[(ix + 1, iy + 1)], verts[(ix, iy + 1)]])
    for f in bm.faces:
        f.smooth = True
    objs.append(_new_mesh_obj("Terrain_Parcelle", bm, collection,
                              "ground", grass_mat))

    # --- HAIE en LIMITE de parcelle ---
    if getattr(props, 'include_hedge', True):
        hedge = _simple_material("Env_Hedge", (0.05, 0.11, 0.035),
                                 roughness=0.95)
        bm = bmesh.new()
        hh, ht = 1.5, 0.7
        m = 0.4
        segs = [((-pw / 2 + m, -pl / 2 + m), (pw / 2 - m, -pl / 2 + m)),
                ((pw / 2 - m, -pl / 2 + m), (pw / 2 - m, pl / 2 - m)),
                ((pw / 2 - m, pl / 2 - m), (-pw / 2 + m, pl / 2 - m)),
                ((-pw / 2 + m, pl / 2 - m), (-pw / 2 + m, -pl / 2 + m))]
        for (a, b) in segs:
            pa = M @ Vector((a[0], a[1], 0))
            pb = M @ Vector((b[0], b[1], 0))
            d = pb - pa
            n_ = Vector((-d.y, d.x, 0)).normalized() * (ht / 2)
            za = ground_z(pa.x, pa.y)
            zb = ground_z(pb.x, pb.y)
            quads = [(pa + n_, pa - n_, pb - n_, pb + n_)]
            for base in quads:
                lo_ = [bm.verts.new((v.x, v.y,
                                     (za if i < 2 else zb)))
                       for i, v in enumerate(base)]
                hi_ = [bm.verts.new((v.x, v.y,
                                     (za if i < 2 else zb) + hh))
                       for i, v in enumerate(base)]
                bm.faces.new(hi_)
                for k in range(4):
                    k2 = (k + 1) % 4
                    bm.faces.new([lo_[k], lo_[k2], hi_[k2], hi_[k]])
        objs.append(_new_mesh_obj("Terrain_Haie", bm, collection,
                                  "hedge", hedge))

    # --- ALLÉE gravier depuis le côté d'accès ---
    access = getattr(props, 'parcel_access', 'FRONT')
    gravel = _simple_material("Env_Gravel", (0.55, 0.52, 0.47),
                              roughness=0.95)
    bm = bmesh.new()
    tx = garage_front[0] if garage_front else \
        (door_x if door_x is not None else W / 2)
    # départ MONDE (devant la porte/garage), arrivée = bord de parcelle
    start = Vector((tx, -1.6 if garage_front is None else -0.3, 0))
    s_loc = Minv @ start                      # en espace parcelle
    edge_loc = {'FRONT': Vector((s_loc.x, -pl / 2, 0)),
                'BACK': Vector((s_loc.x, pl / 2, 0)),
                'LEFT': Vector((-pw / 2, s_loc.y, 0)),
                'RIGHT': Vector((pw / 2, s_loc.y, 0))}.get(access)
    edge = M @ edge_loc
    d = edge - start
    steps = max(2, int(d.length / 3.0))
    wway = 2.6
    for i in range(steps):
        a = start + d * (i / steps)
        b = start + d * ((i + 1) / steps)
        seg = b - a
        n_ = Vector((-seg.y, seg.x, 0)).normalized() * (wway / 2)
        za, zb2 = ground_z(a.x, a.y), ground_z(b.x, b.y)
        va = [bm.verts.new((a.x - n_.x, a.y - n_.y, za + 0.005)),
              bm.verts.new((a.x + n_.x, a.y + n_.y, za + 0.005)),
              bm.verts.new((b.x + n_.x, b.y + n_.y, zb2 + 0.005)),
              bm.verts.new((b.x - n_.x, b.y - n_.y, zb2 + 0.005))]
        bm.faces.new(va)
    objs.append(_new_mesh_obj("Terrain_Allee", bm, collection,
                              "driveway", gravel))

    # --- HERBE (touffes GN) dans la parcelle, hors emprise/allée ---
    if detail_level(props) != 'DRAFT' and \
            getattr(props, 'include_grass', True):
        exclude = [(-0.4, -0.4, W + 0.4, L + 0.4),
                   (min(start.x, edge.x) - 1.6, min(start.y, edge.y) - 1.6,
                    max(start.x, edge.x) + 1.6, max(start.y, edge.y) + 1.6)]
        center = M @ Vector((0, 0, 0))
        objs += _scatter_grass(
            collection, center.x, center.y,
            math.hypot(pw, pl) / 2, exclude,
            seed=norms.derive_seed(props, 'herbe'),
            inside=lambda x, y: (abs((Minv @ Vector((x, y, 0))).x)
                                 < pw / 2 - 0.8
                                 and abs((Minv @ Vector((x, y, 0))).y)
                                 < pl / 2 - 0.8),
            z_of=lambda x, y: ground_z(x, y))

    build_sun(props, collection)
    print(f"[House] ✓ Parcelle {pw:.0f}×{pl:.0f}m, nord "
          f"{getattr(props, 'parcel_north', 0):.0f}°, pente "
          f"{slope_pct:.1f}%, accès {access}, soleil "
          f"{getattr(props, 'sun_hour', 15.0):.1f}h")
    return objs
