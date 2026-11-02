"""VoxelStudio: voxel-art assets for Roblox, built in Blender.

    Bootstrap at the top of voxel_assets/<name>/build.py (purges a stale copy, then loads this project):

    import sys
    LIB = r"D:\\GamesProjects\\VoxelStudio\\plugin\\skills\\voxel-asset"
    PROJECT = r"D:\\GamesProjects\\VoxelStudio"
    for _m in [m for m in sys.modules if m == "voxelstudio" or m.startswith("voxelstudio.")]:
        del sys.modules[_m]
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    import voxelstudio
    vs = voxelstudio.reload_all(project=PROJECT)
"""
from . import config, grid, mesher, reference, blender_io
from .grid import VoxelGrid, VoxelModel
from .blender_io import finalize


def reload_all(project=None):
    """Reload every submodule (config first, so JSON edits apply) and the package; returns the package.

    project: folder holding voxel_assets/ and an optional voxel_config.json (default: the plugin config).
    """
    import importlib
    import os
    import sys
    if project:
        os.environ["VOXELSTUDIO_PROJECT"] = project  # config reads it when reloaded below
    for m in (config, grid, mesher, reference, blender_io):
        importlib.reload(m)
    return importlib.reload(sys.modules[__name__])
