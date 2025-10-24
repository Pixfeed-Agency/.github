# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Windows Module ULTIMATE (BLENDER 4.2+)
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from mathutils import Vector, Matrix
import math

# Constantes - Normes européennes pour fenêtres réalistes
FRAME_DEPTH = 0.07          # 70mm - Profondeur du dormant (standard EN)
GLASS_THICKNESS = 0.02      # 20mm - Double vitrage simplifié
GLASS_INSET = 0.005         # 5mm - Retrait du verre (réduit)
SILL_DEPTH = 0.04           # 40mm - Débord de l'appui


class WindowGenerator:
    """Générateur de fenêtres architecturales réalistes et optimisées
    
    Version ULTIMATE avec :
    - Système de qualité LOW/MEDIUM/HIGH
    - Chanfreins automatiques pour réalisme
    - Matériaux procéduraux intégrés (PBR)
    """
    
    def __init__(self, quality='MEDIUM'):
        """Initialise le générateur avec un niveau de qualité
        
        Args:
            quality (str): 'LOW', 'MEDIUM', ou 'HIGH'
        """
        self.quality = quality
        self.frame_depth = FRAME_DEPTH
        self.glass_thickness = GLASS_THICKNESS
        
        # Paramètres adaptatifs selon la qualité
        if quality == 'LOW':
            self.arc_segments = 6
            self.frame_width = 0.06  # Plus épais = moins de polygones
            self.sash_width = 0.05
            self.mullion_width = 0.05
            self.bevel_amount = 0.0  # Pas de chanfrein
            self.bevel_segments = 0
        elif quality == 'MEDIUM':
            self.arc_segments = 12
            self.frame_width = 0.05
            self.sash_width = 0.045
            self.mullion_width = 0.04
            self.bevel_amount = 0.002  # 2mm chanfrein
            self.bevel_segments = 2
        else:  # HIGH
            self.arc_segments = 24
            self.frame_width = 0.04  # Plus fin = plus réaliste
            self.sash_width = 0.035
            self.mullion_width = 0.03
            self.bevel_amount = 0.003  # 3mm chanfrein
            self.bevel_segments = 3
        
        print(f"[Windows] Qualité: {quality} - Segments arc: {self.arc_segments}, Frame: {self.frame_width*1000}mm")
    
    def generate_window(self, window_type, width, height, location, orientation, collection):
        """Point d'entrée principal pour générer une fenêtre complète
        
        Args:
            window_type (str): Type de fenêtre (CASEMENT, SLIDING, FIXED)
            width (float): Largeur de l'ouverture
            height (float): Hauteur de l'ouverture
            location (Vector): Position dans l'espace
            orientation (str): Orientation du mur (front, back, left, right)
            collection: Collection Blender où ajouter les objets
            
        Returns:
            list: Liste des objets créés (cadre + verre)
        """
        
        # Validation
        if width <= 0 or height <= 0:
            print(f"[Windows] Dimensions invalides: {width}x{height}")
            return []
        
        try:
            # Créer la fenêtre selon le type
            if window_type == 'CASEMENT':
                window_obj = self._create_casement_window(width, height, location, orientation)
            elif window_type == 'SLIDING':
                window_obj = self._create_sliding_window(width, height, location, orientation)
            elif window_type == 'FIXED':
                window_obj = self._create_fixed_window(width, height, location, orientation)
            elif window_type == 'DOUBLE_HUNG':
                window_obj = self._create_double_hung_window(width, height, location, orientation)
            elif window_type == 'ARCHED':
                window_obj = self._create_arched_window(width, height, location, orientation)
            elif window_type == 'PICTURE':
                window_obj = self._create_picture_window(width, height, location, orientation)
            else:
                # Fallback : fenêtre fixe
                window_obj = self._create_fixed_window(width, height, location, orientation)
            
            if window_obj:
                window_obj.name = f"Window_{window_type}"
                collection.objects.link(window_obj)
                window_obj["house_part"] = "wall"
                
                # Appliquer matériau cadre
                self._apply_frame_material(window_obj)
                
                # Créer le verre séparé avec matériau glass
                glass_obj = self._create_glass_object(width, height, location, orientation, window_type)
                if glass_obj:
                    glass_obj.name = f"Window_Glass_{window_type}"
                    collection.objects.link(glass_obj)
                    glass_obj["house_part"] = "glass"
                    
                    # Appliquer matériau verre
                    self._apply_glass_material(glass_obj)
                    
                    return [window_obj, glass_obj]
                
                return [window_obj]
            
        except Exception as e:
            print(f"[Windows] ERREUR création fenêtre {window_type}: {e}")
            import traceback
            traceback.print_exc()
            # Créer fenêtre simple de secours
            return self._create_fallback_window(width, height, location, orientation, collection)
        
        return []
    
    # ============================================================
    # CASEMENT WINDOW (Fenêtre à battant) - Standard européen
    # ============================================================
    
    def _create_casement_window(self, width, height, location, orientation):
        """Fenêtre à battant - UN SEUL objet fusionné"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width
            sash_w = self.sash_width
            
            # === CADRE EXTÉRIEUR (Dormant) ===
            self._add_rectangular_frame(bm, width, height, frame_w, FRAME_DEPTH, offset_y=0)
            
            # === OUVRANT (Sash) ===
            sash_width = width - frame_w * 2 - 0.003
            sash_height = height - frame_w * 2 - 0.003
            sash_center = Vector((0, 0.01, 0))  # Légèrement en avant
            
            self._add_rectangular_frame(bm, sash_width, sash_height, sash_w, FRAME_DEPTH - 0.015, 
                                       offset=sash_center, offset_y=0.01)
            
            # === APPUI DE FENÊTRE ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH)
            
            # === CHANFREINS (si qualité >= MEDIUM) ===
            if self.quality in ['MEDIUM', 'HIGH']:
                self._apply_bevels(bm)
            
            # Appliquer orientation
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            
            # Translater à la position
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            # Créer l'objet
            obj = self._bmesh_to_object(bm, "WindowCasement")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # SLIDING WINDOW (Fenêtre coulissante)
    # ============================================================
    
    def _create_sliding_window(self, width, height, location, orientation):
        """Fenêtre coulissante - UN SEUL objet fusionné"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width
            
            # === CADRE PRINCIPAL ===
            self._add_rectangular_frame(bm, width, height, frame_w, FRAME_DEPTH, offset_y=0)
            
            # === RAIL CENTRAL VERTICAL ===
            rail_height = height - frame_w * 2
            self._add_vertical_mullion(bm, rail_height, self.mullion_width, FRAME_DEPTH - 0.01, 
                                      offset=Vector((0, 0.005, 0)))
            
            # === APPUI ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH)
            
            # === CHANFREINS ===
            if self.quality in ['MEDIUM', 'HIGH']:
                self._apply_bevels(bm)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowSliding")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # FIXED WINDOW (Fenêtre fixe)
    # ============================================================
    
    def _create_fixed_window(self, width, height, location, orientation):
        """Fenêtre fixe simple - UN SEUL objet fusionné"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width * 0.8  # Cadre plus fin pour fenêtre fixe
            
            # === CADRE SIMPLE ===
            self._add_rectangular_frame(bm, width, height, frame_w, FRAME_DEPTH, offset_y=0)
            
            # === APPUI ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH, thin=True)
            
            # === CHANFREINS ===
            if self.quality in ['MEDIUM', 'HIGH']:
                self._apply_bevels(bm)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowFixed")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # DOUBLE HUNG WINDOW (Fenêtre à guillotine)
    # ============================================================
    
    def _create_double_hung_window(self, width, height, location, orientation):
        """Fenêtre à guillotine - UN SEUL objet fusionné"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width
            
            # === CADRE PRINCIPAL ===
            self._add_rectangular_frame(bm, width, height, frame_w, FRAME_DEPTH, offset_y=0)
            
            # === RAIL CENTRAL HORIZONTAL ===
            rail_width = width - frame_w * 2
            self._add_horizontal_mullion(bm, rail_width, self.mullion_width, FRAME_DEPTH - 0.01,
                                        offset=Vector((0, 0.005, 0)))
            
            # === APPUI ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH)
            
            # === CHANFREINS ===
            if self.quality in ['MEDIUM', 'HIGH']:
                self._apply_bevels(bm)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowDoubleHung")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # ARCHED WINDOW (Fenêtre cintrée)
    # ============================================================
    
    def _create_arched_window(self, width, height, location, orientation):
        """Fenêtre avec arc - UN SEUL objet fusionné"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width
            rect_height = height * 0.7  # 70% rectangulaire
            
            # === CADRE RECTANGULAIRE BAS ===
            self._add_rectangular_frame_partial(bm, width, rect_height, frame_w, FRAME_DEPTH,
                                               offset=Vector((0, 0, -height * 0.15)), top_open=True)
            
            # === CADRE ARC EN HAUT ===
            self._add_arched_frame(bm, width, height * 0.3, frame_w, FRAME_DEPTH,
                                  offset=Vector((0, 0, height * 0.35)))
            
            # === APPUI ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH)
            
            # === CHANFREINS ===
            if self.quality in ['MEDIUM', 'HIGH']:
                self._apply_bevels(bm)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowArched")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # PICTURE WINDOW (Fenêtre panoramique)
    # ============================================================
    
    def _create_picture_window(self, width, height, location, orientation):
        """Fenêtre panoramique - Cadre ultra-fin"""
        bm = bmesh.new()
        
        try:
            frame_w = self.frame_width * 0.6  # Cadre très fin
            
            # === CADRE MINIMAL ===
            self._add_rectangular_frame(bm, width, height, frame_w, FRAME_DEPTH * 0.8, offset_y=0)
            
            # === APPUI MINIMAL ===
            self._add_window_sill(bm, width, height, FRAME_DEPTH, thin=True, modern=True)
            
            # === CHANFREINS ===
            if self.quality == 'HIGH':  # Seulement en HIGH pour Picture
                self._apply_bevels(bm)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowPicture")
            return obj
            
        finally:
            bm.free()
    
    # ============================================================
    # FONCTIONS UTILITAIRES - Construction de géométrie
    # ============================================================
    
    def _add_rectangular_frame(self, bm, width, height, frame_w, depth, offset=Vector((0,0,0)), offset_y=0):
        """Ajoute un cadre rectangulaire au bmesh"""
        hw = width / 2
        hh = height / 2
        fw = frame_w
        d = depth
        
        # Créer les 4 barres du cadre
        # HAUT
        self._add_box(bm, 
            center=offset + Vector((0, offset_y + d/2, hh - fw/2)),
            size=(width, d, fw))
        
        # BAS
        self._add_box(bm,
            center=offset + Vector((0, offset_y + d/2, -hh + fw/2)),
            size=(width, d, fw))
        
        # GAUCHE
        self._add_box(bm,
            center=offset + Vector((-hw + fw/2, offset_y + d/2, 0)),
            size=(fw, d, height))
        
        # DROITE
        self._add_box(bm,
            center=offset + Vector((hw - fw/2, offset_y + d/2, 0)),
            size=(fw, d, height))
    
    def _add_rectangular_frame_partial(self, bm, width, height, frame_w, depth, offset=Vector((0,0,0)), top_open=False):
        """Ajoute un cadre rectangulaire partiel (pour fenêtre cintrée)"""
        hw = width / 2
        hh = height / 2
        fw = frame_w
        d = depth
        
        # BAS
        self._add_box(bm,
            center=offset + Vector((0, d/2, -hh + fw/2)),
            size=(width, d, fw))
        
        # GAUCHE
        self._add_box(bm,
            center=offset + Vector((-hw + fw/2, d/2, 0)),
            size=(fw, d, height))
        
        # DROITE
        self._add_box(bm,
            center=offset + Vector((hw - fw/2, d/2, 0)),
            size=(fw, d, height))
        
        # HAUT (optionnel)
        if not top_open:
            self._add_box(bm,
                center=offset + Vector((0, d/2, hh - fw/2)),
                size=(width, d, fw))
    
    def _add_arched_frame(self, bm, width, height, frame_w, depth, offset=Vector((0,0,0))):
        """Ajoute un cadre en arc au bmesh"""
        hw = width / 2
        fw = frame_w
        d = depth
        segments = self.arc_segments  # Utilise la qualité
        
        # Créer les vertices de l'arc extérieur et intérieur
        outer_verts = []
        inner_verts = []
        
        for i in range(segments + 1):
            angle = math.pi * i / segments
            
            # Arc extérieur
            x_out = hw * math.cos(angle)
            z_out = hw * math.sin(angle)
            outer_verts.append(bm.verts.new(offset + Vector((x_out, 0, z_out))))
            
            # Arc intérieur
            x_in = (hw - fw) * math.cos(angle)
            z_in = (hw - fw) * math.sin(angle)
            inner_verts.append(bm.verts.new(offset + Vector((x_in, 0, z_in))))
        
        # Dupliquer pour créer la face arrière
        outer_verts_back = []
        inner_verts_back = []
        
        for i in range(segments + 1):
            angle = math.pi * i / segments
            x_out = hw * math.cos(angle)
            z_out = hw * math.sin(angle)
            outer_verts_back.append(bm.verts.new(offset + Vector((x_out, d, z_out))))
            
            x_in = (hw - fw) * math.cos(angle)
            z_in = (hw - fw) * math.sin(angle)
            inner_verts_back.append(bm.verts.new(offset + Vector((x_in, d, z_in))))
        
        # Créer les faces entre les arcs
        for i in range(segments):
            # Face extérieure
            bm.faces.new([
                outer_verts[i], outer_verts[i+1],
                outer_verts_back[i+1], outer_verts_back[i]
            ])
            
            # Face intérieure
            bm.faces.new([
                inner_verts_back[i], inner_verts_back[i+1],
                inner_verts[i+1], inner_verts[i]
            ])
            
            # Face avant (entre outer et inner)
            bm.faces.new([
                outer_verts[i], inner_verts[i],
                inner_verts[i+1], outer_verts[i+1]
            ])
            
            # Face arrière
            bm.faces.new([
                outer_verts_back[i+1], inner_verts_back[i+1],
                inner_verts_back[i], outer_verts_back[i]
            ])
    
    def _add_vertical_mullion(self, bm, height, width, depth, offset=Vector((0,0,0))):
        """Ajoute un montant vertical"""
        self._add_box(bm,
            center=offset + Vector((0, depth/2, 0)),
            size=(width, depth, height))
    
    def _add_horizontal_mullion(self, bm, width, height, depth, offset=Vector((0,0,0))):
        """Ajoute un montant horizontal"""
        self._add_box(bm,
            center=offset + Vector((0, depth/2, 0)),
            size=(width, depth, height))
    
    def _add_window_sill(self, bm, width, height, depth, thin=False, modern=False):
        """Ajoute un appui de fenêtre avec profil réaliste - CORRIGÉ"""
        hw = width / 2 + 0.02  # Légèrement plus large
        hh = height / 2
        
        sill_depth = SILL_DEPTH if not thin else SILL_DEPTH * 0.6
        sill_height = 0.03 if not thin else 0.02
        
        if modern:
            # Profil moderne simple
            points = [
                (-hw, 0, -hh - 0.015),
                (hw, 0, -hh - 0.015),
                (hw, sill_depth * 0.8, -hh - sill_height - 0.015),
                (hw, sill_depth, -hh - sill_height - 0.02),
                (-hw, sill_depth, -hh - sill_height - 0.02),
                (-hw, sill_depth * 0.8, -hh - sill_height - 0.015),
            ]
        else:
            # Profil standard avec goutte d'eau
            points = [
                (-hw, 0, -hh - 0.01),
                (-hw, 0, -hh),
                (hw, 0, -hh),
                (hw, 0, -hh - 0.01),
                (hw, sill_depth * 0.3, -hh - 0.01),
                (hw, sill_depth * 0.9, -hh - sill_height * 0.9),
                (hw, sill_depth, -hh - sill_height),
                (hw - 0.005, sill_depth - 0.003, -hh - sill_height - 0.005),  # Goutte d'eau
                (-hw + 0.005, sill_depth - 0.003, -hh - sill_height - 0.005),
                (-hw, sill_depth, -hh - sill_height),
                (-hw, sill_depth * 0.9, -hh - sill_height * 0.9),
                (-hw, sill_depth * 0.3, -hh - 0.01),
            ]
        
        # Créer les vertices du profil
        verts = [bm.verts.new(Vector(p)) for p in points]
        
        # Créer la face du profil
        bm.faces.new(verts)
        
        # === CORRECTION CRITIQUE : Mettre à jour la lookup table ===
        bm.faces.ensure_lookup_table()
        
        # Extruder pour donner l'épaisseur
        face = bm.faces[-1]
        ret = bmesh.ops.extrude_face_region(bm, geom=[face])
        extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=extruded_verts, vec=Vector((0, 0, -0.01)))
    
    def _add_box(self, bm, center, size):
        """Ajoute un cube au bmesh à la position donnée"""
        w, d, h = size
        hw, hd, hh = w/2, d/2, h/2
        cx, cy, cz = center
        
        # Créer les 8 vertices du cube
        verts = [
            bm.verts.new((cx - hw, cy - hd, cz - hh)),
            bm.verts.new((cx + hw, cy - hd, cz - hh)),
            bm.verts.new((cx + hw, cy + hd, cz - hh)),
            bm.verts.new((cx - hw, cy + hd, cz - hh)),
            bm.verts.new((cx - hw, cy - hd, cz + hh)),
            bm.verts.new((cx + hw, cy - hd, cz + hh)),
            bm.verts.new((cx + hw, cy + hd, cz + hh)),
            bm.verts.new((cx - hw, cy + hd, cz + hh)),
        ]
        
        # Créer les 6 faces
        bm.faces.new([verts[0], verts[1], verts[2], verts[3]])  # Bas
        bm.faces.new([verts[4], verts[7], verts[6], verts[5]])  # Haut
        bm.faces.new([verts[0], verts[4], verts[5], verts[1]])  # Avant
        bm.faces.new([verts[2], verts[6], verts[7], verts[3]])  # Arrière
        bm.faces.new([verts[0], verts[3], verts[7], verts[4]])  # Gauche
        bm.faces.new([verts[1], verts[5], verts[6], verts[2]])  # Droite
    
    # ============================================================
    # CHANFREINS AUTOMATIQUES
    # ============================================================
    
    def _apply_bevels(self, bm):
        """Applique des chanfreins automatiques sur les arêtes intérieures"""
        if self.bevel_amount <= 0:
            return
        
        # Sélectionner les arêtes pour chanfrein
        edges_to_bevel = []
        
        for edge in bm.edges:
            # Critères : arêtes intérieures (petites arêtes)
            edge_length = edge.calc_length()
            
            # Arêtes courtes = coins du cadre
            if edge_length < 0.15:
                # Vérifier si c'est une arête intérieure (pas sur les bords extérieurs)
                v1, v2 = edge.verts
                
                # Si les deux vertices sont "à l'intérieur" du cadre
                # (heuristique simple : coordonnées Y similaires)
                if abs(v1.co.y - v2.co.y) < 0.01:
                    edges_to_bevel.append(edge)
        
        # Appliquer le chanfrein
        if edges_to_bevel:
            try:
                bmesh.ops.bevel(
                    bm,
                    geom=edges_to_bevel,
                    offset=self.bevel_amount,
                    segments=self.bevel_segments,
                    profile=0.5,
                    affect='EDGES'
                )
                print(f"[Windows] Chanfreins appliqués sur {len(edges_to_bevel)} arêtes")
            except Exception as e:
                print(f"[Windows] Erreur chanfrein: {e}")
    
    # ============================================================
    # CRÉATION DU VERRE (objet séparé)
    # ============================================================
    
    def _create_glass_object(self, width, height, location, orientation, window_type):
        """Crée le vitrage comme objet séparé avec matériau glass"""
        bm = bmesh.new()
        
        try:
            # Calculer dimensions du verre
            if window_type in ['CASEMENT', 'FIXED', 'PICTURE']:
                # Verre simple
                frame_reduction = self.frame_width * 1.6
                glass_width = width - frame_reduction
                glass_height = height - frame_reduction
                
                self._add_glass_pane(bm, glass_width, glass_height, Vector((0, 0.02, 0)))
                
            elif window_type == 'SLIDING':
                # 2 panneaux de verre
                frame_reduction = self.frame_width * 1.6
                glass_width = (width - frame_reduction - self.mullion_width) / 2 - 0.01
                glass_height = height - frame_reduction
                
                # Panneau gauche
                self._add_glass_pane(bm, glass_width, glass_height, 
                                    Vector((-width/4 - self.mullion_width/4, 0.02, 0)))
                # Panneau droit
                self._add_glass_pane(bm, glass_width, glass_height,
                                    Vector((width/4 + self.mullion_width/4, 0.025, 0)))
                
            elif window_type == 'DOUBLE_HUNG':
                # 2 panneaux verticaux
                frame_reduction = self.frame_width * 1.6
                glass_width = width - frame_reduction
                glass_height = (height - frame_reduction - self.mullion_width) / 2 - 0.01
                
                # Panneau haut
                self._add_glass_pane(bm, glass_width, glass_height,
                                    Vector((0, 0.02, height/4 + self.mullion_width/4)))
                # Panneau bas
                self._add_glass_pane(bm, glass_width, glass_height,
                                    Vector((0, 0.025, -height/4 - self.mullion_width/4)))
                
            elif window_type == 'ARCHED':
                # Verre rectangulaire + arc
                frame_reduction = self.frame_width * 1.6
                glass_width = width - frame_reduction
                rect_height = height * 0.65
                
                # Partie rectangulaire
                self._add_glass_pane(bm, glass_width, rect_height,
                                    Vector((0, 0.02, -height * 0.15)))
                
                # Partie arc
                arc_height = height * 0.25
                self._add_glass_arc(bm, glass_width, arc_height,
                                   Vector((0, 0.02, height * 0.35)))
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowGlass")
            return obj
            
        finally:
            bm.free()
    
    def _add_glass_pane(self, bm, width, height, offset=Vector((0,0,0))):
        """Ajoute un panneau de verre au bmesh"""
        hw = width / 2
        hh = height / 2
        gt = GLASS_THICKNESS / 2
        
        # Face avant
        v1 = bm.verts.new(offset + Vector((-hw, -gt, -hh)))
        v2 = bm.verts.new(offset + Vector((hw, -gt, -hh)))
        v3 = bm.verts.new(offset + Vector((hw, -gt, hh)))
        v4 = bm.verts.new(offset + Vector((-hw, -gt, hh)))
        
        # Face arrière
        v5 = bm.verts.new(offset + Vector((-hw, gt, -hh)))
        v6 = bm.verts.new(offset + Vector((hw, gt, -hh)))
        v7 = bm.verts.new(offset + Vector((hw, gt, hh)))
        v8 = bm.verts.new(offset + Vector((-hw, gt, hh)))
        
        # Créer les faces
        bm.faces.new([v1, v2, v3, v4])  # Avant
        bm.faces.new([v5, v8, v7, v6])  # Arrière
        bm.faces.new([v1, v5, v6, v2])  # Bas
        bm.faces.new([v3, v7, v8, v4])  # Haut
        bm.faces.new([v1, v4, v8, v5])  # Gauche
        bm.faces.new([v2, v6, v7, v3])  # Droite
    
    def _add_glass_arc(self, bm, width, height, offset=Vector((0,0,0))):
        """Ajoute un panneau de verre en arc (optimisé avec quads)"""
        hw = width / 2
        gt = GLASS_THICKNESS / 2
        segments = self.arc_segments
        
        # Créer arc avant avec centre
        center_front = bm.verts.new(offset + Vector((0, -gt, 0)))
        arc_verts_front = []
        
        for i in range(segments + 1):
            angle = math.pi * i / segments
            x = hw * 0.9 * math.cos(angle)
            z = hw * 0.9 * math.sin(angle)
            arc_verts_front.append(bm.verts.new(offset + Vector((x, -gt, z))))
        
        # Créer arc arrière avec centre
        center_back = bm.verts.new(offset + Vector((0, gt, 0)))
        arc_verts_back = []
        
        for i in range(segments + 1):
            angle = math.pi * i / segments
            x = hw * 0.9 * math.cos(angle)
            z = hw * 0.9 * math.sin(angle)
            arc_verts_back.append(bm.verts.new(offset + Vector((x, gt, z))))
        
        # Créer faces entre avant et arrière (quads propres)
        for i in range(segments):
            bm.faces.new([
                arc_verts_front[i], arc_verts_front[i+1],
                arc_verts_back[i+1], arc_verts_back[i]
            ])
        
        # Fermer les extrémités avec des triangles au centre
        for i in range(segments):
            bm.faces.new([center_front, arc_verts_front[i+1], arc_verts_front[i]])
            bm.faces.new([center_back, arc_verts_back[i], arc_verts_back[i+1]])
    
    # ============================================================
    # MATÉRIAUX PROCÉDURAUX
    # ============================================================
    
    def _apply_frame_material(self, obj):
        """Applique un matériau PBR réaliste pour cadres de fenêtres"""
        mat_name = f"Window_Frame_Material_{self.quality}"
        mat = bpy.data.materials.get(mat_name)
        
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            
            # Output
            output = nodes.new('ShaderNodeOutputMaterial')
            output.location = (400, 0)
            
            # Principled BSDF
            principled = nodes.new('ShaderNodeBsdfPrincipled')
            principled.location = (0, 0)
            principled.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)  # Blanc
            principled.inputs['Metallic'].default_value = 0.0
            principled.inputs['Roughness'].default_value = 0.3  # Légèrement brillant
            principled.inputs['Specular IOR Level'].default_value = 0.5
            
            # Texture procédurale pour variation (qualité MEDIUM et HIGH)
            if self.quality in ['MEDIUM', 'HIGH']:
                # Noise pour texture bois/PVC
                noise = nodes.new('ShaderNodeTexNoise')
                noise.location = (-600, -200)
                noise.inputs['Scale'].default_value = 150.0 if self.quality == 'HIGH' else 100.0
                noise.inputs['Detail'].default_value = 5.0 if self.quality == 'HIGH' else 3.0
                noise.inputs['Roughness'].default_value = 0.5
                
                # ColorRamp pour ajuster le contraste
                ramp = nodes.new('ShaderNodeValToRGB')
                ramp.location = (-400, -200)
                ramp.color_ramp.elements[0].position = 0.4
                ramp.color_ramp.elements[1].position = 0.6
                
                # Bump pour relief subtil
                bump = nodes.new('ShaderNodeBump')
                bump.location = (-200, -200)
                bump.inputs['Strength'].default_value = 0.05 if self.quality == 'HIGH' else 0.02
                bump.inputs['Distance'].default_value = 0.01
                
                # Connections
                links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
                links.new(ramp.outputs['Color'], bump.inputs['Height'])
                links.new(bump.outputs['Normal'], principled.inputs['Normal'])
            
            # Connection finale
            links.new(principled.outputs['BSDF'], output.inputs['Surface'])
            
            print(f"[Windows] Matériau cadre créé: {mat_name}")
        
        # Assigner le matériau
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    
    def _apply_glass_material(self, obj):
        """Applique un matériau verre réaliste avec reflets"""
        mat_name = f"Window_Glass_Material_{self.quality}"
        mat = bpy.data.materials.get(mat_name)
        
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            
            # Output
            output = nodes.new('ShaderNodeOutputMaterial')
            output.location = (600, 0)
            
            if self.quality == 'LOW':
                # Version simple : Transparent BSDF
                transparent = nodes.new('ShaderNodeBsdfTransparent')
                transparent.location = (0, 0)
                transparent.inputs['Color'].default_value = (0.85, 0.92, 0.95, 1.0)
                
                links.new(transparent.outputs['BSDF'], output.inputs['Surface'])
                
            else:
                # Version réaliste : Glass BSDF + Glossy pour reflets
                
                # Glass BSDF
                glass = nodes.new('ShaderNodeBsdfGlass')
                glass.location = (0, 100)
                glass.inputs['IOR'].default_value = 1.52  # Verre standard
                glass.inputs['Roughness'].default_value = 0.0
                glass.inputs['Color'].default_value = (0.85, 0.92, 0.95, 1.0)  # Légèrement bleuté
                
                # Glossy BSDF pour reflets
                glossy = nodes.new('ShaderNodeBsdfGlossy')
                glossy.location = (0, -100)
                glossy.inputs['Roughness'].default_value = 0.05 if self.quality == 'HIGH' else 0.1
                glossy.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
                
                # Fresnel pour mix réaliste
                fresnel = nodes.new('ShaderNodeFresnel')
                fresnel.location = (-200, 0)
                fresnel.inputs['IOR'].default_value = 1.52
                
                # Mix Shader
                mix = nodes.new('ShaderNodeMixShader')
                mix.location = (300, 0)
                
                # Connections
                links.new(fresnel.outputs['Fac'], mix.inputs['Fac'])
                links.new(glass.outputs['BSDF'], mix.inputs[1])
                links.new(glossy.outputs['BSDF'], mix.inputs[2])
                links.new(mix.outputs['Shader'], output.inputs['Surface'])
                
                # Paramètres de rendu pour transparence
                mat.blend_method = 'BLEND'
                mat.shadow_method = 'HASHED' if self.quality == 'MEDIUM' else 'CLIP'
                # Note: 'use_screen_refraction' et 'refraction_depth' n'existent plus dans Blender 4.2+
                # La réfraction est gérée automatiquement via le Glass BSDF
            
            print(f"[Windows] Matériau verre créé: {mat_name}")
        
        # Assigner le matériau
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    
    # ============================================================
    # UTILITAIRES
    # ============================================================
    
    def _get_orientation_matrix(self, orientation):
        """Retourne la matrice de rotation selon l'orientation"""
        if orientation == 'front':
            return Matrix.Identity(4)
        elif orientation == 'back':
            return Matrix.Rotation(math.radians(180), 4, 'Z')
        elif orientation == 'left':
            return Matrix.Rotation(math.radians(90), 4, 'Z')
        elif orientation == 'right':
            return Matrix.Rotation(math.radians(-90), 4, 'Z')
        else:
            return Matrix.Identity(4)
    
    def _bmesh_to_object(self, bm, name):
        """Convertit un bmesh en objet Blender"""
        # Nettoyer et finaliser
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        
        # Créer le mesh
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        
        # Créer l'objet
        obj = bpy.data.objects.new(name, mesh)
        return obj
    
    def _create_fallback_window(self, width, height, location, orientation, collection):
        """Crée une fenêtre de secours ultra-simple en cas d'erreur"""
        print("[Windows] Création fenêtre de secours")
        bm = bmesh.new()
        
        try:
            # Cadre simple
            self._add_rectangular_frame(bm, width, height, 0.05, 0.07, offset_y=0)
            
            # Appliquer orientation et position
            rotation_matrix = self._get_orientation_matrix(orientation)
            bmesh.ops.transform(bm, matrix=rotation_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts, vec=location)
            
            obj = self._bmesh_to_object(bm, "WindowFallback")
            collection.objects.link(obj)
            obj["house_part"] = "wall"
            
            return [obj]
            
        finally:
            bm.free()


# Liste des classes à enregistrer
classes = ()


def register():
    """Enregistrement du module"""
    print("[House] Module Windows ULTIMATE chargé")
    print("  - Système qualité LOW/MEDIUM/HIGH")
    print("  - Chanfreins automatiques")
    print("  - Matériaux procéduraux PBR")


def unregister():
    """Désenregistrement du module"""
    print("[House] Module Windows déchargé")