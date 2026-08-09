# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - UI Panels Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.types import Panel

from .materials.brick_geometry import BRICK_LENGTH, BRICK_HEIGHT, MORTAR_GAP

# Surface d'une cellule brique+joint sur la façade (m²)
BRICK_CELL_AREA = (BRICK_LENGTH + MORTAR_GAP) * (BRICK_HEIGHT + MORTAR_GAP)


def _estimate_brick_count(props):
    """✅ Estimation UNIQUE du nombre de briques (partagée entre panneaux)

    Basée sur la cellule réelle brique+joint — l'ancienne formule (/0.014)
    ignorait les joints de mortier et surestimait de ~28%.
    """
    perimeter = 2 * (props.house_width + props.house_length)
    total_height = props.num_floors * props.floor_height
    return int(perimeter * total_height / BRICK_CELL_AREA)


class HOUSE_UL_openings(bpy.types.UIList):
    """Liste du tableau d'ouvertures"""
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname):
        row = layout.row(align=True)
        row.label(text=f"{item.wall[:2]} {item.item_type[:4]} "
                       f"{item.width:.2f}×{item.height:.2f} "
                       f"@{item.pos:.1f}m ét.{item.floor}")


class HOUSE_UL_rooms(bpy.types.UIList):
    """Liste du tableau de pièces"""
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname):
        row = layout.row(align=True)
        row.label(text=f"{item.name} ({item.room_type.title()}) "
                       f"{item.surface:.1f} m²")


