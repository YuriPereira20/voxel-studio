"""Reference image intake: background keying, palette quantization, 2D index layers, side-by-side compare.

Images are read through bpy.data.images (no PIL). Arrays are (H, W, 4) float sRGB, row 0 = TOP.
"""
import numpy as np
import bpy

from . import config


def load_reference(path):
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        px = np.empty(w * h * img.channels, np.float32)
        img.pixels.foreach_get(px)
        is_float = img.is_float
    finally:
        bpy.data.images.remove(img)
    px = px.reshape(h, w, -1)
    if px.shape[2] == 3:
        px = np.concatenate([px, np.ones((h, w, 1), np.float32)], 2)
    if is_float:  # float buffers are scene-linear; bring to sRGB like byte images
        c = px[..., :3]
        px[..., :3] = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)
    return px[::-1].copy()


def srgb_to_lab(rgb):
    rgb = np.asarray(rgb, np.float64)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = lin @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]])
    xyz /= (0.95047, 1.0, 1.08883)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _palette_lab():
    return srgb_to_lab(np.array([config.rgb(i) for i in range(1, config.NUM_COLORS)]))


def _nearest(rgb, exclude=()):
    """(N,3) sRGB -> (nearest palette index, delta E), skipping palette names in `exclude`."""
    lab = srgb_to_lab(rgb)
    d = np.linalg.norm(lab[:, None, :] - _palette_lab()[None], axis=2)
    for n in exclude:
        d[:, config.idx(n) - 1] = np.inf
    return d.argmin(1) + 1, d.min(1)


BG_STEP = 0.04   # flood fill: max RGB channel step between neighbouring background pixels (gradients, noise)
BG_CAP = 0.8     # flood fill: never grows further than this from the corner colour (bright floor glow is ~0.7)


def _seg_fill(mask, ok):
    """Spread `mask` along rows through runs of allowed steps (ok[:, i] = pixel i -> i+1 allowed)."""
    h, w = mask.shape
    start = np.concatenate([np.ones((h, 1), bool), ~ok], 1)       # a blocked step starts a new run
    run = np.cumsum(start.ravel()) - 1
    return (np.bincount(run, weights=mask.ravel()) > 0)[run].reshape(h, w)


def _flood_background(rgb, bg):
    """Pixels connected to the image border through small colour steps (<= BG_STEP), within BG_CAP of `bg`."""
    capok = np.abs(rgb - bg).max(2) <= BG_CAP
    ok_h = (np.abs(np.diff(rgb, axis=1)).max(2) <= BG_STEP) & capok[:, 1:] & capok[:, :-1]
    ok_v = (np.abs(np.diff(rgb, axis=0)).max(2) <= BG_STEP) & capok[1:] & capok[:-1]
    mask = np.zeros(capok.shape, bool)
    mask[[0, -1], :] = capok[[0, -1], :]
    mask[:, [0, -1]] = capok[:, [0, -1]]
    n = -1
    while mask.sum() != n:                    # alternate row / column runs until nothing new is reached
        n = mask.sum()
        mask = _seg_fill(_seg_fill(mask, ok_h).T, ok_v.T).T
    return mask


def _key(px, bg_tolerance):
    """Classify pixels: 0 = background, 1 = content, 2 = edge (anti-aliased blend with the background).

    Flat border (5-95% spread <= bg_tolerance, e.g. Codex magenta): background = within bg_tolerance (max RGB
    channel diff) of the median corner color, so enclosed holes stay background.
    Otherwise (gradient, vignette, floor glow): background = flood fill from the whole border through small
    colour steps (<= BG_STEP) within BG_CAP of the corner color; enclosed holes stay content.
    Edge = not background, but closer (Lab) to the background than to any palette color, e.g. magenta fringes.
    """
    bg = np.median(px[[0, 0, -1, -1], [0, -1, 0, -1], :3], 0)
    rgb = px[..., :3]
    border = np.concatenate([rgb[[0, -1]].reshape(-1, 3), rgb[:, [0, -1]].reshape(-1, 3)])
    if np.ptp(np.percentile(border, [5, 95], 0), 0).max() <= bg_tolerance:
        back = np.abs(rgb - bg).max(2) <= bg_tolerance
    else:
        back = _flood_background(rgb, bg)
    cls = np.where(back | (px[..., 3] <= 0.5), 0, 1)
    cand = np.argwhere(cls == 1)
    q = np.rint(rgb[cls == 1] * 255).astype(np.int32)
    packed = (q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2]
    uniq, inv = np.unique(packed, return_inverse=True)
    u_rgb = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], 1) / 255
    _, d_pal = _nearest(u_rgb)
    d_bg = np.linalg.norm(srgb_to_lab(u_rgb) - srgb_to_lab(bg), axis=1)
    edge = (d_bg < d_pal)[inv]
    cls[cand[edge, 0], cand[edge, 1]] = 2
    return cls, bg


