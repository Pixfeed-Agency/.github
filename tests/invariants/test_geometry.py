# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Invariants géométriques (chantier qualité n°2)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""INVARIANTS GÉOMÉTRIQUES — ce que l'œil ne voit pas, les maths le voient.

Complément du banc visuel: des propriétés qui doivent être VRAIES pour
toute maison générée, vérifiées par raycasts et mesures sur la scène.

Chaque invariant vient d'un bug réel de l'historique:
- façade solide hors ouvertures  → Boolean qui avalait le garage
- toit étanche vu du ciel        → pans manquants / champ fantôme
- fenêtres ancrées à un mur      → fenêtres flottantes v1.1
- tuiles posées sur leur dalle   → tuiles flottantes / noyées
- escalier qui ATTEINT l'étage   → maths de marches
- trémie réellement percée       → dalles pleines sous l'escalier
- volets sans chevauchement      → z-fighting des battants

Usage:  python3 -m pytest tests/invariants -q
"""

import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import importlib  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
try:
    House.register()
except ValueError:
    pass  # déjà enregistré par un autre module de tests (même session)


# ============================================================
# GÉNÉRATION (une scène par config, mémoïsée pour la session)
# ============================================================

BASE = dict(house_width=9.0, house_length=7.0, num_floors=1,
            floor_height=2.7, roof_type='GABLE', roof_pitch=32.0,
            roof_overhang=0.45, roof_covering='TILES',
            wall_construction_type='BRICK_3D', brick_use_geonodes=True,
            include_gutters=True, include_shutters=True,
            window_type='CASEMENT', door_type='SINGLE',
            use_materials=True, auto_lighting=False, random_seed=42,
            include_interiors=True)

CONFIGS = {
    "gable_bricks": dict(BASE),
    "shed": dict(BASE, roof_type='SHED'),
    "hip": dict(BASE, roof_type='HIP', roof_pitch=30.0),
    "gambrel": dict(BASE, roof_type='GAMBREL', roof_pitch=24.0),
    "stucco": dict(BASE, wall_construction_type='SIMPLE'),
    "wing_L": dict(BASE, house_width=11.0, house_length=7.5,
                   include_wing=True, wing_side='FRONT', wing_width=5.0,
                   wing_depth=4.5, wing_offset=0.3),
    "garage_stucco": dict(BASE, house_width=16.5, house_length=7.2,
                          wall_construction_type='SIMPLE',
                          roof_pitch=42.0, include_garage=True,
                          garage_position='RIGHT', garage_width=5.0,
                          garage_depth=6.0),
    "floors2": dict(BASE, house_width=10.0, house_length=8.0,
                    num_floors=2, include_balcony=True),
}

_generated = {}


def scene_for(name):
    """Génère (une fois) la config et retourne des infos d'inspection."""
    if name in _generated:
        return _generated[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    for k, v in CONFIGS[name].items():
        setattr(p, k, v)
    res = bpy.ops.house.generate_auto()
    assert 'FINISHED' in res, f"{name}: génération échouée"
    deps = bpy.context.evaluated_depsgraph_get()
    info = dict(props=dict(CONFIGS[name]), deps=deps,
                scene=bpy.context.scene)
    _generated.clear()          # une seule scène vivante à la fois
    _generated[name] = info
    return info


def ray(info, origin, direction, dist=100.0):
    """Premier impact (hit, loc, obj) dans la scène évaluée."""
    hit, loc, _n, _i, obj, _m = info["scene"].ray_cast(
        info["deps"], Vector(origin), Vector(direction).normalized(),
        distance=dist)
    return hit, loc, obj


def part_of(obj):
    return (obj.get("house_part") or "") if obj else ""


# ============================================================
# 1. FAÇADE SOLIDE — bande basse (z=0.5) pleine hors porte
#    (le bug du Boolean qui avalait le garage vivait ici)
# ============================================================

@pytest.mark.parametrize("name", ["gable_bricks", "stucco", "garage_stucco"])
def test_facades_solides(name):
    info = scene_for(name)
    p = info["props"]
    W, L = p["house_width"], p["house_length"]
    door_zone = (W / 2 - 1.2, W / 2 + 1.2)   # porte (déplaçable → large)
    trous = []
    x = 0.3
    while x < W - 0.3:
        if not (door_zone[0] < x < door_zone[1]):
            hit, loc, obj = ray(info, (x, -3.0, 0.5), (0, 1, 0), 8.0)
            if not hit or loc.y > 0.6:
                trous.append(round(x, 2))
        x += 0.25
    assert not trous, f"{name}: façade avant percée hors porte en x={trous}"

    # façade du garage-aile (celle que le Boolean avalait)
    if p.get("include_garage"):
        gx0, gx1 = W + 0.3, W + p["garage_width"] - 0.3
        gd = (W + p["garage_width"] / 2 - 1.5, W + p["garage_width"] / 2 + 1.5)
        trous = []
        x = gx0
        while x < gx1:
            if not (gd[0] < x < gd[1]):
                hit, loc, obj = ray(info, (x, -3.0, 0.5), (0, 1, 0), 8.0)
                if not hit or loc.y > 0.6:
                    trous.append(round(x, 2))
            x += 0.25
        assert not trous, f"{name}: façade GARAGE percée en x={trous}"


# ============================================================
# 2. TOIT ÉTANCHE — vu du ciel, on ne voit QUE de la toiture
# ============================================================

ROOFISH = {"roof", "chimney", "roof_window", "garage"}


@pytest.mark.parametrize("name", ["gable_bricks", "shed", "hip", "gambrel",
                                  "wing_L", "garage_stucco"])
def test_toit_etanche(name):
    info = scene_for(name)
    p = info["props"]
    W, L = p["house_width"], p["house_length"]
    fuites = []
    for i in range(8):
        for j in range(6):
            x = 0.4 + (W - 0.8) * i / 7
            y = 0.4 + (L - 0.8) * j / 5
            hit, loc, obj = ray(info, (x, y, 30.0), (0, 0, -1))
            part = part_of(obj)
            if not hit or part not in ROOFISH:
                fuites.append((round(x, 1), round(y, 1),
                               obj.name if obj else None, part))
    assert not fuites, f"{name}: le ciel voit l'intérieur en {fuites[:6]}"


# ============================================================
# 3. FENÊTRES ANCRÉES — chaque menuiserie colle à un plan de mur
# ============================================================

@pytest.mark.parametrize("name", ["gable_bricks", "wing_L", "floors2"])
def test_fenetres_ancrees(name):
    info = scene_for(name)
    p = info["props"]
    W, L = p["house_width"], p["house_length"]
    flottantes = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or part_of(o) != "window":
            continue
        if o.name.startswith(("Window_Sheer",)):
            continue
        c = o.matrix_world.translation if o.location.length else None
        bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
        cx = sum(v.x for v in bb) / 8
        cy = sum(v.y for v in bb) / 8
        d_walls = min(abs(cy - 0.056), abs(cy - L + 0.056),
                      abs(cx - 0.056), abs(cx - W + 0.056))
        # ailes: accepter aussi la proximité d'un plan de mur d'aile
        if d_walls > 0.45:
            near_wing = False
            for wo in bpy.data.objects:
                if wo.name.startswith(("Wing_Walls", "Brick_Walls", "Walls")):
                    wb = [wo.matrix_world @ Vector(v) for v in wo.bound_box]
                    if min(v.x for v in wb) - 0.5 < cx < max(v.x for v in wb) + 0.5 \
                            and min(v.y for v in wb) - 0.5 < cy < max(v.y for v in wb) + 0.5:
                        near_wing = True
            if not near_wing:
                flottantes.append((o.name, round(d_walls, 2)))
    assert not flottantes, f"{name}: menuiseries flottantes {flottantes[:5]}"


# ============================================================
# 4. TUILES SUR LEUR DALLE — les points d'instance collent au plan
# ============================================================

def test_tuiles_sur_dalle_gable():
    info = scene_for("gable_bricks")
    p = info["props"]
    W, L = p["house_width"], p["house_length"]
    o = bpy.data.objects.get("Roof_Tiles")
    assert o is not None and len(o.data.vertices) > 200, "couverture absente"
    from House.materials.brick_geometry import compute_real_wall_height
    h, _ = compute_real_wall_height(p["num_floors"] * p["floor_height"])
    pitch = math.radians(p["roof_pitch"])
    slope = math.tan(pitch)
    ridge_along_y = L >= W
    half = (W / 2) if ridge_along_y else (L / 2)
    hors_plan = 0
    for v in o.data.vertices:
        x, y, z = (o.matrix_world @ v.co)
        d = (half - abs((x if ridge_along_y else y) - half))
        z_plan = h + slope * min(d, half)
        if not (z_plan - 0.15 <= z <= z_plan + 0.30):
            hors_plan += 1
    ratio = hors_plan / len(o.data.vertices)
    assert ratio < 0.02, f"{ratio:.1%} de tuiles hors de leur plan de dalle"


# ============================================================
# 5. ESCALIER — il ATTEINT l'étage, et la TRÉMIE est percée
# ============================================================

def test_escalier_et_tremie():
    info = scene_for("floors2")
    p = info["props"]
    fha = None
    from House.materials.brick_geometry import compute_real_wall_height
    wall_h, _ = compute_real_wall_height(p["num_floors"] * p["floor_height"])
    fha = wall_h / p["num_floors"]
    steps = bpy.data.objects.get("Stair_Steps")
    assert steps is not None, "escalier absent en 2 étages"
    top = max((steps.matrix_world @ Vector(v)).z for v in steps.bound_box)
    attendu = 0.2 + fha
    assert abs(top - attendu) < 0.08, \
        f"l'escalier culmine à {top:.2f}m au lieu de ~{attendu:.2f}m"
    # trémie: un rayon vertical au-dessus de la volée haute doit passer
    # SOUS le niveau de la dalle d'étage avant de toucher quelque chose
    bb = [steps.matrix_world @ Vector(v) for v in steps.bound_box]
    # point DANS la trémie mais AU-DELÀ de la dernière marche (la trémie
    # déborde de 0.15 après la volée)
    cx = max(v.x for v in bb) + 0.08
    cy = (min(v.y for v in bb) + max(v.y for v in bb)) / 2
    hit, loc, obj = ray(info, (cx, cy, fha + 0.15), (0, 0, -1), 5.0)
    assert hit and loc.z < fha - 0.5, \
        f"trémie non percée: premier impact {obj.name if obj else None} " \
        f"à z={round(loc.z, 2) if hit else None}"


# ============================================================
# 6. VOLETS SANS CHEVAUCHEMENT — plus de z-fighting de battants
# ============================================================

def _bbox(o):
    bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
    return (min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb),
            max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))


