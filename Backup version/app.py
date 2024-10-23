import json
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

# Define a backup file path
BACKUP_FILE = 'game_state.json'

# Define common and city-specific items with their prices for 7 cities
city_prices = {
    'New York': {
        'Item A': 12,
        'Item B': 18,
        'Item C': 25,
        'Item D': 30
    },
    'Los Angeles': {
        'Item A': 10,
        'Item B': 15,
        'Item E': 20,
        'Item F': 25
    },
    'Chicago': {
        'Item A': 8,
        'Item C': 18,
        'Item G': 22,
        'Item H': 30
    },
    'Houston': {
        'Item B': 14,
        'Item D': 26,
        'Item I': 35,
        'Item J': 40
    },
    'Phoenix': {
        'Item A': 11,
        'Item F': 24,
        'Item K': 28,
        'Item L': 33
    },
    'Philadelphia': {
        'Item B': 16,
        'Item C': 22,
        'Item M': 27,
        'Item N': 37
    },
    'San Antonio': {
        'Item A': 9,
        'Item D': 20,
        'Item O': 34,
        'Item P': 42
    }
}

# Function to load the game state from the backup file
def load_game_state():
    try:
        with open(BACKUP_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        # Default initial state if the backup file doesn't exist
        return {
            'players': {
                'Player 1': {'money': 100, 'cargo': ['', '', ''], 'transaction_log': []},
                'Player 2': {'money': 100, 'cargo': ['', '', ''], 'transaction_log': []},
                'Player 3': {'money': 100, 'cargo': ['', '', ''], 'transaction_log': []},
                'Player 4': {'money': 100, 'cargo': ['', '', ''], 'transaction_log': []}
            },
            'selected_city': 'New York',
            'selected_player': 'Player 1'
        }

# Function to save the current game state to the backup file
def save_game_state():
    with open(BACKUP_FILE, 'w') as file:
        json.dump({
            'players': players,
            'selected_city': selected_city,
            'selected_player': selected_player
        }, file)

# Load the game state at startup
game_state = load_game_state()
players = game_state['players']
selected_city = game_state['selected_city']
selected_player = game_state['selected_player']

# Define the available cities
cities = list(city_prices.keys())

@app.route('/')
def index():
    player_data = players[selected_player]
    items = city_prices[selected_city]
    return render_template(
        'index.html',
        items=items,
        cargo=player_data['cargo'],
        money=player_data['money'],
        cities=cities,
        selected_city=selected_city,
        log=player_data['transaction_log'],
        players=players.keys(),
        selected_player=selected_player
    )

@app.route('/buy', methods=['POST'])
def buy():
    global selected_player
    player_data = players[selected_player]

    item = request.form.get('item')
    items = city_prices[selected_city]

    if item in items:
        # Find the first empty cargo space (lowest index)
        for i in range(len(player_data['cargo'])):
            if not player_data['cargo'][i]:  # If the space is empty
                item_price = items[item]
                # Ensure the user has enough money to buy the item
                if player_data['money'] >= item_price:
                    player_data['cargo'][i] = item  # Place the item in the empty space
                    player_data['money'] -= item_price
                    player_data['transaction_log'].append(f"Bought {item} for ${item_price} in {selected_city}.")
                    save_game_state()  # Save game state after the buy action
                    return jsonify(success=True)  # Return a success response
                else:
                    return jsonify(success=False, message="Insufficient funds.")
        else:
            return jsonify(success=False, message="No empty cargo space available.")

    return jsonify(success=False, message="Item not found.")

@app.route('/sell', methods=['POST'])
def sell():
    global selected_player
    player_data = players[selected_player]

    space = request.form.get('space')
    items = city_prices[selected_city]

    if space.isdigit():
        space_index = int(space) - 1
        if 0 <= space_index < len(player_data['cargo']):
            if player_data['cargo'][space_index]:
                item = player_data['cargo'][space_index]
                if item in items:
                    item_price = items[item]
                    player_data['cargo'][space_index] = ''
                    player_data['money'] += item_price
                    player_data['transaction_log'].append(f"Sold {item} for ${item_price} in {selected_city}.")
                    save_game_state()  # Save game state after the sell action
                    return jsonify(success=True)  # Return success response after selling
                else:
                    return jsonify(success=False, message=f"The city does not demand {item}.", status=400)

    return jsonify(success=False, message="Invalid cargo space.")

@app.route('/clear', methods=['POST'])
def clear():
    global selected_player
    player_data = players[selected_player]

    space = request.form.get('space')

    if space.isdigit():
        space_index = int(space) - 1
        if 0 <= space_index < len(player_data['cargo']):
            player_data['cargo'][space_index] = ''  # Clear the cargo space
            save_game_state()  # Save game state after clearing

    return jsonify(success=True)  # Return success response after clearing

@app.route('/set_city', methods=['POST'])
def set_city():
    global selected_city
    selected_city = request.form.get('city')  # Update the selected city
    save_game_state()  # Save the city selection
    return redirect(url_for('index'))

@app.route('/set_player', methods=['POST'])
def set_player():
    global selected_player
    selected_player = request.form.get('player')  # Update the selected player
    save_game_state()  # Save the player selection
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
