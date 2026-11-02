"""Blender side: VoxelLab scene, palette atlas + material, mesh objects, FBX / .blend export, renders.

Only touches the scene 'VoxelLab' and datablocks named 'VX_*'. Never saves the open .blend.
"""
import os
import struct
import zlib

import numpy as np
import bpy
from mathutils import Vector

from . import config, mesher
from .grid import resolve_overlaps

SCENE_NAME = "VoxelLab"
PREFIX = "VX_"


def lab_scene():
    """Get/create VoxelLab, clear its VX_* objects and orphaned VX_* data, make it the window scene."""
    scn = bpy.data.scenes.get(SCENE_NAME) or bpy.data.scenes.new(SCENE_NAME)
    for ob in list(scn.collection.all_objects):
        if ob.name.startswith(PREFIX):
            bpy.data.objects.remove(ob)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for idb in list(coll):
            if idb.name.startswith(PREFIX) and idb.users == 0:
                coll.remove(idb)
    bpy.context.window.scene = scn
    assert bpy.context.scene == scn
    return scn


def _write_gray_png(path, a):
    """8-bit grayscale PNG from an (H, W) 0..1 array with row 0 = bottom (Blender can't save 1-channel)."""
    rows = np.rint(np.clip(a[::-1], 0, 1) * 255).astype(np.uint8)
    raw = b"".join(b"\x00" + r.tobytes() for r in rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", a.shape[1], a.shape[0], 8, 0, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def atlas_images(export_dir, name):
    """Write <name>_color/_metalness/_roughness.png and load them; checks every palette block in the files."""
    px = config.atlas_pixels()
    color = bpy.data.images.new(PREFIX + "Color", config.ATLAS_W, config.ATLAS_H, alpha=False)
    color.pixels.foreach_set(px.ravel())
    color.filepath_raw = os.path.join(export_dir, f"{name}_color.png")
    color.file_format = "PNG"
    color.save()
    assert np.allclose(np.array(color.pixels[:]).reshape(px.shape), px, atol=0.6 / 255)
    imgs = {"color": color}
    for kind in ("metalness", "roughness"):
        path = os.path.join(export_dir, f"{name}_{kind}.png")
        _write_gray_png(path, config.atlas_map(kind))
        img = bpy.data.images.load(path, check_existing=False)
        img.name = PREFIX + kind.capitalize()
        img.colorspace_settings.name = "Non-Color"
        got = np.array(img.pixels[:]).reshape(config.ATLAS_H, config.ATLAS_W, -1)[..., 0]
        for i in range(1, config.NUM_COLORS):  # same layout as the color atlas: every index hits its value
            u, v = config.atlas_uv(i)
            want = config.material_props(i)[("metalness", "roughness").index(kind)]
            assert abs(got[int(v * config.ATLAS_H), int(u * config.ATLAS_W)] - want) <= 0.6 / 255, (kind, i)
        imgs[kind] = img
    return imgs


def palette_material(imgs, emission=0.0):
    """Palette PBR material; emission > 0 also feeds the color atlas into Emission (glow meshes)."""
    m = config.CFG["material"]
    mat = bpy.data.materials.new(m["name"] + ("_Glow" if emission else ""))
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location, out.location = (-100, 0), (250, 0)
    for y, (kind, socket) in zip((300, 0, -300), (("color", "Base Color"), ("metalness", "Metallic"),
                                                  ("roughness", "Roughness"))):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = imgs[kind]
        tex.interpolation = m["interpolation"]
        tex.location = (-450, y)
        nt.links.new(tex.outputs["Color"], bsdf.inputs[socket])
        if kind == "color":
            nt.nodes.active = tex
            if emission:
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = emission
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def build_object(scn, obj_name, mesh, mat, pivot):
    k = config.bu_per_voxel()
    me = bpy.data.meshes.new(obj_name)
    me.from_pydata(((mesh["verts"] - np.array(pivot)) * k).tolist(), [], mesh["faces"])
    me.polygons.foreach_set("use_smooth", [False] * len(mesh["faces"]))
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.repeat(np.array(mesh["uvs"]), 4, axis=0).ravel())  # all faces are quads
    me.materials.append(mat)
    me.validate()
    me.update()
    # Blender-side readback: nothing dropped, every polygon's 4 UVs identical, area preserved
    assert len(me.polygons) == len(mesh["faces"])
    loops = np.zeros(len(me.loops) * 2)
    uv.data.foreach_get("uv", loops)
    assert np.allclose(loops.reshape(-1, 4, 2), np.array(mesh["uvs"])[:, None, :])
    assert abs(sum(p.area for p in me.polygons) - mesh["exposed"] * k * k) < 1e-6 * max(1, mesh["exposed"])
    ob = bpy.data.objects.new(obj_name, me)
    scn.collection.objects.link(ob)
    return ob


