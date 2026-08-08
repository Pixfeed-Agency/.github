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

PARTITION_T = 0.08     # épaisseur cloison (placo)
DOORWAY_W = 0.93       # passage de porte standard
DOORWAY_H = 2.04
CEILING_T = 0.06


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


def build_interiors(props, collection, wall_depth, floor_height_actual,
                    door_center_x, window_xs_front, window_xs_back,
                    window_ys_side, wing_frame=None, passage=None,
                    top_ceiling_z=None, slab_top=0.2):
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
    plaster = _plaster()
    parquet = _parquet()
    objs = []

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
        _add_box(bm_c, t, t, z_top - CEILING_T, W - t, L - t, z_top)
        # ✅ Le parquet se pose SUR la dalle de l'opérateur (épaisseur
        # slab_top) — il était enterré 13cm sous elle
        z_floor = floor * floor_height_actual + slab_top
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

        # 1. REFEND transversal (mur à y = ~55% de la profondeur):
        # sépare la pièce de vie (côté entrée) des chambres.
        y_refend = _avoid(L * 0.55, window_ys_side, 0.75, L * 0.35, L * 0.7)
        # passage aligné sur la porte d'entrée (circulation naturelle)
        door_pass = _avoid(door_center_x, [], 0, t + 0.7, W - t - 0.7)
        _partition_with_doorway(bm, 'X', y_refend, t, W - t, z0, z1, door_pass)

        # 2. Cloison de REFEND longitudinal côté arrière: deux pièces.
        forbidden = list(window_xs_back)
        x_split = _avoid(W * 0.5, forbidden, 0.75, W * 0.3, W * 0.7)
        _partition_with_doorway(bm, 'Y', x_split, y_refend, L - t, z0, z1,
                                (y_refend + L - t) / 2)

    objs.append(_new_mesh_obj("Interior_Partitions", bm, collection,
                              "interior", plaster))

    # --- AILE: plafond + sol (pièce unique: suite) ---
    if wing_frame is not None:
        w, d, h = wing_frame['w'], wing_frame['d'], wing_frame['h']
        bm = bmesh.new()
        # sous le chaperon des murs d'égout de l'aile (dalle + marge)
        _add_box(bm, t, t, h - CEILING_T - 0.32, w - t, d, h - 0.32)
        _add_box(bm, t, t, slab_top + 0.001, w - t, d, slab_top + 0.016)
        bmesh.ops.transform(bm, verts=bm.verts, matrix=wing_frame['M'])
        objs.append(_new_mesh_obj("Wing_Interior", bm, collection,
                                  "interior", plaster))

    print(f"[House] ✓ Intérieurs: plafonds + sols + cloisons "
          f"({props.num_floors} étage(s){', aile' if wing_frame else ''})")
    return objs
