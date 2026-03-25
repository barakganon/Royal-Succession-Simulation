"""Procedural SVG coat of arms generator.

Generates a unique, deterministic heraldic shield SVG for each dynasty.
The same dynasty_id always produces the same arms — seeded from dynasty_id.
"""
import math
import random
from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.heraldry_renderer')

# Heraldic tincture palette: (name, hex_color, is_dark)
TINCTURES = [
    ('or', '#FFD700', False),        # Gold   — light
    ('argent', '#F5F5F5', False),    # Silver — light
    ('gules', '#C41E3A', True),      # Red    — dark
    ('azure', '#003087', True),      # Blue   — dark
    ('sable', '#1A1A1A', True),      # Black  — dark
    ('vert', '#215732', True),       # Green  — dark
    ('purpure', '#5B2D8E', True),    # Purple — dark
]

# Ordinary types
ORDINARIES = ['bend', 'chevron', 'pale', 'fess', 'cross', 'saltire']

# Charge types — expanded to 10+
CHARGES = [
    'lion', 'eagle', 'fleur_de_lis', 'tower', 'star',
    'dragon', 'crown', 'sword', 'rose', 'ship', 'wolf', 'sun', 'crescent', 'tree',
]

# Edge treatment types
EDGE_TREATMENTS = ['plain', 'engrailed', 'border']


def _tincture_is_dark(color: str) -> bool:
    """Return True if the given hex color is a dark tincture."""
    for name, hex_c, is_dark in TINCTURES:
        if hex_c == color:
            return is_dark
    # Fallback: crude luminance check
    color = color.lstrip('#')
    if len(color) == 6:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) < 128
    return True


def _contrasting_charge_color(background_color: str) -> str:
    """Return a charge color that contrasts well against the background.

    Dark background → light charge (or/argent).
    Light background → dark charge (sable/azure/gules).
    """
    if _tincture_is_dark(background_color):
        # Light charges
        lights = [(n, c, d) for n, c, d in TINCTURES if not d and c != background_color]
        return lights[0][1] if lights else '#F5F5F5'
    else:
        # Dark charges
        darks = [(n, c, d) for n, c, d in TINCTURES if d and c != background_color]
        return darks[0][1] if darks else '#1A1A1A'


def _get_contrasting_color(used_colors: list, palette: list) -> str:
    """Pick a colour from palette not yet used.

    Falls back to cycling through the palette if all are used.
    """
    for name, color, *_ in palette:
        if color not in used_colors:
            return color
    for name, color, *_ in palette:
        if color != used_colors[0]:
            return color
    return palette[0][1]


def _shield_clip_path() -> str:
    """Return the SVG defs block with a heater shield clip path."""
    return (
        '<defs>'
        '<clipPath id="shield-clip">'
        '<path d="M10,10 L190,10 L190,130 Q190,200 100,230 Q10,200 10,130 Z"/>'
        '</clipPath>'
        '</defs>'
    )


def _shield_border() -> str:
    """Return a dark border drawn on top of the shield contents."""
    return (
        '<path d="M10,10 L190,10 L190,130 Q190,200 100,230 Q10,200 10,130 Z" '
        'fill="none" stroke="#222222" stroke-width="3"/>'
    )


def _shield_engrailed_border() -> str:
    """Return a wavy/scalloped engrailed border around the shield."""
    # Approximate engrailed with a series of small arcs along the shield outline
    return (
        '<path d="M10,10 L190,10 L190,130 Q190,200 100,230 Q10,200 10,130 Z" '
        'fill="none" stroke="#444" stroke-width="6" stroke-dasharray="8,4"/>'
    )


def _shield_contrasting_border(color: str) -> str:
    """Return a thin contrasting inner border line inside the shield outline."""
    return (
        '<path d="M18,18 L182,18 L182,128 Q182,194 100,222 Q18,194 18,128 Z" '
        f'fill="none" stroke="{color}" stroke-width="4"/>'
    )


# ---------------------------------------------------------------------------
# Quartered shield helpers
# ---------------------------------------------------------------------------

