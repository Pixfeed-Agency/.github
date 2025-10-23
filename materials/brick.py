# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Brick Geometry Generator (ULTIMATE EDITION)
#  Copyright (C) 2025 mvaertan
#
#  AMÉLIORATIONS :
#  - Mesh briques avec chanfreins réalistes
#  - Application correcte des matériaux sur instances
#  - Support couleur unie / présets / matériau custom
#  - Système d'ouvertures pour portes/fenêtres
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math
import random


# ============================================================
# CONFIGURATION DES BRIQUES
# ============================================================

# Dimensions standard d'une brique européenne (en mètres)
BRICK_LENGTH = 0.22      # 22cm
BRICK_HEIGHT = 0.065     # 6.5cm
BRICK_DEPTH = 0.10       # 10cm (épaisseur du mur)

# Espacement mortier
MORTAR_GAP = 0.01        # 1cm entre les briques


# ============================================================
# GÉNÉRATION DES MURS DE LA MAISON EN BRIQUES (OPTIMISÉ)
# ============================================================

def create_brick_3d_material(preset_id, custom_color=None):
    """Crée ou récupère un matériau pour les briques 3D
    
    Args:
        preset_id (str): ID du preset ('BRICK_RED', 'BRICK_PAINTED', etc.)
        custom_color (tuple): Couleur RGBA pour mode COLOR
    
    Returns:
        bpy.types.Material: Le matériau créé
    """
    # Si c'est une couleur unie
    if preset_id == 'BRICK_PAINTED' and custom_color:
        mat_name = f"Brick_Painted_{custom_color[0]:.2f}_{custom_color[1]:.2f}_{custom_color[2]:.2f}"
        
        if mat_name in bpy.data.materials:
            return bpy.data.materials[mat_name]
        
        # Créer un matériau simple coloré
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*custom_color[:3], 1.0)
            bsdf.inputs["Roughness"].default_value = 0.8
            bsdf.inputs["Specular IOR Level"].default_value = 0.3
        
        return mat
    
    # Si c'est un preset
    else:
        # Utiliser les presets du module presets
        from .presets import get_procedural_material
        
        try:
            # Essayer de récupérer le preset
            return get_procedural_material(preset_id)
        except ValueError:
            # Si le preset n'existe pas, créer un matériau par défaut rouge
            print(f"[House] ⚠️ Preset '{preset_id}' non trouvé, utilisation du rouge par défaut")
            
            mat_name = f"Brick_Default_Red"
            if mat_name in bpy.data.materials:
                return bpy.data.materials[mat_name]
            
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            
            bsdf = nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = (0.65, 0.25, 0.15, 1.0)
                bsdf.inputs["Roughness"].default_value = 0.85
                bsdf.inputs["Specular IOR Level"].default_value = 0.3
            
            return mat


def generate_house_walls_bricks(house_width, house_length, total_height, collection, quality='MEDIUM', openings=None, brick_material_mode='PRESET', brick_color=None, brick_preset='BRICK_RED', custom_material=None):
    """Génère les 4 murs extérieurs d'une maison en briques 3D avec instancing
    
    Args:
        house_width (float): Largeur de la maison (axe X)
        house_length (float): Longueur de la maison (axe Y)
        total_height (float): Hauteur totale des murs (tous les étages)
        collection: Collection Blender où ajouter les objets
        quality (str): 'LOW', 'MEDIUM', 'HIGH'
        openings (list): Liste de dictionnaires définissant les ouvertures
        brick_material_mode (str): 'COLOR', 'PRESET', 'CUSTOM'
        brick_color (tuple): Couleur RGBA si mode COLOR
        brick_preset (str): Type de preset si mode PRESET
        custom_material: Matériau Blender personnalisé si mode CUSTOM
        
    Returns:
        list: Liste des objets murs créés
    """
    
    print("\n" + "="*70)
    print("[BrickGeometry] GÉNÉRATION MAISON EN BRIQUES (ULTIMATE EDITION)")
    print("="*70)
    print(f"[BrickGeometry] Dimensions: {house_width}m x {house_length}m x {total_height}m")
    print(f"[BrickGeometry] Qualité: {quality}")
    print(f"[BrickGeometry] Mode matériau: {brick_material_mode}")
    
    # Décider si on utilise l'instancing selon la qualité
    use_instancing = (quality == 'LOW' or quality == 'MEDIUM')
    
    if use_instancing:
        print(f"[BrickGeometry] Mode: INSTANCING (optimisé)")
        return generate_walls_with_instancing(house_width, house_length, total_height, collection, quality, openings, brick_material_mode, brick_color, brick_preset, custom_material)
    else:
        print(f"[BrickGeometry] Mode: GÉOMÉTRIE COMPLÈTE (haute qualité)")
        return generate_walls_full_geometry(house_width, house_length, total_height, collection, quality, openings, brick_material_mode, brick_color, brick_preset, custom_material)


