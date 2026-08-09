# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Properties Module (BLENDER 4.2+ COMPATIBLE)
#  Copyright (C) 2025 mvaertan
#
#  ✅ CORRIGÉ - Lazy loading de pbr_scanner pour éviter l'erreur _RestrictData
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    FloatProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    StringProperty,
    FloatVectorProperty,
    PointerProperty,
)


_regenerate_pending = False

# ============================================================
# ✅ v1.13 — RÉGÉNÉRATION INCRÉMENTALE (chantier qualité n°5)
#
# Quelle propriété invalide quel DOMAINE du pipeline (les `tags` des
# étapes, voir pipeline.py). Toute propriété ABSENTE de cette carte
# invalide 'all' (reconstruction complète) — le défaut est la
# sécurité, la carte ne liste que les raccourcis PROUVÉS sûrs:
# des réglages qui ne changent ni l'enveloppe, ni les trous des murs.
# ============================================================

PROP_TAGS = {
    # Menuiseries et accessoires de façade (mêmes trous, autres objets)
    'shutter_color': ('joinery',),
    'include_shutters': ('joinery',),
    'window_type': ('joinery',),
    'door_type': ('joinery',),
    # Accessoires de toiture
    'include_gutters': ('roof',),
    'include_chimney': ('roof',),
    'roof_covering': ('roof',),
    'include_roof_windows': ('roof',),
    'num_roof_windows': ('roof',),
    'roof_window_style': ('roof',),
    # Environnement / éclairage
    'include_environment': ('env',),
    'terrain_mode': ('env',), 'parcel_width': ('env',),
    'parcel_length': ('env',), 'parcel_north': ('env',),
    'parcel_slope': ('env',), 'parcel_access': ('env',),
    'house_pos_x': ('env',), 'house_pos_y': ('env',),
    'house_rotation': ('env',), 'sun_hour': ('env',),
    'include_hedge': ('env',), 'include_grass': ('env',),
    'terrain_asset': ('env',),
    'auto_lighting': ('env',),
    # Annexes
    'include_terrace': ('structure',),
    # Intérieurs (structure aussi: la trémie est percée dans les dalles)
    'interior_wall_color': ('interior',),
    'include_electrical': ('interior',),
    'include_interior_lights': ('interior',),
    'include_furnishing': ('interior',),
    'kitchen_asset': ('interior',),
    'bathroom_asset': ('interior',),
    'bed_asset': ('interior',),
    'table_asset': ('interior',),
    'sofa_asset': ('interior',),
    'outlets_per_room': ('interior',),
    'num_bedrooms': ('interior', 'structure'),
    'programme_active': ('interior', 'structure'),
    'programme_cells': ('interior', 'structure'),
    # Les entrées du programme n'agissent que via le bouton Résoudre:
    # aucune étape ne dépend d'elles ('none' ne matche aucun tag)
    'prog_bedrooms': ('none',),
    'prog_bathrooms': ('none',),
    'prog_wc_separate': ('none',),
    'prog_garage': ('none',),
    'prog_surface': ('none',),
    # Slots d'assets et finitions (v1.15)
    'window_asset': ('joinery',),
    'door_asset': ('joinery',),
    'shutter_asset': ('joinery',),
    'tile_asset': ('roof',),
    'wall_finish': ('walls',),
    # tableau d'ouvertures: change les trous → tout
    'use_openings_table': ('all',),
    'ridge_height_target': ('all',),
    'attic_habitable': ('all',),
    'attic_trusses': ('interior',),
    'include_stone_surrounds': ('joinery',),
    'joinery_color': ('joinery',),
    'roof_finish': ('roof',),
}

# Photographie des valeurs de props au dernier build — le callback
# update de Blender ne dit PAS quelle propriété a changé; on diffe.
_LAST_PROPS = {}
_pending_tags = set()


def _prop_value(props, name):
    v = getattr(props, name)
    if isinstance(v, bpy.types.bpy_prop_collection):
        return tuple(
            tuple(_prop_value(item, p.identifier)
                  for p in item.bl_rna.properties
                  if p.identifier not in ('rna_type', 'name'))
            for item in v)
    if isinstance(v, bpy.types.ID):
        try:
            return ("ID", v.name)     # pointeurs d'assets (v1.15)
        except ReferenceError:
            return ("ID", None)
    try:
        return tuple(v)          # vecteurs / couleurs
    except TypeError:
        return v


def _iter_prop_names(props):
    for p in props.bl_rna.properties:
        if p.identifier not in ('rna_type', 'name') and not p.is_readonly:
            yield p.identifier


def update_snapshot(props):
    """Appelé par l'opérateur après chaque build réussi."""
    _LAST_PROPS.clear()
    for n in _iter_prop_names(props):
        _LAST_PROPS[n] = _prop_value(props, n)


def _changed_tags(props):
    """Diffe les props contre le dernier build → tags invalidés."""
    if not _LAST_PROPS:
        return {'all'}
    tags = set()
    for n in _iter_prop_names(props):
        if _LAST_PROPS.get(n) != _prop_value(props, n):
            tags.update(PROP_TAGS.get(n, ('all',)))
    return tags or {'all'}


def _deferred_regenerate():
    """Exécute la régénération hors du contexte restreint du callback update"""
    global _regenerate_pending
    _regenerate_pending = False
    tags = ",".join(sorted(_pending_tags))
    _pending_tags.clear()
    try:
        bpy.ops.house.generate_auto(invalidate=tags)
    except Exception as e:
        print(f"[House] ⚠️ Mise à jour auto échouée: {e}")
    return None  # Ne pas répéter le timer


