import unittest

from game import (
    DEFAULT_MAX_INCORRECT,
    STATUS_LOST,
    STATUS_PLAYING,
    STATUS_WON,
    DuplicateGuessError,
    GameOverError,
    GuessError,
    HangmanGame,
    InvalidGuessError,
)


class TestConstruction(unittest.TestCase):
    def test_new_game_initial_state(self):
        game = HangmanGame("apple")
        self.assertEqual(game.status, STATUS_PLAYING)
        self.assertEqual(game.pattern, "_ _ _ _ _")
        self.assertEqual(game.guessed_letters, [])
        self.assertEqual(game.incorrect_letters, [])
        self.assertEqual(game.remaining_guesses, DEFAULT_MAX_INCORRECT)

    def test_default_allows_six_incorrect_guesses(self):
        self.assertEqual(DEFAULT_MAX_INCORRECT, 6)

    def test_word_is_lowercased(self):
        game = HangmanGame("ApPle")
        game.guess("a")
        self.assertEqual(game.pattern, "a _ _ _ _")

    def test_rejects_bad_words(self):
        for word in ["", "two words", "abc1", "don't", "café", None, 42]:
            with self.subTest(word=word):
                with self.assertRaises(ValueError):
                    HangmanGame(word)

    def test_rejects_bad_max_incorrect(self):
        for value in [0, -1, 2.5, "6"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    HangmanGame("apple", max_incorrect=value)


class TestGuessing(unittest.TestCase):
    def test_correct_guess_reveals_all_positions(self):
        game = HangmanGame("eerie")
        self.assertTrue(game.guess("e"))
        self.assertEqual(game.pattern, "e e _ _ e")
        self.assertEqual(game.incorrect_letters, [])
        self.assertEqual(game.remaining_guesses, 6)

    def test_incorrect_guess_costs_a_life(self):
        game = HangmanGame("apple")
        self.assertFalse(game.guess("z"))
        self.assertEqual(game.incorrect_letters, ["z"])
        self.assertEqual(game.remaining_guesses, 5)
        self.assertEqual(game.pattern, "_ _ _ _ _")

    def test_guessed_letters_keep_guess_order(self):
        game = HangmanGame("apple")
        for letter in "zpa":
            game.guess(letter)
        self.assertEqual(game.guessed_letters, ["z", "p", "a"])
        self.assertEqual(game.incorrect_letters, ["z"])

    def test_uppercase_guess_is_normalized(self):
        game = HangmanGame("apple")
        self.assertTrue(game.guess("A"))
        self.assertEqual(game.guessed_letters, ["a"])

    def test_invalid_guesses_rejected_without_state_change(self):
        game = HangmanGame("apple")
        game.guess("a")
        before = game.to_dict()
        for bad in ["", "ab", "1", "!", " ", "é", None, 5]:
            with self.subTest(guess=bad):
                with self.assertRaises(InvalidGuessError):
                    game.guess(bad)
                self.assertEqual(game.to_dict(), before)

    def test_duplicate_guess_rejected_without_state_change(self):
        game = HangmanGame("apple")
        game.guess("a")
        game.guess("z")
        before = game.to_dict()
        for dup in ["a", "A", "z"]:
            with self.subTest(guess=dup):
                with self.assertRaises(DuplicateGuessError):
                    game.guess(dup)
                self.assertEqual(game.to_dict(), before)

    def test_guess_errors_share_a_base_class(self):
        for cls in (InvalidGuessError, DuplicateGuessError, GameOverError):
            self.assertTrue(issubclass(cls, GuessError))


class TestWinAndLoss(unittest.TestCase):
    def test_win(self):
        game = HangmanGame("apple")
        for letter in "ape":
            game.guess(letter)
            self.assertEqual(game.status, STATUS_PLAYING)
        game.guess("l")
        self.assertEqual(game.status, STATUS_WON)
        self.assertTrue(game.is_over)
        self.assertEqual(game.pattern, "a p p l e")

    def test_win_with_misses_keeps_remaining_guesses(self):
        game = HangmanGame("cat")
        for letter in "xyzcat":
            game.guess(letter)
        self.assertEqual(game.status, STATUS_WON)
        self.assertEqual(game.remaining_guesses, 3)

    def test_win_on_last_life(self):
        game = HangmanGame("cat")
        for letter in "bdefg":
            game.guess(letter)
        self.assertEqual(game.remaining_guesses, 1)
        for letter in "cat":
            game.guess(letter)
        self.assertEqual(game.status, STATUS_WON)
        self.assertEqual(game.remaining_guesses, 1)

    def test_loss_after_six_misses(self):
        game = HangmanGame("cat")
        for letter in "bdefg":
            game.guess(letter)
            self.assertEqual(game.status, STATUS_PLAYING)
        game.guess("h")
        self.assertEqual(game.status, STATUS_LOST)
        self.assertEqual(game.remaining_guesses, 0)

    def test_custom_max_incorrect(self):
        game = HangmanGame("cat", max_incorrect=2)
        game.guess("x")
        game.guess("y")
        self.assertEqual(game.status, STATUS_LOST)

    def test_no_guesses_after_game_over(self):
        for letters in ["cat", "bdefgh"]:
            with self.subTest(letters=letters):
                game = HangmanGame("cat")
                for letter in letters:
                    game.guess(letter)
                before = game.to_dict()
                with self.assertRaises(GameOverError):
                    game.guess("z")
                self.assertEqual(game.to_dict(), before)


class TestAnswerDisclosure(unittest.TestCase):
    def test_state_omits_word_while_playing(self):
        game = HangmanGame("secret")
        game.guess("e")
        game.guess("z")
        state = game.to_dict()
        self.assertEqual(state["status"], STATUS_PLAYING)
        self.assertNotIn("word", state)
        self.assertNotIn("secret", str(state))

    def test_repr_never_contains_word(self):
        game = HangmanGame("secret")
        self.assertNotIn("secret", repr(game))

    def test_state_includes_word_after_win(self):
        game = HangmanGame("cat")
        for letter in "cat":
            game.guess(letter)
        self.assertEqual(game.to_dict()["word"], "cat")

    def test_state_includes_word_after_loss(self):
        game = HangmanGame("cat")
        for letter in "bdefgh":
            game.guess(letter)
        state = game.to_dict()
        self.assertEqual(state["status"], STATUS_LOST)
        self.assertEqual(state["word"], "cat")

    def test_state_shape(self):
        state = HangmanGame("apple").to_dict()
        self.assertEqual(
            state,
            {
                "pattern": "_ _ _ _ _",
                "guessed_letters": [],
                "incorrect_letters": [],
                "remaining_guesses": 6,
                "status": "playing",
            },
        )

    def test_state_lists_are_copies(self):
        game = HangmanGame("apple")
        game.guess("z")
        state = game.to_dict()
        state["guessed_letters"].append("a")
        state["incorrect_letters"].clear()
        self.assertEqual(game.guessed_letters, ["z"])
        self.assertEqual(game.incorrect_letters, ["z"])


if __name__ == "__main__":
    unittest.main()
