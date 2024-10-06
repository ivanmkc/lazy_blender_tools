"""
File: profiled_wireframe.py

Description:
This script is part of the LazyTools package, providing a customizable wireframe tool.
It allows users to generate wireframe-like structures with custom profile extrusions (square, round, triangle),
along the edges of selected mesh objects. Unlike Blender's built-in Wireframe Modifier, this tool supports 
custom cross-sectional profiles, including round, square, and triangular shapes, with optional face deletion 
and vertex merging to clean up the geometry.

This tool is unique because it provides:
- Custom profiles (square, round, triangle) instead of just a uniform wireframe thickness.
- Options to control the number of segments for round profiles.
- The ability to clean up and merge vertices for smoother results at junctions.
- Convex hull closing of corners where multiple prisms meet.

Usage:
- Access this tool via the LazyTools UI panel in Blender's 3D Viewport (under the Tool tab).
- Select a mesh object and adjust parameters such as profile type, size, and whether to delete faces before extrusion.
- Press the "Run Custom Wireframe" button to execute the operation.

"""

import bpy
import bmesh
import math
from mathutils import Matrix, Vector
from typing import List, Dict


def create_profile(shape_type: str = 'SQUARE', size: float = 0.05, segments: int = 12) -> List[Vector]:
    """
    Create a 3D profile shape (square, round, or triangle) based on input parameters.

    Args:
    - shape_type: Type of the profile shape ('SQUARE', 'ROUND', or 'TRIANGLE').
    - size: Size of the profile (side length for square and triangle, radius for round).
    - segments: Number of segments for round profiles (ignored for square and triangle).

    Returns:
    - A list of Vector objects representing the vertices of the profile.
    """
    if shape_type == 'SQUARE':
        verts = [(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)]
    elif shape_type == 'ROUND':
        verts = [(math.cos(i * 2 * math.pi / segments) * size, math.sin(i * 2 * math.pi / segments) * size, 0) for i in range(segments)]
    elif shape_type == 'TRIANGLE':
        verts = [(0, size, 0), (-size, -size, 0), (size, -size, 0)]
    else:
        raise ValueError("Unsupported profile type")
    return [Vector(v) for v in verts]


def apply_object_scale(obj: bpy.types.Object) -> None:
    """
    Apply the object's scale so that extrusion operates with proper dimensions.
    
    Args:
    - obj: The mesh object whose scale will be applied.
    """
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def delete_faces(mesh_obj: bpy.types.Object) -> None:
    """
    Delete only the faces of the selected object while keeping the edges and vertices intact.
    
    Args:
    - mesh_obj: The mesh object from which faces will be deleted.
    """
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    bmesh.ops.delete(bm, geom=bm.faces[:], context='FACES_ONLY')
    bmesh.update_edit_mesh(mesh_obj.data)


def merge_prism_vertices(new_obj: bpy.types.Object, merge_threshold: float = 0.0001) -> None:
    """
    Merge nearby vertices in the new mesh to clean up small gaps between prisms.
    
    Args:
    - new_obj: The new object where vertices will be merged.
    - merge_threshold: The distance threshold for merging nearby vertices.
    """
    bpy.context.view_layer.objects.active = new_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(new_obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)
    bmesh.update_edit_mesh(new_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')


def close_corner_with_convex_hull(new_bm: bmesh.types.BMesh, corner_profiles: List[List[bmesh.types.BMVert]]) -> None:
    """
    Use a convex hull operation to close gaps at corners where multiple profiles meet.

    Args:
    - new_bm: The BMesh representation of the new mesh where the convex hull will be applied.
    - corner_profiles: A list of profile vertex lists representing the profiles at a given corner.
    """
    corner_verts = []
    for profile in corner_profiles:
        corner_verts.extend(profile)
    if len(corner_verts) > 3:  # Convex hull requires at least 4 vertices
        bmesh.ops.convex_hull(new_bm, input=corner_verts)


def extrude_profiles_along_edges(
    mesh_obj: bpy.types.Object, 
    profile_type: str = 'SQUARE', 
    size: float = 0.05, 
    segments: int = 12, 
    delete_original_faces: bool = False, 
    merge_threshold: float = 0.0001
) -> None:
    """
    Extrude profiles (square, round, or triangle) along the edges of a mesh object.
    
    Args:
    - mesh_obj: The mesh object along whose edges the profiles will be extruded.
    - profile_type: The type of profile ('SQUARE', 'ROUND', or 'TRIANGLE').
    - size: The size of the profile (side length for square/triangle or radius for round).
    - segments: Number of segments for round profiles (ignored for square and triangle).
    - delete_original_faces: Whether to delete the original mesh faces before extrusion.
    - merge_threshold: Distance threshold for merging vertices in the resulting mesh.
    """
    apply_object_scale(mesh_obj)
    if delete_original_faces:
        delete_faces(mesh_obj)
    
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)

    new_mesh = bpy.data.meshes.new('ProfiledMesh')
    new_obj = bpy.data.objects.new('ProfiledObject', new_mesh)
    bpy.context.collection.objects.link(new_obj)
    new_bm = bmesh.new()

    profile_shape = create_profile(profile_type, size, segments)
    profiles_at_corners: Dict[Vector, List[List[bmesh.types.BMVert]]] = {}

    for edge in bm.edges:
        edge_verts = edge.verts[:]
        if len(edge_verts) == 2:
            v1, v2 = edge_verts
            edge_vector = v2.co - v1.co
            edge_direction = edge_vector.normalized()
            z_axis = Vector((0, 0, 1))
            rot_matrix = edge_direction.rotation_difference(z_axis).to_matrix().to_4x4()
            
            profiles = []
            for vert in (v1.co, v2.co):
                trans_matrix = Matrix.Translation(vert)
                transformation_matrix = trans_matrix @ rot_matrix
                profile_verts = [transformation_matrix @ p for p in profile_shape]
                profiles.append(profile_verts)
            
            start_verts = [new_bm.verts.new(vert) for vert in profiles[0]]
            end_verts = [new_bm.verts.new(vert) for vert in profiles[1]]
            
            # Create lateral faces between start and end profiles
            for i in range(len(start_verts)):
                new_bm.faces.new([
                    start_verts[i],
                    end_verts[i],
                    end_verts[(i + 1) % len(start_verts)],
                    start_verts[(i + 1) % len(start_verts)]
                ])
            
            v1_frozen = v1.co.copy().freeze()
            v2_frozen = v2.co.copy().freeze()

            if v1_frozen not in profiles_at_corners:
                profiles_at_corners[v1_frozen] = []
            profiles_at_corners[v1_frozen].append(start_verts)

            if v2_frozen not in profiles_at_corners:
                profiles_at_corners[v2_frozen] = []
            profiles_at_corners[v2_frozen].append(end_verts)

    for corner, corner_profiles in profiles_at_corners.items():
        if len(corner_profiles) > 1:
            close_corner_with_convex_hull(new_bm, corner_profiles)

    new_bm.to_mesh(new_mesh)
    new_bm.free()

    merge_prism_vertices(new_obj, merge_threshold)


