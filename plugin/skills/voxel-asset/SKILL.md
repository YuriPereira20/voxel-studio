---
name: voxel-asset
description: Create voxel-art 3D assets for Roblox (weapons, tools, characters, animals, trees, props, buildings) from a reference image or a text description, built in Blender through the Blender MCP and exported as an optimized FBX with PBR palette maps. Use when the user asks for a voxel asset or model ("crie uma espada voxel", "faz esse item em voxel", "voxel tree for my game"), sends an image to turn into a voxel model, or wants to edit, re-render or re-export an existing voxel asset.
---

# Voxel asset pipeline

Reference (image or Codex-generated) → voxel grid in Python (`voxelstudio`) → greedy-meshed mesh in Blender → visual validation against the reference → FBX + palette maps for Roblox.

Follow this workflow without asking the user to explain the process. Only ask when the request is genuinely ambiguous (what the object is, which reference to follow).

## Paths
- `LIB` = this skill's base directory (shown when the skill loads). It holds `voxelstudio/`, `config/voxel_config.json` (default config) and `tools/gen_reference.ps1`.
- `PROJECT` = the user's current project folder (the working directory).
- Assets live in `PROJECT/voxel_assets/<name>/`: `build.py`, `reference/`, `renders/`, `export/`, `<name>.blend`.

## Requirements (check once per session)
- Blender running with the Blender MCP connected (`execute_blender_code`). If its tools are deferred, load them with ToolSearch (`select:mcp__Blender__execute_blender_code`).
- For generated references: Codex CLI with the `image_generation` feature (`codex features list`). The script passes `-m gpt-6-sol` because other models can be rejected for ChatGPT accounts; change `-Model` if that model is unavailable.

## First use in a project
If `PROJECT/voxel_config.json` does not exist, copy `LIB/config/voxel_config.json` there and tell the user. That file is the game's visual identity (voxel size, palette, materials, limits, export rules); every asset in the project follows it. **The palette is append-only**: reordering or removing colours changes every existing asset. Add new colours at the end.

## Workflow
1. **Reference**
   - User sent a clean orthographic image on a plain background → save it as `voxel_assets/<name>/reference/front.png`.
   - User sent any other image (perspective, dark/gradient background, lighting effects) → have Codex redraw it cleanly:
     `powershell -File "<LIB>\tools\gen_reference.ps1" -Project "<PROJECT>" -Name <name> -Source "<image path>" -Description "<short English description of the details>"`
     The original is kept as `reference/source.<ext>` and stays the authority for the final comparison, because Codex may drift.
   - No image → `powershell -File "<LIB>\tools\gen_reference.ps1" -Project "<PROJECT>" -Name <name> -Description "<what the user asked, in English, with style and colour details>"`.
   - Default views are front + side. Add `-Views front,side,top` when the top matters (characters, buildings). Run it in the background; it takes 1–3 min per view.
   - Look at every reference image. Regenerate it if it is unusable (perspective, cropped, cluttered).
2. **Analyse** the reference: silhouette, proportions, colour areas, palette matches (`vs.reference.palette_report`).
   - **Resolution rule: match the reference's detail.** Measure the cube pitch with `vs.reference.cube_pitch(front.png)` and build at about 1 voxel per reference cube, even if the model gets large in studs; the user scales it down at Roblox import.
   - Never drop details (runes, wear, skulls…) to hit a target size.
   - Without an image, use a standard scale of about 45–75 voxels for the main axis.