def export_fbx(scn, objs, path):
    vl = scn.view_layers[0]
    for o in scn.objects:
        o.select_set(False, view_layer=vl)
    for o in objs:
        o.select_set(True, view_layer=vl)
    vl.objects.active = objs[0]
    opts = {k: v for k, v in config.CFG["export"]["fbx"].items() if not k.startswith("_")}
    opts["object_types"] = set(opts["object_types"])
    with bpy.context.temp_override(scene=scn, view_layer=vl):
        bpy.ops.export_scene.fbx(filepath=path, **opts)


def write_blend(path, objs, mats, imgs):
    for img in imgs:
        img.pack()  # self-contained .blend
    bpy.data.libraries.write(path, set(objs) | {o.data for o in objs} | set(mats) | set(imgs), fake_user=True)


def _world(r):
    """Camera sees the flat background; everything else (reflections, ambient) sees a sky/ground gradient."""
    world = bpy.data.worlds.get(PREFIX + "World") or bpy.data.worlds.new(PREFIX + "World")
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    remap = nt.nodes.new("ShaderNodeMapRange")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sky = nt.nodes.new("ShaderNodeBackground")
    flat = nt.nodes.new("ShaderNodeBackground")
    path = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], remap.inputs["Value"])
    remap.inputs["From Min"].default_value = -1.0  # view direction z -> 0 (down) .. 1 (up)
    nt.links.new(remap.outputs["Result"], ramp.inputs["Fac"])
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.4, (*r["world_ground"], 1)
    els[1].position, els[1].color = 0.85, (*r["world_sky"], 1)
    horizon = els.new(0.5)
    horizon.color = (*r["world_horizon"], 1)
    nt.links.new(ramp.outputs["Color"], sky.inputs["Color"])
    sky.inputs["Strength"].default_value = r["world_strength"]
    flat.name = "CameraBackground"
    flat.inputs["Color"].default_value = (*_linear(r["background"]), 1)
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(sky.outputs[0], mix.inputs[1])
    nt.links.new(flat.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return world


def _setup_render(scn):
    r = config.CFG["render"]
    scn.world = _world(r)
    scn.view_settings.view_transform = r["view_transform"]
    scn.render.engine = r["engine"]
    scn.eevee.taa_render_samples = r["samples"]
    scn.eevee.use_raytracing = r["raytracing"]
    scn.render.film_transparent = False
    scn.render.image_settings.file_format = "PNG"
    sun = bpy.data.objects.new(PREFIX + "Sun", bpy.data.lights.new(PREFIX + "Sun", "SUN"))
    sun.data.energy = r["sun_energy"]
    sun.data.angle = 0.2
    sun.rotation_euler = r["sun_rotation"]
    scn.collection.objects.link(sun)
    rim = bpy.data.objects.new(PREFIX + "Rim", bpy.data.lights.new(PREFIX + "Rim", "SUN"))
    rim.data.energy = r["rim_energy"]
    rim.data.angle = 0.2
    rim.rotation_euler = Vector(r["rim_toward"]).to_track_quat("Z", "Y").to_euler()  # sun shines along -Z
    scn.collection.objects.link(rim)
    cam = bpy.data.objects.new(PREFIX + "Cam", bpy.data.cameras.new(PREFIX + "Cam"))
    cam.data.type = "ORTHO"
    cam.data.clip_end = 1000
    scn.collection.objects.link(cam)
    scn.camera = cam
    return cam


def _frame(cam, objs, direction, res, margin, region=None):
    """Aim the ortho camera along -direction and fit the objects' bounding boxes (or a region [lo, hi] in BU)."""
    if region:
        lo, hi = region
        pts = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    else:
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    d = Vector(direction).normalized()
    rot = (-d).to_track_quat("-Z", "Y")
    right, up = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    xs, ys, zs = ([p.dot(ax) for p in pts] for ax in (right, up, d))
    ex, ey = max(xs) - min(xs), max(ys) - min(ys)
    w, h = res
    cam.data.ortho_scale = margin * (max(ex, ey * w / h) if w >= h else max(ey, ex * h / w))
    cam.location = right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2 + d * (max(zs) + 10)
    cam.rotation_euler = rot.to_euler()


# Named views a caller can request in extra_views; never rendered by default (existing assets keep their render
# set). Model axes: -Y = front, +X = the model's LEFT, so config "side" (dir -X) shows the model's RIGHT side.
VIEW_PRESETS = {
    "left": {"dir": [1, 0, 0], "res": [512, 768]},
    "back": {"dir": [0, 1, 0], "res": [512, 768]},
    "right": {"dir": [-1, 0, 0], "res": [512, 768]},
    "hero_34": {"dir": [6, -8, 2.5], "res": [768, 768]},   # low 3/4 from the front-left: faces under hats show
}


def _linear(c):
    """View background: 'RRGGBB' sRGB hex -> linear RGB; a list is taken as linear already."""
    if isinstance(c, str):
        return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in config.hex_rgb(c)]
    return list(c)


