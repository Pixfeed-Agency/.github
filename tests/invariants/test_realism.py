# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Pack réalisme (textures scannées optionnelles)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""PACK RÉALISME — le scan reconnaît les conventions ambientCG/Poly
Haven, les matériaux basculent sur les scans quand le slot existe, et
retombent en PROCÉDURAL sinon (rien ne casse jamais)."""

import os
import sys
import tempfile

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


def _fake_pack(root):
    """Écrit un set pierre/ minimal (conventions ambientCG) + un hdr."""
    sub = os.path.join(root, "pierre")
    os.makedirs(sub, exist_ok=True)
    img = bpy.data.images.new("t", width=4, height=4)
    for suffix in ("Stone_Color.png", "Stone_Roughness.png",
                   "Stone_NormalGL.png", "Stone_AmbientOcclusion.png"):
        img.filepath_raw = os.path.join(sub, suffix)
        img.file_format = 'PNG'
        img.save()
    # un "ciel" (le scan ne lit pas le contenu, juste l'extension)
    open(os.path.join(root, "sky_test.hdr"), 'wb').write(b"?#RADIANCE\n")


def test_scan_et_bascule_pbr():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import realism, look

    with tempfile.TemporaryDirectory() as root:
        _fake_pack(root)
        found = realism.scan(root)
        assert 'pierre' in found and 'hdri' in found
        maps = found['pierre']
        assert {'color', 'roughness', 'normal', 'ao'} <= set(maps)

        p.realism_dir = root
        mat = look.wall_material((0.7, 0.65, 0.55), 'PIERRE')
        assert mat.name == "House_Pierre_PBR"
        types = {n.type for n in mat.node_tree.nodes}
        assert 'TEX_IMAGE' in types and 'NORMAL_MAP' in types
        imgs = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
        assert len(imgs) >= 3
        # la couleur reste sRGB, les maps techniques en Non-Color
        spaces = {n.image.colorspace_settings.name for n in imgs}
        assert 'Non-Color' in spaces

    # dossier disparu → retombée PROCÉDURALE silencieuse
    mat = look.wall_material((0.7, 0.65, 0.55), 'PIERRE')
    assert mat.name == "House_Pierre"
    assert any(n.type == 'TEX_BRICK' for n in mat.node_tree.nodes)


def test_vide_reste_procedural():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.realism_dir = ""
    from House import realism, look
    assert realism.active(p) == {}
    mat = look.wall_material((0.5, 0.45, 0.38), 'CREPI_FIN')
    assert mat.name == "House_Stucco"


def test_hdri_corrompu_retombe_sur_nishita():
    """Un .hdr illisible ne doit PAS donner un rendu noir: House le
    rejette et repasse au ciel procédural (bug vécu au banc)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import look

    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "pierre"), exist_ok=True)
        with open(os.path.join(root, "bad_sky.hdr"), 'wb') as f:
            f.write(b"#?RADIANCE\n")          # fichier tronqué
        p.realism_dir = root
        look.setup_sky_and_view(30.0, 120.0)
        nt = bpy.context.scene.world.node_tree
        types = {n.type for n in nt.nodes}
        assert 'TEX_SKY' in types, "pas de repli Nishita"
        assert 'TEX_ENVIRONMENT' not in types, \
            "un HDRI illisible a été branché (rendu noir)"


def test_sol_pack_realisme():
    """Le slot 'sol' doit s'appliquer AUSSI en terrain AUTO (il était
    ignoré: terrain.py fabriquait son propre matériau)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import realism

    with tempfile.TemporaryDirectory() as root:
        sub = os.path.join(root, "sol")
        os.makedirs(sub, exist_ok=True)
        img = bpy.data.images.new("g", width=4, height=4)
        for suffix in ("Grass_Color.png", "Grass_Roughness.png"):
            img.filepath_raw = os.path.join(sub, suffix)
            img.file_format = 'PNG'
            img.save()
        p.realism_dir = root
        assert 'sol' in realism.active(p)
        p.house_width, p.house_length = 8.0, 7.0
        p.include_environment = True
        p.terrain_mode = 'AUTO'
        p.include_grass = False
        assert 'FINISHED' in bpy.ops.house.generate_auto()
        names = {m.name for m in bpy.data.materials}
        assert "Env_Ground_PBR" in names, \
            "le sol du terrain AUTO ignore le pack réalisme"
