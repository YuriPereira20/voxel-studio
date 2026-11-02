"""Stylized medieval longsword (library rebuild of prototype/sword_voxel.py).

Model coords: x = crossguard axis, y = thickness, z = sword axis; model z=0 is the grip center (Tool grip).
Run in Blender: exec(open(r"D:\\GamesProjects\\VoxelStudio\\voxel_assets\\sword\\build.py").read())
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


def build():
    m = vs.VoxelModel()

    pommel = m.add_part("pommel", size=(5, 5, 5), origin=(2, 2, 0), offset=(0, 0, -10))
    pommel.fill_box((-2, -2, 1), (2, 2, 3), "gold_light")
    pommel.remove(lambda x, y, z: (abs(x) == 2) & (abs(y) == 2))       # round the corners
    pommel.fill_box((-1, -1, 0), (1, 1, 0), "gold_dark")
    pommel.fill_box((-1, -1, 4), (1, 1, 4), "gold_dark")
    pommel.set((0, 2, 2), "gem_red")
    pommel.set((0, -2, 2), "gem_red")

    grip = m.add_part("grip", size=(3, 3, 10), origin=(1, 1, 0), offset=(0, 0, -5))
    grip.fill_box((-1, -1, 0), (1, 1, 9), "leather")
    grip.paint("leather_dark", where=lambda x, y, z: z % 2 == 1)      # wrap bands

    guard = m.add_part("guard", size=(15, 5, 4), origin=(7, 2, 0), offset=(0, 0, 5))
    guard.fill_box((0, -1, 0), (5, 1, 1), "gold_light")                # right arm
    guard.fill_box((6, -1, 0), (6, 1, 2), "gold_light")                # flare
    guard.fill_box((7, -1, 1), (7, 1, 3), "gold_light")                # upturned tip
    guard.fill_box((0, -2, 0), (2, 2, 2), "gold_light")                # center block
    guard.paint("gold_dark", where=guard.box((0, -2, 0), (6, 2, 0)))   # darker underside
    guard.paint("gold_dark", where=guard.box((7, -1, 1), (7, 1, 1)))
    guard.mirror("x")
    guard.set((0, 2, 1), "gem_blue")
    guard.set((0, -2, 1), "gem_blue")

    blade = m.add_part("blade", size=(5, 3, 32), origin=(2, 1, 0), offset=(0, 0, 8))
    blade.fill_box((-2, 0, 0), (2, 0, 25), "steel_light")              # 1-thick flats, bright edges
    blade.fill_box((-1, -1, 0), (1, 1, 25), "steel_mid")               # 3-thick core
    blade.fill_box((-1, 0, 26), (1, 0, 29), "steel_light")             # taper
    blade.fill_box((0, -1, 26), (0, 1, 29), "steel_mid")
    blade.fill_box((0, 0, 30), (0, 0, 31), "steel_light")              # point
    blade.paint("steel_dark", where=blade.box((0, -1, 0), (0, 1, 22)))  # fuller line
    return m


result = vs.finalize(build(), "sword")