def generate_walls_with_instancing(house_width, house_length, total_height, collection, quality, openings=None, brick_material_mode='PRESET', brick_color=None, brick_preset='BRICK_RED', custom_material=None):
    """Génère les murs avec instancing pour optimiser les performances"""
    
    walls = []
    
    print("\n[BrickGeometry] Création de la brique maître...")
    
    # Créer UNE SEULE brique maître avec mesh amélioré
    brick_master = create_single_brick_mesh_realistic(quality)
    brick_master.name = "Brick_Master"
    
    # ✅ CORRECTION CRITIQUE : Appliquer le matériau AU MESH avant de linker
    brick_material = _get_brick_material(brick_material_mode, brick_color, brick_preset, custom_material)
    if brick_master.data.materials:
        brick_master.data.materials[0] = brick_material
    else:
        brick_master.data.materials.append(brick_material)
    
    print(f"[BrickGeometry] ✓ Matériau '{brick_material.name}' appliqué au master")
    
    # IMPORTANT : Linker AVANT de cacher
    collection.objects.link(brick_master)
    brick_master.hide_set(True)  # Cacher la brique maître
    brick_master.hide_render = True
    
    print(f"[BrickGeometry] ✓ Brique maître créée: {BRICK_LENGTH*100:.1f}cm x {BRICK_DEPTH*100:.1f}cm x {BRICK_HEIGHT*100:.1f}cm")
    
    print("\n[BrickGeometry] Calcul des positions des briques...")
    
    # Calculer les positions de toutes les briques pour les 4 murs
    brick_positions = []
    
    # MUR AVANT
    print("[BrickGeometry] → Mur AVANT (façade)...")
    front_positions = calculate_brick_positions_for_wall(
        house_width, total_height, 
        start_pos=Vector((0, 0, 0)),
        direction='X',
        openings=[o for o in (openings or []) if o.get('wall') == 'front']
    )
    brick_positions.extend(front_positions)
    print(f"[BrickGeometry]   {len(front_positions)} briques")
    
    # MUR ARRIÈRE
    print("[BrickGeometry] → Mur ARRIÈRE...")
    back_positions = calculate_brick_positions_for_wall(
        house_width, total_height,
        start_pos=Vector((0, house_length, 0)),
        direction='X',
        openings=[o for o in (openings or []) if o.get('wall') == 'back']
    )
    brick_positions.extend(back_positions)
    print(f"[BrickGeometry]   {len(back_positions)} briques")
    
    # MUR GAUCHE
    print("[BrickGeometry] → Mur GAUCHE...")
    left_positions = calculate_brick_positions_for_wall(
        house_length, total_height,
        start_pos=Vector((0, 0, 0)),
        direction='Y',
        openings=[o for o in (openings or []) if o.get('wall') == 'left']
    )
    brick_positions.extend(left_positions)
    print(f"[BrickGeometry]   {len(left_positions)} briques")
    
    # MUR DROIT
    print("[BrickGeometry] → Mur DROIT...")
    right_positions = calculate_brick_positions_for_wall(
        house_length, total_height,
        start_pos=Vector((house_width, 0, 0)),
        direction='Y',
        openings=[o for o in (openings or []) if o.get('wall') == 'right']
    )
    brick_positions.extend(right_positions)
    print(f"[BrickGeometry]   {len(right_positions)} briques")
    
    print(f"\n[BrickGeometry] Total positions calculées: {len(brick_positions)}")
    
    # Créer toutes les instances
    print("\n[BrickGeometry] Création des instances de briques...")
    
    for i, (pos, rot) in enumerate(brick_positions):
        instance = bpy.data.objects.new(f"Brick_Instance_{i}", brick_master.data)
        instance.location = pos
        instance.rotation_euler = rot
        instance["house_part"] = "wall"
        collection.objects.link(instance)
        walls.append(instance)
        
        # Variation de couleur légère par instance (via custom properties)
        if quality == 'MEDIUM':
            instance["color_variation"] = random.uniform(0.9, 1.1)
    
    print(f"[BrickGeometry] ✓ {len(brick_positions)} instances créées")
    
    # Créer les couches de mortier (4 rectangles plats) - CORRIGÉ
    print("\n[BrickGeometry] Création des couches de mortier...")
    mortars = create_mortar_layers(house_width, house_length, total_height, collection)
    walls.extend(mortars)
    print(f"[BrickGeometry] ✓ {len(mortars)} couches de mortier")
    
    print("\n" + "="*70)
    print("[BrickGeometry] ✅ MAISON EN BRIQUES GÉNÉRÉE AVEC SUCCÈS!")
    print("="*70)
    print(f"[BrickGeometry] Briques:           {len(brick_positions):,}")
    print(f"[BrickGeometry] Mortier:           {len(mortars)} plans")
    print(f"[BrickGeometry] Total objets:      {len(walls) + 1:,}")
    print(f"[BrickGeometry] Murs:              4 (tous générés)")
    print(f"[BrickGeometry] Ouvertures:        {len(openings or [])} exclues")
    print(f"[BrickGeometry] Matériau:          {brick_material.name}")
    print("="*70 + "\n")
    
    return walls


