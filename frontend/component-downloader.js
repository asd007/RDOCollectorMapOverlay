/**
 * Component Downloader - Downloads and manages application components
 * Used for both initial installation and runtime updates
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { app } = require('electron');
const crypto = require('crypto');
const GitHubSHA256Fetcher = require('./github-sha256-fetcher');

class ComponentDownloader {
  constructor() {
    this.componentsDir = path.join(app.getPath('userData'), 'components');
    this.manifestUrl = 'https://raw.githubusercontent.com/asd007/rdo-overlay/main/components-manifest.json';
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
      // Fetch actual SHA256 from GitHub if not provided or is a placeholder
      let expectedSHA256 = component.sha256;
      if (!expectedSHA256 || expectedSHA256 === 'CALCULATE_AFTER_BUILD' || expectedSHA256.length !== 64) {
        console.log(`Fetching SHA256 from GitHub for ${component.name}...`);

        if (onProgress) {
          onProgress({
            stage: 'fetching-hash',
            percent: 0,
            message: 'Verifying file integrity with GitHub...'
          });
        }

        const hashInfo = await GitHubSHA256Fetcher.fetchSHA256(component.url);
        expectedSHA256 = hashInfo.sha256;
        console.log(`GitHub SHA256 for ${component.name}: ${expectedSHA256}`);
      }

      // Check if component already exists and is valid
      if (fs.existsSync(destPath)) {
        const hash = await this.getFileHash(destPath);
        if (hash === expectedSHA256) {
          console.log(`Component ${component.name} already up to date`);
          return destPath;
        } else {
          console.log(`Component ${component.name} hash mismatch, will redownload`);
        }
      }

      console.log(`Downloading ${component.name} from ${component.url}`);

      // Download to temp file
      await this.downloadFile(component.url, tempPath, (progress) => {
        if (onProgress) {
          onProgress({
            ...progress,
            stage: 'downloading'
          });
        }
      });

      // Verify hash
      if (onProgress) {
        onProgress({
          stage: 'verifying',
          percent: 100,
          message: 'Verifying download integrity...'
        });
      }

      const hash = await this.getFileHash(tempPath);
      if (hash !== expectedSHA256) {
        throw new Error(
          `Hash mismatch for ${component.name}\n` +
          `Expected: ${expectedSHA256}\n` +
          `Got: ${hash}\n` +
          `File may be corrupted or tampered with.`
        );
      }

      console.log(`SHA256 verification passed for ${component.name}`);

      // Move to final location
      if (fs.existsSync(destPath)) {
        fs.unlinkSync(destPath);
      }
      fs.renameSync(tempPath, destPath);

      if (onProgress) {
        onProgress({
          stage: 'complete',
          percent: 100,
          message: 'Download complete'
        });
      }

      console.log(`Successfully downloaded and verified ${component.name}`);
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