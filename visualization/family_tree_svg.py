"""Procedural SVG family-tree renderer.

Renders a dynasty's family tree as a single, self-contained parchment SVG.
Layout is a pure-Python Reingold-Tilford-style tidy tree (no networkx /
graphviz / matplotlib, no new pip deps) so output is deterministic for a
given set of persons.

Mirrors visualization/map_renderer.py generate_geojson(dynasty_id, session):
the function takes a SQLAlchemy session and queries the DB via
``session.query(PersonDB)...`` rather than the bound ``PersonDB.query``.

Public entrypoint: ``generate_family_tree_svg``.
"""
import logging
import html

logger = logging.getLogger('royal_succession.family_tree_svg')

# ---------------------------------------------------------------------------
# Palette — parchment background, dark-brown strokes, gold crown.
# ---------------------------------------------------------------------------
PALETTE = {
    'parchment': '#f4ecd8',
    'parchment_edge': '#e6dabb',
    'card_fill': '#faf4e4',
    'card_fill_dead': '#e7e0cf',
    'stroke': '#5a4326',          # dark brown
    'stroke_dead': '#9b9078',     # muted gray-brown for deceased
    'edge': '#7a5c30',            # parent-child / marriage lines
    'edge_cross': '#a07b3a',      # cross-dynasty marriage
    'gold': '#c8a200',            # crown
    'text': '#3a2c16',
    'text_muted': '#8a8068',
    'text_dates': '#6a5a3a',
}

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_CARD_W = 150
_CARD_H = 56
_H_GAP = 28           # horizontal gap between adjacent subtree slots
_V_GAP = 70           # vertical gap between generation rows
_SPOUSE_GAP = 14      # gap between a person card and the adjacent spouse card
_MARGIN = 40          # outer SVG margin
_SLOT = _CARD_W + _H_GAP   # horizontal slot width for one leaf node


# ---------------------------------------------------------------------------
# Private helpers (mirror the _helper() fragment style of the other renderers)
# ---------------------------------------------------------------------------

def _esc(value) -> str:
    """XML-escape a value for safe inclusion in SVG text nodes."""
    if value is None:
        return ''
    return html.escape(str(value), quote=True)


def _minimal_svg(width: int = 320, height: int = 160,
                 message: str = 'No family tree available') -> str:
    """Return a minimal but valid parchment SVG (empty dynasty / error case)."""
    w, h = max(width, 80), max(height, 60)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" style="display:block;">'
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" '
        f'fill="{PALETTE["parchment"]}" stroke="{PALETTE["parchment_edge"]}" stroke-width="2"/>'
        f'<text x="{w // 2}" y="{h // 2}" text-anchor="middle" '
        f'font-family="Georgia,serif" font-size="14" fill="{PALETTE["text_muted"]}">'
        f'{_esc(message)}</text>'
        f'</svg>'
    )


def _life_dates(p, current_year) -> str:
    """Return the life-dates label, e.g. 'b.1250-d.1300' or 'b.1250-'."""
    birth = p.birth_year if p.birth_year is not None else '?'
    if p.death_year is not None:
        return f'b.{birth}-d.{p.death_year}'
    return f'b.{birth}-'


def _crown_svg(cx: float, top_y: float) -> str:
    """Small gold heraldic crown drawn above a monarch's card."""
    return (
        f'<polygon points="'
        f'{cx - 14:.1f},{top_y:.1f} {cx - 9:.1f},{top_y - 10:.1f} '
        f'{cx - 4:.1f},{top_y - 3:.1f} {cx:.1f},{top_y - 13:.1f} '
        f'{cx + 4:.1f},{top_y - 3:.1f} {cx + 9:.1f},{top_y - 10:.1f} '
        f'{cx + 14:.1f},{top_y:.1f}" '
        f'fill="{PALETTE["gold"]}" stroke="{PALETTE["stroke"]}" stroke-width="0.8"/>'
    )


