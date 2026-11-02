# VoxelStudio — dev repo of the `voxel-studio` plugin

The asset workflow, rules, API and lessons live in **`plugin/skills/voxel-asset/SKILL.md`** — follow it for any asset request (here or in any project where the plugin is installed). Don't duplicate it here.

## Layout
- `plugin/` — the plugin (`.claude-plugin/plugin.json`, `skills/voxel-asset/` with `SKILL.md`, `voxelstudio/` library, `config/voxel_config.json` default config, `tools/gen_reference.ps1`).
- `.claude-plugin/marketplace.json` — local marketplace pointing at `./plugin`.
- This repo is also a project using the plugin: `voxel_config.json` (project config) and `voxel_assets/<name>/` (sword, axe, tree, dark_sword — templates for new assets). Their `build.py` bootstrap points at `plugin/skills/voxel-asset` directly, so library edits apply here without reinstalling.

## Releasing a library/skill change
1. Edit under `plugin/`, re-run the four assets here and check the stats are unchanged (sword 626/188/376, axe 1372/228/456, tree 7121/2371/4742, dark_sword body 18045 + glow 270 voxels, 11874 triangles).
2. Bump `version` in `plugin/.claude-plugin/plugin.json`.
3. `claude plugin marketplace update voxel-studio` then `claude plugin update voxel-studio@voxel-studio` (restart Claude Code to load it).

Model routing: 3D building/validation → `opus-3d-builder`; routine code/file work → `haiku-worker`.