def _quantize(rgb, exclude=()):
    q = np.rint(rgb * 255).astype(np.int32)
    uniq, inv = np.unique((q[:, 0] << 16) | (q[:, 1] << 8) | q[:, 2], return_inverse=True)
    u_rgb = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], 1) / 255
    return _nearest(u_rgb, exclude)[0][inv]


def content_bbox(px, bg_tolerance=0.1):
    cls, _ = _key(px, bg_tolerance)
    r, c = np.nonzero(cls == 1)
    return r.min(), r.max() + 1, c.min(), c.max() + 1


def image_to_layer(path, width_voxels=None, height_voxels=None, bg_tolerance=0.1, exclude=()):
    """Reference image -> 2D palette-index layer (rows top->bottom, 0 = empty), for extrude_2d or as a guide.

    Crops to the content bbox, splits it into width_voxels and/or height_voxels cells (a missing side keeps
    the aspect; give both to match a measured cube pitch, see cube_pitch), quantizes content pixels to the nearest palette color (CIE Lab) and takes the majority per cell.
    Edge pixels don't vote; a cell is empty if background pixels outnumber its top color.
    `exclude`: palette names never chosen (e.g. metal_* look-alikes of stone_*; assign materials afterwards).
    """
    assert width_voxels or height_voxels
    px = load_reference(path)
    cls, _ = _key(px, bg_tolerance)
    r, c = np.nonzero(cls == 1)
    r0, r1, c0, c1 = r.min(), r.max() + 1, c.min(), c.max() + 1
    px, cls = px[r0:r1, c0:c1], cls[r0:r1, c0:c1]
    h, w = cls.shape
    W = width_voxels or max(1, round(w * height_voxels / h))
    H = height_voxels or max(1, round(h * width_voxels / w))
    idx = np.zeros((h, w), np.int64)
    idx[cls == 1] = _quantize(px[cls == 1][:, :3], exclude)
    K = config.NUM_COLORS
    cell = (np.arange(h) * H // h)[:, None] * W + (np.arange(w) * W // w)[None, :]
    votes = np.bincount((cell * K + idx)[cls != 2], minlength=H * W * K).reshape(H * W, K)
    return votes.argmax(1).reshape(H, W).astype(np.uint8)


def palette_report(path, bg_tolerance=0.1, top=12):
    """Main colors of the reference content (5-bit buckets) with their nearest palette color and delta E."""
    px = load_reference(path)
    cls, bg = _key(px, bg_tolerance)
    rgb = px[cls == 1][:, :3]
    q = (np.rint(rgb * 255).astype(np.int32) >> 3)
    keys, inv, counts = np.unique((q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2], return_inverse=True, return_counts=True)
    order = np.argsort(-counts)[:top]
    means = np.array([rgb[inv == k].mean(0) for k in order])
    near, de = _nearest(means)
    return {
        "background": "%02X%02X%02X" % tuple(np.rint(bg * 255).astype(int)),
        "colors": [{"hex": "%02X%02X%02X" % tuple(np.rint(m * 255).astype(int)),
                    "share": round(float(counts[k]) / len(rgb), 3),
                    "nearest": config.name(int(n)), "delta_e": round(float(d), 1)}
                   for m, k, n, d in zip(means, order, near, de)],
    }


def _first_peak(a, lo, hi):
    """First local maximum of a[lo..hi] reaching half the highest one (multiples of the pitch peak too)."""
    k = np.arange(lo, hi + 1)
    peak = k[(a[k] >= a[k - 1]) & (a[k] >= a[k + 1])]
    if not len(peak):
        return lo + int(np.argmax(a[lo:hi + 1]))
    return int(peak[a[peak] >= 0.5 * a[peak].max()][0])


def cube_pitch(path, bg_tolerance=0.1, max_pitch=None):
    """Pixels per voxel-art cube, from the autocorrelation of luminance edges along the content's longer
    axis (cubes are square in an orthographic view; the short axis has too few periods to be reliable).
    Refined on a far peak for sub-pixel accuracy. Layer size = content size / pitch.
    max_pitch: largest pitch searched (default: the content's shorter side / 8, i.e. >= 8 cubes across)."""
    px = load_reference(path)
    r0, r1, c0, c1 = content_bbox(px, bg_tolerance)
    lum = px[r0:r1, c0:c1, :3] @ np.array([0.299, 0.587, 0.114])
    axis = 0 if lum.shape[0] >= lum.shape[1] else 1
    sig = np.abs(np.diff(lum, axis=axis)).mean(1 - axis)
    s = sig - sig.mean()
    a = np.correlate(s, s, "full")[len(s) - 1:]
    hi = min(int(max_pitch or min(lum.shape) // 8), len(a) - 2)
    p = _first_peak(a, 4, max(hi, 5))                       # first peak = rough pitch
    n = max(1, int(len(s) * 0.4 / p))                       # refine on the n-th peak
    lo = int(n * p - p / 2)
    k = lo + int(np.argmax(a[lo:lo + p]))
    y0, y1, y2 = a[k - 1], a[k], a[k + 1]
    return float(k + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)) / n


def clean_layer(layer):
    """Remove quantization noise: filled pixels with no filled 4-neighbor are cleared; a pixel whose
    color matches none of its 4 neighbors while >= 3 of them agree takes that neighbor color."""
    L = np.asarray(layer).copy()
    P = np.pad(L, 1)
    nbs = np.stack([P[:-2, 1:-1], P[2:, 1:-1], P[1:-1, :-2], P[1:-1, 2:]])
    L[(L > 0) & ((nbs > 0).sum(0) == 0)] = 0
    for r, c in np.argwhere(L > 0):
        n = nbs[:, r, c]
        n = n[n > 0]
        if len(n) and not np.any(n == L[r, c]):
            vals, cnt = np.unique(n, return_counts=True)
            if cnt.max() >= 3:
                L[r, c] = vals[cnt.argmax()]
    return L


def prune_specks(mask, min_size):
    """Keep only 8-connected groups of >= min_size pixels (lines/strokes survive, quantization specks don't)."""
    mask = np.asarray(mask, bool)
    keep = np.zeros_like(mask)
    seen = np.zeros_like(mask)
    H, W = mask.shape
    for r0, c0 in np.argwhere(mask):
        if seen[r0, c0]:
            continue
        group, todo = [], [(r0, c0)]
        seen[r0, c0] = True
        while todo:
            r, c = todo.pop()
            group.append((r, c))
            for rr in range(max(0, r - 1), min(H, r + 2)):
                for cc in range(max(0, c - 1), min(W, c + 2)):
                    if mask[rr, cc] and not seen[rr, cc]:
                        seen[rr, cc] = True
                        todo.append((rr, cc))
        if len(group) >= min_size:
            keep[tuple(np.array(group).T)] = True
    return keep


def layer_report(layer):
    """Color counts of a 2D index layer by palette name."""
    counts = np.bincount(np.asarray(layer).ravel(), minlength=config.NUM_COLORS)
    return {config.name(i): int(n) for i, n in enumerate(counts) if i and n}


def compare_images(ref_path, render_path, out_path, bg_tolerance=0.1, height=768, ref_bbox=None,
                   ref_tolerance=None, render_tolerance=None):
    """Side-by-side PNG: both images cropped to their content bbox and scaled to the same height.

    ref_bbox: manual (r0, r1, c0, c1) crop of the reference in pixels (rows from the top, like content_bbox)
    when keying can't find it. ref_tolerance / render_tolerance override bg_tolerance per image.
    """
    tiles = []
    for p, tol, bbox in ((ref_path, ref_tolerance, ref_bbox), (render_path, render_tolerance, None)):
        px = load_reference(p)
        r0, r1, c0, c1 = bbox or content_bbox(px, bg_tolerance if tol is None else tol)
        crop = px[r0:r1, c0:c1]
        s = height / crop.shape[0]
        ys = np.minimum((np.arange(height) / s).astype(int), crop.shape[0] - 1)
        xs = np.minimum((np.arange(max(1, round(crop.shape[1] * s))) / s).astype(int), crop.shape[1] - 1)
        tiles.append(crop[ys][:, xs])
    gap = np.ones((height, 16, 4), np.float32)
    out = np.concatenate([tiles[0], gap, tiles[1]], 1)
    img = bpy.data.images.new("VX_Compare", out.shape[1], out.shape[0], alpha=False)
    try:
        img.pixels.foreach_set(out[::-1].ravel())
        img.filepath_raw = out_path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)
    return out_path


def _selftest():
    """Keying on a gradient (content found, nothing else) and on a flat background (enclosed hole stays bg)."""
    px = np.ones((24, 24, 4), np.float32)
    px[..., :3] = np.linspace(0.02, 0.3, 24)[None, :, None] * np.array([1.0, 0.1, 0.2])   # dark red gradient
    px[6:18, 8:16, :3] = (0.55, 0.7, 0.18)                                                 # green block
    assert tuple(int(v) for v in content_bbox(px)) == (6, 18, 8, 16)
    flat = px.copy()
    flat[..., :3] = (1.0, 0.0, 1.0)
    flat[6:18, 8:16, :3] = (0.55, 0.7, 0.18)
    flat[10:12, 11:13, :3] = (1.0, 0.0, 1.0)                                               # enclosed hole
    cls, _ = _key(flat, 0.1)
    assert cls[10, 11] == 0 and cls[6, 8] == 1
    a = np.cos(np.arange(60) * 2 * np.pi / 9) + 1.5                                         # period-9 signal
    assert _first_peak(a, 4, 40) == 9


_selftest()
