// Override console.log to also save to file
const fs = require('fs');
const path = require('path');
const logFile = path.join(__dirname, 'renderer.log');

const originalLog = console.log;
console.log = function(...args) {
    const timestamp = new Date().toISOString();
    const message = `${timestamp}: ${args.join(' ')}\n`;
    fs.appendFileSync(logFile, message);
    originalLog.apply(console, args);
};

const { ipcRenderer, shell } = require('electron');
const axios = require('axios');
const io = require('socket.io-client');

// Configuration - backend URL will be set dynamically
let BACKEND_URL = 'http://127.0.0.1:5000';  // Default fallback

// Initialize connection wrapper
function initializeConnection() {
    initialize();
}

// Get dynamic backend port from main process
(async () => {
    try {
        const port = await ipcRenderer.invoke('get-backend-port');
        BACKEND_URL = `http://127.0.0.1:${port}`;
        console.log(`Backend URL: ${BACKEND_URL}`);

        // Initialize connection after we have the port
        initializeConnection();
    } catch (error) {
        console.error('Failed to get backend port:', error);
        // Fall back to default port 5000
        initializeConnection();
    }
})();

// Canvas setup
const canvas = document.getElementById('overlay-canvas');
const ctx = canvas.getContext('2d', { alpha: true });

// UI elements
const statusBar = document.getElementById('status-bar');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const fpsDisplay = document.getElementById('fps-display');
const qualityDisplay = document.getElementById('quality-display');
const collectedDisplay = document.getElementById('collected-display');
const hotkeys = document.getElementById('hotkeys');
const alignmentProgress = document.getElementById('alignment-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');

// State
let overlayVisible = true;
let overlayOpacity = 0.7;
let isAligning = false;
let isTracking = false;
let allCollectibles = []; // ALL collectibles in map coordinates (loaded once from /collectibles)
let currentCollectibles = []; // Visible collectibles with screen coordinates (transformed per frame)
let currentViewport = null; // Current viewport in detection space (updated per frame)
// Collected items now tracked in trackerState.collectedItems (unified storage)
let hoveredCollectible = null; // Track hovered collectible
let continuousCapture = true; // Enable continuous capture
let socket = null; // WebSocket connection
let isBackendConnected = false; // Track backend connection status
let isRdr2Active = null; // Track RDR2 window state (null until first event received)
let isClickThroughEnabled = true; // Track click-through state (disabled when video player/menus open)

// Tooltip element
let tooltip = null;
let tooltipHideTimeout = null;

// Collectible type colors (BGR in Python, RGB in JS)
const TYPE_COLORS = {
  'arrowhead': { r: 168, g: 85, b: 247 },
  'coin': { r: 234, g: 179, b: 8 },
  'heirloom': { r: 236, g: 132, b: 249 },
  'bottle': { r: 62, g: 106, b: 139 },
  'egg': { r: 255, g: 255, b: 255 },
  'flower': { r: 239, g: 68, b: 68 },
  'card': { r: 6, g: 182, b: 212 },
  'fossil': { r: 34, g: 197, b: 94 },
  'jewelry': { r: 234, g: 179, b: 8 },
  'lost_jewelry': { r: 234, g: 179, b: 8 },
  'ring': { r: 234, g: 179, b: 8 },
  'earring': { r: 234, g: 179, b: 8 },
  'bracelet': { r: 234, g: 179, b: 8 },
  'necklace': { r: 234, g: 179, b: 8 },
  'jewelry_random': { r: 234, g: 179, b: 8 },
  'cups': { r: 234, g: 179, b: 8 },
  'wands': { r: 168, g: 85, b: 247 },
  'pentacles': { r: 234, g: 179, b: 8 },
  'swords': { r: 6, g: 182, b: 212 },
  'fossils': { r: 34, g: 197, b: 94 },
  'fossils_random': { r: 34, g: 197, b: 94 },
  'random': { r: 255, g: 255, b: 255 }
};

// Collectible type icons (cute emoji representations)
const TYPE_ICONS = {
  'arrowhead': '🎯',     // Red/white target
  'coin': '🪙',          // Gold coin
  'heirloom': '👑',      // Gold crown
  'bottle': '🍾',        // Gold/green bottle
  'egg': '🥚',           // White/beige egg
  'flower': '🌺',        // Pink/red flower
  'card': '🎴',          // Red card
  'fossil': '🦴',        // White bone
  'jewelry': '💍',       // Gold ring with gem
  'lost_jewelry': '💍',  // Backend sends as lost_jewelry
  'ring': '💍',          // Ring
  'earring': '💎',       // Diamond/earring
  'bracelet': '📿',      // Prayer beads/bracelet
  'necklace': '📿',      // Necklace
  'jewelry_random': '💍', // Random jewelry
  'cups': '🏆',          // Gold trophy
  'wands': '⭐',         // Yellow star
  'pentacles': '🪙',     // Pentacles/coins
  'swords': '⚔️',        // Swords
  'fossils': '🦴',       // White bone
  'fossils_random': '🦴', // Random fossils
  'random': '❓'         // Random items
};

// Collectible sizes (48x48 pixels at 2.4x)
const COLLECTIBLE_SIZE = {
  outerRadius: 24,  // 48px diameter (3x from original 20px)
  hitRadius: 25     // Hit detection radius (tight to visual marker)
};

// Create tooltip element
function createTooltip() {
  tooltip = document.createElement('div');
  tooltip.id = 'collectible-tooltip';
  tooltip.style.cssText = `
    position: absolute;
    background: rgba(0, 0, 0, 0.98);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(217, 119, 6, 0.7);
    border-radius: 8px;
    padding: 10px 12px;
    color: white;
    font-size: 13px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    max-width: 320px;
    z-index: 10000;
    pointer-events: auto;
    display: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  `;

  document.body.appendChild(tooltip);
}

// Show tooltip for collectible
function showTooltip(collectible) {
  if (!tooltip) return;

  // Cancel any pending hide when new tooltip appears
  cancelTooltipHide();

  // Map shortened field names from backend
  const name = collectible.n || collectible.name || 'Unknown';
  const type = collectible.t || collectible.type || 'unknown';
  const helpText = collectible.h || collectible.help || '';
  const videoLink = collectible.v || collectible.video || '';

  // Optimized compact layout with video button (side determined after positioning)
  let tooltipHTML = `
    <div class="tooltip-content" style="position: relative; padding-right: ${videoLink ? '48px' : '0'};">
      <div style="font-weight: bold; color: #fbbf24; margin-bottom: 4px; font-size: 16px; line-height: 1.2;">${name}</div>
      <div style="font-size: 12px; color: #9ca3af; margin-bottom: ${helpText ? '4px' : '6px'};">Type: ${type}</div>
  `;

  if (helpText) {
    tooltipHTML += `<div style="margin-bottom: 6px; font-size: 13px; line-height: 1.3; color: #d1d5db;">${helpText}</div>`;
  }

  // Video button (will be positioned dynamically based on tooltip placement)
  if (videoLink) {
    tooltipHTML += `
      <div class="tooltip-video-link" data-video-url="${videoLink}" data-collectible-name="${name.replace(/"/g, '&quot;')}"
           style="position: absolute; top: 0; right: 0; width: 40px; height: 40px; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 8px rgba(0,0,0,0.4); user-select: none; transition: transform 0.1s;">
        <span style="font-size: 20px; margin-left: 2px;">▶</span>
      </div>`;
  }

  // Add collection status
  const isCollected = trackerState.collectedItems[getCollectibleId(collectible)];
  tooltipHTML += `
      <div style="font-size: 13px; color: ${isCollected ? '#22c55e' : '#ef4444'}; margin-top: 4px; font-weight: 500;">
        ${isCollected ? '✓ Collected' : '⚫ Not Collected'}
      </div>
    </div>
  `;

  tooltip.innerHTML = tooltipHTML;

  // Position off-screen to measure actual dimensions
  tooltip.style.left = '-9999px';
  tooltip.style.top = '-9999px';
  tooltip.style.display = 'block';

  // Get actual rendered dimensions
  const tooltipRect = tooltip.getBoundingClientRect();
  const actualWidth = tooltipRect.width;
  const actualHeight = tooltipRect.height;

  // Recalculate position with actual dimensions
  const adjustedPos = calculateTooltipPosition(collectible.x, collectible.y, actualWidth, actualHeight);

  // Position correctly
  tooltip.style.left = adjustedPos.x + 'px';
  tooltip.style.top = adjustedPos.y + 'px';

  // Reposition video button based on which side the cursor/collectible is on
  if (videoLink) {
    const videoButton = tooltip.querySelector('.tooltip-video-link');
    const tooltipContent = tooltip.querySelector('.tooltip-content');

    if (videoButton && tooltipContent) {
      // If left corners selected, cursor is on left → button on left
      // If right corners selected, cursor is on right → button on right
      const isLeftSide = adjustedPos.corner.includes('left');

      if (isLeftSide) {
        videoButton.style.left = '0';
        videoButton.style.right = 'auto';
        tooltipContent.style.paddingLeft = '48px';
        tooltipContent.style.paddingRight = '0';
      } else {
        videoButton.style.left = 'auto';
        videoButton.style.right = '0';
        tooltipContent.style.paddingLeft = '0';
        tooltipContent.style.paddingRight = '48px';
      }
    }
  }

  // Right-click handled by backend click observer + hit-testing
  // (no need for oncontextmenu handler)
}

// Hide tooltip with delay
function hideTooltip() {
  // Clear any existing timeout
  if (tooltipHideTimeout) {
    clearTimeout(tooltipHideTimeout);
  }

  // Wait 150ms before hiding (reduced from 1000ms)
  tooltipHideTimeout = setTimeout(() => {
    if (tooltip) {
      tooltip.style.display = 'none';
    }
  }, 150);
}

// Cancel pending tooltip hide (when new tooltip appears)
function cancelTooltipHide() {
  if (tooltipHideTimeout) {
    clearTimeout(tooltipHideTimeout);
    tooltipHideTimeout = null;
  }
}

// Video player
let videoPlayerFrame = null;
let youtubePlayer = null;
let isYouTubeAPIReady = false;
let videoCloseHandler = null; // Track close button handler for cleanup
let embedCheckCache = new Map(); // Cache oEmbed check results to avoid repeated API calls

