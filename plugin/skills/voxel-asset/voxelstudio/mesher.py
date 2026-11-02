"""Face culling + greedy meshing (merges coplanar same-color faces) and the mesh self-checks."""
import numpy as np

from . import config


def exposed_mask(data, axis, d):
    """Palette index where a voxel's face toward d (+1/-1) on `axis` touches empty space."""
    nb = np.roll(np.pad(data, 1), -d, axis)[1:-1, 1:-1, 1:-1]
    return np.where((data > 0) & (nb == 0), data, 0)


def greedy_quads(mask):
    """Merge a 2D mask[u, v] of palette indices into maximal same-color rectangles (u, v, w, h, color)."""
    m = mask.copy()
    W, H = m.shape
    out = []
    for v in range(H):
        for u in range(W):
            c = m[u, v]
            if not c:
                continue
            w = 1
            while u + w < W and m[u + w, v] == c:
                w += 1
            h = 1
            while v + h < H and np.all(m[u:u + w, v + h] == c):
                h += 1
            m[u:u + w, v:v + h] = 0
            out.append((u, v, w, h, int(c)))
    return out


def greedy_mesh(grid, offset=(0, 0, 0)):
    """Mesh a VoxelGrid. Returns dict: verts (V,3) in model voxel units (+offset), quad faces,
    per-face color and atlas uv, exposed face count, and `shift` (array index -> model coords)."""
    verts, vidx, faces, colors = [], {}, [], []
    exposed = 0

    def vid(p):
        key = tuple(p)
        if key not in vidx:
            vidx[key] = len(verts)
            verts.append(key)
        return vidx[key]

    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3  # cyclic, so (b x c) points along +a
        for d in (1, -1):
            mask3 = np.moveaxis(exposed_mask(grid.data, a, d), (a, b, c), (0, 1, 2))
            exposed += int(np.count_nonzero(mask3))
            for s in range(mask3.shape[0]):
                plane = s + 1 if d > 0 else s
                for u, v, w, h, col in greedy_quads(mask3[s]):
                    corners = [(u, v), (u + w, v), (u + w, v + h), (u, v + h)]
                    if d < 0:
                        corners.reverse()
                    ids = []
                    for cu, cv in corners:
                        p = [0, 0, 0]
                        p[a], p[b], p[c] = plane, cu, cv
                        ids.append(vid(p))
                    faces.append(ids)
                    colors.append(col)
    shift = np.array(offset, int) - grid.origin
    return {
        "verts": np.array(verts, float).reshape(-1, 3) + shift,
        "faces": faces,
        "colors": colors,
        "uvs": [config.atlas_uv(c) for c in colors],
        "exposed": exposed,
        "shift": shift,
    }


def validate(grid, mesh):
    """Assert: area == exposed faces (nothing lost/duplicated by merging); every quad's UV is one atlas
    block center whose color equals every voxel under the quad; every quad faces empty space."""
    v = mesh["verts"]
    area = 0.0
    atlas = config.atlas_pixels()
    maps = np.stack([config.atlas_map("metalness"), config.atlas_map("roughness")], -1)
    data = grid.data
    for f, uv in zip(mesh["faces"], mesh["uvs"]):
        p = v[f]
        n = np.cross(p[1] - p[0], p[3] - p[0])
        area += np.linalg.norm(n)
        i = config.atlas_index(uv)
        py_, px_ = int(uv[1] * config.ATLAS_H), int(uv[0] * config.ATLAS_W)
        px = atlas[py_, px_, :3]
        assert np.allclose(maps[py_, px_], config.material_props(i)), "metal/roughness block mismatch"
        a = int(np.argmax(np.abs(n)))
        sgn = 1 if n[a] > 0 else -1
        pc = np.rint(p - mesh["shift"]).astype(int)
        lo, hi = pc.min(0), pc.max(0)
        rng = [range(lo[k], hi[k]) if k != a else [lo[a] - 1 if sgn > 0 else lo[a]] for k in range(3)]
        for x in rng[0]:
            for y in rng[1]:
                for z in rng[2]:
                    val = int(data[x, y, z])
                    assert val == i, f"quad color {i} over voxel {val} at {(x, y, z)}"
                    out = [x, y, z]
                    out[a] += sgn
                    inside = all(0 <= out[q] < data.shape[q] for q in range(3))
                    assert not inside or data[tuple(out)] == 0, "quad is not on a boundary"
        assert np.allclose(px, config.rgb(i), atol=0.6 / 255), "atlas pixel color mismatch"
    assert abs(area - mesh["exposed"]) < 1e-6 * max(1, mesh["exposed"]), (area, mesh["exposed"])
    return True
