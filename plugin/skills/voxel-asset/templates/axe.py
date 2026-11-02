"""Voxel axe built FROM reference/front.png (silhouette + colors via image_to_layer) and side.png (depth).

Resolution: 45 rows (4.5 studs at 0.1 stud/voxel, the size standard) instead of the reference's ~35-cube
grid; the head and blade survive the 1.3x resample fine, the handle/wrap/pommel are regularized by hand.
Model coords: x = toward the blade, z = up, y = depth; pivot = center of the wrap (Tool grip).
Run in Blender: exec(open(r"<PROJECT>\\voxel_assets\\axe\\build.py").read())
"""
import sys
LIB = r"<LIB>"
PROJECT = r"<PROJECT>"
for _m in [m for m in sys.modules if m == "voxelstudio" or m.startswith("voxelstudio.")]:
    del sys.modules[_m]
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import voxelstudio
vs = voxelstudio.reload_all(project=PROJECT)

import os

import numpy as np

R, C = vs.reference, vs.config

HERE = os.path.join(vs.config.ASSETS_DIR, "axe")
FRONT = os.path.join(HERE, "reference", "front.png")
ROWS = 45
HANDLE = slice(2, 6)          # layer columns of the handle (4 wide, centered on x = 0)
X0 = -4                       # layer column 0 -> model x
Z0 = -10                      # layer bottom row -> model z (wrap center lands on z = 0)


def front_layer():
    # quantize only against the palette as it was when this layer was approved (the first 34 colors), so
    # colors appended later for other assets can't change it; metal_* are assigned afterwards
    quant = C.NAMES[:34]
    L = R.clean_layer(R.image_to_layer(FRONT, height_voxels=ROWS,
                                       exclude=[n for n in C.NAMES if n not in quant]))
    assert L.shape[0] == ROWS
    i = C.idx
    # Hand fixes (row/col numbers refer to the 45-row layer; see report):
    # handle: shading of the chamfered handle quantized to dark edges -> flat wood, regular wrap bands
    L[1:3, HANDLE] = i("wood")
    L[13:28, HANDLE] = i("wood")
    L[28:41, :] = 0
    for r in range(28, 41):
        L[r, HANDLE] = i(("leather_light", "leather_light", "leather")[(r - 28) % 3])
    # socket: quantized lighting made the front noisy -> flat iron body, lit top ring, keep the rivet
    socket = L[4:12, 0:7]
    socket[(socket > 0) & (socket != i("stone_light"))] = i("iron_mid")
    L[4, 1:7] = i("stone_mid")
    L[3, 1:7] = 0                                   # chamfered rings, 4 wide
    L[3, HANDLE] = i("iron_mid")
    L[12, 0:7] = 0
    L[12, HANDLE] = i("iron_mid")
    # pommel: symmetric two-tier cap with a lit rim
    L[41:45, :8] = 0
    L[41, 1:7] = i("stone_mid")
    L[42, 1:7] = i("iron_mid")
    L[43:45, HANDLE] = i("stone_dark")
    # head: neutral grays only (blue-tinted steel_mid / iron_dark were near-misses for gray pixels)
    head = L[:20, 7:]
    head[head == i("steel_mid")] = i("stone_mid")
    head[head == i("iron_dark")] = i("iron_mid")
    # values: the reference's lighting brightens the blade, quantization put it all on stone_dark.
    # socket iron_mid (darkest) < neck + blade-root band stone_dark < blade body stone_mid < light < white edge
    neck = L[:20, 7:12]
    neck[neck == i("iron_mid")] = i("stone_dark")
    body = L[:20, 12:]
    body[body == i("stone_dark")] = i("stone_mid")
    L[15, 14] = 0                                   # stray dark voxel breaking the lower staircase
    # material: every gray on this axe is metal; quantization picks the (non-metal) stone/white look-alikes
    for a, b in (("stone_dark", "metal_dark"), ("stone_mid", "metal_mid"),
                 ("stone_light", "metal_light"), ("white", "metal_edge")):
        L[L == i(a)] = i(b)
    return L


def depth_map(L):
    """Thickness (even, centered on y = 0) per layer pixel, from the side reference."""
    D = np.full(L.shape, 2)       # blade body / edge
    D[:, 7:12] = 4                # neck + blade root: thicker toward the socket
    D[:, :7] = 4                  # handle, cap, socket rings, lower pommel
    D[4:12, :7] = 6               # socket
    D[41:43, :7] = 6              # upper pommel tier
    return np.where(L > 0, D, 0)


def build():
    L = front_layer()
    D = depth_map(L)
    m = vs.VoxelModel(pivot=[0.0, 0.0, 0.5])
    g = m.add_part("axe", size=(L.shape[1], 6, ROWS), origin=(-X0, 3, -Z0))
    for d in np.unique(D[D > 0]):
        g.extrude_2d(np.where(D == d, L, 0), at=(X0, -d // 2, Z0), depth=int(d))
    removed = g.keep_largest()
    assert removed == 0, f"{removed} floating voxels"
    return m, L


model, layer = build()
result = vs.finalize(model, "axe")
result["compare"] = R.compare_images(FRONT, os.path.join(HERE, "renders", "front.png"),
                                     os.path.join(HERE, "renders", "compare_front.png"))