def _draw_quartered_background(tincture1: str, tincture2: str) -> str:
    """Draw a shield divided into 4 quadrants with alternating tinctures."""
    # Top-left and bottom-right: tincture1
    # Top-right and bottom-left: tincture2
    return (
        # Top-left quadrant
        f'<rect x="0" y="0" width="100" height="120" fill="{tincture1}" clip-path="url(#shield-clip)"/>'
        # Top-right quadrant
        f'<rect x="100" y="0" width="100" height="120" fill="{tincture2}" clip-path="url(#shield-clip)"/>'
        # Bottom-left quadrant
        f'<rect x="0" y="120" width="100" height="120" fill="{tincture2}" clip-path="url(#shield-clip)"/>'
        # Bottom-right quadrant
        f'<rect x="100" y="120" width="100" height="120" fill="{tincture1}" clip-path="url(#shield-clip)"/>'
        # Thin dividing lines
        f'<line x1="100" y1="10" x2="100" y2="230" stroke="#888" stroke-width="1.5" clip-path="url(#shield-clip)"/>'
        f'<line x1="10" y1="120" x2="190" y2="120" stroke="#888" stroke-width="1.5" clip-path="url(#shield-clip)"/>'
    )


# ---------------------------------------------------------------------------
# Ordinary drawers
# ---------------------------------------------------------------------------

def _draw_bend(rng: random.Random, color: str) -> str:
    """Diagonal stripe top-left to bottom-right within the shield."""
    return (
        f'<polygon points="50,10 110,10 190,130 190,170 130,230 70,230 10,130 10,90" '
        f'fill="{color}" clip-path="url(#shield-clip)"/>'
    )


def _draw_chevron(rng: random.Random, color: str) -> str:
    """Upward V shape in the shield."""
    return (
        f'<polygon points="10,160 100,80 190,160 190,195 100,115 10,195" '
        f'fill="{color}" clip-path="url(#shield-clip)"/>'
    )


def _draw_pale(color: str) -> str:
    """Vertical stripe down the center."""
    return (
        f'<rect x="75" y="10" width="50" height="220" '
        f'fill="{color}" clip-path="url(#shield-clip)"/>'
    )


def _draw_fess(color: str) -> str:
    """Horizontal stripe across the middle."""
    return (
        f'<rect x="10" y="90" width="180" height="60" '
        f'fill="{color}" clip-path="url(#shield-clip)"/>'
    )


def _draw_cross(color: str) -> str:
    """Vertical + horizontal stripes crossing center."""
    return (
        f'<rect x="85" y="10" width="30" height="220" fill="{color}" clip-path="url(#shield-clip)"/>'
        f'<rect x="10" y="100" width="180" height="40" fill="{color}" clip-path="url(#shield-clip)"/>'
    )


def _draw_saltire(color: str) -> str:
    """X cross — two diagonal stripes."""
    return (
        f'<polygon points="10,10 50,10 100,80 150,10 190,10 190,50 120,120 190,190 190,230 150,230 100,160 50,230 10,230 10,190 80,120 10,50" '
        f'fill="{color}" clip-path="url(#shield-clip)"/>'
    )


# ---------------------------------------------------------------------------
# Charge drawers
# ---------------------------------------------------------------------------

def _draw_lion(color: str) -> str:
    """Simplified lion silhouette — rectangle-based approximation."""
    return (
        # Body
        f'<rect x="75" y="105" width="55" height="45" rx="10" fill="{color}"/>'
        # Head
        f'<circle cx="135" cy="100" r="22" fill="{color}"/>'
        # Mane ring
        f'<circle cx="135" cy="100" r="28" fill="{color}" opacity="0.5"/>'
        # Tail
        f'<path d="M75,130 Q50,115 55,95 Q60,75 70,90" stroke="{color}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        # Front leg
        f'<rect x="115" y="145" width="12" height="28" rx="4" fill="{color}"/>'
        # Rear leg
        f'<rect x="80" y="145" width="12" height="28" rx="4" fill="{color}"/>'
    )


def _draw_eagle(color: str) -> str:
    """Simplified eagle — spread wings using polygons."""
    return (
        # Left wing
        f'<polygon points="100,110 40,80 30,130 75,125" fill="{color}"/>'
        # Right wing
        f'<polygon points="100,110 160,80 170,130 125,125" fill="{color}"/>'
        # Body
        f'<ellipse cx="100" cy="130" rx="22" ry="30" fill="{color}"/>'
        # Head
        f'<circle cx="100" cy="98" r="14" fill="{color}"/>'
        # Beak
        f'<polygon points="100,98 114,105 108,112" fill="{color}" opacity="0.7"/>'
    )


