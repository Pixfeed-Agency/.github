# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Volumétrie: faîtage cible + combles aménagés
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""VOLUMÉTRIE — le brief type longère: le FAÎTAGE CIBLE pilote la
pente, et les combles sont AMÉNAGÉS (plancher, jambettes 1 m, plafond
2,40 m, escalier qui y monte vraiment)."""

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


def _bbz(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(q.z for q in pts), max(q.z for q in pts))


def _build_longere():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.house_width, p.house_length = 7.2, 21.0
    p.floor_height = 3.10
    p.num_floors = 1
    p.roof_type = 'GABLE'
    p.roof_pitch = 45.0
    p.ridge_height_target = 7.80
    p.attic_habitable = True
    p.attic_trusses = True
    p.include_interiors = True
    p.include_balcony = False
    p.include_garage = False
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    return bpy.data.collections["House"]


def test_faitage_cible_et_combles():
    coll = _build_longere()
    objs = {o.name.split('.')[0]: o for o in coll.objects}

    # FAÎTAGE CIBLE: la pente est dérivée pour atteindre 7.80 (le 45°
    # du slider est ignoré — la cote prime)
    roof = objs["Roof_GABLE"]
    z = _bbz(roof)
    assert abs(z[1] - 7.80) < 0.05, f"faîtage {z[1]:.2f} != 7.80"

    # PLANCHER de combles à l'arase (3.10) + 18cm
    floor = objs["Attic_Floor"]
    z = _bbz(floor)
    assert abs(z[0] - 3.10) < 0.02 and abs(z[1] - 3.28) < 0.02, \
        f"plancher combles z=[{z[0]:.2f},{z[1]:.2f}]"
    zf = z[1]

    # JAMBETTES 1.00m + PLAFOND PLAT à 2.40 au-dessus du sol fini
    knee = objs["Attic_KneeWalls_Ceiling"]
    z = _bbz(knee)
    assert abs(z[0] - zf) < 0.02, "jambettes posées sur le sol fini"
    assert abs(z[1] - (zf + 2.40 + 0.05)) < 0.03, \
        f"plafond combles à {z[1]:.2f}"

    # RAMPANTS entre haut de jambette (1.00) et plafond (2.40)
    ramp = objs["Attic_Rampants"]
    z = _bbz(ramp)
    assert abs(z[0] - (zf + 1.00)) < 0.03 and \
        abs(z[1] - (zf + 2.40)) < 0.03, \
        f"rampants z=[{z[0]:.2f},{z[1]:.2f}]"

    # FERMES APPARENTES sous le plafond
    assert "Attic_Trusses" in objs, "entraits demandés absents"

    # RIEN NE PERCE LE TOIT: chaque sommet des combles reste sous le
    # plan des versants (le bug v0: rampants et abouts d'entraits
    # ressortaient à travers les tuiles à mi-pente)
    import math
    slope = (7.80 - 3.10) / 3.6
    for name in ("Attic_Rampants", "Attic_Trusses",
                 "Attic_KneeWalls_Ceiling"):
        o = objs[name]
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            z_roof = 3.10 + min(w.x, 7.2 - w.x) * slope
            assert w.z <= z_roof + 0.02, \
                f"{name}: sommet ({w.x:.2f},{w.z:.2f}) au-dessus du " \
                f"plan du toit ({z_roof:.2f})"

    # ESCALIER: la volée EXISTE (plain-pied + combles = 1 volée) et
    # ses marches ATTEIGNENT le plancher des combles
    steps = objs["Stair_Steps"]
    assert len(steps.data.vertices) > 0, "escalier fantôme (0 marche)"
    z = _bbz(steps)
    assert abs(z[1] - zf) < 0.06, \
        f"l'escalier s'arrête à {z[1]:.2f}, plancher à {zf:.2f}"


def test_combles_off_par_defaut():
    """Sans attic_habitable, AUCUN objet de combles (défauts intacts)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.house_width, p.house_length = 7.2, 21.0
    p.num_floors = 1
    p.roof_type = 'GABLE'
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    coll = bpy.data.collections["House"]
    assert not any(o.name.startswith("Attic") for o in coll.objects)
    # et l'escalier n'existe pas en plain-pied sans combles
    assert not any(o.name.startswith("Stair") for o in coll.objects)
