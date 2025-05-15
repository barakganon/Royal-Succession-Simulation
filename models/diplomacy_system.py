# models/diplomacy_system.py
"""
Diplomacy system for the multi-agent strategic game.
Handles diplomatic relations between dynasties, treaties, war declarations,
reputation mechanics, and diplomatic actions.
"""

import random
import datetime
from typing import List, Dict, Tuple, Optional, Union, Any
from sqlalchemy.orm import Session
from models.db_models import (
    db, DynastyDB, PersonDB, Territory, DiplomaticRelation, Treaty, TreatyType,
    War, WarGoal, HistoryLogEntryDB
)

class DiplomacySystem:
    """
    Core diplomacy system that handles diplomatic relations between dynasties,
    treaties, war declarations, reputation mechanics, and diplomatic actions.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the diplomacy system.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        
        # Diplomatic action effects on relation score
        self.diplomatic_action_effects = {
            "send_envoy": 5,
            "arrange_marriage": 10,
            "declare_rivalry": -20,
            "issue_ultimatum": -10,
            "broker_peace": 15,
            "spread_rumors": -5,
            "bribe_officials": 3,
            "incite_unrest": -15,
            "assassinate": -30,
            "gift": 8,
            "insult": -8,
            "demand_tribute": -12,
            "offer_tribute": 12,
            "declare_war": -40,
            "offer_peace": 15,
            "break_treaty": -25,
            "cultural_exchange": 7,
            "royal_education": 8
        }
        
        # Treaty maintenance costs
        self.treaty_maintenance_costs = {
            TreatyType.NON_AGGRESSION: 0,
            TreatyType.DEFENSIVE_ALLIANCE: 5,
            TreatyType.MILITARY_ALLIANCE: 10,
            TreatyType.VASSALAGE: -10,  # Negative cost means income for overlord
            TreatyType.TRADE_AGREEMENT: 0,
            TreatyType.MARKET_ACCESS: 0,
            TreatyType.RESOURCE_EXCHANGE: 5,
            TreatyType.ECONOMIC_UNION: 8,
            TreatyType.CULTURAL_EXCHANGE: 3,
            TreatyType.ROYAL_MARRIAGE: 0
        }
    
    def get_diplomatic_relation(self, dynasty1_id: int, dynasty2_id: int, create_if_not_exists: bool = True) -> Optional[DiplomaticRelation]:
        """
        Get the diplomatic relation between two dynasties.
        
        Args:
            dynasty1_id: ID of the first dynasty
            dynasty2_id: ID of the second dynasty
            create_if_not_exists: Whether to create a new relation if one doesn't exist
            
        Returns:
            DiplomaticRelation object or None
        """
        # Always ensure dynasty1_id < dynasty2_id for consistent storage
        if dynasty1_id > dynasty2_id:
            dynasty1_id, dynasty2_id = dynasty2_id, dynasty1_id
            
        # Check if relation exists
        relation = self.session.query(DiplomaticRelation).filter_by(
            dynasty1_id=dynasty1_id,
            dynasty2_id=dynasty2_id
        ).first()
        
        # Create new relation if it doesn't exist and create_if_not_exists is True
        if not relation and create_if_not_exists:
            relation = DiplomaticRelation(
                dynasty1_id=dynasty1_id,
                dynasty2_id=dynasty2_id,
                relation_score=0  # Start with neutral relations
            )
            self.session.add(relation)
            self.session.commit()
            
        return relation
    
    def get_relation_status(self, dynasty1_id: int, dynasty2_id: int) -> Tuple[str, int]:
        """
        Get the diplomatic status between two dynasties.
        
        Args:
            dynasty1_id: ID of the first dynasty
            dynasty2_id: ID of the second dynasty
            
        Returns:
            Tuple of (status_name, relation_score)
        """
        relation = self.get_diplomatic_relation(dynasty1_id, dynasty2_id, create_if_not_exists=False)
        
        if not relation:
            return "Unknown", 0
            
        score = relation.relation_score
        
        # Determine status based on score
        if score >= 75:
            status = "Allied"
        elif score >= 50:
            status = "Friendly"
        elif score >= 25:
            status = "Cordial"
        elif score >= -25:
            status = "Neutral"
        elif score >= -50:
            status = "Unfriendly"
        elif score >= -75:
            status = "Hostile"
        else:
            status = "Nemesis"
            
        return status, score
    
    def _generate_diplomatic_action_description(self, action_type: str, actor_name: str, target_name: str, is_target: bool = False) -> str:
        """
        Generate a description for a diplomatic action for history logs.
        
        Args:
            action_type: Type of diplomatic action
            actor_name: Name of the acting dynasty
            target_name: Name of the target dynasty
            is_target: Whether this description is for the target's log
            
        Returns:
            Description string
        """
        if is_target:
            # Descriptions from target's perspective
            descriptions = {
                "send_envoy": f"{actor_name} has sent an envoy to our court",
                "arrange_marriage": f"{actor_name} has proposed a marriage alliance",
                "declare_rivalry": f"{actor_name} has declared us as their rival",
                "issue_ultimatum": f"{actor_name} has issued an ultimatum to us",
                "broker_peace": f"{actor_name} has offered to broker peace in our conflicts",
                "spread_rumors": f"We have discovered that {actor_name} is spreading rumors about us",
                "bribe_officials": f"Some of our officials have been bribed by {actor_name}",
                "incite_unrest": f"{actor_name} is attempting to incite unrest in our territories",
                "assassinate": f"An assassination attempt from {actor_name} has been discovered",
                "gift": f"{actor_name} has sent us a generous gift",
                "insult": f"{actor_name} has publicly insulted us",
                "demand_tribute": f"{actor_name} is demanding tribute from us",
                "offer_tribute": f"{actor_name} has offered to pay us tribute",
                "declare_war": f"{actor_name} has declared war on us",
                "offer_peace": f"{actor_name} has offered us peace terms",
                "break_treaty": f"{actor_name} has broken their treaty with us",
                "cultural_exchange": f"{actor_name} has proposed a cultural exchange program",
                "royal_education": f"{actor_name} has offered to educate one of our royal children"
            }
        else:
            # Descriptions from actor's perspective
            descriptions = {
                "send_envoy": f"We have sent an envoy to {target_name}",
                "arrange_marriage": f"We have proposed a marriage alliance with {target_name}",
                "declare_rivalry": f"We have declared {target_name} as our rival",
                "issue_ultimatum": f"We have issued an ultimatum to {target_name}",
                "broker_peace": f"We have offered to broker peace for {target_name}",
                "spread_rumors": f"We are spreading rumors about {target_name}",
                "bribe_officials": f"We have bribed officials in {target_name}'s court",
                "incite_unrest": f"We are inciting unrest in {target_name}'s territories",
                "assassinate": f"We have attempted to assassinate a member of {target_name}'s dynasty",
                "gift": f"We have sent a generous gift to {target_name}",
                "insult": f"We have publicly insulted {target_name}",
                "demand_tribute": f"We are demanding tribute from {target_name}",
                "offer_tribute": f"We have offered to pay tribute to {target_name}",
                "declare_war": f"We have declared war on {target_name}",
                "offer_peace": f"We have offered peace terms to {target_name}",
                "break_treaty": f"We have broken our treaty with {target_name}",
                "cultural_exchange": f"We have proposed a cultural exchange program with {target_name}",
                "royal_education": f"We have offered to educate one of {target_name}'s royal children"
            }
            
        return descriptions.get(action_type, f"Diplomatic action '{action_type}' with {target_name}")
    
    def perform_diplomatic_action(self, actor_dynasty_id: int, target_dynasty_id: int, 
                                 action_type: str, additional_data: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Perform a diplomatic action between two dynasties.
        
        Args:
            actor_dynasty_id: ID of the dynasty performing the action
            target_dynasty_id: ID of the target dynasty
            action_type: Type of diplomatic action
            additional_data: Additional data for the action
            
        Returns:
            Tuple of (success, message)
        """
        # Get dynasties
        actor_dynasty = self.session.query(DynastyDB).get(actor_dynasty_id)
        target_dynasty = self.session.query(DynastyDB).get(target_dynasty_id)
        
        if not actor_dynasty or not target_dynasty:
            return False, "One or both dynasties not found"
            
        # Get diplomatic relation
        relation = self.get_diplomatic_relation(actor_dynasty_id, target_dynasty_id)
        
        # Check if action is valid
        if action_type not in self.diplomatic_action_effects:
            return False, f"Invalid diplomatic action: {action_type}"
            
        # Get effect magnitude
        base_magnitude = self.diplomatic_action_effects[action_type]
        
        # Apply modifiers based on reputation attributes
        magnitude = base_magnitude
        
        # Honor affects trustworthiness
        if action_type in ["break_treaty", "declare_war"] and actor_dynasty.honor < 50:
            magnitude *= (1 + (50 - actor_dynasty.honor) / 50)
        
        # Prestige affects influence
        if actor_dynasty.prestige > target_dynasty.prestige:
            prestige_diff = (actor_dynasty.prestige - target_dynasty.prestige) / 100
            magnitude *= (1 + prestige_diff * 0.5)
        
        # Apply the effect to the relation
        relation.update_relation(action_type, int(magnitude))
        
        # Create history log entry
        log_entry = HistoryLogEntryDB(
            dynasty_id=actor_dynasty_id,
            year=actor_dynasty.current_simulation_year,
            event_string=self._generate_diplomatic_action_description(action_type, actor_dynasty.name, target_dynasty.name),
            event_type=f"diplomatic_{action_type}"
        )
        self.session.add(log_entry)
        
        # Create a log entry for the target dynasty as well
        target_log_entry = HistoryLogEntryDB(
            dynasty_id=target_dynasty_id,
            year=target_dynasty.current_simulation_year,
            event_string=self._generate_diplomatic_action_description(action_type, actor_dynasty.name, target_dynasty.name, is_target=True),
            event_type=f"diplomatic_{action_type}"
        )
        self.session.add(target_log_entry)
        
        # Handle special actions
        if action_type == "declare_rivalry":
            # Update reputation
            actor_dynasty.infamy += 5
            
        elif action_type == "assassinate":
            # High risk action
            success_chance = 0.3  # 30% base chance
            
            # Modify based on target's court security (placeholder)
            # success_chance -= target_court_security * 0.1
            
            if random.random() > success_chance:
                # Failed assassination
                actor_dynasty.infamy += 20
                actor_dynasty.honor -= 10
                
                # Create additional log entries for failed assassination
                failed_log = HistoryLogEntryDB(
                    dynasty_id=actor_dynasty_id,
                    year=actor_dynasty.current_simulation_year,
                    event_string=f"Our assassination attempt against {target_dynasty.name} has failed and been discovered!",
                    event_type="failed_assassination"
                )
                self.session.add(failed_log)
                
                target_failed_log = HistoryLogEntryDB(
                    dynasty_id=target_dynasty_id,
                    year=target_dynasty.current_simulation_year,
                    event_string=f"We have uncovered an assassination plot by {actor_dynasty.name}!",
                    event_type="failed_assassination"
                )
                self.session.add(target_failed_log)
                
                # Apply severe relation penalty
                relation.update_relation("failed_assassination", -50)
                
                self.session.commit()
                return False, f"Assassination attempt against {target_dynasty.name} failed and was discovered!"
            else:
                # Successful assassination (would need to handle actual character death)
                actor_dynasty.infamy += 10
                actor_dynasty.honor -= 5
                
                # In a real implementation, this would kill a character
                # For now, just log it
                success_log = HistoryLogEntryDB(
                    dynasty_id=actor_dynasty_id,
                    year=actor_dynasty.current_simulation_year,
                    event_string=f"Our assassination against {target_dynasty.name} was successful!",
                    event_type="successful_assassination"
                )
                self.session.add(success_log)
                
                # No log for target - they don't know it was an assassination
                
                self.session.commit()
                return True, f"Assassination against {target_dynasty.name} was successful!"
        
    def create_treaty(self, dynasty1_id: int, dynasty2_id: int, treaty_type: TreatyType,
                     duration: Optional[int] = None, terms: Optional[Dict] = None) -> Tuple[bool, str, Optional[Treaty]]:
        """
        Create a treaty between two dynasties.
        
        Args:
            dynasty1_id: ID of the first dynasty
            dynasty2_id: ID of the second dynasty
            treaty_type: Type of treaty
            duration: Duration in years (None for permanent)
            terms: Dictionary of treaty terms
            
        Returns:
            Tuple of (success, message, treaty)
        """
        # Get dynasties
        dynasty1 = self.session.query(DynastyDB).get(dynasty1_id)
        dynasty2 = self.session.query(DynastyDB).get(dynasty2_id)
        
        if not dynasty1 or not dynasty2:
            return False, "One or both dynasties not found", None
            
        # Get diplomatic relation
        relation = self.get_diplomatic_relation(dynasty1_id, dynasty2_id)
        
        # Check if relation score is sufficient for treaty
        status, score = self.get_relation_status(dynasty1_id, dynasty2_id)
        
        # Different treaty types require different relation scores
        min_scores = {
            TreatyType.NON_AGGRESSION: -25,  # Can be made even with unfriendly relations
            TreatyType.DEFENSIVE_ALLIANCE: 25,  # Requires at least cordial relations
            TreatyType.MILITARY_ALLIANCE: 50,  # Requires friendly relations
            TreatyType.VASSALAGE: -50,  # Can be forced on hostile dynasties
            TreatyType.TRADE_AGREEMENT: -25,  # Economic interests can overcome mild hostility
            TreatyType.MARKET_ACCESS: 0,  # Requires at least neutral relations
            TreatyType.RESOURCE_EXCHANGE: 25,  # Requires some trust
            TreatyType.ECONOMIC_UNION: 50,  # Requires strong relations
            TreatyType.CULTURAL_EXCHANGE: 25,  # Requires positive relations
            TreatyType.ROYAL_MARRIAGE: 25  # Requires positive relations
        }
        
        if score < min_scores.get(treaty_type, 0):
            return False, f"Relations too poor for {treaty_type.value} treaty", None
            
        # Check for existing treaties of the same type
        existing_treaty = self.session.query(Treaty).filter(
            Treaty.diplomatic_relation_id == relation.id,
            Treaty.treaty_type == treaty_type,
            Treaty.active == True
        ).first()
        
        if existing_treaty:
            return False, f"A {treaty_type.value} treaty already exists between these dynasties", None
            
        # Create the treaty
        new_treaty = Treaty(
            diplomatic_relation_id=relation.id,
            treaty_type=treaty_type,
            start_year=dynasty1.current_simulation_year,
            duration=duration,
            active=True
        )
        
        # Set terms if provided
        if terms:
            new_treaty.set_terms(terms)
            
        # Add to database
        self.session.add(new_treaty)
        
        # Improve relations based on treaty type
        relation_boost = {
            TreatyType.NON_AGGRESSION: 5,
            TreatyType.DEFENSIVE_ALLIANCE: 10,
            TreatyType.MILITARY_ALLIANCE: 15,
            TreatyType.VASSALAGE: -10,  # Vassal may resent overlord
            TreatyType.TRADE_AGREEMENT: 5,
            TreatyType.MARKET_ACCESS: 5,
            TreatyType.RESOURCE_EXCHANGE: 8,
            TreatyType.ECONOMIC_UNION: 10,
            TreatyType.CULTURAL_EXCHANGE: 8,
            TreatyType.ROYAL_MARRIAGE: 15
        }
        
        relation.update_relation("treaty_signed", relation_boost.get(treaty_type, 5))
        
        # Create history log entries
        treaty_name = treaty_type.value.replace('_', ' ').title()
        
        log_entry1 = HistoryLogEntryDB(
            dynasty_id=dynasty1_id,
            year=dynasty1.current_simulation_year,
            event_string=f"Signed a {treaty_name} with {dynasty2.name}",
            event_type="treaty_signed",
            treaty_id=new_treaty.id
        )
        self.session.add(log_entry1)
        
        log_entry2 = HistoryLogEntryDB(
            dynasty_id=dynasty2_id,
            year=dynasty2.current_simulation_year,
            event_string=f"Signed a {treaty_name} with {dynasty1.name}",
            event_type="treaty_signed",
            treaty_id=new_treaty.id
        )
        self.session.add(log_entry2)
        
        # Commit changes
        self.session.commit()
        
        return True, f"{treaty_name} treaty created successfully", new_treaty
    
    def break_treaty(self, treaty_id: int, breaker_dynasty_id: int) -> Tuple[bool, str]:
        """
        Break a treaty between dynasties.
        
        Args:
            treaty_id: ID of the treaty to break
            breaker_dynasty_id: ID of the dynasty breaking the treaty
            
        Returns:
            Tuple of (success, message)
        """
        # Get treaty
        treaty = self.session.query(Treaty).get(treaty_id)
        if not treaty:
            return False, "Treaty not found"
            
        # Check if treaty is active
        if not treaty.active:
            return False, "Treaty is already inactive"
            
        # Get diplomatic relation
        relation = self.session.query(DiplomaticRelation).get(treaty.diplomatic_relation_id)
        if not relation:
            return False, "Diplomatic relation not found"
            
        # Get dynasties
        dynasty1 = self.session.query(DynastyDB).get(relation.dynasty1_id)
        dynasty2 = self.session.query(DynastyDB).get(relation.dynasty2_id)
        
        if not dynasty1 or not dynasty2:
            return False, "One or both dynasties not found"
            
        # Determine other dynasty
        other_dynasty_id = relation.dynasty2_id if breaker_dynasty_id == relation.dynasty1_id else relation.dynasty1_id
        other_dynasty = dynasty2 if breaker_dynasty_id == relation.dynasty1_id else dynasty1
        breaker_dynasty = dynasty1 if breaker_dynasty_id == relation.dynasty1_id else dynasty2
        
        # Deactivate the treaty
        treaty.active = False
        
        # Apply relation penalty
        relation.update_relation("break_treaty", -20)
        
        # Apply honor penalty to breaker
        breaker_dynasty.honor -= 10
        
        # Create history log entries
        treaty_name = treaty.treaty_type.value.replace('_', ' ').title()
        
        log_entry1 = HistoryLogEntryDB(
            dynasty_id=breaker_dynasty_id,
            year=breaker_dynasty.current_simulation_year,
            event_string=f"Broke our {treaty_name} with {other_dynasty.name}",
            event_type="treaty_broken",
            treaty_id=treaty.id
        )
        self.session.add(log_entry1)
        
        log_entry2 = HistoryLogEntryDB(
            dynasty_id=other_dynasty_id,
            year=other_dynasty.current_simulation_year,
            event_string=f"{breaker_dynasty.name} has broken their {treaty_name} with us!",
            event_type="treaty_broken",
            treaty_id=treaty.id
        )
        self.session.add(log_entry2)
        
        # Commit changes
        self.session.commit()
        
        return True, f"Treaty broken successfully"
    
    def declare_war(self, attacker_dynasty_id: int, defender_dynasty_id: int, 
                   war_goal: WarGoal, target_territory_id: Optional[int] = None) -> Tuple[bool, str, Optional[War]]:
        """
        Declare war between dynasties.
        
        Args:
            attacker_dynasty_id: ID of the attacking dynasty
            defender_dynasty_id: ID of the defending dynasty
            war_goal: Goal of the war
            target_territory_id: ID of the target territory (for conquest wars)
            
        Returns:
            Tuple of (success, message, war)
        """
        # Get dynasties
        attacker = self.session.query(DynastyDB).get(attacker_dynasty_id)
        defender = self.session.query(DynastyDB).get(defender_dynasty_id)
        
        if not attacker or not defender:
            return False, "One or both dynasties not found", None
            
        # Check for existing active wars between these dynasties
        existing_war = self.session.query(War).filter(
            ((War.attacker_dynasty_id == attacker_dynasty_id) & (War.defender_dynasty_id == defender_dynasty_id)) |
            ((War.attacker_dynasty_id == defender_dynasty_id) & (War.defender_dynasty_id == attacker_dynasty_id)),
            War.is_active == True
        ).first()
        
        if existing_war:
            return False, "There is already an active war between these dynasties", None
            
        # Check for non-aggression or alliance treaties
        relation = self.get_diplomatic_relation(attacker_dynasty_id, defender_dynasty_id, create_if_not_exists=False)
        
        if relation:
            # Check for treaties that prevent war
            peace_treaties = self.session.query(Treaty).filter(
                Treaty.diplomatic_relation_id == relation.id,
                Treaty.treaty_type.in_([TreatyType.NON_AGGRESSION, TreatyType.DEFENSIVE_ALLIANCE, TreatyType.MILITARY_ALLIANCE]),
                Treaty.active == True
            ).all()
            
            if peace_treaties:
                # Break treaties first
                for treaty in peace_treaties:
                    self.break_treaty(treaty.id, attacker_dynasty_id)
        
        # For conquest wars, verify target territory
        if war_goal == WarGoal.CONQUEST and target_territory_id:
            territory = self.session.query(Territory).get(target_territory_id)
            if not territory:
                return False, "Target territory not found", None
                
            if territory.controller_dynasty_id != defender_dynasty_id:
                return False, "Target territory is not controlled by the defender", None
        
        # Create the war
        new_war = War(
            attacker_dynasty_id=attacker_dynasty_id,
            defender_dynasty_id=defender_dynasty_id,
            war_goal=war_goal,
            target_territory_id=target_territory_id,
            start_year=attacker.current_simulation_year,
            attacker_war_score=0,
            defender_war_score=0,
            is_active=True
        )
        
        # Add to database
        self.session.add(new_war)
        
        # Update diplomatic relation
        if relation:
            relation.update_relation("declare_war", -40)
        else:
            relation = self.get_diplomatic_relation(attacker_dynasty_id, defender_dynasty_id)
            relation.update_relation("declare_war", -40)
        
        # Update reputation
        attacker.infamy += 10
        
        # Create history log entries
        war_goal_name = war_goal.value.replace('_', ' ').title()
        
        log_entry1 = HistoryLogEntryDB(
            dynasty_id=attacker_dynasty_id,
            year=attacker.current_simulation_year,
            event_string=f"Declared war on {defender.name} with the goal of {war_goal_name}",
            event_type="war_declared",
            war_id=new_war.id
        )
        self.session.add(log_entry1)
        
        log_entry2 = HistoryLogEntryDB(
            dynasty_id=defender_dynasty_id,
            year=defender.current_simulation_year,
            event_string=f"{attacker.name} has declared war on us with the goal of {war_goal_name}!",
            event_type="war_declared",
            war_id=new_war.id
        )
        self.session.add(log_entry2)
        
        # Commit changes
        self.session.commit()
        
        return True, f"War declared successfully", new_war
        # Commit changes
        self.session.commit()
        
        return True, f"Diplomatic action '{action_type}' performed successfully"