def _draw_fleur_de_lis(color: str) -> str:
    """Classic fleur-de-lis shape."""
    return (
        # Central petal
        f'<path d="M100,80 Q90,100 95,125 L100,135 L105,125 Q110,100 100,80 Z" fill="{color}"/>'
        # Left petal
        f'<path d="M100,110 Q75,95 65,110 Q75,130 90,120 Z" fill="{color}"/>'
        # Right petal
        f'<path d="M100,110 Q125,95 135,110 Q125,130 110,120 Z" fill="{color}"/>'
        # Lower base
        f'<rect x="92" y="130" width="16" height="30" rx="4" fill="{color}"/>'
        f'<rect x="80" y="155" width="40" height="10" rx="4" fill="{color}"/>'
    )


def _draw_tower(color: str) -> str:
    """Castle tower — rectangles."""
    return (
        # Main tower body
        f'<rect x="82" y="105" width="36" height="65" fill="{color}"/>'
        # Battlements
        f'<rect x="82" y="95" width="8" height="15" fill="{color}"/>'
        f'<rect x="96" y="95" width="8" height="15" fill="{color}"/>'
        f'<rect x="110" y="95" width="8" height="15" fill="{color}"/>'
        # Gate
        f'<rect x="92" y="140" width="16" height="30" rx="8" fill="{color}" opacity="0.4"/>'
        # Left wing wall
        f'<rect x="65" y="120" width="18" height="50" fill="{color}"/>'
        # Right wing wall
        f'<rect x="117" y="120" width="18" height="50" fill="{color}"/>'
    )


def _draw_star(color: str) -> str:
    """5-pointed star polygon."""
    outer_r = 38
    inner_r = 16
    cx, cy = 100, 120
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5  # Start pointing up
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        points.append(f"{x:.1f},{y:.1f}")
    pts_str = ' '.join(points)
    return f'<polygon points="{pts_str}" fill="{color}"/>'


def _draw_dragon(color: str) -> str:
    """Simplified dragon silhouette."""
    return (
        # Body
        f'<ellipse cx="100" cy="130" rx="30" ry="18" fill="{color}"/>'
        # Neck
        f'<path d="M115,120 Q125,100 130,90" stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round"/>'
        # Head
        f'<ellipse cx="132" cy="83" rx="16" ry="12" fill="{color}"/>'
        # Snout
        f'<polygon points="140,80 158,78 148,90" fill="{color}"/>'
        # Left wing
        f'<polygon points="95,118 50,80 60,130 80,125" fill="{color}" opacity="0.85"/>'
        # Right wing
        f'<polygon points="105,118 155,82 148,128 122,123" fill="{color}" opacity="0.85"/>'
        # Tail
        f'<path d="M72,135 Q50,145 45,160 Q55,165 60,155 Q65,148 78,140" stroke="{color}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        # Front leg
        f'<path d="M108,145 L112,168 L118,168" stroke="{color}" stroke-width="7" fill="none" stroke-linecap="round"/>'
        # Rear leg
        f'<path d="M85,145 L82,168 L76,168" stroke="{color}" stroke-width="7" fill="none" stroke-linecap="round"/>'
    )


def _draw_crown(color: str) -> str:
    """Heraldic crown — base band with three points."""
    return (
        # Crown base band
        f'<rect x="68" y="128" width="64" height="18" rx="3" fill="{color}"/>'
        # Left point
        f'<polygon points="72,128 80,100 88,128" fill="{color}"/>'
        # Center point (tallest)
        f'<polygon points="92,128 100,90 108,128" fill="{color}"/>'
        # Right point
        f'<polygon points="112,128 120,100 128,128" fill="{color}"/>'
        # Gems (small circles on tips)
        f'<circle cx="80" cy="101" r="5" fill="{color}" opacity="0.6"/>'
        f'<circle cx="100" cy="91" r="6" fill="{color}" opacity="0.6"/>'
        f'<circle cx="120" cy="101" r="5" fill="{color}" opacity="0.6"/>'
    )


def _draw_sword(color: str) -> str:
    """Upright sword — blade, crossguard, and grip."""
    return (
        # Blade
        f'<polygon points="97,80 103,80 101,160 99,160" fill="{color}"/>'
        # Tip
        f'<polygon points="97,80 103,80 100,68" fill="{color}"/>'
        # Crossguard
        f'<rect x="72" y="158" width="56" height="10" rx="4" fill="{color}"/>'
        # Grip
        f'<rect x="95" y="165" width="10" height="28" rx="4" fill="{color}"/>'
        # Pommel
        f'<circle cx="100" cy="196" r="9" fill="{color}"/>'
    )


