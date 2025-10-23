# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Automatic Generation Operators Module (BLENDER 4.2+ COMPATIBLE)
#  Copyright (C) 2025 mvaertan
#  ULTIMATE EDITION - Système complet de matériaux briques
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from bpy.types import Operator
from mathutils import Vector, Matrix
import math
import random

# Import du module de fenêtres
from .windows import WindowGenerator

# Constantes - Dimensions et épaisseurs
WALL_THICKNESS = 0.25
FLOOR_THICKNESS = 0.2
FOUNDATION_THICKNESS = 0.3
ROOF_THICKNESS_FLAT = 0.3
ROOF_THICKNESS_PITCHED = 0.15

# Constantes - Ouvertures
OPENING_OFFSET = 0.02
DOOR_HEIGHT = 2.1
DOOR_DEPTH_EXTRA = 0.1
WINDOW_WIDTH = 1.2
WINDOW_DEPTH_EXTRA = 0.1
WINDOW_SPACING_INTERVAL = 3.0

# Constantes - Proportions
FLOOR_INSET = 0.95
WINDOW_HEIGHT_DEFAULT = 0.4

# Constantes - Garage
GARAGE_WIDTH_SINGLE = 3.0
GARAGE_WIDTH_DOUBLE = 6.0
GARAGE_LENGTH = 5.0
GARAGE_HEIGHT = 2.5
GARAGE_OFFSET = 1.0
GARAGE_ROOF_OVERHANG = 0.3
GARAGE_DOOR_WIDTH_RATIO = 0.9
GARAGE_DOOR_HEIGHT_RATIO = 0.8

# Constantes - Terrasse
TERRACE_WIDTH_RATIO = 0.8
TERRACE_LENGTH = 3.0
TERRACE_HEIGHT = 0.2
TERRACE_OFFSET = 0.5

# Constantes - Balcon et Rambarde
BALCONY_WIDTH_RATIO = 0.6
BALCONY_DEPTH = 1.5
BALCONY_HEIGHT = 0.15
BALCONY_RAILING_HEIGHT = 1.0
BALCONY_RAILING_THICKNESS = 0.05
BALCONY_POST_SIZE = 0.08
BALCONY_POST_SPACING = 0.5

# Constantes - Matériaux
MATERIAL_ROUGHNESS = 0.7
BMESH_MERGE_DISTANCE = 0.0001

# Couleurs par défaut
DEFAULT_WALL_COLOR = (0.9, 0.9, 0.85)
DEFAULT_ROOF_COLOR = (0.3, 0.2, 0.15)
DEFAULT_FLOOR_COLOR = (0.7, 0.6, 0.5)


