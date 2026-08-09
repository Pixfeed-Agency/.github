# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Qualité de maillage (chantier S7)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""QUALITÉ DE MAILLAGE — ce que "propre" veut dire, verrouillé:

- aucune arête à PLUS de 2 faces (les jonctions en T des dormants et
  des dalles trouées ont été reconstruites en anneaux manifold — S7);
- aucun sommet isolé, aucune face d'aire nulle;
- UVs présents sur tout mesh à faces (projection boîte, 1 UV = 1 m).

Usage:  python3 -m pytest tests/invariants/test_mesh_quality.py -q
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(REPO))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import importlib  # noqa: E402

House = importlib.import_module(os.path.basename(REPO))
try:
    House.register()
except ValueError:
    pass

CFG = dict(house_width=9.0, house_length=7.0, num_floors=2,
           roof_type='GABLE', roof_pitch=32.0, roof_covering='TILES',
           wall_construction_type='SIMPLE', include_gutters=True,
           include_shutters=True, include_chimney=True,
           include_balcony=True, window_type='CASEMENT',
           use_materials=True, random_seed=42, include_interiors=True)


def _build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = bpy.context.scene.house_generator
    for k, v in CFG.items():
        setattr(p, k, v)
    res = bpy.ops.house.generate_auto()
    assert 'FINISHED' in res
    return [o for o in bpy.data.collections["House"].objects
            if o.type == 'MESH' and len(o.data.polygons) > 0]


def test_maillage_propre():
    """Pas d'arête >2 faces, pas de sommet isolé, pas de face nulle."""
    offenders = []
    for o in _build():
        bm = bmesh.new()
        bm.from_mesh(o.data)
        over = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        loose = sum(1 for v in bm.verts if not v.link_edges)
        zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
        bm.free()
        if over or loose or zero:
            offenders.append((o.name, over, loose, zero))
    assert not offenders, (
        "maillages sales (nom, arêtes>2f, verts isolés, faces nulles): "
        f"{offenders[:10]}")


def test_uvs_presents():
    """Tout mesh à faces porte une couche UV (projection boîte S7)."""
    sans_uv = [o.name for o in _build() if not o.data.uv_layers]
    assert not sans_uv, f"meshes sans UV: {sans_uv[:12]}"
