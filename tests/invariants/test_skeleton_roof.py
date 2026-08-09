# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Toit squelette: étanchéité sur emprise en L (chantier S2)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""TOIT SQUELETTE (roof_type SKELETON) — l'invariant décisif: sur une
emprise en L (maison + aile), une grille de rayons zénithaux couvrant
L'EMPRISE UNIFIÉE ne touche QUE du toit. L'aile n'a ni toit propre ni
pignon maçonné (le squelette couvre tout en croupe).

Usage:  python3 -m pytest tests/invariants/test_skeleton_roof.py -q
"""

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


def test_toit_squelette_etanche_sur_L():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    for k, v in dict(house_width=11.0, house_length=7.5, num_floors=1,
                     roof_type='SKELETON', roof_pitch=32.0,
                     roof_covering='TILES',
                     wall_construction_type='SIMPLE',
                     include_wing=True, wing_side='FRONT',
                     wing_width=5.0, wing_depth=4.5, wing_offset=0.3,
                     include_gutters=True, random_seed=42,
                     include_interiors=True).items():
        setattr(p, k, v)
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    coll = bpy.data.collections["House"]
    names = {o.name.split('.')[0] for o in coll.objects}
    assert "Roof_Skeleton" in names and "Roof_Valleys" in names \
        and "Roof_Hips" in names, f"objets toit manquants: {names}"
    assert "Wing_Roof" not in names, \
        "l'aile sous squelette ne doit PAS avoir de toit propre"

    deps = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    leaks = []
    for gx in range(1, 21):
        for gy in range(1, 15):
            x = 0.4 + 10.2 * gx / 21
            y = -4.5 + 11.4 * gy / 15
            inside = (0.3 < x < 10.7 and 0.3 < y < 7.2) or \
                     (0.6 < x < 5.0 and -4.2 < y < -0.3)
            if not inside:
                continue
            hit, _l, _n, _i, obj, _m = sc.ray_cast(
                deps, Vector((x, y, 30)), Vector((0, 0, -1)), distance=40)
            part = (obj.get("house_part") or obj.name) if obj else ""
            if not hit or ("roof" not in str(part)
                           and not obj.name.startswith(("Roof", "Tile"))):
                leaks.append((round(x, 1), round(y, 1), str(part)))
    assert not leaks, f"fuites zénithales: {leaks[:8]}"
