# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Mode PROGRAMME: solveur + distribution réelle (chantier n°6)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""MODE PROGRAMME — deux niveaux de preuve:

1. Le SOLVEUR (Python pur): pour tout programme raisonnable, l'emprise
   respecte les bornes constructives et chaque pièce ses minima.
2. La MAISON GÉNÉRÉE: les cloisons existent LÀ où le solveur les a
   posées — comptées par raycast transversal dans la bande arrière.

Usage:  python3 -m pytest tests/invariants/test_programme.py -q
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import importlib  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
from House import programme  # noqa: E402


# ============================================================
# 1. SOLVEUR PUR (sans Blender)
# ============================================================

@pytest.mark.parametrize("bedrooms", [1, 2, 3, 4])
@pytest.mark.parametrize("bathrooms", [1, 2])
@pytest.mark.parametrize("wc", [True, False])
def test_solver_bornes(bedrooms, bathrooms, wc):
    sol = programme.solve(bedrooms, bathrooms, wc_separate=wc,
                          garage='SINGLE')
    p = sol['props']
    assert programme.WIDTH_MIN <= p['house_width'] <= programme.WIDTH_MAX
    assert programme.DEPTH_MIN <= p['house_length'] <= programme.DEPTH_MAX
    n_cells = bedrooms + bathrooms + (1 if wc else 0)
    assert len(sol['cells']) == n_cells
    assert p['num_bedrooms'] == bedrooms
    # chaque cellule a une largeur exploitable
    for c in sol['cells'][:bedrooms]:
        assert c >= programme.W_CHAMBRE_MIN
    for c in sol['cells'][bedrooms:bedrooms + bathrooms]:
        assert c >= programme.W_SDB_MIN


def test_solver_surfaces_minimales():
    sol = programme.solve(3, 1, wc_separate=True, garage='NONE')
    rooms = dict(sol['rooms'])
    for name, s in rooms.items():
        if name.startswith("Chambre"):
            assert s >= 9.0, f"{name}: {s:.1f} m² < 9 m² (mini légal)"
        elif name.startswith("Salle de bain"):
            assert s >= 4.0, f"{name}: {s:.1f} m²"
        elif name == "WC":
            assert s >= 1.2, f"WC: {s:.1f} m²"
    assert rooms["Séjour + cuisine"] >= 30.0


def test_solver_surface_cible():
    """Une surface cible rapproche le total demandé."""
    s_libre = programme.solve(2, 1)['props']
    s_cible = programme.solve(2, 1, surface=130.0)
    total = (s_cible['props']['house_width']
             * s_cible['props']['house_length'])
    total_libre = s_libre['house_width'] * s_libre['house_length']
    assert abs(total - 130.0) <= abs(total_libre - 130.0) + 1e-6


def test_solver_deterministe():
    a = programme.solve(3, 1, True, 'SINGLE')
    b = programme.solve(3, 1, True, 'SINGLE')
    assert a == b


# ============================================================
# 2. MAISON GÉNÉRÉE — les cloisons du programme existent vraiment
# ============================================================

def _generate_programme(**prog):
    import bpy
    try:
        House.register()
    except ValueError:
        pass
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.wall_construction_type = 'SIMPLE'
    for k, v in prog.items():
        setattr(p, k, v)
    res = bpy.ops.house.solve_programme()
    assert 'FINISHED' in res
    return bpy.context


def test_maison_generee_cloisons():
    """3 ch + SdB + WC: 4 cloisons longitudinales, aux bons endroits."""
    import bpy
    from mathutils import Vector
    ctx = _generate_programme(prog_bedrooms=3, prog_bathrooms=1,
                              prog_wc_separate=True, prog_garage='SINGLE')
    p = ctx.scene.house_generator
    sol = programme.solve(3, 1, True, 'SINGLE')
    assert abs(p.house_width - sol['props']['house_width']) < 1e-4
    assert p.programme_active

    W, L = p.house_width, p.house_length
    y_ref = programme.REFEND_RATIO * L
    y_mid = (y_ref + L) / 2 + 0.35   # bande arrière, hors passages
    deps = ctx.evaluated_depsgraph_get()
    scene = ctx.scene

    # Raycast transversal: collecter les x des cloisons longitudinales
    hits, x0 = [], 0.35
    origin = Vector((x0, y_mid, 1.3))
    for _ in range(40):
        hit, loc, _n, _i, obj, _m = scene.ray_cast(
            deps, origin, Vector((1, 0, 0)), distance=W)
        if not hit:
            break
        if obj and obj.name.startswith("Interior_Partitions"):
            hits.append(loc.x)
        origin = Vector((loc.x + 0.12, y_mid, 1.3))

    cells = [float(v) for v in p.programme_cells.split(',')]
    assert len(hits) == len(cells) - 1, (
        f"{len(hits)} cloison(s) trouvée(s), "
        f"{len(cells) - 1} attendue(s) (cellules: {cells})")

    # positions ≈ cumuls des cellules (tolérance: nudge anti-fenêtre)
    t = programme.WALL_T
    scale = (W - 2 * t) / sum(cells)
    acc, expected = t, []
    for c in cells[:-1]:
        acc += c * scale
        expected.append(acc)
    for got, exp in zip(sorted(hits), expected):
        assert abs(got - exp) < 0.80, (
            f"cloison à x={got:.2f}, attendue vers {exp:.2f}")


def test_programme_desactive_redevient_uniforme():
    """programme_active=False → découpage uniforme historique."""
    import bpy
    ctx = _generate_programme(prog_bedrooms=3, prog_bathrooms=1,
                              prog_wc_separate=True, prog_garage='NONE')
    p = ctx.scene.house_generator
    from House.interiors import interior_layout
    lay_prog = interior_layout(p, 0.3, p.floor_height, p.house_width / 2,
                               [], [])
    assert lay_prog['n_rooms'] == 5   # 3 ch + SdB + WC
    p.programme_active = False
    lay_std = interior_layout(p, 0.3, p.floor_height, p.house_width / 2,
                              [], [])
    assert lay_std['n_rooms'] == 3    # num_bedrooms