// Check if video is embeddable using YouTube oEmbed API
async function checkVideoEmbeddable(videoId) {
  // Check cache first
  if (embedCheckCache.has(videoId)) {
    return embedCheckCache.get(videoId);
  }

  try {
    const response = await fetch(`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });

    const embeddable = response.ok;
    embedCheckCache.set(videoId, embeddable);

    console.log(`[YouTube Pre-check] Video ${videoId} embeddable: ${embeddable}`);
    return embeddable;
  } catch (error) {
    // If oEmbed fails, assume embeddable (let the player try)
    console.warn('[YouTube Pre-check] oEmbed check failed, assuming embeddable:', error);
    return true;
  }
}

// Load YouTube IFrame API
function loadYouTubeAPI() {
  if (window.YT) {
    isYouTubeAPIReady = true;
    return;
  }

  const tag = document.createElement('script');
  tag.src = 'https://www.youtube.com/iframe_api';
  const firstScriptTag = document.getElementsByTagName('script')[0];
  firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

  // API ready callback
  window.onYouTubeIframeAPIReady = () => {
    isYouTubeAPIReady = true;
    console.log('[YouTube] IFrame API loaded');
  };
}

function createVideoPlayer() {
  if (videoPlayerFrame) return videoPlayerFrame;

  videoPlayerFrame = document.createElement('div');
  videoPlayerFrame.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 900px;
    height: 600px;
    background: #000000;
    border: 3px solid #fbbf24;
    border-radius: 12px;
    z-index: 99999;
    display: none;
    padding: 24px;
    box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.85), 0 12px 48px rgba(0, 0, 0, 0.9);
  `;

  document.body.appendChild(videoPlayerFrame);
  return videoPlayerFrame;
}

async function showVideoPlayer(videoUrl, collectibleName) {
  console.log('[Video Player] Opening video player');

  if (!videoPlayerFrame) {
    createVideoPlayer();
  }

  // Disable click-through so user can interact with video player
  console.log('[Video Player] Disabling click-through');
  isClickThroughEnabled = false;
  await ipcRenderer.invoke('set-click-through', false);
  console.log('[Video Player] Click-through disabled, isClickThroughEnabled =', isClickThroughEnabled);

  // Extract YouTube video ID and timestamp
  const youtubeMatch = videoUrl.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&?]+)/);

  if (!youtubeMatch) {
    console.error('[Video Player] Invalid YouTube URL:', videoUrl);
    return;
  }

  const videoId = youtubeMatch[1];

  // Extract start time parameter (t=120s or t=2m30s format)
  let startSeconds = 0;
  const timeMatch = videoUrl.match(/[?&]t=(\d+)([hms]?)/);
  if (timeMatch) {
    const value = parseInt(timeMatch[1]);
    const unit = timeMatch[2] || 's'; // Default to seconds if no unit

    if (unit === 'h') {
      startSeconds = value * 3600;
    } else if (unit === 'm') {
      startSeconds = value * 60;
    } else {
      startSeconds = value; // seconds
    }
  }

  // Also check for #t= format
  const hashTimeMatch = videoUrl.match(/#t=(\d+)/);
  if (hashTimeMatch) {
    startSeconds = parseInt(hashTimeMatch[1]);
  }

  if (startSeconds > 0) {
    console.log(`[Video Player] Starting video at ${startSeconds} seconds (${Math.floor(startSeconds / 60)}:${String(startSeconds % 60).padStart(2, '0')})`);
  }

  // Pre-check if video is embeddable before creating player UI
  const isEmbeddable = await checkVideoEmbeddable(videoId);

  if (!isEmbeddable) {
    // Video cannot be embedded - open directly in external browser with timestamp
    let externalUrl = `https://www.youtube.com/watch?v=${videoId}`;
    if (startSeconds > 0) {
      externalUrl += `&t=${startSeconds}s`;
    }

    console.log('[Video Player] Video not embeddable (pre-check failed), opening in browser:', externalUrl);
    shell.openExternal(externalUrl);

    // Re-enable click-through
    isClickThroughEnabled = true;
    await ipcRenderer.invoke('set-click-through', true);
    return; // Don't create player UI
  }

  // Create player container HTML
  videoPlayerFrame.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h3 style="margin: 0; color: #fbbf24; font-size: 24px; font-weight: bold;">${collectibleName} - Video Guide</h3>
      <button class="video-close-button" style="background: #ef4444; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 18px; font-weight: bold; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.5); transition: all 0.2s;">✕ Close</button>
    </div>
    <div id="youtube-player" style="width: 100%; height: 520px; border-radius: 8px; overflow: hidden;"></div>
  `;

  videoPlayerFrame.style.display = 'block';

  // Remove old event listener if it exists
  const closeButton = videoPlayerFrame.querySelector('.video-close-button');
  if (closeButton && videoCloseHandler) {
    closeButton.removeEventListener('click', videoCloseHandler);
  }

  // Add DOM event listener for close button (works when click-through disabled)
  videoCloseHandler = (e) => {
    e.stopPropagation();
    e.preventDefault();
    console.log('[Video Player] Close button clicked via DOM');
    closeVideoPlayer();
  };

  if (closeButton) {
    closeButton.addEventListener('click', videoCloseHandler);
  }

  // Wait for API to be ready, then create player
  const initPlayer = () => {
    if (window.YT && window.YT.Player) {
      // Destroy existing player if any
      if (youtubePlayer) {
        youtubePlayer.destroy();
      }

      // Create new YouTube player using IFrame API
      youtubePlayer = new YT.Player('youtube-player', {
        height: '520',
        width: '100%',
        videoId: videoId,
        playerVars: {
          autoplay: 1,
          modestbranding: 1,
          rel: 0,
          start: startSeconds, // Start video at specified timestamp
          // Additional parameters to try bypassing embed restrictions
          origin: window.location.origin,
          enablejsapi: 1,
          widgetid: 1
        },
        host: 'https://www.youtube-nocookie.com', // Use nocookie domain (sometimes bypasses restrictions)
        events: {
          onError: (event) => {
            console.error('[YouTube Player] Error code:', event.data);

            // Error 150/153/101/100 = embedding disabled by video owner
            if (event.data === 150 || event.data === 153 || event.data === 101 || event.data === 100) {
              // Fallback: open in external browser (preserve timestamp)
              let fallbackUrl = `https://www.youtube.com/watch?v=${videoId}`;
              if (startSeconds > 0) {
                fallbackUrl += `&t=${startSeconds}s`;
              }
              console.log('[YouTube Player] Embedding disabled (error ' + event.data + '), opening in browser:', fallbackUrl);

              // Show user-friendly message
              const playerContainer = document.getElementById('youtube-player');
              if (playerContainer) {
                playerContainer.innerHTML = `
                  <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; background: #1a1a1a; color: white; text-align: center; padding: 40px;">
                    <div style="font-size: 48px; margin-bottom: 20px;">🎥</div>
                    <div style="font-size: 20px; margin-bottom: 30px;">This video cannot be embedded</div>
                    <div style="font-size: 16px; color: #9ca3af; margin-bottom: 30px;">The video owner has disabled embedding.<br>Opening in your default browser...</div>
                  </div>
                `;
              }

              // Open in external browser after 2 seconds
              setTimeout(() => {
                shell.openExternal(fallbackUrl);
                closeVideoPlayer();
              }, 2000);
            }
          }
        }
      });
    } else {
      // API not ready yet, wait
      setTimeout(initPlayer, 100);
    }
  };

  initPlayer();
}

async function closeVideoPlayer() {
  console.log('[Video Player] Closing video player');

  if (videoPlayerFrame) {
    videoPlayerFrame.style.display = 'none';

    // Destroy YouTube player instance
    if (youtubePlayer) {
      youtubePlayer.destroy();
      youtubePlayer = null;
    }

    videoPlayerFrame.innerHTML = '';

    // Remove event listener
    if (videoCloseHandler) {
      const closeButton = videoPlayerFrame.querySelector('.video-close-button');
      if (closeButton) {
        closeButton.removeEventListener('click', videoCloseHandler);
      }
      videoCloseHandler = null;
    }

    // Re-enable click-through (video player closed)
    console.log('[Video Player] Re-enabling click-through');
    isClickThroughEnabled = true;
    await ipcRenderer.invoke('set-click-through', true);
    console.log('[Video Player] Click-through re-enabled, isClickThroughEnabled =', isClickThroughEnabled);
  }
}

// Video link click handler (no longer used - using hit-testing instead)
// Make global for backwards compatibility
window.closeVideoPlayer = closeVideoPlayer;

// Hit-testing functions for UI elements (overlay is always click-through)

function isClickOnTooltipVideoLink(x, y) {
  /**Check if click is on tooltip video link*/
  if (!tooltip || tooltip.style.display === 'none') {
    return null;
  }

  const videoLink = tooltip.querySelector('.tooltip-video-link');
  if (!videoLink) {
    return null;
  }

  const rect = videoLink.getBoundingClientRect();
  if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
    return {
      videoUrl: videoLink.dataset.videoUrl,
      collectibleName: videoLink.dataset.collectibleName
    };
  }

  return null;
}

