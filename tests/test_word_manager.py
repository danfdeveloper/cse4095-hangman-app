import random
import tempfile
import unittest
from pathlib import Path

from game import HangmanGame
from word_manager import (
    DIFFICULTIES,
    InvalidDifficultyError,
    WordListError,
    WordManager,
    load_word_file,
    normalize_difficulty,
)


class TempWordsDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_all(self, easy="cat\n", medium="rabbit\n", hard="rhythm\n"):
        self.write("easy.txt", easy)
        self.write("medium.txt", medium)
        self.write("hard.txt", hard)


class TestLoadWordFile(TempWordsDir):
    def test_loads_words_in_order(self):
        path = self.write("w.txt", "cat\ndog\nbird\n")
        self.assertEqual(load_word_file(path), ["cat", "dog", "bird"])

    def test_strips_whitespace_and_skips_blank_lines(self):
        path = self.write("w.txt", "  cat  \n\n\t\ndog\r\n")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_lowercases_words(self):
        path = self.write("w.txt", "Cat\nDOG\n")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_removes_duplicates_keeping_first(self):
        path = self.write("w.txt", "cat\ndog\ncat\nCAT\ndog\n")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_rejects_non_alphabetic_entries(self):
        for bad in ["c4t", "ice cream", "don't", "café", "x-ray"]:
            with self.subTest(entry=bad):
                path = self.write("w.txt", f"cat\n{bad}\n")
                with self.assertRaises(WordListError) as ctx:
                    load_word_file(path)
                self.assertIn(":2:", str(ctx.exception))

    def test_rejects_empty_file(self):
        for text in ["", "\n\n  \n"]:
            with self.subTest(text=text):
                path = self.write("w.txt", text)
                with self.assertRaises(WordListError):
                    load_word_file(path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_word_file(self.dir / "missing.txt")


class TestNormalizeDifficulty(unittest.TestCase):
    def test_accepts_known_difficulties(self):
        for value, expected in [
            ("easy", "easy"),
            ("Medium", "medium"),
            (" HARD ", "hard"),
        ]:
            with self.subTest(value=value):
                self.assertEqual(normalize_difficulty(value), expected)

    def test_rejects_unknown_difficulties(self):
        for value in ["", "expert", "med", None, 1, ["easy"]]:
            with self.subTest(value=value):
                with self.assertRaises(InvalidDifficultyError):
                    normalize_difficulty(value)

    def test_invalid_difficulty_is_a_value_error(self):
        self.assertTrue(issubclass(InvalidDifficultyError, ValueError))


class TestWordManager(TempWordsDir):
    def test_loads_each_difficulty(self):
        self.write_all(easy="cat\ndog\n", medium="rabbit\n", hard="rhythm\nfjord\n")
        manager = WordManager(self.dir)
        self.assertEqual(manager.words("easy"), ["cat", "dog"])
        self.assertEqual(manager.words("medium"), ["rabbit"])
        self.assertEqual(manager.words("hard"), ["rhythm", "fjord"])

    def test_missing_difficulty_file_raises(self):
        self.write("easy.txt", "cat\n")
        self.write("medium.txt", "rabbit\n")
        with self.assertRaises(FileNotFoundError):
            WordManager(self.dir)

    def test_invalid_word_file_raises(self):
        self.write_all(hard="rhythm\nbad word\n")
        with self.assertRaises(WordListError):
            WordManager(self.dir)

    def test_random_word_comes_from_requested_difficulty(self):
        self.write_all(easy="cat\ndog\n", medium="rabbit\nturtle\n", hard="rhythm\nfjord\n")
        manager = WordManager(self.dir)
        for difficulty in DIFFICULTIES:
            allowed = set(manager.words(difficulty))
            for _ in range(50):
                self.assertIn(manager.random_word(difficulty), allowed)

    def test_random_word_eventually_picks_every_word(self):
        self.write_all(easy="cat\ndog\nfish\n")
        manager = WordManager(self.dir, rng=random.Random(0))
        picks = {manager.random_word("easy") for _ in range(200)}
        self.assertEqual(picks, {"cat", "dog", "fish"})

    def test_seeded_rng_is_repeatable(self):
        self.write_all(easy="cat\ndog\nfish\nbird\nfrog\n")
        first = WordManager(self.dir, rng=random.Random(42))
        second = WordManager(self.dir, rng=random.Random(42))
        self.assertEqual(
            [first.random_word("easy") for _ in range(20)],
            [second.random_word("easy") for _ in range(20)],
        )

    def test_difficulty_is_case_insensitive(self):
        self.write_all()
        manager = WordManager(self.dir)
        self.assertEqual(manager.random_word("EASY"), "cat")

    def test_invalid_difficulty_rejected(self):
        self.write_all()
        manager = WordManager(self.dir)
        for value in ["expert", "", None]:
            with self.subTest(value=value):
                with self.assertRaises(InvalidDifficultyError):
                    manager.random_word(value)
                with self.assertRaises(InvalidDifficultyError):
                    manager.words(value)

    def test_words_returns_a_copy(self):
        self.write_all(easy="cat\ndog\n")
        manager = WordManager(self.dir)
        manager.words("easy").append("zebra")
        self.assertEqual(manager.words("easy"), ["cat", "dog"])


class TestBundledWordLists(unittest.TestCase):
    """The real words/ directory shipped with the project."""

    def test_bundled_lists_load(self):
        manager = WordManager()
        for difficulty in DIFFICULTIES:
            with self.subTest(difficulty=difficulty):
                words = manager.words(difficulty)
                self.assertGreater(len(words), 0)
                self.assertEqual(len(words), len(set(words)))

    def test_every_bundled_word_can_start_a_game(self):
        manager = WordManager()
        for difficulty in DIFFICULTIES:
            for word in manager.words(difficulty):
                HangmanGame(word)

    def test_random_game_from_each_difficulty(self):
        manager = WordManager()
        for difficulty in DIFFICULTIES:
            with self.subTest(difficulty=difficulty):
                game = HangmanGame(manager.random_word(difficulty))
                self.assertEqual(game.to_dict()["status"], "playing")


if __name__ == "__main__":
    unittest.main()
