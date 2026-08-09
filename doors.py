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

        # ✅ v1.15: SLOT D'ASSET (optionnel, chantier n°7) — l'objet de
        # l'utilisateur remplace la porte procédurale, mis à l'échelle
        # de l'ouverture (ancre = coin bas, convention des portes).
        # Slot vide ou défaillant → porte procédurale (repli).
        try:
            from . import slots
            _p = bpy.context.scene.house_generator
            _asset = slots.slot_object(_p, 'door_asset')
        except Exception:
            _asset = None
        if _asset is not None:
            try:
                rot = {'front': Matrix.Identity(4),
                       'back': Matrix.Rotation(math.radians(180), 4, 'Z'),
                       'left': Matrix.Rotation(math.radians(90), 4, 'Z'),
                       'right': Matrix.Rotation(math.radians(-90), 4, 'Z'),
                       }.get(orientation, Matrix.Identity(4))
                obj = slots.place_asset(
                    _asset, "Door_Asset", width, height, location, rot,
                    collection, part="door", anchor='corner')
                if obj is not None:
                    return [obj]
            except Exception as e:
                print(f"[Doors] Slot asset échoué ({e}) → procédural")

        # ✅ FIX: try/except comme les fenêtres — une erreur bmesh ne doit
        # pas interrompre toute la génération de la maison
        try:
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

        except Exception as e:
            print(f"[Doors] ERREUR création porte {door_type}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _make_openable(self, obj, sign=1.0, max_angle_deg=105.0):
        """✅ ARTICULATION RÉELLE: propriété 'ouverture' (0=fermée,
        1=grande ouverte) pilotant la rotation par DRIVER, pivot sur
        les gonds (l'origine de l'objet est sur la ligne de charnières).

        L'utilisateur sélectionne le battant → panneau N (custom
        properties) → glisse 'ouverture' → la porte s'ouvre. Animable.
        """
        obj["ouverture"] = 0.0
        try:
            ui = obj.id_properties_ui("ouverture")
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                      description="0 = fermée, 1 = grande ouverte")
        except Exception:
            pass
        fcu = obj.driver_add('rotation_euler', 2)
        drv = fcu.driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = 'o'
        var.type = 'SINGLE_PROP'
        var.targets[0].id = obj
        var.targets[0].data_path = '["ouverture"]'
        drv.expression = f'{sign:.0f} * o * {math.radians(max_angle_deg):.5f}'

    def _create_single_door(self, width, height, location, orientation, collection):
        """Crée une porte simple battant OUVRABLE (gonds à gauche)"""
        objects = []

        # Cadre de porte
        frame = self._create_door_frame(width, height, orientation)
        frame.name = "Door_Frame"
        frame.location = location
        collection.objects.link(frame)
        objects.append(frame)

        # Panneau de porte (l'origine du mesh est SUR la ligne de gonds)
        panel = self._create_door_panel(width - self.frame_width * 2, height - self.frame_width, orientation)
        panel.name = "Door_Panel"

        # Positionner le panneau
        panel_offset = self._get_panel_offset(width, orientation, 'single')
        panel.location = location + panel_offset
        collection.objects.link(panel)
        objects.append(panel)

        # ✅ Battant articulé (s'ouvre vers l'intérieur)
        self._make_openable(panel, sign=1.0)

        # Appliquer matériaux
        self._apply_door_materials(frame, panel)

        return objects

    def _create_double_door(self, width, height, location, orientation, collection, with_mullion=True):
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

        # Panneau droit — géométrie MIROIR (gonds à DROITE: l'origine du
        # mesh doit être sur la ligne de gonds pour que la rotation ouvre)
        panel_right = self._create_door_panel(panel_width, height - self.frame_width, orientation,
                                              mirror=True)
        panel_right.name = "Door_Panel_Right"

        # Origine posée sur le jambage DROIT
        offset_right = Vector((width - self.frame_width, 0, self._get_panel_offset(width, orientation, 'double_right').z))
        offset_right.y = self._get_panel_offset(width, orientation, 'double_right').y
        panel_right.location = location + offset_right
        collection.objects.link(panel_right)
        objects.append(panel_right)

        # ✅ Battants articulés (gauche s'ouvre en +, droit en -)
        self._make_openable(panel_left, sign=1.0)
        self._make_openable(panel_right, sign=-1.0)

        # Montant central (sauf porte coulissante)
        if with_mullion:
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
        # ✅ FIX: vraiment SANS montant central (avant: identique à DOUBLE)
        return self._create_double_door(width, height, location, orientation, collection,
                                        with_mullion=False)

    def _create_french_door(self, width, height, location, orientation, collection):
        """✅ IMPLÉMENTÉ: Porte-fenêtre à la française — 2 battants dont
        les panneaux sont largement vitrés (cadre bois + vitre)"""
        objects = self._create_double_door(width, height, location, orientation, collection)

        # Ajouter une vitre au centre de chaque battant
        glass_mat = self._get_glass_material()
        panel_width = (width - self.frame_width * 3) / 2
        glass_w = panel_width - 0.16          # marge du cadre bois
        glass_h = height - self.frame_width - 0.30
        th = self.door_thickness

        for obj in list(objects):
            if "Panel" not in obj.name:
                continue
            bm = bmesh.new()
            gx0 = (panel_width - glass_w) / 2
            gz0 = 0.18
            # Vitre: fine plaque centrée dans l'épaisseur du panneau
            vb = [bm.verts.new(c) for c in (
                (gx0, th * 0.45, gz0), (gx0 + glass_w, th * 0.45, gz0),
                (gx0 + glass_w, th * 0.45, gz0 + glass_h), (gx0, th * 0.45, gz0 + glass_h))]
            vt = [bm.verts.new((v.co.x, th * 0.55, v.co.z)) for v in vb]
            bm.faces.new(vb[::-1])
            bm.faces.new(vt)
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            mesh = bpy.data.meshes.new("Door_Glass_Mesh")
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()
            glass = bpy.data.objects.new("Door_Glass", mesh)
            glass["house_part"] = "glass"
            glass.location = obj.location
            glass.data.materials.append(glass_mat)
            collection.objects.link(glass)
            objects.append(glass)

        return objects

    def _get_glass_material(self):
        """Matériau verre simple pour portes vitrées (mis en cache)"""
        mat = bpy.data.materials.get("Door_Glass_Material")
        if mat is None:
            mat = bpy.data.materials.new("Door_Glass_Material")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            glass = nodes.new('ShaderNodeBsdfGlass')
            glass.inputs['IOR'].default_value = 1.45
            glass.inputs['Color'].default_value = (0.85, 0.92, 0.95, 1.0)
            out = nodes.new('ShaderNodeOutputMaterial')
            mat.node_tree.links.new(glass.outputs['BSDF'], out.inputs['Surface'])
            if hasattr(mat, "surface_render_method"):
                mat.surface_render_method = 'BLENDED'
            elif hasattr(mat, "blend_method"):
                mat.blend_method = 'BLEND'
        return mat

    def _create_door_frame(self, width, height, orientation):
        """Crée le cadre de porte (dormant)"""
        bm = bmesh.new()
        mesh = None

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
            # ✅ FIX: Pas de face "Bas" — les 4 points (z=0, y=0) étaient
            # colinéaires → face d'aire nulle (normales NaN, artefacts).
            # Un dormant de porte n'a pas de traverse basse.
            bm.faces.new([outer_verts[1], outer_verts[2], inner_verts[2], inner_verts[1]])  # Droite
            bm.faces.new([outer_verts[2], outer_verts[3], inner_verts[3], inner_verts[2]])  # Haut
            bm.faces.new([outer_verts[3], outer_verts[0], inner_verts[0], inner_verts[3]])  # Gauche

            # Extrusion pour donner de la profondeur
            # ✅ FIX: use_keep_orig garde la face d'origine → volume fermé
            # (avant: le cadre était creux/ouvert côté y=0)
            extrude_faces = list(bm.faces)
            ret = bmesh.ops.extrude_face_region(bm, geom=extrude_faces, use_keep_orig=True)
            extruded_verts = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, verts=extruded_verts, vec=(0, fd, 0))

            # ✅ FIX: Recalculer les normales (elles pointaient vers
            # l'intérieur du volume → rendu inversé/noir)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            mesh = bpy.data.meshes.new("Door_Frame_Mesh")
            bm.to_mesh(mesh)
            mesh.update()

        finally:
            bm.free()

        obj = bpy.data.objects.new("Door_Frame", mesh)
        obj["house_part"] = "door"

        return obj

    def _create_door_panel(self, width, height, orientation, mirror=False):
        """✅ V2: VRAI panneau de menuiserie — montants + traverses +
        panneaux moulurés en retrait (fini la boîte plate).

        L'origine du mesh est SUR LA LIGNE DE GONDS (x=0) pour que la
        rotation du driver 'ouverture' pivote comme une vraie porte.
        mirror=True construit le battant en x∈[-width,0] (gonds à droite).
        """
        bm = bmesh.new()
        mesh = None

        try:
            th = self.door_thickness
            stile = 0.11          # montants verticaux
            rail_b = 0.20         # traverse basse (plus haute: norme)
            rail_t = 0.11         # traverse haute
            rail_m = 0.09         # traverse intermédiaire
            recess = th * 0.42    # profondeur de moulure

            def box(x0, y0, z0, x1, y1, z1):
                vb = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
                vt = [bm.verts.new(c) for c in ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
                bm.faces.new(vb[::-1]); bm.faces.new(vt)
                for i in range(4):
                    j = (i + 1) % 4
                    bm.faces.new([vb[i], vb[j], vt[j], vt[i]])

            # Cadre du battant (pleine épaisseur)
            box(0, 0, 0, stile, th, height)                              # montant gonds
            box(width - stile, 0, 0, width, th, height)                  # montant serrure
            box(stile, 0, 0, width - stile, th, rail_b)                  # traverse basse
            box(stile, 0, height - rail_t, width - stile, th, height)    # traverse haute
            mid_z = height * 0.62
            box(stile, 0, mid_z - rail_m / 2, width - stile, th, mid_z + rail_m / 2)  # traverse médiane

            # 2 panneaux moulurés EN RETRAIT (épaisseur réduite, centrés)
            y0p = recess / 2
            y1p = th - recess / 2
            box(stile, y0p, rail_b, width - stile, y1p, mid_z - rail_m / 2)          # panneau bas
            box(stile, y0p, mid_z + rail_m / 2, width - stile, y1p, height - rail_t)  # panneau haut

            # Chanfreins de qualité
            if self.bevel_amount > 0:
                bmesh.ops.bevel(bm, geom=list(bm.edges), offset=self.bevel_amount,
                                segments=2, profile=0.5, affect='EDGES')

            # ✅ POIGNÉE (côté serrure)
            hz = min(DOOR_HANDLE_HEIGHT, height - 0.3)
            hx = width - 0.09
            ret = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Diagonal((0.035, 0.012, 0.16, 1.0)))
            bmesh.ops.translate(bm, verts=ret['verts'], vec=(hx, -0.006, hz))
            ret = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.transform(bm, verts=ret['verts'],
                                matrix=Matrix.Diagonal((0.11, 0.018, 0.018, 1.0)))
            bmesh.ops.translate(bm, verts=ret['verts'], vec=(hx - 0.045, -0.028, hz))

            # ✅ Battant miroir: gonds à droite → géométrie en x∈[-width, 0]
            if mirror:
                bmesh.ops.translate(bm, verts=bm.verts, vec=(-width, 0, 0))

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

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
        mesh = None

        try:
            fw = self.frame_width
            th = self.door_thickness

            # Montant vertical simple
            # ✅ FIX: Profondeur = épaisseur du PANNEAU (avant: frame_depth
            # entière → le montant dépassait de 3cm des deux côtés)
            bmesh.ops.create_cube(bm, size=1.0)

            scale_matrix = Matrix.Diagonal((fw, th, height, 1.0))
            bmesh.ops.transform(bm, matrix=scale_matrix, verts=bm.verts)
            bmesh.ops.translate(bm, verts=bm.verts,
                                vec=(fw/2, self.frame_depth/2, height/2))

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

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
            # ✅ v1.9.1: panneau en BOIS VEINÉ (chêne foncé) — l'aplat
            # beige faisait porte de maquette
            try:
                from . import look
                mat = look.wood_material("Door_Panel_Material",
                                         base=(0.185, 0.105, 0.055),
                                         rough=0.42, along='Z')
                panel_obj.data.materials.clear()
                panel_obj.data.materials.append(mat)
                return
            except Exception:
                pass
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
