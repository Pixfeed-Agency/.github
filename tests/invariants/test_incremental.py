# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Régénération incrémentale: preuve d'équivalence (chantier n°5)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""RÉGÉNÉRATION INCRÉMENTALE — l'invariant fondamental:

    build(A) puis regen incrémentale vers B  ==  build(B) directement

pour tout raccourci déclaré dans properties.PROP_TAGS. "Égal" au sens
fort: mêmes objets (noms triés), mêmes comptes de sommets par objet,
mêmes modificateurs. Si un raccourci de tags oublie une dépendance,
c'est ICI que ça casse — pas dans le viewport d'un utilisateur.

Usage:  python3 -m pytest tests/invariants/test_incremental.py -q
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import bpy  # noqa: E402
import importlib  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
try:
    House.register()
except ValueError:
    pass  # déjà enregistré par test_geometry dans la même session pytest

BASE = dict(house_width=9.0, house_length=7.0, num_floors=1,
            floor_height=2.7, roof_type='GABLE', roof_pitch=32.0,
            roof_overhang=0.45, roof_covering='TILES',
            wall_construction_type='SIMPLE',
            include_gutters=True, include_shutters=True,
            window_type='CASEMENT', door_type='SINGLE',
            use_materials=True, auto_lighting=False, random_seed=42,
            include_interiors=True)


def _apply(props, values):
    for k, v in values.items():
        setattr(props, k, v)


def _build_full(values):
    """Scène neuve + build complet."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    _apply(p, values)
    res = bpy.ops.house.generate_auto()
    assert 'FINISHED' in res
    return bpy.data.collections.get("House")


def _signature(collection):
    """Empreinte forte de la scène: nom → (sommets, modificateurs)."""
    sig = {}
    for o in sorted(collection.objects, key=lambda x: x.name):
        nv = len(o.data.vertices) if o.type == 'MESH' else -1
        mods = tuple(sorted(m.type for m in o.modifiers))
        sig[o.name] = (nv, mods)
    return sig


def _incremental_case(base_cfg, change, expected_tags):
    """build(base) → change props → op(invalidate=tags) → signature,
    comparée à build(base+change) direct."""
    from House import properties as props_mod

    coll = _build_full(base_cfg)
    n_before = len(coll.objects)
    p = bpy.context.scene.house_generator
    _apply(p, change)
    # Ce que le diff de snapshot déduirait (vérifié séparément)
    tags = props_mod._changed_tags(p)
    assert tags == set(expected_tags), \
        f"diff de snapshot: {tags} != {set(expected_tags)}"
    res = bpy.ops.house.generate_auto(invalidate=",".join(sorted(tags)))
    assert 'FINISHED' in res
    sig_incr = _signature(bpy.data.collections.get("House"))

    sig_full = _signature(_build_full(dict(base_cfg, **change)))
    assert set(sig_incr) == set(sig_full), (
        "objets divergents — manquants: "
        f"{sorted(set(sig_full) - set(sig_incr))[:8]} / en trop: "
        f"{sorted(set(sig_incr) - set(sig_full))[:8]}")
    diff = [n for n in sig_full if sig_incr[n] != sig_full[n]]
    assert not diff, f"géométrie divergente sur: {diff[:8]}"
    return n_before, sig_incr


def test_incremental_joinery():
    """Changer la couleur des volets ne rejoue que les menuiseries."""
    _incremental_case(dict(BASE),
                      dict(shutter_color=(0.20, 0.30, 0.20)),
                      {'joinery'})


def test_incremental_roof_accessory():
    """Ajouter la cheminée rejoue le domaine toit — et elle apparaît."""
    _, sig = _incremental_case(dict(BASE, include_chimney=False),
                               dict(include_chimney=True),
                               {'roof'})
    assert any(n.startswith("Chimney") for n in sig), \
        "la cheminée n'a pas été créée par la regen incrémentale"


def test_incremental_covering_off():
    """Retirer la couverture supprime bien les tuiles existantes."""
    _, sig = _incremental_case(dict(BASE),
                               dict(roof_covering='NONE'),
                               {'roof'})
    assert not any(n.startswith("Roof_Tiles") for n in sig), \
        "les tuiles auraient dû être supprimées"


def test_unmapped_prop_forces_full():
    """Une prop structurelle (hors carte) invalide 'all'."""
    from House import properties as props_mod
    _build_full(dict(BASE))
    p = bpy.context.scene.house_generator
    p.house_width = 10.5
    assert props_mod._changed_tags(p) == {'all'}


def test_viewport_proxy_toggle():
    """Le proxy suspend les instanciateurs GN dans la vue, pas au rendu."""
    from House import operators_auto as ops_mod
    coll = _build_full(dict(BASE, include_environment=True))
    n = ops_mod.apply_viewport_proxy(coll, True)
    assert n >= 2, "aucun instanciateur lourd trouvé (tuiles + herbe attendus)"
    heavy = [o for o in coll.objects
             if o.name.startswith(ops_mod.PROXY_PREFIXES)]
    assert heavy
    for o in heavy:
        for m in o.modifiers:
            if m.type == 'NODES':
                assert m.show_viewport is False
                assert m.show_render is True
    ops_mod.apply_viewport_proxy(coll, False)
    for o in heavy:
        for m in o.modifiers:
            if m.type == 'NODES':
                assert m.show_viewport is True
