/**
 * Component Downloader - Downloads and manages application components
 * Used for both initial installation and runtime updates
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { app } = require('electron');
const crypto = require('crypto');

class ComponentDownloader {
  constructor() {
    this.componentsDir = path.join(app.getPath('userData'), 'components');
    this.manifestUrl = 'https://raw.githubusercontent.com/YOUR_USERNAME/rdo-overlay/main/components-manifest.json';
    this.ensureDirectories();
  }

  ensureDirectories() {
    if (!fs.existsSync(this.componentsDir)) {
      fs.mkdirSync(this.componentsDir, { recursive: true });
    }
  }

  /**
   * Download a file with progress tracking
   */
  async downloadFile(url, destPath, onProgress = null) {
    return new Promise((resolve, reject) => {
      const file = fs.createWriteStream(destPath);
      let downloaded = 0;

      https.get(url, (response) => {
        if (response.statusCode === 302 || response.statusCode === 301) {
          // Handle redirect
          file.close();
          return this.downloadFile(response.headers.location, destPath, onProgress)
            .then(resolve)
            .catch(reject);
        }

        if (response.statusCode !== 200) {
          file.close();
          fs.unlinkSync(destPath);
          reject(new Error(`Failed to download: ${response.statusCode}`));
          return;
        }

        const totalSize = parseInt(response.headers['content-length'], 10);

        response.on('data', (chunk) => {
          downloaded += chunk.length;
          file.write(chunk);

          if (onProgress) {
            onProgress({
              downloaded,
              total: totalSize,
              percent: (downloaded / totalSize) * 100
            });
          }
        });

        response.on('end', () => {
          file.close();
          resolve(destPath);
        });

        response.on('error', (err) => {
          file.close();
          fs.unlinkSync(destPath);
          reject(err);
        });
      }).on('error', reject);
    });
  }

  /**
   * Calculate SHA256 hash of a file
   */
  async getFileHash(filePath) {
    return new Promise((resolve, reject) => {
      const hash = crypto.createHash('sha256');
      const stream = fs.createReadStream(filePath);

      stream.on('data', (data) => hash.update(data));
      stream.on('end', () => resolve(hash.digest('hex')));
      stream.on('error', reject);
    });
  }

  /**
   * Download and verify a component
   */
  async downloadComponent(component, onProgress = null) {
    const destPath = path.join(this.componentsDir, component.filename);
    const tempPath = destPath + '.tmp';

    try {
      // Check if component already exists and is valid
      if (fs.existsSync(destPath)) {
        const hash = await this.getFileHash(destPath);
        if (hash === component.sha256) {
          console.log(`Component ${component.name} already up to date`);
          return destPath;
        }
      }

      console.log(`Downloading ${component.name} from ${component.url}`);

      // Download to temp file
      await this.downloadFile(component.url, tempPath, onProgress);

      // Verify hash
      const hash = await this.getFileHash(tempPath);
      if (hash !== component.sha256) {
        throw new Error(`Hash mismatch for ${component.name}`);
      }

      // Move to final location
      if (fs.existsSync(destPath)) {
        fs.unlinkSync(destPath);
      }
      fs.renameSync(tempPath, destPath);

      console.log(`Successfully downloaded ${component.name}`);
      return destPath;

    } catch (error) {
      // Clean up temp file
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
      }
      throw error;
    }
  }

  /**
   * Download components manifest from GitHub
   */
  async fetchManifest() {
    return new Promise((resolve, reject) => {
      https.get(this.manifestUrl, (response) => {
        let data = '';

        response.on('data', (chunk) => {
          data += chunk;
        });

        response.on('end', () => {
          try {
            const manifest = JSON.parse(data);
            resolve(manifest);
          } catch (error) {
            reject(new Error('Invalid manifest JSON'));
          }
        });

        response.on('error', reject);
      }).on('error', reject);
    });
  }

  /**
   * Ensure all required components are downloaded
   */
  async ensureComponents(onProgress = null) {
    try {
      const manifest = await this.fetchManifest();
      const components = manifest.components;

      for (const component of components) {
        if (component.required) {
          await this.downloadComponent(component, (progress) => {
            if (onProgress) {
              onProgress({
                component: component.name,
                ...progress
              });
            }
          });
        }
      }

      return {
        backend: path.join(this.componentsDir, 'rdo-overlay-backend.exe'),
        map: path.join(this.componentsDir, 'rdr2_map_hq.png')
      };

    } catch (error) {
      console.error('Failed to ensure components:', error);
      throw error;
    }
  }

  /**
   * Get path to a component
   */
  getComponentPath(filename) {
    return path.join(this.componentsDir, filename);
  }

  /**
   * Check if a component exists
   */
  componentExists(filename) {
    return fs.existsSync(this.getComponentPath(filename));
  }
}

module.exports = ComponentDownloader;