const { app, BrowserWindow, globalShortcut, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const axios = require('axios');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

// Ensure single instance
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('Another instance is already running. Exiting...');
  app.quit();
}

let mainWindow;
let disclaimerWindow;
let backendProcess = null;
let backendPort = 5000; // Backend always runs on port 5000
let isOverlayVisible = true;
let currentOpacity = 0.7;
const isDev = process.argv.includes('--dev');

// Installer paths (production mode)
const PROGRAMDATA = process.env.PROGRAMDATA || 'C:\\ProgramData';
const RUNTIME_DIR = path.join(PROGRAMDATA, 'RDO-Map-Overlay', 'runtime');
const PYTHON_PATH = path.join(RUNTIME_DIR, 'python', 'python.exe');

// Disable GPU and hardware acceleration to prevent GPU process crashes
app.disableHardwareAcceleration();

// Additional command line switches to stabilize GPU
app.commandLine.appendSwitch('--disable-gpu');
app.commandLine.appendSwitch('--disable-gpu-compositing');
app.commandLine.appendSwitch('--disable-gpu-sandbox');
app.commandLine.appendSwitch('--disable-software-rasterizer');
app.commandLine.appendSwitch('--no-sandbox');

// Backend management
async function startBackend() {
  if (isDev) {
    console.log('[Backend] Development mode: Expecting backend to run separately');
    backendPort = 5000;
    return true;
  }

  // Check if backend is already running on default port
  console.log('[Backend] Checking for existing backend on port 5000...');
  try {
    await axios.get(`http://127.0.0.1:5000/status`, { timeout: 1000 });
    console.log('[Backend] Found existing backend on port 5000, using it');
    backendPort = 5000;
    return true;
  } catch (e) {
    // Backend not running, start it
    console.log('[Backend] No existing backend found, starting new instance...');
  }

  // Production: Start Python backend as child process
  console.log('[Backend] Starting Python backend...');

  // Check if Python exists
  if (!fs.existsSync(PYTHON_PATH)) {
    throw new Error(`Python not found at ${PYTHON_PATH}\n\nPlease install RDO Map Overlay using the official installer.`);
  }

  const backendScriptPath = path.join(app.getAppPath(), 'backend', 'app.py');

  // Check if backend script exists
  if (!fs.existsSync(backendScriptPath)) {
    throw new Error(`Backend script not found at ${backendScriptPath}\n\nInstallation may be corrupted.`);
  }

  // Spawn Python backend
  backendProcess = spawn(PYTHON_PATH, [backendScriptPath], {
    env: { ...process.env },
    cwd: path.join(app.getAppPath(), 'backend')
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error] ${data.toString().trim()}`);
  });

  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
    if (code !== 0 && code !== null) {
      dialog.showErrorBox('Backend Crashed', 'The backend process crashed. Please restart the application.');
      app.quit();
    }
  });

  // Backend started in background - UI will show connection status
  console.log('[Backend] Backend started. UI will connect when ready.');
  console.log('[Backend] Initialization may take 10-60 seconds (up to 2 minutes on low-end systems).');
  return true;
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Backend] Stopping backend process');
    backendProcess.kill();
    backendProcess = null;
  }
}

// Check if RDO is the active window
// Active window monitoring removed - user controls overlay visibility with F8 hotkey

async function showDisclaimerWindow() {
  return new Promise((resolve) => {
    disclaimerWindow = new BrowserWindow({
      width: 600,
      height: 400,
      transparent: false,
      frame: true,
      alwaysOnTop: true,
      resizable: false,
      show: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    });

    disclaimerWindow.loadFile('first-launch-disclaimer.html');
    disclaimerWindow.setMenuBarVisibility(false);

    disclaimerWindow.once('ready-to-show', () => {
      disclaimerWindow.show();
    });

    // Listen for acceptance
    ipcMain.once('disclaimer-accepted', () => {
      if (disclaimerWindow) {
        disclaimerWindow.close();
        disclaimerWindow = null;
      }
      resolve();
    });

    disclaimerWindow.on('closed', () => {
      disclaimerWindow = null;
      // If closed without accepting, quit
      if (!mainWindow) {
        app.quit();
      }
    });
  });
}

function showError(title, message) {
  dialog.showErrorBox(title, message);
  app.quit();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    x: 0,  // Position at screen origin
    y: 0,
    width: 1920,
    height: 1080,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    title: 'RDO Map Overlay', // Set explicit title for backend detection
    // Additional stability options
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true,
      backgroundThrottling: false,
      // Disable problematic features
      webgl: false,
      plugins: false,
      experimentalFeatures: false,
      enableWebSQL: false,
      // Optimize for overlay
      offscreen: false
    }
  });

  // Set screen-saver priority so overlay always stays on top
  mainWindow.setAlwaysOnTop(true, 'screen-saver');

  // Enable click-through - all mouse interactions handled by backend global listener
  mainWindow.setIgnoreMouseEvents(true, { forward: true });

  mainWindow.loadFile('index.html');

  // Remove menu bar
  mainWindow.setMenuBarVisibility(false);

  // Force window title after page load (Electron sometimes uses HTML title)
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.setTitle('RDO Map Overlay');
  });

  // Show window when ready to prevent flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // Set title again to be sure
    mainWindow.setTitle('RDO Map Overlay');
  });

  // Error handling
  mainWindow.webContents.on('crashed', (event, killed) => {
    console.error('Window crashed!', { killed });
  });

  mainWindow.on('unresponsive', () => {
    console.error('Window became unresponsive!');
  });

  // Open DevTools in development
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  try {
    // Check if first launch (disclaimer not accepted yet)
    const firstLaunchMarker = path.join(app.getPath('userData'), '.first-launch-complete');
    const isFirstLaunch = !fs.existsSync(firstLaunchMarker);

    // Show disclaimer on first launch
    if (isFirstLaunch) {
      await showDisclaimerWindow();
      // Mark first launch as complete
      fs.writeFileSync(firstLaunchMarker, new Date().toISOString());
    }

    // Create main overlay window (show immediately for visual feedback)
    createWindow();

    // Start backend in background (fire-and-forget)
    // UI will show "Connecting..." until backend is ready
    startBackend().catch(error => {
      console.error('[Backend] Failed to start:', error);
      // UI will show disconnected state - user can retry or check logs
    });
  } catch (error) {
    console.error('Failed to start application:', error);
    showError('Startup Failed', `RDO Map Overlay could not start:\n\n${error.message}\n\nPlease try restarting the application.`);
    return;
  }

  // Register global hotkeys
  
  // F9 - Start/Restart alignment
  globalShortcut.register('F9', () => {
    if (mainWindow) {
      mainWindow.webContents.send('start-alignment');
    }
  });

  // F8 - Toggle overlay visibility
  globalShortcut.register('F8', () => {
    isOverlayVisible = !isOverlayVisible;
    if (mainWindow) {
      if (isOverlayVisible) {
        mainWindow.webContents.send('show-overlay');
      } else {
        mainWindow.webContents.send('hide-overlay');
      }
    }
  });

  // F7 - Cycle opacity
  globalShortcut.register('F7', () => {
    const opacities = [0.3, 0.5, 0.7, 0.9];
    const currentIndex = opacities.indexOf(currentOpacity);
    const nextIndex = (currentIndex + 1) % opacities.length;
    currentOpacity = opacities[nextIndex];
    
    if (mainWindow) {
      mainWindow.webContents.send('set-opacity', currentOpacity);
    }
  });

  // F6 - Refresh Joan Ropke data
  globalShortcut.register('F6', () => {
    if (mainWindow) {
      mainWindow.webContents.send('refresh-data');
    }
  });

  // Ctrl+Q - Close overlay
  globalShortcut.register('CommandOrControl+Q', () => {
    app.quit();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  // Stop backend
  stopBackend();

  // Unregister all shortcuts
  globalShortcut.unregisterAll();
});

// IPC handlers
ipcMain.on('log', (event, message) => {
  console.log('[Renderer]:', message);
});

ipcMain.handle('get-backend-port', () => {
  return backendPort || 5000;
});

// Cursor position and click-through control
ipcMain.handle('get-cursor-position', () => {
  const point = screen.getCursorScreenPoint();
  return { x: point.x, y: point.y };
});

// Click-through control - toggled when video player or menus are open
ipcMain.handle('set-click-through', (event, enabled) => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(enabled, { forward: true });
  }
});

// Control overlay visibility based on RDR2 focus state
ipcMain.on('set-overlay-visibility', (event, visible) => {
  if (mainWindow) {
    if (visible) {
      // RDR2 active - show overlay
      mainWindow.showInactive(); // Show without stealing focus
      mainWindow.setAlwaysOnTop(true, 'screen-saver');
    } else {
      // RDR2 inactive - hide overlay completely
      mainWindow.hide();
    }
  }
});

// Interaction tracking removed - overlay visibility controlled by F8 hotkey only

// Handle app activation properly
app.on('before-quit', () => {
  // Cleanup before quitting
  if (mainWindow) {
    mainWindow.removeAllListeners('close');
  }
});