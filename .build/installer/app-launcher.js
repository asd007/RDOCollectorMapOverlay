// RDO Map Overlay - Application Launcher
// This script handles first-launch setup and dependency verification

const { app, BrowserWindow, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const axios = require('axios');

// Configuration
const BACKEND_PORT = 5000;
const BACKEND_CHECK_INTERVAL = 500;
const BACKEND_MAX_RETRIES = 20;
const MAP_DATA_URL = 'https://github.com/asd007/rdo-overlay/releases/download/v1.0.0/rdr2_map_hq.png';
const MAP_DATA_PATH = path.join(app.getPath('userData'), 'data', 'rdr2_map_hq.png');
const MAP_DATA_SIZE = 175000000; // ~167 MB

class AppLauncher {
  constructor() {
    this.backendProcess = null;
    this.mainWindow = null;
    this.setupWindow = null;
  }

  async start() {
    try {
      // Check if this is first launch
      const isFirstLaunch = await this.checkFirstLaunch();

      if (isFirstLaunch) {
        await this.showSetupWindow();
        await this.performFirstTimeSetup();
        this.closeSetupWindow();
      }

      // Start backend
      await this.startBackend();

      // Wait for backend to be ready
      await this.waitForBackend();

      // Launch main application
      await this.launchMainApp();

    } catch (error) {
      dialog.showErrorBox('Launch Error', `Failed to start application: ${error.message}`);
      app.quit();
    }
  }

  async checkFirstLaunch() {
    // Check if map data exists
    if (!fs.existsSync(MAP_DATA_PATH)) {
      return true;
    }

    // Check if map data is valid size
    const stats = fs.statSync(MAP_DATA_PATH);
    if (stats.size < MAP_DATA_SIZE * 0.9) {
      return true;
    }

    return false;
  }

  async showSetupWindow() {
    this.setupWindow = new BrowserWindow({
      width: 500,
      height: 400,
      resizable: false,
      frame: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    });

    const setupHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body {
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            flex-direction: column;
            height: 360px;
          }
          h1 { margin-top: 0; }
          .progress {
            width: 100%;
            height: 30px;
            background: rgba(255,255,255,0.2);
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
          }
          .progress-bar {
            height: 100%;
            background: rgba(255,255,255,0.8);
            width: 0%;
            transition: width 0.3s;
          }
          .status { margin: 10px 0; }
          .info {
            margin-top: auto;
            padding-top: 20px;
            font-size: 12px;
            opacity: 0.8;
          }
        </style>
      </head>
      <body>
        <h1>RDO Map Overlay - First Time Setup</h1>
        <div class="status" id="status">Preparing...</div>
        <div class="progress">
          <div class="progress-bar" id="progress"></div>
        </div>
        <div id="details"></div>
        <div class="info">
          This is a one-time setup. The application will start automatically when complete.
        </div>
      </body>
      </html>
    `;

    this.setupWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(setupHtml)}`);
  }

  closeSetupWindow() {
    if (this.setupWindow) {
      this.setupWindow.close();
      this.setupWindow = null;
    }
  }

  updateSetupProgress(status, progress, details = '') {
    if (this.setupWindow) {
      this.setupWindow.webContents.executeJavaScript(`
        document.getElementById('status').textContent = '${status}';
        document.getElementById('progress').style.width = '${progress}%';
        document.getElementById('details').textContent = '${details}';
      `);
    }
  }

  async performFirstTimeSetup() {
    // Create data directories
    const dataDir = path.dirname(MAP_DATA_PATH);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    // Download map data
    await this.downloadMapData();

    // Create cache directories
    const cacheDir = path.join(dataDir, 'cache');
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }

    // Save setup complete flag
    fs.writeFileSync(path.join(app.getPath('userData'), 'setup.json'), JSON.stringify({
      setupComplete: true,
      setupDate: new Date().toISOString(),
      version: '1.0.0'
    }));
  }

  async downloadMapData() {
    return new Promise((resolve, reject) => {
      this.updateSetupProgress('Downloading map data...', 0, 'This may take a few minutes');

      const writer = fs.createWriteStream(MAP_DATA_PATH);
      let downloadedBytes = 0;

      axios({
        method: 'get',
        url: MAP_DATA_URL,
        responseType: 'stream',
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.lengthComputable) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            const mbDownloaded = (progressEvent.loaded / 1048576).toFixed(1);
            const mbTotal = (progressEvent.total / 1048576).toFixed(1);
            this.updateSetupProgress(
              'Downloading map data...',
              percentCompleted,
              `${mbDownloaded} MB / ${mbTotal} MB`
            );
          }
        }
      })
      .then(response => {
        response.data.pipe(writer);

        writer.on('finish', () => {
          this.updateSetupProgress('Map data downloaded', 100, 'Setup complete!');
          setTimeout(resolve, 1000);
        });

        writer.on('error', reject);
      })
      .catch(reject);
    });
  }

  async startBackend() {
    const pythonPath = process.platform === 'win32'
      ? path.join(process.resourcesPath, '..', 'runtime', 'python', 'python.exe')
      : 'python3';

    const backendPath = path.join(process.resourcesPath, '..', 'app', 'backend', 'app.py');

    // Set environment variables for the backend
    const env = { ...process.env };
    env.PYTHONPATH = path.join(process.resourcesPath, '..', 'app', 'backend');
    env.RDO_DATA_PATH = path.join(app.getPath('userData'), 'data');

    this.backendProcess = spawn(pythonPath, [backendPath], { env });

    this.backendProcess.stdout.on('data', (data) => {
      console.log(`Backend: ${data}`);
    });

    this.backendProcess.stderr.on('data', (data) => {
      console.error(`Backend Error: ${data}`);
    });

    this.backendProcess.on('close', (code) => {
      console.log(`Backend process exited with code ${code}`);
      if (code !== 0 && code !== null) {
        dialog.showErrorBox('Backend Error', 'The backend process crashed. Please restart the application.');
        app.quit();
      }
    });
  }

  async waitForBackend() {
    for (let i = 0; i < BACKEND_MAX_RETRIES; i++) {
      try {
        const response = await axios.get(`http://localhost:${BACKEND_PORT}/status`);
        if (response.status === 200) {
          console.log('Backend is ready');
          return;
        }
      } catch (error) {
        // Backend not ready yet
      }

      await new Promise(resolve => setTimeout(resolve, BACKEND_CHECK_INTERVAL));
    }

    throw new Error('Backend failed to start within timeout period');
  }

  async launchMainApp() {
    // Load the actual application
    const mainPath = path.join(__dirname, 'main.js');
    require(mainPath);
  }

  cleanup() {
    if (this.backendProcess) {
      this.backendProcess.kill();
    }
  }
}

// Application entry point
const launcher = new AppLauncher();

app.whenReady().then(() => {
  launcher.start();
});

app.on('window-all-closed', () => {
  launcher.cleanup();
  app.quit();
});

app.on('before-quit', () => {
  launcher.cleanup();
});

module.exports = launcher;