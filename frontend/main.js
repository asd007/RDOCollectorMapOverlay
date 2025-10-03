const { app, BrowserWindow, globalShortcut, ipcMain, dialog } = require('electron');
const path = require('path');
const axios = require('axios');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;
let splashWindow;
let backendProcess = null;
let backendPort = null;
let isOverlayVisible = true;
let currentOpacity = 0.7;
const isDev = process.argv.includes('--dev');

// Disable GPU and hardware acceleration to prevent GPU process crashes
app.disableHardwareAcceleration();

// Additional command line switches to stabilize GPU
app.commandLine.appendSwitch('--disable-gpu');
app.commandLine.appendSwitch('--disable-gpu-compositing');
app.commandLine.appendSwitch('--disable-gpu-sandbox');
app.commandLine.appendSwitch('--disable-software-rasterizer');
app.commandLine.appendSwitch('--no-sandbox');

// Backend management
function getBackendPath() {
  if (isDev) {
    // Development: backend runs separately (python app.py)
    return null;
  }
  // Production: backend is bundled in resources
  return path.join(process.resourcesPath, 'backend', 'rdo-overlay-backend.exe');
}

function getPortFilePath() {
  return path.join(os.tmpdir(), 'rdo_overlay_port.json');
}

async function startBackend() {
  const backendPath = getBackendPath();

  if (!backendPath) {
    console.log('Development mode: Expecting backend to run separately');
    // In dev mode, assume backend is at localhost:5000
    backendPort = 5000;
    return true;
  }

  if (!fs.existsSync(backendPath)) {
    throw new Error(`Backend not found at: ${backendPath}`);
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

  throw new Error('Backend failed to start within 30 seconds');
}

function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend...');
    backendProcess.kill();
    backendProcess = null;
  }
}

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 200,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    show: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Simple HTML splash screen
  splashWindow.loadURL(`data:text/html;charset=utf-8,
    <html>
      <head>
        <style>
          body {
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: Arial, sans-serif;
            background: rgba(30, 30, 30, 0.95);
            color: white;
          }
          .container {
            text-align: center;
          }
          h1 {
            font-size: 24px;
            margin-bottom: 10px;
          }
          .spinner {
            width: 50px;
            height: 50px;
            margin: 20px auto;
            border: 4px solid #333;
            border-top: 4px solid #fff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
          }
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>RDO Map Overlay</h1>
          <div class="spinner"></div>
          <p>Starting...</p>
        </div>
      </body>
    </html>
  `);

  splashWindow.once('ready-to-show', () => {
    splashWindow.show();
  });
}

function closeSplash() {
  if (splashWindow) {
    splashWindow.close();
    splashWindow = null;
  }
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

  // REMOVED click-through - let users interact normally with the overlay
  // mainWindow.setIgnoreMouseEvents(true, { forward: true });

  mainWindow.loadFile('index.html');

  // Remove menu bar
  mainWindow.setMenuBarVisibility(false);

  // Show window when ready to prevent flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
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
    // Show splash screen
    createSplash();

    // Start backend and wait for it to be ready
    await startBackend();

    // Close splash and create main window
    closeSplash();
    createWindow();
  } catch (error) {
    console.error('Failed to start application:', error);
    closeSplash();
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

// Remove the enable-right-click IPC handler since we don't need it anymore

// Handle app activation properly
app.on('before-quit', () => {
  // Cleanup before quitting
  if (mainWindow) {
    mainWindow.removeAllListeners('close');
  }
});