function isClickOnVideoCloseButton(x, y) {
  /**Check if click is on video player close button*/
  if (!videoPlayerFrame || videoPlayerFrame.style.display === 'none') {
    return false;
  }

  const closeButton = videoPlayerFrame.querySelector('.video-close-button');
  if (!closeButton) {
    return false;
  }

  const rect = closeButton.getBoundingClientRect();
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

// Hit-testing functions for UI elements (see below: isClickOnTooltipVideoLink, isClickOnVideoCloseButton, findCollectibleAt)

// Get unique ID for collectible using raw item name
function getCollectibleId(collectible) {
  // Use the item name from items.json directly - it's already unique
  // (e.g., "arrowhead_random_0", "provision_duck_egg", etc.)
  // Map shortened field names from backend
  const name = collectible.n || collectible.name;

  if (name) {
    return name;  // Direct use of unique ID from items.json
  }

  // Fallback to lat/lng for items without names (should never happen)
  const type = collectible.t || collectible.type;
  const lat = collectible.lat ? collectible.lat.toFixed(4) : '0';
  const lng = collectible.lng ? collectible.lng.toFixed(4) : '0';
  return `${type}-${lat}-${lng}`;
}

// Legacy: Load old collected items and migrate to tracker format
function loadCollectedItems() {
  try {
    const saved = localStorage.getItem('rdo-collected-items');
    if (saved) {
      // Migrate old Set-based storage to tracker object format
      const items = JSON.parse(saved);
      for (const id of items) {
        trackerState.collectedItems[id] = true;
      }
      // Clear old storage
      localStorage.removeItem('rdo-collected-items');
      saveTrackerState();
    }
  } catch (e) {
    console.error('Failed to migrate collected items:', e);
  }
  return new Set(); // Return empty set, we use trackerState now
}

// Toggle collected status (unified with tracker)
function toggleCollected(collectible) {
  const id = getCollectibleId(collectible);
  const name = collectible.n || collectible.name;
  const type = collectible.t || collectible.type;

  if (trackerState.collectedItems[id]) {
    delete trackerState.collectedItems[id];
    console.log(`[Map] Marked ${name} (${type}) as NOT collected (ID: ${id})`);
  } else {
    trackerState.collectedItems[id] = true;
    console.log(`[Map] Marked ${name} (${type}) as collected (ID: ${id})`);
  }

  // Save to unified storage
  saveTrackerState();

  // Update collected display
  updateCollectedDisplay();

  // Update tracker UI
  renderTrackerAll();

  // Redraw to reflect changes
  drawOverlay();
}

// Update collected items counter
function updateCollectedDisplay() {
  if (collectedDisplay) {
    collectedDisplay.textContent = Object.keys(trackerState.collectedItems).length;
  }
}

// Canvas mouse event handlers removed - backend observes clicks globally, frontend does hit-testing

// Resize canvas to window size
function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// Load all collectibles once (called on startup)
async function loadAllCollectibles() {
  try {
    console.log('Loading all collectibles from backend...');
    const response = await axios.get(`${BACKEND_URL}/collectibles`);

    if (response.data.success) {
      allCollectibles = response.data.collectibles;
      console.log(`✓ Loaded ${allCollectibles.length} collectibles in map coordinates`);
      return true;
    } else {
      console.error('Failed to load collectibles:', response.data.error);
      return false;
    }
  } catch (error) {
    console.error('Error loading collectibles:', error);
    return false;
  }
}

// Transform collectibles from map space to screen space based on viewport
// Cache for incremental transform optimization
let lastViewport = null;
let lastVisibleCollectibles = [];

function transformCollectibles(viewport) {
  if (!viewport || !allCollectibles || allCollectibles.length === 0) {
    return [];
  }

  const { x: viewportX, y: viewportY, width: viewportW, height: viewportH } = viewport;

  // Screen size (1920x1080 full screen - no cropping)
  const screenWidth = 1920;
  const screenHeight = 1080;

  // OPTIMIZATION: Detect pure pan (zoom level unchanged)
  // When only panning, offset existing visible collectibles instead of recalculating from map coords
  const isPurePan = lastViewport &&
    Math.abs(lastViewport.width - viewportW) < 0.1 &&
    Math.abs(lastViewport.height - viewportH) < 0.1;

  if (isPurePan && lastVisibleCollectibles.length > 0) {
    // Calculate screen-space offset based on viewport movement
    // Viewport is in detection space, need to convert to screen pixels accounting for zoom
    const scaleX = screenWidth / viewportW;
    const scaleY = screenHeight / viewportH;

    // Viewport movement in detection space
    const viewportDx = lastViewport.x - viewportX;
    const viewportDy = lastViewport.y - viewportY;

    // Convert to screen space: screen_movement = viewport_movement * (screen_size / viewport_size)
    const dx = viewportDx * scaleX;
    const dy = viewportDy * scaleY;

    // OPTIMIZATION: Build existing map IDs set while offsetting (single pass)
    const offsetCollectibles = [];
    const existingMapIds = new Set();

    for (let i = 0; i < lastVisibleCollectibles.length; i++) {
      const col = lastVisibleCollectibles[i];
      const newX = col.x + dx;
      const newY = col.y + dy;

      // Cull items that moved off-screen (with margin for smooth transitions)
      if (newX < -50 || newX > screenWidth + 50 ||
          newY < -50 || newY > screenHeight + 50) {
        continue;
      }

      // Reuse existing object if possible, mutate in place
      col.x = newX;
      col.y = newY;
      offsetCollectibles.push(col);
      existingMapIds.add(`${col.map_x}_${col.map_y}`);
    }

    // Check boundary regions for newly visible collectibles
    const margin = 100; // Map-space margin for boundary detection
    const expandedLeft = viewportX - margin;
    const expandedRight = viewportX + viewportW + margin;
    const expandedTop = viewportY - margin;
    const expandedBottom = viewportY + viewportH + margin;

    // Only scan collectibles in boundary region (newly entering viewport)
    for (let i = 0; i < allCollectibles.length; i++) {
      const col = allCollectibles[i];
      const mapX = col.map_x;
      const mapY = col.map_y;

      // Only check boundary region (most collectibles fail this check quickly)
      if (mapX < expandedLeft || mapX > expandedRight ||
          mapY < expandedTop || mapY > expandedBottom) {
        continue;
      }

      // Skip if already visible
      const mapId = `${mapX}_${mapY}`;
      if (existingMapIds.has(mapId)) continue;

      // Transform newly visible collectible
      const screenX = (mapX - viewportX) * scaleX;
      const screenY = (mapY - viewportY) * scaleY;

      // Add if on-screen
      if (screenX >= -50 && screenX <= screenWidth + 50 &&
          screenY >= -50 && screenY <= screenHeight + 50) {
        offsetCollectibles.push({
          x: screenX,
          y: screenY,
          t: col.t,
          n: col.n,
          h: col.h,
          v: col.v,
          map_x: mapX,
          map_y: mapY
        });
      }
    }

    lastViewport = viewport;
    lastVisibleCollectibles = offsetCollectibles;
    return offsetCollectibles;
  }

  // Full recalculation (zoom changed or first frame)
  const viewportRight = viewportX + viewportW;
  const viewportBottom = viewportY + viewportH;
  const scaleX = screenWidth / viewportW;
  const scaleY = screenHeight / viewportH;

  const visibleCollectibles = [];

  for (let i = 0; i < allCollectibles.length; i++) {
    const col = allCollectibles[i];
    const mapX = col.map_x;
    const mapY = col.map_y;

    if (mapX < viewportX || mapX > viewportRight ||
        mapY < viewportY || mapY > viewportBottom) {
      continue;
    }

    const screenX = (mapX - viewportX) * scaleX;
    const screenY = (mapY - viewportY) * scaleY;

    visibleCollectibles.push({
      x: screenX,
      y: screenY,
      t: col.t,
      n: col.n,
      h: col.h,
      v: col.v,
      map_x: mapX,
      map_y: mapY
    });
  }

  lastViewport = viewport;
  lastVisibleCollectibles = visibleCollectibles;
  return visibleCollectibles;
}

// Performance metrics
const performanceMetrics = {
  receiveTimestamps: [],
  transformTimes: [],
  updateCounts: 0,
  skippedUpdates: 0
};

// Rendering state
let renderLoopRunning = false;
let lastRenderTime = 0;
let needsRedraw = false;

// Handle viewport updates from WebSocket (non-blocking)
// Track if we're currently processing a viewport update
let isProcessingUpdate = false;
let pendingViewportUpdate = null;

function handleViewportUpdate(data) {
  const receiveTime = performance.now();
  performanceMetrics.receiveTimestamps.push(receiveTime);
  performanceMetrics.updateCounts++;

  if (!continuousCapture) return;

  if (data.success && data.viewport) {
    // If we're still processing the previous update, queue this one
    if (isProcessingUpdate) {
      pendingViewportUpdate = { data, receiveTime };
      return;
    }

    processViewportUpdate(data, receiveTime);
  }
}

function processViewportUpdate(data, receiveTime) {
  isProcessingUpdate = true;

  // Calculate velocity and acceleration for motion prediction
  const now = receiveTime;
  if (lastViewport && lastViewportUpdateTime > 0) {
    const dt = (now - lastViewportUpdateTime) / 1000; // seconds
    if (dt > 0 && dt < 0.5) { // Sanity check: ignore if >500ms gap
      // Calculate velocity (units per second)
      const newVelocityDx = (data.viewport.x - lastViewport.x) / dt;
      const newVelocityDy = (data.viewport.y - lastViewport.y) / dt;

      // Calculate acceleration (change in velocity per second)
      viewportAcceleration.ddx = (newVelocityDx - viewportVelocity.dx) / dt;
      viewportAcceleration.ddy = (newVelocityDy - viewportVelocity.dy) / dt;

      // Update velocity
      lastVelocity.dx = viewportVelocity.dx;
      lastVelocity.dy = viewportVelocity.dy;
      viewportVelocity.dx = newVelocityDx;
      viewportVelocity.dy = newVelocityDy;
    }
  }
  lastViewportUpdateTime = now;

  // Store viewport (lightweight operation)
  currentViewport = data.viewport;
  predictedViewport = null; // Reset prediction when we get real data
  interpolatedViewport = null;

  // Pan tracking: Calculate viewport movement speed and acceleration
  if (lastPanViewport && lastPanTime) {
    const dt = (now - lastPanTime) / 1000; // seconds
    if (dt > 0 && dt < 0.5) {
      // Viewport movement in detection space (INVERTED: when you pan right, viewport.x decreases)
      // Use same formula as collectible transform to get screen-space movement
      const screenScale = currentViewport.width > 0 ? 1920.0 / currentViewport.width : 1.0;
      const dx_screen = (lastPanViewport.x - currentViewport.x) * screenScale;
      const dy_screen = (lastPanViewport.y - currentViewport.y) * screenScale;

      // Speed in screen pixels/sec (absolute value - direction doesn't matter for speed)
      const speed = Math.sqrt(dx_screen * dx_screen + dy_screen * dy_screen) / dt;

      // Calculate acceleration if we have previous speed
      let acceleration = 0;
      if (panHistory.length > 0) {
        const lastSpeed = panHistory[panHistory.length - 1].speed;
        acceleration = (speed - lastSpeed) / dt; // screen px/sec^2
      }

      panHistory.push({
        frame: performanceMetrics.updateCounts,
        timestamp: now,
        dx: dx_screen,  // Screen pixels (signed)
        dy: dy_screen,  // Screen pixels (signed)
        speed: speed,   // Screen pixels/sec (magnitude)
        acceleration: acceleration,  // Screen pixels/sec^2
        dt: dt
      });

      // Keep last 100 samples
      if (panHistory.length > 100) {
        panHistory.shift();
      }
    }
  }
  lastPanViewport = { ...currentViewport };
  lastPanTime = now;

  // Transform collectibles synchronously - async was causing race conditions
  // The transform is optimized with pure-pan detection and is fast enough
  const transformStart = performance.now();
  currentCollectibles = transformCollectibles(currentViewport);
  const transformTime = performance.now() - transformStart;
  performanceMetrics.transformTimes.push(transformTime);

  // Drift tracking: Pick ONE random collectible that's VISIBLE in current viewport
  // This ensures we immediately start tracking with visible items
  if (!driftTrackingCollectible && currentCollectibles && currentCollectibles.length > 0) {
    const randomIndex = Math.floor(Math.random() * currentCollectibles.length);
    const randomCol = currentCollectibles[randomIndex];
    driftTrackingCollectible = {
      n: randomCol.n,
      t: randomCol.t,
      map_x: randomCol.map_x,
      map_y: randomCol.map_y
    };
    console.log(`[Drift Tracking] Selected visible collectible: ${driftTrackingCollectible.n} (${driftTrackingCollectible.t}) at map (${driftTrackingCollectible.map_x.toFixed(1)}, ${driftTrackingCollectible.map_y.toFixed(1)})`);
  }

  // Track drift: Record screen position ONLY when our tracked collectible is visible
  if (driftTrackingCollectible && currentCollectibles.length > 0) {
    // Find our tracked collectible in current visible collectibles
    const tracked = currentCollectibles.find(col =>
      Math.abs(col.map_x - driftTrackingCollectible.map_x) < 1 &&
      Math.abs(col.map_y - driftTrackingCollectible.map_y) < 1
    );

    if (tracked) {
      driftHistory.push({
        frame: performanceMetrics.updateCounts,
        timestamp: now,
        screen_x: tracked.x,
        screen_y: tracked.y,
        viewport_x: currentViewport.x,
        viewport_y: currentViewport.y,
        viewport_w: currentViewport.width,
        viewport_h: currentViewport.height
      });

      // Keep last 100 samples
      if (driftHistory.length > 100) {
        driftHistory.shift();
      }
    }
  }

  isTracking = true;

  // Update status (lightweight)
  const method = data.method || 'unknown';
  const cascadeLevel = data.cascade_level || 'unknown';

  updateStatus(
    `Tracking ${currentCollectibles.length} items | ${method} | ${cascadeLevel}`,
    'active'
  );

  // Update displays (lightweight)
  if (qualityDisplay) {
    qualityDisplay.textContent = currentCollectibles.length;
  }

  // Request redraw on next animation frame (non-blocking)
  needsRedraw = true;

  // Log transform performance
  if (transformTime > 5) {
    console.warn(`[Transform] Slow: ${transformTime.toFixed(1)}ms for ${allCollectibles.length} collectibles`);
  }

  // Mark processing complete and check for pending updates
  isProcessingUpdate = false;
  if (pendingViewportUpdate) {
    const pending = pendingViewportUpdate;
    pendingViewportUpdate = null;
    processViewportUpdate(pending.data, pending.receiveTime);
  }
}

function handleViewportUpdateFallback(data) {
  // Fallback for match failed
  if (!data.success) {
    // Map not open or match failed - show empty
    if (currentCollectibles.length > 0 || isTracking) {
      currentCollectibles = [];
      currentViewport = null;
      isTracking = false;
      updateStatus('Waiting for map...', 'inactive');
      needsRedraw = true;
    }
  }

  // Performance metrics available via backend /profiling-stats endpoint
  // No periodic console logging - keeps frontend fast and clean
}

// Render loop using requestAnimationFrame (60 FPS, smooth)
function renderLoop(timestamp) {
  // Calculate delta time
  const deltaTime = timestamp - lastRenderTime;
  lastRenderTime = timestamp;

  // Redraw if needed
  if (needsRedraw) {
    drawOverlay();
    needsRedraw = false;
  }

  // Continue loop
  if (renderLoopRunning) {
    requestAnimationFrame(renderLoop);
  }
}

// Start render loop
function startRenderLoop() {
  if (renderLoopRunning) return;

  renderLoopRunning = true;
  lastRenderTime = performance.now();
  requestAnimationFrame(renderLoop);
  console.log('[Render Loop] Started at 60 FPS');
}

// Stop render loop
function stopRenderLoop() {
  renderLoopRunning = false;
  console.log('[Render Loop] Stopped');
}

// Deprecated: Old match update handler (kept for backward compatibility)
function handleMatchUpdate(data) {
  const receiveTime = performance.now();
  performanceMetrics.receiveTimestamps.push(receiveTime);
  performanceMetrics.updateCounts++;

  if (!continuousCapture) return;

  if (data.success) {
    // Check if collectibles actually changed using hash
    const newHash = data.collectible_hash || null;

    if (newHash && newHash === lastCollectibleHash) {
      // Collectibles unchanged - skip expensive update
      performanceMetrics.skippedUpdates++;
      return;
    }

    lastCollectibleHash = newHash;

    // Update collectibles
    currentCollectibles = data.collectibles || [];
    isTracking = true;

    // Update status with stats
    const stats = data.stats || {};
    const matchTime = stats.match_time_median_ms || stats.match_time_mean_ms || 0;
    const successRate = stats.success_rate || 0;

    updateStatus(
      `Tracking ${currentCollectibles.length} items | ${matchTime.toFixed(0)}ms | ${successRate.toFixed(0)}% success`,
      'active'
    );

    // Update displays
    if (qualityDisplay) {
      qualityDisplay.textContent = currentCollectibles.length;
    }
    if (fpsDisplay) {
      fpsDisplay.textContent = Math.round(stats.total_frames / Math.max(1, Date.now() / 1000 - stats.start_time || 1));
    }

    drawOverlay();
  } else {
    // Map not open or match failed - show empty
    if (currentCollectibles.length > 0 || isTracking) {
      currentCollectibles = [];
      isTracking = false;
      lastCollectibleHash = null;
      updateStatus('Waiting for map...', 'inactive');
      drawOverlay();
    }
  }

  // Log metrics every 100 frames
  if (performanceMetrics.updateCounts % 100 === 0) {
    const recent = performanceMetrics.receiveTimestamps.slice(-100);
    const intervals = [];
    for (let i = 1; i < recent.length; i++) {
      intervals.push(recent[i] - recent[i - 1]);
    }

    if (intervals.length > 0) {
      const meanInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      const fps = 1000 / meanInterval;

      console.log(`[Performance] Frontend: ${fps.toFixed(1)} FPS (${meanInterval.toFixed(1)}ms/frame), Skipped: ${performanceMetrics.skippedUpdates}`);
    }
  }
}

// Connect to WebSocket server
function connectWebSocket() {
  if (socket) {
    socket.disconnect();
  }

  console.log('Connecting to WebSocket server...');
  updateStatus('Connecting to backend...', 'inactive');

  socket = io(BACKEND_URL, {
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: Infinity,
    timeout: 5000
  });

  // Connection successful
  socket.on('connect', () => {
    isBackendConnected = true;
    console.log('✓ WebSocket connected');
    updateStatus('Connected - Waiting for map...', 'active');
  });

  // Connection lost
  socket.on('disconnect', (reason) => {
    isBackendConnected = false;
    console.error('✗ WebSocket disconnected:', reason);
    currentCollectibles = [];
    isTracking = false;
    updateStatus('Connection lost - Reconnecting...', 'inactive');
    drawOverlay();
  });

  // Reconnection attempt
  socket.on('reconnect_attempt', (attempt) => {
    console.log(`Reconnection attempt ${attempt}...`);
    updateStatus(`Reconnecting (attempt ${attempt})...`, 'inactive');
  });

  // Reconnection successful
  socket.on('reconnect', (attempt) => {
    isBackendConnected = true;
    console.log('✓ Reconnection successful!');
    updateStatus('Reconnected - Waiting for map...', 'active');
  });

  // Reconnection error
  socket.on('reconnect_error', (error) => {
    console.error('Reconnection error:', error.message);
  });

  // Binary viewport update from backend (optimized protocol - 20 bytes vs 150 bytes)
  socket.on('viewport_update_binary', (binaryData) => {
    const receiveTime = performance.now();

    // Decode binary message (20 bytes total)
    // Format: [success(1)] [x(4)] [y(4)] [width(4)] [height(4)] [confidence(2)] [flags(1)]
    const buffer = new Uint8Array(binaryData);
    const view = new DataView(buffer.buffer);

    // Extract fields (little-endian)
    const success = buffer[0] === 1;
    const x = view.getFloat32(1, true);
    const y = view.getFloat32(5, true);
    const width = view.getFloat32(9, true);
    const height = view.getFloat32(13, true);
    const confidenceRaw = view.getUint16(17, true);
    const methodFlags = buffer[19];

    // Convert confidence from uint16 (0-65535) back to float (0.0-1.0)
    const confidence = confidenceRaw / 65535;

    // Decode method flags
    const isMotionOnly = (methodFlags & 0x01) !== 0;

    // Convert to JSON format for handleViewportUpdate
    const data = {
      success: true,
      viewport: { x, y, width, height },
      confidence,
      method: isMotionOnly ? 'motion_prediction_only' : 'akaze',
      cascade_level: isMotionOnly ? 'Motion-Only' : 'AKAZE'
    };

    handleViewportUpdate(data, receiveTime);
  });

  // JSON viewport update (fallback for failures)
  socket.on('viewport_update', (data) => {
    const receiveTime = performance.now();
    handleViewportUpdate(data, receiveTime);
  });

  // Match update from backend (deprecated, kept for backward compatibility)
  socket.on('match_update', handleMatchUpdate);

  // Cycle change notification from backend
  socket.on('cycle_changed', async (data) => {
    console.log('[Cycle Change] Daily cycle changed - reloading collectibles...');
    console.log(`[Cycle Change] ${data.message} (${data.count} collectibles)`);

    // Reload all collectibles from backend
    const reloaded = await loadAllCollectibles();

    if (reloaded) {
      // Clear sprite cache (collectible positions/types may have changed)
      spriteCache.clear();
      console.log('[Cycle Change] Sprite cache cleared');

      // Force redraw with new collectibles
      if (currentViewport) {
        currentCollectibles = transformCollectibles(currentViewport);
        needsRedraw = true;
      }

      // Notify user
      updateStatus(`Cycle changed - ${data.count} collectibles loaded`, 'active');
      setTimeout(() => {
        if (isTracking) {
          updateStatus(`Tracking ${currentCollectibles.length} items`, 'active');
        }
      }, 3000);
    } else {
      console.error('[Cycle Change] Failed to reload collectibles');
      updateStatus('Cycle changed - reload failed', 'inactive');
    }
  });

  // Window focus changes from backend (sent immediately on connect, then broadcast every 100ms)
  socket.on('window-focus-changed', (data) => {
    const newRdr2State = data.is_rdr2_active;

    // Backend always broadcasts, but frontend only updates DOM if state actually changed
    if (newRdr2State === isRdr2Active) {
      return; // No state change, skip DOM update
    }

    isRdr2Active = newRdr2State;

    if (isRdr2Active) {
      // RDR2 is active - show overlay window and content
      ipcRenderer.send('set-overlay-visibility', true);

      if (overlayVisible) {
        canvas.style.display = 'block';
        statusBar.classList.add('visible');
        // hotkeys.classList.add('visible'); // Disabled per user request
      } else {
        canvas.style.display = 'none';
      }
    } else {
      // RDR2 not active - hide overlay window completely
      // UNLESS video player is open (user is interacting with overlay)
      if (!isClickThroughEnabled) {
        console.log('[Focus] RDR2 inactive but video player open - keeping overlay visible');
        return; // Keep overlay visible when video player or menus are open
      }

      ipcRenderer.send('set-overlay-visibility', false);
      canvas.style.display = 'none';
      statusBar.classList.remove('visible');
      // hotkeys.classList.remove('visible'); // Disabled per user request
      hideTooltip();
      closeVideoPlayer();
    }
  });

  // Global mouse click observation from backend
  socket.on('mouse-clicked', async (data) => {
    const { x, y, button } = data;
    console.log(`[Click Observer] Backend click at (${x}, ${y}), button: ${button}, click-through: ${isClickThroughEnabled}`);

    // Hit-test priority order: Video controls > Tooltip elements > Collectible markers
    // Backend ALWAYS sends clicks, but we handle them differently based on click-through state

    // 1. Check video player close button (highest priority, always handle)
    if (isClickOnVideoCloseButton(x, y)) {
      closeVideoPlayer();
      return; // Handled
    }

    // 2. Check tooltip video link (always handle)
    const videoLinkData = isClickOnTooltipVideoLink(x, y);
    if (videoLinkData && button === 'left') {
      showVideoPlayer(videoLinkData.videoUrl, videoLinkData.collectibleName);
      return; // Handled
    }

    // 3. Check tracker menu clicks (backend hit testing)
    const overTracker = isCursorOverTracker(x, y);

    if (overTracker && !isClickThroughEnabled) {
      // Hit-test specific tracker elements
      const setHeader = findTrackerSetHeaderAt(x, y);
      if (setHeader) {
        if (setHeader.isVisibilityToggle) {
          console.log(`[Click Observer] Visibility toggle for: ${setHeader.setName}`);
          toggleTrackerVisibility(setHeader.setName);
        } else {
          console.log(`[Click Observer] Set header click: ${setHeader.setName}`);
          toggleTrackerSet(setHeader.setName);
        }
        // After click, check if cursor is still over interactive area
        // Cursor position is already x, y - just check if still over tracker after DOM update
        setTimeout(async () => {
          const cursorPos = await ipcRenderer.invoke('get-cursor-position');
          const stillOverTracker = isCursorOverTracker(cursorPos.x, cursorPos.y);
          if (!stillOverTracker && !isClickThroughEnabled) {
            await setClickThrough(true);
          }
        }, 50);
        return; // Handled
      }

      const item = findTrackerItemAt(x, y);
      if (item && button === 'left') {
        console.log(`[Click Observer] Item click: ${item.itemId}`);
        toggleTrackerCollected(item.itemId);
        // After click, check if cursor is still over interactive area
        setTimeout(async () => {
          const cursorPos = await ipcRenderer.invoke('get-cursor-position');
          const stillOverTracker = isCursorOverTracker(cursorPos.x, cursorPos.y);
          if (!stillOverTracker && !isClickThroughEnabled) {
            await setClickThrough(true);
          }
        }, 50);
        return; // Handled
      }

      // Click on tracker but not on any specific element - ignore
      console.log('[Click Observer] Click on tracker (no specific element)');
      return;
    }

    // 4. Check collectible markers (works whether click-through is enabled or not)
    // This allows right-clicking collectibles even when menu is open elsewhere on screen
    const collectible = findCollectibleAt(x, y, true);
    if (collectible && button === 'right') {
      console.log(`[Click Observer] Right-click on collectible: ${collectible.name}`);
      toggleCollected(collectible);
      return; // Handled
    }

    // If no UI element hit:
    // - Click-through enabled: Click passes to game naturally
    // - Click-through disabled: Click was on empty overlay space (do nothing)
    if (isClickThroughEnabled) {
      console.log('[Click Observer] No UI hit - click passes to game');
    } else {
      console.log('[Click Observer] No UI hit - click on empty overlay (ignored)');
    }
  });
}

// Cursor polling for tooltips (overlay is always click-through)
let cursorPollingInterval = null;
let currentHoveredCollectible = null;

function findCollectibleAt(x, y, includeCollected = true) {
  /**
   * Hit-test collectibles at cursor position
   * @param {number} x - X coordinate
   * @param {number} y - Y coordinate
   * @param {boolean} includeCollected - Include collected items (default true for tooltips)
   */
  if (!currentCollectibles || currentCollectibles.length === 0) {
    return null;
  }

  for (const collectible of currentCollectibles) {
    // Skip hidden categories/sets
    const categoryName = getCategoryNameForType(collectible.t || collectible.type);
    if (categoryName && trackerState.visibilityMap[categoryName] === false) {
      continue;
    }

    // Skip collected items if explicitly excluded
    if (!includeCollected) {
      const id = getCollectibleId(collectible);
      if (trackerState.collectedItems[id]) {
        continue;
      }
    }

    const dx = x - collectible.x;
    const dy = y - collectible.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance <= COLLECTIBLE_SIZE.hitRadius) {
      return collectible;
    }
  }

  return null;
}