def test_volets_sans_chevauchement():
    scene_for("gable_bricks")
    shutters = [o for o in bpy.data.objects
                if o.name.startswith("Shutter_") and o.type == 'MESH']
    assert shutters, "volets absents"
    paires = []
    for i, a in enumerate(shutters):
        A = _bbox(a)
        for b in shutters[i + 1:]:
            B = _bbox(b)
            ox = min(A[3], B[3]) - max(A[0], B[0])
            oy = min(A[4], B[4]) - max(A[1], B[1])
            oz = min(A[5], B[5]) - max(A[2], B[2])
            if ox > 0.02 and oy > 0.02 and oz > 0.02:
                paires.append((a.name, b.name))
    assert not paires, f"volets en chevauchement: {paires[:4]}"


# ============================================================
# 7. RIEN SOUS LE SOL — aucune géométrie bâtie sous les fondations
# ============================================================

@pytest.mark.parametrize("name", ["gable_bricks", "wing_L"])
def test_rien_sous_le_sol(name):
    scene_for(name)
    coupables = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or part_of(o) in ("environment", ""):
            continue
        zmin = min((o.matrix_world @ Vector(v)).z for v in o.bound_box)
        if zmin < -0.65:
            coupables.append((o.name, round(zmin, 2)))
    assert not coupables, f"géométrie sous les fondations: {coupables[:5]}"
