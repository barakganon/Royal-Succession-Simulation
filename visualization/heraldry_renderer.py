"""Procedural SVG coat of arms generator.

Generates a unique, deterministic heraldic shield SVG for each dynasty.
The same dynasty_id always produces the same arms — seeded from dynasty_id.
"""
import random
from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.heraldry_renderer')

# Heraldic tincture palette: (name, hex_color)
TINCTURES = [
    ('or', '#FFD700'),        # Gold
    ('argent', '#F5F5F5'),    # Silver
    ('gules', '#C41E3A'),     # Red
    ('azure', '#003087'),     # Blue
    ('sable', '#1A1A1A'),     # Black
    ('vert', '#215732'),      # Green
    ('purpure', '#5B2D8E'),   # Purple
]

# Ordinary types
ORDINARIES = ['bend', 'chevron', 'pale', 'fess', 'cross', 'saltire']

# Charge types
CHARGES = ['lion', 'eagle', 'fleur_de_lis', 'tower', 'star']


def _get_contrasting_color(used_colors: list, palette: list) -> str:
    """Pick a colour from palette not yet used.

    Falls back to cycling through the palette if all are used.
    """
    for name, color in palette:
        if color not in used_colors:
            return color
    # Fallback: pick any palette color not matching the very first used color
    for name, color in palette:
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
    # Star centered at (100, 120), outer radius 38, inner radius 16
    import math
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

    # 1. Pick tincture (background)
    tincture_idx = rng.randrange(len(TINCTURES))
    tincture_color = TINCTURES[tincture_idx][1]
    used_colors = [tincture_color]

    # 2. Pick ordinary
    ordinary_name = rng.choice(ORDINARIES)
    ordinary_color = _get_contrasting_color(used_colors, TINCTURES)
    used_colors.append(ordinary_color)

    # 3. Pick charge
    charge_name = rng.choice(CHARGES)
    charge_color = _get_contrasting_color(used_colors, TINCTURES)

    # Truncate long dynasty names for motto display
    motto = dynasty_name if len(dynasty_name) <= 24 else dynasty_name[:21] + '...'

    # Build ordinary SVG
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

    # Build charge SVG
    if charge_name == 'lion':
        charge_svg = _draw_lion(charge_color)
    elif charge_name == 'eagle':
        charge_svg = _draw_eagle(charge_color)
    elif charge_name == 'fleur_de_lis':
        charge_svg = _draw_fleur_de_lis(charge_color)
    elif charge_name == 'tower':
        charge_svg = _draw_tower(charge_color)
    else:  # star
        charge_svg = _draw_star(charge_color)

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" '
        'width="100%" height="100%" '
        'style="display:block;overflow:visible;">'
        + _shield_clip_path()
        # Background fill clipped to shield shape
        + f'<rect x="0" y="0" width="200" height="240" fill="{tincture_color}" clip-path="url(#shield-clip)"/>'
        # Ordinary
        + ordinary_svg
        # Charge
        + charge_svg
        # Shield border on top
        + _shield_border()
        # Motto text
        + f'<text x="100" y="238" text-anchor="middle" '
        f'font-family="Georgia,serif" font-size="11" font-variant="small-caps" '
        f'fill="#222222" stroke="#FFFFFF" stroke-width="2" paint-order="stroke">'
        + motto
        + '</text>'
        + '</svg>'
    )

    logger.debug(f"Generated coat of arms for dynasty_id={dynasty_id} name='{dynasty_name}' "
                 f"(tincture={TINCTURES[tincture_idx][0]}, ordinary={ordinary_name}, charge={charge_name})")
    return svg
