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

const { ipcRenderer } = require('electron');
const axios = require('axios');

// Configuration
const BACKEND_URL = 'http://127.0.0.1:5000';

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
const interactionHint = document.getElementById('interaction-hint');

// State
let overlayVisible = true;
let overlayOpacity = 0.7;
let isAligning = false;
let isTracking = false;
let currentCollectibles = [];
let currentFPS = 30;
let collectedItems = new Set(); // Track collected items
let hoveredCollectible = null; // Track hovered collectible

// Tooltip element
let tooltip = null;

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

// Collectible sizes (20x20 pixels)
const COLLECTIBLE_SIZE = {
  outerRadius: 10,  // 20px diameter
  innerRadius: 4,   // 8px diameter
  glowRadius: 12    // 24px diameter for glow effect
};

// Create tooltip element
function createTooltip() {
  tooltip = document.createElement('div');
  tooltip.id = 'collectible-tooltip';
  tooltip.style.cssText = `
    position: absolute;
    background: rgba(0, 0, 0, 0.9);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(217, 119, 6, 0.7);
    border-radius: 8px;
    padding: 12px;
    color: white;
    font-size: 12px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    max-width: 300px;
    z-index: 10000;
    pointer-events: none;
    display: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  `;
  document.body.appendChild(tooltip);
}

// Show tooltip for collectible
function showTooltip(collectible, x, y) {
  if (!tooltip) return;
  
  const name = collectible.name || 'Unknown';
  const type = collectible.type || 'unknown';
  const helpText = collectible.help || '';
  const videoLink = collectible.video || '';
  
  let tooltipHTML = `
    <div style="font-weight: bold; color: #fbbf24; margin-bottom: 6px;">${name}</div>
    <div style="font-size: 10px; color: #9ca3af; margin-bottom: 4px;">Type: ${type}</div>
  `;
  
  if (helpText) {
    tooltipHTML += `<div style="margin-bottom: 6px; font-size: 11px;">${helpText}</div>`;
  }
  
  if (videoLink) {
    tooltipHTML += `<div style="font-size: 10px;">
      <a href="${videoLink}" target="_blank" style="color: #60a5fa; text-decoration: none;">📹 Watch Guide</a>
    </div>`;
  }
  
  // Add collection status
  const isCollected = collectedItems.has(getCollectibleId(collectible));
  tooltipHTML += `<div style="font-size: 10px; color: ${isCollected ? '#22c55e' : '#ef4444'}; margin-top: 4px;">
    ${isCollected ? '✓ Collected' : '⚫ Not Collected'}
  </div>`;
  
  tooltip.innerHTML = tooltipHTML;
  tooltip.style.display = 'block';
  
  // Position tooltip (avoid going off-screen)
  const tooltipWidth = tooltip.offsetWidth;
  const tooltipHeight = tooltip.offsetHeight;
  
  let posX = x + 20;
  let posY = y + 20;
  
  if (posX + tooltipWidth > window.innerWidth) {
    posX = x - tooltipWidth - 10;
  }
  if (posY + tooltipHeight > window.innerHeight) {
    posY = y - tooltipHeight - 10;
  }
  
  tooltip.style.left = posX + 'px';
  tooltip.style.top = posY + 'px';
}

// Hide tooltip
function hideTooltip() {
  if (tooltip) {
    tooltip.style.display = 'none';
  }
}

// Show interaction hint
function showInteractionHint() {
  if (interactionHint) {
    interactionHint.classList.add('visible');
  }
}

// Hide interaction hint
function hideInteractionHint() {
  if (interactionHint) {
    interactionHint.classList.remove('visible');
  }
}

// Check if point is inside collectible
function isPointInCollectible(x, y, collectible) {
  const distance = Math.sqrt(
    Math.pow(x - collectible.x, 2) + Math.pow(y - collectible.y, 2)
  );
  return distance <= COLLECTIBLE_SIZE.glowRadius;
}

// Find collectible at coordinates
function findCollectibleAt(x, y) {
  return currentCollectibles.find(col => 
    isPointInCollectible(x, y, col)
  );
}

// Get unique ID for collectible
function getCollectibleId(collectible) {
  return `${collectible.type}-${collectible.name}-${collectible.x}-${collectible.y}`;
}

