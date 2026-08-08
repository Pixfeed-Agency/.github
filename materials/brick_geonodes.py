# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Brick Walls via Geometry Nodes (Blender 4.2+)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

"""✅ NOUVEAU MOTEUR: Murs de briques via Geometry Nodes

Au lieu de créer des MILLIERS d'objets Blender (une instance par brique —
l'anti-pattern qui fait ramer le viewport et exploser l'outliner), ce
moteur crée:

  - 1 SEUL objet "nuage de points" (un vertex par brique, avec la
    rotation stockée en attribut)
  - 1 modificateur Geometry Nodes de 6 nodes qui instancie la brique
    maître sur chaque point

Résultat: même géométrie visuelle, mais UN objet au lieu de milliers,
mémoire quasi nulle (vraies instances GPU) et viewport fluide.

Le calcul des positions (murs adaptés au toit, pignons, linteaux,
ouvertures, patterns) reste la logique PARTAGÉE de brick_geometry —
seule la matérialisation change.
"""

import bpy

from . import brick_geometry


NODE_GROUP_NAME = "House_Brick_Instancer"
ROT_ATTR = "brick_rot"


def _build_instancer_node_group(brick_master):
    """Construit le node group d'instanciation.

    Arbre (6 nodes):
        Group Input ─▶ Mesh to Points ─▶ Instance on Points ─▶ Group Output
                           Rotation ◀── Named Attribute 'brick_rot'
                           Instance ◀── Object Info (brique maître)

    ✅ FIX: Un groupe NEUF par génération (Blender suffixe .001 si besoin).
    L'ancienne réutilisation par nom supprimait le groupe de la maison
    précédente → son modificateur perdait son node_group (murs invisibles).
    """
    ng = bpy.data.node_groups.new(NODE_GROUP_NAME, 'GeometryNodeTree')

    # Interface (API Blender 4.x)
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    n_in = ng.nodes.new('NodeGroupInput')
    n_in.location = (-600, 0)

    n_pts = ng.nodes.new('GeometryNodeMeshToPoints')
    n_pts.location = (-400, 0)
    n_pts.mode = 'VERTICES'

    n_obj = ng.nodes.new('GeometryNodeObjectInfo')
    n_obj.location = (-400, -220)
    n_obj.transform_space = 'ORIGINAL'
    n_obj.inputs['Object'].default_value = brick_master
    if 'As Instance' in n_obj.inputs:
        n_obj.inputs['As Instance'].default_value = True

    n_attr = ng.nodes.new('GeometryNodeInputNamedAttribute')
    n_attr.location = (-400, -420)
    n_attr.data_type = 'FLOAT_VECTOR'
    n_attr.inputs['Name'].default_value = ROT_ATTR

    n_inst = ng.nodes.new('GeometryNodeInstanceOnPoints')
    n_inst.location = (-150, 0)

    n_out = ng.nodes.new('NodeGroupOutput')
    n_out.location = (100, 0)

    links = ng.links
    links.new(n_in.outputs['Geometry'], n_pts.inputs['Mesh'])
    links.new(n_pts.outputs['Points'], n_inst.inputs['Points'])
    links.new(n_obj.outputs['Geometry'], n_inst.inputs['Instance'])
    links.new(n_attr.outputs['Attribute'], n_inst.inputs['Rotation'])
    links.new(n_inst.outputs['Instances'], n_out.inputs['Geometry'])

    return ng


def generate_walls_geonodes(
    house_width,
    house_length,
    total_height,
    collection,
    quality,
    openings=None,
    brick_material_mode='PRESET',
    brick_color=None,
    brick_preset='BRICK_RED',
    custom_material=None,
    roof_type='GABLE',
    roof_pitch=35.0,
    mortar_color=None,
    bonding_pattern='RUNNING'
):
    """Génère les murs de briques via Geometry Nodes (1 objet total)

    Même signature et même retour (walls, real_wall_height) que
    generate_walls_with_instancing — interchangeable.
    """
    print("\n" + "=" * 70)
    print("[BrickGN] GÉNÉRATION MURS BRIQUES — MOTEUR GEOMETRY NODES")
    print("=" * 70)

    # 1. Positions D'ABORD (logique partagée: murs adaptés au toit + linteaux)
    # ✅ FIX: Calculées avant de créer le master — un early-return sur liste
    # vide laissait un Brick_Master orphelin dans la collection
    brick_positions = brick_geometry.compute_all_brick_positions(
        house_width, house_length, total_height,
        openings=openings, roof_type=roof_type,
        roof_pitch=roof_pitch, bonding_pattern=bonding_pattern)

    if not brick_positions:
        print("[BrickGN] ⚠️ Aucune position de brique calculée")
        real_wall_height, _ = brick_geometry.compute_real_wall_height(total_height)
        return [], real_wall_height

    # 2. Brique maître + matériaux (logique partagée)
    # ✅ FIX CRITIQUE: keep_evaluated=True — hide_viewport retirait le
    # master du depsgraph et le node Object Info sortait une géométrie
    # VIDE (murs GN invisibles!)
    brick_master = brick_geometry.create_brick_master(
        collection, quality, brick_material_mode, brick_color,
        brick_preset, custom_material, mortar_color,
        keep_evaluated=True)

    # 3. Nuage de points: 1 vertex par brique
    mesh = bpy.data.meshes.new("Brick_Walls_Points")
    mesh.from_pydata([tuple(pos) for pos, _rot in brick_positions], [], [])
    mesh.update()

    # Rotation par brique stockée en attribut vectoriel (radians XYZ)
    attr = mesh.attributes.new(ROT_ATTR, 'FLOAT_VECTOR', 'POINT')
    flat = []
    for _pos, rot in brick_positions:
        flat.extend((rot.x, rot.y, rot.z))
    attr.data.foreach_set('vector', flat)

    walls_obj = bpy.data.objects.new("Brick_Walls_GN", mesh)
    walls_obj["house_part"] = "wall"
    collection.objects.link(walls_obj)

    # 4. Modificateur Geometry Nodes (6 nodes)
    mod = walls_obj.modifiers.new("BrickInstancer", 'NODES')
    mod.node_group = _build_instancer_node_group(brick_master)

    real_wall_height, num_rows = brick_geometry.compute_real_wall_height(total_height)

    print(f"[BrickGN] ✓ {len(brick_positions):,} briques instanciées via GN")
    print(f"[BrickGN] ✓ 1 objet (au lieu de {len(brick_positions):,}!)")
    print(f"[BrickGN] ✓ Hauteur réelle: {real_wall_height:.3f}m ({num_rows} rangées)")
    print("=" * 70 + "\n")

    return [walls_obj], real_wall_height
