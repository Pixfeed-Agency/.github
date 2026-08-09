# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Normes de façade et électricité (audit v1.21)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""AUDIT v1.21 — les mesures automatiques verrouillées:

- LINTEAUX ALIGNÉS: le haut de chaque fenêtre = 2.15 (norme façade),
  plus jamais au-dessus de la porte (le bug "fenêtres trop hautes");
- VOILAGE côté pièce (il pendait DEVANT la façade);
- PORTE DE GARAGE remplissant son ouverture (fente noire de 21cm);
- ÉLECTRICITÉ NF C 15-100: prises à 0.25m, interrupteurs à 1.10m,
  nombre paramétrable par pièce.

Usage:  python3 -m pytest tests/invariants/test_facade_norms.py -q
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

from House import norms  # noqa: E402


def _build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.wall_construction_type = 'SIMPLE'
    p.prog_bedrooms = 3
    p.prog_bathrooms = 1
    p.prog_wc_separate = True
    p.prog_garage = 'SINGLE'
    p.include_electrical = True
    p.outlets_per_room = 3
    p.random_seed = 42
    assert 'FINISHED' in bpy.ops.house.solve_programme()
    return bpy.data.collections["House"], p


def _bb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(q.x for q in pts), max(q.x for q in pts),
            min(q.y for q in pts), max(q.y for q in pts),
            min(q.z for q in pts), max(q.z for q in pts))


def test_mesures_de_facade():
    coll, p = _build()
    for o in coll.objects:
        n = o.name.split('.')[0]
        if n == 'Window_CASEMENT':
            top = _bb(o)[5]
            assert abs(top - norms.LINTEAU_H) < 0.02, \
                f"{o.name}: linteau à {top:.2f} != {norms.LINTEAU_H}"
        elif n == 'Window_Sheer':
            b = _bb(o)
            if b[4] < 1.0 and b[2] < 1.0:   # façade avant
                assert b[2] > 0.1, \
                    f"voilage DEVANT la façade (y={b[2]:.2f})"
        elif n == 'Garage_Door':
            b = _bb(o)
            assert b[4] < 0.25 and b[5] > 2.2, \
                f"porte de garage ne remplit pas l'ouverture: z=[{b[4]:.2f},{b[5]:.2f}]"


def test_electricite_nfc15100():
    coll, p = _build()
    elec = [o for o in coll.objects
            if o.name.startswith("Electrical_Outlets")]
    assert elec, "objet électricité absent"
    me = elec[0].data
    zs = sorted({round(v.co.z, 2) for v in me.vertices})
    z_prise = norms.DALLE_EP + 0.25
    z_inter = norms.DALLE_EP + 1.10
    assert any(abs(z - (z_prise - 0.041)) < 0.03 for z in zs), \
        f"aucune prise à l'axe 0.25m (z vus: {zs[:6]})"
    assert any(abs(z - (z_inter + 0.041)) < 0.03 for z in zs), \
        "aucun interrupteur à 1.10m"
    # nombre paramétrable: 5 pièces × 3 + séjour (3+2) = 20 prises
    # → 20 plaques + 20 saillies + 6 interrupteurs ×2 boîtes = 52 boîtes
    n_boxes = len(me.polygons) // 6
    assert n_boxes == 52, f"{n_boxes} boîtes != 52 attendues"
