bl_info = {
    "name": "LazyTools",
    "blender": (3, 0, 0),
    "category": "Object",
    "version": (1, 0, 0),
    "author": "Your Name",
    "description": "A collection of disparate tools including a custom wireframe tool and drop-to-floor."
}

import bpy
from . import wireframe_tool
from . import drop_to_floor

def register():
    wireframe_tool.register()
    drop_to_floor.register()

def unregister():
    wireframe_tool.unregister()
    drop_to_floor.unregister()

if __name__ == "__main__":
    register()