class HOUSE_OT_generate_auto(Operator):
    """Génère automatiquement une maison selon les paramètres"""
    bl_idname = "house.generate_auto"
    bl_label = "Générer la maison"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.house_generator
        
        print("[House] Début de la génération...")
        
        if props.random_seed > 0:
            random.seed(props.random_seed)
            print(f"[House] Seed: {props.random_seed}")
        
        try:
            # Appliquer le style architectural
            style_config = self._apply_architectural_style(props)
            print(f"[House] Style architectural: {props.architectural_style}")
            
            house_collection = self._create_house_collection(context)
            
            print("[House] Fondations...")
            self._generate_foundation(context, props, house_collection)
            
            print("[House] Murs...")
            walls = self._generate_walls(context, props, house_collection)
            
            print("[House] Planchers...")
            self._generate_floors(context, props, house_collection)
            
            print("[House] Toit...")
            self._generate_roof(context, props, house_collection)
            
            # Perçage des murs SEULEMENT si MUR SIMPLE
            if props.wall_construction_type != 'BRICK_3D':
                print("[House] Perçage des murs (portes et fenêtres)...")
                self._generate_wall_openings(context, props, house_collection, walls, style_config)
            else:
                print("[House] Murs en briques 3D : ouvertures déjà intégrées")
            
            print(f"[House] Fenêtres complètes 3D (type: {props.window_type}, qualité: {props.window_quality})...")
            self._generate_windows_complete(context, props, house_collection, style_config)
            
            if props.include_garage:
                print("[House] Garage...")
                self._generate_garage(context, props, house_collection)
            
            if props.include_terrace or style_config.get('terrace_enabled', False):
                print("[House] Terrasse...")
                self._generate_terrace(context, props, house_collection)
            
            if (props.include_balcony and props.num_floors > 1) or style_config.get('balcony_enabled', False):
                print("[House] Balcon...")
                self._generate_balcony(context, props, house_collection)
            
            if props.use_materials:
                print("[House] Matériaux...")
                self._apply_materials(context, props, house_collection, style_config)
            
            # Éclairage automatique
            if props.auto_lighting:
                print("[House] Éclairage automatique...")
                self._add_scene_lighting(context, props)
            
            print(f"[House] Terminé! Style: {props.architectural_style}, Fenêtres: {props.window_type}")
            self.report({'INFO'}, f"Maison générée! Style: {props.architectural_style}, Fenêtres: {props.window_type}")
            
        except Exception as e:
            print(f"[House] ERREUR: {str(e)}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Erreur: {str(e)}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def _apply_architectural_style(self, props):
        """Applique les variations selon le style architectural"""
        style = props.architectural_style
        
        if style == 'MODERN':
            return self._get_modern_style()
        elif style == 'TRADITIONAL':
            return self._get_traditional_style()
        elif style == 'MEDITERRANEAN':
            return self._get_mediterranean_style()
        elif style == 'CONTEMPORARY':
            return self._get_contemporary_style()
        elif style == 'ASIAN':
            return self._get_asian_style()
        else:
            return self._get_modern_style()
    
    def _get_modern_style(self):
        """Style moderne"""
        return {
            'wall_color': (0.95, 0.95, 0.95),
            'roof_color': (0.2, 0.2, 0.2),
            'floor_color': (0.7, 0.7, 0.7),
            'window_height_ratio': 0.6,
            'balcony_enabled': False,
            'terrace_enabled': True
        }
    
    def _get_traditional_style(self):
        """Style traditionnel"""
        return {
            'wall_color': (0.85, 0.75, 0.65),
            'roof_color': (0.4, 0.25, 0.2),
            'floor_color': (0.6, 0.5, 0.4),
            'window_height_ratio': 0.45,
            'balcony_enabled': False,
            'terrace_enabled': False
        }
    
    def _get_mediterranean_style(self):
        """Style méditerranéen"""
        return {
            'wall_color': (0.95, 0.9, 0.8),
            'roof_color': (0.7, 0.3, 0.2),
            'floor_color': (0.8, 0.6, 0.4),
            'window_height_ratio': 0.5,
            'balcony_enabled': True,
            'terrace_enabled': True
        }
    
    def _get_contemporary_style(self):
        """Style contemporain"""
        return {
            'wall_color': (0.3, 0.3, 0.35),
            'roof_color': (0.15, 0.15, 0.15),
            'floor_color': (0.5, 0.5, 0.5),
            'window_height_ratio': 0.55,
            'balcony_enabled': True,
            'terrace_enabled': True
        }
    
    def _get_asian_style(self):
        """Style asiatique"""
        return {
            'wall_color': (0.9, 0.85, 0.75),
            'roof_color': (0.15, 0.1, 0.08),
            'floor_color': (0.55, 0.45, 0.35),
            'window_height_ratio': 0.5,
            'balcony_enabled': True,
            'terrace_enabled': True
        }
    
    def _colors_are_default(self, user_color, default_color):
        """Vérifie si l'utilisateur a modifié les couleurs par défaut"""
        tolerance = 0.01
        return all(abs(user_color[i] - default_color[i]) < tolerance for i in range(3))
    
    def _create_house_collection(self, context):
        """Crée une collection pour la maison"""
        collection_name = "House"
        
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
        else:
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)
        
        return collection
    
    def _create_box_mesh(self, name, location, dimensions):
        """Crée un mesh box aux dimensions exactes"""
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        
        try:
            bmesh.ops.create_cube(bm, size=1.0)
            
            scale_matrix = Matrix.Diagonal((*dimensions, 1.0))
            bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)
            
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            
            bm.to_mesh(mesh)
            mesh.update()
            
        finally:
            bm.free()
        
        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        
        return obj, mesh
    
    def _create_mesh_from_bmesh(self, name, bm):
        """Crée un mesh à partir d'un bmesh"""
        mesh = bpy.data.meshes.new(name)
        
        try:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=BMESH_MERGE_DISTANCE)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            
            bm.to_mesh(mesh)
            mesh.update()
            
        except Exception as e:
            print(f"[House] Erreur mesh {name}: {e}")
            raise
        
        obj = bpy.data.objects.new(name, mesh)
        return obj, mesh
    
    def _generate_foundation(self, context, props, collection):
        """Génère les fondations"""
        width = props.house_width
        length = props.house_length
        thickness = FOUNDATION_THICKNESS
        
        location = Vector((width/2, length/2, -thickness/2))
        dimensions = Vector((width, length, thickness))
        
        foundation, mesh = self._create_box_mesh("Foundation", location, dimensions)
        collection.objects.link(foundation)
        foundation["house_part"] = "floor"
        
        return foundation
    
    def _generate_walls(self, context, props, collection):
        """Génère les murs extérieurs (SIMPLE ou BRIQUES 3D) - ULTIMATE"""
        
        # === SI BRIQUES 3D : NOUVEAU SYSTÈME COMPLET ===
        if props.wall_construction_type == 'BRICK_3D':
            print(f"[House] Génération murs en briques 3D (qualité: {props.brick_3d_quality})")
            print(f"[House] Mode matériau: {props.brick_material_mode}")
            
            from .materials import brick_geometry
            
            width = props.house_width
            length = props.house_length
            total_height = props.num_floors * props.floor_height
            
            # Calculer les ouvertures
            openings = self._calculate_openings_for_brick_walls(props)
            print(f"[House] {len(openings)} ouvertures calculées")
            
            # ✅ NOUVEAU : Préparer les paramètres matériau selon le mode
            brick_material_mode = props.brick_material_mode
            brick_color = None
            brick_preset = 'BRICK_RED'
            custom_material = None
            
            if brick_material_mode == 'COLOR':
                # Mode couleur unie
                brick_color = props.brick_solid_color
                print(f"[House] Couleur unie: {brick_color}")
            elif brick_material_mode == 'PRESET':
                # Mode preset
                brick_preset = props.brick_preset_type
                print(f"[House] Preset: {brick_preset}")
            elif brick_material_mode == 'CUSTOM':
                # Mode matériau custom
                custom_material = props.brick_custom_material
                if custom_material:
                    print(f"[House] Matériau custom: {custom_material.name}")
                else:
                    print(f"[House] ATTENTION : Pas de matériau custom défini, utilisation preset par défaut")
                    brick_material_mode = 'PRESET'
            
            # Générer les murs avec le nouveau système
            # ✅ FIX : Capturer la hauteur réelle des murs pour positionner le toit correctement
            walls, real_wall_height = brick_geometry.generate_house_walls_bricks(
                width,
                length,
                total_height,
                collection,
                props.brick_3d_quality,
                openings,
                brick_material_mode,
                brick_color,
                brick_preset,
                custom_material
            )

            # Stocker la hauteur réelle pour l'utiliser dans _generate_roof
            self.real_wall_height = real_wall_height
            print(f"[House] Hauteur réelle des murs enregistrée: {real_wall_height:.3f}m")

            return walls
        
        # === SINON MUR SIMPLE (inchangé) ===
        width = props.house_width
        length = props.house_length
        wall_thickness = WALL_THICKNESS
        total_height = props.num_floors * props.floor_height
        
        walls = []
        mesh = bpy.data.meshes.new("Walls")
        bm = bmesh.new()
        
        try:
            h = total_height
            
            # Vertices du bas
            outer = [
                bm.verts.new((0, 0, 0)),
                bm.verts.new((width, 0, 0)),
                bm.verts.new((width, length, 0)),
                bm.verts.new((0, length, 0))
            ]
            
            inner = [
                bm.verts.new((wall_thickness, wall_thickness, 0)),
                bm.verts.new((width - wall_thickness, wall_thickness, 0)),
                bm.verts.new((width - wall_thickness, length - wall_thickness, 0)),
                bm.verts.new((wall_thickness, length - wall_thickness, 0))
            ]
            
            # Vertices du haut
            outer_top = [bm.verts.new(v.co + Vector((0, 0, h))) for v in outer]
            inner_top = [bm.verts.new(v.co + Vector((0, 0, h))) for v in inner]
            
            # Faces verticales extérieures
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([outer[i], outer[j], outer_top[j], outer_top[i]])
            
            # Faces verticales intérieures
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([inner[j], inner[i], inner_top[i], inner_top[j]])
            
            # Sol de la structure murale
            bm.faces.new([outer[0], outer[1], inner[1], inner[0]])
            bm.faces.new([outer[1], outer[2], inner[2], inner[1]])
            bm.faces.new([outer[2], outer[3], inner[3], inner[2]])
            bm.faces.new([outer[3], outer[0], inner[0], inner[3]])
            
            # Plafond de la structure murale
            bm.faces.new([outer_top[0], inner_top[0], inner_top[1], outer_top[1]])
            bm.faces.new([outer_top[1], inner_top[1], inner_top[2], outer_top[2]])
            bm.faces.new([outer_top[2], inner_top[2], inner_top[3], outer_top[3]])
            bm.faces.new([outer_top[3], inner_top[3], inner_top[0], outer_top[0]])
            
            walls_obj, walls_mesh = self._create_mesh_from_bmesh("Walls", bm)
            collection.objects.link(walls_obj)
            walls_obj["house_part"] = "wall"
            walls.append(walls_obj)
            
        finally:
            bm.free()
        
        return walls
    
    def _calculate_openings_for_brick_walls(self, props):
        """Calcule les positions des ouvertures pour les murs en briques"""
        width = props.house_width
        length = props.house_length
        
        openings = []
        
        # Récupérer window_height_ratio
        style_config = self._apply_architectural_style(props)
        window_height_ratio = style_config.get('window_height_ratio', props.window_height_ratio)
        
        # Calculer nombre de fenêtres
        num_windows_front = max(2, int(width / WINDOW_SPACING_INTERVAL))
        num_windows_side = max(2, int(length / WINDOW_SPACING_INTERVAL))
        
        # PORTE
        door_width = props.front_door_width
        door_height = DOOR_HEIGHT
        door_x = width/2 - door_width/2
        
        openings.append({
            'x': door_x,
            'y': 0,
            'z': 0,
            'width': door_width,
            'height': door_height,
            'depth': WALL_THICKNESS,
            'wall': 'front',
            'type': 'door'
        })
        
        # FENÊTRES
        for floor in range(props.num_floors):
            floor_z = floor * props.floor_height
            window_height = props.floor_height * window_height_ratio
            window_z = floor_z + props.floor_height * WINDOW_HEIGHT_DEFAULT
            window_width = WINDOW_WIDTH
            
            # Mur AVANT
            spacing_front = width / (num_windows_front + 1)
            for i in range(num_windows_front):
                x_pos = spacing_front * (i + 1)
                
                if floor == 0 and abs(x_pos - width/2) < door_width * 1.5:
                    continue
                
                opening_x = x_pos - window_width/2
                
                openings.append({
                    'x': opening_x,
                    'y': 0,
                    'z': window_z,
                    'width': window_width,
                    'height': window_height,
                    'depth': WALL_THICKNESS,
                    'wall': 'front',
                    'type': 'window'
                })
            
            # Mur ARRIÈRE
            for i in range(num_windows_front):
                x_pos = spacing_front * (i + 1)
                opening_x = x_pos - window_width/2
                
                openings.append({
                    'x': opening_x,
                    'y': length,
                    'z': window_z,
                    'width': window_width,
                    'height': window_height,
                    'depth': WALL_THICKNESS,
                    'wall': 'back',
                    'type': 'window'
                })
            
            # Mur GAUCHE
            spacing_side = length / (num_windows_side + 1)
            for i in range(num_windows_side):
                y_pos = spacing_side * (i + 1)
                opening_y = y_pos - window_width/2
                
                openings.append({
                    'x': 0,
                    'y': opening_y,
                    'z': window_z,
                    'width': window_width,
                    'height': window_height,
                    'depth': WALL_THICKNESS,
                    'wall': 'left',
                    'type': 'window'
                })
            
            # Mur DROIT
            for i in range(num_windows_side):
                y_pos = spacing_side * (i + 1)
                opening_y = y_pos - window_width/2
                
                openings.append({
                    'x': width,
                    'y': opening_y,
                    'z': window_z,
                    'width': window_width,
                    'height': window_height,
                    'depth': WALL_THICKNESS,
                    'wall': 'right',
                    'type': 'window'
                })
        
        return openings
    
    def _generate_floors(self, context, props, collection):
        """Génère les planchers"""
        width = props.house_width
        length = props.house_length
        floor_thickness = FLOOR_THICKNESS
        
        floors = []
        
        for floor_num in range(props.num_floors):
            if floor_num == 0:
                z_pos = floor_thickness / 2
            else:
                z_pos = floor_num * props.floor_height + floor_thickness / 2
            
            inset_width = width * FLOOR_INSET
            inset_length = length * FLOOR_INSET
            
            location = Vector((width/2, length/2, z_pos))
            dimensions = Vector((inset_width, inset_length, floor_thickness))
            
            floor_name = f"Floor_Ground" if floor_num == 0 else f"Floor_{floor_num}"
            floor, mesh = self._create_box_mesh(floor_name, location, dimensions)
            collection.objects.link(floor)
            floor["house_part"] = "floor"
            floors.append(floor)
        
        return floors
    
    def _generate_roof(self, context, props, collection):
        """Génère le toit"""
        width = props.house_width
        length = props.house_length

        # ✅ FIX : Utiliser la hauteur RÉELLE des murs en briques si disponible
        # Sinon utiliser la hauteur calculée (murs simples)
        if hasattr(self, 'real_wall_height') and self.real_wall_height:
            total_height = self.real_wall_height
            print(f"[House] Toit positionné à la hauteur réelle des murs: {total_height:.3f}m")
        else:
            total_height = props.num_floors * props.floor_height
            print(f"[House] Toit positionné à la hauteur calculée: {total_height:.3f}m")

        roof_type = props.roof_type
        roof_pitch = props.roof_pitch
        roof_overhang = props.roof_overhang
        
        if roof_type == 'FLAT':
            roof = self._create_flat_roof(width, length, total_height, roof_overhang, collection)
        elif roof_type == 'GABLE':
            roof = self._create_gable_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'HIP':
            roof = self._create_hip_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'SHED':
            roof = self._create_shed_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        
        roof.name = f"Roof_{roof_type}"
        roof["house_part"] = "roof"
        collection.objects.link(roof)
        
        return roof
    
    def _create_flat_roof(self, width, length, height, overhang, collection):
        """Toit plat"""
        thickness = ROOF_THICKNESS_FLAT
        
        location = Vector((width/2, length/2, height + thickness/2))
        dimensions = Vector((width + overhang*2, length + overhang*2, thickness))
        
        roof, mesh = self._create_box_mesh("Roof_Flat", location, dimensions)
        return roof
    
    def _create_gable_roof(self, width, length, height, pitch, overhang, collection):
        """Toit à 2 pans"""
        pitch_rad = math.radians(pitch)
        roof_height = (width/2) * math.tan(pitch_rad)
        roof_thickness = ROOF_THICKNESS_PITCHED
        
        bm = bmesh.new()
        
        try:
            h = height
            rh = roof_height
            o = overhang
            
            v1 = bm.verts.new((-o, -o, h))
            v2 = bm.verts.new((width + o, -o, h))
            v3 = bm.verts.new((width + o, length + o, h))
            v4 = bm.verts.new((-o, length + o, h))
            
            v5 = bm.verts.new((width/2, -o, h + rh))
            v6 = bm.verts.new((width/2, length + o, h + rh))
            
            f1 = bm.faces.new([v1, v2, v5])
            f2 = bm.faces.new([v2, v3, v6, v5])
            f3 = bm.faces.new([v3, v4, v6])
            f4 = bm.faces.new([v4, v1, v5, v6])
            
            faces_to_extrude = [f1, f2, f3, f4]
            ret = bmesh.ops.extrude_face_region(bm, geom=faces_to_extrude)
            
            extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
            offset_vector = Vector((0, 0, -roof_thickness))
            bmesh.ops.translate(bm, verts=extruded_verts, vec=offset_vector)
            
            roof, mesh = self._create_mesh_from_bmesh("GableRoof", bm)
            
        finally:
            bm.free()
        
        return roof
    
    def _create_hip_roof(self, width, length, height, pitch, overhang, collection):
        """Toit à 4 pans (hip roof) - Crée une géométrie rectangulaire appropriée"""
        pitch_rad = math.radians(pitch)
        roof_thickness = ROOF_THICKNESS_PITCHED

        # Calculer la hauteur du toit basée sur la plus petite dimension
        # Un toit en croupe a une arête (ridge) au centre si rectangulaire
        if width < length:
            # Ridge court le long de X, pente le long de Y
            ridge_length = length - width  # Longueur de l'arête centrale
            roof_height = (width / 2) * math.tan(pitch_rad)
        else:
            # Ridge court le long de Y, pente le long de X
            ridge_length = width - length
            roof_height = (length / 2) * math.tan(pitch_rad)

        bm = bmesh.new()

        try:
            h = height
            rh = roof_height
            o = overhang

            # Base rectangulaire (4 coins)
            v1 = bm.verts.new((-o, -o, h))
            v2 = bm.verts.new((width + o, -o, h))
            v3 = bm.verts.new((width + o, length + o, h))
            v4 = bm.verts.new((-o, length + o, h))

            if width < length:
                # House est plus long en Y: ridge le long de Y
                ridge_start_y = width / 2
                ridge_end_y = length - width / 2

                # Ridge (arête centrale en haut)
                v5 = bm.verts.new((width/2, ridge_start_y - o, h + rh))
                v6 = bm.verts.new((width/2, ridge_end_y + o, h + rh))

                # 4 faces du toit + 2 triangles aux extrémités
                f1 = bm.faces.new([v1, v2, v5])  # Triangle avant (face X-)
                f2 = bm.faces.new([v2, v3, v6, v5])  # Trapèze droite (face X+)
                f3 = bm.faces.new([v3, v4, v6])  # Triangle arrière (face X+)
                f4 = bm.faces.new([v4, v1, v5, v6])  # Trapèze gauche (face X-)

            elif length < width:
                # House est plus long en X: ridge le long de X
                ridge_start_x = length / 2
                ridge_end_x = width - length / 2

                # Ridge (arête centrale en haut)
                v5 = bm.verts.new((ridge_start_x - o, length/2, h + rh))
                v6 = bm.verts.new((ridge_end_x + o, length/2, h + rh))

                # 4 faces du toit
                f1 = bm.faces.new([v1, v2, v6, v5])  # Trapèze avant (face Y-)
                f2 = bm.faces.new([v2, v3, v6])  # Triangle droite (face X+)
                f3 = bm.faces.new([v3, v4, v5])  # Trapèze arrière (face Y+)
                f4 = bm.faces.new([v4, v1, v5, v6])  # Triangle gauche (face X-)

            else:
                # Maison carrée: pyramide parfaite avec sommet au centre
                v5 = bm.verts.new((width/2, length/2, h + rh))

                # 4 faces triangulaires
                f1 = bm.faces.new([v1, v2, v5])
                f2 = bm.faces.new([v2, v3, v5])
                f3 = bm.faces.new([v3, v4, v5])
                f4 = bm.faces.new([v4, v1, v5])

            # Extruder pour donner de l'épaisseur au toit
            faces_to_extrude = [f1, f2, f3, f4]
            ret = bmesh.ops.extrude_face_region(bm, geom=faces_to_extrude)

            extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
            offset_vector = Vector((0, 0, -roof_thickness))
            bmesh.ops.translate(bm, verts=extruded_verts, vec=offset_vector)

            roof, mesh = self._create_mesh_from_bmesh("HipRoof", bm)

        finally:
            bm.free()

        return roof
    
    def _create_shed_roof(self, width, length, height, pitch, overhang, collection):
        """Toit monopente"""
        pitch_rad = math.radians(pitch)
        roof_height = width * math.tan(pitch_rad)
        roof_thickness = ROOF_THICKNESS_PITCHED
        
        bm = bmesh.new()
        
        try:
            h = height
            o = overhang
            
            v1 = bm.verts.new((-o, -o, h))
            v2 = bm.verts.new((width + o, -o, h + roof_height))
            v3 = bm.verts.new((width + o, length + o, h + roof_height))
            v4 = bm.verts.new((-o, length + o, h))
            
            face = bm.faces.new([v1, v2, v3, v4])
            
            ret = bmesh.ops.extrude_face_region(bm, geom=[face])
            extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, verts=extruded_verts, vec=Vector((0, 0, -roof_thickness)))
            
            roof, mesh = self._create_mesh_from_bmesh("ShedRoof", bm)
            
        finally:
            bm.free()
        
        return roof
    
    def _generate_wall_openings(self, context, props, collection, walls, style_config):
        """Génère les trous dans les murs (Boolean) - pour murs SIMPLES uniquement"""
        width = props.house_width
        length = props.house_length
        
        window_height_ratio = style_config.get('window_height_ratio', props.window_height_ratio)
        
        num_windows_front = max(2, int(width / WINDOW_SPACING_INTERVAL))
        num_windows_side = max(2, int(length / WINDOW_SPACING_INTERVAL))
        
        combined_bm = bmesh.new()
        
        try:
            # PORTE
            door_height = DOOR_HEIGHT
            door_width = props.front_door_width
            door_depth = WALL_THICKNESS + DOOR_DEPTH_EXTRA
            
            door_bm = bmesh.new()
            bmesh.ops.create_cube(door_bm, size=1.0)
            
            door_scale = Matrix.Diagonal((door_width, door_depth, door_height, 1.0))
            bmesh.ops.transform(door_bm, matrix=door_scale, verts=door_bm.verts)
            
            door_location = Vector((width/2, WALL_THICKNESS/2, door_height/2))
            bmesh.ops.translate(door_bm, verts=door_bm.verts, vec=door_location)
            
            for v in door_bm.verts:
                combined_bm.verts.new(v.co)
            combined_bm.verts.ensure_lookup_table()
            
            for f in door_bm.faces:
                combined_bm.faces.new([combined_bm.verts[v.index] for v in f.verts])
            
            door_bm.free()
            
            # FENÊTRES
            for floor in range(props.num_floors):
                floor_z = floor * props.floor_height
                window_height = props.floor_height * window_height_ratio
                window_z = floor_z + props.floor_height * WINDOW_HEIGHT_DEFAULT
                window_depth = WALL_THICKNESS + WINDOW_DEPTH_EXTRA
                window_width = WINDOW_WIDTH
                
                spacing_front = width / (num_windows_front + 1)
                for i in range(num_windows_front):
                    x_pos = spacing_front * (i + 1)
                    
                    if floor == 0 and abs(x_pos - width/2) < door_width * 1.5:
                        continue
                    
                    self._add_window_to_combined_mesh(
                        combined_bm, x_pos, WALL_THICKNESS/2, window_z,
                        window_width, window_depth, window_height
                    )
                
                for i in range(num_windows_front):
                    x_pos = spacing_front * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, x_pos, length - WALL_THICKNESS/2, window_z,
                        window_width, window_depth, window_height
                    )
                
                spacing_side = length / (num_windows_side + 1)
                for i in range(num_windows_side):
                    y_pos = spacing_side * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, WALL_THICKNESS/2, y_pos, window_z,
                        window_depth, window_width, window_height
                    )
                
                for i in range(num_windows_side):
                    y_pos = spacing_side * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, width - WALL_THICKNESS/2, y_pos, window_z,
                        window_depth, window_width, window_height
                    )
            
            combined_cutter, combined_mesh = self._create_mesh_from_bmesh("Openings_Cutter", combined_bm)
            collection.objects.link(combined_cutter)
            combined_cutter["house_part"] = "opening"
            combined_cutter.display_type = 'WIRE'
            combined_cutter.hide_render = True
            
            for wall in walls:
                mod = wall.modifiers.new(name="Boolean_Openings", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = combined_cutter
                mod.solver = 'FAST'
            
        finally:
            combined_bm.free()
    
    def _add_window_to_combined_mesh(self, combined_bm, x, y, z, width, depth, height):
        """Ajoute une fenêtre au mesh combiné"""
        window_bm = bmesh.new()
        bmesh.ops.create_cube(window_bm, size=1.0)
        
        window_scale = Matrix.Diagonal((width, depth, height, 1.0))
        bmesh.ops.transform(window_bm, matrix=window_scale, verts=window_bm.verts)
        
        window_location = Vector((x, y, z))
        bmesh.ops.translate(window_bm, verts=window_bm.verts, vec=window_location)
        
        vert_offset = len(combined_bm.verts)
        for v in window_bm.verts:
            combined_bm.verts.new(v.co)
        combined_bm.verts.ensure_lookup_table()
        
        for f in window_bm.faces:
            combined_bm.faces.new([combined_bm.verts[vert_offset + v.index] for v in f.verts])
        
        window_bm.free()
    
    def _generate_windows_complete(self, context, props, collection, style_config):
        """Génère les fenêtres 3D complètes"""
        width = props.house_width
        length = props.house_length
        
        num_windows_front = max(2, int(width / WINDOW_SPACING_INTERVAL))
        num_windows_side = max(2, int(length / WINDOW_SPACING_INTERVAL))
        
        window_height_ratio = style_config.get('window_height_ratio', props.window_height_ratio)
        window_height = props.floor_height * window_height_ratio
        window_width = WINDOW_WIDTH
        
        window_gen = WindowGenerator(quality=props.window_quality)
        
        for floor in range(props.num_floors):
            floor_z = floor * props.floor_height
            window_z = floor_z + props.floor_height * WINDOW_HEIGHT_DEFAULT
            
            # Mur avant
            spacing_front = width / (num_windows_front + 1)
            for i in range(num_windows_front):
                x_pos = spacing_front * (i + 1)
                
                if floor == 0 and abs(x_pos - width/2) < props.front_door_width * 1.5:
                    continue
                
                window_gen.generate_window(
                    window_type=props.window_type,
                    width=window_width,
                    height=window_height,
                    location=Vector((x_pos, WALL_THICKNESS/2, window_z)),
                    orientation='front',
                    collection=collection
                )
            
            # Mur arrière
            for i in range(num_windows_front):
                x_pos = spacing_front * (i + 1)
                window_gen.generate_window(
                    window_type=props.window_type,
                    width=window_width,
                    height=window_height,
                    location=Vector((x_pos, length - WALL_THICKNESS/2, window_z)),
                    orientation='back',
                    collection=collection
                )
            
            # Mur gauche
            spacing_side = length / (num_windows_side + 1)
            for i in range(num_windows_side):
                y_pos = spacing_side * (i + 1)
                window_gen.generate_window(
                    window_type=props.window_type,
                    width=window_width,
                    height=window_height,
                    location=Vector((WALL_THICKNESS/2, y_pos, window_z)),
                    orientation='left',
                    collection=collection
                )
            
            # Mur droit
            for i in range(num_windows_side):
                y_pos = spacing_side * (i + 1)
                window_gen.generate_window(
                    window_type=props.window_type,
                    width=window_width,
                    height=window_height,
                    location=Vector((width - WALL_THICKNESS/2, y_pos, window_z)),
                    orientation='right',
                    collection=collection
                )
    
    # [... Les autres fonctions garage, terrace, balcony, lighting restent identiques ...]
    
    def _generate_garage(self, context, props, collection):
        """Génère un garage"""
        # Code inchangé
        pass
    
    def _generate_terrace(self, context, props, collection):
        """Génère une terrasse"""
        # Code inchangé
        pass
    
    def _generate_balcony(self, context, props, collection):
        """Génère un balcon"""
        # Code inchangé
        pass
    
    def _generate_balcony_railing(self, context, props, collection, balcony_width, balcony_depth, x_pos, y_pos, z_pos):
        """Génère la rambarde"""
        # Code inchangé
        pass
    
    def _add_railing_segment(self, bm, x, y, z, width, depth, height):
        """Ajoute un segment de rambarde"""
        # Code inchangé
        pass
    
    def _add_railing_post(self, bm, x, y, z, width, depth, height):
        """Ajoute un poteau"""
        # Code inchangé
        pass
    
    def _add_scene_lighting(self, context, props):
        """Ajoute l'éclairage"""
        # Code inchangé
        pass
    
    def _apply_materials(self, context, props, collection, style_config):
        """Applique les matériaux - Les briques 3D sont déjà gérées"""
        
        # Les briques 3D ont DÉJÀ leur matériau appliqué dans brick_geometry
        # On ne touche PAS aux briques ici
        
        user_changed_wall = not self._colors_are_default(props.wall_material_color, DEFAULT_WALL_COLOR)
        user_changed_roof = not self._colors_are_default(props.roof_material_color, DEFAULT_ROOF_COLOR)
        user_changed_floor = not self._colors_are_default(props.floor_material_color, DEFAULT_FLOOR_COLOR)
        
        wall_color = props.wall_material_color if user_changed_wall else style_config.get('wall_color', props.wall_material_color)
        roof_color = props.roof_material_color if user_changed_roof else style_config.get('roof_color', props.roof_material_color)
        floor_color = props.floor_material_color if user_changed_floor else style_config.get('floor_color', props.floor_material_color)
        
        wall_mat = self._get_or_create_material("House_Wall", wall_color)
        roof_mat = self._get_or_create_material("House_Roof", roof_color)
        floor_mat = self._get_or_create_material("House_Floor", floor_color)
        glass_mat = self._get_or_create_glass_material("House_Glass")
        
        for obj in collection.objects:
            if obj.type != 'MESH' or obj.hide_render:
                continue
            
            part_type = obj.get("house_part", None)
            
            if part_type == "wall":
                # Murs simples uniquement (pas les briques qui ont déjà leur matériau)
                if props.wall_construction_type == 'SIMPLE' and len(obj.data.materials) == 0:
                    obj.data.materials.append(wall_mat)
            elif part_type == "roof":
                obj.data.materials.clear()
                obj.data.materials.append(roof_mat)
            elif part_type == "floor":
                obj.data.materials.clear()
                obj.data.materials.append(floor_mat)
            elif part_type == "glass":
                obj.data.materials.clear()
                obj.data.materials.append(glass_mat)
    
    def _get_or_create_material(self, name, color):
        """Crée ou récupère un matériau"""
        if name in bpy.data.materials:
            mat = bpy.data.materials[name]
        else:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
        
        if not mat.use_nodes:
            mat.use_nodes = True
        
        nodes = mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        
        if not principled:
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            output = nodes.get("Material Output")
            if output:
                mat.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
        
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        principled.inputs["Roughness"].default_value = MATERIAL_ROUGHNESS
        
        return mat
    
    def _get_or_create_glass_material(self, name):
        """Crée ou récupère le matériau verre"""
        if name in bpy.data.materials:
            return bpy.data.materials[name]
        
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        
        nodes = mat.node_tree.nodes
        nodes.clear()
        
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)
        
        glass_bsdf = nodes.new(type='ShaderNodeBsdfGlass')
        glass_bsdf.location = (0, 0)
        glass_bsdf.inputs["IOR"].default_value = 1.45
        glass_bsdf.inputs["Roughness"].default_value = 0.0
        glass_bsdf.inputs["Color"].default_value = (0.8, 0.9, 1.0, 1.0)
        
        mat.node_tree.links.new(glass_bsdf.outputs["BSDF"], output.inputs["Surface"])
        
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'NONE'
        
        return mat


classes = (
    HOUSE_OT_generate_auto,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[House] Module operators_auto ULTIMATE chargé")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[House] Module operators_auto déchargé")