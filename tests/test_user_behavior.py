import copy
import tempfile
import unittest
from pathlib import Path

import app as truckerspil_app


class UserBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        truckerspil_app.BACKUP_FILE = Path(self.temp_dir.name) / "game_state.json"

        truckerspil_app.players = copy.deepcopy(truckerspil_app.DEFAULT_PLAYERS)
        truckerspil_app.selected_city = "Tokyo"
        truckerspil_app.selected_player = "Player 1"
        truckerspil_app.city_prices = copy.deepcopy(truckerspil_app.DEFAULT_CITY_PRICES_EU)
        truckerspil_app.breaking_news = ""
        truckerspil_app.closed_cities = []
        truckerspil_app.vogn_settings = copy.deepcopy(truckerspil_app.DEFAULT_VOGN_SETTINGS)
        truckerspil_app.cities = list(truckerspil_app.city_prices.keys())

        self.client = truckerspil_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_index_shows_market_in_regular_city(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Markedet i Tokyo", html)
        self.assertNotIn("Køb opgradering", html)

    def test_set_city_redirects_to_player_page_and_persists_city(self):
        response = self.client.post(
            "/set_city",
            data={"city": truckerspil_app.UPGRADE_CITY, "player": "Player 2"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/p/Player%202"))
        self.assertEqual(truckerspil_app.selected_city, truckerspil_app.UPGRADE_CITY)

    def test_upgrade_option_is_visible_in_yamato_workshop(self):
        truckerspil_app.selected_city = truckerspil_app.UPGRADE_CITY

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Yamato værksted", html)
        self.assertIn("Køb opgradering", html)

    def test_buy_item_updates_money_cargo_and_log(self):
        response = self.client.post(
            "/buy",
            data={"player": "Player 1", "item": "Nudler"},
        )

        payload = response.get_json()
        player = truckerspil_app.players["Player 1"]

        self.assertTrue(payload["success"])
        self.assertEqual(player["cargo"][0], "Nudler")
        self.assertEqual(player["money"], 9100)
        self.assertTrue(any("Købte Nudler" in entry for entry in player["transaction_log"] if isinstance(entry, str)))

    def test_sell_item_updates_money_cargo_and_log(self):
        player = truckerspil_app.players["Player 1"]
        player["cargo"][0] = "Nudler"
        player["money"] = 5000

        response = self.client.post(
            "/sell",
            data={"player": "Player 1", "space": "1"},
        )

        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(player["cargo"][0], "")
        self.assertEqual(player["money"], 5900)
        self.assertTrue(any("Solgte Nudler" in entry for entry in player["transaction_log"] if isinstance(entry, str)))

    def test_clear_item_empties_cargo_slot(self):
        player = truckerspil_app.players["Player 1"]
        player["cargo"][0] = "Nudler"

        response = self.client.post(
            "/clear",
            data={"player": "Player 1", "space": "1"},
        )

        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(player["cargo"][0], "")

    def test_upgrade_truck_in_workshop_increases_capacity_and_deducts_money(self):
        player = truckerspil_app.players["Player 1"]
        truckerspil_app.selected_city = truckerspil_app.UPGRADE_CITY

        response = self.client.post(
            "/upgrade_truck",
            data={"player": "Player 1"},
        )

        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(player["capacity"], 3)
        self.assertEqual(len(player["cargo"]), 3)
        self.assertEqual(player["money"], 5000)

    def test_upgrade_truck_fails_outside_workshop(self):
        player = truckerspil_app.players["Player 1"]
        truckerspil_app.selected_city = "Tokyo"

        response = self.client.post(
            "/upgrade_truck",
            data={"player": "Player 1"},
        )

        payload = response.get_json()

        self.assertFalse(payload["success"])
        self.assertEqual(player["capacity"], 2)
        self.assertIn(truckerspil_app.UPGRADE_CITY, payload["message"])

    def test_upgrade_truck_fails_when_player_cannot_afford_it(self):
        player = truckerspil_app.players["Player 1"]
        player["money"] = 4999
        truckerspil_app.selected_city = truckerspil_app.UPGRADE_CITY

        response = self.client.post(
            "/upgrade_truck",
            data={"player": "Player 1"},
        )

        payload = response.get_json()

        self.assertFalse(payload["success"])
        self.assertEqual(player["capacity"], 2)
        self.assertIn("ikke yen nok", payload["message"])


if __name__ == "__main__":
    unittest.main()
