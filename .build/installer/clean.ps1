# Quick cleanup script for RDO Overlay installer build artifacts

Write-Host "Cleaning RDO Overlay installer build artifacts..." -ForegroundColor Cyan

# Remove plugin downloads
Remove-Item ".\Plugins" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\*.zip" -Force -ErrorAction SilentlyContinue
Remove-Item ".\temp_plugin" -Recurse -Force -ErrorAction SilentlyContinue

# Remove generated files
Remove-Item ".\header.bmp" -Force -ErrorAction SilentlyContinue
Remove-Item ".\wizard.bmp" -Force -ErrorAction SilentlyContinue
Remove-Item ".\_plugins.nsh" -Force -ErrorAction SilentlyContinue

# Remove generated icon
Remove-Item "..\..\frontend\icon.ico" -Force -ErrorAction SilentlyContinue

# Remove built installers
Remove-Item "..\..\build\installer\*.exe" -Force -ErrorAction SilentlyContinue

Write-Host "Cleanup complete!" -ForegroundColor Green