def _draw_rose(color: str) -> str:
    """Stylised heraldic rose — overlapping petals."""
    cx, cy, r_outer, r_inner = 100, 115, 34, 14
    petals = []
    for i in range(5):
        angle = i * 2 * math.pi / 5 - math.pi / 2
        px = cx + r_outer * math.cos(angle)
        py = cy + r_outer * math.sin(angle)
        petals.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="16" ry="10" '
                      f'fill="{color}" transform="rotate({math.degrees(angle):.1f},{px:.1f},{py:.1f})"/>')
    # Centre
    petals.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="{color}" opacity="0.9"/>')
    petals.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{color}" opacity="0.5"/>')
    return ''.join(petals)


def _draw_ship(color: str) -> str:
    """Simplified sailing ship silhouette."""
    return (
        # Hull
        f'<path d="M55,135 Q100,160 145,135 L138,150 Q100,168 62,150 Z" fill="{color}"/>'
        # Mast
        f'<rect x="97" y="85" width="6" height="50" fill="{color}"/>'
        # Main sail
        f'<polygon points="103,88 103,128 140,118 135,88" fill="{color}" opacity="0.85"/>'
        # Fore sail
        f'<polygon points="97,90 97,118 70,112 75,92" fill="{color}" opacity="0.75"/>'
        # Waves beneath hull
        f'<path d="M55,152 Q70,158 85,152 Q100,146 115,152 Q130,158 145,152" '
        f'stroke="{color}" stroke-width="4" fill="none" opacity="0.5"/>'
    )


def _draw_wolf(color: str) -> str:
    """Simplified wolf head (facing forward)."""
    return (
        # Head oval
        f'<ellipse cx="100" cy="110" rx="34" ry="38" fill="{color}"/>'
        # Ears
        f'<polygon points="70,82 78,60 90,80" fill="{color}"/>'
        f'<polygon points="130,82 122,60 110,80" fill="{color}"/>'
        # Snout
        f'<ellipse cx="100" cy="128" rx="18" ry="12" fill="{color}" opacity="0.8"/>'
        # Nose
        f'<ellipse cx="100" cy="120" rx="7" ry="5" fill="{color}" opacity="0.5"/>'
        # Eyes (negative space suggestion via opacity)
        f'<ellipse cx="85" cy="103" rx="7" ry="6" fill="{color}" opacity="0.4"/>'
        f'<ellipse cx="115" cy="103" rx="7" ry="6" fill="{color}" opacity="0.4"/>'
    )


def _draw_sun(color: str) -> str:
    """Sun with rays."""
    cx, cy, r_core, r_ray_outer, r_ray_inner = 100, 115, 26, 48, 34
    rays = []
    for i in range(12):
        angle = i * math.pi / 6
        x_outer = cx + r_ray_outer * math.cos(angle)
        y_outer = cy + r_ray_outer * math.sin(angle)
        x_inner1 = cx + r_ray_inner * math.cos(angle - math.pi / 12)
        y_inner1 = cy + r_ray_inner * math.sin(angle - math.pi / 12)
        x_inner2 = cx + r_ray_inner * math.cos(angle + math.pi / 12)
        y_inner2 = cy + r_ray_inner * math.sin(angle + math.pi / 12)
        rays.append(f'<polygon points="{x_inner1:.1f},{y_inner1:.1f} {x_outer:.1f},{y_outer:.1f} {x_inner2:.1f},{y_inner2:.1f}" fill="{color}"/>')
    rays.append(f'<circle cx="{cx}" cy="{cy}" r="{r_core}" fill="{color}"/>')
    return ''.join(rays)


def _draw_crescent(color: str) -> str:
    """Crescent moon."""
    cx, cy = 100, 115
    return (
        # Full circle
        f'<circle cx="{cx}" cy="{cy}" r="38" fill="{color}"/>'
        # Occluding circle offset to create crescent
        f'<circle cx="{cx + 22}" cy="{cy - 8}" r="34" fill="transparent" '
        f'stroke="{color}" stroke-width="0"/>'
        # Re-draw the occlusion using the background — approximated with a path
        # We clip with a crescent path instead
        f'<path d="M{cx},{cy - 38} A38,38 0 1,1 {cx},{cy + 38} A26,26 0 1,0 {cx},{cy - 38} Z" fill="{color}"/>'
    )


