import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
import copy
from datetime import datetime, timezone, timedelta
import os


app = Flask(__name__)

# ---------------------------------------------------------------------
#  Default data for a fresh game
# ---------------------------------------------------------------------
BACKUP_FILE = Path("game_state.json")
DEFAULT_CITY_PRICES_EU = {
    "Ribe": {
        "Mælk": 9,
        "Hvede": 14,
        "Mjød": 21,
        "Tekstiler": 24,
        "Kød": 30,
        "Vin": 40,
    },
    "Aarhus": {
        "Mælk": 11,
        "Hvede": 16,
        "Mjød": 23,
        "Tekstiler": 27,
        "Kød": 34,
        "Vin": 46,
        "Fisk": 59,
    },
    "Roskilde": {
        "Mjød": 24,
        "Tekstiler": 26,
        "Silke": 74,
        "Møbler": 88,
        "Relikvier": 108,
        "Rustninger": 147,
    },
    "Helsingør": {
        "Mælk": 8,
        "Kød": 33,
        "Vin": 44,
        "Fisk": 57,
        "Silke": 70,
        "Møbler": 85,
    },
    "Odense": {
        "Hvede": 17,
        "Mjød": 20,
        "Tekstiler": 23,
        "Vin": 38,
        "Fisk": 52,
        "Silke": 65,
    },
    "Viborg": {
        "Kød": 36,
        "Vin": 47,
        "Fisk": 61,
        "Møbler": 90,
        "Relikvier": 110,
        "Rustninger": 150,
    },
    "Svendborg": {
        "Mælk": 10,
        "Hvede": 15,
        "Mjød": 22,
        "Tekstiler": 25,
        "Kød": 31,
        "Vin": 41,
        "Relikvier": 93,
    },
    "Vogn Manden": {

    }
}


DEFAULT_PLAYERS = {
    f"Player {i}": {
        "money": 100,
        "capacity": 2,          # ← NEW
        "cargo": ["", ""],      # two slots to match capacity
        "transaction_log": []
    }
    for i in range(1, 5)
}

# ---------------------------------------------------------------------
#  Helper functions for persistence
# ---------------------------------------------------------------------
def next_upgrade_cost(capacity: int) -> int:
    """
    Pricing rule: +1 pallet costs €(200 * capacity – 100)
    → 2→3 slots = €300, 3→4 = €500, 4→5 = €700, …
    """
    return 200 * capacity - 100

