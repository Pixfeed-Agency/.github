# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Manual Construction Operators Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

# ✅ REFONTE COMPLÈTE — l'ancien module était entièrement non fonctionnel:
# - context.scene.house_props n'existe pas (la propriété s'appelle
#   house_generator) → AttributeError sur chaque opérateur
# - primitive_cube_add(size=1) + scale/2 → tous les objets à MOITIÉ taille
# - le dessin de mur lisait le curseur 3D (qui ne bouge pas) au lieu de la
#   souris → "mur trop court" systématique
# - self.position.z = ... sur un FloatVectorProperty → AttributeError
# - unlink depuis scene.collection → RuntimeError si l'objet n'y est pas
# - itération sur wall.modifiers pendant modifier_apply → la moitié des
#   ouvertures jamais percées

import os
import bpy
from bpy.types import Operator
from bpy.props import FloatVectorProperty
from bpy_extras import view3d_utils
from mathutils import Vector
import math


def _move_to_house_collection(context, obj):
    """Déplace un objet dans la collection House (créée au besoin)"""
    collection = bpy.data.collections.get("House")
    if collection is None:
        collection = bpy.data.collections.new("House")
        context.scene.collection.children.link(collection)

    # ✅ FIX: Retirer de TOUTES les collections actuelles (l'ancien code
    # supposait scene.collection et levait RuntimeError sinon)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    return collection


