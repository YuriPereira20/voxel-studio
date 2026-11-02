"""VoxelGrid (fixed-size uint8 palette grid with an origin offset) and VoxelModel (named parts).

Coordinates are integer MODEL coords; array index = model + origin. Shape builders return boolean
masks over the whole grid, so every shape works with fill / remove / paint.
"""
from collections import deque

import numpy as np

from . import config

AXES = {"x": 0, "y": 1, "z": 2, 0: 0, 1: 1, 2: 2}


class VoxelGrid:
    def __init__(self, size, origin=(0, 0, 0)):
        self.data = np.zeros(tuple(size), np.uint8)
        self.origin = np.array(origin, int)

    # ---------------------------------------------------------------- basics
    def coords(self):
        """X, Y, Z model-coordinate arrays with the grid's shape."""
        return [np.arange(n)[tuple(slice(None) if i == a else None for i in range(3))] - self.origin[a]
                for a, n in enumerate(self.data.shape)]

    def _index(self, p):
        i = np.array(p, int) + self.origin
        if np.any(i < 0) or np.any(i >= self.data.shape):
            raise IndexError(f"model coord {tuple(p)} outside grid")
        return tuple(i)

    def set(self, p, color):
        self.data[self._index(p)] = config.idx(color)

    def get(self, p):
        return int(self.data[self._index(p)])

    # ---------------------------------------------------------------- shape masks
    def box(self, lo, hi):
        """Inclusive box between model coords lo and hi."""
        X, Y, Z = self.coords()
        return ((X >= lo[0]) & (X <= hi[0]) & (Y >= lo[1]) & (Y <= hi[1]) & (Z >= lo[2]) & (Z <= hi[2]))

    def ellipsoid(self, center, radii):
        X, Y, Z = self.coords()
        return sum(((c - c0) / r) ** 2 for c, c0, r in zip((X, Y, Z), center, radii)) <= 1.0

    def sphere(self, center, radius):
        return self.ellipsoid(center, (radius,) * 3)

    def cylinder(self, base, radius, height, axis="z"):
        """Circular cylinder from `base` along +axis for `height` voxels."""
        a = AXES[axis]
        C = self.coords()
        d2 = sum((C[k] - base[k]) ** 2 for k in range(3) if k != a)
        return (d2 <= radius ** 2) & (C[a] >= base[a]) & (C[a] < base[a] + height)

    def line_mask(self, p0, p1, radius=0.0):
        """3D DDA line (rounded points, one per step on the longest axis), thickened by `radius`."""
        p0, p1 = np.array(p0, float), np.array(p1, float)
        n = int(np.abs(p1 - p0).max()) + 1
        X, Y, Z = self.coords()
        m = np.zeros(self.data.shape, bool)
        for p in np.rint(np.linspace(p0, p1, n)):
            m |= (X - p[0]) ** 2 + (Y - p[1]) ** 2 + (Z - p[2]) ** 2 <= radius ** 2
        return m

    def _mask(self, mask):
        if callable(mask):
            mask = mask(*self.coords())
        return np.broadcast_to(np.asarray(mask, bool), self.data.shape)

    # ---------------------------------------------------------------- editing
    def fill_mask(self, mask, color):
        """mask: bool array or vectorized f(X, Y, Z) over model coords."""
        self.data[self._mask(mask)] = config.idx(color)

    def remove(self, mask):
        self.data[self._mask(mask)] = 0

    def paint(self, color, where=None, replace=None):
        """Recolor filled voxels only, optionally inside `where` and/or only those of color `replace`."""
        m = self.data > 0
        if where is not None:
            m &= self._mask(where)
        if replace is not None:
            m &= self.data == config.idx(replace)
        self.data[m] = config.idx(color)

    def fill_box(self, lo, hi, color):
        self.fill_mask(self.box(lo, hi), color)

    def fill_ellipsoid(self, center, radii, color):
        self.fill_mask(self.ellipsoid(center, radii), color)

    def fill_sphere(self, center, radius, color):
        self.fill_mask(self.sphere(center, radius), color)

    def fill_cylinder(self, base, radius, height, color, axis="z"):
        self.fill_mask(self.cylinder(base, radius, height, axis), color)

    def line(self, p0, p1, color, radius=0.0):
        self.fill_mask(self.line_mask(p0, p1, radius), color)

    def mirror(self, axis="x", keep="+"):
        """Copy the positive (keep='+') or negative half onto the other side of model coord 0."""
        a = AXES[axis]
        d = np.moveaxis(self.data, a, 0)  # view
        o, n = self.origin[a], d.shape[0]
        for i in range(n):
            m = i - o
            if (m > 0) if keep == "+" else (m < 0):
                j = o - m
                if 0 <= j < n:
                    d[j] = d[i]
                elif d[i].any():
                    raise IndexError("mirror target outside grid; make the grid symmetric around 0")

    def extrude_2d(self, layer, at=(0, 0, 0), depth=1, plane="xz"):
        """Stamp a 2D index layer (rows top->bottom, like an image) with `depth` voxels of thickness.

        plane 'xz' = front view (u->x, v->z, depth->+y), 'yz' = side (u->y), 'xy' = top (u->x, v->y, depth->+z).
        `at` = model coord of the layer's bottom-left pixel on the first depth slice.
        """
        u_ax, v_ax = {"xz": (0, 2), "yz": (1, 2), "xy": (0, 1)}[plane]
        d_ax = 3 - u_ax - v_ax
        layer = np.asarray(layer)
        rows, cols = np.nonzero(layer)
        vals = layer[rows, cols]
        for k in range(depth):
            p = np.zeros((len(rows), 3), int)
            p[:, u_ax] = at[u_ax] + cols
            p[:, v_ax] = at[v_ax] + layer.shape[0] - 1 - rows
            p[:, d_ax] = at[d_ax] + k
            self._put(p, vals)

    def _put(self, model_pts, vals):
        i = model_pts + self.origin
        if len(i) and (np.any(i < 0) or np.any(i >= self.data.shape)):
            raise IndexError("voxels fall outside the grid")
        self.data[tuple(i.T)] = vals

    def translate(self, d):
        pts = np.argwhere(self.data > 0)
        vals = self.data[tuple(pts.T)]
        self.data[:] = 0
        self._put(pts - self.origin + np.array(d, int), vals)

    def rotate90(self, axis="z", k=1):
        """Rotate content (and grid bounds) by k*90 deg around the model axis through model 0."""
        a = AXES[axis]
        b, c = (a + 1) % 3, (a + 2) % 3
        for _ in range(k % 4):
            lo = -self.origin
            hi = lo + np.array(self.data.shape) - 1
            pts = np.argwhere(self.data > 0)
            vals = self.data[tuple(pts.T)]
            m = pts - self.origin
            m[:, b], m[:, c] = -m[:, c].copy(), m[:, b].copy()  # (b, c) -> (-c, b)
            nlo, nhi = lo.copy(), hi.copy()
            nlo[b], nhi[b] = -hi[c], -lo[c]
            nlo[c], nhi[c] = lo[b], hi[b]
            self.data = np.zeros(tuple(nhi - nlo + 1), np.uint8)
            self.origin = -nlo
            self._put(m, vals)

    def copy(self, lo=None, hi=None):
        """Sub-grid between model coords lo..hi (inclusive); its model 0 is `lo`. No args = full copy."""
        if lo is None:
            g = VoxelGrid(self.data.shape, self.origin)
            g.data[:] = self.data
            return g
        a, b = np.array(self._index(lo)), np.array(self._index(hi))
        g = VoxelGrid(b - a + 1)
        g.data[:] = self.data[a[0]:b[0] + 1, a[1]:b[1] + 1, a[2]:b[2] + 1]
        return g

    def paste(self, src, at=(0, 0, 0)):
        """Write src's filled voxels with src model 0 placed at `at` (empty voxels don't overwrite)."""
        pts = np.argwhere(src.data > 0)
        self._put(pts - src.origin + np.array(at, int), src.data[tuple(pts.T)])

    # ---------------------------------------------------------------- analysis
    def noise(self, cell=4, seed=0):
        """Blocky value noise in [0,1) with the grid's shape; `cell` = clump size (int or 3-tuple)."""
        cell = np.broadcast_to(cell, 3)
        coarse = np.random.default_rng(seed).random(tuple(-(-np.array(self.data.shape) // cell)))
        for a in range(3):
            coarse = np.repeat(coarse, cell[a], axis=a)
        return coarse[:self.data.shape[0], :self.data.shape[1], :self.data.shape[2]]

    def pieces(self):
        """6-connected pieces as lists of array indices, largest first."""
        left = set(map(tuple, np.argwhere(self.data > 0)))
        out = []
        while left:
            piece = [left.pop()]
            q = deque(piece)
            while q:
                x, y, z = q.popleft()
                for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                    if n in left:
                        left.remove(n)
                        q.append(n)
                        piece.append(n)
            out.append(piece)
        return sorted(out, key=len, reverse=True)

    def components(self):
        """Number of 6-connected pieces (1 = no floating voxels)."""
        return len(self.pieces())

    def keep_largest(self):
        """Delete floating voxels (every piece but the largest); returns how many were removed."""
        rest = [p for piece in self.pieces()[1:] for p in piece]
        if rest:
            self.data[tuple(np.array(rest).T)] = 0
        return len(rest)

    def stats(self):
        pts = np.argwhere(self.data > 0) - self.origin
        counts = np.bincount(self.data.ravel(), minlength=config.NUM_COLORS)
        return {
            "voxels": int(len(pts)),
            "size": list(self.data.shape),
            "filled_min": pts.min(0).tolist() if len(pts) else None,
            "filled_max": pts.max(0).tolist() if len(pts) else None,
            "colors": {config.name(i): int(n) for i, n in enumerate(counts) if i and n},
        }


class VoxelModel:
    """Named parts (VoxelGrids placed at model offsets). Later parts overwrite earlier ones when merged."""

    def __init__(self, pivot=None):
        self.parts = {}
        self.pivot = pivot or config.CFG["origin"]["pivot_voxels"]

    def add_part(self, name, size, origin=(0, 0, 0), offset=(0, 0, 0)):
        self.parts[name] = (VoxelGrid(size, origin), np.array(offset, int))
        return self.parts[name][0]

    def part(self, name):
        return self.parts[name][0]

    def merged(self, names=None):
        """One grid of the given parts (default: all), in part order."""
        parts = [self.parts[n] for n in (names or self.parts)]
        los = [off - g.origin for g, off in parts]
        his = [lo + g.data.shape - 1 for lo, (g, _) in zip(los, parts)]
        lo, hi = np.min(los, 0), np.max(his, 0)
        out = VoxelGrid(hi - lo + 1, -lo)
        for g, off in parts:
            out.paste(g, off)
        return out