def negotiate_peace(self, war_id: int, enforced_by_attacker: bool, 
                       terms: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Negotiate peace to end a war.
        
        Args:
            war_id: ID of the war
            enforced_by_attacker: Whether the attacker is enforcing terms
            terms: Dictionary of peace terms
            
        Returns:
            Tuple of (success, message)
        """
        # Get war
        war = self.session.query(War).get(war_id)
        if not war:
            return False, "War not found"
            
        # Check if war is active
        if not war.is_active:
            return False, "War is already over"
            
        # Get dynasties
        attacker = self.session.query(DynastyDB).get(war.attacker_dynasty_id)
        defender = self.session.query(DynastyDB).get(war.defender_dynasty_id)
        
        if not attacker or not defender:
            return False, "One or both dynasties not found"
            
        # Check war score to see if terms are reasonable
        if enforced_by_attacker and war.attacker_war_score < 50:
            return False, "Attacker's war score is too low to enforce these terms"
            
        if not enforced_by_attacker and war.defender_war_score < 50:
            return False, "Defender's war score is too low to enforce these terms"
            
        # Process peace terms
        if "territory_transfer" in terms and terms["territory_transfer"]:
            territory_id = terms["territory_transfer"]
            territory = self.session.query(Territory).get(territory_id)
            
            if not territory:
                return False, "Territory not found"
                
            # Transfer territory
            if enforced_by_attacker:
                # Attacker gets territory
                old_controller = territory.controller_dynasty_id
                territory.controller_dynasty_id = war.attacker_dynasty_id
                
                # Log territory transfer
                log_entry1 = HistoryLogEntryDB(
                    dynasty_id=war.attacker_dynasty_id,
                    year=attacker.current_simulation_year,
                    event_string=f"Acquired {territory.name} from {defender.name} in peace settlement",
                    event_type="territory_gained",
                    territory_id=territory.id,
                    war_id=war.id
                )
                self.session.add(log_entry1)
                
                log_entry2 = HistoryLogEntryDB(
                    dynasty_id=war.defender_dynasty_id,
                    year=defender.current_simulation_year,
                    event_string=f"Lost {territory.name} to {attacker.name} in peace settlement",
                    event_type="territory_lost",
                    territory_id=territory.id,
                    war_id=war.id
                )
                self.session.add(log_entry2)
            else:
                # Defender keeps/gets territory
                # This could be a defensive war where defender gets attacker's territory
                if "attacker_territory_id" in terms:
                    attacker_territory_id = terms["attacker_territory_id"]
                    attacker_territory = self.session.query(Territory).get(attacker_territory_id)
                    
                    if attacker_territory and attacker_territory.controller_dynasty_id == war.attacker_dynasty_id:
                        attacker_territory.controller_dynasty_id = war.defender_dynasty_id
                        
                        # Log territory transfer
                        log_entry1 = HistoryLogEntryDB(
                            dynasty_id=war.defender_dynasty_id,
                            year=defender.current_simulation_year,
                            event_string=f"Acquired {attacker_territory.name} from {attacker.name} in peace settlement",
                            event_type="territory_gained",
                            territory_id=attacker_territory.id,
                            war_id=war.id
                        )
                        self.session.add(log_entry1)
                        
                        log_entry2 = HistoryLogEntryDB(
                            dynasty_id=war.attacker_dynasty_id,
                            year=attacker.current_simulation_year,
                            event_string=f"Lost {attacker_territory.name} to {defender.name} in peace settlement",
                            event_type="territory_lost",
                            territory_id=attacker_territory.id,
                            war_id=war.id
                        )
                        self.session.add(log_entry2)
        
        # Handle tribute/reparations
        if "gold_payment" in terms and terms["gold_payment"]:
            payment = terms["gold_payment"]
            
            if enforced_by_attacker:
                # Defender pays attacker
                if defender.current_wealth >= payment:
                    defender.current_wealth -= payment
                    attacker.current_wealth += payment
                    
                    # Log payment
                    log_entry1 = HistoryLogEntryDB(
                        dynasty_id=war.attacker_dynasty_id,
                        year=attacker.current_simulation_year,
                        event_string=f"Received {payment} gold from {defender.name} in war reparations",
                        event_type="reparations_received",
                        war_id=war.id
                    )
                    self.session.add(log_entry1)
                    
                    log_entry2 = HistoryLogEntryDB(
                        dynasty_id=war.defender_dynasty_id,
                        year=defender.current_simulation_year,
                        event_string=f"Paid {payment} gold to {attacker.name} in war reparations",
                        event_type="reparations_paid",
                        war_id=war.id
                    )
                    self.session.add(log_entry2)
                else:
                    # Not enough gold, pay what they can
                    payment = defender.current_wealth
                    attacker.current_wealth += payment
                    defender.current_wealth = 0
            else:
                # Attacker pays defender
                if attacker.current_wealth >= payment:
                    attacker.current_wealth -= payment
                    defender.current_wealth += payment
                    
                    # Log payment
                    log_entry1 = HistoryLogEntryDB(
                        dynasty_id=war.defender_dynasty_id,
                        year=defender.current_simulation_year,
                        event_string=f"Received {payment} gold from {attacker.name} in war reparations",
                        event_type="reparations_received",
                        war_id=war.id
                    )
                    self.session.add(log_entry1)
                    
                    log_entry2 = HistoryLogEntryDB(
                        dynasty_id=war.attacker_dynasty_id,
                        year=attacker.current_simulation_year,
                        event_string=f"Paid {payment} gold to {defender.name} in war reparations",
                        event_type="reparations_paid",
                        war_id=war.id
                    )
                    self.session.add(log_entry2)
                else:
                    # Not enough gold, pay what they can
                    payment = attacker.current_wealth
                    defender.current_wealth += payment
                    attacker.current_wealth = 0
        
        # Handle vassalization
        if "vassalize" in terms and terms["vassalize"]:
            if enforced_by_attacker:
                # Create vassalage treaty
                relation = self.get_diplomatic_relation(war.attacker_dynasty_id, war.defender_dynasty_id)
                
                vassalage_treaty = Treaty(
                    diplomatic_relation_id=relation.id,
                    treaty_type=TreatyType.VASSALAGE,
                    start_year=attacker.current_simulation_year,
                    duration=None,  # Permanent until broken
                    active=True
                )
                
                # Set terms
                vassalage_treaty.set_terms({
                    "overlord_id": war.attacker_dynasty_id,
                    "vassal_id": war.defender_dynasty_id,
                    "tribute_percentage": 0.1  # 10% of income
                })
                
                self.session.add(vassalage_treaty)
                
                # Log vassalization
                log_entry1 = HistoryLogEntryDB(
                    dynasty_id=war.attacker_dynasty_id,
                    year=attacker.current_simulation_year,
                    event_string=f"{defender.name} has become our vassal",
                    event_type="vassalization",
                    war_id=war.id,
                    treaty_id=vassalage_treaty.id
                )
                self.session.add(log_entry1)
                
                log_entry2 = HistoryLogEntryDB(
                    dynasty_id=war.defender_dynasty_id,
                    year=defender.current_simulation_year,
                    event_string=f"We have become a vassal of {attacker.name}",
                    event_type="vassalization",
                    war_id=war.id,
                    treaty_id=vassalage_treaty.id
                )
                self.session.add(log_entry2)
            else:
                # Defender forces attacker to release vassal
                # This would be implemented if there was a vassal system in place
                pass
        
        # End the war
        war.is_active = False
        war.end_year = attacker.current_simulation_year
        
        # Determine winner
        if enforced_by_attacker:
            war.winner_dynasty_id = war.attacker_dynasty_id
        else:
            war.winner_dynasty_id = war.defender_dynasty_id
        
        # Improve relations slightly
        relation = self.get_diplomatic_relation(war.attacker_dynasty_id, war.defender_dynasty_id)
        relation.update_relation("peace_treaty", 10)
        
        # Log peace treaty
        log_entry1 = HistoryLogEntryDB(
            dynasty_id=war.attacker_dynasty_id,
            year=attacker.current_simulation_year,
            event_string=f"Peace treaty signed with {defender.name}",
            event_type="peace_treaty",
            war_id=war.id
        )
        self.session.add(log_entry1)
        
        log_entry2 = HistoryLogEntryDB(
            dynasty_id=war.defender_dynasty_id,
            year=defender.current_simulation_year,
            event_string=f"Peace treaty signed with {attacker.name}",
            event_type="peace_treaty",
            war_id=war.id
        )
        self.session.add(log_entry2)
        
        # Commit changes
        self.session.commit()
        
        return True, "Peace treaty successfully negotiated"