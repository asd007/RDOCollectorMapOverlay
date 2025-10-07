"""
SVG Icon Library for RDO Collectibles

Port of the Electron tracker icons (renderer.js:2364-2392)
24x24 SVG icons optimized for overlay display
"""

# SVG Icon definitions - exactly matching Electron implementation
TRACKER_ICONS = {
    'tarot_card': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="32" y="16" width="64" height="96" rx="4" fill="#2c1810" stroke="#8b6914" stroke-width="2"/><rect x="38" y="22" width="52" height="84" rx="2" fill="none" stroke="#d4af37" stroke-width="1"/><circle cx="64" cy="50" r="12" fill="#ffd700"/><g transform="translate(64,50)"><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(0)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(45)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(90)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(135)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(180)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(225)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(270)"/><path d="M0,-20 L2,-14 L-2,-14 Z" fill="#ffd700" transform="rotate(315)"/></g><path d="M54,85 L64,75 L74,85 L64,95 Z" fill="#d4af37"/></svg>''',

    'egg': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="70" rx="32" ry="42" fill="#f4e4d1" stroke="#8b7355" stroke-width="2"/><ellipse cx="56" cy="50" rx="12" ry="16" fill="#fff" opacity="0.6"/><path d="M40,70 Q64,65 88,70" stroke="#d4a574" stroke-width="1.5" fill="none"/><path d="M40,80 Q64,75 88,80" stroke="#d4a574" stroke-width="1.5" fill="none"/></svg>''',

    'bottle': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="58" y="20" width="12" height="16" rx="2" fill="#8b6b47" stroke="#654321" stroke-width="1"/><rect x="60" y="36" width="8" height="20" fill="#2a4d3a" stroke="#1a3d2a" stroke-width="1"/><path d="M52,56 L52,95 Q52,105 64,105 Q76,105 76,95 L76,56 Z" fill="#2a4d3a" stroke="#1a3d2a" stroke-width="2"/><rect x="56" y="70" width="16" height="20" rx="2" fill="#e8dcc6" opacity="0.8"/><path d="M56,85 L56,95 Q56,101 64,101 Q72,101 72,95 L72,85 Z" fill="#8b0000" opacity="0.6"/><rect x="58" y="60" width="4" height="12" rx="2" fill="#fff" opacity="0.4"/></svg>''',

    'flower': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M64,90 L64,110" stroke="#228b22" stroke-width="3" fill="none"/><ellipse cx="54" cy="95" rx="8" ry="4" fill="#228b22" transform="rotate(-30 54 95)"/><ellipse cx="74" cy="100" rx="8" ry="4" fill="#228b22" transform="rotate(30 74 100)"/><g transform="translate(64,60)"><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(0)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(72)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(144)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(216)"/><ellipse cx="0" cy="-15" rx="10" ry="18" fill="#ff69b4" transform="rotate(288)"/></g><circle cx="64" cy="60" r="12" fill="#ffd700"/><circle cx="64" cy="60" r="8" fill="#ff8c00"/></svg>''',

    'crown': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="30" y="70" width="68" height="20" rx="2" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M30,70 L40,40 L50,60 L64,35 L78,60 L88,40 L98,70" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><circle cx="64" cy="80" r="5" fill="#ff0000"/><circle cx="48" cy="80" r="4" fill="#0000ff"/><circle cx="80" cy="80" r="4" fill="#0000ff"/><circle cx="40" cy="40" r="3" fill="#00ff00"/><circle cx="64" cy="35" r="3" fill="#00ff00"/><circle cx="88" cy="40" r="3" fill="#00ff00"/></svg>''',

    'arrowhead': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M64,25 L45,65 L55,65 L64,95 L73,65 L83,65 Z" fill="#696969" stroke="#2c2c2c" stroke-width="2"/><line x1="55" y1="45" x2="60" y2="50" stroke="#4a4a4a" stroke-width="1"/><line x1="68" y1="45" x2="73" y2="50" stroke="#4a4a4a" stroke-width="1"/><line x1="60" y1="70" x2="64" y2="75" stroke="#4a4a4a" stroke-width="1"/><line x1="64" y1="75" x2="68" y2="70" stroke="#4a4a4a" stroke-width="1"/><path d="M64,30 L50,55 L57,55 L64,35" fill="#8a8a8a" opacity="0.6"/></svg>''',

    'coin': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><circle cx="64" cy="64" r="38" fill="#ffd700" stroke="#b8860b" stroke-width="3"/><circle cx="64" cy="64" r="32" fill="none" stroke="#b8860b" stroke-width="1"/><text x="64" y="75" font-family="Arial, serif" font-size="36" font-weight="bold" text-anchor="middle" fill="#b8860b">$</text><text x="64" y="40" font-family="Arial" font-size="12" text-anchor="middle" fill="#b8860b">★</text><text x="64" y="95" font-family="Arial" font-size="12" text-anchor="middle" fill="#b8860b">★</text><ellipse cx="52" cy="50" rx="8" ry="12" fill="#fff" opacity="0.3"/></svg>''',

    'fossil': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="40" ry="38" fill="#8b7355" stroke="#654321" stroke-width="2"/><path d="M64,64 Q70,64 70,58 Q70,52 62,52 Q54,52 54,60 Q54,68 64,68 Q74,68 74,58 Q74,48 60,48 Q46,48 46,62 Q46,76 64,76" stroke="#4a3c2a" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="40" y1="50" x2="45" y2="55" stroke="#6a5444" stroke-width="1"/><line x1="83" y1="50" x2="88" y2="55" stroke="#6a5444" stroke-width="1"/><line x1="40" y1="73" x2="45" y2="78" stroke="#6a5444" stroke-width="1"/><line x1="83" y1="73" x2="88" y2="78" stroke="#6a5444" stroke-width="1"/></svg>''',

    'ring': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="28" ry="34" fill="none" stroke="#ffd700" stroke-width="8"/><ellipse cx="64" cy="64" rx="28" ry="34" fill="none" stroke="#b8860b" stroke-width="6"/><rect x="54" y="24" width="20" height="20" rx="2" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M64,28 L72,34 L64,40 L56,34 Z" fill="#87ceeb" stroke="#4682b4" stroke-width="1"/><path d="M56,34 L72,34" stroke="#4682b4" stroke-width="0.5"/><path d="M58,30 L64,28 L62,34" fill="#fff" opacity="0.7"/></svg>''',

    'earring': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><g transform="translate(45, 50)"><path d="M0,0 Q0,-10 8,-10" stroke="#c0c0c0" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="0" y1="0" x2="0" y2="15" stroke="#c0c0c0" stroke-width="1"/><circle cx="0" cy="20" r="8" fill="#fffaf0" stroke="#d3d3d3" stroke-width="1"/><circle cx="-2" cy="18" r="3" fill="#fff" opacity="0.6"/></g><g transform="translate(83, 50)"><path d="M0,0 Q0,-10 -8,-10" stroke="#c0c0c0" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="0" y1="0" x2="0" y2="15" stroke="#c0c0c0" stroke-width="1"/><circle cx="0" cy="20" r="8" fill="#fffaf0" stroke="#d3d3d3" stroke-width="1"/><circle cx="-2" cy="18" r="3" fill="#fff" opacity="0.6"/></g></svg>''',

    'bracelet': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><ellipse cx="64" cy="64" rx="35" ry="28" fill="none" stroke="#ffd700" stroke-width="6"/><ellipse cx="64" cy="64" rx="35" ry="28" fill="none" stroke="#b8860b" stroke-width="4"/><g opacity="0.6"><path d="M30,64 Q35,60 40,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M40,64 Q45,68 50,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M50,64 Q55,60 60,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M60,64 Q65,68 70,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M70,64 Q75,60 80,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M80,64 Q85,68 90,64" stroke="#8b6914" stroke-width="2" fill="none"/><path d="M90,64 Q95,60 98,64" stroke="#8b6914" stroke-width="2" fill="none"/></g><circle cx="64" cy="38" r="5" fill="#ff69b4" stroke="#c71585" stroke-width="1"/></svg>''',

    'necklace': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><path d="M30,35 Q64,50 98,35 L98,40 Q64,55 30,40 Z" fill="none" stroke="#ffd700" stroke-width="3"/><path d="M30,35 Q64,50 98,35" fill="none" stroke="#b8860b" stroke-width="2"/><line x1="64" y1="50" x2="64" y2="70" stroke="#ffd700" stroke-width="2"/><g transform="translate(64, 80)"><path d="M0,-12 L8,0 L0,12 L-8,0 Z" fill="#ffd700" stroke="#b8860b" stroke-width="2"/><path d="M0,-8 L5,0 L0,8 L-5,0 Z" fill="#dc143c" stroke="#8b0000" stroke-width="1"/><path d="M-3,-4 L0,-8 L0,-2" fill="#ff6b6b" opacity="0.7"/></g></svg>''',

    'jewelry_random': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="32" y="32" width="64" height="64" rx="8" fill="#4a4a4a" stroke="#2a2a2a" stroke-width="2"/><g stroke="#ffd700" fill="#ffd700"><path d="M25,25 L28,28 L25,31 L22,28 Z"/><path d="M103,25 L106,28 L103,31 L100,28 Z"/><path d="M25,97 L28,100 L25,103 L22,100 Z"/><path d="M103,97 L106,100 L103,103 L100,100 Z"/></g><text x="64" y="75" font-family="Arial" font-size="48" font-weight="bold" text-anchor="middle" fill="#ffd700">?</text><g opacity="0.3" fill="#ffd700"><circle cx="45" cy="45" r="3"/><ellipse cx="83" cy="45" rx="4" ry="2"/><path d="M45,80 L48,83 L45,86 L42,83 Z"/><circle cx="83" cy="83" r="2"/></g></svg>''',

    'random': '''<svg width="24" height="24" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg"><rect x="28" y="28" width="72" height="72" rx="8" fill="#fff" stroke="#333" stroke-width="3"/><g fill="#333"><circle cx="48" cy="48" r="6"/><circle cx="80" cy="48" r="6"/><circle cx="48" cy="80" r="6"/><circle cx="80" cy="80" r="6"/><circle cx="64" cy="64" r="6"/><circle cx="48" cy="64" r="6"/><circle cx="80" cy="64" r="6"/></g></svg>'''
}

