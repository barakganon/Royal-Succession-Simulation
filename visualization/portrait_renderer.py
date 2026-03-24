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


def generate_portrait(person_id: int, traits: list, age: int, gender: str,
                      width: int = 160, height: int = 200) -> str:
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

    Returns:
        A complete SVG string starting with <svg and ending with </svg>.
    """
    rng = random.Random(person_id)
    traits_lower = [t.lower() for t in (traits or [])]
    gender_lower = gender.lower() if gender else 'male'

    # --- Skin tone ---
    skin = rng.choice(SKIN_TONES)
    # Ill or very old: slightly desaturate/lighten via an opacity overlay
    skin_overlay = None
    if 'ill' in traits_lower or age > 60:
        skin_overlay = 'rgba(255,255,255,0.25)'

    # --- Hair colour ---
    if age > 60:
        hair_colour = rng.choice(['#7F8C8D', '#FFFFFF'])
    else:
        hair_colour = rng.choice(HAIR_COLOURS[:5])  # exclude white/grey for young

    # --- Eye colour ---
    eye_colour = rng.choice(EYE_COLOURS)

    # --- Jaw width (affects face ellipse rx) ---
    base_jaw = 38
    if 'brave' in traits_lower:
        jaw_width = base_jaw + 6
    elif age < 20:
        jaw_width = base_jaw - 4  # younger = rounder/narrower
    else:
        jaw_width = base_jaw

    # --- Crown ---
    draw_crown = rng.random() > 0.7

    # --- Beard (males only, adult) ---
    draw_beard = (gender_lower == 'male' and age >= 18 and rng.random() > 0.5)

    # --- Eye shape: shrewd → narrower ---
    eye_ry = 5
    if 'shrewd' in traits_lower:
        eye_ry = 3
    if age < 20:
        eye_ry = min(eye_ry + 1, 6)

    # --- Mouth curve ---
    if 'kind' in traits_lower:
        mouth_type = 'smile'
    elif 'cruel' in traits_lower:
        mouth_type = 'frown'
    else:
        mouth_type = 'neutral'

    # --- Wrinkles for elderly ---
    draw_wrinkles = age > 60

    # --- Dark circles for ill ---
    draw_dark_circles = 'ill' in traits_lower

    # Build SVG parts
    parts = []

    # SVG opening tag
    parts.append(
        f'<svg viewBox="0 0 160 200" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
    )

    # Parchment-style background
    parts.append('<rect width="160" height="200" fill="#f0e6d3" rx="8"/>')

    # --- Crown (drawn behind hair) ---
    if draw_crown:
        parts.append(_crown_svg())

    # --- Hair (behind face) ---
    if gender_lower == 'female':
        # Long hair: extends below face
        parts.append(
            f'<ellipse cx="80" cy="108" rx="{jaw_width + 10}" ry="68" fill="{hair_colour}"/>'
        )
        # Side hair extensions
        parts.append(
            f'<ellipse cx="38" cy="130" rx="16" ry="40" fill="{hair_colour}"/>'
        )
        parts.append(
            f'<ellipse cx="122" cy="130" rx="16" ry="40" fill="{hair_colour}"/>'
        )
    else:
        # Short male hair — cap above and sides of head
        parts.append(
            f'<ellipse cx="80" cy="72" rx="{jaw_width + 4}" ry="32" fill="{hair_colour}"/>'
        )

    # --- Face oval ---
    parts.append(
        f'<ellipse cx="80" cy="105" rx="{jaw_width}" ry="55" fill="{skin}"/>'
    )

    # Skin overlay for ill/old
    if skin_overlay:
        parts.append(
            f'<ellipse cx="80" cy="105" rx="{jaw_width}" ry="55" '
            f'fill="white" opacity="0.22"/>'
        )

    # --- Dark circles (ill) ---
    if draw_dark_circles:
        parts.append(
            '<ellipse cx="65" cy="101" rx="9" ry="4" fill="#6B4F3A" opacity="0.35"/>'
        )
        parts.append(
            '<ellipse cx="95" cy="101" rx="9" ry="4" fill="#6B4F3A" opacity="0.35"/>'
        )

    # --- Eyes ---
    # Left eye
    parts.append(
        f'<ellipse cx="65" cy="98" rx="7" ry="{eye_ry}" fill="white"/>'
    )
    parts.append(
        f'<ellipse cx="65" cy="98" rx="4" ry="{max(eye_ry - 1, 2)}" fill="{eye_colour}"/>'
    )
    parts.append(
        '<ellipse cx="65" cy="98" rx="2" ry="2" fill="#111"/>'
    )
    # Right eye
    parts.append(
        f'<ellipse cx="95" cy="98" rx="7" ry="{eye_ry}" fill="white"/>'
    )
    parts.append(
        f'<ellipse cx="95" cy="98" rx="4" ry="{max(eye_ry - 1, 2)}" fill="{eye_colour}"/>'
    )
    parts.append(
        '<ellipse cx="95" cy="98" rx="2" ry="2" fill="#111"/>'
    )

    # Shrewd raised-brow lines
    if 'shrewd' in traits_lower:
        parts.append(
            '<path d="M58 91 Q65 88 72 91" stroke="#5C4033" stroke-width="1.5" fill="none"/>'
        )
        parts.append(
            '<path d="M88 91 Q95 88 102 91" stroke="#5C4033" stroke-width="1.5" fill="none"/>'
        )

    # --- Nose ---
    parts.append(
        '<path d="M78 106 L75 118 Q80 121 85 118 L82 106" '
        'fill="none" stroke="#C68642" stroke-width="1.2" opacity="0.6"/>'
    )

    # --- Mouth ---
    parts.append(_mouth_svg(mouth_type))

    # --- Beard ---
    if draw_beard:
        parts.append(
            f'<ellipse cx="80" cy="147" rx="{jaw_width - 10}" ry="10" '
            f'fill="{hair_colour}" opacity="0.85"/>'
        )

    # --- Wrinkles ---
    if draw_wrinkles:
        # Crow's feet beside each eye
        parts.append(
            '<line x1="53" y1="96" x2="57" y2="100" stroke="#C68642" stroke-width="1" opacity="0.5"/>'
        )
        parts.append(
            '<line x1="53" y1="100" x2="57" y2="103" stroke="#C68642" stroke-width="1" opacity="0.5"/>'
        )
        parts.append(
            '<line x1="107" y1="96" x2="103" y2="100" stroke="#C68642" stroke-width="1" opacity="0.5"/>'
        )
        parts.append(
            '<line x1="107" y1="100" x2="103" y2="103" stroke="#C68642" stroke-width="1" opacity="0.5"/>'
        )
        # Forehead line
        parts.append(
            '<path d="M65 82 Q80 79 95 82" stroke="#C68642" stroke-width="1" fill="none" opacity="0.4"/>'
        )

    parts.append('</svg>')

    svg = '\n'.join(parts)
    logger.debug(
        f"Generated portrait for person_id={person_id} age={age} gender={gender} "
        f"traits={traits_lower} length={len(svg)}"
    )
    return svg


def _mouth_svg(mouth_type: str) -> str:
    """Return an SVG path for the mouth based on type (smile/frown/neutral)."""
    if mouth_type == 'smile':
        # Upward arc
        return (
            '<path d="M68 128 Q80 137 92 128" '
            'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_type == 'frown':
        # Downward arc
        return (
            '<path d="M68 133 Q80 125 92 133" '
            'stroke="#5C4033" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    else:
        # Neutral line
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