def _node_svg(p, x: float, y: float) -> str:
    """Draw one person card as a <g> with data-person-id and contents.

    x, y is the top-left corner of the card.
    """
    is_dead = p.death_year is not None
    fill = PALETTE['card_fill_dead'] if is_dead else PALETTE['card_fill']
    stroke = PALETTE['stroke_dead'] if is_dead else PALETTE['stroke']
    name_color = PALETTE['text_muted'] if is_dead else PALETTE['text']
    opacity = '0.6' if is_dead else '1'

    cx = x + _CARD_W / 2.0
    full_name = f'{p.name or ""} {p.surname or ""}'.strip()
    dates = _life_dates(p, None)

    father_id = getattr(p, 'father_sim_id', None)
    mother_id = getattr(p, 'mother_sim_id', None)
    spouse_id = getattr(p, 'spouse_sim_id', None)

    parts = [
        f'<g data-person-id="{p.id}" '
        f'data-father-id="{father_id if father_id is not None else ""}" '
        f'data-mother-id="{mother_id if mother_id is not None else ""}" '
        f'data-spouse-id="{spouse_id if spouse_id is not None else ""}" '
        f'opacity="{opacity}">'
    ]

    # Card body
    parts.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{_CARD_W}" height="{_CARD_H}" rx="8" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    )

    # Optional embedded portrait (scaled into a small box on the left).
    portrait = getattr(p, 'portrait_svg', None)
    px = x + 6
    py = y + 6
    pbox = _CARD_H - 12
    if portrait and isinstance(portrait, str) and portrait.lstrip().startswith('<svg'):
        # Embed the existing portrait SVG, scaled into the card's portrait box.
        parts.append(
            f'<svg x="{px:.1f}" y="{py:.1f}" width="{pbox}" height="{pbox}" '
            f'viewBox="0 0 160 200" preserveAspectRatio="xMidYMid meet">'
            f'{portrait}</svg>'
        )
    else:
        # Placeholder bust.
        parts.append(
            f'<circle cx="{px + pbox / 2:.1f}" cy="{py + pbox * 0.4:.1f}" r="{pbox * 0.22:.1f}" '
            f'fill="{stroke}" opacity="0.45"/>'
            f'<path d="M{px + pbox * 0.15:.1f},{py + pbox:.1f} '
            f'Q{px + pbox / 2:.1f},{py + pbox * 0.55:.1f} '
            f'{px + pbox * 0.85:.1f},{py + pbox:.1f} Z" '
            f'fill="{stroke}" opacity="0.45"/>'
        )

    # Text block (name + dates), to the right of the portrait box.
    text_x = x + pbox + 12
    parts.append(
        f'<text x="{text_x:.1f}" y="{y + 24:.1f}" '
        f'font-family="Georgia,serif" font-size="12" font-weight="bold" '
        f'fill="{name_color}">{_esc(full_name)}</text>'
    )
    parts.append(
        f'<text x="{text_x:.1f}" y="{y + 42:.1f}" '
        f'font-family="Georgia,serif" font-size="10" '
        f'fill="{PALETTE["text_dates"]}">{_esc(dates)}</text>'
    )

    # Crown for monarchs.
    if getattr(p, 'is_monarch', False):
        parts.append(_crown_svg(cx, y - 2))

    parts.append('</g>')
    return ''.join(parts)


def _parent_child_edge(parent_cx: float, parent_bottom: float,
                       child_cx: float, child_top: float) -> str:
    """Solid orthogonal-ish line from a parent card bottom to a child card top."""
    mid_y = (parent_bottom + child_top) / 2.0
    return (
        f'<path d="M{parent_cx:.1f},{parent_bottom:.1f} '
        f'L{parent_cx:.1f},{mid_y:.1f} '
        f'L{child_cx:.1f},{mid_y:.1f} '
        f'L{child_cx:.1f},{child_top:.1f}" '
        f'fill="none" stroke="{PALETTE["edge"]}" stroke-width="1.5"/>'
    )


