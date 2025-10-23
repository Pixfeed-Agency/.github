"""
Générateur de Fenêtre Coulissante pour Blender 4.2 - VERSION CORRIGÉE
Conforme aux normes architecturales européennes (NF DTU 36.5)

CORRECTIONS MAJEURES:
- Parentage et positionnement corrigés
- Assemblage correct de tous les éléments
- Hiérarchie d'objets optimisée
- Collections et groupes bien organisés

Dimensions standard respectées:
- Hauteur standard: 1.15m, 1.25m, 1.35m, 2.15m
- Largeur standard: 1.00m à 3.60m (par pas de 0.60m)
- Épaisseur du dormant: 60-80mm
- Épaisseur du vitrage: 24mm (double vitrage standard)
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
from math import radians


class FenetreCoulissanteCorrigee:
    """Classe pour générer une fenêtre coulissante avec assemblage correct"""

    # Constantes pour les profils standards
    PROFONDEUR_PROFIL = 0.06  # Profondeur standard du profil
    LARGEUR_PARCLOSE = 0.015  # Largeur des parcloses
    RAYON_BEVEL = 0.002      # Rayon des biseaux (2mm)
    SEGMENTS_BEVEL = 4        # Segments pour les biseaux

    def __init__(self,
                 largeur=2.40,
                 hauteur=2.15,
                 epaisseur_dormant=0.07,
                 epaisseur_ouvrant=0.06,
                 epaisseur_vitrage=0.024,
                 nombre_vantaux=2,
                 profondeur_rail=0.05,
                 qualite_mesh="MOYENNE"):
        """
        Initialise les paramètres de la fenêtre

        Args:
            largeur: Largeur totale en mètres (défaut: 2.40m)
            hauteur: Hauteur totale en mètres (défaut: 2.15m)
            epaisseur_dormant: Épaisseur du cadre fixe en mètres
            epaisseur_ouvrant: Épaisseur du cadre mobile
            epaisseur_vitrage: Épaisseur du vitrage (24mm standard)
            nombre_vantaux: Nombre de panneaux coulissants (2 ou 3)
            profondeur_rail: Profondeur du rail coulissant
            qualite_mesh: "BASSE", "MOYENNE", "HAUTE"
        """
        # Validation des paramètres
        if largeur < 0.6 or largeur > 6.0:
            raise ValueError("Largeur doit être entre 0.6m et 6.0m")
        if hauteur < 0.6 or hauteur > 3.0:
            raise ValueError("Hauteur doit être entre 0.6m et 3.0m")
        if nombre_vantaux < 2 or nombre_vantaux > 4:
            raise ValueError("Nombre de vantaux doit être entre 2 et 4")

        self.largeur = largeur
        self.hauteur = hauteur
        self.epaisseur_dormant = epaisseur_dormant
        self.epaisseur_ouvrant = epaisseur_ouvrant
        self.epaisseur_vitrage = epaisseur_vitrage
        self.nombre_vantaux = nombre_vantaux
        self.profondeur_rail = profondeur_rail
        self.qualite_mesh = qualite_mesh

        # Configuration qualité
        self.config_qualite = {
            "BASSE": {"subdivisions": 0, "bevel_segments": 2},
            "MOYENNE": {"subdivisions": 1, "bevel_segments": 4},
            "HAUTE": {"subdivisions": 2, "bevel_segments": 6}
        }

        # Collection pour organiser les objets
        self.collection_name = "Fenetre_Coulissante_Pro"
        self.collection = None
        self.parent_empty = None

    def nettoyer_scene(self):
        """Nettoie les objets existants de la fenêtre précédente"""
        if self.collection_name in bpy.data.collections:
            collection = bpy.data.collections[self.collection_name]
            # Supprimer tous les objets de la collection
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            # Supprimer la collection
            bpy.data.collections.remove(collection)
        print("✓ Scène nettoyée")

    def creer_collection(self):
        """Crée une collection pour organiser la fenêtre"""
        # Nettoyer l'ancienne collection si elle existe
        if self.collection_name in bpy.data.collections:
            old_collection = bpy.data.collections[self.collection_name]
            bpy.data.collections.remove(old_collection)

        # Créer la nouvelle collection
        collection = bpy.data.collections.new(self.collection_name)
        bpy.context.scene.collection.children.link(collection)

        # Créer l'objet racine VIDE à l'origine
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
        self.parent_empty = bpy.context.active_object
        self.parent_empty.name = "Fenetre_Coulissante_ROOT"

        # Déplacer vers notre collection
        bpy.context.scene.collection.objects.unlink(self.parent_empty)
        collection.objects.link(self.parent_empty)

        self.collection = collection
        print("✓ Collection créée")
        return collection

    def creer_objet_mesh(self, name, location=(0, 0, 0)):
        """Crée un objet mesh et le configure correctement"""
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        obj = bpy.context.active_object
        obj.name = name
        obj.location = location

        # Déplacer vers notre collection
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        self.collection.objects.link(obj)

        return obj

    def ajouter_bevel(self, obj, width=None, segments=None):
        """Ajoute un modificateur bevel à un objet"""
        if width is None:
            width = self.RAYON_BEVEL
        if segments is None:
            segments = self.config_qualite[self.qualite_mesh]["bevel_segments"]

        bevel = obj.modifiers.new(name="Bevel", type='BEVEL')
        bevel.width = width
        bevel.segments = segments
        bevel.limit_method = 'ANGLE'
        bevel.angle_limit = radians(30)

    def ajouter_subdivision(self, obj, levels=None):
        """Ajoute un modificateur subdivision surface"""
        if levels is None:
            levels = self.config_qualite[self.qualite_mesh]["subdivisions"]

        if levels > 0:
            subsurf = obj.modifiers.new(name="Subdivision", type='SUBSURF')
            subsurf.levels = levels
            subsurf.render_levels = levels + 1

    def creer_dormant(self):
        """Crée le cadre fixe (dormant) - MÉTHODE CORRIGÉE"""
        dormants = []

        largeur_profil = self.epaisseur_dormant
        hauteur_profil = self.PROFONDEUR_PROFIL

        # Montant HAUT
        haut = self.creer_objet_mesh("Dormant_Haut",
                                     location=(0, 0, self.hauteur/2))
        haut.scale = (self.largeur/2, hauteur_profil/2, largeur_profil/2)
        haut.parent = self.parent_empty
        bpy.context.view_layer.objects.active = haut
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(haut)
        dormants.append(haut)

        # Montant BAS
        bas = self.creer_objet_mesh("Dormant_Bas",
                                    location=(0, 0, -self.hauteur/2))
        bas.scale = (self.largeur/2, hauteur_profil/2, largeur_profil/2)
        bas.parent = self.parent_empty
        bpy.context.view_layer.objects.active = bas
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(bas)
        dormants.append(bas)

        # Montant GAUCHE
        gauche = self.creer_objet_mesh("Dormant_Gauche",
                                       location=(-self.largeur/2 + largeur_profil/2, 0, 0))
        gauche.scale = (largeur_profil/2, hauteur_profil/2, (self.hauteur - 2*largeur_profil)/2)
        gauche.parent = self.parent_empty
        bpy.context.view_layer.objects.active = gauche
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(gauche)
        dormants.append(gauche)

        # Montant DROIT
        droit = self.creer_objet_mesh("Dormant_Droit",
                                      location=(self.largeur/2 - largeur_profil/2, 0, 0))
        droit.scale = (largeur_profil/2, hauteur_profil/2, (self.hauteur - 2*largeur_profil)/2)
        droit.parent = self.parent_empty
        bpy.context.view_layer.objects.active = droit
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(droit)
        dormants.append(droit)

        # RAILS COULISSANTS (bas) avec espacement entre les rails
        for i in range(self.nombre_vantaux):
            rail = self.creer_objet_mesh(f"Rail_Inferieur_{i+1}",
                                         location=(0, -0.015 - i*0.015, -self.hauteur/2 + largeur_profil/2 + 0.005))
            rail.scale = ((self.largeur - 2*largeur_profil)/2, 0.008/2, 0.010/2)
            rail.parent = self.parent_empty
            bpy.context.view_layer.objects.active = rail
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            self.ajouter_bevel(rail, width=0.001)
            dormants.append(rail)

        print(f"✓ Dormant créé ({len(dormants)} éléments)")
        return dormants

    def creer_ouvrant_complet(self, numero, offset_x=0):
        """Crée un vantail coulissant complet - MÉTHODE CORRIGÉE"""
        # Dimensions
        largeur_vantail = (self.largeur - 2 * self.epaisseur_dormant) / self.nombre_vantaux
        hauteur_vantail = self.hauteur - 2 * self.epaisseur_dormant

        # Créer un empty pour ce vantail
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(offset_x, 0, 0))
        vantail_empty = bpy.context.active_object
        vantail_empty.name = f"Vantail_{numero}"
        vantail_empty.parent = self.parent_empty

        # Déplacer vers notre collection
        for coll in vantail_empty.users_collection:
            coll.objects.unlink(vantail_empty)
        self.collection.objects.link(vantail_empty)

        ouvrants = []
        ep = self.epaisseur_ouvrant
        prof = self.PROFONDEUR_PROFIL

        # === CADRE OUVRANT ===

        # Traverse HAUTE (position locale par rapport au vantail_empty)
        haut = self.creer_objet_mesh("Cadre_Haut", location=(0, 0, hauteur_vantail/2 - ep/2))
        haut.scale = ((largeur_vantail - 2*ep)/2, prof/2, ep/2)
        haut.parent = vantail_empty
        bpy.context.view_layer.objects.active = haut
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(haut)
        ouvrants.append(haut)

        # Traverse BASSE
        bas = self.creer_objet_mesh("Cadre_Bas", location=(0, 0, -hauteur_vantail/2 + ep/2))
        bas.scale = ((largeur_vantail - 2*ep)/2, prof/2, ep/2)
        bas.parent = vantail_empty
        bpy.context.view_layer.objects.active = bas
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(bas)
        ouvrants.append(bas)

        # Montant GAUCHE
        gauche = self.creer_objet_mesh("Cadre_Gauche", location=(-largeur_vantail/2 + ep/2, 0, 0))
        gauche.scale = (ep/2, prof/2, hauteur_vantail/2)
        gauche.parent = vantail_empty
        bpy.context.view_layer.objects.active = gauche
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(gauche)
        ouvrants.append(gauche)

        # Montant DROIT
        droit = self.creer_objet_mesh("Cadre_Droit", location=(largeur_vantail/2 - ep/2, 0, 0))
        droit.scale = (ep/2, prof/2, hauteur_vantail/2)
        droit.parent = vantail_empty
        bpy.context.view_layer.objects.active = droit
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.ajouter_bevel(droit)
        ouvrants.append(droit)

        # === VITRAGE ===
        largeur_vitrage = largeur_vantail - 2 * ep - 0.01
        hauteur_vitrage = hauteur_vantail - 2 * ep - 0.01

        vitrage = self.creer_objet_mesh("Vitrage", location=(0, 0, 0))
        vitrage.scale = (largeur_vitrage/2, self.epaisseur_vitrage/2, hauteur_vitrage/2)
        vitrage.parent = vantail_empty
        bpy.context.view_layer.objects.active = vitrage
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ouvrants.append(vitrage)

        # === PARCLOSES ===
        larg_parc = self.LARGEUR_PARCLOSE
        offset_y = self.epaisseur_vitrage/2 + larg_parc/2 + 0.002

        # Parclose HAUT
        parc_haut = self.creer_objet_mesh("Parclose_Haut",
                                          location=(0, offset_y, hauteur_vitrage/2))
        parc_haut.scale = (largeur_vitrage/2, larg_parc/2, larg_parc/2)
        parc_haut.parent = vantail_empty
        bpy.context.view_layer.objects.active = parc_haut
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ouvrants.append(parc_haut)

        # Parclose BAS
        parc_bas = self.creer_objet_mesh("Parclose_Bas",
                                         location=(0, offset_y, -hauteur_vitrage/2))
        parc_bas.scale = (largeur_vitrage/2, larg_parc/2, larg_parc/2)
        parc_bas.parent = vantail_empty
        bpy.context.view_layer.objects.active = parc_bas
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ouvrants.append(parc_bas)

        # Parclose GAUCHE
        parc_gauche = self.creer_objet_mesh("Parclose_Gauche",
                                            location=(-largeur_vitrage/2, offset_y, 0))
        parc_gauche.scale = (larg_parc/2, larg_parc/2, hauteur_vitrage/2)
        parc_gauche.parent = vantail_empty
        bpy.context.view_layer.objects.active = parc_gauche
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ouvrants.append(parc_gauche)

        # Parclose DROITE
        parc_droite = self.creer_objet_mesh("Parclose_Droite",
                                            location=(largeur_vitrage/2, offset_y, 0))
        parc_droite.scale = (larg_parc/2, larg_parc/2, hauteur_vitrage/2)
        parc_droite.parent = vantail_empty
        bpy.context.view_layer.objects.active = parc_droite
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ouvrants.append(parc_droite)

        # === POIGNÉE ===
        pos_x = largeur_vantail/2 - ep - 0.06
        pos_y = self.epaisseur_vitrage/2 + 0.025
        pos_z = hauteur_vantail/4

        # Corps de la poignée
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.015, depth=0.08,
                                           location=(pos_x, pos_y, pos_z))
        poignee = bpy.context.active_object
        poignee.name = "Poignee_Corps"
        poignee.rotation_euler = (radians(90), 0, 0)

        # Déplacer vers notre collection
        for coll in poignee.users_collection:
            coll.objects.unlink(poignee)
        self.collection.objects.link(poignee)

        poignee.parent = vantail_empty
        bpy.context.view_layer.objects.active = poignee
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        self.ajouter_bevel(poignee, width=0.001)
        ouvrants.append(poignee)

        # Base de la poignée
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=0.005,
                                           location=(pos_x, pos_y - 0.01, pos_z))
        base_poignee = bpy.context.active_object
        base_poignee.name = "Poignee_Base"
        base_poignee.rotation_euler = (radians(90), 0, 0)

        # Déplacer vers notre collection
        for coll in base_poignee.users_collection:
            coll.objects.unlink(base_poignee)
        self.collection.objects.link(base_poignee)

        base_poignee.parent = vantail_empty
        bpy.context.view_layer.objects.active = base_poignee
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        ouvrants.append(base_poignee)

        # === ROULETTES ===
        pos_z_roulette = -hauteur_vantail/2 - 0.015

        for i, x_offset in enumerate([-largeur_vantail/4, largeur_vantail/4]):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.012, depth=0.008,
                                               location=(x_offset, 0, pos_z_roulette))
            roulette = bpy.context.active_object
            roulette.name = f"Roulette_{i+1}"
            roulette.rotation_euler = (radians(90), 0, 0)

            # Déplacer vers notre collection
            for coll in roulette.users_collection:
                coll.objects.unlink(roulette)
            self.collection.objects.link(roulette)

            roulette.parent = vantail_empty
            bpy.context.view_layer.objects.active = roulette
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            self.ajouter_bevel(roulette, width=0.0005)
            ouvrants.append(roulette)

        print(f"✓ Vantail {numero} créé ({len(ouvrants)} éléments)")
        return [vantail_empty] + ouvrants

    def creer_materiau_verre(self):
        """Crée un matériau verre réaliste"""
        mat_name = "Verre_Double_Vitrage"

        # Vérifier si le matériau existe déjà
        if mat_name in bpy.data.materials:
            return bpy.data.materials[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Output
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (400, 0)

        # Glass BSDF
        glass = nodes.new(type='ShaderNodeBsdfGlass')
        glass.location = (0, 100)
        glass.inputs['IOR'].default_value = 1.52
        glass.inputs['Roughness'].default_value = 0.0

        # Transparent BSDF
        transparent = nodes.new(type='ShaderNodeBsdfTransparent')
        transparent.location = (0, -100)

        # Mix Shader
        mix = nodes.new(type='ShaderNodeMixShader')
        mix.location = (200, 0)
        mix.inputs['Fac'].default_value = 0.1

        # Liens
        links.new(glass.outputs['BSDF'], mix.inputs[1])
        links.new(transparent.outputs['BSDF'], mix.inputs[2])
        links.new(mix.outputs['Shader'], output.inputs['Surface'])

        # Activer le blend mode
        mat.blend_method = 'BLEND'
        mat.use_screen_refraction = True
        mat.refraction_depth = 0.1

        return mat

    def creer_materiau_metal(self):
        """Crée un matériau métal pour les poignées"""
        mat_name = "Metal_Chrome"

        if mat_name in bpy.data.materials:
            return bpy.data.materials[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)

        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)
        principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.82, 1.0)
        principled.inputs['Metallic'].default_value = 1.0
        principled.inputs['Roughness'].default_value = 0.15

        links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        return mat

    def creer_materiau_cadre(self):
        """Crée un matériau pour le cadre PVC blanc"""
        mat_name = "PVC_Blanc"

        if mat_name in bpy.data.materials:
            return bpy.data.materials[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)

        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)
        principled.inputs['Base Color'].default_value = (0.95, 0.95, 0.96, 1.0)
        principled.inputs['Metallic'].default_value = 0.0
        principled.inputs['Roughness'].default_value = 0.35
        principled.inputs['Specular IOR Level'].default_value = 0.3

        links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        return mat

    def creer_materiau_plastique(self):
        """Crée un matériau plastique pour les roulettes"""
        mat_name = "Plastique_Gris"

        if mat_name in bpy.data.materials:
            return bpy.data.materials[mat_name]

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new(type='ShaderNodeOutputMaterial')
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')

        principled.inputs['Base Color'].default_value = (0.3, 0.3, 0.32, 1.0)
        principled.inputs['Roughness'].default_value = 0.6

        links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        return mat

    def appliquer_materiaux(self, objets):
        """Applique les matériaux appropriés aux objets"""
        mat_cadre = self.creer_materiau_cadre()
        mat_verre = self.creer_materiau_verre()
        mat_metal = self.creer_materiau_metal()
        mat_plastique = self.creer_materiau_plastique()

        for obj in objets:
            # Ignorer les objets None ou sans mesh (empties, etc.)
            if obj is None or obj.type != 'MESH':
                continue

            if "Vitrage" in obj.name:
                mat = mat_verre
            elif "Poignee" in obj.name:
                mat = mat_metal
            elif "Roulette" in obj.name:
                mat = mat_plastique
            else:
                mat = mat_cadre

            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

    def generer(self):
        """Génère la fenêtre coulissante complète - VERSION CORRIGÉE"""
        try:
            print("\n" + "="*60)
            print("GÉNÉRATION DE LA FENÊTRE COULISSANTE")
            print("="*60)

            # Nettoyage
            print("\n[1/5] Nettoyage...")
            self.nettoyer_scene()

            # Créer la collection
            print("[2/5] Création de la collection...")
            self.creer_collection()

            # Créer le dormant
            print("[3/5] Création du dormant...")
            tous_objets = []
            dormants = self.creer_dormant()
            tous_objets.extend(dormants)

            # Créer les vantaux coulissants
            print(f"[4/5] Création des {self.nombre_vantaux} vantaux...")
            largeur_vantail = (self.largeur - 2 * self.epaisseur_dormant) / self.nombre_vantaux

            for i in range(self.nombre_vantaux):
                # Calculer la position X du centre de chaque vantail
                offset_x = (-self.largeur/2 + self.epaisseur_dormant +
                           largeur_vantail/2 + i * largeur_vantail)

                # Décaler légèrement en Y pour empêcher les chevauchements
                offset_y_base = -0.015 * i

                ouvrants = self.creer_ouvrant_complet(i+1, offset_x)
                # Appliquer le décalage Y au vantail_empty
                ouvrants[0].location.y = offset_y_base
                tous_objets.extend(ouvrants)

            # Appliquer les matériaux
            print("[5/5] Application des matériaux...")
            self.appliquer_materiaux(tous_objets)

            # Statistiques finales
            nb_objets = len(self.collection.objects)
            nb_vertices = sum(len(obj.data.vertices) for obj in self.collection.objects
                            if obj.type == 'MESH')

            print("\n" + "="*60)
            print("✓ FENÊTRE COULISSANTE GÉNÉRÉE AVEC SUCCÈS!")
            print("="*60)
            print(f"  Dimensions: {self.largeur}m x {self.hauteur}m")
            print(f"  Nombre de vantaux: {self.nombre_vantaux}")
            print(f"  Vitrage: double {self.epaisseur_vitrage*1000:.0f}mm")
            print(f"  Qualité mesh: {self.qualite_mesh}")
            print(f"  Objets créés: {nb_objets}")
            print(f"  Vertices totaux: {nb_vertices}")
            print("="*60)
            print("\nℹ️  Vérifiez la collection 'Fenetre_Coulissante_Pro'")
            print("ℹ️  Les vantaux sont décalés pour éviter les chevauchements")
            print("="*60 + "\n")

            # Sélectionner l'objet racine
            bpy.ops.object.select_all(action='DESELECT')
            self.parent_empty.select_set(True)
            bpy.context.view_layer.objects.active = self.parent_empty

            # Centrer la vue
            try:
                bpy.ops.view3d.view_selected()
            except:
                pass

            return True

        except Exception as e:
            print(f"\n✗ ERREUR lors de la génération: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Fonction principale pour créer la fenêtre"""
    print("\n" + "="*60)
    print("GÉNÉRATEUR DE FENÊTRE COULISSANTE - VERSION CORRIGÉE")
    print("Résolution du problème d'assemblage")
    print("="*60 + "\n")

    # Configuration - Modifiez ces paramètres selon vos besoins
    config = {
        "largeur": 2.40,              # Largeur totale en mètres
        "hauteur": 2.15,              # Hauteur totale en mètres
        "epaisseur_dormant": 0.07,    # 70mm
        "epaisseur_ouvrant": 0.06,    # 60mm
        "epaisseur_vitrage": 0.024,   # 24mm (double vitrage)
        "nombre_vantaux": 2,          # 2, 3 ou 4 vantaux
        "profondeur_rail": 0.05,      # 50mm
        "qualite_mesh": "MOYENNE"     # "BASSE", "MOYENNE", "HAUTE"
    }

    print("Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()

    # Créer et générer la fenêtre
    fenetre = FenetreCoulissanteCorrigee(**config)
    succes = fenetre.generer()

    if succes:
        print("✓ Script terminé avec succès!")
        print("→ La fenêtre est maintenant correctement assemblée")
    else:
        print("✗ Le script a rencontré des erreurs.")

    return fenetre


# Exécution du script
if __name__ == "__main__":
    fenetre = main()
