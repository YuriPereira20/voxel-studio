"""Frog wizard character from 4 user-supplied voxel views (reference/source*.webp), authored in code.

Resolution rule: 1 voxel per reference cube (~42 px), counted per view -> ~27 voxels tall (2.7 studs).
No Codex redraw and no image_to_layer: the sources sit on a dark red gradient with rim light, so every
part is authored from cube counts. Rim-lit yellow-green on the head sides is flattened to 2 greens.
Axes: x = character's LEFT (+x, image-right in the front view), -y = front (face), z = up.
Pivot = feet center on the ground (legs column center). Meshes are split for Roblox rigging.
Run in Blender: exec(open(r"D:\\GamesProjects\\VoxelStudio\\voxel_assets\\frog_wizard\\build.py").read())
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

import os

import numpy as np

R, C = vs.reference, vs.config
NAME = "frog_wizard"
HERE = os.path.join(C.ASSETS_DIR, NAME)
REF = os.path.join(HERE, "reference")
RD = os.path.join(HERE, "renders")

SIZE, ORIGIN = (21, 17, 29), (10, 8, 0)      # model x -10..10, y -8..8, z 0..28
LIME, SHADOW, MOUTH = "frog_lime", "frog_shadow", "frog_dark"
PURPLE, PURPLE_DK, RED = "purple_mid", "purple_dark", "scarlet"


# ---------------------------------------------------------------- body
def build_legs(m):
    for name, s in (("leg_l", 1), ("leg_r", -1)):
        g = m.add_part(name, SIZE, ORIGIN)
        xs = sorted((2 * s, 3 * s))                              # leg columns
        xo = sorted((2 * s, 4 * s))                              # foot columns (wider, outward)
        g.fill_box((xs[0], -1, 2), (xs[1], 0, 2), LIME)          # short leg
        g.fill_box((xs[0], -2, 1), (xs[1], 0, 1), LIME)          # top of foot
        g.fill_box((xo[0], -3, 0), (xo[1], 0, 0), LIME)          # foot sole, 3 wide
        g.remove(g.box((3 * s, -3, 0), (3 * s, -3, 0)))          # notch between the 2 webbed toes
        g.paint(SHADOW, where=lambda X, Y, Z: Z == 0)            # sole row a shade darker


def build_arms(m):
    for name, s in (("arm_l", 1), ("arm_r", -1)):
        g = m.add_part(name, SIZE, ORIGIN)
        g.fill_box((min(5 * s, 6 * s), -1, 5), (max(5 * s, 6 * s), 0, 7), LIME)
        g.fill_box((min(4 * s, 6 * s), -1, 7), (max(4 * s, 6 * s), 0, 7), LIME)   # shoulder reaches the torso
        g.paint(SHADOW, where=lambda X, Y, Z: Z == 5)            # hand underside


def build_torso(m):
    g = m.add_part("torso", SIZE, ORIGIN)
    g.fill_box((-3, -2, 3), (3, 2, 10), LIME)
    # cream belly bulging 1 voxel in front
    g.fill_box((-1, -3, 3), (1, -3, 3), "cream")
    g.fill_box((-2, -3, 4), (2, -3, 8), "cream")
    g.fill_box((-1, -3, 9), (1, -3, 9), "cream")
    g.paint("cream", where=lambda X, Y, Z: (Y == -2) & (abs(X) <= 2) & (Z >= 3) & (Z <= 9))
    # belt (z 6) all around + square gold buckle standing out of the belly
    g.paint("leather", where=lambda X, Y, Z: Z == 6)
    g.set((0, -4, 6), "gold_light")
    # pouch on the LEFT hip (+x), lid lighter, gold clasp
    g.fill_box((2, -3, 4), (4, -1, 5), "leather")
    g.fill_box((2, -4, 6), (4, -1, 6), "leather_light")         # lid overhangs the front
    g.set((3, -4, 5), "gold_light")                              # clasp under the lid
    return g


def cape_bottom(x, y):
    """Lowest capelet row per column: stepped V opening in front, stepped arch at the back, the drape over
    the arms (|x| >= 4) hangs 1 lower than the sides."""
    ax = abs(x)
    if y <= -2:
        return {0: 10, 1: 9, 2: 9, 3: 8}.get(ax, 7)
    if y >= 4:
        return {0: 9, 1: 9, 2: 8, 3: 8}.get(ax, 7)
    return 8


def build_cape(m, head):
    g = m.add_part("cape", SIZE, ORIGIN)
    # long back cape (skirt) down to the calves, red hem
    g.fill_box((-5, 1, 3), (5, 4, 8), PURPLE)
    g.paint(RED, where=lambda X, Y, Z: Z == 3)
    # capelet over the shoulders with stepped red trim
    for x in range(-7, 8):
        for y in range(-3, 6):
            if abs(x) == 7 and y in (-3, 5):
                continue                                      # round the corners
            zb = cape_bottom(x, y)
            top = 10 if abs(x) <= 6 and y <= 4 else 9         # tapers toward the neck
            if abs(x) == 7:
                top = 9
            if zb > top:
                continue
            g.fill_box((x, y, zb), (x, y, top), PURPLE)
            g.set((x, y, zb), RED)
    g.set((0, -3, 10), "gold_light")                          # clasp at the neck
    # collar around the chin, where the head isn't
    collar = g.box((-5, -2, 11), (5, 5, 11)) & (head.data == 0)
    g.fill_mask(collar, PURPLE)
    # brown strap crossing over the cape at the back
    g.fill_box((-4, 5, 6), (4, 5, 6), "leather")
    return g


# ---------------------------------------------------------------- head
def build_head(m):
    g = m.add_part("head", SIZE, ORIGIN)
    g.fill_box((-4, -2, 11), (4, 3, 11), SHADOW)                # chin, darker underneath
    g.fill_box((-5, -3, 12), (5, 4, 12), LIME)
    for z in (13, 14, 15):
        g.fill_box((-4, -3, z), (4, 4, z), LIME)
        g.fill_box((-5, -2, z), (5, 4, z), LIME)                # rounded front corners
        g.fill_box((-6, -1, z), (6, 3, z), LIME)
    g.fill_box((-4, -3, 16), (4, 3, 16), LIME)
    g.fill_box((-5, -2, 16), (5, 3, 16), LIME)
    for s in (1, -1):
        g.fill_box((min(2 * s, 5 * s), -3, 17), (max(2 * s, 5 * s), -1, 17), LIME)   # eye bumps
        g.fill_box((min(2 * s, 4 * s), -3, 14), (max(2 * s, 4 * s), -2, 16), "black")
        g.set((4 * s, -3, 16), "white")                          # highlight, upper-outer
        g.fill_box((min(4 * s, 5 * s), -3, 13), (max(4 * s, 5 * s), -2, 13), "blush_pink")
        g.set((6 * s, -1, 13), "blush_pink")                     # blush wraps to the side
    g.fill_box((-3, -4, 12), (3, -4, 13), LIME)                  # snout
    g.fill_box((-1, -4, 12), (1, -4, 12), MOUTH)                 # smile
    g.set((2, -4, 13), MOUTH)
    g.set((-2, -4, 13), MOUTH)
    g.paint(SHADOW, where=lambda X, Y, Z: (Z == 12) & ((abs(X) == 5) | (Y == 4)))
    return g


# cone rows: z -> (center x, radius x, radius y); the cone bends toward +x (character's left)
CONE = {20: (0, 5.2, 4.4), 21: (0.5, 4.7, 3.8), 22: (0.5, 4.0, 3.2), 23: (1, 3.3, 2.7),
        24: (2, 2.7, 2.2), 25: (3, 2.2, 1.7)}


def build_hat(m, glow):
    g = m.add_part("hat", SIZE, ORIGIN)
    X, Y, Z = g.coords()
    r = np.sqrt((X / 9.5) ** 2 + (Y / 7.5) ** 2)
    # brim, dark underneath; it thickens and droops only at the left/right ends (front stays clear of the eyes)
    ax = np.abs(X)
    for lo, hi, band in ((18, 19, ax <= 6), (17, 19, (ax >= 7) & (ax <= 8)), (16, 18, ax >= 9)):
        g.fill_mask((r <= 1) & band & (Z > lo) & (Z <= hi), PURPLE)
        g.fill_mask((r <= 1) & band & (Z == lo), PURPLE_DK)
    for z, (cx, rx, ry) in CONE.items():
        g.fill_mask((((X - cx) / rx) ** 2 + (Y / ry) ** 2 <= 1) & (Z == z), RED if z == 20 else PURPLE)
    g.fill_box((3, -1, 26), (6, 1, 26), PURPLE)                  # drooping tip
    g.fill_box((6, -1, 25), (7, 1, 25), PURPLE)
    g.set((8, 0, 25), PURPLE)
    g.set((8, 0, 24), "gold_light")                              # gold cap
    # red crystal: octahedral diamond, 4 tall, hanging under the cap
    for z, plus in ((23, False), (22, True), (21, True), (20, False)):
        glow.set((8, 0, z), "glow_red")
        if plus:
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                glow.set((8 + d[0], d[1], z), "glow_red")
    return g


def build():
    m = vs.VoxelModel(pivot=[0.5, 0.0, 0.0])                     # x: column 0 center, y: legs center
    head = build_head(m)
    glow = m.add_part("glow", SIZE, ORIGIN)
    build_hat(m, glow)
    build_torso(m)
    build_cape(m, head)
    build_arms(m)
    build_legs(m)
    return m


MESHES = {"head": ["head", "hat"], "torso": ["torso", "cape"], "arm_l": ["arm_l"], "arm_r": ["arm_r"],
          "leg_l": ["leg_l"], "leg_r": ["leg_r"], "glow": ["glow"]}


# ---------------------------------------------------------------- validation views
BG = "1F020B"                         # sRGB; the sources' dark red background
SOURCES = {"front_dark": "source.webp", "left": "source_left.webp", "back": "source_back.webp",
           "right": "source_right.webp"}

model = build()
k = C.bu_per_voxel()
extra = {v: {"background": BG} for v in ("left", "back", "right", "hero_34")}       # library presets
extra["front_dark"] = {"dir": [0, -1, 0], "res": [512, 768], "background": BG}
extra["closeup_gem"] = {"dir": [4, -8, 3], "res": [512, 512], "background": BG,
                        "region": [[k * 2, k * -4, k * 18], [k * 10, k * 4, k * 28]]}
result = vs.finalize(model, NAME, meshes=MESHES, emissive=("glow",), extra_views=extra)
result["compare"] = [R.compare_images(os.path.join(REF, src), os.path.join(RD, v + ".png"),
                                      os.path.join(RD, f"compare_{v.replace('_dark', '')}.png"))
                     for v, src in SOURCES.items()]
