# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Maçonnerie de pierre (encadrements, chaînages)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""MAÇONNERIE DE PIERRE — encadrements et chaînages, en vraie géométrie.

Sur une façade en pierre réelle, chaque ouverture est cernée de PIERRE
DE TAILLE (jambages, linteau monolithe, appui saillant) et les angles
du bâti sont tenus par des CHAÎNAGES à harpes alternées. C'est ce qui
sépare "un mur avec un shader pierre" d'une façade en pierre.

Tout dérive de la SPEC D'OUVERTURES S4 — donc compatible avec le
tableau d'ouvertures (types/tailles/positions libres) et le mode auto.
"""

import bmesh

from .features import _add_box, _new_mesh_obj

JAMB_W = 0.16          # largeur des jambages
LINTEAU_H = 0.24       # hauteur du linteau monolithe
APPUI_H = 0.12         # hauteur de l'appui saillant
SAILLIE = 0.025        # saillie devant le nu du mur
HARPE_H = 0.34         # hauteur d'une assise de chaînage
HARPE_L1 = 0.42        # harpe longue
HARPE_L2 = 0.26        # harpe courte (alternance)
HARPE_EP = 0.020       # saillie du chaînage (4,5cm faisait
#                        des bosses Lego au soleil rasant)


def build_surrounds(props, collection, spec, wall_depth):
    """Encadrements pierre de taille autour de chaque ouverture
    EXTÉRIEURE de la maison principale (spec S4)."""
    from . import look
    W, L = props.house_width, props.house_length
    mat = look.cut_stone_material()
    bm = bmesh.new()
    n = 0
    for o in spec:
        if o.get('type') == 'passage':
            continue
        wall = o['wall']
        z0, z1 = o['z'], o['z'] + o['height']
        a0 = (o['x'] if wall in ('front', 'back') else o['y'])
        a1 = a0 + o['width']
        is_door = o['type'] == 'door'

        def frame_boxes(face, sgn):
            """face = coordonnée du nu extérieur; sgn = sens de la
            saillie (vers l'extérieur)."""
            f0, f1 = sorted((face, face + sgn * SAILLIE))
            if wall in ('front', 'back'):
                # jambages
                _add_box(bm, a0 - JAMB_W, f0, z0 - (0 if is_door else 0),
                         a0, f1, z1 + 0.02)
                _add_box(bm, a1, f0, z0, a1 + JAMB_W, f1, z1 + 0.02)
                # linteau
                _add_box(bm, a0 - JAMB_W, f0, z1 + 0.02,
                         a1 + JAMB_W, f1, z1 + 0.02 + LINTEAU_H)
                # appui saillant (fenêtres seulement)
                if not is_door:
                    ff0, ff1 = sorted((face, face + sgn * (SAILLIE + 0.02)))
                    _add_box(bm, a0 - JAMB_W - 0.02, ff0, z0 - APPUI_H,
                             a1 + JAMB_W + 0.02, ff1, z0)
            else:
                _add_box(bm, f0, a0 - JAMB_W, z0, f1, a0, z1 + 0.02)
                _add_box(bm, f0, a1, z0, f1, a1 + JAMB_W, z1 + 0.02)
                _add_box(bm, f0, a0 - JAMB_W, z1 + 0.02,
                         f1, a1 + JAMB_W, z1 + 0.02 + LINTEAU_H)
                if not is_door:
                    ff0, ff1 = sorted((face, face + sgn * (SAILLIE + 0.02)))
                    _add_box(bm, ff0, a0 - JAMB_W - 0.02, z0 - APPUI_H,
                             ff1, a1 + JAMB_W + 0.02, z0)

        if wall == 'front':
            frame_boxes(0.0, -1)
        elif wall == 'back':
            frame_boxes(L, +1)
        elif wall == 'left':
            frame_boxes(0.0, -1)
        else:
            frame_boxes(W, +1)
        n += 1
    if n:
        _new_mesh_obj("Stone_Surrounds", bm, collection, "masonry", mat)
        print(f"[House] ✓ Encadrements pierre de taille: {n} ouvertures")
    else:
        bm.free()
    return []


def build_quoins(props, collection, wall_height):
    """Chaînages d'angle à HARPES alternées aux 4 angles du bâti."""
    from . import look
    W, L = props.house_width, props.house_length
    mat = look.cut_stone_material()
    bm = bmesh.new()
    e = HARPE_EP
    z = 0.0
    row = 0
    while z + HARPE_H <= wall_height + 0.01:
        long_x = HARPE_L1 if row % 2 == 0 else HARPE_L2
        long_y = HARPE_L2 if row % 2 == 0 else HARPE_L1
        for (cx, sx) in ((0.0, +1), (W, -1)):
            for (cy, sy) in ((0.0, +1), (L, -1)):
                # harpe côté X (sur les façades avant/arrière)
                _add_box(bm,
                         min(cx, cx + sx * long_x), cy - (e if sy > 0 else 0),
                         z,
                         max(cx, cx + sx * long_x), cy + (e if sy < 0 else 0)
                         + (0 if sy < 0 else 0), z + HARPE_H - 0.012)
                # harpe côté Y (sur les pignons)
                _add_box(bm,
                         cx - (e if sx > 0 else 0), min(cy, cy + sy * long_y),
                         z,
                         cx + (e if sx < 0 else 0),
                         max(cy, cy + sy * long_y), z + HARPE_H - 0.012)
        z += HARPE_H
        row += 1
    _new_mesh_obj("Stone_Quoins", bm, collection, "masonry", mat)
    print(f"[House] ✓ Chaînages d'angle: {row} assises × 4 angles")
    return []
