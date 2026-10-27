import tempfile
import unittest

from server import create_app
from tests.helpers import make_word_manager


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.app = create_app(make_word_manager(self._tmp.name))
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def new_game(self, difficulty="easy"):
        response = self.client.post("/api/games", json={"difficulty": difficulty})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def guess(self, game_id, letter):
        return self.client.post(f"/api/games/{game_id}/guess", json={"letter": letter})

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.get_json())
        self.assertTrue(response.is_json)
        body = response.get_json()
        self.assertEqual(body["code"], code)
        self.assertIsInstance(body["error"], str)


class TestCreateGame(ApiTestCase):
    def test_create_game_response(self):
        body = self.new_game("medium")
        self.assertEqual(
            set(body),
            {
                "game_id",
                "difficulty",
                "pattern",
                "guessed_letters",
                "incorrect_letters",
                "remaining_guesses",
                "status",
            },
        )
        self.assertEqual(body["difficulty"], "medium")
        self.assertEqual(body["pattern"], "_ _ _ _ _ _")
        self.assertEqual(body["remaining_guesses"], 6)
        self.assertEqual(body["status"], "playing")

    def test_each_difficulty_uses_its_word_list(self):
        for difficulty, length in [("easy", 3), ("medium", 6), ("hard", 6)]:
            with self.subTest(difficulty=difficulty):
                body = self.new_game(difficulty)
                self.assertEqual(body["pattern"].count("_"), length)

    def test_difficulty_is_normalized(self):
        self.assertEqual(self.new_game("HARD")["difficulty"], "hard")

    def test_game_ids_are_unique(self):
        ids = {self.new_game()["game_id"] for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertEqual(len(self.app.config["GAME_STORE"]), 50)

    def test_invalid_difficulty(self):
        for difficulty in ["expert", "", None, 3]:
            with self.subTest(difficulty=difficulty):
                response = self.client.post("/api/games", json={"difficulty": difficulty})
                self.assert_error(response, 400, "invalid_difficulty")

    def test_missing_difficulty(self):
        response = self.client.post("/api/games", json={})
        self.assert_error(response, 400, "invalid_difficulty")

    def test_malformed_bodies(self):
        cases = [
            {"data": "not json", "content_type": "application/json"},
            {"data": '{"difficulty": ', "content_type": "application/json"},
            {"data": '["easy"]', "content_type": "application/json"},
            {"data": '"easy"', "content_type": "application/json"},
            {"data": "difficulty=easy", "content_type": "application/x-www-form-urlencoded"},
            {},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                response = self.client.post("/api/games", **kwargs)
                self.assert_error(response, 400, "malformed_request")


class TestGetGame(ApiTestCase):
    def test_get_returns_current_state(self):
        game_id = self.new_game()["game_id"]
        self.guess(game_id, "c")
        self.guess(game_id, "z")
        body = self.client.get(f"/api/games/{game_id}").get_json()
        self.assertEqual(body["game_id"], game_id)
        self.assertEqual(body["pattern"], "c _ _")
        self.assertEqual(body["guessed_letters"], ["c", "z"])
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)
        self.assertEqual(body["status"], "playing")

    def test_unknown_game_id(self):
        self.assert_error(self.client.get("/api/games/nope"), 404, "game_not_found")


class TestGuess(ApiTestCase):
    def test_correct_guess(self):
        game_id = self.new_game()["game_id"]
        response = self.guess(game_id, "a")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["correct"])
        self.assertEqual(body["pattern"], "_ a _")
        self.assertEqual(body["guessed_letters"], ["a"])
        self.assertEqual(body["remaining_guesses"], 6)

    def test_incorrect_guess(self):
        game_id = self.new_game()["game_id"]
        body = self.guess(game_id, "z").get_json()
        self.assertFalse(body["correct"])
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)

    def test_uppercase_guess_accepted(self):
        game_id = self.new_game()["game_id"]
        self.assertEqual(self.guess(game_id, "C").get_json()["pattern"], "c _ _")

    def test_invalid_guesses_do_not_change_state(self):
        game_id = self.new_game()["game_id"]
        before = self.client.get(f"/api/games/{game_id}").get_json()
        for letter in ["", "ab", "1", "?", None, 7, ["a"]]:
            with self.subTest(letter=letter):
                self.assert_error(self.guess(game_id, letter), 400, "invalid_guess")
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), before)

    def test_missing_letter(self):
        game_id = self.new_game()["game_id"]
        response = self.client.post(f"/api/games/{game_id}/guess", json={})
        self.assert_error(response, 400, "invalid_guess")

    def test_malformed_guess_body(self):
        game_id = self.new_game()["game_id"]
        response = self.client.post(
            f"/api/games/{game_id}/guess", data="a", content_type="application/json"
        )
        self.assert_error(response, 400, "malformed_request")

    def test_duplicate_guess(self):
        game_id = self.new_game()["game_id"]
        self.guess(game_id, "z")
        before = self.client.get(f"/api/games/{game_id}").get_json()
        self.assert_error(self.guess(game_id, "z"), 409, "duplicate_guess")
        self.assert_error(self.guess(game_id, "Z"), 409, "duplicate_guess")
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), before)

    def test_guess_on_unknown_game(self):
        self.assert_error(self.guess("nope", "a"), 404, "game_not_found")