# Icon name mapping: collectible type -> SVG icon key
ICON_NAME_MAP = {
    # Tarot cards - all use tarot_card icon
    'cups': 'tarot_card',
    'swords': 'tarot_card',
    'wands': 'tarot_card',
    'pentacles': 'tarot_card',
    'card_tarot': 'tarot_card',

    # Direct mappings
    'egg': 'egg',
    'bottle': 'bottle',
    'flower': 'flower',
    'heirlooms': 'crown',
    'arrowhead': 'arrowhead',
    'coin': 'coin',

    # Fossils
    'fossils': 'fossil',
    'fossils_random': 'fossil',
    'fossil': 'fossil',

    # Jewelry subcategories
    'ring': 'ring',
    'earring': 'earring',
    'bracelet': 'bracelet',
    'necklace': 'necklace',
    'jewelry_random': 'jewelry_random',
    'jewelry': 'jewelry_random',
    'lost_jewelry': 'jewelry_random',

    # Random
    'random': 'random'
}


def get_icon_svg(collectible_type: str) -> str:
    """
    Get SVG icon string for a collectible type.

    Args:
        collectible_type: Type string from collectible (e.g., 'arrowhead', 'ring', 'cups')

    Returns:
        SVG string (24x24 viewBox 0 0 128 128)
    """
    icon_key = ICON_NAME_MAP.get(collectible_type, 'random')
    return TRACKER_ICONS.get(icon_key, TRACKER_ICONS['random'])


def get_icon_name(collectible_type: str) -> str:
    """
    Get icon key name for a collectible type.

    Args:
        collectible_type: Type string from collectible

    Returns:
        Icon key name (e.g., 'tarot_card', 'ring', 'fossil')
    """
    return ICON_NAME_MAP.get(collectible_type, 'random')
