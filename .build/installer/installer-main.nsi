; RDO Map Overlay - Minimal Web Installer
; This installer downloads all dependencies during installation
; Final installer size: ~1-2MB

Unicode True
SetCompressor /SOLID lzma
SetCompressorDictSize 64

; Required includes
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "FileFunc.nsh"
!include "WinVer.nsh"
!include "installer-config.nsh"

; Add build plugins directory
!addplugindir "..\..\build\installer\Plugins\x86-unicode"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "..\..\icon.ico"
!define MUI_UNICON "..\..\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "..\..\build\installer\header.bmp"  ; 150x57 pixels
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\..\build\installer\wizard.bmp"  ; 164x314 pixels

; Finish page - option to launch application
!define MUI_FINISHPAGE_RUN "$INSTDIR\launcher.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"

; Custom Page Variables
Var DownloadDialog
Var DownloadProgress
Var DownloadLabel
Var CurrentDownload
Var TotalDownloadSize
Var DownloadedSize
Var KeepMapData
Var KeepSharedData
Var CommonAppDataDir

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
Page custom DownloadPage DownloadPageLeave
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ShowInstFilesExpanded
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
UninstPage custom un.KeepDataPage
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; Installer Settings
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\..\build\installer\${PRODUCT_NAME_SAFE}-WebSetup-${PRODUCT_VERSION}.exe"
InstallDir "${DEFAULT_INSTALL_DIR}"
InstallDirRegKey HKLM "Software\${PRODUCT_NAME_SAFE}" ""
RequestExecutionLevel admin
BrandingText "${PRODUCT_NAME} ${PRODUCT_VERSION}"

; Version Info (expects 4-part version like X.X.X.X from build script)
VIProductVersion "${PRODUCT_VERSION}"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "LegalCopyright" "© 2024 ${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Web Installer"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"

; Custom Download Page
Function DownloadPage
  !insertmacro MUI_HEADER_TEXT "Download Components" "Setup will download required components"

  nsDialogs::Create 1018
  Pop $DownloadDialog

  ${NSD_CreateLabel} 0 0 100% 12u "The following components will be downloaded:"
  Pop $0

  ${NSD_CreateLabel} 10 15 100% 10u "• Python Runtime (${PYTHON_SIZE_MB} MB)"
  Pop $0
  ${NSD_CreateLabel} 10 27 100% 10u "• PySide6 + WebEngine (${PYSIDE6_WEBENGINE_SIZE_MB} MB)"
  Pop $0
  ${NSD_CreateLabel} 10 39 100% 10u "• OpenCV + NumPy (${OPENCV_SIZE_MB} MB)"
  Pop $0
  ${NSD_CreateLabel} 10 51 100% 10u "• Backend Packages (${BACKEND_PACKAGES_SIZE_MB} MB)"
  Pop $0
  ${NSD_CreateLabel} 10 63 100% 10u "• Map Data (${MAP_HQ_SIZE_MB} MB) - Required"
  Pop $0

  ${NSD_CreateLabel} 0 85 100% 12u "Total download size: ~250 MB"
  Pop $0
  ${NSD_CreateLabel} 0 100 100% 12u "Installation size: ~380 MB"
  Pop $0

  ${NSD_CreateLabel} 0 130 100% 12u "Internet connection required. Downloads will begin after clicking Next."
  Pop $0

  nsDialogs::Show
FunctionEnd

Function DownloadPageLeave
FunctionEnd

; Helper Function: Download with retry
; Helper function to write to log file
Function LogWrite
  Exch $0
  Push $1
  FileOpen $1 "$CommonAppDataDir\RDO-Map-Overlay\install.log" a
  FileSeek $1 0 END
  FileWrite $1 "$0$\r$\n"
  FileClose $1
  Pop $1
  Pop $0
FunctionEnd

Function DownloadWithRetry
  Pop $R2  ; Output file
  Pop $R1  ; URL
  Pop $R0  ; Display name

  ClearErrors

  retry_download:
  DetailPrint "Downloading $R0..."
  Push "Downloading $R0 from $R1"
  Call LogWrite

  ; Using INetC plugin for better progress and reliability
  inetc::get /TIMEOUT=30000 /RESUME "" \
    /CAPTION "Downloading $R0" \
    /POPUP "" \
    /QUESTION "Download failed. Retry?" \
    "$R1" "$R2" \
    /END

  Pop $0
  ${If} $0 != "OK"
    Push "Download failed: $R0 - Error: $0"
    Call LogWrite
    MessageBox MB_RETRYCANCEL "Failed to download $R0.$\n$\nError: $0$\n$\nRetry?" IDRETRY retry_download
    Abort "Download cancelled by user"
  ${EndIf}
  Push "Download successful: $R0"
  Call LogWrite
FunctionEnd

