"""Procedural SVG character portrait generator.

Generates a unique, deterministic SVG face for each PersonDB record,
driven by their traits, age, and gender.
The same person_id + traits always produces the same portrait.
"""
import random
from utils.logging_config import setup_logger

logger = setup_logger('royal_succession.portrait_renderer')

# Skin tone palette (light to dark)
SKIN_TONES = ['#FDBCB4', '#F1C27D', '#E0AC69', '#C68642', '#8D5524']

# Hair colour palette
HAIR_COLOURS = ['#2C1810', '#7B3F00', '#C4A35A', '#F4D03F', '#7F8C8D', '#FFFFFF']

# Eye colour palette
EYE_COLOURS = ['#3B2314', '#2E86AB', '#5B8C5A', '#7B6D8D']

# Background dark tones for portrait backing circle
BG_TONES = ['#2C3E50', '#34495E', '#3D2B1F', '#1A3A2A', '#2D2040', '#3B2020']

# Tunic/robe color palette
ROBE_COLOURS = ['#6B3A2A', '#2A4A6B', '#2A5A2A', '#5A2A5A', '#5A4A1A', '#3A3A5A']


# ---------------------------------------------------------------------------
# Age tier helpers
# ---------------------------------------------------------------------------

def _age_tier(age: int) -> str:
    """Return 'child', 'young', 'middle', or 'elder'."""
    if age < 15:
        return 'child'
    if age < 35:
        return 'young'
    if age < 60:
        return 'middle'
    return 'elder'


# ---------------------------------------------------------------------------
# Trait → visual parameter resolution
# ---------------------------------------------------------------------------

def _resolve_visual_params(traits_lower: list, age: int, gender_lower: str,
                            rng: random.Random) -> dict:
    """Map traits and age to visual parameters used when drawing the portrait."""
    tier = _age_tier(age)

    # --- Jaw / face width ---
    base_jaw = 38
    if tier == 'child':
        jaw_width = base_jaw - 8   # rounder, softer
    elif tier == 'elder':
        jaw_width = base_jaw - 4   # thinner with age
    else:
        jaw_width = base_jaw

    if 'brave' in traits_lower or 'wrathful' in traits_lower:
        jaw_width += 5  # sharp, strong jawline
    if 'ambitious' in traits_lower:
        jaw_width += 3  # prominent cheekbones effect

    # --- Eye vertical radius (ry) ---
    eye_ry = 5
    if 'shrewd' in traits_lower or 'greedy' in traits_lower:
        eye_ry = 3   # narrowed eyes
    if 'paranoid' in traits_lower:
        eye_ry = 7   # wide-eyed
    if 'pious' in traits_lower:
        eye_ry = max(eye_ry - 1, 2)  # slight downward, calm
    if 'heavy_eyelids' in traits_lower or 'slothful' in traits_lower:
        eye_ry = max(eye_ry - 1, 2)  # heavy, drooping
    if tier == 'child':
        eye_ry = min(eye_ry + 2, 7)  # bigger eyes for children

    # --- Brow modifier ---
    # 'furrowed' brow: paranoid, wrathful, shrewd
    brow_furrowed = any(t in traits_lower for t in ('paranoid', 'wrathful', 'shrewd'))
    # 'raised' brow: ambitious (one side raised)
    brow_raised = 'ambitious' in traits_lower and not brow_furrowed

    # --- Mouth type ---
    if 'kind' in traits_lower or 'lustful' in traits_lower:
        mouth_type = 'smile'
    elif 'cruel' in traits_lower or 'wrathful' in traits_lower:
        mouth_type = 'frown'
    elif 'pious' in traits_lower:
        mouth_type = 'pious_neutral'
    else:
        mouth_type = 'neutral'

    # --- Lip fullness (lustful → fuller) ---
    lip_full = 'lustful' in traits_lower

    # --- Smirk (greedy) ---
    mouth_smirk = 'greedy' in traits_lower and mouth_type == 'neutral'
    if mouth_smirk:
        mouth_type = 'smirk'

    # --- Heavy eyelids (slothful) ---
    draw_heavy_lids = 'slothful' in traits_lower or 'ill' in traits_lower

    # --- Wrinkles ---
    draw_wrinkles = tier in ('middle', 'elder')
    wrinkle_depth = 'deep' if tier == 'elder' else 'light'

    # --- Grey/white hair for elder ---
    if tier == 'elder':
        hair_colour = rng.choice(['#7F8C8D', '#AAAAAA', '#FFFFFF'])
    elif tier == 'child':
        # Children lighter hair shades
        hair_colour = rng.choice(HAIR_COLOURS[1:5])
    else:
        hair_colour = rng.choice(HAIR_COLOURS[:5])

    # --- Beard logic (males) ---
    if gender_lower == 'male' and tier not in ('child',):
        if tier == 'middle':
            draw_beard = rng.random() > 0.35  # more likely in middle age
        elif tier == 'elder':
            draw_beard = rng.random() > 0.25  # very likely elder beard
        else:
            draw_beard = rng.random() > 0.55
    else:
        draw_beard = False

    # --- Dark circles (ill) ---
    draw_dark_circles = 'ill' in traits_lower

    # --- Skin overlay (ill / elder) ---
    skin_overlay = tier == 'elder' or 'ill' in traits_lower

    return {
        'jaw_width': jaw_width,
        'eye_ry': eye_ry,
        'brow_furrowed': brow_furrowed,
        'brow_raised': brow_raised,
        'mouth_type': mouth_type,
        'lip_full': lip_full,
        'draw_heavy_lids': draw_heavy_lids,
        'draw_wrinkles': draw_wrinkles,
        'wrinkle_depth': wrinkle_depth,
        'hair_colour': hair_colour,
        'draw_beard': draw_beard,
        'draw_dark_circles': draw_dark_circles,
        'skin_overlay': skin_overlay,
        'tier': tier,
    }


