[CmdletBinding()]
param(
    [string]$SourceDir = "D:\Code\CLionProjects\terraviewer-images\bestiary",
    [string]$NpcIdSource = "C:\Users\depths\Desktop\Tdecoder\code\Terraria\ID\NPCID.cs",
    [string]$OutputDir = $SourceDir,
    [int]$CanvasSize = 96,
    [int]$Padding = 8,
    [string]$ReportPath = "D:\Code\CLionProjects\terraviewer-images\bestiary\_normalization_report.tsv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function Get-CustomPortraitNpcIds {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $ids = New-Object 'System.Collections.Generic.HashSet[int]'
    $pattern = 'CustomTexturePath\s*=\s*"Images/UI/Bestiary/NPCs/NPC_(?<id>-?\d+)"'
    foreach ($line in Get-Content -Path $Path) {
        $match = [regex]::Match($line, $pattern)
        if ($match.Success) {
            [void]$ids.Add([int]$match.Groups['id'].Value)
        }
    }

    return $ids
}

function Get-AlphaBounds {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Bitmap]$Bitmap
    )

    $minX = $Bitmap.Width
    $minY = $Bitmap.Height
    $maxX = -1
    $maxY = -1

    for ($y = 0; $y -lt $Bitmap.Height; $y++) {
        for ($x = 0; $x -lt $Bitmap.Width; $x++) {
            $pixel = $Bitmap.GetPixel($x, $y)
            if ($pixel.A -gt 0) {
                if ($x -lt $minX) { $minX = $x }
                if ($y -lt $minY) { $minY = $y }
                if ($x -gt $maxX) { $maxX = $x }
                if ($y -gt $maxY) { $maxY = $y }
            }
        }
    }

    if ($maxX -lt 0 -or $maxY -lt 0) {
        return [System.Drawing.Rectangle]::FromLTRB(0, 0, $Bitmap.Width, $Bitmap.Height)
    }

    return [System.Drawing.Rectangle]::FromLTRB($minX, $minY, $maxX + 1, $maxY + 1)
}

function Get-StripCropBounds {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Rectangle]$Bounds,
        [Parameter(Mandatory = $true)]
        [bool]$IsCustomPortrait
    )

    $action = "keep"
    if ($IsCustomPortrait) {
        return @{
            Bounds = $Bounds
            Action = "keep_custom_bestiary_texture"
        }
    }

    $width = [double]$Bounds.Width
    $height = [double]$Bounds.Height

    if ($width -ge ($height * 2.0)) {
        $frames = [Math]::Round($width / $height)
        if ($frames -ge 2) {
            $frameWidth = [Math]::Round($width / $frames)
            $delta = [Math]::Abs($frameWidth - $height) / [Math]::Max($height, 1.0)
            if ($delta -le 0.35) {
                return @{
                    Bounds = [System.Drawing.Rectangle]::FromLTRB($Bounds.X, $Bounds.Y, $Bounds.X + $frameWidth, $Bounds.Bottom)
                    Action = "crop_horizontal_strip_first_frame"
                }
            }
        }
    }

    if ($height -ge ($width * 2.0)) {
        $frames = [Math]::Round($height / $width)
        if ($frames -ge 2) {
            $frameHeight = [Math]::Round($height / $frames)
            $delta = [Math]::Abs($frameHeight - $width) / [Math]::Max($width, 1.0)
            if ($delta -le 0.35) {
                return @{
                    Bounds = [System.Drawing.Rectangle]::FromLTRB($Bounds.X, $Bounds.Y, $Bounds.Right, $Bounds.Y + $frameHeight)
                    Action = "crop_vertical_strip_first_frame"
                }
            }
        }
    }

    return @{
        Bounds = $Bounds
        Action = $action
    }
}

