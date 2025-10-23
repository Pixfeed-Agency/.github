# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Manual Construction Operators Module
#  Copyright (C) 2025 mvaertan
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import FloatVectorProperty
from mathutils import Vector
import math


class HOUSE_OT_add_wall(Operator):
    """Ajoute un mur en mode manuel"""
    bl_idname = "house.add_wall"
    bl_label = "Ajouter un mur"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Point de départ du mur (sera défini par l'utilisateur)
    start_point: FloatVectorProperty(
        name="Point de départ",
        size=2,
        default=(0.0, 0.0)
    )
    
    # Point de fin du mur
    end_point: FloatVectorProperty(
        name="Point de fin",
        size=2,
        default=(0.0, 0.0)
    )
    
    # État du mode interactif
    is_drawing = False
    temp_wall = None
    
    def execute(self, context):
        props = context.scene.house_props
        
        # Calculer les dimensions du mur
        start = Vector((self.start_point[0], self.start_point[1], 0))
        end = Vector((self.end_point[0], self.end_point[1], 0))
        
        length = (end - start).length
        
        if length < 0.1:
            self.report({'WARNING'}, "Le mur est trop court")
            return {'CANCELLED'}
        
        # Position centrale du mur
        center = (start + end) / 2
        center.z = props.manual_floor_height / 2
        
        # Calculer l'angle de rotation
        direction = end - start
        angle = math.atan2(direction.y, direction.x)
        
        # Créer le mur
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        wall = context.active_object
        wall.name = "Wall_Manual"
        
        # Dimensionner le mur
        wall.scale = (
            length / 2,
            props.exterior_wall_thickness / 2,
            props.manual_floor_height / 2
        )
        
        # Rotation pour aligner avec les points
        wall.rotation_euler.z = angle
        
        # Appliquer les transformations
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        
        # Ajouter à la collection House si elle existe
        if "House" in bpy.data.collections:
            collection = bpy.data.collections["House"]
            if wall.name not in collection.objects:
                collection.objects.link(wall)
                context.scene.collection.objects.unlink(wall)
        
        self.report({'INFO'}, f"Mur créé: longueur {length:.2f}m")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Mode interactif : l'utilisateur clique deux fois pour définir le mur
        context.window_manager.modal_handler_add(self)
        self.is_drawing = False
        self.start_point = (0, 0)
        self.end_point = (0, 0)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type == 'MOUSEMOVE':
            # Suivre la souris
            if self.is_drawing:
                # Convertir la position de la souris en coordonnées 3D
                pass
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not self.is_drawing:
                # Premier clic : définir le point de départ
                self.is_drawing = True
                # Récupérer la position du curseur 3D
                self.start_point = context.scene.cursor.location[:2]
            else:
                # Deuxième clic : définir le point de fin et créer le mur
                self.end_point = context.scene.cursor.location[:2]
                return self.execute(context)
        
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}


class HOUSE_OT_add_door(Operator):
    """Ajoute une porte sur un mur sélectionné"""
    bl_idname = "house.add_door"
    bl_label = "Ajouter une porte"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Position relative sur le mur (0-1)
    position: FloatVectorProperty(
        name="Position",
        size=3,
        default=(0.0, 0.0, 0.0)
    )
    
    def execute(self, context):
        props = context.scene.house_props
        
        # Vérifier qu'un objet est sélectionné
        if not context.active_object:
            self.report({'WARNING'}, "Aucun mur sélectionné")
            return {'CANCELLED'}
        
        selected_obj = context.active_object
        
        # Créer la porte
        door_width = 0.9
        door_height = props.manual_door_height
        door_depth = 0.1
        
        # Position de la porte (sur le mur sélectionné)
        if self.position == Vector((0, 0, 0)):
            # Si pas de position définie, utiliser la position du curseur
            location = context.scene.cursor.location.copy()
            location.z = door_height / 2
        else:
            location = self.position
        
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        door = context.active_object
        door.name = "Door_Manual"
        
        door.scale = (door_width / 2, door_depth / 2, door_height / 2)
        door.display_type = 'WIRE'
        
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Ajouter à la collection House
        if "House" in bpy.data.collections:
            collection = bpy.data.collections["House"]
            if door.name not in collection.objects:
                collection.objects.link(door)
                context.scene.collection.objects.unlink(door)
        
        self.report({'INFO'}, "Porte ajoutée")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Utiliser la position du curseur 3D
        self.position = context.scene.cursor.location.copy()
        self.position.z = context.scene.house_props.manual_door_height / 2
        return self.execute(context)


class HOUSE_OT_add_window(Operator):
    """Ajoute une fenêtre sur un mur sélectionné"""
    bl_idname = "house.add_window"
    bl_label = "Ajouter une fenêtre"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Position relative sur le mur
    position: FloatVectorProperty(
        name="Position",
        size=3,
        default=(0.0, 0.0, 0.0)
    )
    
    def execute(self, context):
        props = context.scene.house_props
        
        # Créer la fenêtre
        window_width = 1.2
        window_height = props.manual_window_height
        window_depth = 0.1
        
        # Position de la fenêtre
        if self.position == Vector((0, 0, 0)):
            location = context.scene.cursor.location.copy()
            location.z = props.manual_window_sill_height + window_height / 2
        else:
            location = self.position
        
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        window = context.active_object
        window.name = "Window_Manual"
        
        window.scale = (window_width / 2, window_depth / 2, window_height / 2)
        window.display_type = 'WIRE'
        
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Ajouter à la collection House
        if "House" in bpy.data.collections:
            collection = bpy.data.collections["House"]
            if window.name not in collection.objects:
                collection.objects.link(window)
                context.scene.collection.objects.unlink(window)
        
        self.report({'INFO'}, "Fenêtre ajoutée")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        props = context.scene.house_props
        # Utiliser la position du curseur 3D
        self.position = context.scene.cursor.location.copy()
        self.position.z = props.manual_window_sill_height + props.manual_window_height / 2
        return self.execute(context)