def generate_walls_full_geometry(house_width, house_length, total_height, collection, quality, openings=None, brick_material_mode='PRESET', brick_color=None, brick_preset='BRICK_RED', custom_material=None):
    """Génère les murs avec géométrie complète (HIGH quality)"""
    
    walls = []
    
    # Obtenir le matériau
    brick_material = _get_brick_material(brick_material_mode, brick_color, brick_preset, custom_material)
    
    # === MUR AVANT (FAÇADE) ===
    print("[BrickGeometry] Mur avant (façade)...")
    wall_front_bricks, wall_front_mortar = generate_brick_wall(
        house_width, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'front']
    )
    wall_front_bricks.name = "Wall_Front_Bricks"
    wall_front_mortar.name = "Wall_Front_Mortar"
    
    # CORRECTION : Le mortier doit être AU MÊME ENDROIT que les briques
    wall_front_bricks.location = Vector((0, 0, 0))
    wall_front_mortar.location = Vector((0, 0, 0))
    wall_front_bricks.rotation_euler = Euler((0, 0, 0), 'XYZ')
    wall_front_mortar.rotation_euler = Euler((0, 0, 0), 'XYZ')
    
    # Appliquer matériau
    if wall_front_bricks.data.materials:
        wall_front_bricks.data.materials[0] = brick_material
    else:
        wall_front_bricks.data.materials.append(brick_material)
    
    wall_front_bricks["house_part"] = "wall"
    wall_front_mortar["house_part"] = "wall"
    collection.objects.link(wall_front_bricks)
    collection.objects.link(wall_front_mortar)
    walls.extend([wall_front_bricks, wall_front_mortar])
    
    # === MUR ARRIÈRE ===
    print("[BrickGeometry] Mur arrière...")
    wall_back_bricks, wall_back_mortar = generate_brick_wall(
        house_width, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'back']
    )
    wall_back_bricks.name = "Wall_Back_Bricks"
    wall_back_mortar.name = "Wall_Back_Mortar"
    
    wall_back_bricks.location = Vector((0, house_length, 0))
    wall_back_mortar.location = Vector((0, house_length, 0))
    wall_back_bricks.rotation_euler = Euler((0, 0, 0), 'XYZ')
    wall_back_mortar.rotation_euler = Euler((0, 0, 0), 'XYZ')
    
    if wall_back_bricks.data.materials:
        wall_back_bricks.data.materials[0] = brick_material
    else:
        wall_back_bricks.data.materials.append(brick_material)
    
    wall_back_bricks["house_part"] = "wall"
    wall_back_mortar["house_part"] = "wall"
    collection.objects.link(wall_back_bricks)
    collection.objects.link(wall_back_mortar)
    walls.extend([wall_back_bricks, wall_back_mortar])
    
    # === MUR GAUCHE ===
    print("[BrickGeometry] Mur gauche...")
    wall_left_bricks, wall_left_mortar = generate_brick_wall(
        house_length, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'left']
    )
    wall_left_bricks.name = "Wall_Left_Bricks"
    wall_left_mortar.name = "Wall_Left_Mortar"
    
    wall_left_bricks.location = Vector((0, 0, 0))
    wall_left_mortar.location = Vector((0, 0, 0))
    wall_left_bricks.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    wall_left_mortar.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    
    if wall_left_bricks.data.materials:
        wall_left_bricks.data.materials[0] = brick_material
    else:
        wall_left_bricks.data.materials.append(brick_material)
    
    wall_left_bricks["house_part"] = "wall"
    wall_left_mortar["house_part"] = "wall"
    collection.objects.link(wall_left_bricks)
    collection.objects.link(wall_left_mortar)
    walls.extend([wall_left_bricks, wall_left_mortar])
    
    # === MUR DROIT ===
    print("[BrickGeometry] Mur droit...")
    wall_right_bricks, wall_right_mortar = generate_brick_wall(
        house_length, total_height, BRICK_DEPTH, quality,
        openings=[o for o in (openings or []) if o.get('wall') == 'right']
    )
    wall_right_bricks.name = "Wall_Right_Bricks"
    wall_right_mortar.name = "Wall_Right_Mortar"
    
    wall_right_bricks.location = Vector((house_width, 0, 0))
    wall_right_mortar.location = Vector((house_width, 0, 0))
    wall_right_bricks.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    wall_right_mortar.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    
    if wall_right_bricks.data.materials:
        wall_right_bricks.data.materials[0] = brick_material
    else:
        wall_right_bricks.data.materials.append(brick_material)
    
    wall_right_bricks["house_part"] = "wall"
    wall_right_mortar["house_part"] = "wall"
    collection.objects.link(wall_right_bricks)
    collection.objects.link(wall_right_mortar)
    walls.extend([wall_right_bricks, wall_right_mortar])
    
    # Calculer statistiques
    total_bricks = calculate_brick_count(house_width, total_height) * 2 + \
                   calculate_brick_count(house_length, total_height) * 2
    
    print(f"[BrickGeometry] ✅ Maison en briques créée!")
    print(f"[BrickGeometry]    Total briques: ~{total_bricks}")
    print(f"[BrickGeometry]    Objets créés: {len(walls)}")
    print(f"[BrickGeometry]    Ouvertures exclues: {len(openings or [])}")
    print(f"[BrickGeometry]    Matériau: {brick_material.name}")
    
    return walls


