# Technical Implementation of Royal Succession Simulation

This document provides technical details about how the Royal Succession Simulation system is implemented. It's intended for developers who want to understand the code structure, database schema, and simulation logic.

## Implementation Overview

The simulation system is implemented through several components:

1. **Theme Configuration**: JSON definitions of cultural elements
2. **Database Records**: Dynasty, character, and history entries
3. **Simulation Logic**: Rules for character behavior and event generation
4. **Web Interface**: Flask routes for viewing and interacting with dynasties

## Theme Configuration

Cultural themes are defined in `themes/cultural_themes.json`. Each theme configuration includes:

```json
{
  "THEME_KEY": {
    "description": "Description of the cultural theme",
    "start_year_suggestion": 1000,
    "avg_marriage_age_male": 22,
    "avg_marriage_age_female": 18,
    "expected_lifespan_avg": 60,
    "location_flavor": "Geographic/cultural setting",
    "primary_economy": ["Agriculture", "Trade", "Mining"],
    ...
  }
}
```

Key theme parameters that affect simulation behavior:

- **mortality_factor**: Modifies base mortality rate
- **fertility_factor**: Modifies base fertility rate
- **max_children_factor**: Modifies maximum children per couple
- **max_age_factor**: Modifies maximum age
- **starting_wealth_modifier**: Modifies starting wealth

Themes also define culture-specific events like tournaments, plagues, or religious conflicts.

## Database Schema

Dynasty data is stored in several tables defined in `models/db_models.py`:

### DynastyDB Table

The main dynasty record contains:

```python
dynasty = DynastyDB(
    user_id=user.id,
    name="Dynasty Name",
    theme_identifier_or_json=theme_key_or_json_string,
    current_wealth=initial_wealth,
    start_year=start_year,
    current_simulation_year=start_year
)
```

### PersonDB Table

Character records for each family member:

```python
person = PersonDB(
    dynasty_id=dynasty.id,
    name="Character Name",
    surname="Surname",
    gender="MALE",  # or "FEMALE"
    birth_year=birth_year,
    is_noble=True,
    is_monarch=is_founder,
    reign_start_year=start_year if is_founder else None
)
```

Key fields include:
- **name**: Character's given name
- **surname**: Family name or patronymic
- **gender**: "MALE" or "FEMALE"
- **birth_year/death_year**: Life span tracking
- **mother_sim_id/father_sim_id/spouse_sim_id**: Family relationships
- **titles_json/traits_json**: JSON-serialized lists of titles and traits
- **is_monarch/reign_start_year/reign_end_year**: Leadership tracking

### HistoryLogEntryDB Table

Historical events are recorded as:

```python
history_log = HistoryLogEntryDB(
    dynasty_id=dynasty.id,
    year=year,
    event_string="Description of the event",
    person1_sim_id=person_id,
    event_type="event_type"
)
```

Key fields include:
- **year**: When the event occurred (or NULL for timeless events)
- **event_string**: Human-readable description
- **person1_sim_id/person2_sim_id**: Characters involved
- **event_type**: Categorization (birth, death, marriage, etc.)

## Initialization Process

Dynasties are initialized in `main_flask_app.py` through the `initialize_dynasty_founder()` function:

1. Create the dynasty record
2. Create the foundation history log
3. Create the founder character
4. Create the founder's spouse (if applicable)
5. Set up family relationships
6. Create initial history log entries
7. Commit all records to the database

The Flask application initializes the database when it starts:

