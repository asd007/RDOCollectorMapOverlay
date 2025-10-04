; RDO Map Overlay - Configuration for Web Installer
; This file contains all the configuration constants

!define PRODUCT_NAME "RDO Map Overlay"
!define PRODUCT_NAME_SAFE "RDO-Map-Overlay"

; Version can be overridden via command line: /DPRODUCT_VERSION=X.Y.Z
!ifndef PRODUCT_VERSION
!define PRODUCT_VERSION "1.0.0"
!endif

!define PRODUCT_PUBLISHER "Alexandru Clontea"
!define PRODUCT_WEB_SITE "https://github.com/asd007/rdo-overlay"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_SAFE}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; Download URLs - Using specific versions for reproducibility
!define ELECTRON_VERSION "27.0.0"
!define ELECTRON_URL "https://github.com/electron/electron/releases/download/v${ELECTRON_VERSION}/electron-v${ELECTRON_VERSION}-win32-x64.zip"
!define ELECTRON_SIZE_MB "95"  ; Approximate size for progress display

!define NODE_VERSION "20.10.0"
!define NODE_URL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-win-x64.zip"
!define NODE_SIZE_MB "30"

!define PYTHON_VERSION "3.11.8"
!define PYTHON_URL "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip"
!define GET_PIP_URL "https://bootstrap.pypa.io/get-pip.py"
!define PYTHON_SIZE_MB "15"

; Map data (required, downloaded during installation)
!define MAP_HQ_URL "https://media.githubusercontent.com/media/asd007/RDOCollectorMapOverlay/refs/heads/main/data/rdr2_map_hq.png"
!define MAP_HQ_SIZE_MB "167"

; Installation paths
!define DEFAULT_INSTALL_DIR "$PROGRAMFILES64\${PRODUCT_NAME_SAFE}"
!define START_MENU_DIR "${PRODUCT_NAME}"

; Temp download directory
!define TEMP_DIR "$TEMP\RDO-Installer"