def _draw_tree(color: str) -> str:
    """Simplified oak tree."""
    return (
        # Trunk
        f'<rect x="93" y="145" width="14" height="35" rx="3" fill="{color}"/>'
        # Root spread
        f'<path d="M88,178 Q80,182 72,180" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>'
        f'<path d="M112,178 Q120,182 128,180" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>'
        # Lower canopy
        f'<ellipse cx="100" cy="130" rx="42" ry="30" fill="{color}"/>'
        # Upper canopy (smaller, lighter)
        f'<ellipse cx="100" cy="110" rx="32" ry="26" fill="{color}" opacity="0.85"/>'
        # Top canopy
        f'<ellipse cx="100" cy="93" rx="22" ry="20" fill="{color}" opacity="0.75"/>'
    )


# ---------------------------------------------------------------------------
# Supporter drawers
# ---------------------------------------------------------------------------

def _draw_supporters(rng: random.Random, color: str) -> str:
    """Draw small flanking supporters (lion or eagle) at the base of the shield."""
    supporter_type = rng.choice(['lion', 'eagle'])
    if supporter_type == 'lion':
        left = (
            f'<g transform="translate(0,210) scale(0.22)">'
            f'<rect x="75" y="105" width="55" height="45" rx="10" fill="{color}"/>'
            f'<circle cx="135" cy="100" r="22" fill="{color}"/>'
            f'<circle cx="135" cy="100" r="28" fill="{color}" opacity="0.5"/>'
            f'</g>'
        )
        right = (
            f'<g transform="translate(163,210) scale(-0.22,0.22)">'
            f'<rect x="75" y="105" width="55" height="45" rx="10" fill="{color}"/>'
            f'<circle cx="135" cy="100" r="22" fill="{color}"/>'
            f'<circle cx="135" cy="100" r="28" fill="{color}" opacity="0.5"/>'
            f'</g>'
        )
    else:
        left = (
            f'<g transform="translate(2,205) scale(0.2)">'
            f'<polygon points="100,110 40,80 30,130 75,125" fill="{color}"/>'
            f'<ellipse cx="100" cy="130" rx="22" ry="30" fill="{color}"/>'
            f'<circle cx="100" cy="98" r="14" fill="{color}"/>'
            f'</g>'
        )
        right = (
            f'<g transform="translate(158,205) scale(-0.2,0.2)">'
            f'<polygon points="100,110 40,80 30,130 75,125" fill="{color}"/>'
            f'<ellipse cx="100" cy="130" rx="22" ry="30" fill="{color}"/>'
            f'<circle cx="100" cy="98" r="14" fill="{color}"/>'
            f'</g>'
        )
    return left + right


# ---------------------------------------------------------------------------
# Motto banner
# ---------------------------------------------------------------------------

