"""Loads config/voxel_config.json and exposes palette / atlas helpers."""
import json
import os

import numpy as np

LIB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the skill folder
PROJECT = os.environ.get("VOXELSTUDIO_PROJECT") or os.getcwd()
_proj_cfg = os.path.join(PROJECT, "voxel_config.json")
CONFIG_PATH = _proj_cfg if os.path.exists(_proj_cfg) else os.path.join(LIB_ROOT, "config", "voxel_config.json")
ASSETS_DIR = os.path.join(PROJECT, "voxel_assets")

with open(CONFIG_PATH, encoding="utf-8") as _f:
    CFG = json.load(_f)

PALETTE = CFG["palette"]                      # name -> hex; JSON order = index order
NAMES = list(PALETTE)
INDEX = {n: i + 1 for i, n in enumerate(NAMES)}
NUM_COLORS = len(NAMES) + 1                   # including 0 = empty

_A = CFG["atlas"]
BLOCK, COLS, ROWS = _A["block_px"], _A["columns"], _A["rows"]
ATLAS_W, ATLAS_H = COLS * BLOCK, ROWS * BLOCK
assert NUM_COLORS <= COLS * ROWS, "palette larger than the atlas"


def bu_per_voxel():
    return CFG["voxel_size_studs"] * CFG["bu_per_stud"]


def idx(color):
    """Palette index from a name or an int (0 = empty)."""
    if isinstance(color, str):
        if color not in INDEX:
            raise KeyError(f"unknown palette color {color!r}; add it to voxel_config.json")
        return INDEX[color]
    color = int(color)
    if not 0 <= color < NUM_COLORS:
        raise ValueError(f"palette index {color} out of range")
    return color


def name(index):
    return NAMES[index - 1] if index else "empty"


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb(index):
    return hex_rgb(PALETTE[NAMES[index - 1]])


def atlas_uv(index):
    """UV at the center of the atlas block of `index`."""
    col, row = index % COLS, index // COLS
    return ((col + 0.5) * BLOCK / ATLAS_W, (row + 0.5) * BLOCK / ATLAS_H)


def atlas_index(uv):
    """Inverse of atlas_uv; raises if the UV is not exactly a block center."""
    col, row = int(uv[0] * COLS), int(uv[1] * ROWS)
    i = row * COLS + col
    assert np.allclose(uv, atlas_uv(i), atol=1e-6), f"UV {tuple(uv)} is not a block center"
    return i


_M = {k: v for k, v in CFG["materials"].items() if not k.startswith("_")}
assert set(_M) <= set(PALETTE), f"materials for unknown colors: {set(_M) - set(PALETTE)}"


def material_props(index):
    """(metalness, roughness) of a palette index."""
    m = _M.get(NAMES[index - 1], {})
    return (m.get("metalness", CFG["material"]["metallic"]), m.get("roughness", CFG["material"]["roughness"]))


def _block(px, i, value):
    col, row = i % COLS, i // COLS
    px[row * BLOCK:(row + 1) * BLOCK, col * BLOCK:(col + 1) * BLOCK] = value


def atlas_pixels():
    """(H, W, 4) float RGBA color atlas, row 0 = bottom (Blender's pixel order)."""
    px = np.empty((ATLAS_H, ATLAS_W, 4), np.float32)
    px[:] = (*hex_rgb(_A["unused_color"]), 1.0)
    for i in range(1, NUM_COLORS):
        _block(px[..., :3], i, rgb(i))
    return px


def atlas_map(kind):
    """(H, W) float 'metalness' or 'roughness' atlas with the color atlas' block layout (unused blocks 0)."""
    k = ("metalness", "roughness").index(kind)
    a = np.zeros((ATLAS_H, ATLAS_W), np.float32)
    for i in range(1, NUM_COLORS):
        _block(a, i, material_props(i)[k])
    return a
