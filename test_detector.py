import importlib
import os
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("RIOT_API_KEY", "test-key")
os.environ.setdefault(
    "MONITORED_RIOT_IDS",
    "Phvoundves#EUNE;Joshua Graham#DND",
)
detector = importlib.import_module("detector")


class DetectorTests(unittest.TestCase):
    def test_map_names(self):
        self.assertEqual(detector.map_name(11), "Summoner's Rift")
        self.assertEqual(detector.map_name(12), "Howling Abyss")
        self.assertEqual(detector.map_name(999), "Map 999")

    @patch.object(detector, "get_active_game")
    def test_tracks_one_game_id(self, get_game):
        player = detector.Player("Test", "EUNE", puuid="puuid")
        get_game.return_value = {"gameId": 123}
        detector.check_player(player)
        detector.check_player(player)
        self.assertEqual(player.last_game_id, "123")

    @patch.object(detector, "get_active_game", return_value=None)
    def test_resets_after_game(self, _get_game):
        player = detector.Player("Test", "EUNE", puuid="puuid", last_game_id="123")
        detector.check_player(player)
        self.assertIsNone(player.last_game_id)

    def test_public_status_detected(self):
        with detector.STATUS_LOCK:
            detector.PLAYER_STATUS["Phvoundves#EUNE"]["in_game"] = True
        self.assertTrue(detector.public_status()["detected"])
        with detector.STATUS_LOCK:
            detector.PLAYER_STATUS["Phvoundves#EUNE"]["in_game"] = False


if __name__ == "__main__":
    unittest.main()