class HOUSE_PT_main_panel(Panel):
    """Panneau principal du générateur de maison"""
    bl_label = "House Generator"
    bl_idname = "HOUSE_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        box = layout.box()
        box.label(text="Mode de génération", icon='SETTINGS')
        box.prop(props, "generation_mode", expand=True)
        
        if props.generation_mode == 'AUTO':
            self.draw_auto_mode(context, layout, props)
        else:
            self.draw_manual_mode(context, layout, props)
    
    def draw_auto_mode(self, context, layout, props):
        """Interface pour le mode automatique"""
        
        box = layout.box()
        box.label(text="Dimensions", icon='EMPTY_ARROWS')
        col = box.column(align=True)
        col.prop(props, "house_width")
        col.prop(props, "house_length")
        col.separator()
        col.prop(props, "num_floors")
        col.prop(props, "floor_height")
        
        box = layout.box()
        box.label(text="Style architectural", icon='HOME')
        box.prop(props, "architectural_style", text="")
        box.prop(props, "detail_level", text="Détail")

        # ✅ v1.8: presets régionaux (silhouettes complètes)
        box = layout.box()
        box.label(text="Preset régional", icon='WORLD')
        row = box.row(align=True)
        row.prop(props, "house_preset", text="")
        row.operator("house.apply_preset", text="", icon='PLAY')

        # ✅ v1.14: MODE PROGRAMME — décrire le besoin, House résout
        box = layout.box()
        box.label(text="Programme (plain-pied)", icon='OUTLINER')
        row = box.row(align=True)
        row.prop(props, "prog_bedrooms", text="Chambres")
        row.prop(props, "prog_bathrooms", text="SdB")
        row = box.row(align=True)
        row.prop(props, "prog_wc_separate", text="WC séparé")
        row.prop(props, "prog_garage", text="")
        box.prop(props, "prog_surface", text="Surface cible (0 = auto)")
        box.operator("house.solve_programme", icon='CHECKMARK')
        if props.programme_active:
            box.label(text="Distribution pilotée par le programme",
                      icon='CHECKMARK')
            box.prop(props, "programme_active", text="Désactiver",
                     toggle=True, invert_checkbox=True)

        # ✅ v1.15: slots d'assets (optionnels) + finitions procédurales
        box = layout.box()
        box.label(text="Assets & finitions", icon='ASSET_MANAGER')
        box.label(text="Slots optionnels (vide = procédural):")
        box.prop(props, "window_asset", text="Fenêtre")
        box.prop(props, "door_asset", text="Porte")
        box.prop(props, "shutter_asset", text="Volet")
        box.prop(props, "tile_asset", text="Tuile")
        box.prop(props, "wall_finish", text="Murs")
        if props.wall_finish == 'PIERRE':
            box.prop(props, "include_stone_surrounds",
                     text="Encadrements + chaînages pierre")
        box.prop(props, "roof_finish", text="Toit")
        box.prop(props, "joinery_color", text="Menuiseries (RAL)")

        # ✅ v1.29 PACK RÉALISME (textures scannées CC0, optionnel)
        box = layout.box()
        box.label(text="Pack réalisme (textures CC0)", icon='TEXTURE')
        box.prop(props, "realism_dir", text="")
        if props.realism_dir:
            try:
                from . import realism
                rep = realism.report(props)
            except Exception:
                rep = None
            if rep:
                box.label(text=f"Trouvé: {rep}", icon='CHECKMARK')
            else:
                box.label(text="Aucun set reconnu (pierre/, enduit/, "
                               "sol/, tuiles/, *.hdr)", icon='ERROR')
        else:
            box.label(text="polyhaven.com · ambientcg.com (gratuit)")
        
        layout.separator()
        row = layout.row()
        row.scale_y = 2.0
        row.operator("house.generate_auto", text="Générer la maison", icon='HOME')
        
        # ✅ TABLEAU D'OUVERTURES (types/tailles/allèges libres)
        box = layout.box()
        box.prop(props, "use_openings_table",
                 text="Tableau d'ouvertures (remplace l'auto)",
                 toggle=True)
        if props.use_openings_table:
            row = box.row()
            row.template_list("HOUSE_UL_openings", "",
                              props, "openings_table",
                              props, "openings_table_index", rows=4)
            col = row.column(align=True)
            col.operator("house.opening_add", text="", icon='ADD')
            col.operator("house.opening_remove", text="", icon='REMOVE')
            if 0 <= props.openings_table_index < len(props.openings_table):
                it = props.openings_table[props.openings_table_index]
                col2 = box.column(align=True)
                row = col2.row(align=True)
                row.prop(it, "wall", text="")
                row.prop(it, "item_type", text="")
                row = col2.row(align=True)
                row.prop(it, "width", text="L")
                row.prop(it, "height", text="H")
                row = col2.row(align=True)
                row.prop(it, "pos", text="Position")
                row.prop(it, "sill", text="Allège")
                col2.prop(it, "floor", text="Étage")

        # ✅ v1.27 TABLEAU DE PIÈCES (surfaces du brief)
        box = layout.box()
        box.prop(props, "use_rooms_table",
                 text="Tableau de pièces (surfaces m²)", toggle=True)
        if props.use_rooms_table:
            row = box.row()
            row.template_list("HOUSE_UL_rooms", "",
                              props, "rooms_table",
                              props, "rooms_table_index", rows=4)
            col = row.column(align=True)
            col.operator("house.room_add", text="", icon='ADD')
            col.operator("house.room_remove", text="", icon='REMOVE')
            if 0 <= props.rooms_table_index < len(props.rooms_table):
                it = props.rooms_table[props.rooms_table_index]
                col2 = box.column(align=True)
                col2.prop(it, "name", text="Nom")
                row = col2.row(align=True)
                row.prop(it, "room_type", text="")
                row.prop(it, "surface", text="m²")
            if len(props.rooms_table) >= 2:
                total = sum(r.surface for r in props.rooms_table)
                box.label(text=f"Bande arrière: {total:.1f} m² "
                               f"({len(props.rooms_table)} pièces)",
                          icon='INFO')

        # ✅ v1.28 CAMÉRA PHOTO (verticales droites + développement)
        box = layout.box()
        box.label(text="Rendu photo", icon='CAMERA_DATA')
        box.operator("house.camera_photo", icon='RESTRICT_RENDER_OFF')
        box.label(text="Imperfections photo: niveau Détail = Photo")

        # ✅ TERRAIN & IMPLANTATION
        box = layout.box()
        box.label(text="Terrain & implantation", icon='WORLD_DATA')
        box.prop(props, "include_environment", text="Environnement", toggle=True)
        if props.include_environment:
            box.prop(props, "terrain_mode", text="Mode")
            if props.terrain_mode == 'AUTO':
                row = box.row(align=True)
                row.prop(props, "parcel_width", text="Larg.")
                row.prop(props, "parcel_length", text="Long.")
                row = box.row(align=True)
                row.prop(props, "parcel_north", text="Nord°")
                row.prop(props, "parcel_slope", text="Pente%")
                box.prop(props, "parcel_access", text="Accès")
                row = box.row(align=True)
                row.prop(props, "house_pos_x", text="Pos X")
                row.prop(props, "house_pos_y", text="Pos Y")
                box.prop(props, "house_rotation", text="Orientation°")
                row = box.row(align=True)
                row.prop(props, "include_hedge", text="Haie")
                row.prop(props, "include_grass", text="Herbe")
            elif props.terrain_mode == 'CUSTOM':
                box.prop(props, "terrain_asset", text="Mon terrain")
            if props.terrain_mode != 'LEGACY':
                box.prop(props, "sun_hour", text="Heure solaire")

        layout.separator()
        row = layout.row()
        row.prop(context.scene, "house_auto_update", text="Mise à jour auto")
        row.prop(context.scene, "house_viewport_proxy", text="Proxy viewport")

        # ✅ ASSETS: menuiseries réutilisables via l'Asset Browser
        layout.separator()
        layout.operator("house.mark_assets", icon='ASSET_MANAGER')
        layout.operator("house.export_asset_library", icon='EXPORT')
        layout.operator("house.export_gltf", icon='EXPORT')
    
    def draw_manual_mode(self, context, layout, props):
        """Interface pour le mode manuel"""

        box = layout.box()
        box.label(text="Plan 2D", icon='IMAGE_DATA')
        box.prop(props, "plan_image_path", text="")
        box.prop(props, "plan_scale")
        box.prop(props, "plan_opacity")

        row = box.row(align=True)
        row.operator("house.import_plan", text="Importer", icon='IMPORT')
        row.operator("house.toggle_plan", text="Afficher/Masquer", icon='HIDE_OFF')

        # ✅ FIX: Les outils de construction étaient implémentés et
        # enregistrés mais AUCUN bouton ne les exposait — le mode manuel
        # n'avait aucun moyen de créer un mur!
        layout.separator()
        box = layout.box()
        box.label(text="Construction", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        col.operator("house.add_wall", text="Ajouter un mur (2 clics)", icon='MOD_BUILD')
        row = col.row(align=True)
        row.operator("house.add_door", text="Porte", icon='MESH_PLANE')
        row.operator("house.add_window", text="Fenêtre", icon='MOD_LATTICE')

        layout.separator()
        # ✅ FIX: 'house.generate_from_plan' n'existe pas (le panneau entier
        # plantait en mode MANUEL) — l'opérateur réel est finalize_manual
        layout.operator("house.finalize_manual", text="Finaliser la construction", icon='HOME')


class HOUSE_PT_roof_panel(Panel):
    """Panneau pour les paramètres du toit"""
    bl_label = "Toit"
    bl_idname = "HOUSE_PT_roof_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column(align=True)
        col.prop(props, "roof_type", text="Type")
        col.prop(props, "roof_pitch", text="Pente")
        col.prop(props, "ridge_height_target", text="Faîtage cible (0=pente)")
        # ✅ v1.27: CONFLIT DE COTES visible — quand le faîtage cible
        # impose une autre pente que le slider, on le DIT au lieu de
        # choisir en silence (le réflexe "le toit semble trop grand"
        # vient toujours d'un brief incohérent)
        if props.ridge_height_target > 0.1 \
                and props.roof_type in ('GABLE', 'HIP', 'SKELETON'):
            import math as _m
            wall_top = props.num_floors * props.floor_height
            half = min(props.house_width, props.house_length) / 2
            if props.ridge_height_target > wall_top + 0.2 and half > 0.5:
                derived = _m.degrees(_m.atan(
                    (props.ridge_height_target - wall_top) / half))
                eff = max(10.0, min(60.0, derived))
                if abs(eff - props.roof_pitch) > 1.0:
                    box_w = col.box()
                    box_w.label(
                        text=f"Faîtage {props.ridge_height_target:.2f} m "
                             f"→ pente {eff:.1f}°",
                        icon='INFO')
                    box_w.label(
                        text=f"(le slider {props.roof_pitch:.0f}° est "
                             f"ignoré)")
                if abs(eff - derived) > 0.5:
                    col.label(text=f"Faîtage inatteignable (>60°): "
                                   f"réel {wall_top + half * _m.tan(_m.radians(eff)):.2f} m",
                              icon='ERROR')
        col.prop(props, "roof_overhang", text="Débord")
        if props.roof_type == 'GABLE':
            col.prop(props, "attic_habitable", text="Combles aménagés")
            if props.attic_habitable:
                col.prop(props, "attic_trusses", text="Fermes apparentes")

        # ✅ NOUVEAU: Couverture + gouttières + cheminée
        layout.separator()
        col = layout.column(align=True)
        col.prop(props, "roof_covering", text="Couverture")
        if props.roof_covering == 'TILES':
            col.prop(props, "tile_color", text="Couleur tuiles")
        col.prop(props, "include_gutters", text="Gouttières")
        col.prop(props, "include_chimney", text="Cheminée")
        col.prop(props, "include_roof_windows", text="Fenêtres de toit")
        if props.include_roof_windows:
            col.prop(props, "roof_window_style", text="Style")
            col.prop(props, "num_roof_windows", text="Nombre")
            if props.roof_type == 'FLAT':
                col.label(text="Pas de velux sur toit plat", icon='ERROR')

        # ✅ UX: Avertir DANS l'UI quand la pente sera clampée à la plage
        # normative du type de toit (avant: clamp silencieux, console only)
        from .operators_auto import HOUSE_OT_generate_auto
        lo, hi = HOUSE_OT_generate_auto.PITCH_RANGES.get(props.roof_type, (5.0, 60.0))
        if not (lo <= props.roof_pitch <= hi):
            row = layout.row()
            row.alert = True
            clamped = max(lo, min(hi, props.roof_pitch))
            row.label(text=f"Pente ramenée à {clamped:.0f}° (plage {lo:.0f}-{hi:.0f}°)", icon='ERROR')


class HOUSE_PT_windows_panel(Panel):
    """Panneau pour les paramètres des fenêtres"""
    bl_label = "Fenêtres"
    bl_idname = "HOUSE_PT_windows_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column(align=True)
        col.prop(props, "window_type", text="Type")
        col.prop(props, "window_quality", text="Qualité")
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(props, "window_width", text="Largeur")
        # ✅ FIX: En mode AUTO, la hauteur des fenêtres est pilotée par le
        # RATIO (window_height ne sert qu'au mode manuel — le slider
        # "Hauteur" affiché ici ne faisait rien)
        col.prop(props, "window_height_ratio", text="Hauteur (ratio étage)")

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "num_windows_front", text="Façade")
        col.prop(props, "num_windows_back", text="Arrière")
        col.prop(props, "num_windows_side", text="Côtés")

        layout.separator()
        # ✅ NOUVEAU: Volets battants
        layout.prop(props, "include_shutters", text="Volets", toggle=True)