// Toggle collected status
function toggleCollected(collectible) {
  const id = getCollectibleId(collectible);
  
  if (collectedItems.has(id)) {
    collectedItems.delete(id);
    console.log(`Marked ${collectible.name} as NOT collected`);
  } else {
    collectedItems.add(id);
    console.log(`Marked ${collectible.name} as collected`);
  }
  
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

// Mouse event handlers
function handleMouseMove(event) {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  
  const collectible = findCollectibleAt(x, y);
  
  if (collectible && collectible !== hoveredCollectible) {
    hoveredCollectible = collectible;
    showTooltip(collectible, event.clientX, event.clientY);
    canvas.style.cursor = 'pointer';
    showInteractionHint();
  } else if (!collectible && hoveredCollectible) {
    hoveredCollectible = null;
    hideTooltip();
    canvas.style.cursor = 'default';
    hideInteractionHint();
  }
}

function handleContextMenu(event) {
  event.preventDefault();
  
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  
  const collectible = findCollectibleAt(x, y);
  if (collectible) {
    toggleCollected(collectible);
  }
}

// Resize canvas to window size
function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// Initialize
async function initialize() {
  console.log('Initializing overlay...');
  updateStatus('Connecting to backend...', 'inactive');
  
  // Create tooltip
  createTooltip();
  
  // Enable pointer events on canvas for interaction
  canvas.style.pointerEvents = 'auto';
  
  // Add event listeners
  canvas.addEventListener('mousemove', handleMouseMove);
  canvas.addEventListener('contextmenu', handleContextMenu);
  
  // Show interaction hint when tracking starts
  canvas.addEventListener('mouseenter', showInteractionHint);
  canvas.addEventListener('mouseleave', hideInteractionHint);
  
  try {
    const response = await axios.get(`${BACKEND_URL}/status`);
    if (response.data.ready) {
      if (response.data.screenshot_available) {
        updateStatus('Ready - Press F9 to align', 'inactive');
      } else {
        updateStatus('Ready - Screenshots not available', 'inactive');
      }
      statusBar.classList.add('visible');
      hotkeys.classList.add('visible');
    }
  } catch (error) {
    console.error('Backend not available:', error.message);
    updateStatus('Backend offline - Start Python server', 'inactive');
    statusBar.classList.add('visible');
  }
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
    
    // Skip drawing collected items with very low opacity
    if (isCollected) {
      ctx.globalAlpha = 0.2; // Very transparent for collected items
    } else if (isHovered) {
      ctx.globalAlpha = 1.0; // Full opacity for hovered items
    } else {
      ctx.globalAlpha = overlayOpacity; // Normal opacity
    }
    
    const color = TYPE_COLORS[col.type] || { r: 200, g: 200, b: 200 };
    
    // Ensure coordinates are valid
    if (typeof col.x !== 'number' || typeof col.y !== 'number' || 
        col.x < 0 || col.y < 0 || col.x > canvas.width || col.y > canvas.height) {
      console.warn(`Invalid coordinates for ${col.type}: (${col.x}, ${col.y})`);
      continue;
    }
    
    // Draw glow effect (subtle outer glow) - only for non-collected items
    if (!isCollected) {
      ctx.beginPath();
      ctx.arc(col.x, col.y, COLLECTIBLE_SIZE.glowRadius, 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${isHovered ? 0.5 : 0.3})`;
      ctx.fill();
    }
    
    // Draw outer circle (colored) - 20px diameter
    ctx.beginPath();
    ctx.arc(col.x, col.y, COLLECTIBLE_SIZE.outerRadius, 0, 2 * Math.PI);
    ctx.fillStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${isCollected ? 0.3 : 0.9})`;
    ctx.fill();
    
    // Draw inner circle (white center) - 8px diameter
    if (!isCollected) {
      ctx.beginPath();
      ctx.arc(col.x, col.y, COLLECTIBLE_SIZE.innerRadius, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(255, 255, 255, 1.0)';
      ctx.fill();
    }
    
    // Draw outline for better visibility
    ctx.beginPath();
    ctx.arc(col.x, col.y, COLLECTIBLE_SIZE.outerRadius, 0, 2 * Math.PI);
    ctx.strokeStyle = isCollected ? 
      `rgba(${color.r}, ${color.g}, ${color.b}, 0.3)` : 
      `rgba(255, 255, 255, 0.8)`;
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.stroke();
    
    // Draw cross for collected items
    if (isCollected) {
      ctx.strokeStyle = `rgba(${color.r}, ${color.g}, ${color.b}, 0.6)`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(col.x - 6, col.y - 6);
      ctx.lineTo(col.x + 6, col.y + 6);
      ctx.moveTo(col.x + 6, col.y - 6);
      ctx.lineTo(col.x - 6, col.y + 6);
      ctx.stroke();
    }
    
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
      collectedItems.clear(); // Clear collected items on refresh
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
  startAlignment();
});

ipcRenderer.on('show-overlay', () => {
  overlayVisible = true;
  drawOverlay();
  statusBar.classList.add('visible');
  hotkeys.classList.add('visible');
});

ipcRenderer.on('hide-overlay', () => {
  overlayVisible = false;
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

// Start initialization
initialize();