# ---------------------------------------------------------------------------
# Accessory selector
# ---------------------------------------------------------------------------

def _choose_accessory(person_id: int, rng: random.Random, gender_lower: str,
                      traits_lower: list, is_monarch: bool) -> str:
    """Choose a head accessory: crown, helm, hood, veil, circlet, or bare."""
    if is_monarch:
        return 'crown'
    if gender_lower == 'male':
        return rng.choice(['helm', 'hood', 'bare', 'bare', 'circlet'])
    else:
        return rng.choice(['veil', 'circlet', 'bare', 'bare', 'crown'])


# ---------------------------------------------------------------------------
# SVG drawing helpers
# ---------------------------------------------------------------------------

def _bg_circle_svg(person_id: int, rng: random.Random) -> str:
    """Draw a subtle dark-toned background circle behind the portrait face."""
    bg_color = rng.choice(BG_TONES)
    return (
        f'<circle cx="80" cy="105" r="72" fill="{bg_color}" opacity="0.35"/>'
    )


def _neck_and_robe_svg(jaw_width: int, rng: random.Random) -> str:
    """Draw a simple neck column and robe/tunic collar below the face."""
    robe_color = rng.choice(ROBE_COLOURS)
    neck_w = 18
    neck_top = 148
    neck_bot = 175
    collar_w = jaw_width + 22
    return (
        # Neck
        f'<rect x="{80 - neck_w // 2}" y="{neck_top}" width="{neck_w}" height="{neck_bot - neck_top}" '
        f'rx="4" fill="#C68642" opacity="0.8"/>'
        # Robe/tunic body
        f'<path d="M{80 - collar_w // 2},{neck_bot} Q{80 - collar_w // 2 - 10},200 {80 - collar_w // 2 - 5},200 '
        f'L{80 + collar_w // 2 + 5},200 Q{80 + collar_w // 2 + 10},200 {80 + collar_w // 2},{neck_bot} Z" '
        f'fill="{robe_color}"/>'
        # Collar V-notch
        f'<path d="M{80 - 12},{neck_bot - 2} L80,{neck_bot + 10} L{80 + 12},{neck_bot - 2}" '
        f'fill="{robe_color}" stroke="{robe_color}" stroke-width="2"/>'
        # Collar edge line
        f'<path d="M{80 - collar_w // 2},{neck_bot} Q{80 - collar_w // 2 - 10},200 {80 - collar_w // 2 - 5},200" '
        f'stroke="#333" stroke-width="1" fill="none" opacity="0.5"/>'
        f'<path d="M{80 + collar_w // 2},{neck_bot} Q{80 + collar_w // 2 + 10},200 {80 + collar_w // 2 + 5},200" '
        f'stroke="#333" stroke-width="1" fill="none" opacity="0.5"/>'
    )


