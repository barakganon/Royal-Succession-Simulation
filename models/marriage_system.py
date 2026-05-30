"""MarriageSystem — player-initiated cross-dynasty royal marriages (Story 7-3).

Lets the player browse foreign marriageable nobles, list their own eligible
children, and propose a marriage. Acceptance is decided by the target dynasty's
AI (or auto-accepted for human-controlled targets, mirroring Story 7-2). On
acceptance both spouses are linked, relations warm, and a wedding chronicle line
is logged.

The subsystem constructor takes a SQLAlchemy ``Session`` as its only argument.
All DB writes are wrapped in try/except with rollback, and propose_marriage
never raises — it always returns a result dict.
"""

import logging
import os

from models.db_models import (
    db,
    DynastyDB,
    PersonDB,
    HistoryLogEntryDB,
    MarriageOfferDB,
)

logger = logging.getLogger('royal_succession.marriage_system')


class MarriageSystem:
    """Manage player-initiated cross-dynasty royal marriages."""

    def __init__(self, session):
        self.session = session

    # ------------------------------------------------------------------ #
    # Read helpers
    # ------------------------------------------------------------------ #
    def list_foreign_marriageable(self, dynasty_id, year=None):
        """Foreign nobles eligible for marriage with the requesting dynasty.

        Returns alive, noble, unmarried persons aged 16..55 whose dynasty differs
        from ``dynasty_id``.

        Args:
            dynasty_id: the requesting (player) dynasty's id.
            year: simulation year to compute ages against. When ``None`` it is
                derived from the requesting dynasty's ``current_simulation_year``.

        Returns:
            list of dicts with keys: id, name, surname, gender, age, dynasty_id,
            dynasty_name, traits (list[str]), is_ai (bool).
        """
        results = []
        try:
            if year is None:
                requesting = self.session.query(DynastyDB).get(dynasty_id)
                year = requesting.current_simulation_year if requesting else 0

            candidates = (
                self.session.query(PersonDB)
                .filter(
                    PersonDB.death_year.is_(None),
                    PersonDB.is_noble.is_(True),
                    PersonDB.spouse_sim_id.is_(None),
                    PersonDB.dynasty_id != dynasty_id,
                )
                .all()
            )

            dynasty_cache = {}
            for person in candidates:
                age = (year or 0) - (person.birth_year or 0)
                if age < 16 or age > 55:
                    continue

                dyn = dynasty_cache.get(person.dynasty_id)
                if dyn is None and person.dynasty_id is not None:
                    dyn = self.session.query(DynastyDB).get(person.dynasty_id)
                    dynasty_cache[person.dynasty_id] = dyn

                results.append({
                    'id': person.id,
                    'name': person.name,
                    'surname': person.surname,
                    'gender': person.gender,
                    'age': age,
                    'dynasty_id': person.dynasty_id,
                    'dynasty_name': dyn.name if dyn else '',
                    'traits': list(person.get_traits()),
                    'is_ai': bool(getattr(dyn, 'is_ai_controlled', False)) if dyn else False,
                })
        except Exception as exc:
            logger.warning(
                "list_foreign_marriageable failed for dynasty %s: %s",
                dynasty_id, exc,
            )
        return results

    def eligible_children(self, dynasty_id, target_gender):
        """The requesting dynasty's own nobles eligible to be proposed.

        Returns alive, unmarried nobles of the requesting dynasty aged >= 16 whose
        gender is OPPOSITE the given ``target_gender``.

        Args:
            dynasty_id: the requesting (player) dynasty's id.
            target_gender: gender of the intended foreign spouse; children of the
                opposite gender are returned.

        Returns:
            list of dicts with keys: id, name, surname, gender, age.
        """
        results = []
        try:
            requesting = self.session.query(DynastyDB).get(dynasty_id)
            year = requesting.current_simulation_year if requesting else 0

            opposite = 'FEMALE' if (target_gender or '').upper() == 'MALE' else 'MALE'

            children = (
                self.session.query(PersonDB)
                .filter(
                    PersonDB.dynasty_id == dynasty_id,
                    PersonDB.death_year.is_(None),
                    PersonDB.is_noble.is_(True),
                    PersonDB.spouse_sim_id.is_(None),
                    PersonDB.gender == opposite,
                )
                .all()
            )

            for person in children:
                age = (year or 0) - (person.birth_year or 0)
                if age < 16:
                    continue
                results.append({
                    'id': person.id,
                    'name': person.name,
                    'surname': person.surname,
                    'gender': person.gender,
                    'age': age,
                })
        except Exception as exc:
            logger.warning(
                "eligible_children failed for dynasty %s: %s",
                dynasty_id, exc,
            )
        return results

    # ------------------------------------------------------------------ #
    # Proposal
    # ------------------------------------------------------------------ #
    def propose_marriage(self, proposer_person_id, target_person_id, year):
        """Propose a marriage between the player's child and a foreign noble.

        Validates both persons, records a MarriageOfferDB, asks the target
        dynasty's AI to decide (human targets auto-accept), and on acceptance
        links both spouses, warms relations, and logs a wedding chronicle line.

        Never raises; on error rolls back and returns a result dict with
        ``ok=False``.

        Returns:
            dict with keys: ok (bool), accepted (bool), message (str),
            offer_id (int|None).
        """
        # Lazy imports keep the module importable even if these symbols shift.
        from models.ai_controller import AIController
        from models.diplomacy_system import DiplomacySystem
        from utils.llm_prompts import (
            build_wedding_chronicle_prompt,
            generate_wedding_fallback,
        )

        try:
            proposer = self.session.query(PersonDB).get(proposer_person_id)
            target = self.session.query(PersonDB).get(target_person_id)

            if proposer is None or target is None:
                return {'ok': False, 'accepted': False,
                        'message': 'One of the persons could not be found.',
                        'offer_id': None}
            if proposer.death_year is not None or target.death_year is not None:
                return {'ok': False, 'accepted': False,
                        'message': 'Both betrothed must be living.',
                        'offer_id': None}
            if proposer.spouse_sim_id is not None or target.spouse_sim_id is not None:
                return {'ok': False, 'accepted': False,
                        'message': 'One of the betrothed is already wed.',
                        'offer_id': None}
            if proposer.gender == target.gender:
                return {'ok': False, 'accepted': False,
                        'message': 'A royal marriage requires opposite genders.',
                        'offer_id': None}
            if proposer.dynasty_id == target.dynasty_id:
                return {'ok': False, 'accepted': False,
                        'message': 'The betrothed must belong to different dynasties.',
                        'offer_id': None}

            proposer_dynasty = self.session.query(DynastyDB).get(proposer.dynasty_id)
            target_dynasty = self.session.query(DynastyDB).get(target.dynasty_id)

            offer = MarriageOfferDB(
                proposer_dynasty_id=proposer.dynasty_id,
                target_dynasty_id=target.dynasty_id,
                proposer_person_id=proposer_person_id,
                target_person_id=target_person_id,
                status='pending',
                created_year=year,
            )
            self.session.add(offer)
            self.session.flush()  # assign offer.id

            # Decide acceptance: AI targets consult the controller; human targets
            # auto-accept (mirroring Story 7-2).
            accepted = True
            if target_dynasty is not None and getattr(target_dynasty, 'is_ai_controlled', False):
                relation_score = 0
                relation = DiplomacySystem(self.session).get_diplomatic_relation(
                    proposer.dynasty_id, target.dynasty_id
                )
                if relation is not None:
                    relation_score = relation.relation_score
                ai = AIController(
                    self.session,
                    target.dynasty_id,
                    (target_dynasty.ai_personality or ''),
                )
                accepted = bool(ai.decide_marriage_response({
                    'proposer_dynasty_id': proposer.dynasty_id,
                    'relation_score': relation_score,
                    'proposer_prestige': (proposer_dynasty.prestige or 0) if proposer_dynasty else 0,
                    'own_prestige': (target_dynasty.prestige or 0),
                }))

            if not accepted:
                offer.status = 'rejected'
                self.session.commit()
                return {
                    'ok': True,
                    'accepted': False,
                    'message': (
                        f"House {target.surname or (target_dynasty.name if target_dynasty else '')} "
                        f"politely declined the proposal of marriage."
                    ),
                    'offer_id': offer.id,
                }

            # Accepted — link both spouses.
            proposer.spouse_sim_id = target.id
            target.spouse_sim_id = proposer.id

            # A marriage alliance warms relations between the two houses.
            try:
                alliance_relation = DiplomacySystem(self.session).get_diplomatic_relation(
                    proposer.dynasty_id, target.dynasty_id
                )
                if alliance_relation is not None:
                    alliance_relation.update_relation('marriage_alliance', 30)
            except Exception as relation_exc:
                logger.warning(
                    "Marriage alliance relation bump failed (%s <-> %s): %s",
                    proposer.dynasty_id, target.dynasty_id, relation_exc,
                )

            # Wedding chronicle line — LLM when available, else fallback.
            house1 = proposer.surname or (proposer_dynasty.name if proposer_dynasty else '')
            house2 = target.surname or (target_dynasty.name if target_dynasty else '')
            wedding_text = None
            if self._llm_available():
                try:
                    import google.generativeai as genai
                    from flask import current_app
                    api_key = (
                        current_app.config.get('FLASK_APP_GOOGLE_API_KEY')
                        or os.environ.get('GOOGLE_API_KEY')
                    )
                    if api_key:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = build_wedding_chronicle_prompt(
                            proposer.name,
                            proposer.get_traits(),
                            target.name,
                            target.get_traits(),
                            house1,
                            house2,
                            year,
                        )
                        response = model.generate_content(
                            prompt,
                            generation_config={
                                'max_output_tokens': 150,
                                'temperature': 0.8,
                            },
                        )
                        text = response.text.strip() if response.text else ''
                        if text:
                            wedding_text = text
                except Exception as llm_exc:
                    logger.warning(
                        "Wedding chronicle LLM failed (%s & %s): %s",
                        proposer.name, target.name, llm_exc,
                    )
            if not wedding_text:
                wedding_text = generate_wedding_fallback(
                    proposer.name, target.name, house1, house2, year,
                )

            marriage_log = HistoryLogEntryDB(
                dynasty_id=proposer.dynasty_id,
                year=year,
                event_string=wedding_text,
                person1_sim_id=proposer.id,
                person2_sim_id=target.id,
                event_type='marriage',
            )
            self.session.add(marriage_log)

            offer.status = 'accepted'
            self.session.commit()

            return {
                'ok': True,
                'accepted': True,
                'message': wedding_text,
                'offer_id': offer.id,
            }

        except Exception as exc:
            logger.error("propose_marriage failed (%s -> %s): %s",
                         proposer_person_id, target_person_id, exc)
            try:
                self.session.rollback()
            except Exception:
                pass
            return {'ok': False, 'accepted': False,
                    'message': 'The proposal could not be sent.',
                    'offer_id': None}

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    @staticmethod
    def _llm_available():
        """Guard mirroring the project-wide LLM availability check."""
        try:
            from models.free_action_system import _llm_available
            return _llm_available()
        except Exception:
            return False
