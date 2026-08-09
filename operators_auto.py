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

# ✅ S8: dimensions canoniques dans norms.py (source unique documentée)
from .norms import (MUR_EP_BASE as WALL_THICKNESS,
                    DALLE_EP as FLOOR_THICKNESS,
                    FONDATION_EP as FOUNDATION_THICKNESS,
                    TOIT_DALLE_TERRASSE_EP as ROOF_THICKNESS_FLAT,
                    TOIT_DALLE_RAMPANT_EP as ROOF_THICKNESS_PITCHED,
                    PORTE_ENTREE_H as DOOR_HEIGHT)

# Constantes - Ouvertures
OPENING_OFFSET = 0.02
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

# ✅ v1.13: PROXY VIEWPORT — les instanciations GN les plus lourdes
# (milliers de tuiles, ~50k touffes d'herbe) sont suspendues DANS LA
# VUE 3D seulement; le rendu F12 reste complet. La silhouette reste
# lisible: les dalles de toit et le sol sont des objets séparés. Les
# briques restent affichées (elles SONT les murs).
PROXY_PREFIXES = ("Roof_Tiles", "Wing_Tiles", "Env_Grass")


def apply_viewport_proxy(collection, enabled):
    """(Dés)active l'allègement viewport sur les instanciateurs lourds."""
    n = 0
    for obj in collection.objects:
        if not obj.name.startswith(PROXY_PREFIXES):
            continue
        for mod in obj.modifiers:
            if mod.type == 'NODES':
                mod.show_viewport = not enabled
                n += 1
    print(f"[House] Proxy viewport {'ON' if enabled else 'OFF'}: "
          f"{n} instanciation(s) concernée(s)")
    return n


