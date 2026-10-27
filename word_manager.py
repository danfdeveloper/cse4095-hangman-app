"""Word list loading and random word selection by difficulty.

Word files live in a directory with one file per difficulty
(``easy.txt``, ``medium.txt``, ``hard.txt``), one word per line.
Blank lines are skipped. Words are lowercased and duplicates are dropped.
Any other entry that is not plain letters a-z is an error.
"""

import random
from pathlib import Path

DIFFICULTIES = ("easy", "medium", "hard")

DEFAULT_WORDS_DIR = Path(__file__).resolve().parent / "words"


class InvalidDifficultyError(ValueError):
    """The requested difficulty is not one of DIFFICULTIES."""


class WordListError(ValueError):
    """A word file is empty or contains an invalid entry."""


def load_word_file(path):
    """Return the unique, lowercased words in ``path`` in file order."""
    path = Path(path)
    words = []
    seen = set()
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            word = line.strip().lower()
            if not word:
                continue
            if not (word.isascii() and word.isalpha()):
                raise WordListError(
                    f"{path}:{line_number}: {line.strip()!r} is not a word of letters a-z"
                )
            if word not in seen:
                seen.add(word)
                words.append(word)
    if not words:
        raise WordListError(f"{path}: no words found")
    return words


def normalize_difficulty(difficulty):
    """Return ``difficulty`` lowercased, or raise InvalidDifficultyError."""
    if isinstance(difficulty, str):
        normalized = difficulty.strip().lower()
        if normalized in DIFFICULTIES:
            return normalized
    raise InvalidDifficultyError(
        f"difficulty must be one of {', '.join(DIFFICULTIES)}; got {difficulty!r}"
    )


class WordManager:
    """Holds one word list per difficulty and hands out random words."""

    def __init__(self, words_dir=DEFAULT_WORDS_DIR, rng=None):
        self.words_dir = Path(words_dir)
        self._rng = rng if rng is not None else random.Random()
        self._words = {
            difficulty: load_word_file(self.words_dir / f"{difficulty}.txt")
            for difficulty in DIFFICULTIES
        }

    def words(self, difficulty):
        """Return a copy of the word list for ``difficulty``."""
        return list(self._words[normalize_difficulty(difficulty)])

    def random_word(self, difficulty):
        """Return a random word from the ``difficulty`` list."""
        return self._rng.choice(self._words[normalize_difficulty(difficulty)])
