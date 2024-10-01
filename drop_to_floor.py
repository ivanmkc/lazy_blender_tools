"""
File: drop_to_floor.py

Description:
This tool drops selected objects (or their hierarchies) onto the surface of geometry below them using raycasting.
It ensures that selected objects do not interfere with one another during the drop, nor do they hit themselves
or their children. The tool also supports dropping to a user-defined floor if no geometry is detected below.
The tool handles all object types, including meshes, cameras, lights, and empties with children.
"""

import bpy
import mathutils

def get_hierarchy_bounding_box(obj):
    """
    Calculate the bounding box of the object, including its children if it has any.
    This handles cases where the object is an EMPTY and has child objects with a meaningful bounding box.
    
    Args:
    - obj (bpy.types.Object): The parent object whose hierarchy's bounding box is being calculated.

    Returns:
    - List[mathutils.Vector]: A list of world space coordinates representing the bounding box.
    """
    # If the object has no children, just return its bounding box
    if not obj.children:
        matrix_world = obj.matrix_world
        return [matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    
    # If the object has children, calculate the combined bounding box of the entire hierarchy
    bbox_corners = []
    for child in obj.children_recursive:
        matrix_world = child.matrix_world
        bbox_corners.extend([matrix_world @ mathutils.Vector(corner) for corner in child.bound_box])
    
    return bbox_corners

def drop_to_geometry_below(
    obj: bpy.types.Object,
    fallback_to_floor: bool = True,
    custom_floor: float = 0.0,
    move_threshold: float = 0.01
) -> None:
    """
    Drop the given object and its hierarchy to the geometry below by raycasting downward from its lowest point on the Z-axis.
    Temporarily hides other selected objects, the object itself, and its children to prevent collisions during raycasting.
    
    Args:
    - obj (bpy.types.Object): The object (parent) to drop, along with its children.
    - fallback_to_floor (bool): If True, drop to a user-defined floor when no geometry is detected below.
    - custom_floor (float): The Z-coordinate of the user-defined floor.
    - move_threshold (float): The minimum movement distance required to apply the drop.
    """
    print(f"Processing object: {obj.name}")

    # Save the visibility of other selected objects and the object itself and its children
    selected_objects = [o for o in bpy.context.selected_objects if o != obj]
    children_objects = list(obj.children_recursive)  # All children and their children
    
    # Temporarily hide the object itself and its children to prevent hitting them during raycasting
    print(f"Hiding {obj.name} and its {len(children_objects)} children to avoid self-collision during raycasting.")
    for child in children_objects:
        child.hide_viewport = True
    obj.hide_viewport = True

    try:
        # Get the combined bounding box (including children if applicable)
        bbox = get_hierarchy_bounding_box(obj)
        print(f"Object: {obj.name} | Combined Bounding Box (world space): {[(v.x, v.y, v.z) for v in bbox]}")

        # Find the lowest Z-coordinate of the hierarchy (world space)
        lowest_z = min([vertex.z for vertex in bbox])
        print(f"Object: {obj.name} | Lowest Z-coordinate: {lowest_z}")

        # Cast a ray from the hierarchy's lowest point straight down to check for geometry below
        ray_origin = mathutils.Vector((obj.location.x, obj.location.y, lowest_z + 0.01))
        ray_direction = mathutils.Vector((0, 0, -1))
        print(f"Object: {obj.name} | Ray Origin: {ray_origin} | Ray Direction: {ray_direction}")

        # Perform the raycast to detect geometry below
        depsgraph = bpy.context.evaluated_depsgraph_get()
        result, location, normal, index, hit_obj, matrix = bpy.context.scene.ray_cast(
            depsgraph, ray_origin, ray_direction
        )

        # Handle raycast results
        print(f"Object: {obj.name} | Raycast result: {result} | Hit Location: {location} | Hit Object: {hit_obj}")

        if result:
            # Move the object down if geometry is found and the distance exceeds the threshold
            distance_to_move = location.z - lowest_z
            if abs(distance_to_move) > move_threshold:
                obj.location.z += distance_to_move
                print(f"Object: {obj.name} | Moved by: {distance_to_move}")
            else:
                print(f"Object: {obj.name} | Distance to move ({distance_to_move}) is below the threshold ({move_threshold}). No movement applied.")
        else:
            # No geometry found, apply fallback floor if necessary
            print(f"Object: {obj.name} | No geometry detected below.")
            if fallback_to_floor:
                print(f"Object: {obj.name} | Moving to custom floor at Z = {custom_floor}")
                obj.location.z = custom_floor - (lowest_z - obj.location.z)
            else:
                print(f"Object: {obj.name} | No action taken (no fallback floor).")
    finally:
        # Restore visibility of the object, its children, and other hidden objects
        print(f"Restoring visibility for {obj.name}, its children, and other hidden objects.")
        obj.hide_viewport = False
        for child in children_objects:
            child.hide_viewport = False
        for other_obj in selected_objects:
            other_obj.hide_viewport = False  # Restore visibility

class OBJECT_OT_DropToFloorOperator(bpy.types.Operator):
    """Operator that drops selected objects to the geometry or custom floor."""
    bl_idname = "object.drop_to_floor_operator"
    bl_label = "Drop to Floor"
    bl_options = {'REGISTER', 'UNDO'}

    fallback_to_floor: bpy.props.BoolProperty(
        name="Fallback to User Floor",
        description="Drop to user-defined floor if no geometry below",
        default=False
    )

    custom_floor: bpy.props.FloatProperty(
        name="Custom Floor Level",
        description="User-defined Z-axis floor level for when no geometry is below",
        default=0.0
    )

    move_threshold: bpy.props.FloatProperty(
        name="Move Threshold",
        description="Minimum movement distance to apply",
        default=0.01,
        min=0.0,
        max=10.0
    )

    def execute(self, context):
        """Execute the drop to floor operation for all selected objects."""
        for obj in context.selected_objects:
            if obj.type in {'MESH', 'EMPTY', 'CAMERA', 'LIGHT', 'CURVE', 'SURFACE', 'FONT', 'META'}:
                drop_to_geometry_below(
                    obj,
                    fallback_to_floor=self.fallback_to_floor,
                    custom_floor=self.custom_floor,
                    move_threshold=self.move_threshold
                )
        return {'FINISHED'}

class VIEW3D_PT_DropToFloorPanel(bpy.types.Panel):
    """UI Panel to trigger the Drop to Floor tool in the 3D Viewport."""
    bl_label = "Drop to Floor"
    bl_idname = "VIEW3D_PT_drop_to_floor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LazyTools'

    def draw(self, context):
        """Draw the UI panel."""
        layout = self.layout
        layout.operator("object.drop_to_floor_operator", text="Run")


def register():
    """Register the operator and panel with Blender."""
    bpy.utils.register_class(OBJECT_OT_DropToFloorOperator)
    bpy.utils.register_class(VIEW3D_PT_DropToFloorPanel)


def unregister():
    """Unregister the operator and panel from Blender."""
    bpy.utils.unregister_class(OBJECT_OT_DropToFloorOperator)
    bpy.utils.unregister_class(VIEW3D_PT_DropToFloorPanel)
