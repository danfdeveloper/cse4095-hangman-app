import unittest

from hangman_client import ApiError, HangmanClient, ServerUnavailableError
from terminal_client import (
    GALLOWS,
    TerminalGame,
    gallows_stage,
    guesses_phrase,
    is_single_letter,
)
from tests.helpers import LiveServerTestCase, unused_port_url


class ScriptedIO:
    """Feeds scripted input lines and records everything printed."""

    def __init__(self, lines):
        self._lines = list(lines)
        self.prompts = []
        self.output = []

    def input(self, prompt):
        self.prompts.append(prompt)
        if not self._lines:
            raise EOFError
        line = self._lines.pop(0)
        if isinstance(line, BaseException):
            raise line
        return line

    def print(self, text=""):
        self.output.append(text)

    @property
    def text(self):
        return "\n".join(self.output)


def run_game(client, lines):
    io = ScriptedIO(lines)
    TerminalGame(client, input_fn=io.input, output_fn=io.print).run()
    return io


class TestHelpers(unittest.TestCase):
    def test_gallows_stage(self):
        self.assertEqual(gallows_stage(0, 6), 0)
        self.assertEqual(gallows_stage(3, 6), 3)
        self.assertEqual(gallows_stage(6, 6), 6)
        self.assertEqual(gallows_stage(1, 2), 3)
        self.assertEqual(gallows_stage(9, 6), 6)
        self.assertEqual(gallows_stage(0, 0), len(GALLOWS) - 1)

    def test_guesses_phrase(self):
        self.assertEqual(guesses_phrase(1), "1 incorrect guess")
        self.assertEqual(guesses_phrase(0), "0 incorrect guesses")
        self.assertEqual(guesses_phrase(5), "5 incorrect guesses")

    def test_is_single_letter(self):
        for text in ["a", "Z"]:
            self.assertTrue(is_single_letter(text))
        for text in ["", "ab", "1", "?", "é", " "]:
            self.assertFalse(is_single_letter(text))


class TestTerminalGameAgainstServer(LiveServerTestCase):
    def setUp(self):
        self.client = HangmanClient(self.server_url)

    def test_win_then_quit(self):
        io = run_game(self.client, ["1", "c", "a", "t", "n"])
        self.assertIn("Welcome to Hangman!", io.text)
        self.assertIn("Word:       c a t", io.text)
        self.assertIn("You won! The word was 'cat' (6 incorrect guesses to spare).", io.text)
        self.assertTrue(io.output[-1].startswith("Goodbye"))

    def test_loss(self):
        io = run_game(self.client, ["easy", *"bdefgh", "n"])
        self.assertIn("You lost. The word was 'cat'.", io.text)
        self.assertIn("Remaining:  0 incorrect guesses left", io.text)
        self.assertIn(GALLOWS[6][4], io.output)

    def test_display_tracks_guesses(self):
        io = run_game(self.client, ["1", "z", "c", "quit"])
        self.assertIn("Guessed:    z, c", io.text)
        self.assertIn("Incorrect:  z", io.text)
        self.assertIn("Remaining:  5 incorrect guesses left", io.text)
        self.assertIn("Word:       c _ _", io.text)

    def test_difficulty_choices(self):
        for choice, blanks in [("2", "_ _ _ _ _ _"), ("Hard", "_ _ _ _ _ _"), ("e", "_ _ _")]:
            with self.subTest(choice=choice):
                io = run_game(self.client, [choice, "quit"])
                self.assertIn(f"Word:       {blanks}", io.text)

    def test_invalid_difficulty_reprompts(self):
        io = run_game(self.client, ["9", "expert", "1", "quit"])
        self.assertEqual(io.output.count("Please enter 1, 2, or 3."), 2)
        self.assertIn("New easy game started.", io.text)

    def test_invalid_letters_handled_locally(self):
        io = run_game(self.client, ["1", "ab", "7", "", "c", "C", "quit"])
        self.assertEqual(io.output.count("Please enter a single letter a-z."), 3)
        self.assertIn("You already guessed 'c'.", io.text)
        self.assertNotIn("Server rejected", io.text)

    def test_play_again(self):
        io = run_game(self.client, ["1", "c", "a", "t", "y", "1", *"bdefgh", "no"])
        self.assertIn("You won!", io.text)
        self.assertIn("You lost.", io.text)
        self.assertEqual(io.text.count("New easy game started."), 2)

    def test_play_again_reprompts(self):
        io = run_game(self.client, ["1", "c", "a", "t", "maybe", "n"])
        self.assertIn("Please answer y or n.", io.text)

    def test_quit_at_menu(self):
        io = run_game(self.client, ["q"])
        self.assertEqual(io.output, ["Welcome to Hangman!", "Goodbye!"])

    def test_end_of_input_and_ctrl_c_exit_cleanly(self):
        for ending in [EOFError(), KeyboardInterrupt()]:
            with self.subTest(ending=type(ending).__name__):
                io = run_game(self.client, ["1", "c", ending])
                self.assertEqual(io.output[-1], "Goodbye!")

    def test_word_not_shown_until_game_ends(self):
        io = run_game(self.client, ["2", "r", "a", "b", "quit"])
        self.assertNotIn("rabbit", io.text)


class FakeClient:
    """Stands in for HangmanClient to simulate server failures."""

    def __init__(self, guess_errors=(), get_error=None):
        self.guess_errors = list(guess_errors)
        self.get_error = get_error
        self.state = {
            "game_id": "g1",
            "pattern": "_ _ _",
            "guessed_letters": [],
            "incorrect_letters": [],
            "remaining_guesses": 6,
            "status": "playing",
        }

    def create_game(self, difficulty):
        return dict(self.state)

    def guess(self, game_id, letter):
        if self.guess_errors:
            raise self.guess_errors.pop(0)
        self.state["guessed_letters"].append(letter)
        self.state.update(pattern="c a t", status="won", word="cat")
        return dict(self.state)

    def get_game(self, game_id):
        if self.get_error:
            raise self.get_error
        return dict(self.state)


class TestServerErrors(unittest.TestCase):
    def test_server_down_at_start(self):
        client = HangmanClient(unused_port_url(), timeout=2)
        io = run_game(client, ["1", "n"])
        self.assertIn("Could not start a game: could not reach the server", io.text)
        self.assertEqual(io.output[-1], "Goodbye!")

    def test_server_down_mid_game_lets_player_retry(self):
        client = FakeClient(guess_errors=[ServerUnavailableError("could not reach the server")])
        io = run_game(client, ["1", "c", "c", "n"])
        self.assertIn("could not reach the server. Try again, or type quit to leave.", io.text)
        self.assertIn("You won!", io.text)

    def test_rejected_guess_resyncs_with_server(self):
        client = FakeClient(guess_errors=[ApiError(409, "duplicate_guess", "'c' has already been guessed")])
        io = run_game(client, ["1", "c", "c", "n"])
        self.assertIn("Server rejected the guess: 'c' has already been guessed", io.text)
        self.assertIn("You won!", io.text)

    def test_game_lost_by_server_ends_game(self):
        client = FakeClient(
            guess_errors=[ApiError(404, "game_not_found", "no game")],
            get_error=ApiError(404, "game_not_found", "no game"),
        )
        io = run_game(client, ["1", "c", "n"])
        self.assertIn("The server no longer has this game", io.text)
        self.assertNotIn("You won!", io.text)
        self.assertEqual(io.output[-1], "Goodbye!")


if __name__ == "__main__":
    unittest.main()
