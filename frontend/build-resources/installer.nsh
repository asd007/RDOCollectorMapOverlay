; Custom NSIS installer script for downloading backend at install time

!macro customInit
  ; Set up variables for component downloads
  Var /GLOBAL BackendURL
  Var /GLOBAL BackendSize

  ; Backend download URL (you'll update this with each release)
  StrCpy $BackendURL "https://github.com/YOUR_USERNAME/rdo-overlay/releases/download/backend-v1.0.0/rdo-overlay-backend.exe"
  StrCpy $BackendSize "60000000" ; ~60MB in bytes
!macroend

!macro customInstall
  ; Download backend during installation
  DetailPrint "Downloading Python backend..."

  ; Create backend directory
  CreateDirectory "$INSTDIR\resources\backend"

  ; Download backend executable
  NSISdl::download_quiet "$BackendURL" "$INSTDIR\resources\backend\rdo-overlay-backend.exe"
  Pop $0
  ${If} $0 != "success"
    MessageBox MB_OK|MB_ICONEXCLAMATION "Failed to download backend component. Please check your internet connection and try again."
    Abort
  ${EndIf}

  DetailPrint "Backend downloaded successfully"
!macroend

!macro customUninstall
  ; Clean up backend and cached data
  RMDir /r "$INSTDIR\resources\backend"

  ; Also remove cached map data
  RMDir /r "$APPDATA\RDO-Map-Overlay"
!macroend