const { app, BrowserWindow, globalShortcut, ipcMain, dialog } = require('electron');
const path = require('path');
const axios = require('axios');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const { autoUpdater } = require('electron-updater');
const ComponentDownloader = require('./component-downloader');

let mainWindow;
let splashWindow;
let backendProcess = null;
let backendPort = null;
let isOverlayVisible = true;
let currentOpacity = 0.7;
const isDev = process.argv.includes('--dev');
const componentDownloader = new ComponentDownloader();

// Disable GPU and hardware acceleration to prevent GPU process crashes
app.disableHardwareAcceleration();

// Additional command line switches to stabilize GPU
app.commandLine.appendSwitch('--disable-gpu');
app.commandLine.appendSwitch('--disable-gpu-compositing');
app.commandLine.appendSwitch('--disable-gpu-sandbox');
app.commandLine.appendSwitch('--disable-software-rasterizer');
app.commandLine.appendSwitch('--no-sandbox');

// Configure auto-updater
if (!isDev) {
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('update-available', (info) => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'Update Available',
      message: `A new version (${info.version}) is available. Would you like to download it now?`,
      buttons: ['Yes', 'Later'],
      defaultId: 0
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.downloadUpdate();
        showUpdateProgress();
      }
    });
  });

  autoUpdater.on('update-downloaded', () => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: 'Update Ready',
      message: 'Update downloaded. The application will restart to apply the update.',
      buttons: ['Restart Now', 'Later']
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    });
  });

  autoUpdater.on('error', (error) => {
    console.error('Auto-updater error:', error);
  });
}

function showUpdateProgress() {
  if (!splashWindow) return;

  autoUpdater.on('download-progress', (progress) => {
    splashWindow.webContents.send('update-progress', {
      percent: progress.percent,
      bytesPerSecond: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total
    });
  });
}

// Backend management
function getBackendPath() {
  if (isDev) {
    // Development: backend runs separately (python app.py)
    return null;
  }

  // Production: check if backend is downloaded
  const backendPath = componentDownloader.getComponentPath('rdo-overlay-backend.exe');
  if (fs.existsSync(backendPath)) {
    return backendPath;
  }

  // Legacy: check if backend is in resources (old installation)
  const legacyPath = path.join(process.resourcesPath, 'backend', 'rdo-overlay-backend.exe');
  if (fs.existsSync(legacyPath)) {
    return legacyPath;
  }

  return null;
}

function getPortFilePath() {
  return path.join(os.tmpdir(), 'rdo_overlay_port.json');
}

async function downloadComponents() {
  return new Promise((resolve, reject) => {
    // Show download progress in splash window
    if (splashWindow) {
      splashWindow.webContents.send('status-update', 'Downloading components...');
    }

    componentDownloader.ensureComponents((progress) => {
      if (splashWindow) {
        splashWindow.webContents.send('component-progress', progress);
      }
    }).then(resolve).catch(reject);
  });
}

async function startBackend() {
  let backendPath = getBackendPath();

  if (!backendPath && !isDev) {
    // Backend not found, download it
    console.log('Backend not found, downloading...');
    try {
      const components = await downloadComponents();
      backendPath = components.backend;
    } catch (error) {
      console.error('Failed to download backend:', error);
      throw new Error('Failed to download required components. Please check your internet connection.');
    }
  }

  if (!backendPath) {
    console.log('Development mode: Expecting backend to run separately');
    // In dev mode, assume backend is at localhost:5000
    backendPort = 5000;
    return true;
  }

  console.log(`Starting backend: ${backendPath}`);

  // Clean up old port file
  const portFile = getPortFilePath();
  if (fs.existsSync(portFile)) {
    fs.unlinkSync(portFile);
  }

  // Spawn backend process (hidden, no console window)
  backendProcess = spawn(backendPath, [], {
    windowsHide: true,
    detached: false,
    stdio: 'ignore' // Ignore stdin/stdout/stderr
  });

  backendProcess.on('error', (err) => {
    console.error('Backend process error:', err);
  });

  backendProcess.on('exit', (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });

  // Wait for backend to write port file
  console.log('Waiting for backend to start...');
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000));

    if (fs.existsSync(portFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(portFile, 'utf8'));
        backendPort = data.port;
        console.log(`Backend ready on port ${backendPort}`);

        // Verify backend is responding
        try {
          await axios.get(`http://127.0.0.1:${backendPort}/status`, { timeout: 2000 });
          return true;
        } catch (e) {
          // Port file exists but backend not responding yet, continue waiting
        }
      } catch (e) {
        console.error('Failed to read port file:', e);
      }
    }
  }

  throw new Error('Backend failed to start after 30 seconds');
}