assert _linear("FFFFFF") == [1.0, 1.0, 1.0] and abs(_linear("808080")[0] - 0.2158605) < 1e-6


def render_views(scn, objs, folder, views=None, extra_views=None):
    """Render the configured views (or the given subset) plus asset-specific `extra_views` to <folder>/<view>.png.

    extra_views: a list of VIEW_PRESETS names, or {name: view}; a view has the config view keys ("dir", "res",
    "wire", "background" as linear RGB or an sRGB hex string) plus optional "region": [[x,y,z], [x,y,z]] in BU
    for close-ups. A dict entry named after a preset is merged over it (e.g. {"left": {"background": "1F020B"}}).
    """
    os.makedirs(folder, exist_ok=True)
    r = config.CFG["render"]
    cam = _setup_render(scn)
    scn.view_layers[0].update()
    paths = []
    ev = dict.fromkeys(extra_views, {}) if isinstance(extra_views, (list, tuple)) else dict(extra_views or {})
    ev = {n: {**VIEW_PRESETS.get(n, {}), **v} for n, v in ev.items()}
    for vname, v in {**r["views"], **ev}.items():
        if vname.startswith("_") or (views and vname not in views):
            continue
        _frame(cam, objs, v["dir"], v["res"], r["frame_margin"], v.get("region"))
        scn.render.resolution_x, scn.render.resolution_y = v["res"]
        scn.render.resolution_percentage = 100
        scn.render.filepath = os.path.join(folder, vname + ".png")
        tmp = _add_wire(scn, objs, r["wire_thickness_voxels"] * config.bu_per_voxel()) if v.get("wire") else []
        flat = scn.world.node_tree.nodes["CameraBackground"].inputs["Color"]  # what the camera sees
        flat.default_value = (*_linear(v.get("background", r["background"])), 1)
        try:
            bpy.ops.render.render(write_still=True, scene=scn.name)
        finally:
            for o in tmp:
                bpy.data.objects.remove(o)
            if tmp:
                bpy.data.materials.remove(bpy.data.materials[PREFIX + "WireMat"])
        paths.append(scn.render.filepath)
    return paths


def _add_wire(scn, objs, thickness):
    mat = bpy.data.materials.new(PREFIX + "WireMat")
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0, 0, 0, 1)
    b.inputs["Roughness"].default_value = 1.0
    out = []
    for o in objs:
        w = bpy.data.objects.new(PREFIX + "WireTmp", o.data)  # shares the mesh; modifier is render-only scaffolding
        scn.collection.objects.link(w)
        w.material_slots[0].link = "OBJECT"
        w.material_slots[0].material = mat
        mod = w.modifiers.new("wire", "WIREFRAME")
        mod.thickness = thickness
        mod.use_even_offset = False
        out.append(w)
    return out


def check_limits(stats):
    lim = config.CFG["limits"]
    problems = [f"{o['object']}: {o['triangles']} triangles > max_triangles {lim['max_triangles']}"
                for o in stats["objects"] if o["triangles"] > lim["max_triangles"]]
    if stats["voxels"] > lim["max_voxels"]:
        problems.append(f"{stats['voxels']} voxels > max_voxels {lim['max_voxels']}")
    if problems and lim["on_exceed"] == "error":
        raise ValueError("; ".join(problems))
    return problems