3. **Build** `voxel_assets/<name>/build.py` with the bootstrap below. Use `image_to_layer` for the front silhouette and colours (quantize against a **fixed list of colours**, never "whatever is in the palette now", so later palette additions don't change the asset). Then:
   - Flatten baked lighting into clean palette colours.
   - Replace noisy areas with clean geometric shapes. Designed plates, horns and skulls look better authored in code than quantized.
   - Set depth from the side view.
   - Mirror symmetric parts.
   - Remove stray voxels (`keep_largest`, `clean_layer`, `prune_specks`).
   - Use named parts.
4. **Run** it in Blender: `exec(open(r"<PROJECT>\voxel_assets\<name>\build.py").read())`. Stats come back in `result`. Work only in the `VoxelLab` scene; never modify or save the user's open .blend file.
5. **Validate visually.** Do not approve a model just because the code ran.
   - Read the renders (`front`, `side`, `three_quarter`, `top_down`, `wireframe`, plus `compare_*` and any close-ups).
   - Compare them side by side with the reference (`vs.reference.compare_images`). For image-based assets, also compare against `source.*`; use a dark `hero` render if the source is dark.
   - List the differences (silhouette, proportions, colour values, missing or noisy details, things that only read in 3D), fix them and re-run.
   - Do at least one correction pass, and at least two for detailed assets.
6. **Deliver.**
   - Send the key renders to the user with SendUserFile.
   - Report:
     - stats per mesh (voxels, triangles);
     - size in studs;
     - the FBX path `voxel_assets/<name>/export/<name>.fbx`;
     - the honest remaining differences from the reference.

## Build script bootstrap
```python
import sys
LIB = r"<LIB>"            # this skill's base directory
PROJECT = r"<PROJECT>"    # the user's project folder
for _m in [m for m in sys.modules if m == "voxelstudio" or m.startswith("voxelstudio.")]:
    del sys.modules[_m]   # drop a stale copy loaded from another path or version
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import voxelstudio
vs = voxelstudio.reload_all(project=PROJECT)
```
Templates are in the repo's `voxel_assets/` folder (https://github.com/YuriPereira20/voxel-studio/tree/main/voxel_assets):
- `sword`: multi-part, hand-built;
- `axe`: built from a reference;
- `dark_sword`: high-density reference with a glow mesh;
- `tree`: organic shapes with noise.

## Library API (`voxelstudio`)
- Colours are a palette name or an index everywhere. Masks are a bool array or a vectorised `f(X, Y, Z)` in model coordinates.
- `VoxelModel(pivot)`: `add_part(name, size, origin, offset)` returns a `VoxelGrid`; `part(name)`; `merged(names=None)`.
- `VoxelGrid` (fixed size; out-of-bounds writes raise):
  - read and write: `set/get`;
  - filling: `fill_box`, `fill_sphere`, `fill_ellipsoid`, `fill_cylinder(axis)`, `line(p0, p1, c, radius)`, `fill_mask`;
  - editing: `remove(mask)`, `paint(c, where, replace)`;
  - transforms: `mirror(axis)`, `extrude_2d(layer, at, depth, plane)`, `translate`, `rotate90`, `copy/paste`;
  - detail and cleanup: `noise(cell, seed)`, `keep_largest()`;
  - `stats()`.
- `reference`:
  - `cube_pitch(path)`;
  - `image_to_layer(path, width_voxels=, height_voxels=, exclude=())`;
  - `clean_layer`, `prune_specks(mask, min_size)`;
  - `palette_report(path)`, `layer_report(layer)`;
  - `compare_images(ref, render, out)`.
- `finalize(model, name, per_part=False, meshes=None, emissive=(), extra_views=None)`:
  - meshes the model (face culling + greedy merge);
  - self-checks area, UVs, colours and material maps, plus geometry limits (20k triangles per mesh);
  - writes the FBX, colour/metalness/roughness atlases, the .blend and the standard renders;
  - `meshes={"body": [...], "glow": ["glow"]}` groups parts into meshes, `emissive=("glow",)` makes glow meshes;
  - `extra_views` adds views such as `hero` or a close-up with `"region"`.

## Roblox
- **Mesh:** one mesh with one palette material per asset. Glowing details (runes, eyes, crystals) go in a separate emissive mesh, which becomes a MeshPart with Material = Neon.
- **Materials:** put `<name>_color.png`, `<name>_metalness.png` and `<name>_roughness.png` into a SurfaceAppearance (ColorMap, MetalnessMap, RoughnessMap). Metal and roughness are per palette colour (the `materials` map in the config).
- **Scale and pivot:** the user scales on import. The pivot is at the grip or base as each build sets it.

## Lessons
- Reference images bake lighting into colour. Quantize, then flatten shading and replace near-miss tints (for example bluish grays).
- Isolated single-voxel "detail" (grain specks) reads as a defect; use long streaks or nothing.
- A thick dark fuller with big runes reads as letters. Keep glyphs small, with a margin, and keep cracks thin.
- Large flat up-facing metal surfaces blow out to white in 3/4 renders; use rougher metal for big flats.
- Cloth must not share the glow colour, or it reads as glowing.
- Depth is never automatic: always author the thickness profile from the side view.
