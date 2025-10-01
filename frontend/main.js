const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron');
const path = require('path');
const axios = require('axios');

let mainWindow;
let isOverlayVisible = true;
let currentOpacity = 0.7;

// Disable GPU and hardware acceleration to prevent GPU process crashes
app.disableHardwareAcceleration();

// Additional command line switches to stabilize GPU
app.commandLine.appendSwitch('--disable-gpu');
app.commandLine.appendSwitch('--disable-gpu-compositing');
app.commandLine.appendSwitch('--disable-gpu-sandbox');
app.commandLine.appendSwitch('--disable-software-rasterizer');
app.commandLine.appendSwitch('--no-sandbox');

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

app.whenReady().then(() => {
  createWindow();

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
  // Unregister all shortcuts
  globalShortcut.unregisterAll();
});

// IPC handlers
ipcMain.on('log', (event, message) => {
  console.log('[Renderer]:', message);
});

// Remove the enable-right-click IPC handler since we don't need it anymore

// Handle app activation properly
app.on('before-quit', () => {
  // Cleanup before quitting
  if (mainWindow) {
    mainWindow.removeAllListeners('close');
  }
});