; Main installation section
Section "Core Components" SEC_CORE
  SectionIn RO  ; Required section

  SetOutPath "$INSTDIR"

  ; Create shared directory for logs in ProgramData
  CreateDirectory "$CommonAppDataDir\RDO-Map-Overlay"

  ; Create installation log file in ProgramData (persists across installations)
  StrCpy $0 "$CommonAppDataDir\RDO-Map-Overlay\install.log"
  FileOpen $9 "$0" w
  FileWrite $9 "RDO Map Overlay Installation Log$\r$\n"
  FileWrite $9 "=================================$\r$\n"
  FileWrite $9 "Installation started: $\r$\n"
  FileWrite $9 "Install directory: $INSTDIR$\r$\n"
  FileWrite $9 "Shared data directory: $CommonAppDataDir\RDO-Map-Overlay$\r$\n"
  FileWrite $9 "Temp directory: ${TEMP_DIR}$\r$\n"
  FileWrite $9 "$\r$\n"
  FileClose $9

  ; Check if this is first-time installation or update
  IfFileExists "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" is_update is_first_time
  is_first_time:
    DetailPrint "First-time installation detected"
    DetailPrint "This will download approximately 250MB (Python + Qt/PySide6 + Map Data)"
    DetailPrint "Installation will take 3-5 minutes"
    Goto check_done
  is_update:
    DetailPrint "Update installation detected"
    DetailPrint "Existing shared components in ProgramData will be reused"
  check_done:

  ; Create temp directory for downloads
  CreateDirectory "${TEMP_DIR}"

  ; Create shared runtime directory in ProgramData (shared across installations)
  CreateDirectory "$CommonAppDataDir\RDO-Map-Overlay\runtime"

  ; Create application directory structure (local to installation)
  CreateDirectory "$INSTDIR\app"
  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\data\cache"

  ; Copy application files (bundled during build)
  SetOutPath "$INSTDIR\app"
  File "..\..\app.py"
  File "..\..\app_qml.py"
  File "..\..\overlay_qt_v2.py"
  File "..\..\requirements.txt"
  File /r /x __pycache__ "..\..\config"
  File /r /x __pycache__ "..\..\core"
  File /r /x __pycache__ "..\..\matching"
  File /r /x __pycache__ "..\..\api"
  File /r /x __pycache__ "..\..\models"
  File /r /x __pycache__ "..\..\qml"

  ; Download Python embeddable (skip if already installed for updates)
  IfFileExists "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" 0 download_python
    DetailPrint "Python already installed, skipping download"
    Push "Python already installed - skipping download"
    Call LogWrite
    Goto python_done

  download_python:
  Push "Python Runtime"
  Push "${PYTHON_URL}"
  Push "${TEMP_DIR}\python.zip"
  Call DownloadWithRetry

  DetailPrint "Extracting Python..."
  CreateDirectory "$CommonAppDataDir\RDO-Map-Overlay\runtime\python"
  nsExec::ExecToLog 'powershell -Command "Expand-Archive -Path \"${TEMP_DIR}\python.zip\" -DestinationPath \"$CommonAppDataDir\RDO-Map-Overlay\runtime\python\" -Force"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK "Failed to extract Python!$\n$\nExit code: $0"
    Abort
  ${EndIf}
  Delete "${TEMP_DIR}\python.zip"

  python_done:

  ; Configure Python to use pip
  DetailPrint "Configuring Python..."

  ; Create python311._pth file to enable site-packages
  FileOpen $1 "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python311._pth" w
  FileWrite $1 "python311.zip$\r$\n"
  FileWrite $1 ".$\r$\n"
  FileWrite $1 "Lib\site-packages$\r$\n"
  FileWrite $1 "import site$\r$\n"
  FileClose $1

  ; Check if pip is already installed (skip if updating)
  ; Note: Embedded Python does NOT include pip by default, so we must install it
  DetailPrint "Checking for pip..."
  nsExec::ExecToLog '"$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" -m pip --version'
  Pop $0

  ${If} $0 == 0
    DetailPrint "pip already installed (from previous installation)"
    Push "pip already installed - skipping"
    Call LogWrite
    Goto pip_done
  ${EndIf}

  ; Download and install pip (required for embedded Python)
  DetailPrint "Installing pip (embedded Python does not include pip)..."
  Push "pip installer"
  Push "${GET_PIP_URL}"
  Push "${TEMP_DIR}\get-pip.py"
  Call DownloadWithRetry

  ; Install pip
  DetailPrint "Running get-pip.py..."
  nsExec::ExecToLog '"$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" "${TEMP_DIR}\get-pip.py" --no-warn-script-location'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK "Warning: pip installation returned code $0"
  ${EndIf}
  Delete "${TEMP_DIR}\get-pip.py"

  pip_done:

  ; Install Python packages (skip if already installed and requirements.txt unchanged)
  DetailPrint "Checking if Python packages need installation..."

  ; Check if python.exe exists
  IfFileExists "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" python_exists
    MessageBox MB_OK "ERROR: python.exe not found!$\n$\nExpected at: $CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe"
    Abort
  python_exists:

  ; Check if requirements.txt exists
  IfFileExists "$INSTDIR\app\requirements.txt" requirements_exists
    MessageBox MB_OK "ERROR: requirements.txt not found!$\n$\nExpected at: $INSTDIR\app\requirements.txt"
    Abort
  requirements_exists:

  ; Check if we can skip pip install (requirements.txt unchanged)
  StrCpy $3 "0"  ; Default: need to install
  IfFileExists "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\.requirements.txt" 0 need_pip_install
    DetailPrint "Checking if requirements.txt changed..."

    ; Compare requirements.txt files
    nsExec::Exec 'fc /b "$INSTDIR\app\requirements.txt" "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\.requirements.txt"'
    Pop $1
    ${If} $1 == 0
      ; Files are identical - skip pip install
      DetailPrint "requirements.txt unchanged, skipping pip install"
      Push "pip install skipped - Python packages already up-to-date"
      Call LogWrite
      StrCpy $3 "1"  ; Skip pip install
      Goto pip_install_done
    ${EndIf}
  need_pip_install:

  ${If} $3 == "0"
    DetailPrint "Running pip install..."
    Push "Running pip install"
    Call LogWrite

    nsExec::ExecToLog '"$CommonAppDataDir\RDO-Map-Overlay\runtime\python\python.exe" -m pip install --no-warn-script-location -r "$INSTDIR\app\requirements.txt"'
    Pop $0
    DetailPrint "pip install exit code: $0"
    Push "pip install exit code: $0"
    Call LogWrite

    ${If} $0 != 0
      Push "ERROR: pip install failed with exit code $0"
      Call LogWrite
      MessageBox MB_YESNO "pip install returned error code $0.$\n$\nContinue anyway? (Application may not work correctly)" IDYES pip_continue
      Abort
    pip_continue:
    ${EndIf}

    DetailPrint "Python packages installed successfully"
    Push "Python packages installed successfully"
    Call LogWrite

    ; Save copy of requirements.txt to detect changes on next install
    CopyFiles "$INSTDIR\app\requirements.txt" "$CommonAppDataDir\RDO-Map-Overlay\runtime\python\.requirements.txt"
  ${EndIf}

  pip_install_done:

  ; Create launcher batch file (launches Qt/QML overlay)
  FileOpen $1 "$INSTDIR\launcher.bat" w
  FileWrite $1 "@echo off$\r$\n"
  FileWrite $1 "cd /d $\"%~dp0app$\"$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "REM Python runtime path in ProgramData$\r$\n"
  FileWrite $1 "set PYTHON_PATH=%PROGRAMDATA%\RDO-Map-Overlay\runtime\python\python.exe$\r$\n"
  FileWrite $1 "set PYTHONPATH=%~dp0app$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "REM Launch Qt/QML overlay application$\r$\n"
  FileWrite $1 "$\"%PYTHON_PATH%$\" app_qml.py$\r$\n"
  FileClose $1

  ; Clean up temp directory
  RMDir /r "${TEMP_DIR}"

  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${START_MENU_DIR}"
  CreateShortCut "$SMPROGRAMS\${START_MENU_DIR}\${PRODUCT_NAME}.lnk" \
    "$INSTDIR\launcher.bat" "" "" 0 SW_SHOWMINIMIZED
  CreateShortCut "$SMPROGRAMS\${START_MENU_DIR}\Uninstall.lnk" \
    "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" \
    "$INSTDIR\launcher.bat" "" "" 0 SW_SHOWMINIMIZED

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Write registry keys
  WriteRegStr HKLM "Software\${PRODUCT_NAME_SAFE}" "" "$INSTDIR"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "NoRepair" 1

  ; Calculate and write install size
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"

  ; Write completion to log
  Push "================================="
  Call LogWrite
  Push "Installation completed successfully!"
  Call LogWrite
  Push "Install directory: $INSTDIR"
  Call LogWrite
  Push "Shared data directory: $CommonAppDataDir\RDO-Map-Overlay"
  Call LogWrite
  Push "Log file: $CommonAppDataDir\RDO-Map-Overlay\install.log"
  Call LogWrite
  Push "================================="
  Call LogWrite

  ; Show log file location
  DetailPrint "Installation complete! Log file: $CommonAppDataDir\RDO-Map-Overlay\install.log"