def _marriage_edge(x1: float, x2: float, y: float, cross_dynasty: bool) -> str:
    """Double parallel line between two spouse cards.

    Dashed when the marriage crosses dynasties.
    """
    color = PALETTE['edge_cross'] if cross_dynasty else PALETTE['edge']
    dash = ' stroke-dasharray="5,3"' if cross_dynasty else ''
    return (
        f'<line x1="{x1:.1f}" y1="{y - 2:.1f}" x2="{x2:.1f}" y2="{y - 2:.1f}" '
        f'stroke="{color}" stroke-width="1.4"{dash}/>'
        f'<line x1="{x1:.1f}" y1="{y + 2:.1f}" x2="{x2:.1f}" y2="{y + 2:.1f}" '
        f'stroke="{color}" stroke-width="1.4"{dash}/>'
    )


# ---------------------------------------------------------------------------
# Generation assignment + tidy layout (pure Python, deterministic)
# ---------------------------------------------------------------------------

def _assign_generations(people_by_id: dict) -> dict:
    """BFS generation assignment.

    Roots = persons whose parents are both absent from this tree -> gen 0.
    Child gen = parent gen + 1 (child located via father/mother sim ids).
    Cycle-guarded with a visited set. Unresolved-parent persons default gen 0.
    """
    ids = set(people_by_id.keys())

    # Children mapping: parent_id -> ordered list of child ids.
    children = {pid: [] for pid in ids}
    for pid in sorted(ids):  # sorted => deterministic ordering
        p = people_by_id[pid]
        f = p.father_sim_id if p.father_sim_id in ids else None
        m = p.mother_sim_id if p.mother_sim_id in ids else None
        for parent in (f, m):
            if parent is not None and pid not in children[parent]:
                children[parent].append(pid)

    # Roots: no in-tree parent.
    roots = []
    for pid in sorted(ids):
        p = people_by_id[pid]
        has_parent = (p.father_sim_id in ids) or (p.mother_sim_id in ids)
        if not has_parent:
            roots.append(pid)

    gen = {}
    visited = set()
    # BFS from roots.
    queue = [(r, 0) for r in roots]
    while queue:
        pid, g = queue.pop(0)
        if pid in visited:
            # Keep the shallowest generation seen.
            if g < gen.get(pid, g):
                gen[pid] = g
            continue
        visited.add(pid)
        gen[pid] = g
        for c in children[pid]:
            if c not in visited:
                queue.append((c, g + 1))

    # Any persons not reached (e.g. orphaned by cycles) default to gen 0.
    for pid in ids:
        if pid not in gen:
            gen[pid] = 0

    return gen, children, roots


