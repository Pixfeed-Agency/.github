# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Tableau d'ouvertures hétérogènes
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""TABLEAU D'OUVERTURES — le cas du brief: baies 2.40×2.15, fenêtres
1.20×1.40 allège 0.90 et portes multiples SUR LA MÊME FAÇADE."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import bpy  # noqa: E402
import importlib  # noqa: E402
from mathutils import Vector  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
try:
    House.register()
except ValueError:
    pass


def _bb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(q.x for q in pts), max(q.x for q in pts),
            min(q.z for q in pts), max(q.z for q in pts))


def test_facade_mixte_du_brief():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.house_width, p.house_length = 21.0, 7.2
    p.floor_height = 3.10
    p.wall_construction_type = 'SIMPLE'
    p.num_windows_side = 0
    p.include_shutters = True
    p.use_openings_table = True
    rows = [('FRONT', 'DOOR', 1.00, 2.15, 0.0, 2.8),
            ('FRONT', 'SLIDING', 2.40, 2.15, 0.0, 5.6),
            ('FRONT', 'CASEMENT', 1.20, 1.40, 0.90, 14.0),
            ('BACK', 'DOOR', 0.90, 2.05, 0.0, 2.2)]
    for (w_, tp, wd, h, s, pos) in rows:
        it = p.openings_table.add()
        it.wall, it.item_type = w_, tp
        it.width, it.height, it.sill, it.pos = wd, h, s, pos
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    coll = bpy.data.collections["House"]

    sliders = [o for o in coll.objects
               if o.name.startswith("Window_SLIDING")]
    assert len(sliders) == 1
    b = _bb(sliders[0])
    assert abs((b[1] - b[0]) - 2.40) < 0.05, "largeur baie"
    assert abs(b[2] - 0.0) < 0.06 and abs(b[3] - 2.15) < 0.06, \
        f"baie z=[{b[2]:.2f},{b[3]:.2f}] != [0, 2.15]"

    cas = [o for o in coll.objects
           if o.name.startswith("Window_CASEMENT") and 'Sash' not in o.name]
    assert len(cas) == 1
    b = _bb(cas[0])
    assert abs(b[2] - 0.90) < 0.05, \
        f"allège {b[2]:.2f} != 0.90"   # bbox inclut l'appui (-3cm)
    assert abs(b[3] - 2.30) < 0.05, "haut fenêtre 0.90+1.40"

    doors = [o for o in coll.objects
             if o.name.split('.')[0] == 'Door_Frame']
    assert len(doors) >= 2, "porte d'entrée + porte de service"
    # volets UNIQUEMENT sur la battante (pas sur la baie)
    shutters = [o for o in coll.objects if o.name.startswith("Shutter")]
    assert len(shutters) == 2, f"{len(shutters)} battants != 2"
