# Royal Succession Simulation User Guide

This guide will help you navigate the Royal Succession Simulation system and interact with your dynasties.

## Getting Started

### Accessing the Web Interface

1. Start the Flask application:
   ```
   python main_flask_app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. You will be directed to the home page of the Royal Succession Simulation.

### Logging In

1. Click on the "Login" button in the navigation bar.
2. Use the following credentials:
   - Username: `test_user`
   - Password: `password`
3. Click "Login" to access your dashboard.

## Dashboard

The dashboard displays all dynasties associated with your account:

1. You'll see a list of your dynasties with basic information including:
   - Dynasty name
   - Current year
   - Start year
   - Current wealth
   - Last played date

2. Click on "View Dynasty" to explore a dynasty in detail.

## Viewing a Dynasty

The dynasty view page provides comprehensive information about your selected dynasty:

### Dynasty Overview

At the top of the page, you'll find:
- Dynasty name
- Current year
- Theme description
- Current wealth

### Current Monarch

This section shows details about the current ruler of your dynasty:
- Name and title
- Age
- Traits
- Reign duration

### Living Nobles

This section lists all living noble members of your dynasty:
- Name
- Age
- Gender
- Titles
- Traits

### Recent Events

A chronological list of recent events in your dynasty's history, including:
- Births
- Deaths
- Marriages
- Successions
- World events

### Family Tree

If available, a visual representation of your dynasty's family tree will be displayed.

## Advancing the Simulation

To progress your dynasty through time:

1. Click the "Advance Turn" button on the dynasty view page.
2. This will simulate 5 years of events for your dynasty.
3. The page will refresh with updated information.
4. New events will appear in the Recent Events section.
5. Character ages will increase, and new characters may be born.

## Understanding Simulation Events

As you advance the simulation, various events may occur:

### Character Life Events

- **Births**: New children may be born to married couples.
- **Coming of Age**: Children will grow into adults.
- **Marriages**: Characters may marry when they reach marriageable age.
- **Deaths**: Characters may die from old age, disease, or other causes.

### Dynasty Events

- **Succession**: When a monarch dies, succession rules determine the new ruler.
- **World Events**: Random events like wars, plagues, or festivals may affect the dynasty.
- **Wealth Changes**: The dynasty's wealth may increase or decrease based on events.

### Culture-Specific Events

Different cultural themes have their own specific events:

- **Medieval European**: Tournaments, plagues, crusades
- **Norse**: Raids, Thing assemblies, harsh winters
- **Byzantine**: Court intrigues, religious conflicts, trade agreements

## Creating Your Own Dynasty

To create a new dynasty:

1. From the dashboard, click "Create New Dynasty".
2. Choose a name for your dynasty.
3. Select a predefined theme or provide a custom story.
4. Set the starting year and succession rules.
5. Click "Create Dynasty" to begin your own saga.

## Advanced Features

### Viewing Historical Records

To see the complete history of your dynasty:
1. On the dynasty view page, scroll to the Recent Events section.
2. Click "View Full History" to see all recorded events.

### Checking Character Relationships

To understand family connections:
1. Click on any character's name in the Living Nobles section.
2. This will show their parents, spouse, and children.

## Troubleshooting

### Login Issues

If you cannot log in with the test user:
1. Ensure the Flask application is running.
2. Check that the database has been properly initialized.
3. Try restarting the application with `python main_flask_app.py`.

### Simulation Not Advancing

If clicking "Advance Turn" doesn't work:
1. Check for error messages in the Flask console.
2. Ensure the database is writable.
3. Refresh the page and try again.

### Missing Family Tree Visualization

If the family tree doesn't appear:
1. Check if the visualization directory exists (`static/visualizations`).
2. Ensure the application has write permissions to this directory.
3. Try advancing the turn to trigger visualization generation.

## Command Line Tools

For advanced users, several command-line tools are available:

### Run Local Simulation

To run a standalone simulation without the web interface:
```
python run_local_simulation.py
```

## Next Steps

After exploring your first dynasty, consider:

1. Creating additional dynasties with different cultural themes.
2. Contributing to the project by adding new features or cultural themes.
3. Exploring the code to understand how the simulation works.
4. Creating custom themes for specific historical periods or fictional settings.

Enjoy your journey through the ages with the Royal Succession Simulation!