function Save-NormalizedIcon {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [int]$CanvasSize,
        [Parameter(Mandatory = $true)]
        [int]$Padding,
        [Parameter(Mandatory = $true)]
        [bool]$IsCustomPortrait
    )

    $inputBytes = [System.IO.File]::ReadAllBytes($InputPath)
    $inputStream = [System.IO.MemoryStream]::new($inputBytes, $false)
    $sourceBitmap = [System.Drawing.Bitmap]::new($inputStream)
    try {
        $trimmedBounds = Get-AlphaBounds -Bitmap $sourceBitmap
        $cropDecision = Get-StripCropBounds -Bounds $trimmedBounds -IsCustomPortrait $IsCustomPortrait
        $finalBounds = [System.Drawing.Rectangle]$cropDecision.Bounds

        $croppedBitmap = $sourceBitmap.Clone($finalBounds, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $innerSize = [Math]::Max(1, $CanvasSize - ($Padding * 2))
            $scale = [Math]::Min($innerSize / [double]$croppedBitmap.Width, $innerSize / [double]$croppedBitmap.Height)
            $drawWidth = [Math]::Max(1, [int][Math]::Round($croppedBitmap.Width * $scale))
            $drawHeight = [Math]::Max(1, [int][Math]::Round($croppedBitmap.Height * $scale))
            $offsetX = [int][Math]::Floor(($CanvasSize - $drawWidth) / 2.0)
            $offsetY = [int][Math]::Floor(($CanvasSize - $drawHeight) / 2.0)

            $canvas = [System.Drawing.Bitmap]::new($CanvasSize, $CanvasSize, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
            try {
                $graphics = [System.Drawing.Graphics]::FromImage($canvas)
                try {
                    $graphics.Clear([System.Drawing.Color]::Transparent)
                    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
                    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
                    $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
                    $graphics.DrawImage($croppedBitmap, $offsetX, $offsetY, $drawWidth, $drawHeight)
                }
                finally {
                    $graphics.Dispose()
                }

                $temporaryOutputPath = if ([string]::Equals($InputPath, $OutputPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                    "$OutputPath.__tmp__.png"
                }
                else {
                    $OutputPath
                }

                $canvas.Save($temporaryOutputPath, [System.Drawing.Imaging.ImageFormat]::Png)

                if ($temporaryOutputPath -ne $OutputPath) {
                    if (Test-Path -LiteralPath $OutputPath) {
                        Remove-Item -LiteralPath $OutputPath -Force
                    }
                    [System.IO.File]::Move($temporaryOutputPath, $OutputPath)
                }
            }
            finally {
                $canvas.Dispose()
            }

            return [PSCustomObject]@{
                OriginalWidth = $sourceBitmap.Width
                OriginalHeight = $sourceBitmap.Height
                TrimmedWidth = $trimmedBounds.Width
                TrimmedHeight = $trimmedBounds.Height
                FinalCropWidth = $finalBounds.Width
                FinalCropHeight = $finalBounds.Height
                DrawWidth = $drawWidth
                DrawHeight = $drawHeight
                Action = [string]$cropDecision.Action
            }
        }
        finally {
            $croppedBitmap.Dispose()
        }
    }
    finally {
        $sourceBitmap.Dispose()
        $inputStream.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $SourceDir)) {
    throw "Source directory not found: $SourceDir"
}

if (-not (Test-Path -LiteralPath $NpcIdSource)) {
    throw "NPCID source not found: $NpcIdSource"
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($ReportPath)) -Force | Out-Null

$customPortraitIds = Get-CustomPortraitNpcIds -Path $NpcIdSource
$reportRows = New-Object System.Collections.Generic.List[string]
$reportRows.Add("file`tnpcNetId`tisCustomPortrait`toriginalWidth`toriginalHeight`ttrimmedWidth`ttrimmedHeight`tfinalCropWidth`tfinalCropHeight`tdrawWidth`tdrawHeight`taction")

Get-ChildItem -LiteralPath $SourceDir -File -Filter "npc_*.png" |
    Sort-Object Name |
    ForEach-Object {
        if ($_.BaseName -notmatch '^npc_(?<id>-?\d+)$') {
            return
        }

        $npcNetId = [int]$Matches['id']
        $isCustomPortrait = $customPortraitIds.Contains($npcNetId)
        $result = Save-NormalizedIcon `
            -InputPath $_.FullName `
            -OutputPath (Join-Path $OutputDir $_.Name) `
            -CanvasSize $CanvasSize `
            -Padding $Padding `
            -IsCustomPortrait $isCustomPortrait

        $reportRows.Add((
            "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}`t{9}`t{10}`t{11}" -f
            $_.Name,
            $npcNetId,
            $isCustomPortrait.ToString().ToLowerInvariant(),
            $result.OriginalWidth,
            $result.OriginalHeight,
            $result.TrimmedWidth,
            $result.TrimmedHeight,
            $result.FinalCropWidth,
            $result.FinalCropHeight,
            $result.DrawWidth,
            $result.DrawHeight,
            $result.Action
        ))
    }

Set-Content -LiteralPath $ReportPath -Value $reportRows -Encoding UTF8
Write-Host "Normalized bestiary icons written to $OutputDir"
Write-Host "Report written to $ReportPath"