```python
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

## Simulation Logic

The simulation engine in `simulation_engine.py` handles the progression of dynasties:

### Character Lifecycle

Characters follow these lifecycle rules:

1. **Birth**: Children are born to married couples based on fertility factors
2. **Marriage**: Characters marry when they reach marriageable age (varies by culture)
3. **Children**: Couples can have children up to a maximum (modified by cultural factors)
4. **Death**: Characters die based on age and mortality factors (modified by cultural factors)

### Succession Rules

The system supports multiple succession types:

1. **PRIMOGENITURE_MALE_PREFERENCE**: Male children inherit before female children
2. **PRIMOGENITURE_ABSOLUTE**: Oldest child inherits regardless of gender
3. **ELECTIVE_NOBLE_COUNCIL**: A new ruler is chosen from eligible candidates

This is implemented in `process_succession()` in `simulation_engine.py` and `main_flask_app.py`.

### Event Generation

Culture-specific events are defined in themes and triggered randomly:

```python
"events": [
    {
        "id": "event_id",
        "name": "Event Name",
        "chance_per_year": 0.05,
        "narrative": "Description with {dynasty_name} and {location_flavor} placeholders",
        "wealth_change": 30,
        "trait_grant_on_leader": "Trait"
    },
    ...
]
```

These events can:
- Change dynasty wealth
- Grant traits to characters
- Affect mortality rates
- Last for multiple years

## Web Interface Integration

Dynasties are accessible through the Flask web interface:

### Routes

Key routes in `main_flask_app.py`:

- **`/dashboard`**: Shows all dynasties for the current user
- **`/dynasty/<id>/view`**: Detailed view of a specific dynasty
- **`/dynasty/<id>/advance_turn`**: Progresses the simulation by 5 years

### Templates

The interface uses these templates:

- **`templates/dashboard.html`**: Lists all dynasties
- **`templates/view_dynasty.html`**: Shows dynasty details, characters, and events

### Visualization

Family tree visualization is handled by:

- **`visualization/plotter.py`**: Generates family tree images
- **`generate_family_tree_visualization()`**: Flask wrapper function

## Advancing the Simulation

When a user clicks "Advance Turn", the following happens:

1. `advance_turn()` route is called with the dynasty ID
2. `process_dynasty_turn()` is called to simulate 5 years
3. For each year:
   - Process world events
   - Check for character deaths
   - Check for marriages
   - Check for childbirths
   - Check for succession if the monarch died
4. Update the dynasty's `current_simulation_year`
5. Redirect back to the dynasty view

## Extending the System

### Adding New Characters

```python
new_character = PersonDB(
    dynasty_id=dynasty_id,
    name="Character Name",
    surname="Surname",
    gender="MALE",  # or "FEMALE"
    birth_year=year,
    mother_sim_id=mother_id,  # if applicable
    father_sim_id=father_id,  # if applicable
    is_noble=True
)
new_character.set_traits(["Trait1", "Trait2"])
db.session.add(new_character)
db.session.commit()
```

### Adding Historical Events

```python
new_event = HistoryLogEntryDB(
    dynasty_id=dynasty_id,
    year=year,
    event_string="Description of the event",
    person1_sim_id=character_id,  # if applicable
    event_type="event_type"  # e.g., "birth", "death", "generic_event"
)
db.session.add(new_event)
db.session.commit()
```

### Creating New Cultural Themes

Add a new theme to `themes/cultural_themes.json`:
```json
"NEW_THEME_KEY": {
  "description": "Theme description",
  "names_male": ["Male names list"],
  "names_female": ["Female names list"],
  ...
}
```

## Performance Considerations

The simulation system has these performance characteristics:

- **Database Growth**: Each 5-year turn generates approximately 2-5 new records
- **Visualization Cost**: Family tree generation is the most resource-intensive operation
- **Memory Usage**: Minimal for normal usage, primarily database-bound
- **Scaling**: Can support multiple dynasties in parallel

## Known Limitations

Current implementation limitations:

1. **Name Uniqueness**: The system doesn't prevent duplicate names
2. **Historical Accuracy**: Some cultural elements are simplified
3. **Event Variety**: Limited set of culture-specific events
4. **Character Depth**: Traits don't significantly affect behavior yet

## Future Enhancements

Potential improvements for the system:

1. **Religion System**: Add religious practices and beliefs
2. **Military System**: More detailed warfare mechanics
3. **Character Portraits**: Visual representations of dynasty members
4. **Interactive Decisions**: Allow users to make choices for the dynasty
5. **Extended Family**: More detailed tracking of extended family relationships

## Conclusion

The Royal Succession Simulation system provides a flexible framework for modeling historically-inspired dynasties with cultural specificity. The implementation balances historical authenticity with gameplay mechanics to create engaging narratives that unfold over generations.