def regenerate_house(self, context):
    """Callback pour régénérer la maison quand une propriété change

    ✅ FIX: Implémenté (avant: stub 'pass' — la case 'Mise à jour auto'
    ne faisait rien). L'appel d'opérateur est différé via un timer car les
    callbacks update s'exécutent dans un contexte restreint.
    ✅ v1.13: les props changées sont diffées contre le dernier build →
    seuls les domaines touchés sont rejoués (voir PROP_TAGS).
    """
    global _regenerate_pending
    if not getattr(context.scene, 'house_auto_update', False):
        return
    _pending_tags.update(_changed_tags(self))
    if _regenerate_pending:
        return  # Une régénération est déjà planifiée (anti-rafale)
    _regenerate_pending = True
    bpy.app.timers.register(_deferred_regenerate, first_interval=0.1)


def _toggle_viewport_proxy(self, context):
    """✅ v1.13: allègement viewport immédiat (aucune régénération)."""
    try:
        from . import operators_auto
        props = context.scene.house_generator
        coll = bpy.data.collections.get(props.collection_name or "House")
        if coll is not None:
            operators_auto.apply_viewport_proxy(
                coll, context.scene.house_viewport_proxy)
    except Exception as e:
        print(f"[House] ⚠️ Proxy viewport: {e}")


# ✅ FIX: Cache module-level pour les items d'EnumProperty dynamiques.
# Blender ne copie PAS les chaînes retournées par un callback items= ;
# sans référence Python vivante, elles peuvent être libérées pendant
# l'affichage (crash / texte corrompu — bug classique Blender).
_PRESET_ITEMS_CACHE = []

_PRESET_ITEMS_FALLBACK = [
    ('BRICK_RED', "🧱 Briques rouges", "Briques rouges traditionnelles", 'MATERIAL', 0),
    ('BRICK_RED_DARK', "🧱 Briques rouges foncées", "Briques rouges sombres", 'MATERIAL', 1),
    ('BRICK_ORANGE', "🧱 Briques orangées", "Briques orangées/terre cuite", 'MATERIAL', 2),
    ('BRICK_BROWN', "🧱 Briques brunes", "Briques brunes/chocolat", 'MATERIAL', 3),
    ('BRICK_YELLOW', "🧱 Briques jaunes (London)", "Briques jaunes type London", 'MATERIAL', 4),
    ('BRICK_GREY', "🧱 Briques grises modernes", "Briques grises contemporaines", 'MATERIAL', 5),
]


def get_brick_presets_safe(self, context):
    """Wrapper sécurisé pour get_brick_preset_items avec fallback

    ✅ CORRECTION: Lazy loading du scanner + cache des chaînes (voir ci-dessus)
    """
    global _PRESET_ITEMS_CACHE
    try:
        from .materials import pbr_scanner
        _PRESET_ITEMS_CACHE = pbr_scanner.get_brick_preset_items(self, context)
        return _PRESET_ITEMS_CACHE
    except Exception as e:
        print(f"[House] ⚠️ Erreur scan PBR: {e}")

    # Fallback: presets hardcodés si le scanner ne marche pas
    _PRESET_ITEMS_CACHE = list(_PRESET_ITEMS_FALLBACK)
    return _PRESET_ITEMS_CACHE


class HouseOpeningItem(PropertyGroup):
    """✅ TABLEAU D'OUVERTURES: une ligne = une ouverture réelle
    (le brief type mélange baies 2.40×2.15 et fenêtres 1.20×1.40 sur
    la même façade — impossible avec un type/taille unique)."""
    wall: EnumProperty(
        name="Façade",
        items=[('FRONT', "Avant", ""), ('BACK', "Arrière", ""),
               ('LEFT', "Gauche", ""), ('RIGHT', "Droite", "")],
        default='FRONT', update=regenerate_house)
    item_type: EnumProperty(
        name="Type",
        items=[('CASEMENT', "Fenêtre battante", "2 vantaux"),
               ('SLIDING', "Baie coulissante", ""),
               ('FIXED', "Châssis fixe", ""),
               ('DOOR', "Porte", "Porte pleine (entrée/service)")],
        default='CASEMENT', update=regenerate_house)
    width: FloatProperty(name="Largeur", default=1.20, min=0.4, max=6.0,
                         update=regenerate_house)
    height: FloatProperty(name="Hauteur", default=1.40, min=0.4, max=3.0,
                          update=regenerate_house)
    sill: FloatProperty(name="Allège", description="Hauteur du bas de "
                        "la fenêtre depuis le sol de l'étage",
                        default=0.90, min=0.0, max=2.0,
                        update=regenerate_house)
    pos: FloatProperty(name="Position", description="Centre de "
                       "l'ouverture le long du mur (m depuis le coin)",
                       default=2.0, min=0.2, max=60.0,
                       update=regenerate_house)
    floor: IntProperty(name="Étage", default=0, min=0, max=4,
                       update=regenerate_house)