def _get_brick_material(mode, color, preset, custom_material):
    """Obtient le matériau selon le mode choisi
    
    Args:
        mode (str): 'COLOR', 'PRESET', 'CUSTOM'
        color (tuple): Couleur RGBA
        preset (str): Nom du preset
        custom_material: Matériau Blender custom
        
    Returns:
        bpy.types.Material: Matériau à appliquer
    """
    from .materials import brick
    
    if mode == 'COLOR' and color:
        # Couleur unie
        return brick.create_brick_3d_material('BRICK_PAINTED', custom_color=color)
    elif mode == 'CUSTOM' and custom_material:
        # Matériau personnalisé
        return custom_material
    else:
        # Preset (par défaut)
        return brick.create_brick_3d_material(preset, custom_color=None)


# ============================================================
# CRÉATION DU MESH BRIQUE RÉALISTE
# ============================================================

def create_single_brick_mesh_realistic(quality='MEDIUM'):
    """Crée UNE seule brique RÉALISTE avec chanfreins
    
    Args:
        quality (str): 'LOW', 'MEDIUM', 'HIGH'
        
    Returns:
        bpy.types.Object: Objet brique
    """
    
    mesh = bpy.data.meshes.new("Brick_Master_Mesh")
    bm = bmesh.new()
    
    try:
        # Créer un cube simple
        bmesh.ops.create_cube(bm, size=1.0)
        
        # Mise à l'échelle pour correspondre aux dimensions d'une brique
        scale_matrix = Matrix.Diagonal((BRICK_LENGTH, BRICK_DEPTH, BRICK_HEIGHT, 1.0))
        bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)
        
        # Centrer la brique à l'origine
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((BRICK_LENGTH/2, BRICK_DEPTH/2, BRICK_HEIGHT/2)))
        
        # ✅ AMÉLIORATION : Ajouter des chanfreins réalistes
        if quality in ['MEDIUM', 'HIGH']:
            bevel_amount = 0.001 if quality == 'MEDIUM' else 0.0015  # 1mm ou 1.5mm
            segments = 1 if quality == 'MEDIUM' else 2
            
            # Chanfreiner toutes les arêtes
            edges_to_bevel = list(bm.edges)
            
            if edges_to_bevel:
                bmesh.ops.bevel(
                    bm,
                    geom=edges_to_bevel,
                    offset=bevel_amount,
                    segments=segments,
                    profile=0.5,
                    affect='EDGES'
                )
                print(f"[BrickGeometry] ✓ Chanfreins appliqués : {bevel_amount*1000:.1f}mm, {segments} segments")
        
        # ✅ AMÉLIORATION : Ajouter légère déformation aléatoire (qualité HIGH)
        if quality == 'HIGH':
            for vert in bm.verts:
                # Déformation subtile pour un aspect artisanal
                vert.co.x += random.uniform(-0.0005, 0.0005)
                vert.co.y += random.uniform(-0.0005, 0.0005)
                vert.co.z += random.uniform(-0.0003, 0.0003)
        
        bm.to_mesh(mesh)
        mesh.update()
        
    finally:
        bm.free()
    
    obj = bpy.data.objects.new("Brick_Master", mesh)
    return obj


