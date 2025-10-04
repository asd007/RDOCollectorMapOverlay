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
let currentCollectibles = [];
let currentFPS = 5; // Now using continuous capture at 5fps
let collectedItems = loadCollectedItems(); // Track collected items (persisted)
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
  'cups': { r: 234, g: 179, b: 8 },
  'wands': { r: 168, g: 85, b: 247 },
  'fossils': { r: 34, g: 197, b: 94 }
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
  'cups': '🏆',          // Gold trophy
  'wands': '⭐',         // Yellow star
  'fossils': '🦴'        // White bone
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
    background: rgba(0, 0, 0, 0.95);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(217, 119, 6, 0.7);
    border-radius: 8px;
    padding: 18px;
    color: white;
    font-size: 18px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    max-width: 450px;
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

  const name = collectible.name || 'Unknown';
  const type = collectible.type || 'unknown';
  const helpText = collectible.help || '';
  const videoLink = collectible.video || '';

  let tooltipHTML = `
    <div style="font-weight: bold; color: #fbbf24; margin-bottom: 9px; font-size: 20px;">${name}</div>
    <div style="font-size: 15px; color: #9ca3af; margin-bottom: 6px;">Type: ${type}</div>
  `;

  if (helpText) {
    tooltipHTML += `<div style="margin-bottom: 9px; font-size: 16px; line-height: 1.4;">${helpText}</div>`;
  }

  if (videoLink) {
    tooltipHTML += `<div style="margin-bottom: 12px; display: flex; justify-content: center;">
      <div class="tooltip-video-link" data-video-url="${videoLink}" data-collectible-name="${name.replace(/"/g, '&quot;')}" style="width: 64px; height: 64px; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 12px rgba(0,0,0,0.4); user-select: none;">
        <span style="font-size: 32px; margin-left: 4px;">▶</span>
      </div>
    </div>`;
  }

  // Add collection status
  const isCollected = collectedItems.has(getCollectibleId(collectible));
  tooltipHTML += `<div style="font-size: 15px; color: ${isCollected ? '#22c55e' : '#ef4444'}; margin-top: 6px;">
    ${isCollected ? '✓ Collected' : '⚫ Not Collected'}
  </div>`;

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

// Get unique ID for collectible using stable lat/lng coordinates
function getCollectibleId(collectible) {
  // Use lat/lng as stable identifier (rounded to avoid floating point issues)
  const lat = collectible.lat ? collectible.lat.toFixed(4) : '0';
  const lng = collectible.lng ? collectible.lng.toFixed(4) : '0';
  return `${collectible.type}-${lat}-${lng}`;
}

// Load collected items from localStorage
function loadCollectedItems() {
  try {
    const saved = localStorage.getItem('rdo-collected-items');
    if (saved) {
      const items = JSON.parse(saved);
      return new Set(items);
    }
  } catch (e) {
    console.error('Failed to load collected items:', e);
  }
  return new Set();
}

// Save collected items to localStorage
function saveCollectedItems() {
  try {
    const items = Array.from(collectedItems);
    localStorage.setItem('rdo-collected-items', JSON.stringify(items));
  } catch (e) {
    console.error('Failed to save collected items:', e);
  }
}

// Toggle collected status
function toggleCollected(collectible) {
  const id = getCollectibleId(collectible);

  if (collectedItems.has(id)) {
    collectedItems.delete(id);
    console.log(`Marked ${collectible.name} as NOT collected (${collectible.lat}, ${collectible.lng})`);
  } else {
    collectedItems.add(id);
    console.log(`Marked ${collectible.name} as collected (${collectible.lat}, ${collectible.lng})`);
  }

  // Save to localStorage
  saveCollectedItems();

  // Update collected display
  updateCollectedDisplay();

  // Redraw to reflect changes
  drawOverlay();
}

