# Generates voxel-style reference images with Codex (image_generation tool).
# Usage: .\plugin\skills\voxel-asset\tools\gen_reference.ps1 -Name axe -Description "stylized medieval battle axe with wooden handle"
# Output: <Project>\voxel_assets\<Name>\reference\<view>.png  (front first; other views get front.png attached for consistency)
# With -Source <image>: the user's image is attached to every view and Codex redraws it cleanly (ortho, magenta bg);
# the original is kept as reference\source.<ext> for the final comparison.
param(
    [Parameter(Mandatory)][string]$Name,
    [string]$Description = 'the object shown in the attached source image',
    [string]$Source,
    [string[]]$Views = @('front', 'side'),
    # Explicit model: the default in ~/.codex/config.toml (gpt-6.1-sol) is rejected for ChatGPT accounts.
    [string]$Model = 'gpt-6-sol',
    [string]$Project = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
$outDir = Join-Path $Project "voxel_assets\$Name\reference"
New-Item -ItemType Directory -Force $outDir | Out-Null
$srcCopy = $null
if ($Source) {
    $srcCopy = Join-Path $outDir ('source' + [IO.Path]::GetExtension($Source))
    Copy-Item $Source $srcCopy -Force
    $Description += '. Reproduce the attached source image faithfully: same design, details, colors and proportions; only change the view, background and lighting as instructed'
}

$viewText = @{
    front         = 'straight front view, orthographic (no perspective)'
    side          = 'straight side view from the right, orthographic (no perspective), of the SAME object shown in the attached image: match its design, colors and proportions exactly'
    back          = 'straight back view, orthographic (no perspective), of the SAME object shown in the attached image: match its design, colors and proportions exactly'
    top           = 'straight top-down view, orthographic (no perspective), of the SAME object shown in the attached image: match its design, colors and proportions exactly'
    three_quarter = '3/4 isometric view showing front, side and top, of the SAME object shown in the attached image: match its design, colors and proportions exactly'
}

foreach ($view in $Views) {
    if (-not $viewText.ContainsKey($view)) { throw "Unknown view '$view'. Use: $($viewText.Keys -join ', ')" }
    $rel = "voxel_assets\$Name\reference\$view.png"
    # No double quotes inside the prompt: PowerShell 5.1 mangles them when passing args to native exes.
    $prompt = @"
Use your image generation tool to create ONE reference image of a game asset: $Description.
Style: voxel art built entirely from small visible uniform cubes, stylized, chunky readable proportions, saturated flat colors with minimal shading, no outlines.
View: $($viewText[$view]). Whole object visible and centered, filling about 80 percent of the frame.
Background: plain solid pure magenta (#FF00FF), no ground, no shadow, no text, no extra objects.
Then copy the generated PNG to $rel (relative to the current directory) and print its path. Do nothing else.
"@
    $codexArgs = @('exec', '--skip-git-repo-check', '-m', $Model, '-s', 'workspace-write', '-C', $Project, $prompt)
    $front = Join-Path $outDir 'front.png'
    # -i goes after the prompt: it takes multiple values and would swallow the prompt otherwise.
    $images = @()
    if ($srcCopy) { $images += $srcCopy }
    if ($view -ne 'front' -and (Test-Path $front)) { $images += $front }
    if ($images) { $codexArgs += @('-i') + $images }
    Write-Host "Generating $view view..."
    # PS 5.1 turns native stderr into terminating errors under 'Stop'; $null closes stdin so codex doesn't wait on it.
    $ErrorActionPreference = 'Continue'
    $null | & codex @codexArgs 2>&1 | ForEach-Object { "$_" } | Select-Object -Last 5 | Out-Host
    $ErrorActionPreference = 'Stop'
    $file = Join-Path $Project $rel
    if (-not (Test-Path $file)) { throw "Codex did not produce $rel" }
    Write-Host "OK $file"
}