// Click-through toggling removed - overlay is now always click-through
// Backend observes clicks via global hooks and emits to frontend for hit-testing

function isCursorOverTooltip(x, y) {
  if (!tooltip || tooltip.style.display === 'none') {
    return false;
  }

  const rect = tooltip.getBoundingClientRect();

  return x >= rect.left &&
         x <= rect.right &&
         y >= rect.top &&
         y <= rect.bottom;
}

function isTrackerVisible() {
  const tracker = document.getElementById('cycle-tracker');
  return tracker && tracker.style.display !== 'none';
}

function isCursorOverTracker(x, y) {
  // Check header (always visible)
  const header = document.getElementById('tracker-header-clickable');
  if (header) {
    const headerRect = header.getBoundingClientRect();
    if (x >= headerRect.left && x <= headerRect.right &&
        y >= headerRect.top && y <= headerRect.bottom) {
      return true;
    }
  }

  // Check body (only if not collapsed)
  const tracker = document.getElementById('cycle-tracker');
  if (!tracker || tracker.classList.contains('collapsed')) {
    return false;
  }

  const rect = tracker.getBoundingClientRect();
  return x >= rect.left &&
         x <= rect.right &&
         y >= rect.top &&
         y <= rect.bottom;
}

function findTrackerSetHeaderAt(x, y) {
  /**
   * Hit-test tracker set/category headers
   * Returns {setName, isVisibilityToggle} or null
   */
  const tracker = document.getElementById('cycle-tracker');
  if (!tracker || tracker.classList.contains('collapsed')) {
    return null;
  }

  // Find all set headers
  const headers = tracker.querySelectorAll('.tracker-set-header');
  for (const header of headers) {
    const rect = header.getBoundingClientRect();

    // Check if click is within this header row
    if (x >= rect.left && x <= rect.right &&
        y >= rect.top && y <= rect.bottom) {

      // Find the set name from the header's text content
      const setNameEl = header.querySelector('.tracker-set-name');
      if (!setNameEl) continue;
      const setName = setNameEl.textContent.trim();

      // Check if click is on visibility toggle (eye icon column on the right)
      const eyeIcon = header.querySelector('.tracker-eye-icon');
      if (eyeIcon) {
        const eyeRect = eyeIcon.getBoundingClientRect();
        // Eye icon column should be full height of header row
        if (x >= eyeRect.left && x <= eyeRect.right) {
          return { setName, isVisibilityToggle: true };
        }
      }

      // Click is on the main row area (expand/collapse)
      return { setName, isVisibilityToggle: false };
    }
  }

  return null;
}

function findTrackerItemAt(x, y) {
  /**
   * Hit-test tracker items (collectibles within expanded sets)
   * Returns {itemId} or null
   */
  const tracker = document.getElementById('cycle-tracker');
  if (!tracker || tracker.classList.contains('collapsed')) {
    return null;
  }

  // Find all visible items in expanded sets
  const items = tracker.querySelectorAll('.tracker-item-compact');
  for (const item of items) {
    const rect = item.getBoundingClientRect();

    // Check if click is within this item row
    if (x >= rect.left && x <= rect.right &&
        y >= rect.top && y <= rect.bottom) {

      // Get item ID directly from data attribute (no longer needs parsing)
      const itemId = item.getAttribute('data-set-item');
      if (!itemId) continue;

      return { itemId };
    }
  }

  return null;
}

