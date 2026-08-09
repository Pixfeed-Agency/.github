# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Plan 2D unifié: union d'emprises (chantier S1, noyau)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""PLAN 2D UNIFIÉ — l'union maison+ailes est UN contour propre.

Python pur (aucun bpy). La chaîne complète plan2d → skeleton est
vérifiée: n'importe quelle emprise rectiligne connexe donne un toit
qui couvre exactement l'emprise.

Usage:  python3 -m pytest tests/invariants/test_plan2d.py -q
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

from House import plan2d, skeleton  # noqa: E402


def _area(pc):
    s = 0.0
    for i in range(len(pc)):
        x0, y0 = pc[i][:2]
        x1, y1 = pc[(i + 1) % len(pc)][:2]
        s += x0 * y1 - x1 * y0
    return s / 2      # signée: >0 = CCW


def test_rectangle_seul():
    c = plan2d.union_rects([(0, 0, 10, 7)])
    assert c == [(0.0, 0.0), (10.0, 0.0), (10.0, 7.0), (0.0, 7.0)]


def test_aile_pleine_largeur_fusionnee():
    """Deux rectangles bord à bord → UN rectangle (colinéaires fondus)."""
    c = plan2d.union_rects([(0, 0, 10, 7), (10, 0, 14, 7)])
    assert len(c) == 4 and abs(_area(c) - 98.0) < 1e-9


def test_creneau_et_u_ccw():
    for rects, n, aire in [
        ([(0, 0, 10, 7), (2, -4, 7, 0)], 8, 90.0),               # créneau
        ([(0, 0, 12, 7), (0, -4, 4, 0), (8, -4, 12, 0)], 8, 116.0),  # U
        ([(0, 0, 10, 7), (10, 2, 14, 6)], 8, 86.0),              # T couché
    ]:
        c = plan2d.union_rects(rects)
        assert len(c) == n, f"{rects}: {len(c)} sommets"
        assert abs(_area(c) - aire) < 1e-9      # CCW ET aire exacte


def test_non_connexe_refuse():
    with pytest.raises(ValueError):
        plan2d.union_rects([(0, 0, 2, 2), (5, 5, 7, 7)])


@pytest.mark.parametrize("rects,aire", [
    ([(0, 0, 10, 7), (2, -4, 7, 0)], 90.0),
    ([(0, 0, 12, 7), (0, -4, 4, 0), (8, -4, 12, 0)], 116.0),
    ([(0, 0, 9, 7), (3, 7, 7, 12), (9, 1, 12, 5)], 95.0),
])
def test_chaine_plan_vers_squelette(rects, aire):
    """N'importe quelle emprise → toit squelette couvrant EXACTEMENT."""
    contour = plan2d.union_rects(rects)
    cells = skeleton.faces(contour)
    tot = sum(abs(_area(p)) for _i, ps in cells for p in ps)
    assert abs(tot - aire) < 1e-6, f"couverture {tot} != {aire}"
    assert [i for i, _ in cells] == list(range(len(contour)))