class HOUSE_OT_generate_auto(Operator):
    """Génère automatiquement une maison selon les paramètres"""
    bl_idname = "house.generate_auto"
    bl_label = "Générer la maison"
    bl_options = {'REGISTER', 'UNDO'}

    # ✅ v1.13: tags de domaines invalidés ("joinery,roof", …) — vide
    # ou "all" = reconstruction complète. Rempli par la mise à jour
    # auto (properties.regenerate_house) qui diffe les props changées.
    invalidate: bpy.props.StringProperty(
        name="Domaines invalidés", default="",
        options={'HIDDEN', 'SKIP_SAVE'})

    def _try_incremental(self, context, props, pipeline):
        """Prépare une régénération INCRÉMENTALE si possible.

        Retourne (collection, steps) ou None si les conditions ne sont
        pas réunies (pas d'état sauvegardé, collection absente, objets
        non estampillés — vieux fichier) → reconstruction complète.
        """
        inval = {t for t in self.invalidate.split(",") if t}
        if not inval or "all" in inval or not pipeline.LAST_STATE:
            return None
        collection = bpy.data.collections.get(
            props.collection_name or "House")
        if collection is None or not len(collection.objects):
            return None
        if any("house_step" not in o.keys() for o in collection.objects):
            return None  # scène d'une version antérieure → full
        steps = pipeline.steps_for_tags(inval)
        replay = {s.name for s in steps}
        for obj in list(collection.objects):
            if obj.get("house_step") in replay:
                mesh = obj.data if obj.type == 'MESH' else None
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh is not None and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
        pipeline.restore_state(self)
        # La distribution intérieure dépend de props qui ont pu changer
        if inval & {"interior", "structure"}:
            self._interior_layout = None
        # Travail de seed_style SANS ses remises à zéro destructrices
        if props.random_seed > 0:
            random.seed(props.random_seed)
        self.style_config = self._apply_architectural_style(props)
        print(f"[House] Régénération INCRÉMENTALE {sorted(inval)} → "
              f"{[s.name for s in steps]}")
        return collection, steps

    def execute(self, context):
        """✅ v1.11: la construction est un PIPELINE DÉCLARATIF
        (voir pipeline.py) — ordre et dépendances explicites, validés
        statiquement à l'import et contractuellement à l'exécution.
        Ce corps n'est plus que le driver. ✅ v1.13: si `invalidate`
        cible des domaines précis, seules leurs étapes sont rejouées."""
        from . import pipeline
        props = context.scene.house_generator

        print("[House] Début de la génération...")
        if props.random_seed > 0:
            print(f"[House] Seed: {props.random_seed}")

        inc = self._try_incremental(context, props, pipeline)
        if inc is not None:
            house_collection, steps = inc
        else:
            house_collection = self._create_house_collection(context)
            steps = pipeline.HOUSE_STEPS
        try:
            pipeline.run_pipeline(steps, self, context,
                                  props, house_collection)
            pipeline.save_state(self)
            from . import properties as _props_mod
            _props_mod.update_snapshot(props)
            if getattr(context.scene, 'house_viewport_proxy', False):
                apply_viewport_proxy(house_collection, True)
            print(f"[House] Terminé! Style: {props.architectural_style}, "
                  f"Fenêtres: {props.window_type}")
            self.report({'INFO'},
                        f"Maison générée! Style: {props.architectural_style}, "
                        f"Fenêtres: {props.window_type}")
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
        # ✅ FIX: Comparer au défaut DÉCLARÉ de la propriété (le littéral
        # 0.4 en dur cassait silencieusement si le défaut changeait)
        default_ratio = props.bl_rna.properties['window_height_ratio'].default
        if abs(props.window_height_ratio - default_ratio) > 1e-6:
            ratio = props.window_height_ratio  # L'utilisateur a changé le slider
        else:
            ratio = style_config.get('window_height_ratio', props.window_height_ratio)
        return {
            'num_front': props.num_windows_front,
            'num_back': props.num_windows_back,
            'num_side': props.num_windows_side,
            'width': props.window_width,
            'height_ratio': ratio,
        }

    @staticmethod
    def _window_vertical(floor_z, floor_height, height_ratio):
        """✅ S3: délègue au MODÈLE DE NIVEAUX (levels.py) — la formule
        canonique (hauteur, allège, centre) vit là-bas."""
        from . import levels
        return levels.window_vertical(floor_z, floor_height, height_ratio)

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
            from .features import box_uv
            box_uv(mesh)          # ✅ S7: UVs systématiques

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
            from .features import box_uv
            box_uv(mesh)          # ✅ S7: UVs systématiques

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

    def _get_wing_frames(self, props):
        """✅ v1.5: repères des ailes actives (1 ou 2), avec étages clampés
        aux étages de la maison et contrôle de chevauchement."""
        from . import volumes
        eff = self._effective_pitch(props.roof_type, props.roof_pitch)
        brick = props.wall_construction_type == 'BRICK_3D'
        if brick:
            from .materials.brick_geometry import compute_real_wall_height
            h_main, _ = compute_real_wall_height(props.num_floors * props.floor_height)
        else:
            h_main = props.num_floors * props.floor_height

        def make(side, w, d, off, floors):
            floors = max(1, min(int(floors), props.num_floors))
            if brick:
                from .materials.brick_geometry import compute_real_wall_height
                h_wing, _ = compute_real_wall_height(floors * props.floor_height)
            else:
                h_wing = floors * props.floor_height
            f = volumes.wing_frame(props, eff, h_main, h_wing,
                                   side=side, wing_width=w, wing_depth=d,
                                   wing_offset=off)
            if f:
                f['floors'] = floors
                f['fh'] = f['h'] / floors
            return f

        frames = []
        if getattr(props, 'include_wing', False):
            f1 = make(props.wing_side, props.wing_width, props.wing_depth,
                      props.wing_offset, getattr(props, 'wing_floors', 1))
            if f1:
                frames.append(f1)
            if getattr(props, 'include_wing2', False):
                f2 = make(props.wing2_side, props.wing2_width, props.wing2_depth,
                          props.wing2_offset, getattr(props, 'wing2_floors', 1))
                if f2:
                    if any(volumes.frames_overlap(f2, f) for f in frames):
                        print("[House] ⚠️ Aile 2 en chevauchement avec l'aile 1 — ignorée")
                    else:
                        frames.append(f2)

        # ✅ v1.7: le GARAGE est une AILE maçonnée avec vraie toiture
        # (positions LEFT/RIGHT/FRONT; ATTACHED = RIGHT)
        if getattr(props, 'include_garage', False) and \
                props.roof_type in ('GABLE', 'HIP', 'GAMBREL'):
            gpos = getattr(props, 'garage_position', 'RIGHT')
            side = {'LEFT': 'LEFT', 'RIGHT': 'RIGHT', 'FRONT': 'FRONT',
                    'ATTACHED': 'RIGHT'}[gpos]
            if side in ('LEFT', 'RIGHT'):
                gw, gd, goff = props.garage_depth, props.garage_width, 0.0
            else:
                gw, gd, goff = props.garage_width, props.garage_depth, 0.0
            fg = make(side, gw, gd, goff, 1)
            if fg:
                if any(volumes.frames_overlap(fg, f) for f in frames):
                    print("[House] ⚠️ Garage en chevauchement avec une aile — "
                          "garage simple conservé")
                else:
                    fg['garage'] = True
                    frames.append(fg)
                    self._garage_as_wing = True
        return frames

    def _covered_by_wing(self, wall, center_along, margin=0.35):
        """True si une position de fenêtre est masquée par l'aile."""
        for wing in getattr(self, '_wings', []):
            if wing['attached_wall'] != wall:
                continue
            a0, a1 = wing['span']
            if (a0 - margin) < center_along < (a1 + margin):
                return True
        return False

    def _door_center_x(self, props):
        """✅ MULTI-VOLUMES: centre de la porte d'entrée — déplacée dans le
        plus grand segment libre si l'aile couvre le centre de la façade."""
        width = props.house_width
        cx = width / 2
        spans = sorted(w['span'] for w in getattr(self, '_wings', [])
                       if w['attached_wall'] == 'front')
        if any((a0 - 0.35) < cx < (a1 + 0.35) for (a0, a1) in spans):
            # segments libres entre les ailes
            free, cursor = [], 0.0
            for (a0, a1) in spans:
                if a0 > cursor:
                    free.append((cursor, a0))
                cursor = max(cursor, a1)
            if cursor < width:
                free.append((cursor, width))
            dw = props.front_door_width
            free = [(s, e) for (s, e) in free if e - s >= dw + 0.6] or [(0.0, width)]
            s, e = max(free, key=lambda f: f[1] - f[0])
            cx = max(dw / 2 + 0.3, min(width - dw / 2 - 0.3, (s + e) / 2))
            print(f"[House] Aile devant l'entrée → porte déplacée à x={cx:.2f}m")
        return cx

    def _generate_wing(self, context, props, collection, wing):
        """✅ MULTI-VOLUMES: fondations, plancher et toit d'UNE aile.
        (Les murs sont fusionnés dans le nuage de briques, ou générés en
        mode murs simples par _generate_walls.)"""
        from . import volumes
        volumes.build_wing_foundation(props, collection, wing,
                                      self._plinth_visible(props))
        volumes.build_wing_floor(props, collection, wing)
        volumes.build_wing_roof(
            props, collection, wing,
            o_eave=props.roof_overhang,
            o_rake=self._rake_overhang(props.roof_overhang),
            tile_color=tuple(props.tile_color)[:3],
            make_tiles=(props.roof_covering == 'TILES'))
        if wing.get('garage'):
            volumes.build_garage_wing_door(
                wing, props, collection, wing.get('garage_opening'),
                wing.get('garage_front_local'))

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

            # ✅ MULTI-VOLUMES: briques de l'aile calculées dans son repère
            # local (pignon maçonné, briques coupées, linteaux) puis
            # fusionnées dans le MÊME nuage Geometry Nodes
            if getattr(self, '_wings', None):
                from . import volumes
                extra = []
                for wing in self._wings:
                    extra += volumes.compute_wing_brick_positions(
                        wing, props, wing.get('openings') or [])
                brick_kwargs['extra_positions'] = extra

            if props.brick_use_geonodes:
                # ✅ NOUVEAU MOTEUR: 1 objet Geometry Nodes au lieu de
                # milliers d'instances (fallback auto si erreur)
                from .materials import brick_geonodes
                # ✅ FIX: Snapshot pour purger les objets partiels si le
                # moteur GN échoue (sinon Brick_Master orphelin + point
                # cloud fantôme restaient dans la collection)
                pre_objs = set(collection.objects)
                try:
                    walls, real_wall_height = brick_geonodes.generate_walls_geonodes(
                        width, length, total_height, collection,
                        props.brick_3d_quality, **brick_kwargs)
                except Exception as e:
                    print(f"[House] ⚠️ Moteur GN échoué ({e}) → fallback instancing")
                    import traceback
                    traceback.print_exc()
                    for obj in [o for o in collection.objects if o not in pre_objs]:
                        mesh_data = obj.data if obj.type == 'MESH' else None
                        bpy.data.objects.remove(obj, do_unlink=True)
                        if mesh_data is not None and mesh_data.users == 0:
                            bpy.data.meshes.remove(mesh_data)
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
                # ✅ FIX: Pour les toits en pente, la dalle du toit descend
                # sous le plan de base — abaisser le plafond des murs pour ne
                # pas transpercer le toit près des avant-toits.
                # ✅ FIX 2: solidify épaissit PERPENDICULAIREMENT → la chute
                # VERTICALE est thickness/cos(pente): la marge doit suivre
                # (GABLE/HIP). GAMBREL est en dalles verticales → 0.15 suffit.
                if props.roof_type in ('GABLE', 'HIP'):
                    eff = self._effective_pitch(props.roof_type, props.roof_pitch)
                    cap = self.slab_vertical_drop(eff) + 0.05
                elif props.roof_type == 'GAMBREL':
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

        # ✅ MULTI-VOLUMES: murs de l'aile (segments exacts + pignon prisme)
        for wing in getattr(self, '_wings', []):
            from . import volumes
            walls += volumes.build_wing_simple_walls(
                wing, props, collection, wing.get('openings') or [])

        return walls

    def _calculate_openings_for_brick_walls(self, props):
        """✅ S4: délègue à la SPEC D'OUVERTURE UNIFIÉE (openings.py) —
        même liste pour les trous briques, les Booleans, les menuiseries
        et les volets."""
        from . import openings as openings_mod
        return openings_mod.compute(self, props)

    def _calculate_openings_LEGACY_S4(self, props):
        """Corps historique conservé en référence pendant S4 (supprimé
        après validation complète) — NE PLUS APPELER."""
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
        door_x = self._door_center_x(props) - door_width/2

        openings.append({
            'x': door_x,
            'y': 0,
            # ✅ FIX: L'ouverture démarre au niveau du seuil (soubassement
            # visible) — cohérent avec la porte visuelle posée dessus
            'z': self._plinth_visible(props),
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

                if floor == 0 and abs(x_pos - self._door_center_x(props)) < door_width * 1.5:
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
            # ✅ FIX: num_windows_back enfin câblé (la façade arrière
            # copiait toujours le compte de la façade avant)
            num_windows_back = layout['num_back']
            spacing_back = width / (num_windows_back + 1)
            for i in range(num_windows_back):
                x_pos = spacing_back * (i + 1)
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

        # ✅ v1.7: PORTE-FENÊTRE derrière le balcon (étage 1, façade avant)
        if getattr(props, 'include_balcony', False) and props.num_floors > 1:
            pf_w = min(1.5, max(1.1, getattr(props, 'balcony_width', 2.6) - 0.6))
            pf_z = floor_height_actual + 0.02
            pf_x = width / 2 - pf_w / 2
            # supprimer les fenêtres avant de l'étage 1 qui chevauchent
            openings = [o for o in openings
                        if not (o['type'] == 'window' and o['wall'] == 'front'
                                and o['z'] > floor_height_actual * 0.9
                                and abs((o['x'] + o['width'] / 2) - width / 2)
                                < pf_w / 2 + o['width'] / 2 + 0.3)]
            openings.append({'x': pf_x, 'y': 0, 'z': pf_z, 'width': pf_w,
                             'height': 2.05, 'depth': wall_depth,
                             'wall': 'front', 'type': 'door'})

        # ✅ MULTI-VOLUMES: fenêtres masquées par l'aile supprimées +
        # ouverture de PASSAGE dans le mur mitoyen
        for wing in getattr(self, '_wings', []):
            from . import volumes
            before = len(openings)
            openings = [o for o in openings
                        if o['type'] != 'window' or not volumes.opening_in_span(o, wing)]
            removed = before - len(openings)
            if removed:
                print(f"[House] Aile {wing['side']}: {removed} fenêtre(s) masquée(s) supprimée(s)")
            openings.append(volumes.passage_opening(
                wing, props, wall_depth, self._plinth_visible(props)))

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
                # ✅ FIX: Hauteur RÉELLE (briques) — les dalles d'étage
                # divergeaient des fenêtres jusqu'à 7.6cm par étage
                fh = (self.real_wall_height / props.num_floors) \
                    if getattr(self, 'real_wall_height', None) else props.floor_height
                z_pos = floor_num * fh + floor_thickness / 2

            location = Vector((width/2, length/2, z_pos))
            dimensions = Vector((inset_width, inset_length, floor_thickness))

            floor_name = "Floor_Ground" if floor_num == 0 else f"Floor_{floor_num}"

            # ✅ v1.5: TRÉMIE d'escalier découpée dans les dalles d'étage
            tremie = None
            if floor_num >= 1 and getattr(props, 'include_interiors', True):
                style_config = self._apply_architectural_style(props)
                il = self._get_interior_layout(props, style_config)
                tremie = il.get('tremie')
            if tremie is not None:
                bm = bmesh.new()
                x0, y0 = width/2 - inset_width/2, length/2 - inset_length/2
                x1, y1 = width/2 + inset_width/2, length/2 + inset_length/2
                z0, z1 = z_pos - floor_thickness/2, z_pos + floor_thickness/2
                hx0, hy0, hx1, hy1 = tremie
                hx0, hx1 = max(x0, hx0), min(x1, hx1)
                hy0, hy1 = max(y0, hy0), min(y1, hy1)
                if hx0 > x0 and hx1 < x1 and hy0 > y0 and hy1 < y1:
                    # ✅ S7: dalle trouée = ANNEAU manifold — l'assemblage
                    # de 4 boîtes fusionnées créait des arêtes en T
                    # (>2 faces). Surfaces identiques, joints internes
                    # disparus.
                    def _ring(z):
                        o = [bm.verts.new(v) for v in
                             ((x0, y0, z), (x1, y0, z),
                              (x1, y1, z), (x0, y1, z))]
                        i = [bm.verts.new(v) for v in
                             ((hx0, hy0, z), (hx1, hy0, z),
                              (hx1, hy1, z), (hx0, hy1, z))]
                        return o, i
                    ob_, ib_ = _ring(z0)
                    ot_, it_ = _ring(z1)
                    for k in range(4):
                        k2 = (k + 1) % 4
                        bm.faces.new([ot_[k], ot_[k2], it_[k2], it_[k]])
                        bm.faces.new([ib_[k], ib_[k2], ob_[k2], ob_[k]])
                        bm.faces.new([ob_[k], ob_[k2], ot_[k2], ot_[k]])
                        bm.faces.new([it_[k], it_[k2], ib_[k2], ib_[k]])
                else:
                    # trémie tangente au bord (cas limite): boîtes
                    # séparées, coques closes indépendantes
                    boxes = []
                    if hx0 > x0: boxes.append((x0, y0, hx0, y1))
                    if hx1 < x1: boxes.append((hx1, y0, x1, y1))
                    if hy0 > y0: boxes.append((hx0, y0, hx1, hy0))
                    if hy1 < y1: boxes.append((hx0, hy1, hx1, y1))
                    from .features import _add_box as _fbox
                    for (bx0, by0, bx1, by1) in boxes:
                        _fbox(bm, bx0, by0, z0, bx1, by1, z1)
                floor, mesh = self._create_mesh_from_bmesh(floor_name, bm)
                bm.free()
            else:
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

        # ✅ FIX: Les murs briques construisent leurs propres pignons
        # maçonnés — le toit ne doit alors PAS fermer les pignons (ses
        # triangles pleins masquaient entièrement la maçonnerie)
        closed_gable = props.wall_construction_type != 'BRICK_3D'

        if roof_type == 'FLAT':
            roof = self._create_flat_roof(width, length, total_height, roof_overhang, collection)
        elif roof_type == 'GABLE':
            roof = self._create_gable_roof(width, length, total_height, roof_pitch, roof_overhang, collection,
                                           closed_gable=closed_gable)
        elif roof_type == 'HIP':
            roof = self._create_hip_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'SHED':
            roof = self._create_shed_roof(width, length, total_height, roof_pitch, roof_overhang, collection)
        elif roof_type == 'GAMBREL':
            # ✅ NOUVEAU: Vrai toit mansarde/gambrel avec 2 pentes
            roof = self._create_gambrel_roof(width, length, total_height, roof_pitch, roof_overhang, collection,
                                             closed_gable=closed_gable)
        else:
            # Fallback pour types inconnus
            # ✅ FIX: Clamper avec 'GABLE' (le type inconnu passait la plage
            # par défaut 5-60° au lieu de la plage GABLE)
            print(f"[House] ERREUR: Type de toit inconnu '{roof_type}', utilisation toit pignon par défaut")
            roof = self._create_gable_roof(width, length, total_height,
                                           self._effective_pitch('GABLE', props.roof_pitch),
                                           roof_overhang, collection)

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

            # ✅ FIX: Acrotère en ANNEAU FERMÉ — les 4 boîtes indépendantes
            # étaient soudées par remove_doubles en arêtes non-manifold
            # (normales aléatoires, faces intérieures fantômes)
            # Garde-fou: épaisseur limitée pour les toits très étroits
            pt = min(parapet_thick, (x1 - x0) / 3, (y1 - y0) / 3)
            z_top = z_slab_top + parapet_height

            outer = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            inner = [(x0 + pt, y0 + pt), (x1 - pt, y0 + pt),
                     (x1 - pt, y1 - pt), (x0 + pt, y1 - pt)]
            ob = [bm.verts.new((x, y, z_slab_top)) for x, y in outer]
            ot = [bm.verts.new((x, y, z_top)) for x, y in outer]
            ib = [bm.verts.new((x, y, z_slab_top)) for x, y in inner]
            it = [bm.verts.new((x, y, z_top)) for x, y in inner]
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([ob[i], ob[j], ot[j], ot[i]])   # peau extérieure
                bm.faces.new([ib[j], ib[i], it[i], it[j]])   # peau intérieure
                bm.faces.new([ot[i], ot[j], it[j], it[i]])   # couvertine (dessus)

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

    @staticmethod
    def _plinth_visible(props):
        """✅ S3: délègue au MODÈLE DE NIVEAUX (levels.py) — la formule
        canonique vit là-bas, avec toutes les autres altitudes."""
        from . import levels
        return levels.plinth_visible(props)

    @staticmethod
    def slab_vertical_drop(pitch_deg, thickness=ROOF_THICKNESS_PITCHED):
        """✅ FIX: Chute VERTICALE d'une dalle de toit épaissie par solidify.

        solidify décale le long de la NORMALE → une dalle inclinée à θ
        descend de thickness/cos(θ) verticalement. Tous les dégagements
        (plafond des murs, briques) doivent utiliser cette valeur, pas
        l'épaisseur brute — sinon les murs percent la dalle dès 32°.
        """
        return thickness / max(0.2, math.cos(math.radians(pitch_deg)))

    def _create_gable_roof(self, width, length, height, pitch, overhang, collection,
                           closed_gable=True):
        """Toit à 2 pans

        ✅ NORMES: Le faîtage court le long de la PLUS GRANDE dimension.
        ✅ FIX: Le plan du toit passe par la FAÇADE à z=h (les égouts
        descendent de o·tan(pente)) — avant, le plan pivotait au bord du
        débord: la pente réelle était plus faible que demandé et un jour
        d'air s'ouvrait entre le mur et le toit.
        ✅ FIX: closed_gable=False (murs briques) n'ajoute PAS les
        triangles de pignon — ils masquaient les pignons maçonnés.
        """
        pitch_rad = math.radians(pitch)
        roof_thickness = ROOF_THICKNESS_PITCHED

        o_eave = overhang                    # Débord d'égout (bas de pente)
        o_rake = self._rake_overhang(overhang)  # Débord de rive (pignons)

        # ✅ FIX: Les égouts descendent sous h pour que le plan passe par
        # la façade à z=h exactement
        z_eave = height - o_eave * math.tan(pitch_rad)

        ridge_along_y = length >= width  # Faîtage parallèle au grand côté

        bm = bmesh.new()

        try:
            h = height

            if ridge_along_y:
                # Faîtage le long de Y — pentes descendant vers ±X,
                # pignons sur les façades avant/arrière (rives en Y)
                rh = (width / 2) * math.tan(pitch_rad)

                v1 = bm.verts.new((-o_eave, -o_rake, z_eave))
                v2 = bm.verts.new((width + o_eave, -o_rake, z_eave))
                v3 = bm.verts.new((width + o_eave, length + o_rake, z_eave))
                v4 = bm.verts.new((-o_eave, length + o_rake, z_eave))

                v5 = bm.verts.new((width/2, -o_rake, h + rh))
                v6 = bm.verts.new((width/2, length + o_rake, h + rh))

                slopes = [
                    bm.faces.new([v2, v3, v6, v5]),      # Pan droit (X+)
                    bm.faces.new([v4, v1, v5, v6]),      # Pan gauche (X-)
                ]
                if closed_gable:
                    bm.faces.new([v1, v2, v5])           # Pignon avant (Y-)
                    bm.faces.new([v3, v4, v6])           # Pignon arrière (Y+)
            else:
                # Faîtage le long de X — pentes descendant vers ±Y,
                # pignons sur les murs gauche/droit (rives en X)
                rh = (length / 2) * math.tan(pitch_rad)

                v1 = bm.verts.new((-o_rake, -o_eave, z_eave))
                v2 = bm.verts.new((width + o_rake, -o_eave, z_eave))
                v3 = bm.verts.new((width + o_rake, length + o_eave, z_eave))
                v4 = bm.verts.new((-o_rake, length + o_eave, z_eave))

                v5 = bm.verts.new((-o_rake, length/2, h + rh))
                v6 = bm.verts.new((width + o_rake, length/2, h + rh))

                slopes = [
                    bm.faces.new([v1, v2, v6, v5]),      # Pan avant (Y-)
                    bm.faces.new([v3, v4, v5, v6]),      # Pan arrière (Y+)
                ]
                if closed_gable:
                    bm.faces.new([v2, v3, v6])           # Pignon droit (X+)
                    bm.faces.new([v4, v1, v5])           # Pignon gauche (X-)

            print(f"[House] Toit GABLE: faîtage {'Y' if ridge_along_y else 'X'} "
                  f"(grand côté), hauteur {rh:.2f}m, rives {o_rake:.2f}m / égouts {o_eave:.2f}m, "
                  f"pignons {'fermés' if closed_gable else 'maçonnés (briques)'}")

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
            # ✅ FIX: Les égouts descendent sous h pour que les plans passent
            # par les façades à z=h (comme GABLE/SHED) — sinon la pente
            # effective était plus faible et un jour s'ouvrait sous le toit
            z_eave = h - o * math.tan(pitch_rad)

            v1 = bm.verts.new((-o, -o, z_eave))
            v2 = bm.verts.new((width + o, -o, z_eave))
            v3 = bm.verts.new((width + o, length + o, z_eave))
            v4 = bm.verts.new((-o, length + o, z_eave))

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
            # ✅ FIX: Winding vers l'EXTÉRIEUR (avant: normales vers
            # l'intérieur, rattrapées uniquement par recalc_face_normals)
            bm.faces.new([v1_bot, v2_bot, v2_top, v1_top])  # Face avant (Y-)
            bm.faces.new([v2_bot, v3_bot, v3_top, v2_top])  # Face droite (X+)
            bm.faces.new([v3_bot, v4_bot, v4_top, v3_top])  # Face arrière (Y+)
            bm.faces.new([v4_bot, v1_bot, v1_top, v4_top])  # Face gauche (X-)

            roof, mesh = self._create_mesh_from_bmesh("ShedRoof", bm)

        finally:
            bm.free()

        return roof

    def _create_gambrel_roof(self, width, length, height, pitch, overhang, collection,
                             closed_gable=True):
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

            # ✅ FIX CRITIQUE: Les cassures sont PROCHES DES FAÇADES
            # (à break_distance du mur), pas proches du faîtage! L'ancienne
            # formule width/2 ∓ break_distance inversait brisis et terrasson:
            # le "brisis 68°" ne faisait en réalité que ~39°.
            break_x_left = break_distance
            break_x_right = width - break_distance

            # ✅ FIX: Le plan du brisis passe par la façade à z=h —
            # l'égout (au bout du débord) descend de o·tan(68°)
            z_eave = h - o * math.tan(brisis_rad)

            y0, y1 = -o_rake, length + o_rake

            # ✅ FIX: Construction en DALLES À ÉPAISSEUR VERTICALE (comme le
            # toit SHED) au lieu de solidify: avec un brisis à 68°, solidify
            # donnait une chute verticale de 0.40m (0.15/cos68°) qui rendait
            # tous les dégagements faux, plus des auto-intersections au
            # niveau de la cassure.

            # Profil du toit (x, z) — surface supérieure
            profile = [
                (-o, z_eave),                      # égout gauche
                (break_x_left, h + break_height),  # cassure gauche
                (width / 2, h + rh),               # faîtage
                (break_x_right, h + break_height), # cassure droite
                (width + o, z_eave),               # égout droit
            ]

            top_f = [bm.verts.new((x, y0, z)) for x, z in profile]
            top_b = [bm.verts.new((x, y1, z)) for x, z in profile]
            bot_f = [bm.verts.new((x, y0, z - t)) for x, z in profile]
            bot_b = [bm.verts.new((x, y1, z - t)) for x, z in profile]

            n = len(profile)
            for i in range(n - 1):
                # Surface supérieure (normale vers le haut)
                bm.faces.new([top_f[i], top_f[i + 1], top_b[i + 1], top_b[i]])
                # Surface inférieure (normale vers le bas)
                bm.faces.new([bot_b[i], bot_b[i + 1], bot_f[i + 1], bot_f[i]])

            # Bandes d'épaisseur aux pignons (avant/arrière) — le "W"
            bm.faces.new(list(reversed(top_f)) + bot_f)   # pignon avant (Y-)
            bm.faces.new(top_b + list(reversed(bot_b)))   # pignon arrière (Y+)

            # Chants d'égout (extrémités gauche/droite)
            bm.faces.new([top_f[0], top_b[0], bot_b[0], bot_f[0]])
            bm.faces.new([top_b[-1], top_f[-1], bot_f[-1], bot_b[-1]])

            # ✅ v1.5: PIGNONS FERMÉS (murs simples) — remplissage sous le
            # profil en W du mur (les briques maçonnent ce pignon en mode
            # BRICK_3D, closed_gable est alors False)
            if closed_gable:
                for yy, flip in ((0.0, False), (length, True)):
                    ring = [bm.verts.new((x, yy, z - t)) for x, z in profile]
                    b0 = bm.verts.new((0.0, yy, h - 0.05))
                    b1 = bm.verts.new((width, yy, h - 0.05))
                    poly = [b0] + ring + [b1]
                    face = bm.faces.new(poly if flip else list(reversed(poly)))

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

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
            # ✅ S4: on consomme LA SPEC UNIFIÉE (openings.py) — les
            # boucles parallèles à garder synchrones avec les briques
            # sont mortes. Bonus de l'unification: la porte-fenêtre du
            # balcon est enfin DÉCOUPÉE aussi dans les murs simples.
            from . import openings as openings_mod
            for o in openings_mod.compute(self, props):
                extra = WINDOW_DEPTH_EXTRA if o['type'] == 'window' \
                    else DOOR_DEPTH_EXTRA
                d = wall_thickness + extra
                cz = o['z'] + o['height'] / 2
                if o['wall'] in ('front', 'back'):
                    cy = wall_thickness / 2 if o['wall'] == 'front' \
                        else length - wall_thickness / 2
                    self._add_window_to_combined_mesh(
                        combined_bm, o['x'] + o['width'] / 2, cy, cz,
                        o['width'], d, o['height'])
                else:
                    cx = wall_thickness / 2 if o['wall'] == 'left' \
                        else width - wall_thickness / 2
                    self._add_window_to_combined_mesh(
                        combined_bm, cx, o['y'] + o['width'] / 2, cz,
                        d, o['width'], o['height'])

            combined_cutter, combined_mesh = self._create_mesh_from_bmesh("Openings_Cutter", combined_bm)
            collection.objects.link(combined_cutter)
            combined_cutter["house_part"] = "opening"
            # ✅ FIX: Cutter complètement masqué (le wireframe restait
            # visible en permanence dans le viewport)
            combined_cutter.display_type = 'WIRE'
            combined_cutter.hide_render = True
            combined_cutter.hide_viewport = True

            for wall in walls:
                if wall.get("no_boolean"):
                    continue  # murs d'aile: ouvertures déjà maçonnées
                mod = wall.modifiers.new(name="Boolean_Openings", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = combined_cutter
                # ✅ FIX: EXACT — FAST est peu robuste sur les cutters
                # tangents/coplanaires (faces manquantes aléatoires)
                mod.solver = 'EXACT'

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

        # ✅ NOUVEAU: Collecte des specs pour les volets (mêmes valeurs
        # que les fenêtres visuelles — cohérence garantie)
        shutter_specs = []

        # ✅ S4: on consomme LA SPEC UNIFIÉE — mêmes ouvertures que les
        # trous (briques ET Booleans): les skips porte/aile/balcon sont
        # DANS la spec, plus dupliqués ici. En mode PROGRAMME, chaque
        # pièce arrière reçoit SA fenêtre (centre de cellule).
        from . import openings as openings_mod
        for o in openings_mod.windows_of(openings_mod.compute(self, props)):
            wall = o['wall']
            z_center = o['z'] + o['height'] / 2
            if wall == 'front':
                loc = Vector((o['along'], wall_depth / 2, z_center))
                sx, sy = o['along'], 0
            elif wall == 'back':
                loc = Vector((o['along'], length - wall_depth / 2, z_center))
                sx, sy = o['along'], length
            elif wall == 'left':
                loc = Vector((wall_depth / 2, o['along'], z_center))
                sx, sy = 0, o['along']
            else:
                loc = Vector((width - wall_depth / 2, o['along'], z_center))
                sx, sy = width, o['along']
            window_gen.generate_window(
                window_type=props.window_type,
                width=o['width'], height=o['height'],
                location=loc, orientation=wall, collection=collection)
            shutter_specs.append({'x': sx, 'y': sy, 'z_center': z_center,
                                  'width': o['width'],
                                  'height': o['height'], 'wall': wall})

        # ✅ MULTI-VOLUMES: fenêtres de l'aile (mêmes réglages, repère
        # transformé) + leurs volets
        for wing in getattr(self, '_wings', []):
            if wing.get('specs'):
                from . import volumes
                shutter_specs += volumes.generate_wing_windows(
                    wing, props, collection, wing['specs'],
                    window_gen, wall_depth)

        # ✅ NOUVEAU: Volets battants (option)
        if getattr(props, 'include_shutters', False) and shutter_specs:
            from . import features
            features.build_shutters(props, collection, shutter_specs)

    def _generate_door_visual(self, context, props, collection):
        """Génère la porte d'entrée visuelle (objet 3D)"""
        from .doors import DOOR_FRAME_DEPTH

        width = props.house_width

        # ✅ FIX: Profondeur de mur partagée avec les ouvertures
        wall_depth = self._get_wall_depth(props)

        door_width = props.front_door_width
        door_height = DOOR_HEIGHT
        door_x = self._door_center_x(props)  # centre (déplacé si aile devant)

        print(f"[House] Génération porte visuelle {props.door_type}: {door_width}x{door_height}m")

        door_gen = DoorGenerator(quality=props.door_quality)

        # ✅ FIX: Le cadre de porte s'étend de y=0 à y=DOOR_FRAME_DEPTH dans
        # son repère local — on le CENTRE dans l'épaisseur du mur (avant, il
        # était enfoncé d'une demi-épaisseur vers l'intérieur de la maison)
        door_gen.generate_door(
            door_type=props.door_type,
            width=door_width,
            height=door_height,
            # ✅ FIX: La porte POSE sur le seuil/socle (z = hauteur visible du
            # soubassement) — avant, son bas restait enterré derrière le socle
            location=Vector((door_x - door_width/2, (wall_depth - DOOR_FRAME_DEPTH) / 2,
                             self._plinth_visible(props))),
            orientation='front',
            collection=collection
        )

    def _get_interior_layout(self, props, style_config):
        """✅ v1.5: distribution intérieure PARTAGÉE (cloisons, escalier,
        trémie) — utilisée par les dalles ET les intérieurs."""
        if getattr(self, '_interior_layout', None) is not None:
            return self._interior_layout
        from . import interiors
        wl = self._get_window_layout(props, style_config)
        if getattr(self, 'real_wall_height', None):
            fha = self.real_wall_height / props.num_floors
        else:
            fha = props.floor_height
        W, L = props.house_width, props.house_length
        nb, ns = wl['num_back'], wl['num_side']
        self._interior_layout = interiors.interior_layout(
            props, self._get_wall_depth(props), fha,
            self._door_center_x(props),
            [W / (nb + 1) * (i + 1) for i in range(nb)],
            [L / (ns + 1) * (i + 1) for i in range(ns)])
        return self._interior_layout

    def _generate_interiors(self, context, props, collection, style_config):
        """✅ INTÉRIEURS: plafonds, cloisons, sols, escalier, portes."""
        from . import interiors
        layout = self._get_window_layout(props, style_config)
        if getattr(self, 'real_wall_height', None):
            fha = self.real_wall_height / props.num_floors
        else:
            fha = props.floor_height
        W, L = props.house_width, props.house_length
        nf, nb, ns = layout['num_front'], layout['num_back'], layout['num_side']
        # Plafond du dernier étage: sous le chaperon des murs d'égout
        wall_h = getattr(self, 'real_wall_height', None) or (props.num_floors * props.floor_height)
        eff = self._effective_pitch(props.roof_type, props.roof_pitch)
        if props.roof_type in ('GABLE', 'HIP'):
            cap = self.slab_vertical_drop(eff) + 0.07
        elif props.roof_type in ('GAMBREL', 'SHED'):
            cap = ROOF_THICKNESS_PITCHED + 0.07
        else:
            cap = 0.02
        interiors.build_interiors(
            props, collection, self._get_wall_depth(props), fha,
            self._door_center_x(props),
            [W / (nf + 1) * (i + 1) for i in range(nf)],
            [W / (nb + 1) * (i + 1) for i in range(nb)],
            [L / (ns + 1) * (i + 1) for i in range(ns)],
            wing_frames=getattr(self, '_wings', []),
            top_ceiling_z=wall_h - cap,
            slab_top=self.levels.slab_top(0) if getattr(self, 'levels', None)
            else FLOOR_THICKNESS,
            layout=self._get_interior_layout(props, style_config),
            ceiling_profile=self._cathedral_profile(props, wall_h))

        # ✅ v1.5: escalier (si ≥ 2 étages) + portes intérieures
        il = self._get_interior_layout(props, style_config)
        interiors.build_staircase(props, collection, il, fha,
                                  FLOOR_THICKNESS, props.architectural_style)
        interiors.build_interior_doors(props, collection, il, fha,
                                       FLOOR_THICKNESS)

        # ✅ v1.5: doublage intérieur peint (réservations aux ouvertures)
        interiors.build_wall_liners(
            props, collection, self._get_wall_depth(props),
            self._calculate_openings_for_brick_walls(props),
            fha, wall_h - cap, FLOOR_THICKNESS,
            wing_frames=getattr(self, '_wings', []))

    def _cathedral_profile(self, props, wall_h):
        """✅ v1.7: profil (x, z_sous-face) du toit pour le plafond
        CATHÉDRALE du dernier étage (monopente et mansarde uniquement —
        le GABLE garde ses combles perdus plafonnés plat)."""
        W = props.house_width
        eff = self._effective_pitch(props.roof_type, props.roof_pitch)
        if props.roof_type == 'SHED':
            slope = math.tan(math.radians(eff))
            rt = ROOF_THICKNESS_PITCHED
            return [(0.0, wall_h - rt), (W, wall_h + slope * W - rt)]
        if props.roof_type == 'GAMBREL':
            brisis = math.tan(math.radians(68.0))
            bd = (W / 2) * 0.25
            bh = bd * brisis
            rh = bh + (W / 2 - bd) * math.tan(math.radians(eff))
            rt = ROOF_THICKNESS_PITCHED
            return [(0.0, wall_h - rt), (bd, wall_h + bh - rt),
                    (W / 2, wall_h + rh - rt), (W - bd, wall_h + bh - rt),
                    (W, wall_h - rt)]
        return None

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

        # Partie VISIBLE au-dessus du sol (soubassement) — helper partagé
        visible = self._plinth_visible(props)

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
            # ✅ FIX: La marche s'ARRÊTE contre la face du socle (avant elle
            # traversait le socle jusque DANS le mur, avec sa face supérieure
            # coplanaire au socle → z-fighting garanti)
            door_width = props.front_door_width
            step_width = door_width + 0.4              # 20cm de chaque côté
            y_far = -(0.6 + foundation_overhang)        # Bord extérieur de la marche
            y_near = -foundation_overhang + 0.001       # Contre la face du socle
            x0 = width/2 - step_width/2
            x1 = width/2 + step_width/2

            step_verts_b = [bm.verts.new(c) for c in (
                (x0, y_far, 0), (x1, y_far, 0),
                (x1, y_near, 0), (x0, y_near, 0))]
            step_verts_t = [bm.verts.new(c) for c in (
                (x0, y_far, visible), (x1, y_far, visible),
                (x1, y_near, visible), (x0, y_near, visible))]
            bm.faces.new(step_verts_b[::-1])
            bm.faces.new(step_verts_t)
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([step_verts_b[i], step_verts_b[j], step_verts_t[j], step_verts_t[i]])

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            foundation_mesh = bpy.data.meshes.new("Foundation_Mesh")
            bm.to_mesh(foundation_mesh)
            foundation_mesh.update()
            from .features import box_uv
            box_uv(foundation_mesh)   # ✅ S7: UVs systématiques

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
    # ✅ FONCTIONNALITÉS EXTÉRIEURES (module features.py)
    # ============================================================

    def _roof_metrics(self, props):
        """Métriques du toit partagées par cheminée/gouttières/tuiles:
        (hauteur murs, pente effective, altitude faîtage, égouts g/d, débords)"""
        h = getattr(self, 'real_wall_height', None) or (props.num_floors * props.floor_height)
        pitch = self._effective_pitch(props.roof_type, props.roof_pitch)
        pitch_rad = math.radians(pitch)
        o_eave = props.roof_overhang
        o_rake = self._rake_overhang(props.roof_overhang)
        width, length = props.house_width, props.house_length

        if props.roof_type == 'GABLE':
            half = width / 2 if length >= width else length / 2
            peak = h + half * math.tan(pitch_rad)
            eave = h - o_eave * math.tan(pitch_rad)
            eave_l = eave_r = eave
        elif props.roof_type == 'HIP':
            half = min(width, length) / 2
            peak = h + half * math.tan(pitch_rad)
            eave_l = eave_r = h - o_eave * math.tan(pitch_rad)
        elif props.roof_type == 'SHED':
            slope = math.tan(pitch_rad)
            peak = h + width * slope
            eave_l = h - o_eave * slope           # côté bas (x=0)
            eave_r = h + (width + o_eave) * slope  # côté haut
        elif props.roof_type == 'GAMBREL':
            brisis = math.radians(68.0)
            bd = (width / 2) * 0.25
            peak = h + bd * math.tan(brisis) + (width / 2 - bd) * math.tan(pitch_rad)
            eave_l = eave_r = h - o_eave * math.tan(brisis)
        else:  # FLAT
            peak = h + ROOF_THICKNESS_FLAT + 0.45
            eave_l = eave_r = h
        return h, pitch, peak, eave_l, eave_r, o_eave, o_rake

    def _generate_garage(self, context, props, collection):
        """✅ Garage attenant + porte sectionnelle"""
        from . import features
        features.build_garage(props, collection, self._plinth_visible(props))

    def _generate_terrace(self, context, props, collection):
        """✅ Terrasse en lames de bois à l'arrière"""
        from . import features
        features.build_terrace(props, collection, self._plinth_visible(props))

    def _generate_balcony(self, context, props, collection):
        """✅ Balcon au 1er étage + PORTE-FENÊTRE française articulée"""
        from . import features
        if getattr(self, 'real_wall_height', None):
            fh = self.real_wall_height / props.num_floors
        else:
            fh = props.floor_height
        features.build_balcony(props, collection, fh)
        # ✅ v1.7: porte-fenêtre FRENCH dans l'ouverture du balcon
        try:
            from .doors import DoorGenerator, DOOR_FRAME_DEPTH
            wall_depth = self._get_wall_depth(props)
            pf_w = min(1.5, max(1.1, getattr(props, 'balcony_width', 2.6) - 0.6))
            gen = DoorGenerator(quality=props.door_quality)
            gen.generate_door(
                door_type='FRENCH', width=pf_w, height=2.05,
                location=Vector((props.house_width / 2 - pf_w / 2,
                                 (wall_depth - DOOR_FRAME_DEPTH) / 2,
                                 fh + 0.02)),
                orientation='front', collection=collection)
            print("[House] ✓ Porte-fenêtre posée derrière le balcon")
        except Exception as e:
            print(f"[House] Porte-fenêtre du balcon échouée: {e}")

    def _generate_chimney(self, context, props, collection):
        """✅ Cheminée en brique traversant le toit"""
        from . import features
        h, _pitch, peak, *_ = self._roof_metrics(props)
        features.build_chimney(props, collection, h, peak)

    def _eave_exclusions(self):
        """✅ v1.7: intervalles d'égout couverts par les ailes en noue
        (les gouttières/chevrons/fascias y sont interrompus)."""
        ex = {}
        for wing in getattr(self, '_wings', []):
            if not wing.get('valley'):
                continue
            a0, a1 = wing['span']
            ex.setdefault(wing['attached_wall'], []).append((a0 - 0.05, a1 + 0.05))
        return ex

    def _generate_gutters(self, context, props, collection):
        """✅ Gouttières le long des égouts + descentes"""
        from . import features
        _h, _pitch, _peak, eave_l, eave_r, o_eave, o_rake = self._roof_metrics(props)
        features.build_gutters(props, collection, eave_l, eave_r, o_eave, o_rake,
                               eave_exclusions=self._eave_exclusions())

    def _generate_roof_details(self, context, props, collection):
        """✅ Charpente apparente + rives (la 'façon de faire les toits' V2)"""
        from . import features
        h, pitch, _peak, _el, _er, o_eave, o_rake = self._roof_metrics(props)
        features.build_roof_carpentry(props, collection, h, pitch, o_eave, o_rake,
                                      tile_color=tuple(props.tile_color)[:3],
                                      eave_exclusions=self._eave_exclusions())
        # ✅ v1.5: fenêtres de toit (velux) — tuiles exclues par calepinage partagé
        if getattr(props, 'include_roof_windows', False):
            features.build_roof_windows(props, collection, h, pitch, o_eave, o_rake)

    def _generate_roof_tiles(self, context, props, collection):
        """✅ Couverture en tuiles instanciées (GN) — GABLE/SHED"""
        from . import features
        h, pitch, _peak, _el, _er, o_eave, o_rake = self._roof_metrics(props)
        features.build_roof_tiles(props, collection, h, pitch, o_eave, o_rake)

    def _add_scene_lighting(self, context, props):
        """✅ Éclairage automatique: soleil + remplissage + ciel"""
        from . import features
        features.add_scene_lighting(props, collection=self._light_collection(context))

    def _light_collection(self, context):
        """Les lumières vont dans la collection House si elle existe"""
        return bpy.data.collections.get("House") or context.scene.collection

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
                    # ✅ v1.9.1: ENDUIT TALOCHÉ réel au lieu de l'aplat
                    # lisse; ✅ v1.15: finition au CHOIX (wall_finish)
                    try:
                        from . import look
                        obj.data.materials.append(
                            look.wall_material(
                                tuple(wall_color)[:3],
                                getattr(props, 'wall_finish', 'AUTO')))
                    except Exception:
                        obj.data.materials.append(wall_mat)
            elif part_type == "roof":
                # ✅ FIX MAJEUR: ne PAS écraser les matériaux déjà posés —
                # ce clear() repeignait chevrons (bois), planches de rive
                # (blanc), faîtières/rives (terre cuite) et bandes de noue
                # (zinc) en brun uni à CHAQUE génération
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(roof_mat)
            elif part_type == "floor":
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(floor_mat)
            elif part_type == "glass":
                if len(obj.data.materials) == 0:
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


class HOUSE_OT_mark_assets(bpy.types.Operator):
    """✅ ASSETS: marque les menuiseries générées comme ASSETS Blender
    (Asset Browser) — portes, fenêtres, volets, porte de garage et tuile
    maître deviennent réutilisables par glisser-déposer dans toute scène.
    """
    bl_idname = "house.mark_assets"
    bl_label = "Menuiseries → Asset Browser"
    bl_description = ("Marque portes, fenêtres, volets et tuile maître "
                      "comme assets réutilisables (Asset Browser). "
                      "Enregistrez ensuite le .blend dans une bibliothèque "
                      "d'assets (Préférences > Chemins de fichiers)")
    bl_options = {'REGISTER', 'UNDO'}

    ASSET_PARTS = {"door", "window", "shutter"}
    ASSET_PREFIXES = ("Garage_Door", "Tile_Master", "Brick_Master")

    def execute(self, context):
        tagged = 0
        for obj in bpy.data.objects:
            part = obj.get("house_part")
            eligible = part in self.ASSET_PARTS or \
                obj.name.startswith(self.ASSET_PREFIXES)
            if not eligible or obj.type != 'MESH':
                continue
            try:
                obj.asset_mark()
                if obj.asset_data:
                    obj.asset_data.author = "House Generator"
                    obj.asset_data.description = \
                        f"Menuiserie générée par House ({part or 'master'})"
                    existing = {t.name for t in obj.asset_data.tags}
                    for tag in (part or "master", "house"):
                        if tag not in existing:
                            obj.asset_data.tags.new(tag)
                # ✅ Les aperçus nécessitent l'interface (crash en headless)
                if not bpy.app.background:
                    obj.asset_generate_preview()
                tagged += 1
            except Exception as e:
                print(f"[House] Asset '{obj.name}' ignoré: {e}")

        if tagged:
            self.report({'INFO'},
                        f"{tagged} objet(s) marqués comme assets — "
                        f"enregistrez le .blend dans votre bibliothèque")
        else:
            self.report({'WARNING'}, "Aucune menuiserie à marquer "
                                     "(générez d'abord une maison)")
        return {'FINISHED'}


class HOUSE_OT_export_assets(bpy.types.Operator):
    """✅ v1.5: exporte les menuiseries marquées dans un .blend de
    BIBLIOTHÈQUE D'ASSETS prêt à distribuer/brancher dans les
    Préférences > Chemins de fichiers > Asset Libraries."""
    bl_idname = "house.export_asset_library"
    bl_label = "Exporter la bibliothèque d'assets (.blend)"
    bl_description = ("Marque les menuiseries comme assets puis les écrit "
                      "dans un fichier .blend de bibliothèque réutilisable")

    filepath: bpy.props.StringProperty(subtype='FILE_PATH',
                                       default="house_assets.blend")
    filter_glob: bpy.props.StringProperty(default="*.blend", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "house_assets.blend"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        bpy.ops.house.mark_assets()
        ids = {o for o in bpy.data.objects if o.asset_data}
        # inclure les matériaux/mesh liés (écrits automatiquement comme
        # dépendances par libraries.write)
        if not ids:
            self.report({'WARNING'}, "Aucun asset à exporter — générez "
                                     "d'abord une maison")
            return {'CANCELLED'}
        fp = self.filepath
        if not fp.lower().endswith('.blend'):
            fp += '.blend'
        try:
            bpy.data.libraries.write(fp, ids, fake_user=True)
        except Exception as e:
            self.report({'ERROR'}, f"Écriture échouée: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{len(ids)} asset(s) exportés → {fp}")
        print(f"[House] ✓ Bibliothèque d'assets écrite: {fp} ({len(ids)} objets)")
        return {'FINISHED'}


HOUSE_PRESETS = {
    # ✅ v1.8: silhouettes régionales — jeux de réglages COMPLETS
    'LONGERE': dict(
        house_width=16.0, house_length=6.5, num_floors=1, floor_height=2.6,
        architectural_style='TRADITIONAL', roof_type='GABLE', roof_pitch=45.0,
        roof_overhang=0.35, roof_covering='TILES',
        wall_construction_type='BRICK_3D', brick_preset_type='BRICK_BROWN',
        include_roof_windows=True, roof_window_style='LUCARNE',
        num_roof_windows=3, include_gutters=True, include_chimney=True,
        include_shutters=True, window_type='CASEMENT', num_windows_front=4,
        num_windows_side=1, include_wing=False, include_garage=False,
    ),
    'CHALET': dict(
        house_width=9.0, house_length=11.0, num_floors=2, floor_height=2.5,
        architectural_style='TRADITIONAL', roof_type='GABLE', roof_pitch=28.0,
        roof_overhang=1.0, roof_covering='TILES',
        wall_construction_type='BRICK_3D', brick_preset_type='BRICK_BROWN',
        include_balcony=True, balcony_width=3.2, balcony_depth=1.4,
        include_gutters=True, include_chimney=True, include_shutters=True,
        window_type='CASEMENT', num_windows_front=2, num_windows_side=2,
        include_roof_windows=False, include_wing=False, include_garage=False,
    ),
    'BASTIDE': dict(
        house_width=14.0, house_length=10.0, num_floors=1, floor_height=3.0,
        architectural_style='MEDITERRANEAN', roof_type='HIP', roof_pitch=22.0,
        roof_overhang=0.5, roof_covering='TILES',
        wall_construction_type='SIMPLE',
        include_gutters=True, include_chimney=True, include_shutters=True,
        window_type='CASEMENT', num_windows_front=3, num_windows_side=2,
        include_terrace=True, include_roof_windows=False,
        include_wing=False, include_garage=False,
    ),
    'MEULIERE': dict(
        house_width=9.5, house_length=8.5, num_floors=2, floor_height=2.8,
        architectural_style='TRADITIONAL', roof_type='GAMBREL',
        roof_pitch=25.0, roof_overhang=0.4, roof_covering='TILES',
        wall_construction_type='BRICK_3D', brick_preset_type='BRICK_RED',
        include_gutters=True, include_chimney=True, include_shutters=True,
        include_balcony=False, window_type='CASEMENT', num_windows_front=2,
        num_windows_side=2, include_roof_windows=False,
        include_wing=False, include_garage=False,
    ),
}


class HOUSE_OT_apply_preset(bpy.types.Operator):
    """✅ v1.8: applique un PRESET RÉGIONAL (longère, chalet, bastide,
    meulière) puis regénère la maison."""
    bl_idname = "house.apply_preset"
    bl_label = "Appliquer le preset régional"
    bl_description = ("Applique la silhouette régionale choisie "
                      "(dimensions, toit, matériaux, options) et regénère")

    def execute(self, context):
        props = context.scene.house_generator
        preset = HOUSE_PRESETS.get(props.house_preset)
        if not preset:
            self.report({'WARNING'}, "Choisissez un preset dans la liste")
            return {'CANCELLED'}
        for k, v in preset.items():
            try:
                setattr(props, k, v)
            except Exception as e:
                print(f"[House] Preset: réglage '{k}' ignoré ({e})")
        bpy.ops.house.generate_auto()
        self.report({'INFO'}, f"Preset {props.house_preset} appliqué")
        return {'FINISHED'}


class HOUSE_OT_solve_programme(bpy.types.Operator):
    """✅ v1.14: MODE PROGRAMME — "3 chambres, SdB, garage" → House
    résout l'emprise, la distribution et les options, puis génère."""
    bl_idname = "house.solve_programme"
    bl_label = "Résoudre le programme"
    bl_description = ("Traduit le programme fonctionnel (chambres, salles "
                      "de bain, WC, garage) en maison complète: emprise, "
                      "distribution, fenêtres, options")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . import programme
        props = context.scene.house_generator
        try:
            sol = programme.solve(
                bedrooms=props.prog_bedrooms,
                bathrooms=props.prog_bathrooms,
                wc_separate=props.prog_wc_separate,
                garage=props.prog_garage,
                surface=props.prog_surface)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        for k, v in sol['props'].items():
            try:
                setattr(props, k, v)
            except Exception as e:
                print(f"[House][Programme] réglage '{k}' ignoré ({e})")
        props.programme_cells = ",".join(f"{c:.3f}" for c in sol['cells'])
        props.programme_active = True
        for line in sol['report']:
            print(f"[House][Programme] {line}")
        res = bpy.ops.house.generate_auto()
        if 'FINISHED' in res:
            self.report({'INFO'}, sol['summary'])
        return res


class HOUSE_OT_export_gltf(bpy.types.Operator):
    """✅ v1.7: exporte la maison en glTF (.glb) — format d'échange
    web/moteurs temps réel, hiérarchie et noms sémantiques conservés."""
    bl_idname = "house.export_gltf"
    bl_label = "Exporter la maison (.glb)"
    bl_description = "Exporte la scène générée en glTF binaire (.glb)"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', default="house.glb")
    filter_glob: bpy.props.StringProperty(default="*.glb", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "house.glb"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        fp = self.filepath
        if not fp.lower().endswith('.glb'):
            fp += '.glb'
        try:
            bpy.ops.export_scene.gltf(filepath=fp, export_format='GLB',
                                      export_apply=True)
        except Exception as e:
            self.report({'ERROR'}, f"Export glTF échoué: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Maison exportée → {fp}")
        return {'FINISHED'}


classes = (
    HOUSE_OT_generate_auto,
    HOUSE_OT_mark_assets,
    HOUSE_OT_export_assets,
    HOUSE_OT_export_gltf,
    HOUSE_OT_apply_preset,
    HOUSE_OT_solve_programme,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[House] Module operators_auto ULTIMATE chargé")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[House] Module operators_auto déchargé")