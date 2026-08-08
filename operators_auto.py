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
from .doors import DoorGenerator

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

            # ✅ FIX: Réinitialiser real_wall_height (l'opérateur est réutilisé
            # par le panneau Redo — une valeur périmée décalait toit/fenêtres
            # après un changement de type de mur)
            self.real_wall_height = None

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
            
            # ✅ NOUVEAU: Générer les fondations (AVANT les murs)
            if props.foundation_height > 0:
                print(f"[House] Fondations visuelles (hauteur: {props.foundation_height}m)...")
                self._generate_foundation(context, props, house_collection)

            print(f"[House] Fenêtres complètes 3D (type: {props.window_type}, qualité: {props.window_quality})...")
            self._generate_windows_complete(context, props, house_collection, style_config)

            # ✅ NOUVEAU: Générer la porte d'entrée visuelle
            print(f"[House] Porte d'entrée visuelle (type: {props.door_type}, qualité: {props.door_quality})...")
            self._generate_door_visual(context, props, house_collection)

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
    
    def _get_wall_depth(self, props):
        """✅ Épaisseur réelle du mur selon le type de construction

        Valeur PARTAGÉE entre ouvertures, fenêtres et portes — les
        incohérences ici créaient des fenêtres flottantes / des jeux.
        """
        if props.wall_construction_type == 'BRICK_3D':
            from .materials.brick_geometry import BRICK_DEPTH, MORTAR_GAP
            return BRICK_DEPTH + MORTAR_GAP  # 0.112m (brique + mortier)
        return props.wall_thickness

    # ✅ NORMES ARCHITECTURALES: Plages de pente réalistes par type de toit.
    # Le slider (5-60°) est GLOBAL, mais chaque type de toit a sa plage
    # normative — une monopente à 35° donnait un mur pignon de 10m!
    PITCH_RANGES = {
        'SHED':    (5.0, 25.0),   # Monopente: bac acier ~5°, tuiles max ~25°
        'GABLE':   (15.0, 50.0),  # 2 pans: tuiles 15-50° selon région
        'HIP':     (15.0, 50.0),  # 4 pans: idem
        'GAMBREL': (15.0, 30.0),  # Mansarde: pente du TERRASSON (le brisis est fixe)
    }

    @classmethod
    def _effective_pitch(cls, roof_type, pitch):
        """Pente effective clampée à la plage normative du type de toit.

        UNIQUE source de vérité — utilisée par les toits, les murs adaptés
        (SHED/GABLE) et la génération de briques, pour que tout reste aligné.
        """
        lo, hi = cls.PITCH_RANGES.get(roof_type, (5.0, 60.0))
        clamped = max(lo, min(hi, pitch))
        if abs(clamped - pitch) > 1e-6:
            print(f"[House] Pente {pitch:.0f}° hors norme pour {roof_type} → clampée à {clamped:.0f}° (plage {lo:.0f}-{hi:.0f}°)")
        return clamped

    def _get_window_layout(self, props, style_config):
        """✅ Paramètres fenêtres PARTAGÉS (ouvertures + objets visuels)

        Câble les sliders utilisateur qui étaient ignorés
        (num_windows_front/side, window_width) et fait primer le ratio
        utilisateur sur celui du style s'il a été modifié.
        """
        if abs(props.window_height_ratio - 0.4) > 1e-6:
            ratio = props.window_height_ratio  # L'utilisateur a changé le slider
        else:
            ratio = style_config.get('window_height_ratio', props.window_height_ratio)
        return {
            'num_front': props.num_windows_front,
            'num_side': props.num_windows_side,
            'width': props.window_width,
            'height_ratio': ratio,
        }

    @staticmethod
    def _window_vertical(floor_z, floor_height, height_ratio):
        """✅ Géométrie verticale UNIQUE d'une fenêtre (hauteur, z bas, z centre)

        Partagée par les ouvertures (briques = bas, murs simples = centre)
        et par les objets fenêtres visuels — le décalage d'une demi-hauteur
        entre le trou et la fenêtre venait de conventions différentes ici.
        La fenêtre est clampée pour ne pas dépasser le plafond de l'étage.
        """
        window_height = floor_height * height_ratio
        sill_ratio = min(WINDOW_HEIGHT_DEFAULT, max(0.05, 1.0 - height_ratio - 0.05))
        z_bottom = floor_z + floor_height * sill_ratio
        return window_height, z_bottom, z_bottom + window_height / 2

    def _create_house_collection(self, context):
        """Crée une collection pour la maison"""
        props = context.scene.house_generator
        # ✅ FIX: Utiliser le nom de collection choisi par l'utilisateur
        collection_name = props.collection_name or "House"

        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            # ✅ FIX: Purger aussi les meshes orphelins (fuite mémoire à
            # chaque régénération) et re-lier la collection à la scène si
            # elle avait été détachée (sinon la maison est invisible)
            for obj in list(collection.objects):
                mesh_data = obj.data if obj.type == 'MESH' else None
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh_data is not None and mesh_data.users == 0:
                    bpy.data.meshes.remove(mesh_data)
            if collection.name not in context.scene.collection.children:
                try:
                    context.scene.collection.children.link(collection)
                except RuntimeError:
                    pass  # Déjà liée ailleurs dans la hiérarchie
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
            # ✅ FIX: Ne pas laisser un datablock mesh orphelin en cas d'erreur
            bpy.data.meshes.remove(mesh)
            raise

        obj = bpy.data.objects.new(name, mesh)
        return obj, mesh
    
    # Note: l'ancienne première définition de _generate_foundation a été
    # supprimée — elle était écrasée par la définition complète plus bas
    # et provoquait une double génération des fondations.

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

            # ✅ FIX: Calculer la hauteur réelle AVANT les ouvertures
            BRICK_HEIGHT = brick_geometry.BRICK_HEIGHT
            MORTAR_GAP = brick_geometry.MORTAR_GAP
            num_rows = int(total_height / (BRICK_HEIGHT + MORTAR_GAP))
            real_wall_height = num_rows * (BRICK_HEIGHT + MORTAR_GAP)
            self.real_wall_height = real_wall_height
            print(f"[House] Hauteur réelle calculée: {real_wall_height:.3f}m ({num_rows} rangées)")

            # Calculer les ouvertures avec hauteur réelle
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
            # ✅ NOUVEAU : roof_type/roof_pitch (murs adaptés), mortar_color,
            # bonding_pattern, et choix du moteur (Geometry Nodes ou instancing)
            brick_kwargs = dict(
                openings=openings,
                brick_material_mode=brick_material_mode,
                brick_color=brick_color,
                brick_preset=brick_preset,
                custom_material=custom_material,
                roof_type=props.roof_type,
                # ✅ NORMES: Pente clampée à la plage du type de toit
                roof_pitch=self._effective_pitch(props.roof_type, props.roof_pitch),
                mortar_color=tuple(props.mortar_color),
                bonding_pattern=props.brick_bonding_pattern,
            )

            if props.brick_use_geonodes:
                # ✅ NOUVEAU MOTEUR: 1 objet Geometry Nodes au lieu de
                # milliers d'instances (fallback auto si erreur)
                from .materials import brick_geonodes
                try:
                    walls, real_wall_height = brick_geonodes.generate_walls_geonodes(
                        width, length, total_height, collection,
                        props.brick_3d_quality, **brick_kwargs)
                except Exception as e:
                    print(f"[House] ⚠️ Moteur GN échoué ({e}) → fallback instancing")
                    import traceback
                    traceback.print_exc()
                    walls, real_wall_height = brick_geometry.generate_house_walls_bricks(
                        width, length, total_height, collection,
                        props.brick_3d_quality, **brick_kwargs)
            else:
                walls, real_wall_height = brick_geometry.generate_house_walls_bricks(
                    width, length, total_height, collection,
                    props.brick_3d_quality, **brick_kwargs)

            # Stocker la hauteur réelle pour l'utiliser dans _generate_roof
            self.real_wall_height = real_wall_height
            print(f"[House] Hauteur réelle des murs enregistrée: {real_wall_height:.3f}m")

            return walls
        
        # === SINON MUR SIMPLE ===
        width = props.house_width
        length = props.house_length
        # ✅ FIX: Utiliser l'épaisseur de mur choisie par l'utilisateur
        # (le slider "Épaisseur murs" était ignoré avant)
        wall_thickness = props.wall_thickness
        total_height = props.num_floors * props.floor_height

        # ✅ FIX: Calculer hauteur additionnelle pour SHED roof
        if props.roof_type == 'SHED':
            # ✅ NORMES: Pente clampée (une monopente à 35° donnait +7m!)
            pitch_rad = math.radians(self._effective_pitch('SHED', props.roof_pitch))
            roof_height = width * math.tan(pitch_rad)
            print(f"[House] Murs simples adaptés SHED roof: +{roof_height:.3f}m à droite")
        else:
            roof_height = 0

        walls = []
        bm = bmesh.new()

        try:
            h = total_height

            # Vertices du bas
            outer = [
                bm.verts.new((0, 0, 0)),           # 0: gauche-avant
                bm.verts.new((width, 0, 0)),       # 1: droite-avant
                bm.verts.new((width, length, 0)),  # 2: droite-arrière
                bm.verts.new((0, length, 0))       # 3: gauche-arrière
            ]

            inner = [
                bm.verts.new((wall_thickness, wall_thickness, 0)),
                bm.verts.new((width - wall_thickness, wall_thickness, 0)),
                bm.verts.new((width - wall_thickness, length - wall_thickness, 0)),
                bm.verts.new((wall_thickness, length - wall_thickness, 0))
            ]

            # ✅ FIX: Vertices du haut avec hauteur variable pour SHED roof
            if props.roof_type == 'SHED':
                # SHED: Gauche (X=0) bas, Droite (X=width) haut
                # Abaisser le plafond sous la FACE INFÉRIEURE de la dalle du toit
                # (épaisseur ROOF_THICKNESS_PITCHED + gap de sécurité)
                wall_cap_offset = ROOF_THICKNESS_PITCHED + 0.05

                # ✅ FIX: Calculer la hauteur du toit à la position X RÉELLE de
                # chaque vertex (les sommets intérieurs ne sont pas aux bords!)
                def shed_top(x):
                    return h + roof_height * (x / width) - wall_cap_offset

                outer_top = [
                    bm.verts.new((0, 0, shed_top(0))),                  # 0: gauche-avant (bas)
                    bm.verts.new((width, 0, shed_top(width))),          # 1: droite-avant (haut)
                    bm.verts.new((width, length, shed_top(width))),     # 2: droite-arrière (haut)
                    bm.verts.new((0, length, shed_top(0)))              # 3: gauche-arrière (bas)
                ]
                inner_top = [
                    bm.verts.new((wall_thickness, wall_thickness, shed_top(wall_thickness))),
                    bm.verts.new((width - wall_thickness, wall_thickness, shed_top(width - wall_thickness))),
                    bm.verts.new((width - wall_thickness, length - wall_thickness, shed_top(width - wall_thickness))),
                    bm.verts.new((wall_thickness, length - wall_thickness, shed_top(wall_thickness)))
                ]
            else:
                # ✅ FIX: Pour les toits en pente (GABLE/HIP/GAMBREL), la dalle
                # du toit descend de ROOF_THICKNESS sous le plan de base —
                # abaisser le plafond des murs pour ne pas transpercer le toit
                # près des avant-toits. FLAT garde la hauteur pleine.
                if props.roof_type in ('GABLE', 'HIP', 'GAMBREL'):
                    cap = ROOF_THICKNESS_PITCHED + 0.05
                else:
                    cap = 0.0
                outer_top = [bm.verts.new(v.co + Vector((0, 0, h - cap))) for v in outer]
                inner_top = [bm.verts.new(v.co + Vector((0, 0, h - cap))) for v in inner]
            
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

        # ✅ FIX: Profondeur/paramètres PARTAGÉS via helpers (les valeurs
        # divergentes créaient des jeux entre trous et fenêtres)
        wall_depth = self._get_wall_depth(props)
        style_config = self._apply_architectural_style(props)
        layout = self._get_window_layout(props, style_config)
        window_height_ratio = layout['height_ratio']
        num_windows_front = layout['num_front']
        num_windows_side = layout['num_side']

        # ✅ FIX: Utiliser la hauteur RÉELLE si disponible
        if getattr(self, 'real_wall_height', None):
            floor_height_actual = self.real_wall_height / props.num_floors
        else:
            floor_height_actual = props.floor_height

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
            'depth': wall_depth,
            'wall': 'front',
            'type': 'door'
        })

        # FENÊTRES
        for floor in range(props.num_floors):
            floor_z = floor * floor_height_actual
            # ✅ FIX: Géométrie verticale partagée (les ouvertures briques
            # utilisent le BAS de la fenêtre)
            window_height, window_z, _ = self._window_vertical(
                floor_z, floor_height_actual, window_height_ratio)
            window_width = layout['width']
            
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
                    'depth': wall_depth,
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
                    'depth': wall_depth,
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
                    'depth': wall_depth,
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
                    'depth': wall_depth,
                    'wall': 'right',
                    'type': 'window'
                })
        
        return openings
    
    def _generate_floors(self, context, props, collection):
        """Génère les planchers"""
        width = props.house_width
        length = props.house_length
        floor_thickness = FLOOR_THICKNESS

        # ✅ FIX: Calculer l'encastrement depuis l'épaisseur RÉELLE des murs.
        # L'ancien ratio 0.95 faisait déborder le plancher DANS les murs
        # pour toute maison de moins de 10m.
        wall_t = self._get_wall_depth(props)
        inset_width = max(0.1, width - 2 * wall_t)
        inset_length = max(0.1, length - 2 * wall_t)

        floors = []

        for floor_num in range(props.num_floors):
            if floor_num == 0:
                z_pos = floor_thickness / 2
            else:
                z_pos = floor_num * props.floor_height + floor_thickness / 2

            location = Vector((width/2, length/2, z_pos))
            dimensions = Vector((inset_width, inset_length, floor_thickness))

            floor_name = "Floor_Ground" if floor_num == 0 else f"Floor_{floor_num}"
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
        # ✅ NORMES: Pente clampée à la plage normative du type de toit —
        # même valeur que celle utilisée pour les murs adaptés (cohérence)
        roof_pitch = self._effective_pitch(roof_type, props.roof_pitch)
        roof_overhang = props.roof_overhang
        
        if roof_type == 'FLAT':
            roof = self._create_flat_roof(width, length, total_height, roof_overhang, collection)
        elif roof_type == 'GABLE':
            roof = self._create_gable_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'HIP':
            roof = self._create_hip_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'SHED':
            roof = self._create_shed_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'GAMBREL':
            # ✅ NOUVEAU: Vrai toit mansarde/gambrel avec 2 pentes
            roof = self._create_gambrel_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        else:
            # Fallback pour types inconnus
            print(f"[House] ERREUR: Type de toit inconnu '{roof_type}', utilisation toit pignon par défaut")
            roof = self._create_gable_roof(width, length, total_height, roof_pitch, roof_overhang, collection)

        roof.name = f"Roof_{roof_type}"
        roof["house_part"] = "roof"
        collection.objects.link(roof)
        
        return roof
    
    def _create_flat_roof(self, width, length, height, overhang, collection):
        """Toit plat (toit-terrasse)

        ✅ NORMES: Ajout de l'ACROTÈRE — le muret périphérique obligatoire
        des toits-terrasses (généralement 15cm à 1m de haut). C'est LE
        marqueur visuel d'un toit plat réel; avant, le toit était une
        simple dalle posée.
        """
        thickness = ROOF_THICKNESS_FLAT
        parapet_height = 0.45   # Hauteur d'acrotère courante
        parapet_thick = 0.15    # Épaisseur du muret

        bm = bmesh.new()

        def add_box(x0, y0, z0, x1, y1, z1):
            """Boîte alignée sur les axes [x0..x1]×[y0..y1]×[z0..z1]"""
            vb = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
            vt = [bm.verts.new(c) for c in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
            bm.faces.new(vb[::-1])
            bm.faces.new(vt)
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([vb[i], vb[j], vt[j], vt[i]])

        try:
            o = overhang
            x0, x1 = -o, width + o
            y0, y1 = -o, length + o
            z_slab_top = height + thickness

            # Dalle de toiture
            add_box(x0, y0, height, x1, y1, z_slab_top)

            # Acrotère: 4 murets sur le pourtour de la dalle
            pt = parapet_thick
            z_top = z_slab_top + parapet_height
            add_box(x0, y0, z_slab_top, x1, y0 + pt, z_top)          # Avant
            add_box(x0, y1 - pt, z_slab_top, x1, y1, z_top)          # Arrière
            add_box(x0, y0 + pt, z_slab_top, x0 + pt, y1 - pt, z_top)  # Gauche
            add_box(x1 - pt, y0 + pt, z_slab_top, x1, y1 - pt, z_top)  # Droite

            roof, mesh = self._create_mesh_from_bmesh("Roof_Flat", bm)

        finally:
            bm.free()

        print(f"[House] Toit PLAT: dalle {thickness:.2f}m + acrotère {parapet_height:.2f}m")
        return roof
    
    @staticmethod
    def _rake_overhang(overhang):
        """✅ NORMES: Débord de RIVE (pignon) plus court que le débord
        d'ÉGOUT — en construction réelle, la rive fait 10-30cm quand
        l'égout fait 30-60cm. Avant, les deux étaient identiques."""
        return max(0.1, min(0.3, overhang * 0.4))

    def _create_gable_roof(self, width, length, height, pitch, overhang, collection):
        """Toit à 2 pans

        ✅ NORMES: Le faîtage court le long de la PLUS GRANDE dimension
        (avant: toujours le long de Y, donnant un toit anormalement haut
        et pentu pour toute maison plus large que longue).
        """
        pitch_rad = math.radians(pitch)
        roof_thickness = ROOF_THICKNESS_PITCHED

        o_eave = overhang                    # Débord d'égout (bas de pente)
        o_rake = self._rake_overhang(overhang)  # Débord de rive (pignons)

        ridge_along_y = length >= width  # Faîtage parallèle au grand côté

        bm = bmesh.new()

        try:
            h = height

            if ridge_along_y:
                # Faîtage le long de Y — pentes descendant vers ±X,
                # pignons sur les façades avant/arrière (rives en Y)
                rh = (width / 2) * math.tan(pitch_rad)

                v1 = bm.verts.new((-o_eave, -o_rake, h))
                v2 = bm.verts.new((width + o_eave, -o_rake, h))
                v3 = bm.verts.new((width + o_eave, length + o_rake, h))
                v4 = bm.verts.new((-o_eave, length + o_rake, h))

                v5 = bm.verts.new((width/2, -o_rake, h + rh))
                v6 = bm.verts.new((width/2, length + o_rake, h + rh))

                f1 = bm.faces.new([v1, v2, v5])          # Pignon avant (Y-)
                f2 = bm.faces.new([v2, v3, v6, v5])      # Pan droit (X+)
                f3 = bm.faces.new([v3, v4, v6])          # Pignon arrière (Y+)
                f4 = bm.faces.new([v4, v1, v5, v6])      # Pan gauche (X-)
            else:
                # Faîtage le long de X — pentes descendant vers ±Y,
                # pignons sur les murs gauche/droit (rives en X)
                rh = (length / 2) * math.tan(pitch_rad)

                v1 = bm.verts.new((-o_rake, -o_eave, h))
                v2 = bm.verts.new((width + o_rake, -o_eave, h))
                v3 = bm.verts.new((width + o_rake, length + o_eave, h))
                v4 = bm.verts.new((-o_rake, length + o_eave, h))

                v5 = bm.verts.new((-o_rake, length/2, h + rh))
                v6 = bm.verts.new((width + o_rake, length/2, h + rh))

                f1 = bm.faces.new([v1, v2, v6, v5])      # Pan avant (Y-)
                f2 = bm.faces.new([v2, v3, v6])          # Pignon droit (X+)
                f3 = bm.faces.new([v3, v4, v5, v6])      # Pan arrière (Y+)
                f4 = bm.faces.new([v4, v1, v5])          # Pignon gauche (X-)

            print(f"[House] Toit GABLE: faîtage {'Y' if ridge_along_y else 'X'} "
                  f"(grand côté), hauteur {rh:.2f}m, rives {o_rake:.2f}m / égouts {o_eave:.2f}m")

            # ✅ FIX: Utiliser solidify au lieu d'une extrusion -Z manuelle.
            # L'extrusion verticale des pignons (f1/f3) créait des faces
            # coplanaires dégénérées (z-fighting, géométrie non-manifold).
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=roof_thickness)

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
            roof_height = (width / 2) * math.tan(pitch_rad)
        else:
            # Ridge court le long de Y, pente le long de X
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

                # Ridge (arête centrale en haut) - PAS d'overhang sur le ridge!
                v5 = bm.verts.new((width/2, ridge_start_y, h + rh))
                v6 = bm.verts.new((width/2, ridge_end_y, h + rh))

                # 4 faces du toit + 2 triangles aux extrémités
                f1 = bm.faces.new([v1, v2, v5])  # Triangle avant (face Y-)
                f2 = bm.faces.new([v2, v3, v6, v5])  # Trapèze droite (face X+)
                f3 = bm.faces.new([v3, v4, v6])  # Triangle arrière (face Y+)
                f4 = bm.faces.new([v4, v1, v5, v6])  # Trapèze gauche (face X-)

            elif length < width:
                # House est plus long en X: ridge le long de X
                ridge_start_x = length / 2
                ridge_end_x = width - length / 2

                # Ridge (arête centrale en haut) - PAS d'overhang sur le ridge!
                v5 = bm.verts.new((ridge_start_x, length/2, h + rh))
                v6 = bm.verts.new((ridge_end_x, length/2, h + rh))

                # 4 faces du toit
                # ✅ FIX: f3 doit être le TRAPÈZE [v3,v4,v5,v6] et f4 le
                # TRIANGLE [v4,v1,v5] (les faces étaient inversées → toit
                # ouvert et auto-intersecté pour toute maison plus large que longue)
                f1 = bm.faces.new([v1, v2, v6, v5])  # Trapèze avant (face Y-)
                f2 = bm.faces.new([v2, v3, v6])      # Triangle droite (face X+)
                f3 = bm.faces.new([v3, v4, v5, v6])  # Trapèze arrière (face Y+)
                f4 = bm.faces.new([v4, v1, v5])      # Triangle gauche (face X-)

            else:
                # Maison carrée: pyramide parfaite avec sommet au centre
                v5 = bm.verts.new((width/2, length/2, h + rh))

                # 4 faces triangulaires
                f1 = bm.faces.new([v1, v2, v5])
                f2 = bm.faces.new([v2, v3, v5])
                f3 = bm.faces.new([v3, v4, v5])
                f4 = bm.faces.new([v4, v1, v5])

            # ✅ FIX: solidify donne une épaisseur propre et manifold
            # (l'extrusion -Z manuelle laissait la surface d'origine ouverte)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=roof_thickness)

            roof, mesh = self._create_mesh_from_bmesh("HipRoof", bm)

        finally:
            bm.free()

        return roof
    
    def _create_shed_roof(self, width, length, height, pitch, overhang, collection):
        """Toit monopente - Crée un volume fermé complet"""
        pitch_rad = math.radians(pitch)
        roof_height = width * math.tan(pitch_rad)
        roof_thickness = ROOF_THICKNESS_PITCHED

        bm = bmesh.new()

        try:
            h = height
            # ✅ NORMES: Les bords bas (x=0) et haut (x=width) sont des
            # ÉGOUTS (plein débord); les côtés Y sont des RIVES (débord court)
            o_eave = overhang
            o_rake = self._rake_overhang(overhang)
            t = roof_thickness

            # ✅ FIX: La pente doit être tan(pitch) sur TOUTE la surface, y
            # compris le débord. Avant, le toit montait de rh entre -o et
            # width+o, donc la pente réelle était plus faible et le toit
            # arrivait TROP BAS à x=width → les murs le transperçaient.
            slope = math.tan(pitch_rad)

            def roof_z(x):
                """Hauteur du toit à la position x (ligne de toit: h à x=0)"""
                return h + slope * x

            # Face supérieure du toit (4 vertices)
            v1_top = bm.verts.new((-o_eave, -o_rake, roof_z(-o_eave)))
            v2_top = bm.verts.new((width + o_eave, -o_rake, roof_z(width + o_eave)))
            v3_top = bm.verts.new((width + o_eave, length + o_rake, roof_z(width + o_eave)))
            v4_top = bm.verts.new((-o_eave, length + o_rake, roof_z(-o_eave)))

            # Face inférieure du toit (4 vertices décalés vers le bas)
            v1_bot = bm.verts.new((-o_eave, -o_rake, roof_z(-o_eave) - t))
            v2_bot = bm.verts.new((width + o_eave, -o_rake, roof_z(width + o_eave) - t))
            v3_bot = bm.verts.new((width + o_eave, length + o_rake, roof_z(width + o_eave) - t))
            v4_bot = bm.verts.new((-o_eave, length + o_rake, roof_z(-o_eave) - t))

            # Créer les 6 faces pour fermer le volume
            # Face supérieure (inclinée)
            f_top = bm.faces.new([v1_top, v2_top, v3_top, v4_top])

            # Face inférieure (inclinée, sens inverse)
            f_bot = bm.faces.new([v4_bot, v3_bot, v2_bot, v1_bot])

            # 4 faces latérales pour fermer le volume
            f_front = bm.faces.new([v1_top, v2_top, v2_bot, v1_bot])  # Face avant (Y-)
            f_right = bm.faces.new([v2_top, v3_top, v3_bot, v2_bot])  # Face droite (X+)
            f_back = bm.faces.new([v3_top, v4_top, v4_bot, v3_bot])   # Face arrière (Y+)
            f_left = bm.faces.new([v4_top, v1_top, v1_bot, v4_bot])   # Face gauche (X-)

            roof, mesh = self._create_mesh_from_bmesh("ShedRoof", bm)

        finally:
            bm.free()

        return roof

    def _create_gambrel_roof(self, width, length, height, pitch, overhang, collection):
        """Toit mansarde/gambrel - 2 pentes par côté (raide puis douce)"""
        pitch_rad = math.radians(pitch)
        roof_thickness = ROOF_THICKNESS_PITCHED

        # ✅ NORMES MANSARDE: Les proportions étaient INVERSÉES par rapport
        # à un vrai comble à la Mansart. En réalité:
        #   - BRISIS (segment bas): TRÈS RAIDE, ~60-75° (fixé ici à 68°)
        #     sur une courte distance horizontale (~25% de la demi-largeur)
        #   - TERRASSON (segment haut): DOUX, 15-30° (= pente utilisateur,
        #     clampée par _effective_pitch)
        # Avant: brisis = pente utilisateur (35°) et terrasson = pente/2.5,
        # ce qui donnait un simple gable "cassé", pas une mansarde.
        BRISIS_ANGLE = 68.0
        brisis_rad = math.radians(BRISIS_ANGLE)

        # Le brisis couvre 25% de la demi-largeur (course horizontale courte)
        break_ratio = 0.25
        break_distance = (width / 2) * break_ratio

        # Hauteur du brisis (raide → haut malgré la courte distance)
        break_height = break_distance * math.tan(brisis_rad)

        # Terrasson: pente douce utilisateur sur le reste
        terrasson_rad = pitch_rad
        remaining_distance = (width / 2) * (1 - break_ratio)
        upper_height = remaining_distance * math.tan(terrasson_rad)

        # Hauteur totale du toit
        total_roof_height = break_height + upper_height

        print(f"[House] Toit MANSARDE: brisis {BRISIS_ANGLE:.0f}° ({break_height:.2f}m), "
              f"terrasson {pitch:.0f}° ({upper_height:.2f}m), total {total_roof_height:.2f}m")

        bm = bmesh.new()

        try:
            h = height
            # ✅ NORMES: Égouts en X (bas des brisis), rives courtes en Y
            o = overhang
            o_rake = self._rake_overhang(overhang)
            rh = total_roof_height
            t = roof_thickness

            # Position X de la cassure (break point)
            break_x_left = width/2 - break_distance
            break_x_right = width/2 + break_distance

            # ✅ GÉOMÉTRIE COMPLÈTE CORRIGÉE
            # Base (4 coins)
            v1 = bm.verts.new((-o, -o_rake, h))
            v2 = bm.verts.new((width + o, -o_rake, h))
            v3 = bm.verts.new((width + o, length + o_rake, h))
            v4 = bm.verts.new((-o, length + o_rake, h))

            # Break points gauche (4 vertices)
            v5_front = bm.verts.new((break_x_left, -o_rake, h + break_height))
            v5_back = bm.verts.new((break_x_left, length + o_rake, h + break_height))

            # Break points droite (4 vertices)
            v6_front = bm.verts.new((break_x_right, -o_rake, h + break_height))
            v6_back = bm.verts.new((break_x_right, length + o_rake, h + break_height))

            # Sommet (ridge - 2 vertices)
            v_top_front = bm.verts.new((width/2, -o_rake, h + rh))
            v_top_back = bm.verts.new((width/2, length + o_rake, h + rh))

            # ✅ FACES PRINCIPALES (surface extérieure)
            # Pente GAUCHE (2 trapèzes)
            f1 = bm.faces.new([v1, v4, v5_back, v5_front])  # Trapèze inférieur gauche
            f2 = bm.faces.new([v5_front, v5_back, v_top_back, v_top_front])  # Trapèze supérieur gauche

            # Pente DROITE (2 trapèzes)
            f3 = bm.faces.new([v2, v6_front, v6_back, v3])  # Trapèze inférieur droit
            f4 = bm.faces.new([v6_front, v_top_front, v_top_back, v6_back])  # Trapèze supérieur droit

            # Pignon AVANT - Y- (4 triangles formant le W)
            f5 = bm.faces.new([v1, v2, v6_front, v5_front])  # Base avant
            f6 = bm.faces.new([v5_front, v6_front, v_top_front])  # Sommet avant

            # Pignon ARRIÈRE - Y+ (4 triangles formant le W)
            f7 = bm.faces.new([v4, v5_back, v6_back, v3])  # Base arrière
            f8 = bm.faces.new([v5_back, v_top_back, v6_back])  # Sommet arrière

            # ✅ FIX: solidify au lieu d'extrusion -Z manuelle — l'extrusion
            # verticale des pignons (f5-f8) créait des faces coplanaires
            # dégénérées (épaisseur nulle, z-fighting)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=t)

            roof, mesh = self._create_mesh_from_bmesh("GambrelRoof", bm)

        finally:
            bm.free()

        return roof

    def _generate_wall_openings(self, context, props, collection, walls, style_config):
        """Génère les trous dans les murs (Boolean) - pour murs SIMPLES uniquement"""
        width = props.house_width
        length = props.house_length

        # ✅ FIX: Paramètres fenêtres partagés (mêmes valeurs que les visuels)
        layout = self._get_window_layout(props, style_config)
        window_height_ratio = layout['height_ratio']
        num_windows_front = layout['num_front']
        num_windows_side = layout['num_side']
        wall_thickness = props.wall_thickness

        combined_bm = bmesh.new()

        try:
            # PORTE
            door_height = DOOR_HEIGHT
            door_width = props.front_door_width
            door_depth = wall_thickness + DOOR_DEPTH_EXTRA

            door_bm = bmesh.new()
            bmesh.ops.create_cube(door_bm, size=1.0)

            door_scale = Matrix.Diagonal((door_width, door_depth, door_height, 1.0))
            bmesh.ops.transform(door_bm, matrix=door_scale, verts=door_bm.verts)

            door_location = Vector((width/2, wall_thickness/2, door_height/2))
            bmesh.ops.translate(door_bm, verts=door_bm.verts, vec=door_location)

            # ✅ FIX: index_update() obligatoire — les .index de bmesh ne sont
            # pas maintenus automatiquement (faces du cutter corrompues sinon)
            door_bm.verts.index_update()
            vert_offset = len(combined_bm.verts)
            for v in door_bm.verts:
                combined_bm.verts.new(v.co)
            combined_bm.verts.ensure_lookup_table()

            for f in door_bm.faces:
                combined_bm.faces.new([combined_bm.verts[vert_offset + v.index] for v in f.verts])

            door_bm.free()

            # FENÊTRES
            for floor in range(props.num_floors):
                floor_z = floor * props.floor_height
                # ✅ FIX: Géométrie verticale partagée (le cutter des murs
                # simples est centré sur le CENTRE de la fenêtre)
                window_height, _, window_z = self._window_vertical(
                    floor_z, props.floor_height, window_height_ratio)
                window_depth = wall_thickness + WINDOW_DEPTH_EXTRA
                window_width = layout['width']

                spacing_front = width / (num_windows_front + 1)
                for i in range(num_windows_front):
                    x_pos = spacing_front * (i + 1)

                    if floor == 0 and abs(x_pos - width/2) < door_width * 1.5:
                        continue

                    self._add_window_to_combined_mesh(
                        combined_bm, x_pos, wall_thickness/2, window_z,
                        window_width, window_depth, window_height
                    )

                for i in range(num_windows_front):
                    x_pos = spacing_front * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, x_pos, length - wall_thickness/2, window_z,
                        window_width, window_depth, window_height
                    )

                spacing_side = length / (num_windows_side + 1)
                for i in range(num_windows_side):
                    y_pos = spacing_side * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, wall_thickness/2, y_pos, window_z,
                        window_depth, window_width, window_height
                    )

                for i in range(num_windows_side):
                    y_pos = spacing_side * (i + 1)
                    self._add_window_to_combined_mesh(
                        combined_bm, width - wall_thickness/2, y_pos, window_z,
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

        # ✅ FIX: index_update() obligatoire — .index n'est pas maintenu par bmesh
        window_bm.verts.index_update()
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

        # ✅ FIX: Paramètres PARTAGÉS avec les ouvertures — le "jeu" entre
        # les trous et les fenêtres venait de valeurs calculées différemment
        layout = self._get_window_layout(props, style_config)
        window_height_ratio = layout['height_ratio']
        num_windows_front = layout['num_front']
        num_windows_side = layout['num_side']

        # ✅ FIX: Utiliser la hauteur RÉELLE si disponible (murs en briques)
        if getattr(self, 'real_wall_height', None):
            floor_height_actual = self.real_wall_height / props.num_floors
            print(f"[House] Fenêtres positionnées selon hauteur réelle: {floor_height_actual:.3f}m/étage")
        else:
            floor_height_actual = props.floor_height
            print(f"[House] Fenêtres positionnées selon hauteur théorique: {floor_height_actual:.3f}m/étage")

        # ✅ FIX: Profondeur de mur partagée (0.112m briques / épaisseur réglée sinon)
        wall_depth = self._get_wall_depth(props)
        print(f"[House] Fenêtres ajustées: profondeur mur {wall_depth*100:.1f}cm")

        window_width = layout['width']

        window_gen = WindowGenerator(quality=props.window_quality)

        for floor in range(props.num_floors):
            floor_z = floor * floor_height_actual
            # ✅ FIX MAJEUR: L'objet fenêtre est construit CENTRÉ sur son
            # origine, mais les ouvertures des murs briques stockent le BAS
            # du trou → la fenêtre visuelle était une demi-hauteur trop bas
            # (le fameux "jeu" entre le trou et la fenêtre). On place
            # désormais la fenêtre à son CENTRE, cohérent avec le trou.
            window_height, _, window_z = self._window_vertical(
                floor_z, floor_height_actual, window_height_ratio)

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
                    location=Vector((x_pos, wall_depth/2, window_z)),
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
                    location=Vector((x_pos, length - wall_depth/2, window_z)),
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
                    location=Vector((wall_depth/2, y_pos, window_z)),
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
                    location=Vector((width - wall_depth/2, y_pos, window_z)),
                    orientation='right',
                    collection=collection
                )

    def _generate_door_visual(self, context, props, collection):
        """Génère la porte d'entrée visuelle (objet 3D)"""
        from .doors import DOOR_FRAME_DEPTH

        width = props.house_width

        # ✅ FIX: Profondeur de mur partagée avec les ouvertures
        wall_depth = self._get_wall_depth(props)

        door_width = props.front_door_width
        door_height = DOOR_HEIGHT
        door_x = width/2  # Position centrale

        print(f"[House] Génération porte visuelle {props.door_type}: {door_width}x{door_height}m")

        door_gen = DoorGenerator(quality=props.door_quality)

        # ✅ FIX: Le cadre de porte s'étend de y=0 à y=DOOR_FRAME_DEPTH dans
        # son repère local — on le CENTRE dans l'épaisseur du mur (avant, il
        # était enfoncé d'une demi-épaisseur vers l'intérieur de la maison)
        door_gen.generate_door(
            door_type=props.door_type,
            width=door_width,
            height=door_height,
            location=Vector((door_x - door_width/2, (wall_depth - DOOR_FRAME_DEPTH) / 2, 0)),
            orientation='front',
            collection=collection
        )

    def _generate_foundation(self, context, props, collection):
        """Génère les fondations visuelles (socle béton/pierre)

        ✅ FIX MAJEUR: L'ancien socle était centré à -height/2 → son sommet
        affleurait exactement z=0: il était ENTIÈREMENT enterré et donc
        invisible! Un soubassement réel dépasse de 15-25cm du sol.
        ✅ NORMES: Ajout d'un SEUIL (perron) devant la porte pour franchir
        le soubassement — sans lui, le bas de la porte était masqué par
        la bande de socle.
        """

        if props.foundation_height <= 0:
            print("[House] Fondations désactivées (hauteur = 0)")
            return

        width = props.house_width
        length = props.house_length
        height = props.foundation_height

        # Partie VISIBLE au-dessus du sol (soubassement): 40% plafonné à 20cm
        visible = min(0.2, height * 0.4)

        # Les fondations dépassent légèrement des murs
        foundation_overhang = 0.15  # 15cm de débord

        print(f"[House] Génération fondations: "
              f"{width+2*foundation_overhang:.2f}x{length+2*foundation_overhang:.2f}x{height:.2f}m "
              f"(visible: {visible*100:.0f}cm)")

        bm = bmesh.new()

        try:
            # Créer un bloc rectangulaire
            bmesh.ops.create_cube(bm, size=1.0)

            # Mise à l'échelle
            scale_matrix = Matrix.Diagonal((
                width + 2*foundation_overhang,
                length + 2*foundation_overhang,
                height,
                1.0
            ))
            bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)

            # ✅ FIX: Sommet du socle à +visible (et non à 0)
            translate_vec = Vector((
                width/2,
                length/2,
                visible - height/2
            ))
            bmesh.ops.translate(bm, verts=bm.verts, vec=translate_vec)

            # ✅ NOUVEAU: SEUIL DE PORTE (perron) — marche devant l'entrée
            door_width = props.front_door_width
            step_width = door_width + 0.4          # 20cm de chaque côté
            step_depth = 0.6 + foundation_overhang  # Dépasse le socle
            x0 = width/2 - step_width/2
            x1 = width/2 + step_width/2

            step_verts_b = [bm.verts.new(c) for c in (
                (x0, -step_depth, 0), (x1, -step_depth, 0),
                (x1, 0.02, 0), (x0, 0.02, 0))]
            step_verts_t = [bm.verts.new(c) for c in (
                (x0, -step_depth, visible), (x1, -step_depth, visible),
                (x1, 0.02, visible), (x0, 0.02, visible))]
            bm.faces.new(step_verts_b[::-1])
            bm.faces.new(step_verts_t)
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([step_verts_b[i], step_verts_b[j], step_verts_t[j], step_verts_t[i]])

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            foundation_mesh = bpy.data.meshes.new("Foundation_Mesh")
            bm.to_mesh(foundation_mesh)
            foundation_mesh.update()

        finally:
            bm.free()

        foundation_obj = bpy.data.objects.new("Foundation", foundation_mesh)
        foundation_obj["house_part"] = "foundation"
        collection.objects.link(foundation_obj)

        # Appliquer matériau béton/pierre
        self._apply_foundation_material(foundation_obj)

        print("[House] ✓ Fondations générées (socle visible + seuil de porte)")

    def _apply_foundation_material(self, obj):
        """Applique un matériau béton aux fondations"""
        mat_name = "Foundation_Material"

        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()

            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)  # Gris béton
            bsdf.inputs['Roughness'].default_value = 0.8
            # Note: 'Specular' n'existe plus dans Blender 4.2+

            output = nodes.new('ShaderNodeOutputMaterial')
            mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        else:
            mat = bpy.data.materials[mat_name]

        obj.data.materials.clear()
        obj.data.materials.append(mat)

    # ============================================================
    # FONCTIONNALITÉS NON IMPLÉMENTÉES (TODO)
    # ============================================================

    def _generate_garage(self, context, props, collection):
        """Génère un garage"""
        # TODO: Implémenter la génération de garage
        print("[House] ⚠️  AVERTISSEMENT: Génération de garage non implémentée")
        self.report({'WARNING'}, "Garage: Fonctionnalité non encore implémentée")

    def _generate_terrace(self, context, props, collection):
        """Génère une terrasse"""
        # TODO: Implémenter la génération de terrasse
        print("[House] ⚠️  AVERTISSEMENT: Génération de terrasse non implémentée")
        self.report({'WARNING'}, "Terrasse: Fonctionnalité non encore implémentée")

    def _generate_balcony(self, context, props, collection):
        """Génère un balcon"""
        # TODO: Implémenter la génération de balcon
        print("[House] ⚠️  AVERTISSEMENT: Génération de balcon non implémentée")
        self.report({'WARNING'}, "Balcon: Fonctionnalité non encore implémentée")

    def _generate_balcony_railing(self, context, props, collection, balcony_width, balcony_depth, x_pos, y_pos, z_pos):
        """Génère la rambarde"""
        # TODO: Implémenter la rambarde de balcon
        pass

    def _add_railing_segment(self, bm, x, y, z, width, depth, height):
        """Ajoute un segment de rambarde"""
        # TODO: Implémenter les segments de rambarde
        pass

    def _add_railing_post(self, bm, x, y, z, width, depth, height):
        """Ajoute un poteau"""
        # TODO: Implémenter les poteaux de rambarde
        pass

    def _add_scene_lighting(self, context, props):
        """Ajoute l'éclairage automatique"""
        # TODO: Implémenter l'éclairage automatique de scène
        print("[House] ⚠️  AVERTISSEMENT: Éclairage automatique non implémenté")
        self.report({'WARNING'}, "Éclairage automatique: Fonctionnalité non encore implémentée")
    
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
        # ✅ FIX: Chercher par TYPE de node, pas par nom anglais (les noms
        # peuvent être localisés/renommés → matériau noir silencieux)
        principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)

        if not principled:
            principled = nodes.new(type='ShaderNodeBsdfPrincipled')
            output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
            if not output:
                output = nodes.new(type='ShaderNodeOutputMaterial')
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
        
        # ✅ Compat Blender 4.2+ (EEVEE Next): 'surface_render_method' remplace
        # 'blend_method' (conservé en fallback pour les versions antérieures)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = 'BLENDED'
        elif hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
        # Note: 'shadow_method' n'existe plus dans Blender 4.2+ (EEVEE Next)

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