/**
 * Python Environment Manager
 * Downloads Python embeddable runtime and installs packages from PyPI
 * Replaces the 58MB PyInstaller bundle with ~30MB runtime + packages downloaded at install time
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { app } = require('electron');
const ComponentDownloader = require('./component-downloader');

class PythonEnvironmentManager {
  constructor() {
    this.componentsDir = path.join(app.getPath('userData'), 'components');
    this.pythonDir = path.join(this.componentsDir, 'python');
    this.downloader = new ComponentDownloader();

    // Python embeddable version (no installer needed)
    this.pythonVersion = '3.11.8';
    this.pythonUrl = `https://www.python.org/ftp/python/${this.pythonVersion}/python-${this.pythonVersion}-embed-amd64.zip`;
    this.pythonExe = path.join(this.pythonDir, 'python.exe');

    this.ensureDirectories();
  }

  ensureDirectories() {
    if (!fs.existsSync(this.pythonDir)) {
      fs.mkdirSync(this.pythonDir, { recursive: true });
    }
  }

  /**
   * Check if Python runtime is installed
   */
  isPythonInstalled() {
    return fs.existsSync(this.pythonExe);
  }

  /**
   * Download and extract Python embeddable runtime
   */
  async downloadPython(onProgress = null) {
    const zipPath = path.join(this.componentsDir, 'python.zip');

    try {
      if (this.isPythonInstalled()) {
        console.log('Python already installed');
        return this.pythonExe;
      }

      console.log(`Downloading Python ${this.pythonVersion}...`);

      // Download Python zip
      await this.downloader.downloadFile(this.pythonUrl, zipPath, (progress) => {
        if (onProgress) {
          onProgress({
            component: `Python ${this.pythonVersion}`,
            stage: 'downloading',
            ...progress
          });
        }
      });

      // Extract using PowerShell (built into Windows)
      console.log('Extracting Python...');
      if (onProgress) {
        onProgress({
          component: `Python ${this.pythonVersion}`,
          stage: 'extracting',
          percent: 50
        });
      }

      await this.extractZip(zipPath, this.pythonDir);

      // Enable pip by modifying python*._pth file
      await this.enablePip();

      // Clean up
      fs.unlinkSync(zipPath);

      console.log('Python runtime installed successfully');
      return this.pythonExe;

    } catch (error) {
      // Clean up on error
      if (fs.existsSync(zipPath)) {
        fs.unlinkSync(zipPath);
      }
      if (fs.existsSync(this.pythonDir)) {
        fs.rmSync(this.pythonDir, { recursive: true });
      }
      throw error;
    }
  }

  /**
   * Extract zip file using PowerShell
   */
  async extractZip(zipPath, destPath) {
    return new Promise((resolve, reject) => {
      const cmd = `powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${destPath}' -Force"`;

      exec(cmd, (error, stdout, stderr) => {
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }

  /**
   * Enable pip in embeddable Python by modifying python*._pth file
   */
  async enablePip() {
    const pthFiles = fs.readdirSync(this.pythonDir).filter(f => f.endsWith('._pth'));

    if (pthFiles.length === 0) {
      throw new Error('Python ._pth file not found');
    }

    const pthFile = path.join(this.pythonDir, pthFiles[0]);
    let content = fs.readFileSync(pthFile, 'utf8');

    // Uncomment "import site" line to enable pip
    content = content.replace('#import site', 'import site');

    fs.writeFileSync(pthFile, content, 'utf8');
  }

  /**
   * Download and install get-pip.py
   */
  async installPip(onProgress = null) {
    const getPipUrl = 'https://bootstrap.pypa.io/get-pip.py';
    const getPipPath = path.join(this.pythonDir, 'get-pip.py');

    try {
      console.log('Downloading get-pip.py...');
      await this.downloader.downloadFile(getPipUrl, getPipPath);

      if (onProgress) {
        onProgress({
          component: 'pip',
          stage: 'installing',
          percent: 50
        });
      }

      console.log('Installing pip...');
      await this.runPython([getPipPath, '--no-warn-script-location']);

      fs.unlinkSync(getPipPath);
      console.log('pip installed successfully');

    } catch (error) {
      if (fs.existsSync(getPipPath)) {
        fs.unlinkSync(getPipPath);
      }
      throw error;
    }
  }

  /**
   * Install Python packages from requirements.txt
   */
  async installPackages(requirementsPath, onProgress = null) {
    console.log('Installing Python packages...');

    if (!fs.existsSync(requirementsPath)) {
      throw new Error(`Requirements file not found: ${requirementsPath}`);
    }

    const packages = fs.readFileSync(requirementsPath, 'utf8')
      .split('\n')
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#'));

    let installed = 0;

    for (const pkg of packages) {
      console.log(`Installing ${pkg}...`);

      if (onProgress) {
        onProgress({
          component: pkg,
          stage: 'installing',
          percent: (installed / packages.length) * 100
        });
      }

      await this.runPython([
        '-m', 'pip', 'install',
        pkg,
        '--no-warn-script-location'
      ]);

      installed++;
    }

    console.log('All packages installed successfully');
  }

  /**
   * Run Python command
   */
  async runPython(args, options = {}) {
    return new Promise((resolve, reject) => {
      const cmd = `"${this.pythonExe}" ${args.map(a => `"${a}"`).join(' ')}`;

      exec(cmd, options, (error, stdout, stderr) => {
        if (error) {
          console.error('Python error:', stderr);
          reject(error);
        } else {
          resolve(stdout);
        }
      });
    });
  }

  /**
   * Setup complete Python environment: runtime + packages
   */
  async setupEnvironment(requirementsPath, onProgress = null) {
    try {
      // Step 1: Download Python runtime
      await this.downloadPython((progress) => {
        if (onProgress) {
          onProgress({ step: 1, total: 3, ...progress });
        }
      });

      // Step 2: Install pip
      await this.installPip((progress) => {
        if (onProgress) {
          onProgress({ step: 2, total: 3, ...progress });
        }
      });

      // Step 3: Install packages
      await this.installPackages(requirementsPath, (progress) => {
        if (onProgress) {
          onProgress({ step: 3, total: 3, ...progress });
        }
      });

      console.log('Python environment setup complete');
      return {
        pythonExe: this.pythonExe,
        pythonDir: this.pythonDir
      };

    } catch (error) {
      console.error('Failed to setup Python environment:', error);
      throw error;
    }
  }

  /**
   * Launch backend Python application
   */
  async launchBackend(backendScriptPath) {
    if (!this.isPythonInstalled()) {
      throw new Error('Python runtime not installed');
    }

    return new Promise((resolve, reject) => {
      const process = exec(
        `"${this.pythonExe}" "${backendScriptPath}"`,
        { cwd: path.dirname(backendScriptPath) }
      );

      process.stdout.on('data', (data) => {
        console.log('[Backend]', data.toString().trim());
      });

      process.stderr.on('data', (data) => {
        console.error('[Backend Error]', data.toString().trim());
      });

      process.on('error', reject);

      // Resolve immediately with the process handle
      resolve(process);
    });
  }

  /**
   * Get Python environment info
   */
  getEnvironmentInfo() {
    return {
      pythonExe: this.pythonExe,
      pythonDir: this.pythonDir,
      installed: this.isPythonInstalled(),
      version: this.pythonVersion
    };
  }
}

module.exports = PythonEnvironmentManager;
