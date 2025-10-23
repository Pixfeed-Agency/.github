# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Preferences Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.types import AddonPreferences
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
    FloatProperty,
    IntProperty,
)


class HouseAddonPreferences(AddonPreferences):
    """Préférences de l'extension House"""
    bl_idname = __package__
    
    # ============================================================
    # PARAMÈTRES GÉNÉRAUX
    # ============================================================
    
    default_units: EnumProperty(
        name="Unités par défaut",
        description="Système d'unités à utiliser par défaut",
        items=[
            ('METRIC', "Métrique", "Utiliser le système métrique (mètres)", 0),
            ('IMPERIAL', "Impérial", "Utiliser le système impérial (pieds/pouces)", 1),
        ],
        default='METRIC'
    )
    
    auto_save: BoolProperty(
        name="Sauvegarde automatique",
        description="Sauvegarder automatiquement après la génération d'une maison",
        default=False
    )
    
    show_tips: BoolProperty(
        name="Afficher les astuces",
        description="Afficher des conseils et astuces dans l'interface",
        default=True
    )
    
    debug_mode: BoolProperty(
        name="Mode debug",
        description="Afficher des informations de debug dans la console",
        default=False
    )
    
    # ============================================================
    # PARAMÈTRES DE GÉNÉRATION
    # ============================================================
    
    default_style: EnumProperty(
        name="Style par défaut",
        description="Style architectural utilisé par défaut",
        items=[
            ('MODERN', "Moderne", "Style contemporain"),
            ('TRADITIONAL', "Traditionnel", "Style classique"),
            ('COTTAGE', "Cottage", "Style campagne"),
            ('VILLA', "Villa", "Style méditerranéen"),
        ],
        default='MODERN'
    )
    
    auto_apply_materials: BoolProperty(
        name="Appliquer matériaux automatiquement",
        description="Appliquer automatiquement les matériaux lors de la génération",
        default=True
    )
    
    create_collection: BoolProperty(
        name="Créer une collection",
        description="Créer automatiquement une collection 'House' pour organiser les objets",
        default=True
    )
    
    # ============================================================
    # PARAMÈTRES D'AFFICHAGE
    # ============================================================
    
    ui_scale: FloatProperty(
        name="Échelle de l'interface",
        description="Échelle des éléments de l'interface (boutons, texte)",
        default=1.0,
        min=0.5,
        max=2.0,
        step=0.1
    )
    
    show_advanced_by_default: BoolProperty(
        name="Afficher options avancées",
        description="Afficher les options avancées par défaut dans l'interface",
        default=False
    )
    
    panel_category: StringProperty(
        name="Catégorie du panneau",
        description="Nom de l'onglet dans la sidebar où apparaît le panneau House",
        default="House",
        maxlen=64
    )
    
    # ============================================================
    # PARAMÈTRES DE PERFORMANCE
    # ============================================================
    
    max_subdivision: IntProperty(
        name="Subdivision max",
        description="Niveau maximum de subdivision pour les meshes générés",
        default=2,
        min=0,
        max=5
    )
    
    use_instances: BoolProperty(
        name="Utiliser les instances",
        description="Utiliser des instances pour les éléments répétitifs (fenêtres, portes) pour améliorer les performances",
        default=True
    )
    
    optimize_mesh: BoolProperty(
        name="Optimiser les meshes",
        description="Optimiser automatiquement les meshes générés (merge vertices, etc.)",
        default=True
    )
    
    # ============================================================
    # CHEMINS ET BIBLIOTHÈQUES
    # ============================================================
    
    assets_path: StringProperty(
        name="Dossier des assets",
        description="Chemin vers le dossier contenant les assets (textures, modèles)",
        default="",
        subtype='DIR_PATH'
    )
    
    presets_path: StringProperty(
        name="Dossier des presets",
        description="Chemin vers le dossier contenant les presets de maisons",
        default="",
        subtype='DIR_PATH'
    )
    
    # ============================================================
    # RACCOURCIS CLAVIER (pour version future)
    # ============================================================
    
    enable_shortcuts: BoolProperty(
        name="Activer les raccourcis",
        description="Activer les raccourcis clavier pour l'extension",
        default=False
    )
    
    # ============================================================
    # FONCTIONNALITÉS EXPÉRIMENTALES
    # ============================================================
    
    experimental_features: BoolProperty(
        name="Fonctionnalités expérimentales",
        description="Activer les fonctionnalités expérimentales (peut être instable)",
        default=False
    )
    
    enable_ai_generation: BoolProperty(
        name="Génération IA",
        description="Activer la génération procédurale avancée (expérimental)",
        default=False
    )
    
    # ============================================================
    # INTERFACE DE PRÉFÉRENCES
    # ============================================================
    
    def draw(self, context):
        layout = self.layout
        
        # En-tête
        box = layout.box()
        row = box.row()
        row.label(text="House Extension v1.0", icon='HOME')
        row = box.row()
        row.label(text="Par mvaertan")
        
        layout.separator()
        
        # ===== SECTION GÉNÉRAL =====
        box = layout.box()
        box.label(text="Paramètres généraux", icon='PREFERENCES')
        
        col = box.column(align=True)
        col.prop(self, "default_units")
        col.prop(self, "auto_save")
        col.prop(self, "show_tips")
        col.prop(self, "debug_mode")
        
        layout.separator()
        
        # ===== SECTION GÉNÉRATION =====
        box = layout.box()
        box.label(text="Génération", icon='MODIFIER_ON')
        
        col = box.column(align=True)
        col.prop(self, "default_style")
        col.prop(self, "auto_apply_materials")
        col.prop(self, "create_collection")
        
        layout.separator()
        
        # ===== SECTION INTERFACE =====
        box = layout.box()
        box.label(text="Interface", icon='WINDOW')
        
        col = box.column(align=True)
        col.prop(self, "ui_scale", slider=True)
        col.prop(self, "show_advanced_by_default")
        col.prop(self, "panel_category")
        
        row = col.row()
        row.label(text="Redémarrez Blender pour appliquer les changements de catégorie", icon='INFO')
        
        layout.separator()
        
        # ===== SECTION PERFORMANCE =====
        box = layout.box()
        box.label(text="Performance", icon='SCENE')
        
        col = box.column(align=True)
        col.prop(self, "max_subdivision")
        col.prop(self, "use_instances")
        col.prop(self, "optimize_mesh")
        
        layout.separator()
        
        # ===== SECTION CHEMINS =====
        box = layout.box()
        box.label(text="Chemins et bibliothèques", icon='FILE_FOLDER')
        
        col = box.column(align=True)
        col.prop(self, "assets_path")
        col.prop(self, "presets_path")
        
        layout.separator()
        
        # ===== SECTION RACCOURCIS =====
        box = layout.box()
        box.label(text="Raccourcis clavier", icon='EVENT_K')
        
        col = box.column(align=True)
        col.prop(self, "enable_shortcuts")
        
        if self.enable_shortcuts:
            col.label(text="Fonctionnalité à venir...", icon='TIME')
        
        layout.separator()
        
        # ===== SECTION EXPÉRIMENTAL =====
        box = layout.box()
        box.label(text="Fonctionnalités expérimentales", icon='EXPERIMENTAL')
        
        col = box.column(align=True)
        col.prop(self, "experimental_features")
        
        if self.experimental_features:
            col.prop(self, "enable_ai_generation")
            col.label(text="⚠ Attention : Ces fonctionnalités peuvent être instables", icon='ERROR')
        
        layout.separator()
        
        # ===== BOUTONS D'ACTION =====
        box = layout.box()
        box.label(text="Actions", icon='SETTINGS')
        
        row = box.row(align=True)
        row.operator("house.reset_preferences", icon='FILE_REFRESH')
        row.operator("house.export_preferences", icon='EXPORT')
        row.operator("house.import_preferences", icon='IMPORT')
        
        layout.separator()
        
        # ===== FOOTER =====
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Support & Documentation", icon='QUESTION')
        col.operator("wm.url_open", text="Documentation", icon='URL').url = "https://github.com/mvaertan/house"
        col.operator("wm.url_open", text="Signaler un bug", icon='URL').url = "https://github.com/mvaertan/house/issues"


