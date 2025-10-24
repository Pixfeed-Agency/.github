# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Doors Module (BLENDER 4.2+)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math

# Constantes pour portes réalistes
DOOR_FRAME_DEPTH = 0.10         # 10cm - Profondeur du dormant
DOOR_THICKNESS = 0.04           # 4cm - Épaisseur d'une porte standard
DOOR_FRAME_WIDTH = 0.06         # 6cm - Largeur du cadre
DOOR_HANDLE_HEIGHT = 1.05       # 1.05m - Hauteur de la poignée


class DoorGenerator:
    """Générateur de portes architecturales réalistes

    Supporte:
    - Qualité LOW/MEDIUM/HIGH
    - Types: SINGLE, DOUBLE, SLIDING, FRENCH
    - Matériaux procéduraux
    """

    def __init__(self, quality='MEDIUM'):
        """Initialise le générateur avec un niveau de qualité

        Args:
            quality (str): 'LOW', 'MEDIUM', ou 'HIGH'
        """
        self.quality = quality
        self.frame_depth = DOOR_FRAME_DEPTH
        self.door_thickness = DOOR_THICKNESS

        # Paramètres adaptatifs selon la qualité
        if quality == 'LOW':
            self.frame_width = 0.08
            self.panel_segments = 1
            self.bevel_amount = 0.0
        elif quality == 'MEDIUM':
            self.frame_width = 0.06
            self.panel_segments = 2
            self.bevel_amount = 0.002
        else:  # HIGH
            self.frame_width = 0.05
            self.panel_segments = 4
            self.bevel_amount = 0.003

        print(f"[Doors] Qualité: {quality} - Frame: {self.frame_width*1000}mm")

    def generate_door(self, door_type, width, height, location, orientation, collection):
        """Point d'entrée principal pour générer une porte complète

        Args:
            door_type (str): Type de porte (SINGLE, DOUBLE, SLIDING, FRENCH)
            width (float): Largeur de l'ouverture
            height (float): Hauteur de l'ouverture
            location (Vector): Position dans l'espace
            orientation (str): Orientation du mur (front, back, left, right)
            collection: Collection Blender où ajouter les objets

        Returns:
            list: Liste des objets créés
        """

        # Validation
        if width <= 0 or height <= 0:
            print(f"[Doors] ERREUR: Dimensions invalides ({width}x{height})")
            return []

        print(f"[Doors] Génération porte {door_type}: {width}x{height}m à {location}")

        # Générer selon le type
        if door_type == 'SINGLE':
            objects = self._create_single_door(width, height, location, orientation, collection)
        elif door_type == 'DOUBLE':
            objects = self._create_double_door(width, height, location, orientation, collection)
        elif door_type == 'SLIDING':
            objects = self._create_sliding_door(width, height, location, orientation, collection)
        elif door_type == 'FRENCH':
            objects = self._create_french_door(width, height, location, orientation, collection)
        else:
            print(f"[Doors] Type '{door_type}' non reconnu, utilisation SINGLE par défaut")
            objects = self._create_single_door(width, height, location, orientation, collection)

        return objects

    def _create_single_door(self, width, height, location, orientation, collection):
        """Crée une porte simple battant"""
        objects = []

        # Cadre de porte
        frame = self._create_door_frame(width, height, orientation)
        frame.name = "Door_Frame"
        frame.location = location
        collection.objects.link(frame)
        objects.append(frame)

        # Panneau de porte
        panel = self._create_door_panel(width - self.frame_width * 2, height - self.frame_width, orientation)
        panel.name = "Door_Panel"

        # Positionner le panneau
        panel_offset = self._get_panel_offset(width, orientation, 'single')
        panel.location = location + panel_offset
        collection.objects.link(panel)
        objects.append(panel)

        # Appliquer matériaux
        self._apply_door_materials(frame, panel)

        return objects

    def _create_double_door(self, width, height, location, orientation, collection):
        """Crée une porte double battant"""
        objects = []

        # Cadre de porte
        frame = self._create_door_frame(width, height, orientation)
        frame.name = "Door_Frame_Double"
        frame.location = location
        collection.objects.link(frame)
        objects.append(frame)

        # Panneau gauche
        panel_width = (width - self.frame_width * 3) / 2  # Divisé par 2 + montant central
        panel_left = self._create_door_panel(panel_width, height - self.frame_width, orientation)
        panel_left.name = "Door_Panel_Left"

        offset_left = self._get_panel_offset(width, orientation, 'double_left')
        panel_left.location = location + offset_left
        collection.objects.link(panel_left)
        objects.append(panel_left)

        # Panneau droit
        panel_right = self._create_door_panel(panel_width, height - self.frame_width, orientation)
        panel_right.name = "Door_Panel_Right"

        offset_right = self._get_panel_offset(width, orientation, 'double_right')
        panel_right.location = location + offset_right
        collection.objects.link(panel_right)
        objects.append(panel_right)

        # Montant central
        mullion = self._create_mullion(height - self.frame_width, orientation)
        mullion.name = "Door_Mullion"
        mullion.location = location + self._get_mullion_offset(width, orientation)
        collection.objects.link(mullion)
        objects.append(mullion)

        # Appliquer matériaux
        for obj in objects:
            if "Panel" in obj.name:
                self._apply_door_materials(None, obj)
            else:
                self._apply_door_materials(obj, None)

        return objects

    def _create_sliding_door(self, width, height, location, orientation, collection):
        """Crée une porte coulissante (simplifié)"""
        # Pour l'instant, identique à double door mais sans montant central
        return self._create_double_door(width, height, location, orientation, collection)

    def _create_french_door(self, width, height, location, orientation, collection):
        """Crée une porte-fenêtre vitrée (simplifié)"""
        # Pour l'instant, porte double avec verre ajouté
        objects = self._create_double_door(width, height, location, orientation, collection)

        # TODO: Ajouter vitres (similaire aux fenêtres)

        return objects

    def _create_door_frame(self, width, height, orientation):
        """Crée le cadre de porte (dormant)"""
        bm = bmesh.new()

        try:
            fw = self.frame_width
            fd = self.frame_depth

            # Cadre extérieur (rectangle)
            outer_verts = [
                bm.verts.new((0, 0, 0)),
                bm.verts.new((width, 0, 0)),
                bm.verts.new((width, 0, height)),
                bm.verts.new((0, 0, height))
            ]

            # Cadre intérieur (pour l'ouverture)
            inner_verts = [
                bm.verts.new((fw, 0, 0)),
                bm.verts.new((width - fw, 0, 0)),
                bm.verts.new((width - fw, 0, height - fw)),
                bm.verts.new((fw, 0, height - fw))
            ]

            # Créer faces avant
            bm.faces.new([outer_verts[0], outer_verts[1], inner_verts[1], inner_verts[0]])  # Bas
            bm.faces.new([outer_verts[1], outer_verts[2], inner_verts[2], inner_verts[1]])  # Droite
            bm.faces.new([outer_verts[2], outer_verts[3], inner_verts[3], inner_verts[2]])  # Haut
            bm.faces.new([outer_verts[3], outer_verts[0], inner_verts[0], inner_verts[3]])  # Gauche

            # Extrusion pour donner de la profondeur
            extrude_faces = list(bm.faces)
            ret = bmesh.ops.extrude_face_region(bm, geom=extrude_faces)
            extruded_verts = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, verts=extruded_verts, vec=(0, fd, 0))

            mesh = bpy.data.meshes.new("Door_Frame_Mesh")
            bm.to_mesh(mesh)
            mesh.update()

        finally:
            bm.free()

        obj = bpy.data.objects.new("Door_Frame", mesh)
        obj["house_part"] = "door"

        return obj

    def _create_door_panel(self, width, height, orientation):
        """Crée le panneau de porte"""
        bm = bmesh.new()

        try:
            th = self.door_thickness

            # Panneau simple (rectangle avec épaisseur)
            bmesh.ops.create_cube(bm, size=1.0)

            # Mise à l'échelle
            scale_matrix = Matrix.Diagonal((width, th, height, 1.0))
            bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)

            # Décalage pour centrer
            bmesh.ops.translate(bm, verts=bm.verts, vec=(width/2, th/2, height/2))

            mesh = bpy.data.meshes.new("Door_Panel_Mesh")
            bm.to_mesh(mesh)
            mesh.update()

        finally:
            bm.free()

        obj = bpy.data.objects.new("Door_Panel", mesh)
        obj["house_part"] = "door"

        return obj

    def _create_mullion(self, height, orientation):
        """Crée un montant central pour porte double"""
        bm = bmesh.new()

        try:
            fw = self.frame_width
            fd = self.frame_depth

            # Montant vertical simple
            bmesh.ops.create_cube(bm, size=1.0)

            scale_matrix = Matrix.Diagonal((fw, fd, height, 1.0))
            bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=(fw/2, fd/2, height/2))

            mesh = bpy.data.meshes.new("Door_Mullion_Mesh")
            bm.to_mesh(mesh)
            mesh.update()

        finally:
            bm.free()

        obj = bpy.data.objects.new("Door_Mullion", mesh)
        obj["house_part"] = "door"

        return obj

    def _get_panel_offset(self, door_width, orientation, panel_type):
        """Calcule l'offset du panneau selon l'orientation"""
        fw = self.frame_width
        th = self.door_thickness

        if panel_type == 'single':
            # Panneau simple: centré dans le cadre
            offset_x = fw
            offset_y = self.frame_depth/2 - th/2
            offset_z = 0

            return Vector((offset_x, offset_y, offset_z))

        elif panel_type == 'double_left':
            # Panneau gauche
            offset_x = fw
            offset_y = self.frame_depth/2 - th/2
            offset_z = 0

            return Vector((offset_x, offset_y, offset_z))

        elif panel_type == 'double_right':
            # Panneau droit
            panel_width = (door_width - fw * 3) / 2
            offset_x = fw * 2 + panel_width
            offset_y = self.frame_depth/2 - th/2
            offset_z = 0

            return Vector((offset_x, offset_y, offset_z))

        return Vector((0, 0, 0))

    def _get_mullion_offset(self, door_width, orientation):
        """Calcule l'offset du montant central"""
        panel_width = (door_width - self.frame_width * 3) / 2
        offset_x = self.frame_width + panel_width
        offset_y = 0
        offset_z = 0

        return Vector((offset_x, offset_y, offset_z))

    def _apply_door_materials(self, frame_obj, panel_obj):
        """Applique les matériaux aux portes"""

        if frame_obj:
            # Matériau cadre (bois clair ou blanc)
            mat_name = "Door_Frame_Material"
            if mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                nodes.clear()

                bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                bsdf.inputs['Base Color'].default_value = (0.9, 0.9, 0.85, 1.0)  # Blanc cassé
                bsdf.inputs['Roughness'].default_value = 0.4

                output = nodes.new('ShaderNodeOutputMaterial')
                mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            else:
                mat = bpy.data.materials[mat_name]

            frame_obj.data.materials.clear()
            frame_obj.data.materials.append(mat)

        if panel_obj:
            # Matériau panneau (bois)
            mat_name = "Door_Panel_Material"
            if mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                nodes.clear()

                bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                bsdf.inputs['Base Color'].default_value = (0.3, 0.2, 0.1, 1.0)  # Bois foncé
                bsdf.inputs['Roughness'].default_value = 0.6
                # Note: 'Specular' n'existe plus dans Blender 4.2+

                output = nodes.new('ShaderNodeOutputMaterial')
                mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            else:
                mat = bpy.data.materials[mat_name]

            panel_obj.data.materials.clear()
            panel_obj.data.materials.append(mat)