class HouseGeneratorProperties(PropertyGroup):
    """Propriétés pour le générateur de maison"""
    
    # ============================================================
    # MODE DE GÉNÉRATION
    # ============================================================
    
    generation_mode: EnumProperty(
        name="Mode",
        description="Mode de génération de la maison",
        items=[
            ('AUTO', "Automatique", "Génération automatique selon des critères", 'AUTO', 0),
            ('MANUAL', "Plan Manuel", "Construction à partir d'un plan 2D", 'GREASEPENCIL', 1),
        ],
        default='AUTO'
    )
    
    house_preset: EnumProperty(
        name="Preset régional",
        description="Applique une silhouette régionale complète "
                    "(dimensions, toit, matériaux, options)",
        items=[
            ('NONE', "— Aucun —", "Réglages manuels"),
            ('LONGERE', "Longère", "Volume long et bas, toit GABLE 45°, "
                                   "lucarnes, briques brunes"),
            ('CHALET', "Chalet", "Pignon en façade, débords profonds, "
                                 "balcon bois, 2 niveaux"),
            ('BASTIDE', "Bastide", "Croupe provençale douce, enduit clair, "
                                   "volets, plain-pied généreux"),
            ('MEULIERE', "Meulière", "Étage + mansarde, lucarnes, "
                                     "briques rouges, grille de meulière"),
        ],
        default='NONE',
    )

    # ============================================================
    # DIMENSIONS GÉNÉRALES
    # ============================================================
    
    house_width: FloatProperty(
        name="Largeur",
        description="Largeur de la maison (axe X)",
        default=10.0,
        min=3.0,
        max=50.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    house_length: FloatProperty(
        name="Longueur",
        description="Longueur de la maison (axe Y)",
        default=12.0,
        min=3.0,
        max=50.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    num_floors: IntProperty(
        name="Nombre d'étages",
        description="Nombre d'étages de la maison",
        default=1,
        min=1,
        max=4,
        update=regenerate_house
    )
    
    floor_height: FloatProperty(
        name="Hauteur d'étage",
        description="Hauteur d'un étage",
        default=2.7,
        min=2.0,
        max=4.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    wall_thickness: FloatProperty(
        name="Épaisseur murs",
        description="Épaisseur des murs extérieurs",
        default=0.3,
        min=0.1,
        max=0.6,
        unit='LENGTH',
        update=regenerate_house
    )
    
    # ============================================================
    # STYLE ARCHITECTURAL
    # ============================================================
    
    detail_level: EnumProperty(
        name="Niveau de détail",
        description="Budget de détail constructif de la génération",
        items=[
            ('DRAFT', "Brouillon", "Rapide: sans charpente visible, "
                                   "voilages, quincaillerie ni végétation"),
            ('NORMAL', "Normal", "Le niveau de détail standard"),
            ('PHOTO', "Photo", "Tout le réel: appuis débordants, doublis "
                               "d'égout, arêtes adoucies, volets "
                               "entrouverts variés"),
        ],
        default='NORMAL',
        update=regenerate_house
    )

    architectural_style: EnumProperty(
        name="Style",
        description="Style architectural de la maison",
        items=[
            ('MODERN', "Moderne", "Architecture contemporaine minimaliste"),
            ('TRADITIONAL', "Traditionnel", "Style classique européen"),
            ('MEDITERRANEAN', "Méditerranéen", "Style villa du sud"),
            ('CONTEMPORARY', "Contemporain", "Style moderne mixte"),
            ('ASIAN', "Asiatique", "Style japonais/chinois"),
        ],
        default='TRADITIONAL',
        update=regenerate_house
    )
    
    # ============================================================
    # TOIT
    # ============================================================
    
    roof_type: EnumProperty(
        name="Type de toit",
        description="Forme du toit",
        items=[
            ('GABLE', "Pignon", "Toit à deux pentes (standard)"),
            ('HIP', "Croupe", "Toit à quatre pentes"),
            ('SKELETON', "Auto (squelette)",
             "Croupe DÉDUITE du plan par squelette droit — emprise "
             "quelconque (maison + ailes en L/T/U natifs, plain-pied)"),
            ('FLAT', "Plat", "Toit-terrasse"),
            ('GAMBREL', "Mansarde", "Toit à combles"),
            ('SHED', "Monopente", "Toit à une seule pente"),
        ],
        default='GABLE',
        update=regenerate_house
    )
    
    roof_pitch: FloatProperty(
        name="Pente du toit",
        description="Angle de pente du toit en degrés",
        default=35.0,
        min=5.0,
        max=60.0,
        # ✅ FIX: subtype='ANGLE' supprimé — il faisait stocker des radians et
        # afficher ~2005° dans l'UI alors que tout le code attend des degrés
        update=regenerate_house
    )
    
    roof_overhang: FloatProperty(
        name="Débord de toit",
        description="Longueur du débord du toit",
        default=0.5,
        min=0.0,
        max=2.0,
        unit='LENGTH',
        update=regenerate_house
    )

    # ✅ NOUVEAU: Couverture du toit
    roof_covering: EnumProperty(
        name="Couverture",
        description="Revêtement du toit",
        items=[
            ('NONE', "Lisse", "Dalle simple (rapide)"),
            ('TILES', "Tuiles", "Tuiles mécaniques instanciées (GABLE/monopente)"),
        ],
        default='NONE',
        update=regenerate_house
    )

    tile_color: FloatVectorProperty(
        name="Couleur tuiles",
        description="Couleur des tuiles de couverture",
        subtype='COLOR',
        size=3,
        default=(0.34, 0.115, 0.062),  # Terre cuite profonde (AgX)
        min=0.0,
        max=1.0,
        update=regenerate_house
    )

    include_gutters: BoolProperty(
        name="Gouttières",
        description="Ajouter gouttières et descentes le long des égouts",
        default=True,
        update=regenerate_house
    )

    include_chimney: BoolProperty(
        name="Cheminée",
        description="Ajouter une cheminée en brique traversant le toit",
        default=False,
        update=regenerate_house
    )

    include_roof_windows: BoolProperty(
        name="Fenêtres de toit",
        description="Fenêtres de toit (type velux) sur le pan visible "
                    "(toit GABLE)",
        default=False,
        update=regenerate_house
    )

    roof_window_style: EnumProperty(
        name="Style de fenêtre de toit",
        items=[
            ('VELUX', "Fenêtre de toit (velux)", "Châssis vitré dans le pan"),
            ('LUCARNE', "Lucarne jacobine", "Lucarne à 2 pans avec fenêtre "
                                            "verticale (toit GABLE)"),
        ],
        default='VELUX',
        update=regenerate_house
    )

    num_roof_windows: IntProperty(
        name="Nombre de fenêtres de toit",
        description="Nombre de fenêtres de toit sur le pan",
        default=2,
        min=1,
        max=4,
        update=regenerate_house
    )

    shutter_color: FloatVectorProperty(
        name="Couleur volets",
        description="Couleur des volets battants",
        subtype='COLOR',
        size=3,
        default=(0.30, 0.32, 0.34),
        min=0.0, max=1.0,
        update=regenerate_house
    )

    include_shutters: BoolProperty(
        name="Volets",
        description="Ajouter des volets battants de part et d'autre des fenêtres",
        default=False,
        update=regenerate_house
    )
    
    # ============================================================
    # FONDATIONS
    # ============================================================
    
    foundation_height: FloatProperty(
        name="Hauteur fondations",
        description="Hauteur visible des fondations",
        default=0.5,
        min=0.0,
        max=2.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    # ============================================================
    # FENÊTRES
    # ============================================================
    
    window_width: FloatProperty(
        name="Largeur fenêtre",
        description="Largeur standard des fenêtres",
        default=1.2,
        min=0.6,
        max=3.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    window_height: FloatProperty(
        name="Hauteur fenêtre",
        description="Hauteur standard des fenêtres",
        default=1.4,
        min=0.8,
        max=2.5,
        unit='LENGTH',
        update=regenerate_house
    )
    
    window_height_ratio: FloatProperty(
        name="Ratio hauteur fenêtre",
        description="Ratio de hauteur par rapport à la hauteur de l'étage (0.4 = 40%)",
        default=0.4,
        min=0.2,
        max=0.8,
        update=regenerate_house
    )
    
    window_type: EnumProperty(
        name="Type fenêtre",
        description="Type de fenêtre par défaut",
        items=[
            ('CASEMENT', "Battant", "Fenêtre à battant (standard européen)"),
            ('SLIDING', "Coulissante", "Fenêtre coulissante horizontale"),
            ('FIXED', "Fixe", "Fenêtre fixe (ne s'ouvre pas)"),
            ('DOUBLE_HUNG', "Guillotine", "Fenêtre à guillotine (style américain)"),
            ('ARCHED', "Cintrée", "Fenêtre avec arc en haut"),
            ('PICTURE', "Panoramique", "Grande baie vitrée"),
        ],
        default='CASEMENT',
        update=regenerate_house
    )
    
    window_quality: EnumProperty(
        name="Qualité fenêtres",
        description="Niveau de détail des fenêtres",
        items=[
            ('LOW', "Basse", "Peu de détails, rapide (pour grandes scènes)", 0),
            ('MEDIUM', "Moyenne", "Bon équilibre détails/performance", 1),
            ('HIGH', "Haute", "Maximum de détails (pour rendus finaux)", 2),
        ],
        default='MEDIUM',
        update=regenerate_house
    )
    
    num_windows_front: IntProperty(
        name="Fenêtres façade",
        description="Nombre de fenêtres sur la façade avant",
        default=3,
        min=0,
        max=10,
        update=regenerate_house
    )
    
    num_windows_side: IntProperty(
        name="Fenêtres côtés",
        description="Nombre de fenêtres sur les côtés",
        default=2,
        min=0,
        max=10,
        update=regenerate_house
    )
    
    num_windows_back: IntProperty(
        name="Fenêtres arrière",
        description="Nombre de fenêtres sur la façade arrière",
        default=2,
        min=0,
        max=10,
        update=regenerate_house
    )
    
    
    # ============================================================
    # PORTES
    # ============================================================
    
    # ✅ FIX: 'door_width' supprimé — c'était un doublon jamais lu de
    # 'front_door_width' (deux propriétés indépendantes désynchronisées)
    front_door_width: FloatProperty(
        name="Largeur porte entrée",
        description="Largeur de la porte d'entrée",
        default=1.0,
        min=0.8,
        max=2.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    door_height: FloatProperty(
        name="Hauteur porte",
        description="Hauteur de la porte d'entrée",
        default=2.1,
        min=1.8,
        max=2.5,
        unit='LENGTH',
        update=regenerate_house
    )
    
    door_type: EnumProperty(
        name="Type porte",
        description="Type de porte d'entrée",
        items=[
            ('SINGLE', "Simple", "Porte simple battant"),
            ('DOUBLE', "Double", "Porte double battant"),
            ('SLIDING', "Coulissante", "Porte coulissante"),
            ('FRENCH', "Française", "Porte-fenêtre vitrée"),
        ],
        default='SINGLE',
        update=regenerate_house
    )
    
    door_quality: EnumProperty(
        name="Qualité portes",
        description="Niveau de détail des portes",
        items=[
            ('LOW', "Basse", "Peu de détails", 0),
            ('MEDIUM', "Moyenne", "Bon équilibre", 1),
            ('HIGH', "Haute", "Maximum de détails", 2),
        ],
        default='MEDIUM',
        update=regenerate_house
    )
    
    # ============================================================
    # GARAGE
    # ============================================================
    
    # ✅ FIX: 'add_garage' supprimé — doublon jamais lu de 'include_garage'
    include_garage: BoolProperty(
        name="Inclure garage",
        description="Inclure un garage",
        default=False,
        update=regenerate_house
    )
    
    garage_width: FloatProperty(
        name="Largeur garage",
        description="Largeur du garage",
        default=3.0,
        min=2.5,
        max=6.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    garage_depth: FloatProperty(
        name="Profondeur garage",
        description="Profondeur du garage",
        default=5.0,
        min=4.0,
        max=8.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    garage_position: EnumProperty(
        name="Position garage",
        description="Position du garage par rapport à la maison",
        items=[
            ('LEFT', "Gauche", "Garage sur le côté gauche"),
            ('RIGHT', "Droite", "Garage sur le côté droit"),
            ('FRONT', "Avant", "Garage en façade"),
            ('ATTACHED', "Attaché", "Garage intégré à la maison"),
        ],
        default='LEFT',
        update=regenerate_house
    )
    
    num_bedrooms: IntProperty(
        name="Chambres",
        description="Nombre de chambres derrière le refend (la pièce de "
                    "vie reste côté entrée)",
        default=2,
        min=1,
        max=4,
        update=regenerate_house
    )

    # ============================================================
    # ✅ v1.14 — MODE PROGRAMME (chantier n°6): l'utilisateur décrit
    # le BESOIN, le solveur (programme.py) résout l'emprise et la
    # distribution. Les prog_* n'agissent que via le bouton Résoudre.
    # ============================================================
    prog_bedrooms: IntProperty(
        name="Chambres (programme)",
        description="Nombre de chambres du programme fonctionnel",
        default=3, min=1, max=4
    )
    prog_bathrooms: IntProperty(
        name="Salles de bain (programme)",
        description="Nombre de salles de bain du programme",
        default=1, min=1, max=2
    )
    prog_wc_separate: BoolProperty(
        name="WC séparé",
        description="WC indépendant de la salle de bain",
        default=True
    )
    prog_garage: EnumProperty(
        name="Garage (programme)",
        description="Garage accolé (aile droite)",
        items=[
            ('NONE', "Sans garage", "Pas de garage"),
            ('SINGLE', "Garage simple", "Une voiture (3.6m)"),
            ('DOUBLE', "Garage double", "Deux voitures (6.0m)"),
        ],
        default='SINGLE'
    )
    prog_surface: FloatProperty(
        name="Surface cible",
        description="Surface au sol visée en m² (0 = automatique)",
        default=0.0, min=0.0, max=250.0
    )
    programme_active: BoolProperty(
        name="Programme actif",
        description="La distribution intérieure suit les cellules "
                    "résolues par le programme",
        default=False,
        update=regenerate_house
    )
    programme_cells: StringProperty(
        name="Cellules du programme",
        description="Largeurs des cellules de la bande arrière "
                    "(m, séparées par des virgules) — posé par le solveur",
        default="",
        update=regenerate_house
    )

    # ============================================================
    # ✅ v1.15 — SLOTS D'ASSETS (chantier n°7): optionnels, JAMAIS
    # obligatoires. Slot vide → menuiserie PROCÉDURALE habituelle.
    # ============================================================
    window_asset: bpy.props.PointerProperty(
        name="Asset fenêtre",
        description="Objet à instancier à la place des fenêtres "
                    "procédurales (mis à l'échelle de chaque ouverture); "
                    "vide = fenêtres procédurales",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(),
        update=regenerate_house
    )
    door_asset: bpy.props.PointerProperty(
        name="Asset porte",
        description="Objet à instancier à la place des portes "
                    "procédurales; vide = portes procédurales",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(),
        update=regenerate_house
    )
    shutter_asset: bpy.props.PointerProperty(
        name="Asset volet",
        description="Objet utilisé pour chaque battant de volet "
                    "(articulation 'fermeture' conservée); "
                    "vide = volets procéduraux",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(),
        update=regenerate_house
    )
    tile_asset: bpy.props.PointerProperty(
        name="Asset tuile",
        description="Mesh utilisé comme tuile maître (instancié sur "
                    "toute la couverture); vide = tuile canal procédurale",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(),
        update=regenerate_house
    )

    # ✅ v1.15 — FINITIONS PROCÉDURALES au choix (en plus de la couleur
    # unie et des textures PBR)
    wall_finish: EnumProperty(
        name="Finition murale",
        description="Matière procédurale des murs enduits",
        items=[
            ('AUTO', "Auto (taloché)", "Enduit taloché fin (défaut)"),
            ('CREPI_FIN', "Crépi fin", "Enduit taloché, grain serré"),
            ('CREPI_GROS', "Crépi projeté", "Gros grain projeté, relief net"),
            ('LISSE', "Peinture lisse", "Peinture mate unie (sans grain)"),
            ('PIERRE', "Pierre vue", "Calcaire appareillé à pierre vue "
                                     "(procédural) — moellons plus "
                                     "sombres au soubassement"),
        ],
        default='AUTO',
        update=regenerate_house
    )
    roof_finish: EnumProperty(
        name="Finition de couverture",
        description="Matière procédurale des tuiles",
        items=[
            ('AUTO', "Auto (terre cuite)", "Tuile terre cuite (défaut)"),
            ('TERRE_CUITE', "Terre cuite", "Variation de cuisson par tuile"),
            ('ARDOISE', "Ardoise", "Gris bleuté satiné, feuilletage"),
            ('BETON', "Béton", "Tuile béton grise mate"),
            ('PLATE', "Tuile plate", "Tuile plate terre cuite vieillie, "
                                     "tons mélangés (longères/bourgogne)"),
        ],
        default='AUTO',
        update=regenerate_house
    )

    # ✅ ÉLECTRICITÉ (NF C 15-100): prises + interrupteurs
    include_electrical: BoolProperty(
        name="Électricité",
        description="Prises de courant (axe 0.25m) et interrupteurs "
                    "(1.10m) sur les parois intérieures — NF C 15-100",
        default=False,
        update=regenerate_house
    )
    outlets_per_room: IntProperty(
        name="Prises par pièce",
        description="Nombre de prises par pièce (le séjour en reçoit "
                    "deux de plus, minimum normatif 5)",
        default=3, min=1, max=8,
        update=regenerate_house
    )

    # ✅ PIERRE: encadrements de taille + chaînages (géométrie réelle)
    include_stone_surrounds: BoolProperty(
        name="Encadrements pierre",
        description="Jambages, linteaux et appuis en pierre de taille "
                    "autour de chaque ouverture + chaînages d'angle",
        default=False, update=regenerate_house)
    joinery_color: FloatVectorProperty(
        name="Couleur menuiseries",
        description="Teinte des dormants et ouvrants (RAL) — les "
                    "volets ont leur propre couleur",
        subtype='COLOR', size=3, min=0.0, max=1.0,
        default=(0.95, 0.95, 0.95),   # blanc historique
        update=regenerate_house)

    # ✅ VOLUMÉTRIE: faîtage cible + combles aménagés
    ridge_height_target: FloatProperty(
        name="Faîtage cible",
        description="Hauteur de faîtage VISÉE depuis le sol (0 = la "
                    "pente pilote) — la pente est dérivée",
        default=0.0, min=0.0, max=15.0, update=regenerate_house)
    attic_habitable: BoolProperty(
        name="Combles aménagés",
        description="Niveau habitable sous rampants: plancher, "
                    "jambettes 1m, plafond 2.40 sous entrait, escalier "
                    "(GABLE, plain-pied + combles)",
        default=False, update=regenerate_house)
    attic_trusses: BoolProperty(
        name="Fermes apparentes",
        description="Entraits de charpente visibles dans les combles",
        default=False, update=regenerate_house)

    # ✅ TABLEAU D'OUVERTURES (prime sur le calcul automatique)
    use_openings_table: BoolProperty(
        name="Tableau d'ouvertures",
        description="Les lignes du tableau REMPLACENT les fenêtres et "
                    "portes automatiques (types, tailles, allèges et "
                    "positions libres, par façade)",
        default=False, update=regenerate_house)
    openings_table: bpy.props.CollectionProperty(type=HouseOpeningItem)
    openings_table_index: IntProperty(default=0)

    # ✅ TERRAIN & IMPLANTATION (parcelle, nord, soleil, pente)
    terrain_mode: EnumProperty(
        name="Terrain",
        description="Mode de terrain sous la maison",
        items=[
            ('LEGACY', "Auto simple", "Terrain circulaire historique"),
            ('AUTO', "Parcelle", "Parcelle paramétrique: dimensions, "
                                 "nord, pente, accès, haie en limite"),
            ('CUSTOM', "Mon terrain", "Votre mesh (slot terrain) — "
                                      "House garde soleil et implantation"),
        ],
        default='LEGACY', update=regenerate_house)
    parcel_width: FloatProperty(
        name="Largeur parcelle", default=40.0, min=10.0, max=300.0,
        update=regenerate_house)
    parcel_length: FloatProperty(
        name="Longueur parcelle", default=60.0, min=10.0, max=300.0,
        update=regenerate_house)
    parcel_north: FloatProperty(
        name="Nord (°)", description="Angle du nord par rapport à "
        "l'arrière de la maison (boussole)", default=0.0,
        min=-180.0, max=180.0, update=regenerate_house)
    parcel_slope: FloatProperty(
        name="Pente (%)", description="Pente du terrain naturel — la "
        "maison pose sur une plateforme avec talus",
        default=0.0, min=0.0, max=15.0, update=regenerate_house)
    parcel_access: EnumProperty(
        name="Accès", description="Côté d'arrivée de l'allée",
        items=[('FRONT', "Avant", ""), ('BACK', "Arrière", ""),
               ('LEFT', "Gauche", ""), ('RIGHT', "Droite", "")],
        default='FRONT', update=regenerate_house)
    house_pos_x: FloatProperty(
        name="Position X", description="Position de la maison sur la "
        "parcelle (depuis le centre)", default=0.0, min=-120.0,
        max=120.0, update=regenerate_house)
    house_pos_y: FloatProperty(
        name="Position Y", default=0.0, min=-120.0, max=120.0,
        update=regenerate_house)
    house_rotation: FloatProperty(
        name="Orientation (°)", description="Rotation de la maison "
        "sur la parcelle", default=0.0, min=-180.0, max=180.0,
        update=regenerate_house)
    sun_hour: FloatProperty(
        name="Heure solaire", description="Position du soleil (6-21h, "
        "course est→ouest selon le nord)", default=15.0, min=6.0,
        max=21.0, update=regenerate_house)
    include_hedge: BoolProperty(
        name="Haie en limite", default=True, update=regenerate_house)
    include_grass: BoolProperty(
        name="Herbe", default=True, update=regenerate_house)
    terrain_asset: bpy.props.PointerProperty(
        name="Slot terrain", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)

    # ✅ AMÉNAGEMENT (rendu client): éclairage, cuisine, SdB, mobilier
    include_interior_lights: BoolProperty(
        name="Éclairage intérieur",
        description="Suspensions chaudes (2700K) dans chaque pièce",
        default=False, update=regenerate_house)
    include_furnishing: BoolProperty(
        name="Aménagement",
        description="Cuisine, sanitaires et mobilier — équipement de "
                    "base paramétrique, remplacé par vos assets si les "
                    "slots sont remplis",
        default=False, update=regenerate_house)
    kitchen_asset: bpy.props.PointerProperty(
        name="Asset cuisine", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)
    bathroom_asset: bpy.props.PointerProperty(
        name="Asset salle de bain", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)
    bed_asset: bpy.props.PointerProperty(
        name="Asset lit", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)
    table_asset: bpy.props.PointerProperty(
        name="Asset table", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)
    sofa_asset: bpy.props.PointerProperty(
        name="Asset canapé", type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
        and "house_step" not in obj.keys(), update=regenerate_house)

    interior_wall_color: FloatVectorProperty(
        name="Couleur murs intérieurs",
        description="Peinture du doublage intérieur des murs extérieurs",
        subtype='COLOR',
        size=3,
        default=(0.87, 0.85, 0.80),
        min=0.0, max=1.0,
        update=regenerate_house
    )

    include_interiors: BoolProperty(
        name="Intérieurs",
        description="Plafonds en plâtre, cloisons de distribution avec "
                    "passages de porte, sols parquet",
        default=True,
        update=regenerate_house
    )

    # ============================================================
    # ✅ MULTI-VOLUMES: AILE (plans en L)
    # ============================================================

    include_wing: BoolProperty(
        name="Inclure une aile (plan en L)",
        description="Second volume habitable accolé à une façade "
                    "(plain-pied, toit à noues raccordé au toit principal)",
        default=False,
        update=regenerate_house
    )

    wing_side: EnumProperty(
        name="Côté de l'aile",
        description="Façade sur laquelle l'aile est accolée",
        items=[
            ('FRONT', "Avant", "Aile en avancée sur la façade avant"),
            ('BACK', "Arrière", "Aile sur la façade arrière"),
            ('LEFT', "Gauche", "Aile sur le pignon gauche"),
            ('RIGHT', "Droite", "Aile sur le pignon droit"),
        ],
        default='FRONT',
        update=regenerate_house
    )

    wing_width: FloatProperty(
        name="Largeur aile",
        description="Largeur de l'aile le long de la façade",
        default=4.5,
        min=2.0,
        max=12.0,
        unit='LENGTH',
        update=regenerate_house
    )

    wing_depth: FloatProperty(
        name="Profondeur aile",
        description="Avancée de l'aile devant la façade",
        default=4.0,
        min=1.5,
        max=10.0,
        unit='LENGTH',
        update=regenerate_house
    )

    wing_offset: FloatProperty(
        name="Position aile",
        description="Décalage de l'aile le long de la façade "
                    "(0 = collée au coin gauche)",
        default=0.0,
        min=0.0,
        max=20.0,
        unit='LENGTH',
        update=regenerate_house
    )

    wing_floors: IntProperty(
        name="Étages de l'aile",
        description="Nombre d'étages de l'aile (limité aux étages de la "
                    "maison — noues seulement à égouts alignés)",
        default=1,
        min=1,
        max=3,
        update=regenerate_house
    )

    include_wing2: BoolProperty(
        name="Seconde aile (plans en T/U)",
        description="Deuxième volume accolé — permet les plans en T et en U",
        default=False,
        update=regenerate_house
    )

    wing2_side: EnumProperty(
        name="Côté aile 2",
        description="Façade de la seconde aile",
        items=[
            ('FRONT', "Avant", ""),
            ('BACK', "Arrière", ""),
            ('LEFT', "Gauche", ""),
            ('RIGHT', "Droite", ""),
        ],
        default='BACK',
        update=regenerate_house
    )

    wing2_width: FloatProperty(
        name="Largeur aile 2",
        default=4.0, min=2.0, max=12.0, unit='LENGTH',
        update=regenerate_house
    )

    wing2_depth: FloatProperty(
        name="Profondeur aile 2",
        default=3.5, min=1.5, max=10.0, unit='LENGTH',
        update=regenerate_house
    )

    wing2_offset: FloatProperty(
        name="Position aile 2",
        default=0.0, min=0.0, max=20.0, unit='LENGTH',
        update=regenerate_house
    )

    wing2_floors: IntProperty(
        name="Étages de l'aile 2",
        default=1, min=1, max=3,
        update=regenerate_house
    )

    # ============================================================
    # BALCONS / TERRASSES
    # ============================================================
    
    # ✅ FIX: 'add_balcony' et 'add_terrace' supprimés — doublons jamais lus
    # de 'include_balcony' / 'include_terrace'
    include_balcony: BoolProperty(
        name="Inclure balcon",
        description="Inclure un balcon aux étages supérieurs",
        default=False,
        update=regenerate_house
    )

    include_terrace: BoolProperty(
        name="Inclure terrasse",
        description="Inclure une terrasse au rez-de-chaussée",
        default=False,
        update=regenerate_house
    )
    
    balcony_width: FloatProperty(
        name="Largeur balcon",
        description="Largeur du balcon",
        default=2.0,
        min=1.0,
        max=4.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    balcony_depth: FloatProperty(
        name="Profondeur balcon",
        description="Profondeur du balcon",
        default=1.2,
        min=0.8,
        max=2.0,
        unit='LENGTH',
        update=regenerate_house
    )
    
    # ✅ FIX: 'global_quality' supprimée — 4e molette de qualité qui ne
    # pilotait rien (window/door/brick_3d_quality existent déjà)

    # ============================================================
    # MATÉRIAUX ET TEXTURES
    # ============================================================
    
    use_materials: BoolProperty(
        name="Utiliser matériaux",
        description="Appliquer automatiquement des matériaux",
        default=True,
        update=regenerate_house
    )
    
    # ============================================================
    # PROPRIÉTÉS AJOUTÉES : CONSTRUCTION MURS BRIQUES 3D
    # ============================================================
    
    wall_construction_type: EnumProperty(
        name="Type de construction murs",
        description="Méthode de construction des murs",
        items=[
            ('SIMPLE', "Mur simple", "Mur simple avec matériau shader", 'SHADING_TEXTURE', 0),
            ('BRICK_3D', "Briques 3D", "Mur avec vraies briques 3D géométriques", 'MESH_CUBE', 1),
        ],
        default='SIMPLE',
        update=regenerate_house
    )
    
    brick_3d_quality: EnumProperty(
        name="Qualité briques 3D",
        description="Niveau de détail des briques 3D",
        items=[
            ('LOW', "Basse", "Instancing simple (rapide)", 0),
            ('MEDIUM', "Moyenne", "Instancing avec briques détaillées", 1),
            ('HIGH', "Haute", "Géométrie complète (lourd!)", 2),
        ],
        default='MEDIUM',
        update=regenerate_house
    )
    
    brick_material_mode: EnumProperty(
        name="Mode matériau briques 3D",
        description="Comment appliquer le matériau aux briques",
        items=[
            ('COLOR', "Couleur unie", "Utiliser une couleur unie", 0),
            ('PRESET', "Preset", "Utiliser un preset de matériau", 1),
            ('CUSTOM', "Personnalisé", "Utiliser matériau custom", 2),
        ],
        default='PRESET',
        update=regenerate_house
    )
    
    brick_preset_type: EnumProperty(
        name="Preset briques",
        description="Type de briques à utiliser",
        items=get_brick_presets_safe,
        update=regenerate_house
    )
    
    brick_solid_color: FloatVectorProperty(
        name="Couleur briques 3D",
        description="Couleur pour les briques 3D",
        subtype='COLOR',
        size=4,
        default=(0.65, 0.25, 0.15, 1.0),
        update=regenerate_house,
        min=0.0,
        max=1.0
    )
    
    brick_custom_material: PointerProperty(
        name="Matériau custom",
        description="Matériau personnalisé pour briques 3D",
        type=bpy.types.Material,
        update=regenerate_house
    )

    # ✅ NOUVEAU MOTEUR: Geometry Nodes (1 objet au lieu de milliers)
    brick_use_geonodes: BoolProperty(
        name="Moteur Geometry Nodes",
        description=(
            "Instancie les briques via Geometry Nodes: 1 seul objet au lieu "
            "de milliers, viewport fluide, mémoire minimale. "
            "Même rendu visuel que le moteur classique"
        ),
        default=False,
        update=regenerate_house
    )

    # ✅ NOUVELLE PROPRIÉTÉ: Couleur du mortier personnalisable
    mortar_color: FloatVectorProperty(
        name="Couleur mortier",
        description="Couleur du mortier entre les briques (pour briques 3D)",
        subtype='COLOR',
        size=4,
        default=(0.92, 0.92, 0.90, 1.0),  # Blanc cassé / crème clair (très contrasté avec briques)
        min=0.0,
        max=1.0,
        update=regenerate_house
    )

    # ✅ NOUVELLE PROPRIÉTÉ: Pattern d'appareillage des briques
    brick_bonding_pattern: EnumProperty(
        name="Appareillage briques",
        description="Pattern d'arrangement des briques (bonding pattern)",
        items=[
            ('RUNNING', "Running Bond (Quinconce)", "Pattern standard avec offset de demi-brique", 0),
            ('STACK', "Stack Bond (Empilé)", "Briques alignées verticalement (moderne)", 1),
            ('FLEMISH', "Flemish Bond", "Alternance headers/stretchers (traditionnel)", 2),
            ('ENGLISH', "English Bond", "Rangées alternées headers/stretchers", 3),
        ],
        default='RUNNING',
        update=regenerate_house
    )

    # ✅ FIX: 'wall_material_type', 'wall_brick_quality' et 'wall_brick_color'
    # supprimées — 8 styles et 3 qualités affichés que le générateur ne
    # lisait JAMAIS (les murs simples utilisent wall_material_color)


    # ✅ FIX: 'use_geometry_bricks' et 'geometry_brick_quality' supprimés —
    # doublons jamais lus de 'wall_construction_type' et 'brick_3d_quality'
    # (trois sources de vérité concurrentes pour le même réglage)

    wall_material_color: FloatVectorProperty(
        name="Couleur murs (legacy)",
        description="Couleur des murs (ancienne propriété, conservée pour compatibilité)",
        subtype='COLOR',
        default=(0.9, 0.9, 0.85),
        min=0.0,
        max=1.0,
        size=3,
        update=regenerate_house
    )
    
    
    roof_material_color: FloatVectorProperty(
        name="Couleur toit",
        description="Couleur du toit",
        subtype='COLOR',
        default=(0.3, 0.2, 0.15),
        min=0.0,
        max=1.0,
        size=3,
        update=regenerate_house
    )
    
    floor_material_color: FloatVectorProperty(
        name="Couleur sol",
        description="Couleur du sol",
        subtype='COLOR',
        default=(0.7, 0.6, 0.5),
        min=0.0,
        max=1.0,
        size=3,
        update=regenerate_house
    )
    
    # ============================================================
    # MODE MANUEL
    # ============================================================
    
    exterior_wall_thickness: FloatProperty(
        name="Mur extérieur",
        description="Épaisseur des murs extérieurs",
        default=0.25,
        min=0.15,
        max=0.60,
        unit='LENGTH',
        precision=3
    )
    
    
    
    
    
    
    plan_image_path: StringProperty(
        name="Chemin du plan",
        description="Chemin vers l'image du plan 2D",
        default="",
        subtype='FILE_PATH'
    )
    
    plan_scale: FloatProperty(
        name="Échelle du plan",
        description="Échelle du plan importé (mètres par pixel)",
        default=0.01,
        min=0.001,
        max=1.0,
        precision=4
    )
    
    plan_opacity: FloatProperty(
        name="Opacité du plan",
        description="Opacité de l'image de référence",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )
    
    # ============================================================
    # OPTIONS AVANCÉES
    # ============================================================
    
    include_environment: BoolProperty(
        name="Environnement de rendu",
        description="Terrain gazonné, allée, arbres, ciel physique Nishita "
                    "et caméra cadrée automatiquement",
        default=False,
        update=regenerate_house
    )

    auto_lighting: BoolProperty(
        name="Éclairage automatique",
        description="Ajouter des lumières à la scène",
        default=False,
        update=regenerate_house
    )
    
    collection_name: StringProperty(
        name="Nom collection",
        description="Nom de la collection où créer la maison",
        default="House",
        update=regenerate_house
    )
    
    
    
    random_seed: IntProperty(
        name="Seed aléatoire",
        description="Seed pour la génération procédurale (0 = aléatoire)",
        default=0,
        min=0,
        max=999999,
        update=regenerate_house
    )
    
    advanced_mode: BoolProperty(
        name="Mode avancé",
        description="Afficher les options avancées et le scripting Python",
        default=False
    )
    
    python_script: StringProperty(
        name="Script Python",
        description="Script Python personnalisé pour générer la maison",
        default=""
    )


# Classes à enregistrer
classes = (
    HouseOpeningItem,
    HouseGeneratorProperties,
)


def register():
    """Enregistrement des propriétés"""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.house_generator = bpy.props.PointerProperty(type=HouseGeneratorProperties)
    bpy.types.Scene.house_auto_update = bpy.props.BoolProperty(
        name="Mise à jour auto",
        description="Régénérer automatiquement la maison quand les paramètres changent",
        default=False
    )
    bpy.types.Scene.house_viewport_proxy = bpy.props.BoolProperty(
        name="Proxy viewport",
        description="Suspendre les instanciations lourdes (tuiles, herbe) "
                    "dans la vue 3D — le rendu final reste complet",
        default=False,
        update=_toggle_viewport_proxy
    )
    
    print("[House] Propriétés enregistrées")
    print("  ✓ Système matériaux briques 3 modes (COLOR/PRESET/CUSTOM)")
    print("  ✓ Scan automatique textures PBR activé (lazy loading)")


def unregister():
    """Désenregistrement des propriétés"""
    # ✅ FIX: Guards pour ne pas planter si register() a partiellement échoué
    for attr in ("house_generator", "house_auto_update",
                 "house_viewport_proxy"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[House] Propriétés désenregistrées")