# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Graines dérivées (chantier S6)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""GRAINES DÉRIVÉES — les deux propriétés qui comptent:

1. REPRODUCTIBLE: même random_seed → maison STRICTEMENT identique
   (positions et rotations de tuiles au bit près).
2. NON-JUMELLES: random_seed différents → micro-variations différentes
   (avant S6, toutes les maisons partageaient les mêmes seeds 42/4242/
   777 → patines et jitters identiques côte à côte).

Usage:  python3 -m pytest tests/invariants/test_seeds.py -q
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import bpy  # noqa: E402
import importlib  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
try:
    House.register()
except ValueError:
    pass

from House.norms import derive_seed  # noqa: E402

CFG = dict(house_width=9.0, house_length=7.0, num_floors=1,
           roof_type='GABLE', roof_pitch=32.0, roof_covering='TILES',
           wall_construction_type='SIMPLE', use_materials=True,
           include_interiors=False)


def _tile_rots(seed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    for k, v in dict(CFG, random_seed=seed).items():
        setattr(p, k, v)
    res = bpy.ops.house.generate_auto()
    assert 'FINISHED' in res
    obj = next(o for o in bpy.data.collections["House"].objects
               if o.name.startswith("Roof_Tiles"))
    attr = obj.data.attributes["tile_rot"]
    out = [0.0] * (len(attr.data) * 3)
    attr.data.foreach_get('vector', out)
    return tuple(out)


def test_derive_seed_stable_et_distincte():
    """FNV stable entre sessions; labels/base distincts → seeds ≠."""
    class P:
        random_seed = 42
    assert derive_seed(P, 'tuiles') == derive_seed(P, 'tuiles')
    assert derive_seed(P, 'tuiles') != derive_seed(P, 'lucarnes')

    class P2:
        random_seed = 43
    assert derive_seed(P, 'tuiles') != derive_seed(P2, 'tuiles')


def test_meme_graine_meme_maison():
    """Reproductibilité stricte: mêmes rotations de tuiles au bit près."""
    assert _tile_rots(42) == _tile_rots(42)


def test_graines_differentes_pas_jumelles():
    """random_seed 42 vs 43: les micro-jitters de tuiles diffèrent."""
    assert _tile_rots(42) != _tile_rots(43), \
        "deux maisons de graines différentes sont encore JUMELLES"