def _accessory_svg(accessory: str, jaw_width: int, hair_colour: str) -> str:
    """Return SVG for the chosen head accessory."""
    if accessory == 'crown':
        return (
            '<polygon points="55,62 65,48 72,58 80,44 88,58 95,48 105,62" '
            'fill="#DAA520" stroke="#B8860B" stroke-width="1.5"/>'
        )
    elif accessory == 'helm':
        # Simple rounded helm
        cx, top_y = 80, 55
        return (
            f'<ellipse cx="{cx}" cy="{top_y + 8}" rx="{jaw_width + 6}" ry="20" fill="#888"/>'
            f'<rect x="{cx - jaw_width - 4}" y="{top_y + 8}" width="{2 * (jaw_width + 4)}" height="14" fill="#999"/>'
            # Nasal guard
            f'<rect x="{cx - 2}" y="{top_y + 10}" width="4" height="22" rx="2" fill="#777"/>'
        )
    elif accessory == 'hood':
        return (
            f'<path d="M{80 - jaw_width - 12},75 Q{80 - jaw_width - 8},48 80,44 '
            f'Q{80 + jaw_width + 8},48 {80 + jaw_width + 12},75" '
            f'fill="{hair_colour}" opacity="0.7" stroke="#333" stroke-width="1"/>'
            # Hood drape sides
            f'<rect x="{80 - jaw_width - 14}" y="74" width="14" height="60" rx="4" fill="{hair_colour}" opacity="0.6"/>'
            f'<rect x="{80 + jaw_width}" y="74" width="14" height="60" rx="4" fill="{hair_colour}" opacity="0.6"/>'
        )
    elif accessory == 'veil':
        return (
            f'<path d="M{80 - jaw_width - 8},65 Q80,48 {80 + jaw_width + 8},65" '
            f'stroke="#DDD" stroke-width="2" fill="#EEE" opacity="0.55"/>'
            f'<rect x="{80 - jaw_width - 8}" y="65" width="14" height="70" rx="4" fill="#DDD" opacity="0.35"/>'
            f'<rect x="{80 + jaw_width - 6}" y="65" width="14" height="70" rx="4" fill="#DDD" opacity="0.35"/>'
        )
    elif accessory == 'circlet':
        return (
            f'<ellipse cx="80" cy="67" rx="{jaw_width - 2}" ry="7" '
            'fill="none" stroke="#DAA520" stroke-width="4"/>'
            '<circle cx="80" cy="62" r="5" fill="#DAA520"/>'
            '<circle cx="65" cy="64" r="3" fill="#DAA520"/>'
            '<circle cx="95" cy="64" r="3" fill="#DAA520"/>'
        )
    return ''  # bare