// Simple click-through management (same approach as video player)
let clickThroughTimeout = null;
async function setClickThrough(enabled, immediate = false) {
  if (isClickThroughEnabled === enabled) {
    // Clear any pending timeout if state matches
    if (clickThroughTimeout) {
      clearTimeout(clickThroughTimeout);
      clickThroughTimeout = null;
    }
    return; // Already in desired state
  }

  // Clear any pending timeout
  if (clickThroughTimeout) {
    clearTimeout(clickThroughTimeout);
    clickThroughTimeout = null;
  }

  // When re-enabling click-through, add a small delay to prevent rapid toggling
  // Unless immediate flag is set
  if (enabled && !immediate) {
    clickThroughTimeout = setTimeout(async () => {
      isClickThroughEnabled = true;
      await ipcRenderer.invoke('set-click-through', true);
      console.log(`[Click-Through] Enabled (delayed)`);
      clickThroughTimeout = null;
    }, 150); // 150ms delay before re-enabling
  } else {
    // Disable immediately (no delay) OR enable immediately if immediate=true
    isClickThroughEnabled = enabled;
    await ipcRenderer.invoke('set-click-through', enabled);
    console.log(`[Click-Through] ${enabled ? 'Enabled' : 'Disabled'}${immediate ? ' (immediate)' : ''}`);
  }
}

async function pollCursor() {
  /**Poll cursor position for tooltip display and click-through management*/

  if (!isRdr2Active || !overlayVisible) {
    // RDR2 not active or overlay hidden - hide tooltip and enable click-through
    if (currentHoveredCollectible) {
      currentHoveredCollectible = null;
      hideTooltip();
    }
    if (!isClickThroughEnabled) {
      await setClickThrough(true);
    }
    return;
  }

  try {
    const cursorPos = await ipcRenderer.invoke('get-cursor-position');

    // Check proximity to interactive elements
    const overTooltip = isCursorOverTooltip(cursorPos.x, cursorPos.y);
    const overTracker = isCursorOverTracker(cursorPos.x, cursorPos.y);
    const overVideoPlayer = videoPlayerFrame && videoPlayerFrame.style.display !== 'none';

    // Determine if click-through should be disabled
    // Disable when cursor is actually over interactive elements OR video player is open
    const needsInteraction = overTooltip || overTracker || overVideoPlayer;

    if (needsInteraction && isClickThroughEnabled) {
      await setClickThrough(false);
    } else if (!needsInteraction && !isClickThroughEnabled) {
      await setClickThrough(true);
    }

    // If cursor is over tooltip or tracker, don't change collectible hover state
    // But still allow tooltips to show if cursor moves from collectible to tooltip
    if (overTooltip) {
      // Cursor over tooltip - keep current tooltip visible
      return;
    }

    if (overTracker) {
      // Cursor over tracker menu - hide tooltip if showing
      if (currentHoveredCollectible) {
        currentHoveredCollectible = null;
        hideTooltip();
      }
      return;
    }

    // Check for collectible hover (not over UI elements)
    const hoveredItem = findCollectibleAt(cursorPos.x, cursorPos.y);

    // Check if hover state changed
    if (hoveredItem !== currentHoveredCollectible) {
      if (hoveredItem) {
        // Started hovering a collectible - show tooltip immediately
        currentHoveredCollectible = hoveredItem;
        showTooltip(hoveredItem);
        console.log(`[Cursor] Hovering collectible: ${hoveredItem.name} at (${hoveredItem.x}, ${hoveredItem.y})`);
      } else {
        // Stopped hovering - hide tooltip with delay
        currentHoveredCollectible = null;
        hideTooltip();
      }
    }
  } catch (error) {
    console.error('[Cursor Poll] Error:', error);
  }
}

function calculateTooltipPosition(collectibleX, collectibleY, tooltipWidth, tooltipHeight) {
  /**
   * Calculate tooltip position with corner near collectible,
   * minimizing overlap with other collectibles.
   */
  const screenWidth = 1920;
  const screenHeight = 1080;
  const offset = 6; // Small gap between tooltip corner and collectible

  console.log(`[Tooltip] Calculating position for collectible at (${collectibleX}, ${collectibleY}), tooltip size: ${tooltipWidth}x${tooltipHeight}`);

  // Try 4 positions: each corner of tooltip offset by 6px from collectible
  const candidates = [
    // Bottom-left corner offset (tooltip to the right and up)
    { x: collectibleX + offset, y: collectibleY - tooltipHeight - offset, corner: 'bottom-left' },
    // Bottom-right corner offset (tooltip to the left and up)
    { x: collectibleX - tooltipWidth - offset, y: collectibleY - tooltipHeight - offset, corner: 'bottom-right' },
    // Top-left corner offset (tooltip to the right and down)
    { x: collectibleX + offset, y: collectibleY + offset, corner: 'top-left' },
    // Top-right corner offset (tooltip to the left and down)
    { x: collectibleX - tooltipWidth - offset, y: collectibleY + offset, corner: 'top-right' }
  ];

  // Filter out positions that go off-screen
  const validCandidates = candidates.filter(pos => {
    return pos.x >= 0 &&
           pos.x + tooltipWidth <= screenWidth &&
           pos.y >= 0 &&
           pos.y + tooltipHeight <= screenHeight;
  });

  // If no valid candidates (collectible at screen edge), use fallback
  if (validCandidates.length === 0) {
    return {
      x: Math.max(0, Math.min(collectibleX, screenWidth - tooltipWidth)),
      y: Math.max(0, Math.min(collectibleY, screenHeight - tooltipHeight))
    };
  }

  // For each valid position, count how many collectibles it overlaps
  const scored = validCandidates.map(pos => {
    let overlapCount = 0;

    if (currentCollectibles) {
      for (const col of currentCollectibles) {
        // Skip the collectible we're showing tooltip for
        if (col.x === collectibleX && col.y === collectibleY) {
          continue;
        }

        // Check if collectible marker is inside tooltip bounds
        if (col.x >= pos.x &&
            col.x <= pos.x + tooltipWidth &&
            col.y >= pos.y &&
            col.y <= pos.y + tooltipHeight) {
          overlapCount++;
        }
      }
    }

    return { ...pos, overlapCount };
  });

  // Pick position with minimum overlap
  scored.sort((a, b) => a.overlapCount - b.overlapCount);

  const selected = scored[0];

  // Calculate which corner is centered on collectible
  const corners = {
    'top-left': { x: selected.x, y: selected.y },
    'top-right': { x: selected.x + tooltipWidth, y: selected.y },
    'bottom-left': { x: selected.x, y: selected.y + tooltipHeight },
    'bottom-right': { x: selected.x + tooltipWidth, y: selected.y + tooltipHeight }
  };

  // Find which corner matches collectible position
  let matchingCorner = 'NONE';
  for (const [corner, pos] of Object.entries(corners)) {
    if (pos.x === collectibleX && pos.y === collectibleY) {
      matchingCorner = corner;
      break;
    }
  }

  console.log(`[Tooltip] Selected position: (${selected.x}, ${selected.y}), corner: ${selected.corner}, overlaps: ${selected.overlapCount}`);
  console.log(`[Tooltip] Corner verification: ${matchingCorner} at (${collectibleX}, ${collectibleY})`);
  console.log(`[Tooltip] Tooltip bounds: x=${selected.x}, y=${selected.y}, width=${tooltipWidth}, height=${tooltipHeight}`);

  return { x: selected.x, y: selected.y, corner: selected.corner };
}

function startCursorPolling() {
  /**Start polling cursor at 60fps (16ms interval) for responsive click-through*/
  if (cursorPollingInterval) {
    return; // Already polling
  }

  console.log('[Cursor Poll] Starting at 60fps (16ms interval)');
  cursorPollingInterval = setInterval(pollCursor, 16);
}

function stopCursorPolling() {
  /**Stop cursor polling*/
  if (cursorPollingInterval) {
    clearInterval(cursorPollingInterval);
    cursorPollingInterval = null;
    console.log('[Cursor Poll] Stopped');
  }
}

// Initialize
async function initialize() {
  console.log('[Initialize] Starting initialization...');
  console.log('[Initialize] Backend URL:', BACKEND_URL);
  console.log('[Initialize] Initial state - overlayVisible:', overlayVisible, 'isRdr2Active:', isRdr2Active);
  updateStatus('Connecting to backend...', 'inactive');

  // Pre-render SVG sprite cache
  console.log('[Initialize] Pre-rendering SVG sprites...');
  await initializeSpriteCache();
  console.log('[Initialize] Sprite cache ready');

  // Load YouTube IFrame API for video player
  loadYouTubeAPI();

  // Create tooltip
  createTooltip();

  // Canvas is always click-through (pointer events not needed)
  // Clicks are observed by backend global hooks and emitted via WebSocket
  canvas.style.pointerEvents = 'none';

  // DON'T set canvas display here - let window-focus handler decide based on actual RDR2 state
  console.log('[Initialize] Waiting for RDR2 state from backend...');
  console.log('[Initialize] Canvas initial display value:', canvas.style.display);

  // Show status UI (but not canvas yet)
  console.log('[Initialize] Showing status bar');
  statusBar.classList.add('visible');
  // hotkeys.classList.add('visible'); // Disabled per user request

  // Connect to WebSocket (will immediately receive RDR2 state on connect)
  console.log('[Initialize] Connecting to WebSocket...');
  connectWebSocket();

  // Load all collectibles in map coordinates (once)
  console.log('[Initialize] Loading all collectibles...');
  const collectiblesLoaded = await loadAllCollectibles();
  if (!collectiblesLoaded) {
    console.error('[Initialize] Failed to load collectibles - overlay will not work');
    updateStatus('Failed to load collectibles', 'inactive');
  }

  // Update collected items display with persisted count
  updateCollectedDisplay();
  console.log(`Loaded ${Object.keys(trackerState.collectedItems).length} collected items from storage`);

  // Start cursor polling for hover detection (20fps = 50ms interval)
  startCursorPolling();

  // Start render loop (60 FPS)
  startRenderLoop();

  // Ctrl+Shift+C to clear all collected items
  window.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'C') {
      const count = Object.keys(trackerState.collectedItems).length;
      if (count > 0) {
        trackerState.collectedItems = {};
        saveTrackerState();
        updateCollectedDisplay();
        renderTrackerAll(); // Update tracker UI
        drawOverlay();
        console.log(`Cleared ${count} collected items`);
        updateStatus(`Cleared ${count} collected items`, 'active');
        setTimeout(() => {
          if (!isTracking) {
            updateStatus('Ready - Press F9 to align', 'inactive');
          }
        }, 2000);
      }
    }
  });
}

// Update status display
function updateStatus(text, state) {
  statusText.textContent = text;
  statusDot.className = 'status-dot';
  if (state === 'aligning') {
    statusDot.classList.add('aligning');
  } else if (state === 'inactive') {
    statusDot.classList.add('inactive');
  }
}

// Start alignment process - now receives collectibles data directly
async function startAlignment() {
  if (isAligning) return;
  isAligning = true;
  
  console.log('→ Starting alignment process...');
  
  try {
    // Show progress indicator
    if (alignmentProgress) {
      alignmentProgress.style.display = 'block';
      alignmentProgress.classList.add('visible');
    }
    updateStatus('Taking screenshot...', 'aligning');
    
    // Call backend to take screenshot and align
    console.log('→ Requesting backend to take screenshot and align...');
    const response = await axios.post(`${BACKEND_URL}/align-with-screenshot`);
    
    if (response.data.success) {
      // Receive viewport and transform collectibles client-side
      if (response.data.viewport) {
        currentViewport = response.data.viewport;
        currentCollectibles = transformCollectibles(currentViewport);
        console.log(`→ Alignment successful: ${currentCollectibles.length} collectibles visible`);
      }
      alignmentComplete(true, response.data);
    } else {
      throw new Error(response.data.error || 'Alignment failed');
    }
    
  } catch (error) {
    console.error('Alignment failed:', error);
    alignmentComplete(false);
  }
}

// Handle alignment completion
function alignmentComplete(success, result = null) {
  isAligning = false;
  
  console.log(`Alignment complete: ${success}`);
  
  // Hide progress indicator
  if (alignmentProgress) {
    alignmentProgress.classList.remove('visible');
    setTimeout(() => {
      alignmentProgress.style.display = 'none';
    }, 300);
  }
  
  if (success) {
    console.log('Alignment successful - rendering collectibles...');
    updateStatus(`Tracking ${currentCollectibles.length} items`, 'active');
    statusBar.classList.add('visible');
    // hotkeys.classList.add('visible'); // Disabled per user request
    overlayVisible = true;
    isTracking = true;
    
    // Update displays
    if (qualityDisplay) {
      qualityDisplay.textContent = currentCollectibles.length;
    }
    if (fpsDisplay) {
      fpsDisplay.textContent = currentFPS;
    }
    updateCollectedDisplay();
    
    // Draw the collectibles immediately
    drawOverlay();
    
  } else {
    console.error('Alignment failed');
    updateStatus('Alignment failed - Press F9 to retry', 'inactive');
    statusBar.classList.add('visible');
    // hotkeys.classList.add('visible'); // Disabled per user request
    currentCollectibles = [];
    drawOverlay();
  }
}