class HOUSE_PT_doors_panel(Panel):
    """Panneau pour les paramètres des portes"""
    bl_label = "Portes"
    bl_idname = "HOUSE_PT_doors_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column(align=True)
        col.prop(props, "front_door_width", text="Largeur porte")
        # ✅ FIX: door_type et door_quality étaient lus par le générateur
        # mais jamais exposés — 4 styles et 3 qualités inaccessibles!
        col.prop(props, "door_type", text="Type")
        col.prop(props, "door_quality", text="Qualité")


class HOUSE_PT_walls_panel(Panel):
    """Panneau pour les paramètres des murs"""
    bl_label = "Murs"
    bl_idname = "HOUSE_PT_walls_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        box = layout.box()
        box.label(text="Type de construction", icon='MESH_CUBE')
        box.prop(props, "wall_construction_type", text="")
        
        if props.wall_construction_type == 'BRICK_3D':
            box.separator()
            box.label(text="Qualité géométrie 3D:", icon='MESH_GRID')
            box.prop(props, "brick_3d_quality", text="")

            # ✅ NOUVEAU: Moteur Geometry Nodes (1 objet au lieu de milliers)
            box.separator()
            box.prop(props, "brick_use_geonodes", text="Moteur Geometry Nodes", toggle=True)
            if props.brick_use_geonodes:
                box.label(text="1 objet, viewport fluide", icon='GEOMETRY_NODES')
            
            # ✅ FIX: Estimation basée sur la CELLULE réelle brique+joint
            # (0.232×0.077m) — l'ancien /0.014 surestimait de ~28%
            brick_count_approx = _estimate_brick_count(props)

            box.separator()
            info_box = box.box()
            info_box.label(text=f"Briques: ~{brick_count_approx:,}", icon='INFO')
            
            if props.brick_3d_quality == 'HIGH':
                info_box.label(text="Calcul intensif", icon='ERROR')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(props, "wall_thickness", text="Épaisseur")