# Code original pour rétrocompatibilité
def create_single_brick_mesh():
    """Version simple sans chanfreins (rétrocompatibilité)"""
    return create_single_brick_mesh_realistic('LOW')


# ============================================================
# FONCTIONS D'INSTANCING (INCHANGÉES)
# ============================================================

def is_brick_in_opening(brick_x, brick_y, brick_z, brick_width, brick_height, openings):
    """Vérifie si une brique se trouve dans une zone d'ouverture"""
    if not openings:
        return False
    
    brick_x_end = brick_x + brick_width
    brick_z_end = brick_z + brick_height
    
    for opening in openings:
        opening_x = opening.get('x', 0)
        opening_y = opening.get('y', 0)
        opening_z = opening.get('z', 0)
        opening_width = opening.get('width', 0)
        opening_height = opening.get('height', 0)
        
        x_overlap = (brick_x < opening_x + opening_width) and (brick_x_end > opening_x)
        z_overlap = (brick_z < opening_z + opening_height) and (brick_z_end > opening_z)
        
        if x_overlap and z_overlap:
            return True
    
    return False


def calculate_brick_positions_for_wall(wall_length, wall_height, start_pos, direction, openings=None):
    """Calcule toutes les positions de briques pour un mur (AVEC EXCLUSION DES OUVERTURES)"""
    
    positions = []
    
    num_bricks_width = int(wall_length / (BRICK_LENGTH + MORTAR_GAP))
    num_bricks_height = int(wall_height / (BRICK_HEIGHT + MORTAR_GAP))
    
    for row in range(num_bricks_height):
        # Pattern en quinconce
        offset = (BRICK_LENGTH + MORTAR_GAP) / 2 if row % 2 == 1 else 0
        
        for col in range(num_bricks_width + 1):
            # Position le long du mur
            distance_along_wall = col * (BRICK_LENGTH + MORTAR_GAP) + offset
            
            # Ne pas dépasser la longueur
            if distance_along_wall + BRICK_LENGTH > wall_length + 0.05:
                continue
            
            # Hauteur
            z = row * (BRICK_HEIGHT + MORTAR_GAP)
            
            # Calculer position selon direction
            if direction == 'X':
                pos = start_pos + Vector((distance_along_wall, 0, z))
                rot = Euler((0, 0, 0), 'XYZ')
                
                # Vérifier si dans une ouverture
                if is_brick_in_opening(distance_along_wall, start_pos.y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                    continue
                    
            else:  # Y
                pos = start_pos + Vector((0, distance_along_wall, z))
                rot = Euler((0, 0, math.radians(90)), 'XYZ')
                
                # Vérifier si dans une ouverture
                if is_brick_in_opening(start_pos.x, distance_along_wall, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                    continue
            
            positions.append((pos, rot))
    
    return positions


def create_mortar_layers(house_width, house_length, total_height, collection):
    """Crée les couches de mortier pour les 4 murs (CORRIGÉ)"""
    
    mortars = []
    
    # Créer matériau mortier
    from .materials import brick
    mortar_mat = brick.create_mortar_3d_material()
    
    # Mortier avant
    mortar_front = create_flat_mortar_plane(house_width, total_height, BRICK_DEPTH)
    mortar_front.name = "Mortar_Front"
    mortar_front.location = Vector((house_width/2, BRICK_DEPTH/2, total_height/2))
    mortar_front["house_part"] = "wall"
    if mortar_front.data.materials:
        mortar_front.data.materials[0] = mortar_mat
    else:
        mortar_front.data.materials.append(mortar_mat)
    collection.objects.link(mortar_front)
    mortars.append(mortar_front)
    
    # Mortier arrière
    mortar_back = create_flat_mortar_plane(house_width, total_height, BRICK_DEPTH)
    mortar_back.name = "Mortar_Back"
    mortar_back.location = Vector((house_width/2, house_length - BRICK_DEPTH/2, total_height/2))
    mortar_back["house_part"] = "wall"
    if mortar_back.data.materials:
        mortar_back.data.materials[0] = mortar_mat
    else:
        mortar_back.data.materials.append(mortar_mat)
    collection.objects.link(mortar_back)
    mortars.append(mortar_back)
    
    # Mortier gauche
    mortar_left = create_flat_mortar_plane(house_length, total_height, BRICK_DEPTH)
    mortar_left.name = "Mortar_Left"
    mortar_left.location = Vector((BRICK_DEPTH/2, house_length/2, total_height/2))
    mortar_left.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    mortar_left["house_part"] = "wall"
    if mortar_left.data.materials:
        mortar_left.data.materials[0] = mortar_mat
    else:
        mortar_left.data.materials.append(mortar_mat)
    collection.objects.link(mortar_left)
    mortars.append(mortar_left)
    
    # Mortier droit
    mortar_right = create_flat_mortar_plane(house_length, total_height, BRICK_DEPTH)
    mortar_right.name = "Mortar_Right"
    mortar_right.location = Vector((house_width - BRICK_DEPTH/2, house_length/2, total_height/2))
    mortar_right.rotation_euler = Euler((0, 0, math.radians(90)), 'XYZ')
    mortar_right["house_part"] = "wall"
    if mortar_right.data.materials:
        mortar_right.data.materials[0] = mortar_mat
    else:
        mortar_right.data.materials.append(mortar_mat)
    collection.objects.link(mortar_right)
    mortars.append(mortar_right)
    
    return mortars


def create_flat_mortar_plane(width, height, depth):
    """Crée un plan plat pour le mortier"""
    
    mesh = bpy.data.meshes.new("Mortar_Plane_Mesh")
    bm = bmesh.new()
    
    try:
        bmesh.ops.create_cube(bm, size=1.0)
        scale_matrix = Matrix.Diagonal((width, depth, height, 1.0))
        bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)
        
        bm.to_mesh(mesh)
        mesh.update()
        
    finally:
        bm.free()
    
    obj = bpy.data.objects.new("Mortar_Plane", mesh)
    return obj


# ============================================================
# GÉNÉRATION GÉOMÉTRIE COMPLÈTE (pour HIGH quality)
# ============================================================

def generate_brick_wall(width, height, depth=BRICK_DEPTH, quality='MEDIUM', openings=None):
    """Génère UN mur en briques 3D avec toute la géométrie"""
    
    use_variations = (quality in ['MEDIUM', 'HIGH'])
    
    num_bricks_width = int(width / (BRICK_LENGTH + MORTAR_GAP))
    num_bricks_height = int(height / (BRICK_HEIGHT + MORTAR_GAP))
    
    bricks_bm = bmesh.new()
    brick_count = 0
    
    for row in range(num_bricks_height):
        offset = (BRICK_LENGTH + MORTAR_GAP) / 2 if row % 2 == 1 else 0
        
        for col in range(num_bricks_width + 1):
            x = col * (BRICK_LENGTH + MORTAR_GAP) + offset
            y = 0
            z = row * (BRICK_HEIGHT + MORTAR_GAP)
            
            if x + BRICK_LENGTH > width + 0.05:
                continue
            
            # Vérifier si dans une ouverture
            if is_brick_in_opening(x, y, z, BRICK_LENGTH, BRICK_HEIGHT, openings):
                continue
            
            if use_variations:
                x += random.uniform(-0.001, 0.001)
                z += random.uniform(-0.0005, 0.0005)
            
            add_brick_to_bmesh(bricks_bm, x, y, z, BRICK_LENGTH, depth, BRICK_HEIGHT, use_variations)
            brick_count += 1
    
    bricks_mesh = bpy.data.meshes.new("BrickWall_Mesh")
    bricks_bm.to_mesh(bricks_mesh)
    bricks_bm.free()
    
    bricks_obj = bpy.data.objects.new("BrickWall", bricks_mesh)
    
    mortar_obj = create_mortar_base(width, height, depth)
    
    if quality == 'HIGH':
        add_brick_displacement(bricks_obj, strength=0.003)
    
    return bricks_obj, mortar_obj


def add_brick_to_bmesh(bm, x, y, z, length, depth, height, use_variations=True):
    """Ajoute une brique au bmesh"""
    
    if use_variations:
        height_var = height + random.uniform(-0.001, 0.001)
        length_var = length + random.uniform(-0.0008, 0.0008)
    else:
        height_var = height
        length_var = length
    
    v1 = bm.verts.new((x, y, z))
    v2 = bm.verts.new((x + length_var, y, z))
    v3 = bm.verts.new((x + length_var, y + depth, z))
    v4 = bm.verts.new((x, y + depth, z))
    
    v5 = bm.verts.new((x, y, z + height_var))
    v6 = bm.verts.new((x + length_var, y, z + height_var))
    v7 = bm.verts.new((x + length_var, y + depth, z + height_var))
    v8 = bm.verts.new((x, y + depth, z + height_var))
    
    bm.faces.new([v1, v2, v3, v4])
    bm.faces.new([v5, v8, v7, v6])
    bm.faces.new([v1, v5, v6, v2])
    bm.faces.new([v2, v6, v7, v3])
    bm.faces.new([v3, v7, v8, v4])
    bm.faces.new([v4, v8, v5, v1])


def create_mortar_base(width, height, depth):
    """Crée une couche de mortier plate"""
    
    bm = bmesh.new()
    
    w = width + 0.02
    h = height + 0.02
    d = depth
    
    v1 = bm.verts.new((0, 0, 0))
    v2 = bm.verts.new((w, 0, 0))
    v3 = bm.verts.new((w, d, 0))
    v4 = bm.verts.new((0, d, 0))
    
    v5 = bm.verts.new((0, 0, h))
    v6 = bm.verts.new((w, 0, h))
    v7 = bm.verts.new((w, d, h))
    v8 = bm.verts.new((0, d, h))
    
    bm.faces.new([v1, v2, v3, v4])
    bm.faces.new([v5, v8, v7, v6])
    bm.faces.new([v1, v5, v6, v2])
    bm.faces.new([v2, v6, v7, v3])
    bm.faces.new([v3, v7, v8, v4])
    bm.faces.new([v4, v8, v5, v1])
    
    mesh = bpy.data.meshes.new("Mortar_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    
    mortar_obj = bpy.data.objects.new("Mortar", mesh)
    
    return mortar_obj


def add_brick_displacement(obj, strength=0.003):
    """Ajoute un modificateur Displace pour relief"""
    
    tex = bpy.data.textures.new("Brick_Displace_Tex", 'CLOUDS')
    tex.noise_scale = 0.3
    tex.noise_depth = 3
    tex.noise_basis = 'BLENDER_ORIGINAL'
    
    mod = obj.modifiers.new("BrickDisplace", 'DISPLACE')
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    mod.direction = 'NORMAL'


# ============================================================
# STATS ET UTILITAIRES
# ============================================================

def calculate_brick_count(width, height):
    """Calcule le nombre de briques pour un mur"""
    num_width = int(width / (BRICK_LENGTH + MORTAR_GAP))
    num_height = int(height / (BRICK_HEIGHT + MORTAR_GAP))
    
    total = 0
    for row in range(num_height):
        if row % 2 == 1:
            total += num_width + 1
        else:
            total += num_width
    
    return total


def get_brick_dimensions():
    """Retourne les dimensions standards des briques"""
    return {
        'length': BRICK_LENGTH,
        'height': BRICK_HEIGHT,
        'depth': BRICK_DEPTH,
        'mortar_gap': MORTAR_GAP
    }


def print_house_brick_stats(house_width, house_length, total_height):
    """Affiche des statistiques sur la maison en briques"""
    front_back = calculate_brick_count(house_width, total_height) * 2
    left_right = calculate_brick_count(house_length, total_height) * 2
    total = front_back + left_right
    
    dims = get_brick_dimensions()
    
    print("\n" + "="*60)
    print("STATISTIQUES MAISON EN BRIQUES")
    print("="*60)
    print(f"Dimensions maison: {house_width:.2f}m x {house_length:.2f}m x {total_height:.2f}m")
    print(f"Murs avant/arrière: ~{front_back} briques")
    print(f"Murs gauche/droite: ~{left_right} briques")
    print(f"TOTAL: ~{total} briques")
    print(f"Dimensions brique: {dims['length']*100:.1f}cm x {dims['height']*100:.1f}cm x {dims['depth']*100:.1f}cm")
    print(f"Épaisseur mortier: {dims['mortar_gap']*100:.1f}cm")
    print("="*60 + "\n")