bl_info = {
    "name": "Custom Wireframe with Profiles",
    "blender": (3, 0, 0),
    "category": "Object",
    "version": (1, 0, 0),
    "author": "Your Name",
    "description": "Generate custom wireframe-like structures with square, round profiles and close gaps using convex hulls."
}

import bpy
import bmesh
import math
from mathutils import Matrix, Vector
from typing import List, Dict


# Define a PropertyGroup to store our custom properties
class CustomWireframeProperties(bpy.types.PropertyGroup):
    profile_type: bpy.props.EnumProperty(
        name="Profile Type",
        description="Type of profile to extrude",
        items=[('SQUARE', "Square", ""), ('ROUND', "Round", "")],
        default='SQUARE'
    )
    size: bpy.props.FloatProperty(
        name="Profile Size",
        description="Size of the profile",
        default=0.05,
        min=0.001,
        max=10.0
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        description="Number of segments (for round profiles)",
        default=12,
        min=3,
        max=64
    )
    delete_original_faces: bpy.props.BoolProperty(
        name="Delete Original Faces",
        description="Delete original mesh faces before extrusion",
        default=True
    )

def create_profile(shape_type: str = 'SQUARE', size: float = 0.05, segments: int = 12) -> List[Vector]:
    """Create a 3D profile shape (square or round) based on input parameters."""
    if shape_type == 'SQUARE':
        verts = [(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)]
    elif shape_type == 'ROUND':
        verts = [
            (math.cos(i * 2 * math.pi / segments) * size, math.sin(i * 2 * math.pi / segments) * size, 0)
            for i in range(segments)
        ]
    else:
        raise ValueError("Unsupported profile type")
    return [Vector(v) for v in verts]

def apply_object_scale(obj: bpy.types.Object) -> None:
    """Apply the object's scale to ensure proper dimensions before extrusion."""
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

def delete_faces(mesh_obj: bpy.types.Object) -> None:
    """Delete the faces of the selected object, keeping only the edges and vertices."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    bmesh.ops.delete(bm, geom=bm.faces[:], context='FACES_ONLY')
    bmesh.update_edit_mesh(mesh_obj.data)

def merge_prism_vertices(new_obj: bpy.types.Object, merge_threshold: float = 0.0001) -> None:
    """Merge nearby vertices in the new object to close small gaps between prisms."""
    bpy.context.view_layer.objects.active = new_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(new_obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)
    bmesh.update_edit_mesh(new_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

def close_corner_with_convex_hull(new_bm: bmesh.types.BMesh, corner_profiles: List[List[bmesh.types.BMVert]]) -> None:
    """Close the corner where multiple edges meet using a convex hull to form a smooth surface."""
    corner_verts = []
    for profile in corner_profiles:
        corner_verts.extend(profile)
    if len(corner_verts) > 3:
        bmesh.ops.convex_hull(new_bm, input=corner_verts)

def extrude_profiles_along_edges(
    mesh_obj: bpy.types.Object,
    profile_type: str = 'SQUARE',
    size: float = 0.05,
    segments: int = 12,
    delete_original_faces: bool = False,
    merge_threshold: float = 0.0001
) -> None:
    """Extrude profiles along the edges of the selected mesh object, centering them on each edge."""
    apply_object_scale(mesh_obj)
    if delete_original_faces:
        delete_faces(mesh_obj)

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)

    # Create a new object to hold the extruded profiles
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
        obj = context.active_object
        props = context.scene.custom_wireframe_props
        if obj and obj.type == 'MESH':
            extrude_profiles_along_edges(
                obj,
                profile_type=props.profile_type,
                size=props.size,
                segments=props.segments,
                delete_original_faces=props.delete_original_faces,
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
    bl_category = 'Custom Wireframe'

    def draw(self, context):
        layout = self.layout
        props = context.scene.custom_wireframe_props

        layout.prop(props, "profile_type")
        layout.prop(props, "size")
        layout.prop(props, "segments")
        layout.prop(props, "delete_original_faces")
        layout.operator("object.custom_wireframe_operator", text="Run Custom Wireframe")

def register():
    bpy.utils.register_class(CustomWireframeProperties)
    bpy.types.Scene.custom_wireframe_props = bpy.props.PointerProperty(type=CustomWireframeProperties)
    bpy.utils.register_class(OBJECT_OT_CustomWireframeOperator)
    bpy.utils.register_class(VIEW3D_PT_CustomWireframePanel)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_CustomWireframePanel)
    bpy.utils.unregister_class(OBJECT_OT_CustomWireframeOperator)
    del bpy.types.Scene.custom_wireframe_props
    bpy.utils.unregister_class(CustomWireframeProperties)

if __name__ == "__main__":
    register()
