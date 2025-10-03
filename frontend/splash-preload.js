const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the splash to receive updates
contextBridge.exposeInMainWorld('electron', {
  onStatusUpdate: (callback) => {
    ipcRenderer.on('status-update', (event, status) => callback(status));
  },
  onComponentProgress: (callback) => {
    ipcRenderer.on('component-progress', (event, data) => callback(data));
  },
  onUpdateProgress: (callback) => {
    ipcRenderer.on('update-progress', (event, data) => callback(data));
  }
});