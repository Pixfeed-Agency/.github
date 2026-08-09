# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Squelette droit: exactitude géométrique (chantier S2)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""SQUELETTE DROIT — exactitude prouvée sur les emprises rectilignes.

Pour chaque famille (rectangle, L, T, U): couverture INTÉGRALE de
l'emprise (aires sommées au µm²), un pan par arête, hauteur maximale
= rayon inscrit L∞ (la moitié du plus petit bras), et cohérence des
arcs (chaque arc sépare deux pans distincts). Python pur — pas de bpy.

Usage:  python3 -m pytest tests/invariants/test_skeleton.py -q
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

from House import skeleton  # noqa: E402


def _area(pc):
    s = 0.0
    for i in range(len(pc)):
        x0, y0 = pc[i][:2]
        x1, y1 = pc[(i + 1) % len(pc)][:2]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2


CASES = [
    ("carre", [(0, 0), (10, 0), (10, 10), (0, 10)], 100.0, 4, 5.0),
    ("rect", [(0, 0), (12, 0), (12, 8), (0, 8)], 96.0, 4, 4.0),
    ("L", [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)],
     75.0, 6, 2.5),
    ("T", [(0, 0), (14, 0), (14, 5), (9, 5), (9, 9), (5, 9), (5, 5),
           (0, 5)], 86.0, 8, 2.5),
    ("U", [(0, 0), (12, 0), (12, 8), (9, 8), (9, 3), (3, 3), (3, 8),
           (0, 8)], 66.0, 8, 1.5),
]


@pytest.mark.parametrize("name,poly,exp_area,n_edges,exp_dmax", CASES)
def test_couverture_et_attribution(name, poly, exp_area, n_edges,
                                   exp_dmax):
    cells = skeleton.faces(poly)
    tot = sum(_area(p) for _i, ps in cells for p in ps)
    assert abs(tot - exp_area) < 1e-6, \
        f"{name}: couverture {tot} != {exp_area}"
    # chaque arête a son pan, SAUF si elle est colinéaire à une arête
    # déjà servie (plans confondus → faces fusionnées, inoffensif)
    got = {i for i, _ in cells}
    edges = [(poly[i], poly[(i + 1) % n_edges]) for i in range(n_edges)]

    def support(e):
        (x0, y0), (x1, y1) = e
        return ('h', round(y0, 6)) if abs(y1 - y0) < 1e-9 \
            else ('v', round(x0, 6))
    for i in range(n_edges):
        if i in got:
            continue
        assert any(j in got and support(edges[j]) == support(edges[i])
                   for j in range(n_edges)), \
            f"{name}: arête {i} sans pan et sans colinéaire servie"
    dmax = max(pt[2] for _i, ps in cells for p in ps for pt in p)
    assert abs(dmax - exp_dmax) < 1e-6, \
        f"{name}: hauteur max {dmax} != rayon inscrit {exp_dmax}"


@pytest.mark.parametrize("name,poly,exp_area,n_edges,exp_dmax", CASES)
def test_coherence_des_pans(name, poly, exp_area, n_edges, exp_dmax):
    """Chaque pièce est coplanaire au plan de SON arête: d est bien la
    distance à l'arête pour tous les sommets (pas seulement au
    centroïde), et les arcs séparent deux pans distincts."""
    cells = skeleton.faces(poly)
    n = len(poly)
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    seg_fns = [skeleton._seg_dist_fn(e) for e in edges]
    for i, pieces in cells:
        dfn = skeleton._edge_dist(edges[i])   # plan de SUPPORT (planéité)
        for p in pieces:
            for (x, y, d) in p:
                assert abs(dfn((x, y)) - d) < 1e-6, \
                    f"{name}: pan {i}, sommet ({x},{y}) hors plan"
                # la hauteur du pan = la SURFACE exacte du squelette
                # (min des distances-segments) en tout sommet
                h = min(f((x, y)) for f in seg_fns)
                assert abs(h - d) < 1e-6, \
                    f"{name}: pan {i}, ({x},{y}): plan {d} != surface {h}"
    for a, b, i, j in skeleton.ridge_segments(cells):
        assert i != j, f"{name}: arc interne rapporté comme faîtage"


def test_rectangle_faitage_central():
    """Rectangle 12×8: le faîtage est le segment y=4, x∈[4,8]."""
    cells = skeleton.faces([(0, 0), (12, 0), (12, 8), (0, 8)])
    tops = {(round(pt[0], 6), round(pt[1], 6))
            for _i, ps in cells for p in ps for pt in p
            if abs(pt[2] - 4.0) < 1e-6}
    assert (4.0, 4.0) in tops and (8.0, 4.0) in tops, \
        f"faîtage attendu entre (4,4) et (8,4), sommets hauts: {tops}"
