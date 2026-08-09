# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Photoréalisme maison (v1.28)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""PHOTORÉALISME — la pierre est ASSISÉE, les imperfections photo ne
s'activent qu'au niveau PHOTO (NORMAL bit-identique), et la caméra
photo garde les verticales droites (horizontale + shift)."""

import math
import os
import sys

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


def test_pierre_assisee():
    """Le shader pierre est un appareillage en ASSISES (Brick Texture),
    plus l'opus incertum Voronoï."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from House import look
    mat = look.stone_material()
    types = {n.type for n in mat.node_tree.nodes}
    assert 'TEX_BRICK' in types, "pierre sans assises (Brick manquant)"
    assert 'TEX_VORONOI' not in types, "l'opus incertum est revenu"
    brick = next(n for n in mat.node_tree.nodes if n.type == 'TEX_BRICK')
    rh = brick.inputs['Row Height'].default_value
    bw = brick.inputs['Brick Width'].default_value
    assert bw > rh * 1.5, "moellons pas plus longs que hauts"


def test_imperfections_photo_seulement():
    """PHOTO: roughness bruitée + AO; NORMAL: graphe historique."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    from House import look

    p.detail_level = 'NORMAL'
    mat = look.stucco_material("Test_Stucco_N")
    bsdf = next(n for n in mat.node_tree.nodes
                if n.type == 'BSDF_PRINCIPLED')
    assert not bsdf.inputs['Roughness'].is_linked, \
        "NORMAL ne doit pas avoir de roughness bruitée (baselines!)"
    assert not any(n.type == 'AMBIENT_OCCLUSION'
                   for n in mat.node_tree.nodes)

    p.detail_level = 'PHOTO'
    mat = look.stucco_material("Test_Stucco_P")
    bsdf = next(n for n in mat.node_tree.nodes
                if n.type == 'BSDF_PRINCIPLED')
    assert bsdf.inputs['Roughness'].is_linked, "roughness uniforme"
    types = {n.type for n in mat.node_tree.nodes}
    assert 'AMBIENT_OCCLUSION' in types, "pas de salissure des creux"
    assert 'BEVEL' in types, "pas d'adoucissement d'arêtes"


def test_camera_photo_verticales():
    """Caméra horizontale (verticales droites), shift vertical calculé,
    DOF activée, compositor photo en place."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    p.house_width, p.house_length = 10.0, 12.0
    res = bpy.ops.house.camera_photo(direction='SO')
    assert 'FINISHED' in res
    cam_obj = bpy.context.scene.camera
    assert cam_obj is not None and cam_obj.name == "House_PhotoCam"
    # caméra horizontale: rotation X = 90° exactement
    assert abs(cam_obj.rotation_euler.x - math.pi / 2) < 1e-4, \
        f"caméra pas horizontale ({cam_obj.rotation_euler.x:.3f})"
    cam = cam_obj.data
    assert cam.shift_y > 0.01, "pas de décentrement vertical"
    assert cam.dof.use_dof and abs(cam.dof.aperture_fstop - 8.0) < 0.1
    # développement compositor
    scene = bpy.context.scene
    assert scene.use_nodes
    types = {n.type for n in scene.node_tree.nodes}
    assert 'GLARE' in types and 'LENSDIST' in types, \
        "développement photo absent du compositor"
