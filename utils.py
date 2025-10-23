# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Utilities Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from mathutils import Vector, Matrix
import math


# ============================================================
# FONCTIONS DE CRÉATION D'OBJETS
# ============================================================

def create_mesh_object(name, vertices, faces, collection=None):
    """
    Crée un objet mesh à partir de vertices et faces
    
    Args:
        name (str): Nom de l'objet
        vertices (list): Liste de tuples (x, y, z)
        faces (list): Liste de tuples d'indices de vertices
        collection (bpy.types.Collection): Collection où ajouter l'objet
    
    Returns:
        bpy.types.Object: L'objet créé
    """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    
    # Ajouter à la collection
    if collection:
        collection.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    
    # Créer le mesh
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    
    return obj


def create_box(name, location, dimensions, collection=None):
    """
    Crée une boîte (cube dimensionné)
    
    Args:
        name (str): Nom de l'objet
        location (tuple): Position (x, y, z)
        dimensions (tuple): Dimensions (width, depth, height)
        collection (bpy.types.Collection): Collection où ajouter l'objet
    
    Returns:
        bpy.types.Object: L'objet créé
    """
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (dimensions[0]/2, dimensions[1]/2, dimensions[2]/2)
    
    # Appliquer l'échelle
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # Déplacer vers la collection si spécifiée
    if collection and obj.name not in collection.objects:
        collection.objects.link(obj)
        bpy.context.scene.collection.objects.unlink(obj)
    
    return obj


# ============================================================
# FONCTIONS GÉOMÉTRIQUES
# ============================================================

def calculate_distance_2d(point1, point2):
    """
    Calcule la distance entre deux points en 2D
    
    Args:
        point1 (tuple): Point (x, y)
        point2 (tuple): Point (x, y)
    
    Returns:
        float: Distance
    """
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    return math.sqrt(dx*dx + dy*dy)


def calculate_angle_2d(point1, point2):
    """
    Calcule l'angle entre deux points en 2D
    
    Args:
        point1 (tuple): Point de départ (x, y)
        point2 (tuple): Point d'arrivée (x, y)
    
    Returns:
        float: Angle en radians
    """
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    return math.atan2(dy, dx)


def get_bounding_box(objects):
    """
    Calcule la bounding box d'une liste d'objets
    
    Args:
        objects (list): Liste d'objets Blender
    
    Returns:
        dict: {'min': Vector, 'max': Vector, 'center': Vector, 'size': Vector}
    """
    if not objects:
        return None
    
    min_x = min([obj.location.x - obj.dimensions.x/2 for obj in objects])
    max_x = max([obj.location.x + obj.dimensions.x/2 for obj in objects])
    min_y = min([obj.location.y - obj.dimensions.y/2 for obj in objects])
    max_y = max([obj.location.y + obj.dimensions.y/2 for obj in objects])
    min_z = min([obj.location.z - obj.dimensions.z/2 for obj in objects])
    max_z = max([obj.location.z + obj.dimensions.z/2 for obj in objects])
    
    min_vec = Vector((min_x, min_y, min_z))
    max_vec = Vector((max_x, max_y, max_z))
    center = (min_vec + max_vec) / 2
    size = max_vec - min_vec
    
    return {
        'min': min_vec,
        'max': max_vec,
        'center': center,
        'size': size
    }


def point_in_polygon_2d(point, polygon):
    """
    Vérifie si un point est à l'intérieur d'un polygone (2D)
    Utilise l'algorithme Ray Casting
    
    Args:
        point (tuple): Point (x, y)
        polygon (list): Liste de points [(x1, y1), (x2, y2), ...]
    
    Returns:
        bool: True si le point est dans le polygone
    """
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


# ============================================================
# FONCTIONS DE MATÉRIAUX
# ============================================================

def create_simple_material(name, base_color, roughness=0.7, metallic=0.0):
    """
    Crée un matériau Principled BSDF simple
    
    Args:
        name (str): Nom du matériau
        base_color (tuple): Couleur RGB (r, g, b)
        roughness (float): Rugosité (0-1)
        metallic (float): Métallique (0-1)
    
    Returns:
        bpy.types.Material: Le matériau créé
    """
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    
    # Récupérer le noeud Principled BSDF
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    
    if principled:
        principled.inputs["Base Color"].default_value = (*base_color, 1.0)
        principled.inputs["Roughness"].default_value = roughness
        principled.inputs["Metallic"].default_value = metallic
    
    return mat


def assign_material_to_object(obj, material):
    """
    Assigne un matériau à un objet
    
    Args:
        obj (bpy.types.Object): Objet cible
        material (bpy.types.Material): Matériau à assigner
    """
    if obj.type != 'MESH':
        return
    
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material


def create_material_with_texture(name, texture_path, base_color=(1, 1, 1)):
    """
    Crée un matériau avec texture (pour usage futur)
    
    Args:
        name (str): Nom du matériau
        texture_path (str): Chemin vers la texture
        base_color (tuple): Couleur de base RGB
    
    Returns:
        bpy.types.Material: Le matériau créé
    """
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Nettoyer les noeuds existants
    nodes.clear()
    
    # Créer les noeuds
    node_tex = nodes.new(type='ShaderNodeTexImage')
    node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    
    # Positionner les noeuds
    node_tex.location = (-300, 0)
    node_bsdf.location = (0, 0)
    node_output.location = (300, 0)
    
    # Charger la texture
    try:
        if texture_path in bpy.data.images:
            img = bpy.data.images[texture_path]
        else:
            img = bpy.data.images.load(texture_path)
        node_tex.image = img
    except:
        pass
    
    # Connecter les noeuds
    links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
    links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    
    return mat


