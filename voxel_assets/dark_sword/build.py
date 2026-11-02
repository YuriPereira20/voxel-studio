"""Dark-fantasy greatsword from the user's reference (source.webp), via the Codex front redraw (front.png).

Image-based standard: 1 voxel per reference cube. front.png cube pitch = 9.06 px (reference.cube_pitch),
content 1215 x 435 px -> 134 x 49 layer = 13.4 x 4.9 studs at 0.1 stud/voxel (scaled down at Roblox import).
The layer is the base: silhouette, chips, plates, grooves, slashes, wear speckle, guard, horns, cloth and
crack all come from it. By hand: palette roles per region (baked shading -> clean colors), symmetry of
pommel/collar/guard/skull, runes, grip wrap, rivets, and the whole depth profile.
x = guard axis (col - 24), y = depth (-y = front), z = up (pivot = grip center, layer row 19).
Run in Blender: exec(open(r"D:\\GamesProjects\\VoxelStudio\\voxel_assets\\dark_sword\\build.py").read())
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
N = C.INDEX

HERE = os.path.join(vs.config.ASSETS_DIR, "dark_sword")
REF = os.path.join(HERE, "reference")
FRONT = os.path.join(REF, "front.png")
ROWS, COLS, CX, YR = 134, 49, 24, 10
GRIP_ROW = 19
# Quantize against fixed, general palette colors used as luminance/hue classes, so retuning this asset's
# own colors (steel_worn_*, bone, cloth...) never changes the layer. Classes are remapped per region below.
QUANT = ["white", "metal_light", "stone_light", "stone_mid", "stone_dark", "iron_mid", "iron_black", "black",
         "gem_red", "cloth_red", "cloth_red_dark", "leather_dark"]
LIGHT = {N["white"], N["metal_light"], N["stone_light"]}
MID = {N["stone_mid"]}
DARK = {N["stone_dark"]}
IRON = {N["iron_mid"]}
BLACK = {N["iron_black"], N["black"]}
RED = {N["cloth_red"], N["cloth_red_dark"], N["leather_dark"]}
RED_DARK = {N["cloth_red_dark"], N["leather_dark"]}
GLOW = N["gem_red"]

RUNES = [  # 5x5 glyphs, not letters: trident, barred box, dotted diamond, snowflake
    ["X.X.X", "X.X.X", ".XXX.", "..X..", "..X.."],
    ["X...X", ".XXX.", ".X.X.", ".XXX.", "X...X"],
    ["..X..", ".X.X.", "X.X.X", ".X.X.", "..X.."],
    ["X.X.X", ".XXX.", "..X..", ".XXX.", "X.X.X"],
]
RUNE_TOPS = [46, 53, 60, 67]
SKULL_HW = [2, 3, 4, 4, 4, 4, 4, 4, 3, 3, 2]   # skull half-width per row, rows 32..42
SKULL_TOP = 32
RIVETS = [(x, 34) for x in (-7, 7, -11, 11, -15, 15)] + [(x, 29) for x in (-3, 0, 3)]


def front_layer():
    L = R.image_to_layer(FRONT, width_voxels=COLS, height_voxels=ROWS,
                         exclude=[n for n in C.NAMES if n not in QUANT])
    L = R.clean_layer(L)
    for r in list(range(0, 11)) + list(range(28, 44)):   # pommel, collar, guard, skull: symmetric
        L[r, CX + 1:] = L[r, :CX][::-1]
    return L


def fill(g, col, row, y0, y1, color):
    g.data[col, y0 + YR:y1 + YR + 1, ROWS - 1 - row] = N[color] if isinstance(color, str) else color


def bridge(m):
    """Make diagonal-only contacts 4-connected so 2D cloth extrudes as one piece."""
    m = m.copy()
    for r in range(m.shape[0] - 1):
        for c in range(1, m.shape[1] - 1):
            if m[r, c] and not m[r + 1, c] and ((m[r + 1, c - 1] and not m[r, c - 1]) or
                                                (m[r + 1, c + 1] and not m[r, c + 1])):
                m[r + 1, c] = True
    return m


def metal(v):
    """Guard / pommel / collar shading -> clean iron tones (no bright metal on big flats)."""
    if v in LIGHT or v in MID:
        return "iron_lit"
    if v in DARK or v in IRON:
        return "iron_mid"
    return "iron_black"


# ----------------------------------------------------------------------------- hilt
def build_pommel(g, glow, L):
    for r in range(0, 11):
        cols = np.nonzero(L[r])[0]
        hy = int(np.clip(round((cols.max() - cols.min()) / 2), 1, 5))   # round knob: depth ~ width
        for c in cols:
            if L[r, c] == GLOW:
                fill(g, c, r, -hy + 1, hy - 1, "iron_black")
                for y in (-hy, hy):
                    fill(glow, c, r, y, y, "glow_red")
            else:
                fill(g, c, r, -hy, hy, metal(L[r, c]))


def build_grip(g):
    """7x7 dark core with a raised crisscross wrap (period 7 divides the 28-voxel perimeter: no seam)."""
    for r in range(11, 28):
        for c in range(CX - 3, CX + 4):
            fill(g, c, r, -3, 3, "leather_red_dark")
        ring = [(x, -4) for x in range(-3, 4)] + [(4, y) for y in range(-3, 4)] + \
               [(x, 4) for x in range(3, -4, -1)] + [(-4, y) for y in range(3, -4, -1)]
        for t, (x, y) in enumerate(ring):
            if (r + t) % 7 < 2 or (r - t) % 7 < 2:
                fill(g, CX + x, r, y, y, "leather_red")


def build_collar(g, L):
    for r in range(28, 31):
        for c in np.nonzero(L[r])[0]:
            fill(g, c, r, -5, 5, metal(L[r, c]))


# ----------------------------------------------------------------------------- guard + skull
def build_guard(g, cloth, L):
    for r in range(31, 44):
        for c in np.nonzero(L[r])[0]:
            v = L[r, c]
            if (v in RED or v == GLOW) and not 13 <= c <= 35:      # cloth wrapped around the guard
                fill(cloth, c, r, -5, 5, "blood_red" if v in RED_DARK else "cloth_crimson")
            else:
                fill(g, c, r, -4, 4, metal(v))
    for x, r in RIVETS:
        fill(g, CX + x, r, -6 if r < 31 else -5, 6 if r < 31 else 5, "metal_light")


def build_skull(g, glow, L):
    for k, hw in enumerate(SKULL_HW):
        r = SKULL_TOP + k
        for dx in range(-hw, hw + 1):
            c = CX + dx
            e = min(hw - abs(dx), k, len(SKULL_HW) - 1 - k)
            p = (3, 5, 6)[min(e, 2)]                         # protrusion: rounded head, 6 at the center
            v = L[r, c]
            if v == GLOW:                                    # eye: glowing socket floor
                fill(g, c, r, -(4 + p - 3), 4 + p - 3, "iron_black")
                for y in (-(4 + p - 2), 4 + p - 2):
                    fill(glow, c, r, y, y, "glow_red")
            elif v in BLACK or v in RED:                     # socket / nose / teeth gaps: recessed 2
                fill(g, c, r, -(4 + p - 2), 4 + p - 2, "iron_black")
            else:
                fill(g, c, r, -(4 + p), 4 + p, "bone" if (v in LIGHT or v in MID) else "bone_shadow")
    for s in (-1, 1):                                        # horns curling up and out of the head
        for x, r, col in ((3, 32, "bone_shadow"), (4, 32, "bone_shadow"), (4, 31, "bone_shadow"),
                          (5, 31, "bone_shadow"), (5, 30, "bone"), (5, 29, "bone")):
            for y in (-7, -6, -5, 5, 6, 7):
                fill(g, CX + s * x, r, y, y, col)


# ----------------------------------------------------------------------------- blade
def fuller_hw(r):
    return 2 if r <= 81 else 1 if r <= 104 else 0 if r <= 107 else None


def build_blade(g, glow, L):
    crack = np.zeros(L.shape, bool)
    blade_zone = np.zeros(L.shape, bool)
    blade_zone[44:, 12:37] = True
    # black / glow pixels on the flats: strokes (slashes, crack branches) stay, specks are quantized cube seams
    slashes = R.prune_specks(blade_zone & np.isin(L, list(BLACK)), 4)
    branches = R.prune_specks(blade_zone & (L == GLOW), 3)
    for r in range(44, ROWS):
        row = L[r]
        cols = [c for c in range(12, 37) if row[c]]
        runs = np.split(np.array(cols), np.nonzero(np.diff(cols) > 1)[0] + 1) if cols else []
        hf = fuller_hw(r)
        for run in runs:
            a, b = run[0], run[-1]
            for c in run:
                v, dx = row[c], c - CX
                e = min(c - a, b - c)
                h = (1, 2, 3)[min(e, 2)]                      # chipped edge 3 thick -> core 7
                if hf is not None and abs(dx) <= hf:           # fuller floor, recessed 2
                    in_runes = 44 <= r < 74                    # clean gap between the last rune and the crack
                    halo = v in (N["cloth_red"], N["cloth_red_dark"]) and not in_runes   # red light by the crack
                    col = "blood_red" if halo else "iron_black"
                    fill(g, c, r, -1, 1, col)
                    if v == GLOW and not in_runes:
                        crack[r, c] = True
                    continue
                if hf is not None and abs(dx) == hf + 1:       # fuller wall
                    fill(g, c, r, -3, 3, "iron_black")
                    continue
                if v in IRON:                                  # raised bevel plate, darker than the flats
                    h, col = 4, "steel_worn_dark"
                elif v in BLACK and slashes[r, c]:             # groove / slash, carved 1
                    h, col = max(1, h - 1), "iron_black"
                elif v in BLACK:
                    col = "steel_worn_dark"
                elif v in RED or (v == GLOW and (not branches[r, c] or e == 0)):
                    col = "blood_red"                          # stains, and bloody (not glowing) edges
                elif v == GLOW:
                    col = "blood_red"
                    crack[r, c] = r >= 74
                else:
                    col = "steel_worn_light" if v in LIGHT else "steel_worn_mid" if v in MID else "steel_worn_dark"
                fill(g, c, r, -h, h, col)
    # runes on both groove floors
    for top, glyph in zip(RUNE_TOPS, RUNES):
        for k, line in enumerate(glyph):
            for dx, ch in zip(range(-2, 3), line):
                if ch == "X":
                    for y in (-1, 1):
                        fill(glow, CX + dx, top + k, y, y, "glow_red")
    # crack: layer glow pixels, gaps of one row bridged, placed on the surface of whatever is there
    for r in range(74, ROWS - 2):
        for c in np.nonzero(crack[r])[0]:
            if not crack[r + 1, max(0, c - 1):c + 2].any() and crack[r + 2, max(0, c - 1):c + 2].any():
                crack[r + 1, c] = True
    for r, c in np.argwhere(crack):
        ys = np.nonzero(g.data[c, :, ROWS - 1 - r])[0] - YR
        if len(ys) > 1:
            for y in (ys.min(), ys.max()):
                fill(glow, c, r, y, y, "glow_red")


# ----------------------------------------------------------------------------- cloth
FOLD = [0, 1, 1, 0, -1, -1]


def hang(cloth, L, mask):
    """2-thick sheet in the x-z plane, rippled in y by column/row so it reads as folds, not a cutout."""
    for r, c in np.argwhere(mask):
        f = FOLD[(c + r // 5) % 6]
        v = L[r, c]
        col = "cloth_crimson" if (v not in RED_DARK and f >= 0) else "blood_red"
        fill(cloth, c, r, f - 1, f, col)


def build_cloth(cloth, L):
    strips = np.zeros(L.shape, bool)
    strips[44:60, :13] = L[44:60, :13] > 0
    strips[44:60, 36:] = L[44:60, 36:] > 0
    hang(cloth, L, bridge(strips))
    tassel = np.zeros(L.shape, bool)
    tassel[12:28, 28:42] = L[12:28, 28:42] > 0
    hang(cloth, L, bridge(tassel))


# ----------------------------------------------------------------------------- model
def build():
    L = front_layer()
    m = vs.VoxelModel()
    size, origin = (COLS, 2 * YR + 1, ROWS), (CX, YR, ROWS - 1 - GRIP_ROW)
    blade, guard, hilt, cloth, glow = (m.add_part(n, size, origin) for n in ("blade", "guard", "hilt", "cloth", "glow"))
    build_pommel(hilt, glow, L)
    build_grip(hilt)
    build_collar(hilt, L)
    build_guard(guard, cloth, L)
    build_skull(guard, glow, L)
    build_blade(blade, glow, L)
    build_cloth(cloth, L)
    for p in (blade, guard, hilt, cloth):        # glow replaces whatever body voxel is there
        p.data[glow.data > 0] = 0
    body = m.merged(["blade", "guard", "hilt", "cloth"])
    stray = [len(p) for p in body.pieces()[1:]]          # floating bits from quantization, reported + removed
    for p in (blade, guard, hilt, cloth):
        p.data[(p.data > 0) & (body.data == 0)] = 0
    keep = body.copy()
    keep.keep_largest()
    for p in (blade, guard, hilt, cloth):
        p.data[keep.data == 0] = 0
    return m, L, stray


def k(x):  # layer col/row -> BU for close-up framing
    return x * C.bu_per_voxel()


model, layer, removed = build()
closeup = {"dir": [-4, -8, 3], "res": [768, 768],
           "region": [[k(-24), k(-10), k(GRIP_ROW - 75)], [k(25), k(10), k(GRIP_ROW - 26)]]}
result = vs.finalize(model, "dark_sword",
                     meshes={"body": ["blade", "guard", "hilt", "cloth"], "glow": ["glow"]},
                     emissive=("glow",), extra_views={"closeup": closeup})
result["floating_removed"] = removed
rd = os.path.join(HERE, "renders")
result["compare"] = [R.compare_images(FRONT, os.path.join(rd, "front.png"), os.path.join(rd, "compare_front.png")),
                     R.compare_images(os.path.join(REF, "source.webp"), os.path.join(rd, "hero.png"),
                                      os.path.join(rd, "compare_source.png"), bg_tolerance=0.12)]