def _brow_svg(brow_furrowed: bool, brow_raised: bool, jaw_width: int) -> str:
    """Return SVG for eyebrows based on expression."""
    # Brow positions relative to jaw_width
    lx1, lx2 = 58, 74
    rx1, rx2 = 86, 102
    by = 90

    if brow_furrowed:
        # Both brows drawn inward/downward toward center
        return (
            f'<path d="M{lx1} {by + 3} Q{lx2 - 4} {by - 3} {lx2} {by + 1}" '
            f'stroke="#5C4033" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
            f'<path d="M{rx1} {by + 1} Q{rx1 + 4} {by - 3} {rx2} {by + 3}" '
            f'stroke="#5C4033" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        )
    elif brow_raised:
        # One brow (right) subtly arched higher
        return (
            f'<path d="M{lx1} {by} Q{(lx1 + lx2)//2} {by - 4} {lx2} {by}" '
            f'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
            f'<path d="M{rx1} {by - 3} Q{(rx1 + rx2)//2} {by - 8} {rx2} {by - 3}" '
            f'stroke="#5C4033" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        )
    else:
        # Default neutral brows
        return (
            f'<path d="M{lx1} {by} Q{(lx1 + lx2)//2} {by - 3} {lx2} {by}" '
            f'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
            f'<path d="M{rx1} {by} Q{(rx1 + rx2)//2} {by - 3} {rx2} {by}" '
            f'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )


def _heavy_lids_svg(eye_ry: int) -> str:
    """Draw heavy upper eyelid covers over both eyes."""
    return (
        # Left lid cover (upper half of eye, drooping)
        f'<path d="M58 98 Q65 {98 - eye_ry - 1} 72 98" '
        f'fill="#C68642" opacity="0.55"/>'
        # Right lid cover
        f'<path d="M88 98 Q95 {98 - eye_ry - 1} 102 98" '
        f'fill="#C68642" opacity="0.55"/>'
    )


def _wrinkle_svg(depth: str) -> str:
    """Return wrinkle lines appropriate for middle-aged or elder characters."""
    base_opacity = '0.5' if depth == 'deep' else '0.3'
    svg = (
        # Crow's feet
        f'<line x1="53" y1="96" x2="57" y2="100" stroke="#C68642" stroke-width="1" opacity="{base_opacity}"/>'
        f'<line x1="53" y1="100" x2="57" y2="103" stroke="#C68642" stroke-width="1" opacity="{base_opacity}"/>'
        f'<line x1="107" y1="96" x2="103" y2="100" stroke="#C68642" stroke-width="1" opacity="{base_opacity}"/>'
        f'<line x1="107" y1="100" x2="103" y2="103" stroke="#C68642" stroke-width="1" opacity="{base_opacity}"/>'
        # Forehead lines
        f'<path d="M65 82 Q80 79 95 82" stroke="#C68642" stroke-width="1" fill="none" opacity="{base_opacity}"/>'
    )
    if depth == 'deep':
        # Extra nasolabial folds and deeper forehead for elder
        svg += (
            f'<path d="M64 82 Q80 77 96 82" stroke="#C68642" stroke-width="1" fill="none" opacity="0.35"/>'
            f'<path d="M62 113 Q65 125 68 130" stroke="#C68642" stroke-width="1" fill="none" opacity="0.4"/>'
            f'<path d="M98 113 Q95 125 92 130" stroke="#C68642" stroke-width="1" fill="none" opacity="0.4"/>'
        )
    return svg


def _mouth_svg(mouth_type: str, lip_full: bool = False) -> str:
    """Return an SVG path for the mouth based on type."""
    lip_extra = 2 if lip_full else 0
    if mouth_type == 'smile':
        return (
            f'<path d="M68 128 Q80 {137 + lip_extra} 92 128" '
            'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_type == 'frown':
        return (
            f'<path d="M68 133 Q80 {125 - lip_extra} 92 133" '
            'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_type == 'smirk':
        # Asymmetric: right corner raised
        return (
            '<path d="M68 131 Q78 132 90 126" '
            'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_type == 'pious_neutral':
        # Slightly pursed, calm
        return (
            '<line x1="71" y1="130" x2="89" y2="130" '
            'stroke="#5C4033" stroke-width="1.5" stroke-linecap="round"/>'
        )
    else:
        return (
            '<line x1="70" y1="130" x2="90" y2="130" '
            'stroke="#5C4033" stroke-width="2" stroke-linecap="round"/>'
        )


def _crown_svg() -> str:
    """Return a simple SVG crown shape drawn above the hair area."""
    return (
        '<polygon points="55,62 65,48 72,58 80,44 88,58 95,48 105,62" '
        'fill="#DAA520" stroke="#B8860B" stroke-width="1.5"/>'
    )


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_portrait(person_id: int, traits: list, age: int, gender: str,
                      width: int = 160, height: int = 200,
                      is_monarch: bool = False) -> str:
    """Generate a deterministic procedural SVG portrait for a character.

    The portrait is fully self-contained SVG with no external assets or JS.
    The same inputs always produce the same output.

    Args:
        person_id: Unique person identifier used to seed the RNG.
        traits: List of trait strings (e.g. ['brave', 'kind', 'shrewd']).
        age: Character age in years.
        gender: 'MALE' or 'FEMALE' (case-insensitive).
        width: Output SVG width in pixels (default 160).
        height: Output SVG height in pixels (default 200).
        is_monarch: If True, always place a crown accessory (default False).

    Returns:
        A complete SVG string starting with <svg and ending with </svg>.
    """
    rng = random.Random(person_id)
    traits_lower = [t.lower() for t in (traits or [])]
    gender_lower = gender.lower() if gender else 'male'

    # Resolve all visual parameters from traits/age
    vp = _resolve_visual_params(traits_lower, age, gender_lower, rng)
    jaw_width = vp['jaw_width']
    eye_ry = vp['eye_ry']
    hair_colour = vp['hair_colour']

    # --- Skin tone ---
    skin = rng.choice(SKIN_TONES)

    # --- Eye colour ---
    eye_colour = rng.choice(EYE_COLOURS)

    # --- Accessory ---
    accessory = _choose_accessory(person_id, rng, gender_lower, traits_lower, is_monarch)

    # Build SVG parts
    parts = []

    # SVG opening tag
    parts.append(
        f'<svg viewBox="0 0 160 200" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
    )

    # Parchment-style background
    parts.append('<rect width="160" height="200" fill="#f0e6d3" rx="8"/>')

    # Subtle tinted background circle behind face
    parts.append(_bg_circle_svg(person_id, rng))

    # --- Neck and robe/tunic collar (drawn first, behind everything) ---
    parts.append(_neck_and_robe_svg(jaw_width, rng))

    # --- Accessory behind hair ---
    acc_svg = _accessory_svg(accessory, jaw_width, hair_colour)
    parts.append(acc_svg)

    # --- Hair (behind face) ---
    if vp['tier'] == 'child':
        # Shorter, rounder hair for children
        if gender_lower == 'female':
            parts.append(
                f'<ellipse cx="80" cy="102" rx="{jaw_width + 8}" ry="55" fill="{hair_colour}"/>'
            )
        else:
            parts.append(
                f'<ellipse cx="80" cy="70" rx="{jaw_width + 2}" ry="26" fill="{hair_colour}"/>'
            )
    elif gender_lower == 'female':
        # Long hair: extends below face
        parts.append(
            f'<ellipse cx="80" cy="108" rx="{jaw_width + 10}" ry="68" fill="{hair_colour}"/>'
        )
        parts.append(
            f'<ellipse cx="38" cy="130" rx="16" ry="40" fill="{hair_colour}"/>'
        )
        parts.append(
            f'<ellipse cx="122" cy="130" rx="16" ry="40" fill="{hair_colour}"/>'
        )
    else:
        # Short male hair
        parts.append(
            f'<ellipse cx="80" cy="72" rx="{jaw_width + 4}" ry="32" fill="{hair_colour}"/>'
        )

    # --- Face oval ---
    # Elder: slightly narrower/longer face
    face_rx = jaw_width
    face_ry = 55 if vp['tier'] != 'child' else 48
    if vp['tier'] == 'elder':
        face_ry = 57  # slightly elongated
    parts.append(
        f'<ellipse cx="80" cy="105" rx="{face_rx}" ry="{face_ry}" fill="{skin}"/>'
    )

    # Skin overlay for ill/elder
    if vp['skin_overlay']:
        parts.append(
            f'<ellipse cx="80" cy="105" rx="{face_rx}" ry="{face_ry}" '
            f'fill="white" opacity="0.22"/>'
        )

    # --- Dark circles (ill) ---
    if vp['draw_dark_circles']:
        parts.append(
            '<ellipse cx="65" cy="101" rx="9" ry="4" fill="#6B4F3A" opacity="0.35"/>'
        )
        parts.append(
            '<ellipse cx="95" cy="101" rx="9" ry="4" fill="#6B4F3A" opacity="0.35"/>'
        )

    # --- Eyebrows ---
    parts.append(_brow_svg(vp['brow_furrowed'], vp['brow_raised'], jaw_width))

    # --- Eyes ---
    parts.append(f'<ellipse cx="65" cy="98" rx="7" ry="{eye_ry}" fill="white"/>')
    parts.append(f'<ellipse cx="65" cy="98" rx="4" ry="{max(eye_ry - 1, 2)}" fill="{eye_colour}"/>')
    parts.append('<ellipse cx="65" cy="98" rx="2" ry="2" fill="#111"/>')

    parts.append(f'<ellipse cx="95" cy="98" rx="7" ry="{eye_ry}" fill="white"/>')
    parts.append(f'<ellipse cx="95" cy="98" rx="4" ry="{max(eye_ry - 1, 2)}" fill="{eye_colour}"/>')
    parts.append('<ellipse cx="95" cy="98" rx="2" ry="2" fill="#111"/>')

    # Pious downward gaze: pupil shifted slightly down
    if 'pious' in traits_lower:
        parts.append('<ellipse cx="65" cy="99" rx="2" ry="2" fill="#111"/>')
        parts.append('<ellipse cx="95" cy="99" rx="2" ry="2" fill="#111"/>')

    # Heavy eyelids for slothful/ill
    if vp['draw_heavy_lids']:
        parts.append(_heavy_lids_svg(eye_ry))

    # --- Nose ---
    parts.append(
        '<path d="M78 106 L75 118 Q80 121 85 118 L82 106" '
        'fill="none" stroke="#C68642" stroke-width="1.2" opacity="0.6"/>'
    )

    # --- Mouth ---
    parts.append(_mouth_svg(vp['mouth_type'], vp['lip_full']))

    # --- Beard ---
    if vp['draw_beard']:
        parts.append(
            f'<ellipse cx="80" cy="147" rx="{jaw_width - 10}" ry="10" '
            f'fill="{hair_colour}" opacity="0.85"/>'
        )
        # Middle-aged: fuller beard patch
        if vp['tier'] == 'middle':
            parts.append(
                f'<ellipse cx="80" cy="138" rx="{jaw_width - 16}" ry="7" '
                f'fill="{hair_colour}" opacity="0.6"/>'
            )

    # --- Wrinkles ---
    if vp['draw_wrinkles']:
        parts.append(_wrinkle_svg(vp['wrinkle_depth']))

    parts.append('</svg>')

    svg = '\n'.join(parts)
    logger.debug(
        f"Generated portrait for person_id={person_id} age={age} gender={gender} "
        f"tier={vp['tier']} traits={traits_lower} length={len(svg)}"
    )
    return svg