def _object_name(name):
    return PREFIX + "".join(w[:1].upper() + w[1:] for w in name.split("_"))


def finalize(model, name, per_part=False, meshes=None, emissive=(), asset_dir=None, render=True,
             extra_views=None):
    """Mesh + validate + export FBX/.blend + render an asset.

    One mesh by default; one per part if per_part; or meshes={"mesh": [part names]} to group parts.
    `emissive`: mesh names (or part names with per_part) that glow: emissive material in Blender,
    Material=Neon in Roblox. Glow pieces may be disconnected, so they skip the floating-voxel warning.
    With meshes=, glow voxels are removed from the other meshes and any other voxel shared by two meshes
    raises ValueError. extra_views: see render_views (preset names or view dicts).
    """
    asset_dir = asset_dir or os.path.join(config.ASSETS_DIR, name)
    export_dir, render_dir = os.path.join(asset_dir, "export"), os.path.join(asset_dir, "renders")
    os.makedirs(export_dir, exist_ok=True)
    scn = lab_scene()

    if meshes:
        grids = {m: model.merged(parts) for m, parts in meshes.items()}
        resolve_overlaps(grids, emissive)            # glow wins; any other shared voxel is an error
        pieces = [(m, g, (0, 0, 0)) for m, g in grids.items()]
    elif per_part:
        pieces = [(p, g, off) for p, (g, off) in model.parts.items()]
    else:
        pieces = [(None, model.merged(), (0, 0, 0))]

    imgs = atlas_images(export_dir, name)
    mat = palette_material(imgs)
    glow_mat = palette_material(imgs, config.CFG["material"]["glow_emission"]) if emissive else None
    objs, per_obj, neon = [], [], []
    for key, grid, off in pieces:
        mesh = mesher.greedy_mesh(grid, off)
        mesher.validate(grid, mesh)
        glows = key in emissive
        ob = build_object(scn, _object_name(f"{name}_{key}" if key else name), mesh,
                          glow_mat if glows else mat, model.pivot)
        if glows:
            top = int(np.argmax(np.bincount(grid.data.ravel(), minlength=config.NUM_COLORS)[1:])) + 1
            neon.append(f"{ob.name}: MeshPart Material=Neon, Color=#{config.PALETTE[config.name(top)]}")
        objs.append(ob)
        per_obj.append({
            "object": ob.name,
            "voxels": int(np.count_nonzero(grid.data)),
            "exposed_faces": mesh["exposed"],
            "quads": len(mesh["faces"]),
            "triangles": 2 * len(mesh["faces"]),
            "components": 1 if glows else grid.components(),
        })

    scn.view_layers[0].update()
    co = np.array([o.matrix_world @ Vector(c) for o in objs for c in o.bound_box])
    stats = {
        "name": name,
        "voxels": sum(s["voxels"] for s in per_obj),
        "exposed_faces": sum(s["exposed_faces"] for s in per_obj),
        "quads": sum(s["quads"] for s in per_obj),
        "triangles": sum(s["triangles"] for s in per_obj),
        "object_count": len(objs),
        "material_count": 2 if emissive else 1,
        "bbox_studs": [round(float(x), 3) for x in (co.max(0) - co.min(0)) / config.CFG["bu_per_stud"]],
        "objects": per_obj,
    }
    stats["warnings"] = check_limits(stats) + [
        f"{s['object']}: {s['components']} disconnected pieces" for s in per_obj if s["components"] != 1]

    fbx = os.path.join(export_dir, f"{name}.fbx")
    export_fbx(scn, objs, fbx)
    blend = os.path.join(asset_dir, f"{name}.blend")
    write_blend(blend, objs, [m for m in (mat, glow_mat) if m], list(imgs.values()))
    maps = {k: os.path.basename(i.filepath_raw) for k, i in imgs.items()}
    stats["roblox"] = "; ".join([f"SurfaceAppearance: ColorMap={maps['color']}, MetalnessMap={maps['metalness']}, "
                                 f"RoughnessMap={maps['roughness']}"] + neon)
    stats["files"] = ([fbx, blend] + [i.filepath_raw for i in imgs.values()]
                      + (render_views(scn, objs, render_dir, extra_views=extra_views) if render else []))
    return stats