SectionEnd

; Map data section (required for first-time installation)
Section "Download Map Data" SEC_MAP
  SectionIn RO  ; Required section

  ; Create shared data directory in ProgramData
  CreateDirectory "$CommonAppDataDir\RDO-Map-Overlay\data"

  ; Check if map already exists in ProgramData (shared across installations)
  IfFileExists "$CommonAppDataDir\RDO-Map-Overlay\data\rdr2_map_hq.png" map_exists 0
    DetailPrint "Downloading map data (167MB, this may take a while)..."
    Push "Map Data"
    Push "${MAP_HQ_URL}"
    Push "$CommonAppDataDir\RDO-Map-Overlay\data\rdr2_map_hq.png"
    Call DownloadWithRetry
    DetailPrint "Map data downloaded successfully to: $CommonAppDataDir\RDO-Map-Overlay\data\"
    Goto map_done

  map_exists:
    DetailPrint "Map data already exists at: $CommonAppDataDir\RDO-Map-Overlay\data\"

  map_done:
SectionEnd

; Custom uninstall page to keep shared data
Function un.KeepDataPage
  !insertmacro MUI_HEADER_TEXT "Uninstall Options" "Choose what to remove"

  nsDialogs::Create 1018
  Pop $0

  ${NSD_CreateLabel} 0 0 100% 36u "Shared components are stored in ProgramData and can be reused by future installations.$\r$\n$\r$\nThis includes Python runtime, Qt/PySide6 packages, and map data (total ~250 MB).$\r$\nWould you like to keep these for future installations?"
  Pop $0

  ${NSD_CreateCheckbox} 10 50 100% 12u "Keep shared runtimes and map data (saves ~250 MB on reinstall)"
  Pop $KeepSharedData
  ${NSD_Check} $KeepSharedData  ; Check by default

  nsDialogs::Show
