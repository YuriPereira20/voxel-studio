"""Small stylized voxel tree: trunk with roots/branches + clumpy three-green canopy. Model z=0 = ground.
Run in Blender: exec(open(r"D:\\GamesProjects\\VoxelStudio\\voxel_assets\\tree\\build.py").read())
"""
import sys
LIB = r"D:\GamesProjects\VoxelStudio\plugin\skills\voxel-asset"
PROJECT = r"D:\GamesProjects\VoxelStudio"
for _m in [m for m in sys.modules if m == "voxelstudio" or m.startswith("voxelstudio.")]:
    del sys.modules[_m]
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import voxelstudio
vs = voxelstudio.reload_all(project=PROJECT)

import numpy as np

SEED = 7


def build():
    m = vs.VoxelModel()
    size, origin = (31, 31, 50), (15, 15, 0)

    trunk = m.add_part("trunk", size, origin)
    trunk.fill_cylinder((0, 0, 0), 2.8, 28, "wood")
    trunk.fill_cylinder((0, 0, 0), 3.6, 3, "wood")                     # flared base
    for end in ((5, 1, 0), (-4, 4, 0), (-2, -5, 0)):                   # roots
        trunk.line((0, 0, 3), end, "wood", radius=1.3)
    for end in ((7, 3, 27), (-7, -2, 28), (1, -6, 29)):                # branches, hidden inside the canopy
        trunk.line((0, 0, 20), end, "wood", radius=1.0)
    trunk.paint("wood_dark", where=trunk.noise(cell=(1, 1, 7), seed=SEED) > 0.72)  # vertical bark streaks

    canopy = m.add_part("canopy", size, origin)
    blobs = [((0, 0, 32), (12, 12, 9)), ((7, 3, 27), (7, 7, 5.5)), ((-7, -2, 28), (7, 7, 5.5)),
             ((1, -6, 29), (6.5, 6.5, 5)), ((-2, 3, 40), (8, 8, 6)), ((4, -1, 38), (6.5, 6.5, 5.5))]
    for c, r in blobs:
        canopy.fill_ellipsoid(c, r, "leaf_mid")
    core = np.zeros(canopy.data.shape, bool)
    for c, r in blobs:
        core |= canopy.ellipsoid(c, [x * 0.8 for x in r])
    canopy.remove((canopy.noise(cell=2, seed=SEED + 1) > 0.72) & ~core)  # bumpy outline
    canopy.keep_largest()  # noise can cut off single leaves

    # shade by height + clumpy noise: dark underneath, light on top
    X, Y, Z = canopy.coords()
    t = (Z - 21) / 26 + (canopy.noise(cell=3, seed=SEED + 2) - 0.5) * 0.45
    canopy.paint("leaf_dark", where=t < 0.38)
    canopy.paint("leaf_light", where=t > 0.72)
    return m


result = vs.finalize(build(), "tree")
