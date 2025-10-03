/**
 * GitHub SHA256 Fetcher
 * Fetches actual SHA256 hash from GitHub API for verification
 * Instead of hardcoding placeholder values
 */

const https = require('https');

class GitHubSHA256Fetcher {
  /**
   * Extract owner, repo, and file path from GitHub raw URL
   * Example: https://raw.githubusercontent.com/asd007/rdo-overlay/main/data/rdr2_map_hq.png
   * Returns: { owner: 'asd007', repo: 'rdo-overlay', branch: 'main', path: 'data/rdr2_map_hq.png' }
   */
  static parseGitHubUrl(url) {
    const match = url.match(/github(?:usercontent)?\.com\/([^\/]+)\/([^\/]+)\/(?:raw\/)?([^\/]+)\/(.+)/);

    if (!match) {
      throw new Error(`Invalid GitHub URL format: ${url}`);
    }

    return {
      owner: match[1],
      repo: match[2],
      branch: match[3],
      path: match[4]
    };
  }

  /**
   * Fetch SHA256 from GitHub API
   * Uses GitHub's blob API which returns the SHA (SHA-1, but we convert to get file info)
   */
  static async fetchSHA256(githubUrl) {
    const { owner, repo, branch, path } = this.parseGitHubUrl(githubUrl);

    try {
      // Step 1: Get the commit SHA for the branch
      const commitSha = await this.getLatestCommitSHA(owner, repo, branch);

      // Step 2: Get the tree for that commit
      const treeSha = await this.getTreeSHA(owner, repo, commitSha);

      // Step 3: Find the file in the tree
      const fileSha = await this.getFileSHA(owner, repo, treeSha, path);

      // Step 4: Download the blob and calculate SHA256
      const sha256 = await this.calculateBlobSHA256(owner, repo, fileSha);

      return {
        sha256,
        url: githubUrl,
        path,
        branch,
        commitSha
      };

    } catch (error) {
      console.error(`Failed to fetch SHA256 for ${githubUrl}:`, error.message);

      // Fallback: Download file and calculate SHA256 directly
      console.log('Falling back to direct download for hash calculation...');
      return await this.fetchSHA256FromDirectDownload(githubUrl);
    }
  }

  /**
   * Fallback method: Download file directly and calculate SHA256
   */
  static async fetchSHA256FromDirectDownload(url) {
    const crypto = require('crypto');
    const hash = crypto.createHash('sha256');

    return new Promise((resolve, reject) => {
      https.get(url, (response) => {
        if (response.statusCode !== 200) {
          reject(new Error(`HTTP ${response.statusCode}: ${response.statusMessage}`));
          return;
        }

        response.on('data', (chunk) => {
          hash.update(chunk);
        });

        response.on('end', () => {
          const sha256 = hash.digest('hex');
          resolve({
            sha256,
            url,
            method: 'direct-download'
          });
        });

        response.on('error', reject);
      }).on('error', reject);
    });
  }

  /**
   * Get latest commit SHA for a branch
   */
  static async getLatestCommitSHA(owner, repo, branch) {
    const url = `https://api.github.com/repos/${owner}/${repo}/git/ref/heads/${branch}`;
    const data = await this.githubApiRequest(url);
    return data.object.sha;
  }

  /**
   * Get tree SHA from commit
   */
  static async getTreeSHA(owner, repo, commitSha) {
    const url = `https://api.github.com/repos/${owner}/${repo}/git/commits/${commitSha}`;
    const data = await this.githubApiRequest(url);
    return data.tree.sha;
  }

  /**
   * Find file SHA in tree
   */
  static async getFileSHA(owner, repo, treeSha, filePath) {
    const url = `https://api.github.com/repos/${owner}/${repo}/git/trees/${treeSha}?recursive=1`;
    const data = await this.githubApiRequest(url);

    const file = data.tree.find(item => item.path === filePath);
    if (!file) {
      throw new Error(`File not found in tree: ${filePath}`);
    }

    return file.sha;
  }

  /**
   * Download blob and calculate SHA256
   */
  static async calculateBlobSHA256(owner, repo, blobSha) {
    const url = `https://api.github.com/repos/${owner}/${repo}/git/blobs/${blobSha}`;
    const data = await this.githubApiRequest(url);

    // GitHub returns base64 encoded content
    const buffer = Buffer.from(data.content, 'base64');

    const crypto = require('crypto');
    const hash = crypto.createHash('sha256');
    hash.update(buffer);

    return hash.digest('hex');
  }

  /**
   * Make GitHub API request with User-Agent header
   */
  static async githubApiRequest(url) {
    return new Promise((resolve, reject) => {
      const options = {
        headers: {
          'User-Agent': 'RDO-Map-Overlay',
          'Accept': 'application/vnd.github.v3+json'
        }
      };

      https.get(url, options, (response) => {
        let data = '';

        response.on('data', (chunk) => {
          data += chunk;
        });

        response.on('end', () => {
          if (response.statusCode !== 200) {
            reject(new Error(`GitHub API error: ${response.statusCode} - ${data}`));
            return;
          }

          try {
            resolve(JSON.parse(data));
          } catch (error) {
            reject(new Error(`Failed to parse GitHub API response: ${error.message}`));
          }
        });

        response.on('error', reject);
      }).on('error', reject);
    });
  }

  /**
   * Verify downloaded file against expected SHA256
   */
  static async verifyFile(filePath, expectedSHA256) {
    const fs = require('fs');
    const crypto = require('crypto');

    return new Promise((resolve, reject) => {
      const hash = crypto.createHash('sha256');
      const stream = fs.createReadStream(filePath);

      stream.on('data', (chunk) => {
        hash.update(chunk);
      });

      stream.on('end', () => {
        const actualSHA256 = hash.digest('hex');
        const isValid = actualSHA256.toLowerCase() === expectedSHA256.toLowerCase();

        resolve({
          isValid,
          expected: expectedSHA256,
          actual: actualSHA256,
          filePath
        });
      });

      stream.on('error', reject);
    });
  }
}

module.exports = GitHubSHA256Fetcher;