# ============================================================
# OPÉRATEURS POUR LES PRÉFÉRENCES
# ============================================================

class HOUSE_OT_reset_preferences(bpy.types.Operator):
    """Réinitialise toutes les préférences aux valeurs par défaut"""
    bl_idname = "house.reset_preferences"
    bl_label = "Réinitialiser les préférences"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Récupérer les préférences
        prefs = context.preferences.addons[__package__].preferences
        
        # Réinitialiser aux valeurs par défaut
        prefs.property_unset("default_units")
        prefs.property_unset("auto_save")
        prefs.property_unset("show_tips")
        prefs.property_unset("debug_mode")
        prefs.property_unset("default_style")
        prefs.property_unset("auto_apply_materials")
        prefs.property_unset("create_collection")
        prefs.property_unset("ui_scale")
        prefs.property_unset("show_advanced_by_default")
        prefs.property_unset("max_subdivision")
        prefs.property_unset("use_instances")
        prefs.property_unset("optimize_mesh")
        prefs.property_unset("experimental_features")
        prefs.property_unset("enable_ai_generation")
        
        self.report({'INFO'}, "Préférences réinitialisées")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class HOUSE_OT_export_preferences(bpy.types.Operator):
    """Exporte les préférences dans un fichier"""
    bl_idname = "house.export_preferences"
    bl_label = "Exporter les préférences"
    bl_options = {'REGISTER'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    
    def execute(self, context):
        self.report({'INFO'}, "Fonctionnalité à venir...")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class HOUSE_OT_import_preferences(bpy.types.Operator):
    """Importe les préférences depuis un fichier"""
    bl_idname = "house.import_preferences"
    bl_label = "Importer les préférences"
    bl_options = {'REGISTER'}
    
    filepath: StringProperty(subtype='FILE_PATH')
    
    def execute(self, context):
        self.report({'INFO'}, "Fonctionnalité à venir...")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# ============================================================
# ENREGISTREMENT
# ============================================================

classes = (
    HouseAddonPreferences,
    HOUSE_OT_reset_preferences,
    HOUSE_OT_export_preferences,
    HOUSE_OT_import_preferences,
)


def register():
    """Enregistrement des classes"""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Désenregistrement des classes"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)