class HOUSE_PT_materials_panel(Panel):
    """Panneau pour les matériaux"""
    bl_label = "Matériaux"
    bl_idname = "HOUSE_PT_materials_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = False
        
        layout.prop(props, "use_materials", text="Utiliser les matériaux", toggle=True)
        
        if not props.use_materials:
            return
        
        layout.separator()
        
        # ============================================================
        # ✅ NOUVEAU : SYSTÈME DE MATÉRIAUX BRIQUES 3D
        # ============================================================
        
        box = layout.box()
        box.label(text="Murs extérieurs", icon='MATERIAL')
        
        col = box.column(align=True)
        
        # Si briques 3D : afficher le nouveau système
        if props.wall_construction_type == 'BRICK_3D':
            col.label(text="Mode matériau briques 3D:", icon='NODE_MATERIAL')
            col.prop(props, "brick_material_mode", text="")
            
            col.separator()
            
            # MODE COULEUR UNIE
            if props.brick_material_mode == 'COLOR':
                subbox = col.box()
                subbox.label(text="Couleur unie:", icon='COLOR')
                subbox.prop(props, "brick_solid_color", text="")
                
            # MODE PRESET RÉALISTE
            elif props.brick_material_mode == 'PRESET':
                subbox = col.box()
                subbox.label(text="Preset briques:", icon='TEXTURE')
                subbox.prop(props, "brick_preset_type", text="")
                
                # Afficher un aperçu du preset
                preset_colors = {
                    'BRICK_RED': "🔴 Rouge traditionnel",
                    'BRICK_RED_DARK': "🟤 Rouge foncé",
                    'BRICK_ORANGE': "🟠 Orangé/terre cuite",
                    'BRICK_BROWN': "🟫 Brun/chocolat",
                    'BRICK_YELLOW': "🟡 Jaune (London)",
                    'BRICK_GREY': "⚪ Gris moderne"
                }
                # ✅ FIX: .get() avec fallback — les presets PBR scannés
                # (PBR_*) n'apparaissaient pas dans l'aperçu
                subbox.label(
                    text=preset_colors.get(props.brick_preset_type, "🎨 Preset PBR (texture)"),
                    icon='INFO')
            
            # MODE CUSTOM
            elif props.brick_material_mode == 'CUSTOM':
                subbox = col.box()
                subbox.label(text="Matériau personnalisé:", icon='MATERIAL_DATA')
                subbox.prop(props, "brick_custom_material", text="")

                if not props.brick_custom_material:
                    warning = subbox.box()
                    warning.label(text="⚠ Aucun matériau sélectionné", icon='ERROR')
                    warning.label(text="Preset utilisé par défaut")

            # ✅ NOUVEAU: Couleur du mortier (joints entre briques)
            col.separator()
            subbox = col.box()
            subbox.label(text="Mortier (joints):", icon='MOD_BUILD')
            subbox.prop(props, "mortar_color", text="")

            # ✅ NOUVEAU: Pattern d'appareillage des briques
            subbox = col.box()
            subbox.label(text="Appareillage:", icon='MESH_GRID')
            subbox.prop(props, "brick_bonding_pattern", text="")

        # Si murs simples : couleur du mur
        # ✅ FIX: L'ancienne section (wall_material_type / wall_brick_quality /
        # wall_brick_color) n'était lue par AUCUN code générateur — 8 styles
        # et 3 qualités qui ne faisaient rien, pendant que la propriété
        # réellement utilisée (wall_material_color) n'était pas exposée!
        else:
            col.label(text="Couleur des murs:", icon='COLOR')
            col.prop(props, "wall_material_color", text="")

        layout.separator()

        box = layout.box()
        box.label(text="Toit", icon='MATERIAL')
        col = box.column(align=True)
        # ✅ FIX: Le swatch éditait roof_color, mais le générateur lit
        # roof_material_color — la couleur du toit ne changeait jamais!
        col.prop(props, "roof_material_color", text="Couleur")

        box = layout.box()
        box.label(text="Planchers", icon='MATERIAL')
        col = box.column(align=True)
        col.prop(props, "floor_material_color", text="Couleur")