FunctionEnd

; Uninstaller
Section "Uninstall"
  ; Kill any running processes
  nsExec::Exec 'taskkill /F /IM python.exe'
  nsExec::Exec 'taskkill /F /IM pythonw.exe'

  ; Remove local application files
  Delete "$INSTDIR\launcher.bat"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\install.log"

  ; Use Windows native rmdir for fast deletion
  DetailPrint "Removing application files..."
  nsExec::Exec 'cmd /c rmdir /s /q "$INSTDIR\app"'
  nsExec::Exec 'cmd /c rmdir /s /q "$INSTDIR\data"'

  ; Remove install directory if empty
  RMDir "$INSTDIR"

  ; Handle shared components in ProgramData based on user choice
  ${NSD_GetState} $KeepSharedData $0
  ${If} $0 == ${BST_CHECKED}
    ; Keep shared runtimes and map data
    DetailPrint "Keeping shared components at: $CommonAppDataDir\RDO-Map-Overlay\"
    DetailPrint "  - Python runtime and Qt/PySide6 packages: ~83 MB"
    DetailPrint "  - Map data: ~167 MB"
  ${Else}
    ; Remove all shared components from ProgramData (fast deletion)
    DetailPrint "Removing shared components from: $CommonAppDataDir\RDO-Map-Overlay\"
    nsExec::Exec 'cmd /c rmdir /s /q "$CommonAppDataDir\RDO-Map-Overlay"'
  ${EndIf}

  ; Remove shortcuts
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${START_MENU_DIR}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${START_MENU_DIR}\Uninstall.lnk"
  RMDir "$SMPROGRAMS\${START_MENU_DIR}"

  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "Software\${PRODUCT_NAME_SAFE}"
SectionEnd

; Show install files page with details expanded
Function ShowInstFilesExpanded
  FindWindow $0 "#32770" "" $HWNDPARENT
  GetDlgItem $1 $0 1016
  ShowWindow $1 ${SW_HIDE}
  GetDlgItem $1 $0 1027
  ShowWindow $1 ${SW_SHOW}
FunctionEnd

; Installation initialization
Function .onInit
  ; Read ProgramData environment variable
  ReadEnvStr $CommonAppDataDir "PROGRAMDATA"
  ${If} $CommonAppDataDir == ""
    ReadEnvStr $CommonAppDataDir "ALLUSERSPROFILE"
  ${EndIf}
  ${If} $CommonAppDataDir == ""
    MessageBox MB_OK|MB_ICONEXCLAMATION "Cannot locate ProgramData directory!"
    Abort
  ${EndIf}

  ; Check for Windows 10 or later
  ${If} ${AtLeastWin10}
    ; OK
  ${Else}
    MessageBox MB_OK|MB_ICONEXCLAMATION "This application requires Windows 10 or later."
    Abort
  ${EndIf}

  ; Check for 64-bit Windows
  System::Call "kernel32::GetCurrentProcess() i .s"
  System::Call "kernel32::IsWow64Process(i s, *i .r0)"
  ${If} $0 == 0
    MessageBox MB_OK|MB_ICONEXCLAMATION "This application requires 64-bit Windows."
    Abort
  ${EndIf}
FunctionEnd