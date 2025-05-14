# check_dynasty.py
import os
import sys
from flask import Flask
from models.db_models import db, User, DynastyDB, PersonDB, HistoryLogEntryDB

# Create a minimal Flask app to access the database
app = Flask(__name__)
instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "dynastysim.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def check_dynasty(dynasty_name=None, dynasty_id=None):
    """Check if a dynasty exists in the database and print its details.
    
    Args:
        dynasty_name: Name of the dynasty to check
        dynasty_id: ID of the dynasty to check (alternative to name)
    """
    with app.app_context():
        # Find the dynasty
        dynasty = None
        if dynasty_id:
            dynasty = DynastyDB.query.get(dynasty_id)
        elif dynasty_name:
            dynasty = DynastyDB.query.filter_by(name=dynasty_name).first()
        else:
            # If no name or ID provided, list all dynasties
            dynasties = DynastyDB.query.all()
            if dynasties:
                print(f"Found {len(dynasties)} dynasties in the database:")
                for d in dynasties:
                    print(f"- {d.name} (ID: {d.id}, Year: {d.current_simulation_year})")
                return
            else:
                print("No dynasties found in the database.")
                return
        
        if dynasty:
            print(f"Dynasty '{dynasty.name}' found in database (ID: {dynasty.id})")
            print(f"Start Year: {dynasty.start_year}")
            print(f"Current Simulation Year: {dynasty.current_simulation_year}")
            print(f"Current Wealth: {dynasty.current_wealth}")
            
            # Get the founder
            founder = PersonDB.query.get(dynasty.founder_person_db_id) if dynasty.founder_person_db_id else None
            if founder:
                print(f"\nFounder: {founder.name} {founder.surname}")
                print(f"Gender: {founder.gender}")
                print(f"Birth Year: {founder.birth_year}")
                print(f"Titles: {founder.get_titles()}")
                print(f"Traits: {founder.get_traits()}")
                
                # Get founder's spouse
                if founder.spouse_sim_id:
                    spouse = PersonDB.query.get(founder.spouse_sim_id)
                    if spouse:
                        print(f"\nFounder's Spouse: {spouse.name} {spouse.surname}")
                        print(f"Birth Year: {spouse.birth_year}")
                        print(f"Titles: {spouse.get_titles()}")
                        print(f"Traits: {spouse.get_traits()}")
            
            # Get all members of the dynasty
            members = PersonDB.query.filter_by(dynasty_id=dynasty.id).all()
            print(f"\nTotal Members: {len(members)}")
            print("\nDynasty Members:")
            for member in members:
                print(f"- {member.name} {member.surname} (Born: {member.birth_year}, {'Alive' if member.death_year is None else f'Died: {member.death_year}'})")
            
            # Get history logs
            history_logs = HistoryLogEntryDB.query.filter_by(dynasty_id=dynasty.id).order_by(HistoryLogEntryDB.year).all()
            print(f"\nHistory Logs ({len(history_logs)} entries):")
            for log in history_logs:
                year_display = log.year if log.year is not None else "----"
                print(f"Year {year_display}: {log.event_string}")
        else:
            if dynasty_name:
                print(f"Dynasty '{dynasty_name}' not found in the database.")
            else:
                print(f"Dynasty with ID {dynasty_id} not found in the database.")

if __name__ == "__main__":
    # Check if dynasty name was provided as command line argument
    if len(sys.argv) > 1:
        # Check if it's a number (ID) or name
        if sys.argv[1].isdigit():
            check_dynasty(dynasty_id=int(sys.argv[1]))
        else:
            check_dynasty(dynasty_name=sys.argv[1])
    else:
        # List all dynasties if no argument provided
        check_dynasty()