// Offscreen canvas for pre-rendered collectible sprites
let spriteCache = new Map(); // Cache emoji sprites by type
const SPRITE_SIZE = 48; // 48x48 pixels (30px font renders to ~48px)

// Pre-render emoji sprite to offscreen canvas (expensive operation, cached)
// Map collectible types to icon names from trackerIcons
function getIconNameForType(type) {
  const typeToIcon = {
    'arrowhead': 'arrowhead',
    'coin': 'coin',
    'heirloom': 'crown',
    'bottle': 'bottle',
    'egg': 'egg',
    'flower': 'flower',
    'card': 'tarot_card',
    'card_tarot_cups': 'tarot_card',
    'card_tarot_swords': 'tarot_card',
    'card_tarot_wands': 'tarot_card',
    'card_tarot_pentacles': 'tarot_card',
    'cups': 'tarot_card',
    'swords': 'tarot_card',
    'wands': 'tarot_card',
    'pentacles': 'tarot_card',
    'fossil': 'fossil',
    'fossils': 'fossil',
    'fossils_random': 'fossil',
    'jewelry': 'jewelry_random',
    'lost_jewelry': 'jewelry_random',
    'ring': 'ring',
    'earring': 'earring',
    'bracelet': 'bracelet',
    'necklace': 'necklace',
    'jewelry_random': 'jewelry_random',
    'random': 'random'
  };
  return typeToIcon[type] || 'random';
}

// Pre-render SVG sprite (async, called during initialization)
async function prerenderSprite(iconName, isCollected) {
  return new Promise((resolve) => {
    const offscreen = document.createElement('canvas');
    offscreen.width = SPRITE_SIZE;
    offscreen.height = SPRITE_SIZE;
    const offscreenCtx = offscreen.getContext('2d', { alpha: true });

    const svgString = trackerIcons[iconName] || trackerIcons.random;

    // Create Image from SVG
    const img = new Image();
    const svgData = svgString.replace(/width="24" height="24"/, `width="${SPRITE_SIZE}" height="${SPRITE_SIZE}"`);
    const svgDataUrl = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));

    img.onload = () => {
      // Shadow for visibility
      offscreenCtx.shadowColor = 'rgba(0, 0, 0, 0.9)';
      offscreenCtx.shadowBlur = 6;

      // Adjust alpha for collected items
      offscreenCtx.globalAlpha = isCollected ? 0.5 : 1.0;

      // Draw SVG image
      offscreenCtx.drawImage(img, 0, 0, SPRITE_SIZE, SPRITE_SIZE);

      // Reset alpha
      offscreenCtx.globalAlpha = 1.0;

      resolve(offscreen);
    };

    img.onerror = () => {
      console.error(`Failed to load SVG icon: ${iconName}`);
      resolve(offscreen); // Return blank canvas on error
    };

    img.src = svgDataUrl;
  });
}

// Initialize sprite cache with all icons (called on page load)
async function initializeSpriteCache() {
  const uniqueIcons = [...new Set(Object.values(getIconNameForType))];
  const promises = [];

  for (const iconName of Object.keys(trackerIcons)) {
    // Pre-render both normal and collected states
    promises.push(
      prerenderSprite(iconName, false).then(sprite => {
        spriteCache.set(`icon_${iconName}_normal`, sprite);
      })
    );
    promises.push(
      prerenderSprite(iconName, true).then(sprite => {
        spriteCache.set(`icon_${iconName}_collected`, sprite);
      })
    );
  }

  await Promise.all(promises);
  console.log(`[Sprite Cache] Pre-rendered ${promises.length} SVG sprites`);
}

function getCollectibleSprite(type, isCollected) {
  const iconName = getIconNameForType(type);
  const cacheKey = `icon_${iconName}_${isCollected ? 'collected' : 'normal'}`;

  // Return cached sprite (should always be available after initialization)
  if (spriteCache.has(cacheKey)) {
    return spriteCache.get(cacheKey);
  }

  // Fallback: create a blank sprite if somehow not cached
  console.warn(`[Sprite Cache] Missing sprite for ${cacheKey}, using fallback`);
  const offscreen = document.createElement('canvas');
  offscreen.width = SPRITE_SIZE;
  offscreen.height = SPRITE_SIZE;
  return offscreen;
}

// Optimized draw function using sprite caching
function drawOverlay() {
  // Clear canvas (fast operation)
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!overlayVisible) {
    return;
  }

  // Draw a subtle indicator that overlay is active even with no collectibles
  if (currentCollectibles.length === 0 && isTracking) {
    ctx.save();
    ctx.globalAlpha = 0.3;
    ctx.fillStyle = '#fbbf24';
    ctx.font = '10px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('Overlay Active - No items in view', 10, canvas.height - 10);
    ctx.restore();
    return;
  }

  // Set global opacity (applied to all sprites)
  ctx.globalAlpha = overlayOpacity;

  // Batch draw all collectibles using cached sprites (FAST)
  let drawnCount = 0;

  // Optimization: Disable shadow for batch drawing (sprites already have shadows)
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;

  for (const col of currentCollectibles) {
    // Map shortened field names from backend
    const type = col.t || col.type;

    // Check if this category/set is hidden in tracker
    const categoryName = getCategoryNameForType(type);
    if (categoryName && trackerState.visibilityMap[categoryName] === false) {
      continue; // Skip hidden categories
    }

    const isCollected = trackerState.collectedItems[getCollectibleId(col)];

    // Ensure coordinates are valid
    if (typeof col.x !== 'number' || typeof col.y !== 'number' ||
        col.x < 0 || col.y < 0 || col.x > canvas.width || col.y > canvas.height) {
      continue;
    }

    // Get pre-rendered sprite (cached, no rendering cost)
    const sprite = getCollectibleSprite(type, isCollected);

    // Draw sprite to main canvas (FAST: single bitmap copy)
    // Center sprite on collectible position
    const drawX = col.x - SPRITE_SIZE / 2;
    const drawY = col.y - SPRITE_SIZE / 2;

    // Use drawImage for hardware-accelerated blit
    ctx.drawImage(sprite, drawX, drawY);

    drawnCount++;
  }

  // Reset opacity
  ctx.globalAlpha = 1.0;
}

// Refresh data
async function refreshData() {
  try {
    updateStatus('Refreshing data...', 'aligning');
    const response = await axios.post(`${BACKEND_URL}/refresh-data`);
    
    if (response.data.success) {
      updateStatus('Ready - Press F9 to align', 'inactive');
      currentCollectibles = [];
      // Don't clear collected items on refresh - they persist
      updateCollectedDisplay();
      isTracking = false;
      drawOverlay();
    } else {
      updateStatus('Refresh failed', 'inactive');
    }
  } catch (error) {
    console.error('Data refresh failed:', error.message);
    updateStatus('Refresh failed', 'inactive');
  }
}

// IPC event handlers
ipcRenderer.on('start-alignment', async () => {
  // F9 resets tracking state and forces full cascade AKAZE alignment
  console.log('F9 pressed - resetting tracker and forcing full alignment');
  currentCollectibles = [];
  isTracking = false;
  updateStatus('Resetting tracker...', 'aligning');

  try {
    // Reset cascade matcher state to force full AKAZE on next frame
    await axios.post(`${BACKEND_URL}/reset-tracking`);
    console.log('Tracker reset - next frame will use full cascade AKAZE');
    updateStatus('Waiting for next frame...', 'aligning');
  } catch (error) {
    console.error('Failed to reset tracker:', error);
    updateStatus('Reset failed - retrying...', 'inactive');
  }

  pollLatestMatch(); // Force immediate poll
});

ipcRenderer.on('show-overlay', () => {
  overlayVisible = true;
  drawOverlay();
  // Only show UI elements if RDR2 is actually active
  if (isRdr2Active) {
    canvas.style.display = 'block';
    statusBar.classList.add('visible');
    // hotkeys.classList.add('visible'); // Disabled per user request
  }
});

ipcRenderer.on('hide-overlay', () => {
  overlayVisible = false;
  canvas.style.display = 'none';
  drawOverlay();
  statusBar.classList.remove('visible');
  // hotkeys.classList.remove('visible'); // Disabled per user request
});

ipcRenderer.on('set-opacity', (event, opacity) => {
  overlayOpacity = opacity;
  drawOverlay();
});

ipcRenderer.on('refresh-data', () => {
  refreshData();
});

ipcRenderer.on('toggle-tracker', () => {
  const tracker = document.getElementById('cycle-tracker');
  if (!tracker) return;

  if (tracker.classList.contains('collapsed')) {
    // Expanding - remove hidden first, then remove collapsed to trigger animation
    tracker.classList.remove('hidden');
    tracker.offsetHeight; // Force reflow
    tracker.classList.remove('collapsed');
  } else {
    // Collapsing - add collapsed to trigger animation
    tracker.classList.add('collapsed');
    // Add hidden class after animation completes (300ms)
    setTimeout(() => {
      if (tracker.classList.contains('collapsed')) {
        tracker.classList.add('hidden');
      }
    }, 300);
  }
});