def _build_layout(people_by_id: dict, spouse_of: dict):
    """Compute an (x, gen) position for each person id.

    Reingold-Tilford-style tidy pass:
      - x of a leaf is the next free slot (left-to-right).
      - x of an internal node is the average of its children's x.
      - spouses are placed immediately to the right of their partner.
    Returns dict: person_id -> {'x': float, 'gen': int}.
    """
    gen, children, roots = _assign_generations(people_by_id)

    positions = {}
    # Mutable cursor for the next free leaf slot.
    cursor = {'x': 0.0}
    placed = set()

    def place(pid):
        """Post-order placement; returns the node's x."""
        if pid in placed:
            return positions[pid]['x']
        placed.add(pid)

        kids = [c for c in children.get(pid, []) if c not in placed]
        if not kids:
            x = cursor['x']
            cursor['x'] += _SLOT
            positions[pid] = {'x': x, 'gen': gen[pid]}
            _place_spouse(pid)
            return x

        child_xs = [place(c) for c in kids]
        x = sum(child_xs) / len(child_xs)
        positions[pid] = {'x': x, 'gen': gen[pid]}
        _place_spouse(pid)
        return x

    def _place_spouse(pid):
        sp = spouse_of.get(pid)
        # Only lay out an in-tree spouse that hasn't been positioned yet and
        # whose own placement isn't independently driven (avoid double slot).
        if sp is None:
            return
        if sp in placed or sp not in people_by_id:
            return
        # Place spouse immediately to the right, sharing the partner's row.
        placed.add(sp)
        positions[sp] = {
            'x': positions[pid]['x'] + _CARD_W + _SPOUSE_GAP,
            'gen': gen.get(sp, positions[pid]['gen']),
        }
        # Reserve a slot so later leaves don't overlap the spouse card.
        cursor['x'] = max(cursor['x'], positions[sp]['x'] + _SLOT)

    for r in sorted(roots):
        place(r)

    # Any unplaced persons (cycles / detached) get trailing slots.
    for pid in sorted(people_by_id.keys()):
        if pid not in placed:
            placed.add(pid)
            positions[pid] = {'x': cursor['x'], 'gen': gen[pid]}
            cursor['x'] += _SLOT

    return positions, children


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_family_tree_svg(dynasty_id: int, session, current_year=None,
                             show_deceased: bool = True) -> str:
    """Generate a deterministic parchment SVG of a dynasty's family tree.

    Args:
        dynasty_id: ID of the dynasty whose members form the tree.
        session: SQLAlchemy session (queried via session.query(PersonDB)...).
        current_year: Reference year; if None, derived from the dynasty's
            current_simulation_year (fallback to max year present, else 1300).
        show_deceased: When False, only living persons (death_year is None)
            are included.

    Returns:
        One complete, self-contained SVG string. Starts with '<svg', ends with
        '</svg>'. Never raises — empty dynasty or any internal error yields a
        minimal valid parchment SVG.
    """
    try:
        from models.db_models import PersonDB, DynastyDB

        # --- Query persons for this dynasty ---
        q = session.query(PersonDB).filter(PersonDB.dynasty_id == dynasty_id)
        if not show_deceased:
            q = q.filter(PersonDB.death_year.is_(None))
        people = q.all()

        if not people:
            return _minimal_svg(message='No family tree available')

        people_by_id = {p.id: p for p in people}
        in_tree_ids = set(people_by_id.keys())

        # --- Resolve current_year ---
        if current_year is None:
            dynasty = session.get(DynastyDB, dynasty_id)
            current_year = getattr(dynasty, 'current_simulation_year', None) if dynasty else None
        if current_year is None:
            years = [p.birth_year for p in people if p.birth_year is not None]
            years += [p.death_year for p in people if p.death_year is not None]
            current_year = max(years) if years else 1300

        # --- Resolve spouses (may live in another dynasty -> fetch directly) ---
        # spouse_of maps an in-tree person id to their spouse's person id (in-tree
        # or not). spouse_dynasty maps a spouse id to its dynasty_id for cross-
        # dynasty marriage detection.
        spouse_of = {}
        spouse_dynasty = {}
        spouse_obj_by_id = {}
        for p in people:
            sid = p.spouse_sim_id
            if not sid:
                continue
            spouse_of[p.id] = sid
            sp_obj = people_by_id.get(sid)
            if sp_obj is None:
                sp_obj = session.get(PersonDB, sid)
            if sp_obj is not None:
                spouse_dynasty[sid] = sp_obj.dynasty_id
                spouse_obj_by_id[sid] = sp_obj

        # --- Layout (in-tree persons only) ---
        positions, children = _build_layout(people_by_id, spouse_of)

        # --- Satellite spouses (married IN from another dynasty) ---
        # An in-married spouse lives in a different dynasty, so they are not in
        # people_by_id and the tidy layout never positions them. Place each
        # beside their in-tree partner so the (dashed) cross-dynasty marriage
        # edge has both endpoints and the spouse renders as a node. Satellites
        # do NOT participate in generation/subtree layout.
        sat_positions = {}
        satellites = {}
        for p in people:
            sid = p.spouse_sim_id
            if not sid or sid in people_by_id or p.id not in positions:
                continue
            if sid in sat_positions:
                continue
            sp_obj = spouse_obj_by_id.get(sid)
            if sp_obj is None:
                continue
            partner = positions[p.id]
            sat_positions[sid] = {
                'x': partner['x'] + _CARD_W + _SPOUSE_GAP,
                'gen': partner['gen'],
            }
            satellites[sid] = sp_obj

        # Combined views used for sizing, edges and node rendering.
        all_positions = {**positions, **sat_positions}
        all_objs = {**people_by_id, **satellites}

        # Map x/gen to pixel coordinates.
        max_gen = max((pos['gen'] for pos in all_positions.values()), default=0)
        min_x = min((pos['x'] for pos in all_positions.values()), default=0.0)
        max_x = max((pos['x'] for pos in all_positions.values()), default=0.0)

        def px(pos):
            return _MARGIN + (pos['x'] - min_x)

        def py(pos):
            return _MARGIN + pos['gen'] * (_CARD_H + _V_GAP)

        width = int(_MARGIN * 2 + (max_x - min_x) + _CARD_W)
        height = int(_MARGIN * 2 + max_gen * (_CARD_H + _V_GAP) + _CARD_H)

        # --- Build edges (beneath nodes) ---
        edge_parts = []

        # Marriage edges (between spouses both positioned in the tree).
        drawn_marriages = set()
        for pid, sid in spouse_of.items():
            if sid not in all_positions or pid not in all_positions:
                continue
            key = tuple(sorted((pid, sid)))
            if key in drawn_marriages:
                continue
            drawn_marriages.add(key)
            a, b = all_positions[pid], all_positions[sid]
            ax = px(a) + _CARD_W
            bx = px(b)
            # Determine left/right ordering for the connecting segment.
            if px(a) <= px(b):
                x1, x2 = px(a) + _CARD_W, px(b)
            else:
                x1, x2 = px(b) + _CARD_W, px(a)
            y_mid = py(a) + _CARD_H / 2.0
            p_obj = people_by_id.get(pid)
            sp_dyn = spouse_dynasty.get(sid)
            cross = (sp_dyn is not None and p_obj is not None
                     and sp_dyn != p_obj.dynasty_id)
            edge_parts.append(_marriage_edge(x1, x2, y_mid, cross))

        # Parent-child edges.
        for parent_id, kids in children.items():
            if parent_id not in positions:
                continue
            pp = positions[parent_id]
            parent_cx = px(pp) + _CARD_W / 2.0
            parent_bottom = py(pp) + _CARD_H
            for c in kids:
                if c not in positions:
                    continue
                cp = positions[c]
                child_cx = px(cp) + _CARD_W / 2.0
                child_top = py(cp)
                edge_parts.append(
                    _parent_child_edge(parent_cx, parent_bottom, child_cx, child_top)
                )

        # --- Build nodes (on top of edges) ---
        node_parts = []
        for pid in sorted(all_positions.keys()):
            p = all_objs.get(pid)
            if p is None:
                continue
            pos = all_positions[pid]
            node_parts.append(_node_svg(p, px(pos), py(pos)))

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'style="display:block;">'
            f'<rect x="0" y="0" width="{width}" height="{height}" '
            f'fill="{PALETTE["parchment"]}" stroke="{PALETTE["parchment_edge"]}" '
            f'stroke-width="3"/>'
            + ''.join(edge_parts)
            + ''.join(node_parts)
            + '</svg>'
        )

        logger.debug(
            f"Generated family tree for dynasty_id={dynasty_id}: "
            f"{len(people)} persons, gens=0..{max_gen}, "
            f"size={width}x{height}, length={len(svg)}"
        )
        return svg

    except Exception as exc:  # noqa: BLE001 — never raise to the caller
        logger.error(
            f"Family tree generation failed for dynasty_id={dynasty_id}: {exc}",
            exc_info=True,
        )
        return _minimal_svg(message='Family tree unavailable')
