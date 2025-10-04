const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');
const { exec } = require('child_process');
const AdmZip = require('adm-zip');

let mainWindow;

// URLs to download from (set via environment or config)
const DOWNLOAD_URLS = {
  runtime: process.env.RUNTIME_URL || 'https://github.com/YOUR_USER/rdo_overlay/releases/download/runtime-v1.0.0/runtime.zip',
  backend: process.env.BACKEND_URL || 'https://github.com/YOUR_USER/rdo_overlay/releases/download/v1.0.0/backend.zip',
  code: process.env.CODE_URL || 'https://github.com/YOUR_USER/rdo_overlay/releases/download/v1.0.0/code.zip'
};

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 650,
    height: 700,
    resizable: false,
    frame: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, '..', 'bootstrap-installer.html'));
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

// IPC Handlers

ipcMain.handle('download-file', async (event, { url, dest, onProgress }) => {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);

    https.get(url, (response) => {
      const totalSize = parseInt(response.headers['content-length'], 10);
      let downloadedSize = 0;

      response.on('data', (chunk) => {
        downloadedSize += chunk.length;
        const progress = downloadedSize / totalSize;
        event.sender.send('download-progress', progress);
      });

      response.pipe(file);

      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
});

ipcMain.handle('create-install-dir', async (event, installPath) => {
  if (!fs.existsSync(installPath)) {
    fs.mkdirSync(installPath, { recursive: true });
  }
  return true;
});

ipcMain.handle('extract-zip', async (event, { file, dest }) => {
  const zip = new AdmZip(file);
  zip.extractAllTo(dest, true);
  return true;
});

ipcMain.handle('create-shortcuts', async (event, installPath) => {
  // Create desktop shortcut (Windows-specific)
  const vbsScript = `
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "${process.env.USERPROFILE}\\Desktop\\RDO Map Overlay.lnk"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "${installPath}\\RDO Map Overlay.exe"
    oLink.WorkingDirectory = "${installPath}"
    oLink.Save
  `;

  const vbsFile = path.join(process.env.TEMP, 'create-shortcut.vbs');
  fs.writeFileSync(vbsFile, vbsScript);

  return new Promise((resolve) => {
    exec(`cscript //nologo "${vbsFile}"`, () => {
      fs.unlinkSync(vbsFile);
      resolve();
    });
  });
});

ipcMain.handle('cleanup-temp-files', async () => {
  const tempFiles = ['runtime.zip', 'backend.zip', 'code.zip'];
  tempFiles.forEach(file => {
    if (fs.existsSync(file)) {
      fs.unlinkSync(file);
    }
  });
  return true;
});

ipcMain.handle('launch-app', async (event, installPath) => {
  const exePath = path.join(installPath, 'RDO Map Overlay.exe');
  exec(`"${exePath}"`);
  return true;
});