// Cycle timer widget
function updateCycleTimerWidget() {
  const now = new Date();
  const utcNow = new Date(now.getTime() + now.getTimezoneOffset() * 60000);

  const tomorrow = new Date(utcNow);
  tomorrow.setUTCHours(24, 0, 0, 0);

  const diff = tomorrow - utcNow;

  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  const timeString = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// ===== CYCLE TRACKER =====

// Tracker state
const trackerState = {
  expandedSets: {},
  visibilityMap: {},
  collectedItems: {},
  cycleData: null,
  itemsData: null,
  activeTab: 'guaranteed',
  lastRefreshTime: null
};

// Load persisted state
function loadTrackerPersistedState() {
  try {
    const saved = localStorage.getItem('cycleTrackerState');
    if (saved) {
      const parsed = JSON.parse(saved);
      trackerState.collectedItems = parsed.collectedItems || {};
      trackerState.visibilityMap = parsed.visibilityMap || {};
      // Don't load expandedSets - start all collapsed by default
      trackerState.expandedSets = {};
    }

    // Migrate legacy collected items from old Set-based storage
    loadCollectedItems();
  } catch (e) {
    console.error('[Tracker] Failed to load persisted state:', e);
  }
}

// Save state
function saveTrackerState() {
  try {
    localStorage.setItem('cycleTrackerState', JSON.stringify({
      collectedItems: trackerState.collectedItems,
      visibilityMap: trackerState.visibilityMap
      // Don't persist expandedSets - always start collapsed
    }));
  } catch (e) {
    console.error('[Tracker] Failed to save state:', e);
  }
}

// Countdown timer to 00:00 UTC
function updateTrackerTimer() {
  const now = new Date();
  const utcNow = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
  const tomorrow = new Date(utcNow);
  tomorrow.setUTCHours(24, 0, 0, 0);
  const diff = tomorrow - utcNow;

  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  const timeString = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  document.getElementById('tracker-timer').textContent = timeString;

  // Check if cycle just changed (00:00:00)
  if (hours === 0 && minutes === 0 && seconds === 0) {
    const today = utcNow.toISOString().split('T')[0];
    if (trackerState.lastRefreshTime !== today) {
      console.log('[Tracker] Cycle changed! Refreshing data...');
      trackerState.lastRefreshTime = today;
      loadTrackerData();
      // Also trigger backend refresh
      fetch(`http://localhost:${backendPort}/refresh-data`, { method: 'POST' })
        .then(res => res.json())
        .then(data => console.log('[Tracker] Backend data refreshed:', data))
        .catch(err => console.error('[Tracker] Failed to refresh backend:', err));
    }
  }
}

// Smart name shortening
function shortenItemName(rawName, category) {
  let name = rawName.toLowerCase(); // Normalize to lowercase first

  // Remove common prefixes
  name = name
    .replace(/^(document_card_|provision_|consumable_)/, '')
    .replace(/^(hrlm_|egg_)/, '');

  if (name.includes('_random_')) {
    const match = name.match(/_random_(\d+)/);
    if (match) return `#${match[1]}`;
  }

  if (['cups', 'swords', 'wands', 'pentacles'].includes(category)) {
    name = name.replace(/_(cups|swords|wands|pentacles)$/, '');
  }

  if (category === 'egg') {
    name = name.replace(/_egg(_\d+)?$/, '');
  }

  if (category === 'flower') {
    // Remove all flower-related prefixes and suffixes
    name = name
      .replace(/^american_wild_flower_/, '')
      .replace(/^wild_flower_/, '')
      .replace(/^wldflwr_/, '')
      .replace(/wldflwr_?/g, '')  // Remove "wldflwr" anywhere with optional underscore
      .replace(/_flower$/, '')
      .replace(/_blossom$/, '');
  }

  if (category === 'heirlooms') {
    name = name
      .replace(/^(brush_|comb_|hairpin_)/, '')
      .replace(/_brush$/, ' Br.')
      .replace(/_comb$/, ' Cb.')
      .replace(/_hairpin$/, ' Pin');
  }

  if (['ring', 'earring', 'bracelet', 'necklace', 'jewelry_random'].includes(category)) {
    name = name
      .replace(/^jewelry_/, '')
      .replace(/_(ring|earring|bracelet|necklace)$/, '');
  }

  // Capitalize words after all replacements
  name = name.replace(/_/g, ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  return name;
}

// Load real data from Joan Ropke API
async function loadTrackerData() {
  try {
    const [cyclesResponse, itemsResponse] = await Promise.all([
      fetch('https://jeanropke.github.io/RDR2CollectorsMap/data/cycles.json'),
      fetch('https://jeanropke.github.io/RDR2CollectorsMap/data/items.json')
    ]);

    const cyclesData = await cyclesResponse.json();
    const itemsData = await itemsResponse.json();

    const now = new Date();
    const utcNow = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    const today = utcNow.toISOString().split('T')[0];

    const todayCycles = cyclesData.find(entry => entry.date === today);

    if (!todayCycles) {
      console.error('[Tracker] No cycle data for today:', today);
      document.getElementById('tracker-content').innerHTML = '<div class="tracker-loading">No cycle data available for today</div>';
      return null;
    }

    trackerState.cycleData = todayCycles;
    trackerState.itemsData = itemsData;
    trackerState.lastRefreshTime = today;

    renderTrackerAll();
    return { cycles: todayCycles, items: itemsData };
  } catch (error) {
    console.error('[Tracker] Failed to load real data:', error);
    document.getElementById('tracker-content').innerHTML = '<div class="tracker-loading">Failed to load cycle data</div>';
    return null;
  }
}

// Helper to get icon HTML from icon name
function getTrackerIcon(iconName) {
  return trackerIcons[iconName] || trackerIcons.random;
}

// SVG Icon Library - 24x24 optimized for tracker display
const trackerIcons = {
  tarot_card: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="32" y="16" width="64" height="96" rx="4" fill="#2c1810" stroke="#8b6914" stroke-width="2"/><rect x="38" y="22" width="52" height="84" rx="2" fill="none" stroke="#d4af37" stroke-width="1"/><circle cx="64" cy="50" r="12" fill="#ffd700"/><g transform="translate(64,50)"><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(0)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(45)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(90)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(135)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(180)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(225)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(270)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(315)"/></g><path d="M54,85 L64,75 L74,85 L64,95 Z" fill="#d4af37"/></svg>`,

  egg: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="70" rx="32" ry="42" fill="#f4e4d1" stroke="#8b7355" stroke-width="2"/><ellipse cx="56" cy="50" rx="12" ry="16" fill="#fff" opacity="0.6"/><path d="M40,70 Q64,65 88,70" stroke="#d4a574" stroke-width="1.5" fill="none"/><path d="M40,80 Q64,75 88,80" stroke="#d4a574" stroke-width="1.5" fill="none"/></svg>`,

  bottle: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="58" y="20" width="12" height="16" rx="2" fill="#8b6b47" stroke="#654321" stroke-width="1"/><rect x="60" y="36" width="8" height="20" fill="#2a4d3a" stroke="#1a3d2a" stroke-width="1"/><path d="M52,56 L52,95 Q52,105 64,105 Q76,105 76,95 L76,56 Z" fill="#2a4d3a" stroke="#1a3d2a" stroke-width="2"/><rect x="56" y="70" width="16" height="20" rx="2" fill="#e8dcc6" opacity="0.8"/><path d="M56,85 L56,95 Q56,101 64,101 Q72,101 72,95 L72,85 Z" fill="#8b0000" opacity="0.6"/><rect x="58" y="60" width="4" height="12" rx="2" fill="#fff" opacity="0.4"/></svg>`,

  flower: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M64,90 L64,110" stroke="#228b22" stroke-width="3" fill="none"/><ellipse cx="54" cy="95" rx="8" ry="4" fill="#228b22" transform="rotate(-30 54 95)"/><ellipse cx="74" cy="100" rx="8" ry="4" fill="#228b22" transform="rotate(30 74 100)"/><g transform="translate(64,60)"><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(0)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(72)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(144)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(216)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(288)"/></g><circle cx="64" cy="60" r="12" fill="#ffd700"/><circle cx="64" cy="60" r="8" fill="#ff8c00"/></svg>`,

  crown: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="30" y="70" width="68" height="20" rx="2" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M30,70 L40,40 L50,60 L64,35 L78,60 L88,40 L98,70" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><circle cx="64" cy="80" r="5" fill="#ff0000"/><circle cx="48" cy="80" r="4" fill="#0000ff"/><circle cx="80" cy="80" r="4" fill="#0000ff"/><circle cx="40" cy="40" r="3" fill="#00ff00"/><circle cx="64" cy="35" r="3" fill="#00ff00"/><circle cx="88" cy="40" r="3" fill="#00ff00"/></svg>`,

  arrowhead: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M64,25 L45,65 L55,65 L64,95 L73,65 L83,65 Z" fill="#696969" stroke="#2c2c2c" stroke-width="2"/><line x1="55" y1="45" x2="60" y2="50" stroke="#4a4a4a" stroke-width="1"/><line x1="68" y1="45" x2="73" y2="50" stroke="#4a4a4a" stroke-width="1"/><line x1="60" y1="70" x2="64" y2="75" stroke="#4a4a4a" stroke-width="1"/><line x1="64" y1="75" x2="68" y2="70" stroke="#4a4a4a" stroke-width="1"/><path d="M64,30 L50,55 L57,55 L64,35" fill="#8a8a8a" opacity="0.6"/></svg>`,

  coin: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><circle cx="64" cy="64" r="38" fill="#ffd700" stroke="#b8860b" stroke-width="3"/><circle cx="64" cy="64" r="32" fill="none" stroke="#b8860b" stroke-width="1"/><text x="64" y="75" font-family="Arial, serif" font-size="36" font-weight="bold" text-anchor="middle" fill="#b8860b">$</text><text x="64" y="40" font-family="Arial" font-size="12" text-anchor="middle" fill="#b8860b">★</text><text x="64" y="95" font-family="Arial" font-size="12" text-anchor="middle" fill="#b8860b">★</text><ellipse cx="52" cy="50" rx="8" ry="12" fill="#fff" opacity="0.3"/></svg>`,

  fossil: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="40" ry="38" fill="#8b7355" stroke="#654321" stroke-width="2"/><path d="M64,64 Q70,64 70,58 Q70,52 62,52 Q54,52 54,60 Q54,68 64,68 Q74,68 74,58 Q74,48 60,48 Q46,48 46,62 Q46,76 64,76" stroke="#4a3c2a" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="40" y1="50" x2="45" y2="55" stroke="#6a5444" stroke-width="1"/><line x1="83" y1="50" x2="88" y2="55" stroke="#6a5444" stroke-width="1"/><line x1="40" y1="73" x2="45" y2="78" stroke="#6a5444" stroke-width="1"/><line x1="83" y1="73" x2="88" y2="78" stroke="#6a5444" stroke-width="1"/></svg>`,

  ring: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="28" ry="34" fill="none" stroke="#ffd700" stroke-width="8"/><ellipse cx="64" cy="64" rx="28" ry="34" fill="none" stroke="#b8860b" stroke-width="6"/><rect x="54" y="24" width="20" height="20" rx="2" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M64,28 L72,34 L64,40 L56,34 Z" fill="#87ceeb" stroke="#4682b4" stroke-width="1"/><path d="M56,34 L72,34" stroke="#4682b4" stroke-width="0.5"/><path d="M58,30 L64,28 L62,34" fill="#fff" opacity="0.7"/></svg>`,

  earring: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><g transform="translate(45, 50)"><path d="M0,0 Q0,-10 8,-10" stroke="#c0c0c0" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="0" y1="0" x2="0" y2="15" stroke="#c0c0c0" stroke-width="1"/><circle cx="0" cy="20" r="8" fill="#fffaf0" stroke="#d3d3d3" stroke-width="1"/><circle cx="-2" cy="18" r="3" fill="#fff" opacity="0.6"/></g><g transform="translate(83, 50)"><path d="M0,0 Q0,-10 -8,-10" stroke="#c0c0c0" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="0" y1="0" x2="0" y2="15" stroke="#c0c0c0" stroke-width="1"/><circle cx="0" cy="20" r="8" fill="#fffaf0" stroke="#d3d3d3" stroke-width="1"/><circle cx="-2" cy="18" r="3" fill="#fff" opacity="0.6"/></g></svg>`,

  bracelet: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="35" ry="28" fill="none" stroke="#ffd700" stroke-width="6"/><ellipse cx="64" cy="64" rx="35" ry="28" fill="none" stroke="#b8860b" stroke-width="4"/><g opacity="0.6"><path d="M30,64 Q35,60 40,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M40,64 Q45,68 50,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M50,64 Q55,60 60,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M60,64 Q65,68 70,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M70,64 Q75,60 80,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M80,64 Q85,68 90,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M90,64 Q95,60 98,64" stroke="#8b6914" stroke-width="2" fill="none"/></g><circle cx="64" cy="38" r="5" fill="#ff69b4" stroke="#c71585" stroke-width="1"/></svg>`,

  necklace: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M30,35 Q64,50 98,35 L98,40 Q64,55 30,40 Z" fill="none" stroke="#ffd700" stroke-width="3"/><path d="M30,35 Q64,50 98,35" fill="none" stroke="#b8860b" stroke-width="2"/><line x1="64" y1="50" x2="64" y2="70" stroke="#ffd700" stroke-width="2"/><g transform="translate(64, 80)"><path d="M0,-12 L8,0 L0,12 L-8,0 Z" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M0,-8 L5,0 L0,8 L-5,0 Z" fill="#dc143c" stroke="#8b0000" stroke-width="1"/><path d="M-3,-4 L0,-8 L0,-2" fill="#ff6b6b" opacity="0.7"/></g></svg>`,

  jewelry_random: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="32" y="32" width="64" height="64" rx="8" fill="#4a4a4a" stroke="#2a2a2a" stroke-width="2"/><g stroke="#ffd700" fill="#ffd700"><path d="M25,25 L28,28 L25,31 L22,28 Z"/><path d="M103,25 L106,28 L103,31 L100,28 Z"/><path d="M25,97 L28,100 L25,103 L22,100 Z"/><path d="M103,97 L106,100 L103,103 L100,100 Z"/></g><text x="64" y="75" font-family="Arial" font-size="48" font-weight="bold" text-anchor="middle" fill="#ffd700">?</text><g opacity="0.3" fill="#ffd700"><circle cx="45" cy="45" r="3"/><ellipse cx="83" cy="45" rx="4" ry="2"/><path d="M45,80 L48,83 L45,86 L42,83 Z"/><circle cx="83" cy="83" r="2"/></g></svg>`,

  random: `<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="28" y="28" width="72" height="72" rx="8" fill="#fff" stroke="#333" stroke-width="3"/><g fill="#333"><circle cx="48" cy="48" r="6"/><circle cx="80" cy="48" r="6"/><circle cx="48" cy="80" r="6"/><circle cx="80" cy="80" r="6"/><circle cx="64" cy="64" r="6"/><circle cx="48" cy="64" r="6"/><circle cx="80" cy="64" r="6"/></g></svg>`
};

// Parse real data into organized sets
function parseTrackerData() {
  if (!trackerState.cycleData || !trackerState.itemsData) return null;

  const sets = [];
  const randomCategories = [];

  const categoryConfig = {
    // Guaranteed sets (tarot cards) - all use card icon
    'cups': { icon: 'tarot_card', name: 'Cups', type: 'guaranteed' },
    'swords': { icon: 'tarot_card', name: 'Swords', type: 'guaranteed' },
    'wands': { icon: 'tarot_card', name: 'Wands', type: 'guaranteed' },
    'pentacles': { icon: 'tarot_card', name: 'Pentacles', type: 'guaranteed' },

    // Guaranteed sets (other) - category-specific icons
    'egg': { icon: 'egg', name: 'Eggs', type: 'guaranteed' },
    'bottle': { icon: 'bottle', name: 'Bottles', type: 'guaranteed' },
    'flower': { icon: 'flower', name: 'Flowers', type: 'guaranteed' },
    'heirlooms': { icon: 'crown', name: 'Heirlooms', type: 'guaranteed' },

    // Random collectibles - category-specific icons
    'arrowhead': { icon: 'arrowhead', name: 'Arrowheads', type: 'random' },
    'coin': { icon: 'coin', name: 'Coins', type: 'random' },
    'fossils_random': { icon: 'fossil', name: 'Random Fossils', type: 'random' },

    // Random jewelry - distinct descriptive icons
    'ring': { icon: 'ring', name: 'Rings', type: 'random', cycleKey: 'lost_jewelry' },
    'earring': { icon: 'earring', name: 'Earrings', type: 'random', cycleKey: 'lost_jewelry' },
    'bracelet': { icon: 'bracelet', name: 'Bracelets', type: 'random', cycleKey: 'lost_jewelry' },
    'necklace': { icon: 'necklace', name: 'Necklaces', type: 'random', cycleKey: 'lost_jewelry' },
    'jewelry_random': { icon: 'jewelry_random', name: 'Random Jewelry', type: 'random', cycleKey: 'lost_jewelry' },

    // Random spawn spots (mounds, chests, shallow digs)
    // Shows spawn locations that give random collectibles - trackable to mark visited
    'random': { icon: 'random', name: 'Random Spots', type: 'random' }
  };

  // Process configured categories
  for (const [category, config] of Object.entries(categoryConfig)) {
    // Use cycleKey if specified (for jewelry subcategories), otherwise use category name
    const cycleKey = config.cycleKey || category;
    const cycleNum = trackerState.cycleData[cycleKey];
    if (!cycleNum) {
      console.log(`[Tracker] No cycle data for ${category} (cycleKey: ${cycleKey})`);
      continue;
    }

    const categoryItems = trackerState.itemsData[category];
    if (!categoryItems) {
      console.log(`[Tracker] No item data for category: ${category}`);
      continue;
    }

    const cycleItems = categoryItems[String(cycleNum)];
    if (!cycleItems || !Array.isArray(cycleItems)) {
      console.log(`[Tracker] No items for ${category} cycle ${cycleNum}`);
      continue;
    }

    console.log(`[Tracker] Loading ${category}: ${cycleItems.length} items in cycle ${cycleNum}`);

    const isRandom = cycleItems.some(item => item.text && item.text.includes('_random_'));

    const items = cycleItems.map((item) => {
      const rawName = item.text || 'Unknown';
      const readableName = shortenItemName(rawName, category);
      return { id: rawName, name: readableName, collected: false };
    });

    if (isRandom || config.type === 'random') {
      randomCategories.push({
        icon: config.icon,
        name: config.name,
        category: category,
        total: items.length,
        collected: 0,
        visible: true,
        items: items
      });
    } else {
      sets.push({
        icon: config.icon,
        name: config.name,
        category: category,
        total: items.length,
        collected: 0,
        visible: true,
        items: items
      });
    }
  }

  // Catch any unconfigured categories from itemsData
  if (trackerState.itemsData) {
    for (const [category, categoryData] of Object.entries(trackerState.itemsData)) {
      // Skip if already processed
      if (categoryConfig[category]) continue;

      // Try to find cycle data
      const cycleNum = trackerState.cycleData[category];
      if (!cycleNum) continue;

      const cycleItems = categoryData[String(cycleNum)];
      if (!cycleItems || !Array.isArray(cycleItems)) continue;

      const items = cycleItems.map((item) => {
        const rawName = item.text || 'Unknown';
        const readableName = shortenItemName(rawName, category);
        return { id: rawName, name: readableName, collected: false };
      });

      // Add as random category with default config
      randomCategories.push({
        icon: 'random',  // Use random icon for unknown types
        name: category.charAt(0).toUpperCase() + category.slice(1),  // Capitalize first letter
        category: category,
        total: items.length,
        collected: 0,
        visible: true,
        items: items
      });

      console.log(`[Tracker] Found unconfigured category: ${category} with ${items.length} items`);
    }
  }

  return { sets, randomCategories };
}

// Helper to map collectible type to tracker category name
function getCategoryNameForType(type) {
  // Map API types to category keys (matching categoryConfig keys in parseTrackerData)
  const typeToCategory = {
    'arrowhead': 'arrowhead',
    'coin': 'coin',
    'heirloom': 'heirlooms',
    'bottle': 'bottle',
    'egg': 'egg',
    'flower': 'flower',
    'card': 'cups',  // Generic card type maps to cups (will be overridden by specific suit)
    'card_tarot_cups': 'cups',
    'card_tarot_swords': 'swords',
    'card_tarot_wands': 'wands',
    'card_tarot_pentacles': 'pentacles',
    'cups': 'cups',
    'swords': 'swords',
    'wands': 'wands',
    'pentacles': 'pentacles',
    'fossil': 'fossils_random',
    'fossils': 'fossils_random',
    'fossils_random': 'fossils_random',
    'jewelry': 'jewelry_random',
    'lost_jewelry': 'jewelry_random',
    'ring': 'ring',
    'earring': 'earring',
    'bracelet': 'bracelet',
    'necklace': 'necklace',
    'jewelry_random': 'jewelry_random',
    'random': 'random'
  };
  return typeToCategory[type] || type;  // Fallback to type itself if not mapped
}

// Toggle functions - accordion style (only one open at a time)
function toggleTrackerSet(setName) {
  const wasExpanded = trackerState.expandedSets[setName];

  // Close all sets first (accordion behavior)
  trackerState.expandedSets = {};

  // If this set wasn't expanded, expand it
  if (!wasExpanded) {
    trackerState.expandedSets[setName] = true;
  }

  saveTrackerState();
  renderTrackerAll();
}

function toggleTrackerVisibility(setName) {
  trackerState.visibilityMap[setName] = !trackerState.visibilityMap[setName];
  saveTrackerState();
  renderTrackerAll();
  drawOverlay(); // Redraw map to show/hide collectibles
  console.log(`[Tracker] Visibility toggled for ${setName}: ${trackerState.visibilityMap[setName] !== false}`);
}

function toggleTrackerCollected(itemId) {
  trackerState.collectedItems[itemId] = !trackerState.collectedItems[itemId];
  console.log(`[Tracker] Toggled ${itemId}: ${trackerState.collectedItems[itemId] ? 'collected' : 'not collected'}`);
  saveTrackerState();
  updateCollectedDisplay();
  renderTrackerAll();
  drawOverlay(); // Force redraw to update collectible visual state on map
}

// Render guaranteed sets
function renderTrackerGuaranteedSets(data) {
  if (!data || !data.sets) return '<div class="tracker-loading">No data available</div>';

  return data.sets.map(set => {
    const isExpanded = trackerState.expandedSets[set.name];
    const isVisible = trackerState.visibilityMap[set.name] !== false;
    const expandIcon = isExpanded ? '▼' : '▽';

    let collectedCount = 0;
    set.items.forEach(item => {
      if (trackerState.collectedItems[item.id]) collectedCount++;
    });

    const isComplete = collectedCount === set.total;

    let itemsHTML = '';
    if (isExpanded) {
      itemsHTML = `
        <div class="tracker-items-list expanded">
          ${set.items.map(item => {
            const isCollected = trackerState.collectedItems[item.id];
            return `
              <div class="tracker-item-compact" data-set-item="${item.id}">
                <span class="tracker-item-checkbox ${isCollected ? 'collected' : ''}">
                  ${isCollected ? '✓' : '○'}
                </span>
                <span class="tracker-item-name ${isCollected ? 'collected' : ''}" title="${item.name}">
                  ${item.name}
                </span>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    return `
      <div class="tracker-set-item">
        <div class="tracker-set-header">
          <span class="tracker-expand-icon">${expandIcon}</span>
          <span class="tracker-set-emoji">${getTrackerIcon(set.icon)}</span>
          <span class="tracker-set-progress">${collectedCount}/${set.total}</span>
          <span class="tracker-set-name ${isComplete ? 'complete' : ''}">${set.name}</span>
          <span class="tracker-eye-icon ${isVisible ? 'visible' : 'hidden'}">
            ${isVisible ? '👁️' : '👁️‍🗨️'}
          </span>
        </div>
        ${itemsHTML}
      </div>
    `;
  }).join('');
}

// Render random categories
function renderTrackerRandomCategories(data) {
  if (!data || !data.randomCategories) return '<div class="tracker-loading">No data available</div>';

  return data.randomCategories.map(cat => {
    const isExpanded = trackerState.expandedSets[cat.name];
    const isVisible = trackerState.visibilityMap[cat.name] !== false;
    const expandIcon = isExpanded ? '▼' : '▽';

    let collectedCount = 0;
    cat.items.forEach(item => {
      if (trackerState.collectedItems[item.id]) collectedCount++;
    });

    let itemsHTML = '';
    if (isExpanded) {
      itemsHTML = `
        <div class="tracker-items-list expanded">
          ${cat.items.map(item => {
            const isCollected = trackerState.collectedItems[item.id];
            return `
              <div class="tracker-item-compact" data-set-item="${item.id}">
                <span class="tracker-item-checkbox ${isCollected ? 'collected' : ''}">
                  ${isCollected ? '✓' : '○'}
                </span>
                <span class="tracker-item-name ${isCollected ? 'collected' : ''}" title="${item.name}">
                  ${item.name}
                </span>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    return `
      <div class="tracker-set-item">
        <div class="tracker-set-header">
          <span class="tracker-expand-icon">${expandIcon}</span>
          <span class="tracker-set-emoji">${getTrackerIcon(cat.icon)}</span>
          <span class="tracker-set-progress">${collectedCount}/${cat.total}</span>
          <span class="tracker-set-name">${cat.name}</span>
          <span class="tracker-eye-icon ${isVisible ? 'visible' : 'hidden'}">
            ${isVisible ? '👁️' : '👁️‍🗨️'}
          </span>
        </div>
        ${itemsHTML}
      </div>
    `;
  }).join('');
}

// Render all
function renderTrackerAll() {
  const data = parseTrackerData();
  if (!data) return;

  const content = document.getElementById('tracker-content');

  if (trackerState.activeTab === 'guaranteed') {
    content.innerHTML = renderTrackerGuaranteedSets(data);
  } else if (trackerState.activeTab === 'random') {
    content.innerHTML = renderTrackerRandomCategories(data);
  }

  // Update footer
  const totalItems = data.sets.reduce((sum, set) => sum + set.total, 0) +
                    data.randomCategories.reduce((sum, cat) => sum + cat.total, 0);
  let totalCollected = 0;

  data.sets.forEach(set => {
    set.items.forEach(item => {
      const key = `${set.name}-${item.id}`;
      if (trackerState.collectedItems[key]) totalCollected++;
    });
  });

  data.randomCategories.forEach(cat => {
    cat.items.forEach(item => {
      const key = `${cat.name}-${item.id}`;
      if (trackerState.collectedItems[key]) totalCollected++;
    });
  });

  // Update footer progress
  const footerProgress = document.getElementById('tracker-footer-progress');
  if (footerProgress) {
    footerProgress.textContent = `${totalCollected}/${totalItems} (${Math.round(totalCollected/totalItems*100)}%)`;
  }
}

// Tab switching
document.querySelectorAll('.tracker-tab').forEach(tab => {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.tracker-tab').forEach(t => t.classList.remove('active'));
    this.classList.add('active');
    trackerState.activeTab = this.dataset.tab;
    renderTrackerAll();
  });
});

// Header click to toggle collapse/expand with animation
document.getElementById('tracker-header-clickable').addEventListener('click', () => {
  const tracker = document.getElementById('cycle-tracker');
  if (!tracker) return;

  if (tracker.classList.contains('collapsed')) {
    // Expanding - remove hidden first, then remove collapsed to trigger animation
    tracker.classList.remove('hidden');
    tracker.offsetHeight; // Force reflow
    tracker.classList.remove('collapsed');
  } else {
    // Collapsing - add collapsed to trigger animation
    tracker.classList.add('collapsed');
    // Add hidden class after animation completes (300ms)
    setTimeout(() => {
      if (tracker.classList.contains('collapsed')) {
        tracker.classList.add('hidden');
      }
    }, 300);
  }
});

// Initialize tracker
loadTrackerPersistedState();
setInterval(updateTrackerTimer, 1000);
updateTrackerTimer();
loadTrackerData();

// Initialization is handled by async function at the top after getting backend port