def _mouse_to_ground(context, event):
    """Projette la position de la souris sur le plan Z=0"""
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None
    coord = (event.mouse_region_x, event.mouse_region_y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    if abs(direction.z) < 1e-6:
        return None
    t = -origin.z / direction.z
    if t < 0:
        return None
    return origin + direction * t


class HOUSE_OT_add_wall(Operator):
    """Ajoute un mur en mode manuel (2 clics: départ puis fin)"""
    bl_idname = "house.add_wall"
    bl_label = "Ajouter un mur"
    bl_options = {'REGISTER', 'UNDO'}

    start_point: FloatVectorProperty(name="Point de départ", size=2, default=(0.0, 0.0))
    end_point: FloatVectorProperty(name="Point de fin", size=2, default=(0.0, 0.0))

    is_drawing = False

    def execute(self, context):
        props = context.scene.house_generator

        start = Vector((self.start_point[0], self.start_point[1], 0))
        end = Vector((self.end_point[0], self.end_point[1], 0))

        length = (end - start).length

        if length < 0.1:
            self.report({'WARNING'}, "Le mur est trop court")
            return {'CANCELLED'}

        center = (start + end) / 2
        center.z = props.floor_height / 2

        direction = end - start
        angle = math.atan2(direction.y, direction.x)

        # ✅ FIX: size=2 → un scale de dimension/2 donne la dimension voulue
        # (avec size=1, tous les murs sortaient à moitié taille)
        bpy.ops.mesh.primitive_cube_add(size=2, location=center)
        wall = context.active_object
        wall.name = "Wall_Manual"

        wall.scale = (
            length / 2,
            props.exterior_wall_thickness / 2,
            props.floor_height / 2
        )
        wall.rotation_euler.z = angle

        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        _move_to_house_collection(context, wall)

        self.report({'INFO'}, f"Mur créé: longueur {length:.2f}m")
        return {'FINISHED'}

    def invoke(self, context, event):
        if context.region_data is None:
            self.report({'WARNING'}, "Utilisez cet outil dans une vue 3D")
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        self.is_drawing = False
        self.start_point = (0, 0)
        self.end_point = (0, 0)
        self.report({'INFO'}, "Cliquez pour le départ du mur, puis pour la fin (Échap pour annuler)")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        # ✅ FIX: Guard None (crash quand la souris sort des zones)
        if context.area:
            context.area.tag_redraw()

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # ✅ FIX: Position réelle de la SOURIS projetée sur le sol —
            # l'ancien code lisait le curseur 3D qui ne bouge pas entre les
            # deux clics → longueur toujours nulle
            hit = _mouse_to_ground(context, event)
            if hit is None:
                return {'RUNNING_MODAL'}

            if not self.is_drawing:
                self.is_drawing = True
                self.start_point = (hit.x, hit.y)
            else:
                self.end_point = (hit.x, hit.y)
                return self.execute(context)

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class HOUSE_OT_add_door(Operator):
    """Ajoute une porte (volume de découpe) à la position du curseur 3D"""
    bl_idname = "house.add_door"
    bl_label = "Ajouter une porte"
    bl_options = {'REGISTER', 'UNDO'}

    position: FloatVectorProperty(name="Position", size=3, default=(0.0, 0.0, 0.0))

    def execute(self, context):
        props = context.scene.house_generator

        if not context.active_object:
            self.report({'WARNING'}, "Aucun mur sélectionné")
            return {'CANCELLED'}

        door_width = props.front_door_width
        door_height = props.door_height
        door_depth = props.exterior_wall_thickness + 0.1

        # ✅ FIX: comparaison composante par composante (bpy_prop_array ==
        # Vector est toujours False)
        if all(abs(c) < 1e-6 for c in self.position):
            location = context.scene.cursor.location.copy()
            location.z = door_height / 2
        else:
            location = Vector(self.position)

        bpy.ops.mesh.primitive_cube_add(size=2, location=location)
        door = context.active_object
        door.name = "Door_Manual"

        door.scale = (door_width / 2, door_depth / 2, door_height / 2)
        door.display_type = 'WIRE'

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        _move_to_house_collection(context, door)

        self.report({'INFO'}, "Porte ajoutée")
        return {'FINISHED'}

    def invoke(self, context, event):
        props = context.scene.house_generator
        # ✅ FIX: Construire un Vector local puis assigner (l'assignation
        # renvoie un bpy_prop_array sans attribut .z)
        loc = context.scene.cursor.location.copy()
        loc.z = props.door_height / 2
        self.position = loc
        return self.execute(context)


class HOUSE_OT_add_window(Operator):
    """Ajoute une fenêtre (volume de découpe) à la position du curseur 3D"""
    bl_idname = "house.add_window"
    bl_label = "Ajouter une fenêtre"
    bl_options = {'REGISTER', 'UNDO'}

    position: FloatVectorProperty(name="Position", size=3, default=(0.0, 0.0, 0.0))

    WINDOW_SILL_HEIGHT = 1.0  # Hauteur d'allège par défaut

    def execute(self, context):
        props = context.scene.house_generator

        window_width = props.window_width
        window_height = props.window_height
        window_depth = props.exterior_wall_thickness + 0.1

        if all(abs(c) < 1e-6 for c in self.position):
            location = context.scene.cursor.location.copy()
            location.z = self.WINDOW_SILL_HEIGHT + window_height / 2
        else:
            location = Vector(self.position)

        bpy.ops.mesh.primitive_cube_add(size=2, location=location)
        window = context.active_object
        window.name = "Window_Manual"

        window.scale = (window_width / 2, window_depth / 2, window_height / 2)
        window.display_type = 'WIRE'

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        _move_to_house_collection(context, window)

        self.report({'INFO'}, "Fenêtre ajoutée")
        return {'FINISHED'}

    def invoke(self, context, event):
        props = context.scene.house_generator
        loc = context.scene.cursor.location.copy()
        loc.z = self.WINDOW_SILL_HEIGHT + props.window_height / 2
        self.position = loc
        return self.execute(context)


class HOUSE_OT_import_plan(Operator):
    """Importe un plan 2D comme image de référence"""
    bl_idname = "house.import_plan"
    bl_label = "Importer le plan"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.house_generator

        if not props.plan_image_path:
            self.report({'WARNING'}, "Aucun chemin de plan défini")
            return {'CANCELLED'}

        try:
            bpy.ops.object.empty_add(type='IMAGE', location=(0, 0, 0))
            empty = context.active_object
            empty.name = "Plan_Reference"

            # ✅ FIX: Rechercher par nom de fichier (les images Blender sont
            # nommées par basename, pas par chemin complet → l'image était
            # rechargée à chaque import)
            img_name = os.path.basename(props.plan_image_path)
            img = bpy.data.images.get(img_name)
            if img is None:
                img = bpy.data.images.load(props.plan_image_path)

            empty.data = img

            # ✅ FIX: L'échelle passe par empty_display_size — l'ancien
            # scale=(0.01, ...) rendait le plan quasi invisible
            empty.empty_display_size = 10.0 * max(props.plan_scale, 0.001)
            empty.show_in_front = True

            # Rotation pour mettre à plat (vue du dessus)
            empty.rotation_euler.x = math.radians(90)

            _move_to_house_collection(context, empty)

            self.report({'INFO'}, "Plan importé avec succès")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Erreur lors de l'import: {str(e)}")
            return {'CANCELLED'}


class HOUSE_OT_toggle_plan(Operator):
    """Affiche ou masque le plan de référence"""
    bl_idname = "house.toggle_plan"
    bl_label = "Afficher/Masquer le plan"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        plan_obj = bpy.data.objects.get("Plan_Reference")

        if plan_obj:
            plan_obj.hide_viewport = not plan_obj.hide_viewport
            plan_obj.hide_render = plan_obj.hide_viewport

            status = "masqué" if plan_obj.hide_viewport else "affiché"
            self.report({'INFO'}, f"Plan {status}")
        else:
            self.report({'WARNING'}, "Aucun plan de référence trouvé")

        return {'FINISHED'}


class HOUSE_OT_finalize_manual(Operator):
    """Finalise la construction manuelle (perce les ouvertures, ajoute plancher et toit)"""
    bl_idname = "house.finalize_manual"
    bl_label = "Finaliser la construction"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.house_generator

        if "House" not in bpy.data.collections:
            self.report({'WARNING'}, "Aucune maison à finaliser")
            return {'CANCELLED'}

        collection = bpy.data.collections["House"]
        walls = [obj for obj in collection.objects if 'Wall' in obj.name and obj.type == 'MESH']
        openings = [obj for obj in collection.objects
                    if ('Door' in obj.name or 'Window' in obj.name) and obj.type == 'MESH']

        if not walls:
            self.report({'WARNING'}, "Aucun mur trouvé")
            return {'CANCELLED'}

        # 1. Booléens: ne soustraire une ouverture que des murs qu'elle
        # intersecte réellement (avant: chaque ouverture perçait TOUS les murs)
        for wall in walls:
            for opening in openings:
                if not self._bboxes_intersect(wall, opening):
                    continue
                mod = wall.modifiers.new(name=f"Opening_{opening.name}", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = opening

        # 2. Appliquer tous les modificateurs
        # ✅ FIX: snapshot des noms — itérer wall.modifiers pendant
        # modifier_apply saute un modificateur sur deux
        for wall in walls:
            context.view_layer.objects.active = wall
            for mod_name in [m.name for m in wall.modifiers]:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod_name)
                except RuntimeError as e:
                    print(f"[House] Échec modifier '{mod_name}' sur {wall.name}: {e}")

        # 3. Masquer les ouvertures (elles ont servi pour les booléens)
        for opening in openings:
            opening.hide_viewport = True
            opening.hide_render = True

        # 4. Plancher + 5. Toit
        self._create_floor(context, props, collection, walls)
        self._create_simple_roof(context, props, collection, walls)

        # 6. Matériaux
        if props.use_materials:
            self._apply_materials(context, props, collection)

        self.report({'INFO'}, "Construction finalisée avec succès!")
        return {'FINISHED'}

    @staticmethod
    def _bboxes_intersect(obj_a, obj_b, margin=0.05):
        """Test d'intersection des boîtes englobantes monde de deux objets"""
        def world_bbox(obj):
            pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
            return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

        ax0, ax1, ay0, ay1, az0, az1 = world_bbox(obj_a)
        bx0, bx1, by0, by1, bz0, bz1 = world_bbox(obj_b)
        return not (ax1 + margin < bx0 or bx1 + margin < ax0 or
                    ay1 + margin < by0 or by1 + margin < ay0 or
                    az1 + margin < bz0 or bz1 + margin < az0)

    def _bounds_of_walls(self, walls):
        min_x = min(obj.location.x - obj.dimensions.x / 2 for obj in walls)
        max_x = max(obj.location.x + obj.dimensions.x / 2 for obj in walls)
        min_y = min(obj.location.y - obj.dimensions.y / 2 for obj in walls)
        max_y = max(obj.location.y + obj.dimensions.y / 2 for obj in walls)
        return min_x, max_x, min_y, max_y

    def _create_floor(self, context, props, collection, walls):
        """Crée un plancher basé sur l'emprise des murs"""
        if not walls:
            return

        min_x, max_x, min_y, max_y = self._bounds_of_walls(walls)
        width = max_x - min_x
        length = max_y - min_y
        thickness = 0.2

        bpy.ops.mesh.primitive_cube_add(
            size=2,
            location=((min_x + max_x) / 2, (min_y + max_y) / 2, -thickness / 2)
        )

        floor = context.active_object
        floor.name = "Floor_Manual"
        floor.scale = (width / 2, length / 2, thickness / 2)

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        _move_to_house_collection(context, floor)

    def _create_simple_roof(self, context, props, collection, walls):
        """Crée un toit simple basé sur l'emprise des murs"""
        if not walls:
            return

        min_x, max_x, min_y, max_y = self._bounds_of_walls(walls)
        width = max_x - min_x
        length = max_y - min_y

        height = props.floor_height
        thickness = 0.3

        bpy.ops.mesh.primitive_cube_add(
            size=2,
            location=((min_x + max_x) / 2, (min_y + max_y) / 2, height + thickness / 2)
        )

        roof = context.active_object
        roof.name = "Roof_Manual"
        roof.scale = ((width + 1) / 2, (length + 1) / 2, thickness / 2)  # +1m de débord

        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        _move_to_house_collection(context, roof)

    def _apply_materials(self, context, props, collection):
        """Applique les matériaux aux objets de la collection"""
        wall_mat = self._create_material("House_Wall", props.wall_material_color)
        roof_mat = self._create_material("House_Roof", props.roof_material_color)
        floor_mat = self._create_material("House_Floor", props.floor_material_color)

        for obj in collection.objects:
            if obj.type == 'MESH' and not obj.hide_viewport:
                if 'Wall' in obj.name:
                    self._assign_material(obj, wall_mat)
                elif 'Roof' in obj.name:
                    self._assign_material(obj, roof_mat)
                elif 'Floor' in obj.name:
                    self._assign_material(obj, floor_mat)

    def _create_material(self, name, color):
        """Crée un matériau simple"""
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
        # ✅ FIX: Un matériau existant sans nodes plantait sur node_tree
        if not mat.use_nodes:
            mat.use_nodes = True

        # ✅ FIX: Chercher par TYPE, pas par nom anglais
        nodes = mat.node_tree.nodes
        principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)

        if principled:
            principled.inputs["Base Color"].default_value = (*color, 1.0)
            principled.inputs["Roughness"].default_value = 0.7

        return mat

    def _assign_material(self, obj, material):
        """Assigne un matériau à un objet"""
        if len(obj.data.materials) == 0:
            obj.data.materials.append(material)
        else:
            obj.data.materials[0] = material


# Liste des classes à enregistrer
classes = (
    HOUSE_OT_add_wall,
    HOUSE_OT_add_door,
    HOUSE_OT_add_window,
    HOUSE_OT_import_plan,
    HOUSE_OT_toggle_plan,
    HOUSE_OT_finalize_manual,
)


def register():
    """Enregistrement des classes"""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Désenregistrement des classes"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