class HOUSE_PT_elements_panel(Panel):
    """Panneau pour les éléments additionnels"""
    bl_label = "Éléments additionnels"
    bl_idname = "HOUSE_PT_elements_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        # ✅ INTÉRIEURS
        box = layout.box()
        box.prop(props, "include_interiors", text="Intérieurs (plafonds, cloisons)", toggle=True)
        if props.include_interiors:
            box.prop(props, "num_bedrooms", text="Chambres")
            box.prop(props, "include_electrical", text="Électricité (prises)")
            if props.include_electrical:
                box.prop(props, "outlets_per_room", text="Prises par pièce")
            box.prop(props, "include_interior_lights", text="Éclairage intérieur")
            box.prop(props, "include_furnishing", text="Aménagement (cuisine/SdB/mobilier)")
            if props.include_furnishing:
                col = box.column(align=True)
                col.label(text="Slots meubles (vide = procédural):")
                col.prop(props, "kitchen_asset", text="Cuisine")
                col.prop(props, "bathroom_asset", text="SdB")
                col.prop(props, "bed_asset", text="Lit")
                col.prop(props, "table_asset", text="Table")
                col.prop(props, "sofa_asset", text="Canapé")
            box.operator("house.camera_interior", icon='CAMERA_DATA')
            box.prop(props, "interior_wall_color", text="Peinture murs")

        # ✅ MULTI-VOLUMES: aile en L (module volumes.py)
        box = layout.box()
        box.prop(props, "include_wing", text="Aile (plan en L)", toggle=True)
        if props.include_wing:
            col = box.column(align=True)
            col.prop(props, "wing_side", text="Côté")
            col.prop(props, "wing_width", text="Largeur")
            col.prop(props, "wing_depth", text="Profondeur")
            col.prop(props, "wing_offset", text="Position")
            col.prop(props, "wing_floors", text="Étages")
            box.prop(props, "include_wing2", text="Seconde aile (T/U)", toggle=True)
            if props.include_wing2:
                col = box.column(align=True)
                col.prop(props, "wing2_side", text="Côté")
                col.prop(props, "wing2_width", text="Largeur")
                col.prop(props, "wing2_depth", text="Profondeur")
                col.prop(props, "wing2_offset", text="Position")
                col.prop(props, "wing2_floors", text="Étages")
            if props.roof_type not in ('GABLE', 'HIP', 'GAMBREL'):
                box.label(text="Toit GABLE/croupe/mansarde requis", icon='ERROR')

        # ✅ IMPLÉMENTÉ: garage, terrasse, balcon (module features.py)
        box = layout.box()
        box.prop(props, "include_garage", text="Garage", toggle=True)
        if props.include_garage:
            col = box.column(align=True)
            col.prop(props, "garage_width", text="Largeur")
            col.prop(props, "garage_depth", text="Profondeur")
            col.prop(props, "garage_position", text="Côté")

        box = layout.box()
        box.prop(props, "include_terrace", text="Terrasse (arrière)", toggle=True)

        box = layout.box()
        box.prop(props, "include_balcony", text="Balcon (étages 2+)", toggle=True)

        layout.separator()
        box = layout.box()
        box.label(text="Fondations", icon='MESH_PLANE')
        box.prop(props, "foundation_height", text="Hauteur")