class TestFullGames(ApiTestCase):
    def test_win_reveals_word(self):
        game_id = self.new_game()["game_id"]
        for letter in "ca":
            self.assertEqual(self.guess(game_id, letter).get_json()["status"], "playing")
        body = self.guess(game_id, "t").get_json()
        self.assertEqual(body["status"], "won")
        self.assertEqual(body["word"], "cat")
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json()["word"], "cat")

    def test_loss_reveals_word(self):
        game_id = self.new_game()["game_id"]
        for letter in "bdefg":
            self.assertEqual(self.guess(game_id, letter).get_json()["status"], "playing")
        body = self.guess(game_id, "h").get_json()
        self.assertEqual(body["status"], "lost")
        self.assertEqual(body["remaining_guesses"], 0)
        self.assertEqual(body["word"], "cat")

    def test_no_guesses_after_game_over(self):
        game_id = self.new_game()["game_id"]
        for letter in "cat":
            self.guess(game_id, letter)
        self.assert_error(self.guess(game_id, "z"), 409, "game_over")

    def test_games_are_independent(self):
        first = self.new_game()["game_id"]
        second = self.new_game()["game_id"]
        self.guess(first, "z")
        body = self.client.get(f"/api/games/{second}").get_json()
        self.assertEqual(body["incorrect_letters"], [])


class TestNoAnswerLeak(ApiTestCase):
    def test_word_never_appears_while_playing(self):
        game_id = self.new_game("medium")["game_id"]
        responses = [self.client.get(f"/api/games/{game_id}")]
        # Guess every letter of "rabbit" except "t", plus a few misses.
        for letter in "rabizyx":
            responses.append(self.guess(game_id, letter))
        responses.append(self.guess(game_id, "r"))  # duplicate -> error response
        responses.append(self.guess(game_id, "1"))  # invalid -> error response
        responses.append(self.client.get(f"/api/games/{game_id}"))
        for response in responses:
            body = response.get_json()
            self.assertNotIn("word", body)
            self.assertNotIn("rabbit", response.get_data(as_text=True))
        self.assertEqual(responses[-1].get_json()["status"], "playing")


class TestHttpErrors(ApiTestCase):
    def test_unknown_route_returns_json(self):
        self.assert_error(self.client.get("/api/nothing"), 404, "not_found")

    def test_wrong_method_returns_json(self):
        self.assert_error(self.client.get("/api/games"), 405, "method_not_allowed")
        game_id = self.new_game()["game_id"]
        self.assert_error(
            self.client.get(f"/api/games/{game_id}/guess"), 405, "method_not_allowed"
        )


if __name__ == "__main__":
    unittest.main()