function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend...');
    backendProcess.kill();
    backendProcess = null;
  }
}

// Create splash screen for loading
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 250,
    frame: false,
    alwaysOnTop: true,
    transparent: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'splash-preload.js')
    }
  });

  splashWindow.loadFile('splash.html');
  splashWindow.center();
}

// Main window creation
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1920,
    height: 1080,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    fullscreen: false,
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile('index.html');
  mainWindow.setIgnoreMouseEvents(true);

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopBackend();
    app.quit();
  });

  // IPC handlers for renderer
  ipcMain.handle('get-backend-port', () => backendPort);
  ipcMain.handle('toggle-mouse-events', (_, ignore) => {
    mainWindow.setIgnoreMouseEvents(ignore);
  });
  ipcMain.handle('set-opacity', (_, opacity) => {
    currentOpacity = opacity;
    mainWindow.setOpacity(opacity);
  });

  // Register global hotkeys
  registerHotkeys();

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      setTimeout(() => {
        splashWindow.close();
        splashWindow = null;
        mainWindow.show();
      }, 500);
    } else {
      mainWindow.show();
    }
  });

  // Check for updates after window is ready
  if (!isDev) {
    setTimeout(() => {
      autoUpdater.checkForUpdatesAndNotify();
    }, 5000);
  }
}

function registerHotkeys() {
  // F9: Start/restart alignment
  globalShortcut.register('F9', () => {
    console.log('F9 pressed - triggering alignment');
    mainWindow.webContents.send('trigger-alignment');
  });

  // F8: Toggle overlay visibility
  globalShortcut.register('F8', () => {
    console.log('F8 pressed - toggling overlay');
    isOverlayVisible = !isOverlayVisible;
    mainWindow.webContents.send('toggle-visibility', isOverlayVisible);
  });

  // F7: Cycle opacity
  globalShortcut.register('F7', () => {
    console.log('F7 pressed - cycling opacity');
    const opacities = [0.3, 0.5, 0.7, 0.9];
    const currentIndex = opacities.indexOf(currentOpacity);
    const nextIndex = (currentIndex + 1) % opacities.length;
    currentOpacity = opacities[nextIndex];
    mainWindow.setOpacity(currentOpacity);
    mainWindow.webContents.send('opacity-changed', currentOpacity);
  });

  // F6: Refresh collectibles
  globalShortcut.register('F6', () => {
    console.log('F6 pressed - refreshing collectibles');
    mainWindow.webContents.send('refresh-collectibles');
  });

  // Ctrl+Q: Quit application
  globalShortcut.register('CommandOrControl+Q', () => {
    console.log('Ctrl+Q pressed - quitting');
    app.quit();
  });
}

// App lifecycle
app.whenReady().then(async () => {
  try {
    createSplashWindow();

    if (splashWindow) {
      splashWindow.webContents.on('did-finish-load', async () => {
        splashWindow.webContents.send('status-update', 'Starting backend...');

        try {
          await startBackend();
          splashWindow.webContents.send('status-update', 'Backend ready!');
          createMainWindow();
        } catch (error) {
          dialog.showErrorBox('Backend Error', error.message);
          app.quit();
        }
      });
    }
  } catch (error) {
    console.error('Startup error:', error);
    dialog.showErrorBox('Startup Error', error.message);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  stopBackend();
});

app.on('activate', () => {
  if (!mainWindow) {
    createMainWindow();
  }
});