# Note: le panneau "Distribution des pièces" a été retiré car il référençait
# des propriétés inexistantes (num_rooms, include_kitchen, include_bathroom,
# num_bathrooms) et cassait l'affichage. À réintroduire quand la génération
# de pièces intérieures sera implémentée.


class HOUSE_PT_advanced_panel(Panel):
    """Panneau pour les options avancées"""
    bl_label = "Options avancées"
    bl_idname = "HOUSE_PT_advanced_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        col = layout.column(align=True)
        # ✅ FIX: "(bientôt)" — fonctionnalité non implémentée (et défaut
        # passé à False: elle levait un warning à CHAQUE génération)
        col.prop(props, "auto_lighting", text="Éclairage auto (bientôt)")
        # ✅ FIX: show_dimensions / show_grid retirés — lus par aucun code

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "collection_name", text="Collection")
        col.prop(props, "random_seed", text="Seed aléatoire")


class HOUSE_PT_info_panel(Panel):
    """Panneau d'informations"""
    bl_label = "Informations"
    bl_idname = "HOUSE_PT_info_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'House'
    # ✅ FIX: Rattaché au panneau principal comme les autres sous-panneaux
    bl_parent_id = "HOUSE_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.house_generator
        
        total_height = props.num_floors * props.floor_height
        total_area = props.house_width * props.house_length
        wall_perimeter = 2 * (props.house_width + props.house_length)
        
        box = layout.box()
        box.label(text="Statistiques", icon='INFO')
        
        col = box.column(align=True)
        col.label(text=f"Surface: {total_area:.1f} m²")
        col.label(text=f"Hauteur totale: {total_height:.1f} m")
        col.label(text=f"Périmètre: {wall_perimeter:.1f} m")
        
        if props.wall_construction_type == 'BRICK_3D':
            # ✅ FIX: Formule partagée (l'ancienne surestimait de ~28%)
            brick_count = _estimate_brick_count(props)
            col.separator()
            col.label(text=f"Briques: ~{brick_count:,}")

        layout.separator()

        box = layout.box()
        box.label(text="À propos", icon='QUESTION')
        col = box.column(align=True)
        # ✅ FIX: Version lue depuis bl_info (le "v1.0" en dur avait dérivé)
        from . import bl_info
        col.label(text="House Generator v" + ".".join(str(v) for v in bl_info["version"]))
        col.label(text="© 2025 mvaertan")

        layout.separator()
        layout.operator("wm.url_open", text="Documentation", icon='URL').url = "https://github.com/mvaertan/house-generator"


classes = (
    HOUSE_UL_openings,
    HOUSE_UL_rooms,
    HOUSE_PT_main_panel,
    HOUSE_PT_roof_panel,
    HOUSE_PT_windows_panel,
    HOUSE_PT_doors_panel,
    HOUSE_PT_walls_panel,
    HOUSE_PT_materials_panel,
    HOUSE_PT_elements_panel,
    HOUSE_PT_advanced_panel,
    HOUSE_PT_info_panel,
)


def register():
    """Enregistrement des panneaux UI"""
    for cls in classes:
        bpy.utils.register_class(cls)
    print("[House] Panneaux UI enregistrés")
    print("  ✓ Interface système matériaux briques (COLOR/PRESET/CUSTOM)")


def unregister():
    """Désenregistrement des panneaux UI"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[House] Panneaux UI désenregistrés")