class OBJECT_OT_CustomWireframeOperator(bpy.types.Operator):
    """Extrude profiles along edges"""
    bl_idname = "object.custom_wireframe_operator"
    bl_label = "Custom Wireframe Operator"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        profile_type = scene.custom_wireframe_profile_type
        size = scene.custom_wireframe_size
        segments = scene.custom_wireframe_segments
        delete_faces = scene.custom_wireframe_delete_faces

        obj = context.active_object
        if obj and obj.type == 'MESH':
            extrude_profiles_along_edges(
                obj,
                profile_type=profile_type,
                size=size,
                segments=segments,
                delete_original_faces=delete_faces,
                merge_threshold=0.0001
            )
        else:
            self.report({'WARNING'}, "Select a mesh object.")
        return {'FINISHED'}


class VIEW3D_PT_CustomWireframePanel(bpy.types.Panel):
    """Panel for the custom wireframe operator"""
    bl_label = "Custom Wireframe Tool"
    bl_idname = "VIEW3D_PT_custom_wireframe"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LazyTools'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "custom_wireframe_profile_type")
        layout.prop(scene, "custom_wireframe_size")
        layout.prop(scene, "custom_wireframe_segments")
        layout.prop(scene, "custom_wireframe_delete_faces")
        layout.operator("object.custom_wireframe_operator", text="Run")


def register():
    bpy.utils.register_class(OBJECT_OT_CustomWireframeOperator)
    bpy.utils.register_class(VIEW3D_PT_CustomWireframePanel)
    
    # Define custom properties for the tool
    bpy.types.Scene.custom_wireframe_profile_type = bpy.props.EnumProperty(
        name="Profile Type",
        description="Type of profile to extrude",
        items=[('SQUARE', "Square", ""), ('ROUND', "Round", ""), ('TRIANGLE', "Triangle", "")],
        default='SQUARE'
    )
    bpy.types.Scene.custom_wireframe_size = bpy.props.FloatProperty(
        name="Profile Size",
        description="Size of the profile",
        default=0.05,
        min=0.001,
        max=1.0
    )
    bpy.types.Scene.custom_wireframe_segments = bpy.props.IntProperty(
        name="Segments",
        description="Number of segments (for round profiles)",
        default=12,
        min=3,
        max=64
    )
    bpy.types.Scene.custom_wireframe_delete_faces = bpy.props.BoolProperty(
        name="Delete Original Faces",
        description="Delete original mesh faces before extrusion",
        default=True
    )


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_CustomWireframeOperator)
    bpy.utils.unregister_class(VIEW3D_PT_CustomWireframePanel)

    del bpy.types.Scene.custom_wireframe_profile_type
    del bpy.types.Scene.custom_wireframe_size
    del bpy.types.Scene.custom_wireframe_segments
    del bpy.types.Scene.custom_wireframe_delete_faces


if __name__ == "__main__":
    register()
