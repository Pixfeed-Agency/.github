# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Slots d'assets + finitions procédurales (chantier n°7)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""SLOTS D'ASSETS — l'invariant: OPTIONNELS, jamais obligatoires.

- Slot rempli → l'asset remplace la menuiserie, mis à l'échelle exacte
  de l'ouverture (bbox vérifiée), articulations conservées (volets).
- Slot vide → menuiseries procédurales habituelles (repli).
- Objet généré par House dans un slot → refusé (il serait détruit à la
  régénération suivante).
- Finitions procédurales: le matériau change réellement.

Usage:  python3 -m pytest tests/invariants/test_assets.py -q
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
    pass

CFG = dict(house_width=9.0, house_length=7.0, num_floors=1,
           roof_type='GABLE', roof_pitch=32.0, roof_covering='TILES',
           wall_construction_type='SIMPLE', include_gutters=True,
           include_shutters=True, window_type='CASEMENT',
           door_type='SINGLE', use_materials=True, random_seed=42,
           include_interiors=True)


def _cube(name, dims=(1.0, 0.4, 2.0)):
    """Cube-témoin (8 sommets, 6 faces) hors collection House."""
    me = bpy.data.meshes.new(name)
    w, d, h = dims
    verts = [(x, y, z) for x in (0, w) for y in (0, d) for z in (0, h)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _fresh(**extra):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    for k, v in dict(CFG, **extra).items():
        setattr(p, k, v)
    return p


def _gen():
    res = bpy.ops.house.generate_auto()
    assert 'FINISHED' in res
    return bpy.data.collections.get("House")


def _named(coll, prefix):
    return [o for o in coll.objects if o.name.startswith(prefix)]


def test_slots_remplis_remplacent():
    """Assets branchés: fenêtres/porte/volets/tuile viennent de l'asset."""
    p = _fresh()
    p.window_asset = _cube("MaFenetre")
    p.door_asset = _cube("MaPorte")
    p.shutter_asset = _cube("MonVolet", dims=(0.5, 0.04, 1.2))
    p.tile_asset = _cube("MaTuile", dims=(0.3, 0.45, 0.05))
    coll = _gen()

    wins = _named(coll, "Window_Asset")
    assert wins, "aucune fenêtre instanciée depuis l'asset"
    assert not _named(coll, "Window_CASEMENT"), \
        "les fenêtres procédurales n'auraient pas dû être construites"
    # échelle exacte de l'ouverture (bbox = largeur × hauteur)
    w0 = wins[0]
    assert abs(w0.dimensions.x - p.window_width) < 0.02 or \
        abs(w0.dimensions.y - p.window_width) < 0.02
    assert abs(w0.dimensions.z
               - (p.floor_height * 0.6)) < p.floor_height * 0.35

    assert _named(coll, "Door_Asset"), "porte asset absente"
    assert not _named(coll, "Door_Frame"), "porte procédurale présente"

    shutters = _named(coll, "Shutter_")
    assert shutters, "volets absents"
    for s in shutters:
        assert len(s.data.vertices) == 8, \
            "battant ≠ copie du cube asset (8 sommets attendus)"
        assert "fermeture" in s.keys(), "articulation perdue sur l'asset"

    master = _named(coll, "Tile_Master")
    assert master and len(master[0].data.polygons) == 6, \
        "le master de tuile n'est pas le mesh de l'asset"


def test_slots_vides_procedural():
    """Slots vides: menuiseries procédurales habituelles (repli)."""
    _fresh()
    coll = _gen()
    assert _named(coll, "Window_CASEMENT")
    assert _named(coll, "Door_Frame")
    assert not _named(coll, "Window_Asset")
    assert not _named(coll, "Door_Asset")
    master = _named(coll, "Tile_Master")
    assert master and len(master[0].data.polygons) > 6  # tuile galbée


def test_objet_house_refuse():
    """Un objet généré par House est refusé par le slot (anti-cycle)."""
    from House import slots
    _fresh()
    coll = _gen()
    p = bpy.context.scene.house_generator
    win = _named(coll, "Window_CASEMENT")[0]
    try:
        p.window_asset = win     # le poll UI le refuse déjà…
    except Exception:
        pass
    assert slots.slot_object(p, 'window_asset') is None, \
        "un objet généré par House ne doit JAMAIS être accepté comme asset"


def test_finitions_procedurales():
    """wall_finish/roof_finish changent réellement les matériaux."""
    _fresh(wall_finish='LISSE', roof_finish='ARDOISE')
    coll = _gen()
    walls = [o for o in coll.objects if o.get("house_part") == "wall"
             and o.data.materials]
    assert walls
    assert any(m and m.name.startswith("House_Wall_Lisse")
               for o in walls for m in o.data.materials), \
        "finition LISSE non appliquée aux murs"
    master = _named(coll, "Tile_Master")[0]
    assert master.data.materials[0].name.startswith("House_Tile_Ardoise"), \
        f"finition ARDOISE absente ({master.data.materials[0].name})"

    # crépi projeté: le nom reste House_Stucco mais le grain change
    _fresh(wall_finish='CREPI_GROS')
    _gen()
    mat = bpy.data.materials.get("House_Stucco")
    assert mat is not None
    scales = [n.inputs['Scale'].default_value
              for n in mat.node_tree.nodes if n.type == 'TEX_NOISE']
    assert any(abs(s - 95.0) < 1.0 for s in scales), \
        "le grain GROS (scale 95) n'est pas dans l'arbre de House_Stucco"


def test_asset_fallback_sur_mesh_plat():
    """Asset dégénéré (plat) → repli procédural, pas de crash."""
    p = _fresh()
    flat = _cube("Plat", dims=(1.0, 0.4, 2.0))
    for v in flat.data.vertices:
        v.co.z = 0.0             # aplati → bbox z nulle
    p.window_asset = flat
    coll = _gen()
    assert _named(coll, "Window_CASEMENT"), \
        "le repli procédural n'a pas fonctionné sur asset plat"
    assert not _named(coll, "Window_Asset")
