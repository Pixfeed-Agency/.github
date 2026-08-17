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


def test_conventions_bump_cavity_et_ratio():
    """Conventions Quixel/Poliigon (Bump = height, Cavity = AO) et
    textures NON CARRÉES (ratio respecté, sinon pierres déformées)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import realism, look

    with tempfile.TemporaryDirectory() as root:
        sub = os.path.join(root, "pierre")
        os.makedirs(sub, exist_ok=True)
        img = bpy.data.images.new("w", width=64, height=32)   # 2:1
        for suffix in ("Wall_Basecolor.jpg", "Wall_8K_Bump.jpg",
                       "Wall_8K_Cavity.jpg", "Wall_8K_Normal.jpg",
                       "Wall_8K_Roughness.jpg"):
            img.filepath_raw = os.path.join(sub, suffix)
            img.file_format = 'JPEG'
            img.save()
        maps = realism.scan(root)['pierre']
        assert set(maps) == {'color', 'height', 'ao', 'normal',
                             'roughness'}, f"maps manquantes: {set(maps)}"

        p.realism_dir = root
        mat = look.wall_material((0.7, 0.6, 0.5), 'PIERRE')
        mapping = next(n for n in mat.node_tree.nodes
                       if n.type == 'MAPPING')
        sx, _sy, sz = mapping.inputs['Scale'].default_value
        assert abs(sz / sx - 2.0) < 0.01, \
            f"ratio 2:1 non compensé (sz/sx={sz / sx:.2f})"


def test_interrupteur_retour_procedural():
    """L'utilisateur doit TOUJOURS pouvoir revenir au procédural —
    sans perdre le chemin de son dossier de textures."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import realism, look

    with tempfile.TemporaryDirectory() as root:
        _fake_pack(root)
        p.realism_dir = root

        p.use_realism_pack = True
        assert 'pierre' in realism.active(p)
        assert look.wall_material((0.7, 0.6, 0.5),
                                  'PIERRE').name == "House_Pierre_PBR"

        p.use_realism_pack = False          # un seul clic
        assert realism.active(p) == {}, "le pack reste actif"
        assert look.wall_material((0.7, 0.6, 0.5),
                                  'PIERRE').name == "House_Pierre"
        assert p.realism_dir == root, "le chemin a été perdu"


def test_deux_maisons_materiaux_independants():
    """Garder une maison puis en générer une seconde ne doit PAS
    repeindre la première (elles partageaient les datablocks nommés
    canoniquement: House_Stucco, House_Roof…)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.include_environment = False
    p.house_width, p.house_length = 9.0, 8.0
    p.wall_material_color = (0.85, 0.55, 0.35)      # A: terre cuite
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    cA = bpy.data.collections["House"]
    cA.name = "Maison_A"
    walls_a = next(o for o in cA.objects
                   if o.name.split('.')[0] == "Walls")

    def teinte(obj):
        """1re teinte du dégradé du matériau (le vrai porteur de la
        couleur: l'entrée Base Color est reliée, pas brute)."""
        mat = obj.data.materials[0]
        ramp = next(n for n in mat.node_tree.nodes
                    if n.type == 'VALTORGB')
        return tuple(round(c, 4) for c in ramp.color_ramp.elements[0].color)

    teinte_a = teinte(walls_a)

    p.wall_material_color = (0.20, 0.28, 0.60)      # B: bleu
    p.house_width = 12.0
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    cB = bpy.data.collections["House"]
    walls_b = next(o for o in cB.objects
                   if o.name.split('.')[0] == "Walls")

    # la maison A reçoit une COPIE privée (c'est le mécanisme de
    # protection) — ce qui doit être préservé, c'est son APPARENCE
    assert teinte(walls_a) == teinte_a, \
        f"maison A repeinte: {teinte_a} -> {teinte(walls_a)}"
    assert teinte(walls_b) != teinte_a, \
        "la maison B n'a pas pris sa propre couleur"
    assert walls_a.data.materials[0] is not walls_b.data.materials[0], \
        "les deux maisons partagent encore le datablock"


def test_pas_de_materiaux_orphelins():
    """Aucun matériau créé puis laissé sans utilisateur (House_Wall et
    House_Glass l'étaient systématiquement en murs SIMPLE)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.include_environment = False
    p.wall_construction_type = 'SIMPLE'
    assert 'FINISHED' in bpy.ops.house.generate_auto()
    orphelins = sorted(m.name for m in bpy.data.materials
                       if m.users == 0)
    assert not orphelins, f"matériaux orphelins: {orphelins}"
