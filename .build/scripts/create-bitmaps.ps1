# Create western-themed bitmaps for NSIS installer
# header.bmp: 150x57 pixels
# wizard.bmp: 164x314 pixels

param(
    [string]$OutputDir = "..\installer"
)

Add-Type -AssemblyName System.Drawing

$installerDir = $OutputDir

# Create header bitmap (150x57) - Top banner
Write-Host "Creating header.bmp..." -ForegroundColor Cyan
$headerWidth = 150
$headerHeight = 57
$headerBmp = New-Object System.Drawing.Bitmap($headerWidth, $headerHeight)
$headerGraphics = [System.Drawing.Graphics]::FromImage($headerBmp)
$headerGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

# Western sunset gradient background
$headerRect = New-Object System.Drawing.Rectangle(0, 0, $headerWidth, $headerHeight)
$startColor = [System.Drawing.Color]::FromArgb(255, 140, 60, 30)  # Dark orange
$endColor = [System.Drawing.Color]::FromArgb(255, 200, 120, 60)   # Light orange
$brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($headerRect, $startColor, $endColor, 90.0)
$headerGraphics.FillRectangle($brush, 0, 0, $headerWidth, $headerHeight)

# Draw simple mountain silhouettes
$mountainBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(180, 60, 30, 15))
$mountain1 = @(
    (New-Object System.Drawing.Point(0, $headerHeight)),
    (New-Object System.Drawing.Point(40, 20)),
    (New-Object System.Drawing.Point(80, $headerHeight))
)
$headerGraphics.FillPolygon($mountainBrush, $mountain1)

$mountain2 = @(
    (New-Object System.Drawing.Point(60, $headerHeight)),
    (New-Object System.Drawing.Point(100, 25)),
    (New-Object System.Drawing.Point(140, $headerHeight))
)
$headerGraphics.FillPolygon($mountainBrush, $mountain2)

# Add text "RDO Overlay"
$font = New-Object System.Drawing.Font("Arial", 16, [System.Drawing.FontStyle]::Bold)
$textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$shadowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(100, 0, 0, 0))

# Shadow
$headerGraphics.DrawString("RDO", $font, $shadowBrush, 12, 7)
$headerGraphics.DrawString("Overlay", $font, $shadowBrush, 12, 27)
# Main text
$headerGraphics.DrawString("RDO", $font, $textBrush, 10, 5)
$headerGraphics.DrawString("Overlay", $font, $textBrush, 10, 25)

# Save header
$headerBmp.Save("$installerDir\header.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
Write-Host "Header bitmap created (150x57)" -ForegroundColor Green

# Cleanup
$brush.Dispose()
$mountainBrush.Dispose()
$font.Dispose()
$textBrush.Dispose()
$shadowBrush.Dispose()
$headerGraphics.Dispose()
$headerBmp.Dispose()

# Create wizard bitmap (164x314) - Side panel
Write-Host "Creating wizard.bmp..." -ForegroundColor Cyan
$wizardWidth = 164
$wizardHeight = 314
$wizardBmp = New-Object System.Drawing.Bitmap($wizardWidth, $wizardHeight)
$wizardGraphics = [System.Drawing.Graphics]::FromImage($wizardBmp)
$wizardGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

# Sunset sky gradient
$skyRect = New-Object System.Drawing.Rectangle(0, 0, $wizardWidth, $wizardHeight)
$skyTop = [System.Drawing.Color]::FromArgb(255, 100, 50, 30)
$skyBottom = [System.Drawing.Color]::FromArgb(255, 220, 150, 100)
$skyBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($skyRect, $skyTop, $skyBottom, 90.0)
$wizardGraphics.FillRectangle($skyBrush, 0, 0, $wizardWidth, $wizardHeight)

# Draw a simple sun
$sunBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 255, 200, 100))
$sunRect = New-Object System.Drawing.Rectangle(100, 40, 50, 50)
$wizardGraphics.FillEllipse($sunBrush, $sunRect)

# Desert ground
$groundBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 139, 90, 43))
$groundY = [int]($wizardHeight * 0.7)
$wizardGraphics.FillRectangle($groundBrush, 0, $groundY, $wizardWidth, $wizardHeight - $groundY)

# Draw simple cacti silhouettes
$cactusBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 60, 80, 40))

# Cactus 1 (left)
$wizardGraphics.FillRectangle($cactusBrush, 20, $groundY + 20, 15, 60)
$wizardGraphics.FillRectangle($cactusBrush, 10, $groundY + 30, 15, 30)
$wizardGraphics.FillRectangle($cactusBrush, 25, $groundY + 35, 15, 25)

# Cactus 2 (right, smaller)
$wizardGraphics.FillRectangle($cactusBrush, 120, $groundY + 40, 12, 45)
$wizardGraphics.FillRectangle($cactusBrush, 110, $groundY + 50, 12, 20)

# Add tumbleweeds (circles)
$tumbleweedBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(150, 101, 67, 33))
$wizardGraphics.FillEllipse($tumbleweedBrush, 80, $groundY + 50, 20, 15)
$wizardGraphics.FillEllipse($tumbleweedBrush, 140, $groundY + 70, 15, 12)

# Draw a cowboy hat silhouette at bottom
$hatY = $wizardHeight - 80
$hatBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(200, 101, 67, 33))
# Hat brim
$wizardGraphics.FillEllipse($hatBrush, 50, $hatY + 30, 64, 20)
# Hat crown
$wizardGraphics.FillEllipse($hatBrush, 65, $hatY, 34, 35)

# Add decorative stars
$starBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(150, 255, 255, 200))
for ($i = 0; $i -lt 8; $i++) {
    $x = Get-Random -Minimum 10 -Maximum 150
    $y = Get-Random -Minimum 10 -Maximum 100
    $wizardGraphics.FillEllipse($starBrush, $x, $y, 3, 3)
}

# Save wizard
$wizardBmp.Save("$installerDir\wizard.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
Write-Host "Wizard bitmap created (164x314)" -ForegroundColor Green

# Cleanup
$skyBrush.Dispose()
$sunBrush.Dispose()
$groundBrush.Dispose()
$cactusBrush.Dispose()
$tumbleweedBrush.Dispose()
$hatBrush.Dispose()
$starBrush.Dispose()
$wizardGraphics.Dispose()
$wizardBmp.Dispose()

Write-Host ""
Write-Host "🤠 All western-themed bitmaps created!" -ForegroundColor Cyan
