const { app, BrowserWindow, globalShortcut, ipcMain, dialog, screen } = require('electron');
const path = require('path');
const axios = require('axios');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const PythonEnvironmentManager = require('./python-environment-manager');
const NodeEnvironmentManager = require('./node-environment-manager');

// Ensure single instance
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('Another instance is already running. Exiting...');
  app.quit();
}

let mainWindow;
let setupWindow;
let disclaimerWindow;
let backendProcess = null;
let backendPort = null;
let isOverlayVisible = true;
let currentOpacity = 0.7;
const isDev = process.argv.includes('--dev');
let pythonEnvManager = null;

// Disable GPU and hardware acceleration to prevent GPU process crashes
app.disableHardwareAcceleration();

// Additional command line switches to stabilize GPU
app.commandLine.appendSwitch('--disable-gpu');
app.commandLine.appendSwitch('--disable-gpu-compositing');
app.commandLine.appendSwitch('--disable-gpu-sandbox');
app.commandLine.appendSwitch('--disable-software-rasterizer');
app.commandLine.appendSwitch('--no-sandbox');

// Backend management
function getPortFilePath() {
  return path.join(os.tmpdir(), 'rdo_overlay_port.json');
}

async function startBackend() {
  if (isDev) {
    console.log('Development mode: Expecting backend to run separately');
    // In dev mode, assume backend is at localhost:5000
    backendPort = 5000;
    return true;
  }

  // Production: backend is launched by launcher.bat before Electron starts
  // Just wait for the port file and connect
  console.log('Production mode: Waiting for backend to be ready...');

  const portFile = getPortFilePath();

  // Wait for backend to write port file
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000));

    if (fs.existsSync(portFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(portFile, 'utf8'));
        backendPort = data.port;

        // Verify backend is responding
        try {
          await axios.get(`http://127.0.0.1:${backendPort}/status`, { timeout: 2000 });
          console.log(`Backend ready on port ${backendPort}`);
          return true;
        } catch (e) {
          // Port file exists but backend not responding yet, continue waiting
        }
      } catch (e) {
        console.error('Failed to read port file:', e);
      }
    }
  }

  throw new Error('Backend failed to start within 30 seconds');
}

function stopBackend() {
  // In production mode, backend is managed by launcher.bat and will stop when Electron exits
  // In development mode, backend runs separately
  // No action needed here
  console.log('Frontend shutting down (backend managed externally)');
}

// Check if RDO is the active window
// Active window monitoring removed - user controls overlay visibility with F8 hotkey


function createSetupWindow() {
  setupWindow = new BrowserWindow({
    width: 600,
    height: 500,
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

  setupWindow.loadFile('setup-progress.html');
  setupWindow.setMenuBarVisibility(false);

  setupWindow.once('ready-to-show', () => {
    setupWindow.show();
  });

  return setupWindow;
}

function closeSetupWindow() {
  if (setupWindow) {
    setupWindow.close();
    setupWindow = null;
  }
}

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
    // Check if running from installer (environment already set up)
    const skipEnvSetup = process.env.RDO_SKIP_ENV_SETUP === '1' || process.env.RDO_INSTALLER_MODE === '1';

    // Initialize environment managers
    const appPath = isDev ? __dirname : app.getAppPath();
    const nodeEnvManager = new NodeEnvironmentManager(appPath);

    if (!isDev && !skipEnvSetup) {
      pythonEnvManager = new PythonEnvironmentManager(app.getPath('userData'));
    }

    // Check if first launch (disclaimer not accepted yet)
    const firstLaunchMarker = path.join(app.getPath('userData'), '.first-launch-complete');
    const isFirstLaunch = !fs.existsSync(firstLaunchMarker);

    // Production: Check if environment needs setup
    if (!isDev && !skipEnvSetup) {
      const needsNodeSetup = !nodeEnvManager.isDependenciesInstalled();
      const needsPythonSetup = pythonEnvManager ? !(await pythonEnvManager.isPythonReady()) : false;

      if (needsNodeSetup || needsPythonSetup) {
        const setupWin = createSetupWindow();

        // Step 1: Install Node.js dependencies
        if (needsNodeSetup) {
          await nodeEnvManager.installDependencies((progress) => {
            setupWin.webContents.send('setup-progress', {
              step: 1,
              ...progress
            });
          });
        }

        // Steps 2-4: Python setup
        if (needsPythonSetup) {
          // Setup progress updates - shift steps by 1
          pythonEnvManager.on('progress', (data) => {
            setupWin.webContents.send('setup-progress', {
              ...data,
              step: data.step + 1  // Shift from steps 1-3 to 2-4
            });
          });

          pythonEnvManager.on('component-complete', (component) => {
            setupWin.webContents.send('component-complete', component);
          });

          pythonEnvManager.on('error', (error) => {
            setupWin.webContents.send('setup-error', error);
          });

          // Run Python setup
          await pythonEnvManager.ensurePythonEnvironment();
        }

        closeSetupWindow();
      }
    }

    // Start backend and wait for it to be ready
    await startBackend();

    // Show disclaimer on first launch
    if (isFirstLaunch) {
      await showDisclaimerWindow();
      // Mark first launch as complete
      fs.writeFileSync(firstLaunchMarker, new Date().toISOString());
    }

    // Create main overlay window
    createWindow();
  } catch (error) {
    console.error('Failed to start application:', error);
    closeSetupWindow();
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