class HOUSE_OT_import_plan(Operator):
    """Importe un plan 2D comme image de référence"""
    bl_idname = "house.import_plan"
    bl_label = "Importer le plan"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.house_props
        
        if not props.plan_image_path:
            self.report({'WARNING'}, "Aucun chemin de plan défini")
            return {'CANCELLED'}
        
        try:
            # Créer un objet Empty avec l'image comme arrière-plan
            bpy.ops.object.empty_add(type='IMAGE', location=(0, 0, 0))
            empty = context.active_object
            empty.name = "Plan_Reference"
            
            # Charger l'image
            if props.plan_image_path in bpy.data.images:
                img = bpy.data.images[props.plan_image_path]
            else:
                img = bpy.data.images.load(props.plan_image_path)
            
            empty.data = img
            
            # Configurer l'affichage
            empty.empty_display_size = 10.0
            empty.show_in_front = True
            
            # Appliquer l'échelle du plan
            empty.scale = (props.plan_scale, props.plan_scale, props.plan_scale)
            
            # Rotation pour mettre à plat (vue du dessus)
            empty.rotation_euler.x = math.radians(90)
            
            # Ajouter à la collection House
            if "House" in bpy.data.collections:
                collection = bpy.data.collections["House"]
                if empty.name not in collection.objects:
                    collection.objects.link(empty)
                    context.scene.collection.objects.unlink(empty)
            
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
        # Chercher l'objet Plan_Reference
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
    """Finalise la construction manuelle (génère les murs solides, ajoute le toit, etc.)"""
    bl_idname = "house.finalize_manual"
    bl_label = "Finaliser la construction"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.house_props
        
        # Récupérer tous les objets de la collection House
        if "House" not in bpy.data.collections:
            self.report({'WARNING'}, "Aucune maison à finaliser")
            return {'CANCELLED'}
        
        collection = bpy.data.collections["House"]
        walls = [obj for obj in collection.objects if 'Wall' in obj.name and obj.type == 'MESH']
        openings = [obj for obj in collection.objects if ('Door' in obj.name or 'Window' in obj.name) and obj.type == 'MESH']
        
        if not walls:
            self.report({'WARNING'}, "Aucun mur trouvé")
            return {'CANCELLED'}
        
        # 1. Appliquer les booléens pour créer les ouvertures dans les murs
        for wall in walls:
            for opening in openings:
                # Créer un modificateur Boolean pour soustraire l'ouverture
                mod = wall.modifiers.new(name=f"Opening_{opening.name}", type='BOOLEAN')
                mod.operation = 'DIFFERENCE'
                mod.object = opening
        
        # 2. Appliquer tous les modificateurs
        for wall in walls:
            context.view_layer.objects.active = wall
            for mod in wall.modifiers:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except:
                    pass
        
        # 3. Masquer les ouvertures (elles ont servi pour les booléens)
        for opening in openings:
            opening.hide_viewport = True
            opening.hide_render = True
        
        # 4. Créer un plancher
        self._create_floor(context, props, collection, walls)
        
        # 5. Ajouter un toit simple
        self._create_simple_roof(context, props, collection, walls)
        
        # 6. Appliquer les matériaux
        if props.use_materials:
            self._apply_materials(context, props, collection)
        
        self.report({'INFO'}, "Construction finalisée avec succès!")
        return {'FINISHED'}
    
    def _create_floor(self, context, props, collection, walls):
        """Crée un plancher basé sur l'emprise des murs"""
        if not walls:
            return
        
        # Calculer la bounding box de tous les murs
        min_x = min([obj.location.x - obj.dimensions.x/2 for obj in walls])
        max_x = max([obj.location.x + obj.dimensions.x/2 for obj in walls])
        min_y = min([obj.location.y - obj.dimensions.y/2 for obj in walls])
        max_y = max([obj.location.y + obj.dimensions.y/2 for obj in walls])
        
        width = max_x - min_x
        length = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        thickness = 0.2
        
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(center_x, center_y, -thickness/2)
        )
        
        floor = context.active_object
        floor.name = "Floor_Manual"
        floor.scale = (width/2, length/2, thickness/2)
        
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Ajouter à la collection
        if floor.name not in collection.objects:
            collection.objects.link(floor)
            context.scene.collection.objects.unlink(floor)
    
    def _create_simple_roof(self, context, props, collection, walls):
        """Crée un toit simple basé sur l'emprise des murs"""
        if not walls:
            return
        
        # Calculer la bounding box
        min_x = min([obj.location.x - obj.dimensions.x/2 for obj in walls])
        max_x = max([obj.location.x + obj.dimensions.x/2 for obj in walls])
        min_y = min([obj.location.y - obj.dimensions.y/2 for obj in walls])
        max_y = max([obj.location.y + obj.dimensions.y/2 for obj in walls])
        
        width = max_x - min_x
        length = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        height = props.manual_floor_height
        thickness = 0.3
        
        bpy.ops.mesh.primitive_cube_add(
            size=1,
            location=(center_x, center_y, height + thickness/2)
        )
        
        roof = context.active_object
        roof.name = "Roof_Manual"
        roof.scale = ((width + 1)/2, (length + 1)/2, thickness/2)  # +1m de débord
        
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Ajouter à la collection
        if roof.name not in collection.objects:
            collection.objects.link(roof)
            context.scene.collection.objects.unlink(roof)
    
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
        if name in bpy.data.materials:
            mat = bpy.data.materials[name]
        else:
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
        
        nodes = mat.node_tree.nodes
        principled = nodes.get("Principled BSDF")
        
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