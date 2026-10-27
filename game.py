"""Core Hangman game engine.

This module has no dependency on Flask, the browser client, or the terminal
client. It holds the hidden word and enforces every game rule; callers only
ever see the client-safe state returned by ``HangmanGame.to_dict()``.
"""

STATUS_PLAYING = "playing"
STATUS_WON = "won"
STATUS_LOST = "lost"

DEFAULT_MAX_INCORRECT = 6


class GuessError(ValueError):
    """Base class for guesses the engine rejects without changing state."""


class InvalidGuessError(GuessError):
    """The guess is not exactly one alphabetic letter."""


class DuplicateGuessError(GuessError):
    """The letter has already been guessed in this game."""


class GameOverError(GuessError):
    """A guess was submitted after the game ended."""


class HangmanGame:
    """A single game of Hangman around one hidden word."""

    def __init__(self, word, max_incorrect=DEFAULT_MAX_INCORRECT):
        if not isinstance(word, str) or not word.isascii() or not word.isalpha():
            raise ValueError("word must be a non-empty string of letters a-z")
        if not isinstance(max_incorrect, int) or max_incorrect < 1:
            raise ValueError("max_incorrect must be a positive integer")

        self._word = word.lower()
        self.max_incorrect = max_incorrect
        # Letters are kept in the order they were guessed.
        self.guessed_letters = []
        self.incorrect_letters = []

    @property
    def remaining_guesses(self):
        return self.max_incorrect - len(self.incorrect_letters)

    @property
    def status(self):
        if all(ch in self.guessed_letters for ch in self._word):
            return STATUS_WON
        if self.remaining_guesses <= 0:
            return STATUS_LOST
        return STATUS_PLAYING

    @property
    def is_over(self):
        return self.status != STATUS_PLAYING

    @property
    def pattern(self):
        """Masked word, e.g. ``"_ e _ _ e"``."""
        return " ".join(ch if ch in self.guessed_letters else "_" for ch in self._word)

    @staticmethod
    def normalize_guess(letter):
        """Return ``letter`` lowercased, or raise InvalidGuessError."""
        if (
            not isinstance(letter, str)
            or len(letter) != 1
            or not letter.isascii()
            or not letter.isalpha()
        ):
            raise InvalidGuessError("guess must be a single letter a-z")
        return letter.lower()

    def guess(self, letter):
        """Apply one guess and return True if the letter is in the word.

        Rejected guesses raise a GuessError subclass and leave the game
        state unchanged.
        """
        if self.is_over:
            raise GameOverError("the game has already ended")
        letter = self.normalize_guess(letter)
        if letter in self.guessed_letters:
            raise DuplicateGuessError(f"'{letter}' has already been guessed")

        self.guessed_letters.append(letter)
        correct = letter in self._word
        if not correct:
            self.incorrect_letters.append(letter)
        return correct

    def to_dict(self):
        """Client-safe game state. The word is included only once the game ends."""
        state = {
            "pattern": self.pattern,
            "guessed_letters": list(self.guessed_letters),
            "incorrect_letters": list(self.incorrect_letters),
            "remaining_guesses": self.remaining_guesses,
            "status": self.status,
        }
        if self.is_over:
            state["word"] = self._word
        return state

    def __repr__(self):
        # Deliberately omits the hidden word so it cannot leak through logs.
        return f"<HangmanGame pattern={self.pattern!r} status={self.status!r}>"
