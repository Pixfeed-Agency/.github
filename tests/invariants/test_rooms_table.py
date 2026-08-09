# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Tableau de pièces
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""TABLEAU DE PIÈCES — les surfaces du brief pilotent le refend, les
cloisons, les rôles (SdB au bon endroit) et une fenêtre par pièce."""

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

ROWS = [("Chambre 1", 'CHAMBRE', 12.0),
        ("Chambre 2", 'CHAMBRE', 10.0),
        ("Salle d'eau", 'SDB', 6.0),
        ("WC", 'WC', 2.5)]


def _setup(p):
    p.house_width, p.house_length = 12.0, 10.0
    p.num_floors = 1
    p.roof_type = 'GABLE'
    p.wall_construction_type = 'SIMPLE'
    p.include_interiors = True
    p.include_furnishing = True
    p.use_rooms_table = True
    for (nm, tp, s) in ROWS:
        it = p.rooms_table.add()
        it.name, it.room_type, it.surface = nm, tp, s


def test_layout_surfaces():
    """Refend et cloisons dérivés des surfaces demandées."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    _setup(p)
    from House import interiors
    t = 0.3
    lay = interiors.interior_layout(p, t, 2.7, 3.0, [], [])
    W, L = 12.0, 10.0
    total = sum(s for (_n, _t, s) in ROWS)          # 30.5 m²
    depth_wanted = total / (W - 2 * t)              # ≈ 2.68 m
    # y_refend recule pour loger la somme (clampé à [0.35L, 0.7L])
    want = max(L * 0.35, min(L * 0.7, L - t - depth_wanted))
    assert abs(lay['y_refend'] - want) < 0.4, \
        f"y_refend {lay['y_refend']:.2f} != {want:.2f}"
    # cellules proportionnelles aux surfaces
    xs = [t] + list(lay['x_splits']) + [W - t]
    assert len(xs) - 1 == 4
    widths = [xs[i + 1] - xs[i] for i in range(4)]
    inner = W - 2 * t
    for w_, (_n, _t2, s) in zip(widths, ROWS):
        expect = inner * s / total
        assert abs(w_ - expect) < 0.35, \
            f"largeur {w_:.2f} vs {expect:.2f} pour {s}m²"
    assert lay['rooms'][2]['role'] == 'sdb'
    assert lay['rooms'][3]['role'] == 'wc'


def test_sdb_dans_la_bonne_cellule():
    """La douche/vasque est bâtie DANS la cellule déclarée SdB."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    _setup(p)
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    coll = bpy.data.collections["House"]
    bath = [o for o in coll.objects
            if o.name.startswith("Bathroom_Fixtures")]
    assert bath, "sanitaires absents"
    pts = [bath[0].matrix_world @ Vector(c) for c in bath[0].bound_box]
    cx = (min(q.x for q in pts) + max(q.x for q in pts)) / 2
    # cellule SdB = 3e cellule: après ~12+10 m² sur 30.5 de 11.4m utile
    total = sum(s for (_n, _t, s) in ROWS)
    inner = 12.0 - 0.6
    x_lo = 0.3 + inner * (12.0 + 10.0) / total - 0.4
    x_hi = 0.3 + inner * (12.0 + 10.0 + 6.0) / total + 0.4
    assert x_lo < cx < x_hi, \
        f"SdB à x={cx:.2f}, attendue dans [{x_lo:.2f},{x_hi:.2f}]"
