import unittest

from hangman_client import ApiError, HangmanClient, ServerUnavailableError
from tests.helpers import LiveServerTestCase, unused_port_url


class TestHangmanClient(LiveServerTestCase):
    def setUp(self):
        self.client = HangmanClient(self.server_url)

    def test_play_full_game(self):
        state = self.client.create_game("easy")
        self.assertEqual(state["pattern"], "_ _ _")
        game_id = state["game_id"]
        self.assertEqual(self.client.guess(game_id, "c")["pattern"], "c _ _")
        self.assertEqual(self.client.get_game(game_id)["guessed_letters"], ["c"])
        self.client.guess(game_id, "a")
        final = self.client.guess(game_id, "t")
        self.assertEqual(final["status"], "won")
        self.assertEqual(final["word"], "cat")

    def test_trailing_slash_in_url(self):
        client = HangmanClient(self.server_url + "/")
        self.assertEqual(client.create_game("easy")["status"], "playing")

    def test_api_errors_carry_status_and_code(self):
        cases = [
            (lambda: self.client.create_game("expert"), 400, "invalid_difficulty"),
            (lambda: self.client.get_game("missing"), 404, "game_not_found"),
            (lambda: self.client.guess("missing", "a"), 404, "game_not_found"),
        ]
        for call, status, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ApiError) as ctx:
                    call()
                self.assertEqual(ctx.exception.status, status)
                self.assertEqual(ctx.exception.code, code)
                self.assertTrue(ctx.exception.message)

    def test_duplicate_guess_error(self):
        game_id = self.client.create_game("easy")["game_id"]
        self.client.guess(game_id, "z")
        with self.assertRaises(ApiError) as ctx:
            self.client.guess(game_id, "z")
        self.assertEqual(ctx.exception.code, "duplicate_guess")

    def test_odd_game_ids_are_not_found(self):
        for game_id in ["../games", "a/b", "a b", "?x=1"]:
            with self.subTest(game_id=game_id):
                with self.assertRaises(ApiError) as ctx:
                    self.client.get_game(game_id)
                self.assertEqual(ctx.exception.status, 404)


class TestServerUnavailable(unittest.TestCase):
    def test_unreachable_server(self):
        client = HangmanClient(unused_port_url(), timeout=2)
        with self.assertRaises(ServerUnavailableError):
            client.create_game("easy")


if __name__ == "__main__":
    unittest.main()