def _draw_motto_banner(motto: str, color: str, text_color: str) -> str:
    """Draw a curved banner/scroll beneath the shield with the motto."""
    # Arc path for the banner ribbon
    banner = (
        # Banner ribbon shape (a curved path with slight upward bow)
        f'<path d="M8,242 Q100,232 192,242 Q100,258 8,242 Z" fill="{color}" stroke="#555" stroke-width="1.5"/>'
        # Curled ends
        f'<path d="M8,242 Q4,248 10,252 Q14,248 8,242" fill="{color}" stroke="#555" stroke-width="1"/>'
        f'<path d="M192,242 Q196,248 190,252 Q186,248 192,242" fill="{color}" stroke="#555" stroke-width="1"/>'
        # Motto text along arc
        f'<text text-anchor="middle" font-family="Georgia,serif" font-size="10" '
        f'font-variant="small-caps" fill="{text_color}">'
        f'<textPath href="#motto-arc" startOffset="50%">{motto}</textPath>'
        f'</text>'
    )
    # Define the arc path for textPath
    arc_def = (
        f'<defs><path id="motto-arc" d="M15,248 Q100,236 185,248"/></defs>'
    )
    return arc_def + banner


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_coat_of_arms(dynasty_id: int, dynasty_name: str) -> str:
    """Generate a deterministic heraldic shield SVG for the given dynasty.

    The same dynasty_id always produces the same arms (seeded RNG).

    Args:
        dynasty_id: Unique integer ID of the dynasty — used as RNG seed.
        dynasty_name: Dynasty name shown as motto below the shield.

    Returns:
        A complete, self-contained SVG string.
    """
    rng = random.Random(dynasty_id)

    # 1. Determine if shield is quartered (dynasty_id > 100)
    is_quartered = dynasty_id > 100

    # 2. Pick tincture(s) — background
    tincture_idx = rng.randrange(len(TINCTURES))
    tincture_color = TINCTURES[tincture_idx][1]
    used_colors = [tincture_color]

    if is_quartered:
        # Pick a second tincture for alternating quadrants
        remaining = [(n, c, d) for n, c, d in TINCTURES if c != tincture_color]
        tincture2_tuple = rng.choice(remaining)
        tincture2_color = tincture2_tuple[1]
        used_colors.append(tincture2_color)

    # 3. Pick ordinary
    ordinary_name = rng.choice(ORDINARIES)
    ordinary_color = _get_contrasting_color(used_colors, TINCTURES)
    used_colors.append(ordinary_color)

    # 4. Pick charge — color contrasts with background
    charge_name = rng.choice(CHARGES)
    charge_color = _contrasting_charge_color(tincture_color)

    # 5. Edge treatment
    edge_treatment = rng.choice(EDGE_TREATMENTS)
    # Border contrast color
    border_contrast = _get_contrasting_color(used_colors, TINCTURES)

    # 6. Supporters
    draw_supporters = rng.random() > 0.45
    supporter_color = _get_contrasting_color(used_colors + [charge_color], TINCTURES)

    # Truncate long dynasty names for motto display
    motto = dynasty_name if len(dynasty_name) <= 24 else dynasty_name[:21] + '...'

    # --- Banner tincture: dark bg → light banner, light bg → dark banner ---
    if _tincture_is_dark(tincture_color):
        banner_color = '#E8D8A0'
        banner_text_color = '#222'
    else:
        banner_color = '#4A3520'
        banner_text_color = '#F5F0E0'

    # --- Build ordinary SVG ---
    if ordinary_name == 'bend':
        ordinary_svg = _draw_bend(rng, ordinary_color)
    elif ordinary_name == 'chevron':
        ordinary_svg = _draw_chevron(rng, ordinary_color)
    elif ordinary_name == 'pale':
        ordinary_svg = _draw_pale(ordinary_color)
    elif ordinary_name == 'fess':
        ordinary_svg = _draw_fess(ordinary_color)
    elif ordinary_name == 'cross':
        ordinary_svg = _draw_cross(ordinary_color)
    else:  # saltire
        ordinary_svg = _draw_saltire(ordinary_color)

    # --- Build charge SVG ---
    charge_map = {
        'lion': _draw_lion,
        'eagle': _draw_eagle,
        'fleur_de_lis': _draw_fleur_de_lis,
        'tower': _draw_tower,
        'star': _draw_star,
        'dragon': _draw_dragon,
        'crown': _draw_crown,
        'sword': _draw_sword,
        'rose': _draw_rose,
        'ship': _draw_ship,
        'wolf': _draw_wolf,
        'sun': _draw_sun,
        'crescent': _draw_crescent,
        'tree': _draw_tree,
    }
    charge_fn = charge_map.get(charge_name, _draw_star)
    charge_svg = charge_fn(charge_color)

    # --- Build edge treatment SVG ---
    if edge_treatment == 'engrailed':
        edge_svg = _shield_engrailed_border()
    elif edge_treatment == 'border':
        edge_svg = _shield_contrasting_border(border_contrast)
    else:
        edge_svg = ''  # plain — just the standard shield_border() later

    # --- Background ---
    if is_quartered:
        bg_svg = _draw_quartered_background(tincture_color, tincture2_color)
    else:
        bg_svg = f'<rect x="0" y="0" width="200" height="240" fill="{tincture_color}" clip-path="url(#shield-clip)"/>'

    # --- Supporters ---
    supporter_svg = _draw_supporters(rng, supporter_color) if draw_supporters else ''

    # --- Motto banner ---
    motto_svg = _draw_motto_banner(motto, banner_color, banner_text_color)

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 270" '
        'width="100%" height="100%" '
        'style="display:block;overflow:visible;">'
        + _shield_clip_path()
        # Background
        + bg_svg
        # Ordinary
        + ordinary_svg
        # Charge
        + charge_svg
        # Edge treatment (inner border or engrailed) — below outer border
        + edge_svg
        # Shield border on top
        + _shield_border()
        # Supporters flanking the shield base
        + supporter_svg
        # Motto banner
        + motto_svg
        + '</svg>'
    )

    logger.debug(
        f"Generated coat of arms for dynasty_id={dynasty_id} name='{dynasty_name}' "
        f"(tincture={TINCTURES[tincture_idx][0]}, ordinary={ordinary_name}, "
        f"charge={charge_name}, quartered={is_quartered}, edge={edge_treatment})"
    )
    return svg
