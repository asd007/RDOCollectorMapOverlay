# Create a funny western-themed icon for RDO Overlay
# Features a simple cowboy hat design

Add-Type -AssemblyName System.Drawing

$sizes = @(16, 32, 48, 256)
$iconPath = "..\..\frontend\icon.ico"

# Create a bitmap for each size
$bitmaps = @()

foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    # Clear background (transparent)
    $graphics.Clear([System.Drawing.Color]::Transparent)

    # Scale factor for drawing
    $scale = $size / 32.0

    # Colors - brown cowboy hat
    $hatBrown = [System.Drawing.Color]::FromArgb(139, 90, 43)
    $hatDark = [System.Drawing.Color]::FromArgb(101, 67, 33)
    $hatLight = [System.Drawing.Color]::FromArgb(160, 110, 60)

    # Create brushes
    $brownBrush = New-Object System.Drawing.SolidBrush($hatBrown)
    $darkBrush = New-Object System.Drawing.SolidBrush($hatDark)
    $lightBrush = New-Object System.Drawing.SolidBrush($hatLight)

    # Draw cowboy hat brim (bottom oval)
    $brimRect = New-Object System.Drawing.RectangleF(
        [float]($size * 0.1),
        [float]($size * 0.6),
        [float]($size * 0.8),
        [float]($size * 0.25)
    )
    $graphics.FillEllipse($darkBrush, $brimRect)

    # Draw hat crown (rounded rectangle)
    $crownRect = New-Object System.Drawing.RectangleF(
        [float]($size * 0.25),
        [float]($size * 0.2),
        [float]($size * 0.5),
        [float]($size * 0.5)
    )
    $graphics.FillEllipse($brownBrush, $crownRect)

    # Add highlight to make it look 3D
    $highlightRect = New-Object System.Drawing.RectangleF(
        [float]($size * 0.28),
        [float]($size * 0.25),
        [float]($size * 0.3),
        [float]($size * 0.15)
    )
    $graphics.FillEllipse($lightBrush, $highlightRect)

    # Add a funny detail - a tiny star badge/pin on the hat
    $starSize = [Math]::Max(2, [int]($size * 0.15))
    $starX = [int]($size * 0.45)
    $starY = [int]($size * 0.45)

    $starBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Gold)
    $starPen = New-Object System.Drawing.Pen([System.Drawing.Color]::DarkGoldenrod, [Math]::Max(1, $scale))

    # Draw a simple star (5 points)
    $starPoints = @()
    for ($i = 0; $i -lt 5; $i++) {
        $angle = [Math]::PI * 2 * $i / 5 - [Math]::PI / 2
        $x = $starX + [Math]::Cos($angle) * $starSize
        $y = $starY + [Math]::Sin($angle) * $starSize
        $starPoints += New-Object System.Drawing.PointF($x, $y)

        # Inner point
        $angle2 = [Math]::PI * 2 * ($i + 0.5) / 5 - [Math]::PI / 2
        $x2 = $starX + [Math]::Cos($angle2) * ($starSize * 0.4)
        $y2 = $starY + [Math]::Sin($angle2) * ($starSize * 0.4)
        $starPoints += New-Object System.Drawing.PointF($x2, $y2)
    }

    if ($size -ge 32) {
        $graphics.FillPolygon($starBrush, $starPoints)
        $graphics.DrawPolygon($starPen, $starPoints)
    }

    # Cleanup brushes
    $brownBrush.Dispose()
    $darkBrush.Dispose()
    $lightBrush.Dispose()
    $starBrush.Dispose()
    $starPen.Dispose()
    $graphics.Dispose()

    $bitmaps += $bmp
}

# Save as ICO file using a temporary PNG conversion method
# Create the icon using the largest bitmap
try {
    $ms = New-Object System.IO.MemoryStream
    $bitmaps[0].Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)

    # Use Icon.FromHandle for simpler conversion
    $iconHandle = $bitmaps[3].GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($iconHandle)

    $fileStream = [System.IO.File]::Create($iconPath)
    $icon.Save($fileStream)
    $fileStream.Close()

    Write-Host "Icon created successfully at $iconPath" -ForegroundColor Green
    Write-Host "🤠 Yeehaw! Cowboy hat icon ready!" -ForegroundColor Cyan
}
catch {
    Write-Host "Failed to create icon: $_" -ForegroundColor Red

    # Fallback: just save the largest bitmap as ICO
    $bitmaps[3].Save($iconPath, [System.Drawing.Imaging.ImageFormat]::Icon)
    Write-Host "Created fallback icon" -ForegroundColor Yellow
}
finally {
    # Cleanup
    foreach ($bmp in $bitmaps) {
        $bmp.Dispose()
    }
    if ($ms) { $ms.Dispose() }
    if ($icon) { $icon.Dispose() }
}