// Update collected items counter
function updateCollectedDisplay() {
  if (collectedDisplay) {
    collectedDisplay.textContent = collectedItems.size;
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

// Handle match updates from WebSocket
function handleMatchUpdate(data) {
  if (!continuousCapture) return;

  if (data.success) {
    // Update collectibles
    const newCollectibles = data.collectibles || [];

    // Only update and redraw if collectibles changed
    if (JSON.stringify(newCollectibles) !== JSON.stringify(currentCollectibles)) {
      currentCollectibles = newCollectibles;
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
    }
  } else {
    // Map not open or match failed - show empty
    if (currentCollectibles.length > 0 || isTracking) {
      currentCollectibles = [];
      isTracking = false;
      updateStatus('Waiting for map...', 'inactive');
      drawOverlay();
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

  // Match update from backend
  socket.on('match_update', handleMatchUpdate);

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
        hotkeys.classList.add('visible');
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
      hotkeys.classList.remove('visible');
      hideTooltip();
      closeVideoPlayer();
    }
  });

  // Global mouse click observation from backend
  socket.on('mouse-clicked', (data) => {
    // Only process backend click events when click-through is enabled
    // When video player or menus are open, DOM handles clicks naturally
    if (!isClickThroughEnabled) {
      console.log('[Click Observer] Ignoring backend click - click-through disabled (video player/menu open)');
      return;
    }

    const { x, y, button } = data;
    console.log(`[Click Observer] Processing backend click at (${x}, ${y}), button: ${button}`);

    // Hit-test priority order: Video controls > Tooltip elements > Collectible markers
    // (overlay is click-through when enabled, clicks also go to game)

    // 1. Check video player close button (highest priority)
    if (isClickOnVideoCloseButton(x, y)) {
      closeVideoPlayer();
      return; // Handled
    }

    // 2. Check tooltip video link
    const videoLinkData = isClickOnTooltipVideoLink(x, y);
    if (videoLinkData && button === 'left') {
      showVideoPlayer(videoLinkData.videoUrl, videoLinkData.collectibleName);
      return; // Handled
    }

    // 3. Check collectible markers
    const collectible = findCollectibleAt(x, y);
    if (collectible && button === 'right') {
      // Right-click toggles collected status
      toggleCollected(collectible);
      return; // Handled
    }

    // If no UI element hit, click naturally goes to game (overlay is click-through)
    // This includes left-clicks on collectibles (useful for gameplay)
  });
}

// Cursor polling for tooltips (overlay is always click-through)
let cursorPollingInterval = null;
let currentHoveredCollectible = null;

function findCollectibleAt(x, y) {
  /**Hit-test collectibles at cursor position*/
  if (!currentCollectibles || currentCollectibles.length === 0) {
    return null;
  }

  for (const collectible of currentCollectibles) {
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
  /**Check if cursor is over the tooltip*/
  if (!tooltip || tooltip.style.display === 'none') {
    return false;
  }

  const rect = tooltip.getBoundingClientRect();
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

async function pollCursor() {
  /**Poll cursor position for tooltip display - overlay is always click-through*/
  if (!isRdr2Active || !overlayVisible) {
    // RDR2 not active or overlay hidden - hide tooltip
    if (currentHoveredCollectible) {
      currentHoveredCollectible = null;
      hideTooltip();
    }
    return;
  }

  try {
    const cursorPos = await ipcRenderer.invoke('get-cursor-position');
    const overTooltip = isCursorOverTooltip(cursorPos.x, cursorPos.y);

    // If cursor is over tooltip, don't check for other collectibles
    // User is likely trying to interact with the tooltip (click video, etc.)
    if (overTooltip) {
      return; // Keep current tooltip visible, don't switch
    }

    const hoveredItem = findCollectibleAt(cursorPos.x, cursorPos.y);

    // Debug logging when hovering a collectible
    if (hoveredItem && hoveredItem !== currentHoveredCollectible) {
      console.log(`[Cursor] Cursor at (${cursorPos.x}, ${cursorPos.y}) hovering collectible at (${hoveredItem.x}, ${hoveredItem.y})`);
    }

    // Check if hover state changed
    if (hoveredItem !== currentHoveredCollectible) {
      if (hoveredItem) {
        // Started hovering a collectible - show tooltip near the marker
        currentHoveredCollectible = hoveredItem;
        showTooltip(hoveredItem);
      } else {
        // Stopped hovering - hide tooltip
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
   * Calculate tooltip position with corner centered on collectible,
   * minimizing overlap with other collectibles.
   */
  const screenWidth = 1920;
  const screenHeight = 1080;

  console.log(`[Tooltip] Calculating position for collectible at (${collectibleX}, ${collectibleY}), tooltip size: ${tooltipWidth}x${tooltipHeight}`);

  // Try 4 positions: each corner of tooltip centered on collectible
  const candidates = [
    // Bottom-left corner on collectible (tooltip to the right and up)
    { x: collectibleX, y: collectibleY - tooltipHeight, corner: 'bottom-left' },
    // Bottom-right corner on collectible (tooltip to the left and up)
    { x: collectibleX - tooltipWidth, y: collectibleY - tooltipHeight, corner: 'bottom-right' },
    // Top-left corner on collectible (tooltip to the right and down)
    { x: collectibleX, y: collectibleY, corner: 'top-left' },
    // Top-right corner on collectible (tooltip to the left and down)
    { x: collectibleX - tooltipWidth, y: collectibleY, corner: 'top-right' }
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

  return { x: selected.x, y: selected.y };
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
  console.log('[Initialize] Showing status bar and hotkeys');
  statusBar.classList.add('visible');
  hotkeys.classList.add('visible');

  // Connect to WebSocket (will immediately receive RDR2 state on connect)
  console.log('[Initialize] Connecting to WebSocket...');
  connectWebSocket();

  // Update collected items display with persisted count
  updateCollectedDisplay();
  console.log(`Loaded ${collectedItems.size} collected items from storage`);

  // Start cursor polling for hover detection (20fps = 50ms interval)
  startCursorPolling();

  // Ctrl+Shift+C to clear all collected items
  window.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'C') {
      if (collectedItems.size > 0) {
        const count = collectedItems.size;
        collectedItems.clear();
        saveCollectedItems();
        updateCollectedDisplay();
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
      // Receive collectibles data directly from alignment
      if (response.data.collectibles) {
        currentCollectibles = response.data.collectibles;
        console.log(`→ Received ${currentCollectibles.length} collectibles from alignment`);
        
        // Debug first few collectibles
        for (let i = 0; i < Math.min(3, currentCollectibles.length); i++) {
          const col = currentCollectibles[i];
          console.log(`  Collectible ${i+1}: ${col.type} "${col.name}" at screen(${col.x}, ${col.y})`);
        }
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
    hotkeys.classList.add('visible');
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
    hotkeys.classList.add('visible');
    currentCollectibles = [];
    drawOverlay();
  }
}

// Draw collectibles directly on canvas
function drawOverlay() {
  // Clear canvas
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
  
  // Set global opacity
  ctx.globalAlpha = overlayOpacity;
  
  // Draw each collectible
  let drawnCount = 0;
  for (const col of currentCollectibles) {
    const isCollected = collectedItems.has(getCollectibleId(col));
    const isHovered = hoveredCollectible === col;

    // Set opacity: 60% for collected, normal for uncollected
    if (isCollected) {
      ctx.globalAlpha = 0.6 * overlayOpacity; // 60% alpha for collected items
    } else {
      ctx.globalAlpha = overlayOpacity; // Normal opacity
    }

    // Ensure coordinates are valid
    if (typeof col.x !== 'number' || typeof col.y !== 'number' ||
        col.x < 0 || col.y < 0 || col.x > canvas.width || col.y > canvas.height) {
      console.warn(`Invalid coordinates for ${col.type}: (${col.x}, ${col.y})`);
      continue;
    }

    // Draw emoji icon (simple, no extra decorations)
    const icon = TYPE_ICONS[col.type] || '📍';
    ctx.save();
    ctx.font = '30px Arial';  // Larger font for 3x size (48px)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    // Add subtle shadow for better visibility
    ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
    ctx.shadowBlur = 4;
    ctx.fillText(icon, col.x, col.y);
    ctx.restore();

    drawnCount++;
  }
  
  // Reset opacity
  ctx.globalAlpha = 1.0;
  
  console.log(`Drew ${drawnCount}/${currentCollectibles.length} collectibles on canvas`);
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
ipcRenderer.on('start-alignment', () => {
  // F9 now triggers a manual refresh (useful if tracking gets stuck)
  console.log('F9 pressed - manual refresh');
  currentCollectibles = [];
  isTracking = false;
  updateStatus('Manual refresh - waiting for next frame...', 'aligning');
  pollLatestMatch(); // Force immediate poll
});

ipcRenderer.on('show-overlay', () => {
  overlayVisible = true;
  drawOverlay();
  // Only show UI elements if RDR2 is actually active
  if (isRdr2Active) {
    canvas.style.display = 'block';
    statusBar.classList.add('visible');
    hotkeys.classList.add('visible');
  }
});

ipcRenderer.on('hide-overlay', () => {
  overlayVisible = false;
  canvas.style.display = 'none';
  drawOverlay();
  statusBar.classList.remove('visible');
  hotkeys.classList.remove('visible');
});

ipcRenderer.on('set-opacity', (event, opacity) => {
  overlayOpacity = opacity;
  drawOverlay();
});

ipcRenderer.on('refresh-data', () => {
  refreshData();
});

// Initialization is handled by async function at the top after getting backend port