def iso_now():
    """UTC ISO-8601 timestamp, seconds only."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_game_state():
    """Load state from disk or create a brand-new one."""
    if BACKUP_FILE.exists():
        with BACKUP_FILE.open("r") as f:
            data = json.load(f)
    else:
        data = {}

    # Fill in any missing keys so old save files still work
    data.setdefault("players", DEFAULT_PLAYERS.copy())
    data.setdefault("selected_city", "Odense")
    data.setdefault("selected_player", "Player 1")
    data.setdefault("city_prices", DEFAULT_CITY_PRICES_EU.copy())
    data.setdefault("breaking_news", "")
    data.setdefault("closed_cities", [])
    # ---------- NEW: ensure Vogn Manden exists even in older saves ----------
    if "Vogn Manden" not in data["city_prices"]:
        data["city_prices"]["Vogn Manden"] = {}
    # -----------------------------------------------------------------------

    for p in data["players"].values():
        p.setdefault("capacity", 2)
        # ensure cargo list length == capacity
        while len(p["cargo"]) < p["capacity"]:
            p["cargo"].append("")
    return data


def save_game_state():
    """Write *all* in-memory state to disk."""
    with BACKUP_FILE.open("w") as f:
        json.dump(
            {
                "players": players,
                "selected_city": selected_city,
                "selected_player": selected_player,
                "city_prices": city_prices,
                "breaking_news": breaking_news,
                "closed_cities": closed_cities,
            },
            f,
            indent=2,
        )


# ---------------------------------------------------------------------
#  In-memory copies (Flask will mutate these)
# ---------------------------------------------------------------------
_state = load_game_state()
players         = _state["players"]
selected_city   = _state["selected_city"]
selected_player = _state["selected_player"]
city_prices     = _state["city_prices"]
breaking_news   = _state["breaking_news"]
closed_cities   = _state["closed_cities"]

# Convenience list for the dropdown
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
        selected_player=selected_player,
        breaking_news=breaking_news,  # Pass breaking news to the front end
        closed_cities=closed_cities,
        capacity=player_data['capacity'],          # NEW
        upgrade_cost=next_upgrade_cost(player_data['capacity'])  # NEW 
    )

@app.route('/buy', methods=['POST'])

def buy():
    global selected_player
    player_data = players[selected_player]
    if selected_city in closed_cities:
        return jsonify(success=False, message=f"{selected_city} is currently closed.")
    if player_data["cargo"].count("") == 0:
        return jsonify(success=False, message="All cargo spaces full. Consider a truck upgrade.")

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
                    # after you charge the player’s money …
                    player_data['transaction_log'].append(
                        f"Bought {item} for €{item_price} in {selected_city}."
                    )
                    player_data['transaction_log'].append(
                        {"ts": iso_now(), "money": player_data["money"]}
                    )

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
    if selected_city in closed_cities:
        return jsonify(success=False, message=f"{selected_city} is currently closed.")

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
                    player_data['transaction_log'].append(
                        f"Sold {item} for €{item_price} in {selected_city}."
                    )
                    player_data['transaction_log'].append(
                        {"ts": iso_now(), "money": player_data["money"]}
                    )

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


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global selected_city
    # When the city dropdown auto-submits, capture the choice
    if request.method == 'POST':
        chosen = request.form.get('city')
        if chosen in city_prices:
            selected_city = chosen
            save_game_state()

    return render_template(
        'admin.html',
        cities=cities,
        city_prices=city_prices,
        breaking_news=breaking_news,
        closed_cities=closed_cities,
        players=players,
        selected_city=selected_city  # ← pass it to the template
    )
@app.route('/update_prices', methods=['POST'])
def update_prices():
    city = request.form.get('city')
    
    if city in city_prices:
        updated_prices = {}
        for item in city_prices[city]:
            price_str = request.form.get(item)
            
            if price_str is not None:
                try:
                    updated_price = int(price_str)
                    updated_prices[item] = updated_price
                except ValueError:
                    return f"Invalid input for item {item}: Please enter a valid number.", 400
            else:
                return f"Price not provided for item {item}", 400
        
        # Update the city prices
        city_prices[city].update(updated_prices)
        save_game_state()  # Optionally save the state after the update
    
    return redirect(url_for('admin'))


@app.route('/push_news', methods=['POST'])
def push_news():
    news_message = request.form.get('news_message')
    # You can store this message in a global variable, or integrate a notification system
    global breaking_news
    breaking_news = news_message
    
    return redirect(url_for('admin'))




# ------------------------------------------------------------------
#  Toggle city open / closed from the admin panel
# ------------------------------------------------------------------
@app.route('/update_city_status', methods=['POST'])
def update_city_status():
    global closed_cities
    # Flask builds a list containing the value for every checked box
    closed_cities = request.form.getlist('closed_cities')
    save_game_state()
    return redirect(url_for('admin'))


# ------------------------------------------------------------------
#  Adjust player balances (admin only)
# ------------------------------------------------------------------
@app.route('/adjust_money', methods=['POST'])
def adjust_money():
    # Every input uses the player-name as its field name
    for player_name, delta_str in request.form.items():
        try:
            delta = int(delta_str)
        except ValueError:
            continue            # ignore blanks / bad input
        players[player_name]['money'] += delta
        # optional audit log:
        players[player_name]['transaction_log'].append(
            f"Admin adjustment: €{delta:+d}"
        )
        players[player_name]['transaction_log'].append(
            {"ts": iso_now(), "money": players[player_name]['money']}
        )
        save_game_state()
    return redirect(url_for('admin'))

@app.route('/upgrade_truck', methods=['POST'])
def upgrade_truck():
    if selected_city != "Vogn Manden":
        return jsonify(success=False, message="Upgrades only available in the Vogn Manden.")
    player = players[selected_player]
    cost = next_upgrade_cost(player["capacity"])
    if player["money"] < cost:
        return jsonify(success=False, message="Not enough cash for that upgrade.")
    # Perform upgrade
    player["money"]   -= cost
    player["capacity"] += 1
    player["cargo"].append("")            # new empty slot
    player["transaction_log"].append(
        f"Upgraded truck to {player['capacity']} pallets for €{cost}."
    )
    player["transaction_log"].append(
        {"ts": iso_now(), "money": player["money"]}
    )
    save_game_state()
    return jsonify(success=True)

# ------------------------------------------------------------------
#  Hard reset – starts a brand-new game with default data
# ------------------------------------------------------------------
@app.route('/reset_game', methods=['POST'])
def reset_game():
    global players, selected_city, selected_player
    global city_prices, breaking_news, closed_cities

    # Fresh deep copies so we don't accidentally share state
    players         = copy.deepcopy(DEFAULT_PLAYERS)
    selected_city   = next(iter(DEFAULT_CITY_PRICES_EU))
    selected_player = "Player 1"
    city_prices     = copy.deepcopy(DEFAULT_CITY_PRICES_EU)
    breaking_news   = ""
    closed_cities   = []

    save_game_state()
    return redirect(url_for('admin'))

@app.route('/breaking_news')
def get_breaking_news():
    """Return the current breaking-news string for AJAX polling."""
    return jsonify(news=breaking_news)


def iso_minute(dt: datetime) -> str:
    return dt.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")

@app.route('/money_series')
def money_series():
    """
    Return per-player balances aggregated to 1-minute buckets,
    filled forward over a configurable window (default 2 hours).
    Query param: ?hours=24  (clamped 1..168)
    """
    try:
        hours = int(request.args.get("hours", 2))
    except Exception:
        hours = 2
    hours = max(1, min(hours, 168))

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(hours=hours)

    def iso_minute(dt: datetime) -> str:
        return dt.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")

    series = {}
    for name, pdata in players.items():
        # Collect minute → money snapshots from the log
        buckets = {}
        for rec in pdata.get("transaction_log", []):
            if not isinstance(rec, dict):
                continue  # skip legacy string entries
            try:
                t = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except Exception:
                continue
            t = t.replace(second=0, microsecond=0)
            buckets[t] = rec["money"]  # last value in that minute wins

        # Start from the last known balance BEFORE the window; otherwise leave undefined
        last_val = None
        if buckets:
            before = [t for t in buckets.keys() if t < start]
            if before:
                last_val = buckets[max(before)]

        # Build minute-by-minute series; no prefill if no prior value
        pts = []
        t = start
        while t <= now:
            if t in buckets:
                last_val = buckets[t]
            # Append None (→ null in JSON) until we have the first known value
            pts.append([iso_minute(t), last_val])
            t += timedelta(minutes=1)

        series[name] = pts


    resp = jsonify(series)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    return resp


# ------------------------------------------------------------------
#  ADD a player
# ------------------------------------------------------------------
@app.route('/add_player', methods=['POST'])
def add_player():
    name = request.form.get('new_player_name', '').strip()
    if not name or name in players:
        return redirect(url_for('admin'))
    players[name] = {
        "money": 100,
        "capacity": 2,
        "cargo": ["", ""],
        "transaction_log": []
    }
    players[name]["transaction_log"].append({"ts": iso_now(), "money": players[name]["money"]})

    save_game_state()
    return redirect(url_for('admin'))


# ------------------------------------------------------------------
#  RENAME a player
# ------------------------------------------------------------------
@app.route('/rename_player', methods=['POST'])
def rename_player():
    old = request.form.get('old_name')
    new = request.form.get('new_name', '').strip()
    if (not old or not new or
            old not in players or
            new in players):
        return redirect(url_for('admin'))

    players[new] = players.pop(old)
    global selected_player
    if selected_player == old:
        selected_player = new
    save_game_state()
    return redirect(url_for('admin'))


# ------------------------------------------------------------------
#  DELETE a player
# ------------------------------------------------------------------
@app.route('/delete_player', methods=['POST'])
def delete_player():
    name = request.form.get('delete_player_name')
    if name in players:
        players.pop(name)
        global selected_player
        if selected_player == name:
            # pick the first remaining name or blank if none
            selected_player = next(iter(players), '')
        save_game_state()
    return redirect(url_for('admin'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # bind to 0.0.0.0 and use Render's $PORT
    app.run(host="0.0.0.0", port=port, debug=False)