# ============================================================
# FONCTIONS DE COLLECTION
# ============================================================

def get_or_create_collection(name, parent=None):
    """
    Récupère ou crée une collection
    
    Args:
        name (str): Nom de la collection
        parent (bpy.types.Collection): Collection parente (optionnel)
    
    Returns:
        bpy.types.Collection: La collection
    """
    if name in bpy.data.collections:
        collection = bpy.data.collections[name]
    else:
        collection = bpy.data.collections.new(name)
        if parent:
            parent.children.link(collection)
        else:
            bpy.context.scene.collection.children.link(collection)
    
    return collection


def move_object_to_collection(obj, collection):
    """
    Déplace un objet vers une collection
    
    Args:
        obj (bpy.types.Object): Objet à déplacer
        collection (bpy.types.Collection): Collection de destination
    """
    # Retirer de toutes les collections actuelles
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    
    # Ajouter à la nouvelle collection
    collection.objects.link(obj)


def delete_collection(name, delete_objects=True):
    """
    Supprime une collection
    
    Args:
        name (str): Nom de la collection
        delete_objects (bool): Supprimer aussi les objets dedans
    """
    if name not in bpy.data.collections:
        return
    
    collection = bpy.data.collections[name]
    
    if delete_objects:
        # Supprimer tous les objets de la collection
        for obj in collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Supprimer la collection
    bpy.data.collections.remove(collection)


# ============================================================
# FONCTIONS DE MODIFICATEURS
# ============================================================

def apply_boolean_modifier(target_obj, tool_obj, operation='DIFFERENCE'):
    """
    Applique un modificateur booléen
    
    Args:
        target_obj (bpy.types.Object): Objet cible
        tool_obj (bpy.types.Object): Objet outil
        operation (str): Type d'opération ('DIFFERENCE', 'UNION', 'INTERSECT')
    
    Returns:
        bool: True si succès
    """
    if target_obj.type != 'MESH':
        return False
    
    # Créer le modificateur
    mod = target_obj.modifiers.new(name=f"Boolean_{tool_obj.name}", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool_obj
    
    # Appliquer le modificateur
    bpy.context.view_layer.objects.active = target_obj
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return True
    except:
        return False


def add_solidify_modifier(obj, thickness=0.1):
    """
    Ajoute un modificateur Solidify
    
    Args:
        obj (bpy.types.Object): Objet cible
        thickness (float): Épaisseur
    
    Returns:
        bpy.types.Modifier: Le modificateur créé
    """
    if obj.type != 'MESH':
        return None
    
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = thickness
    
    return mod


# ============================================================
# FONCTIONS DE MESH
# ============================================================

def extrude_face_along_normal(obj, face_index, distance):
    """
    Extrude une face le long de sa normale
    
    Args:
        obj (bpy.types.Object): Objet mesh
        face_index (int): Index de la face
        distance (float): Distance d'extrusion
    """
    if obj.type != 'MESH':
        return
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    
    # Désélectionner tout
    for face in bm.faces:
        face.select = False
    
    # Sélectionner la face
    if face_index < len(bm.faces):
        bm.faces[face_index].select = True
        bm.faces.active = bm.faces[face_index]
        
        # Extruder
        bmesh.ops.extrude_face_region(bm, geom=[bm.faces[face_index]])
        
        bmesh.update_edit_mesh(mesh)
    
    bpy.ops.object.mode_set(mode='OBJECT')


def subdivide_mesh(obj, cuts=1):
    """
    Subdivise un mesh
    
    Args:
        obj (bpy.types.Object): Objet mesh
        cuts (int): Nombre de coupes
    """
    if obj.type != 'MESH':
        return
    
    mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    mod.levels = cuts
    mod.render_levels = cuts


# ============================================================
# FONCTIONS UTILITAIRES DIVERSES
# ============================================================

def select_objects(objects, deselect_others=True):
    """
    Sélectionne une liste d'objets
    
    Args:
        objects (list): Liste d'objets à sélectionner
        deselect_others (bool): Désélectionner les autres objets
    """
    if deselect_others:
        bpy.ops.object.select_all(action='DESELECT')
    
    for obj in objects:
        obj.select_set(True)
    
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def safe_delete_object(obj):
    """
    Supprime un objet en toute sécurité
    
    Args:
        obj (bpy.types.Object): Objet à supprimer
    """
    if obj and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)


def clean_unused_data():
    """
    Nettoie les données non utilisées (meshes, materials, etc.)
    """
    # Nettoyer les meshes
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    
    # Nettoyer les matériaux
    for material in bpy.data.materials:
        if material.users == 0:
            bpy.data.materials.remove(material)
    
    # Nettoyer les images
    for image in bpy.data.images:
        if image.users == 0:
            bpy.data.images.remove(image)


def get_3d_cursor_location():
    """
    Récupère la position du curseur 3D
    
    Returns:
        Vector: Position du curseur
    """
    return bpy.context.scene.cursor.location.copy()


def set_3d_cursor_location(location):
    """
    Définit la position du curseur 3D
    
    Args:
        location (tuple ou Vector): Position (x, y, z)
    """
    bpy.context.scene.cursor.location = location


# ============================================================
# CLASSES (vide pour l'instant, mais prêt pour le futur)
# ============================================================

classes = (
    # Pas de classes pour l'instant
)


def register():
    """Enregistrement (pas de classes pour l'instant)"""
    pass


def unregister():
    """Désenregistrement (pas de classes pour l'instant)"""
    pass