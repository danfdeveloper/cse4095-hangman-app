"""Play Hangman in the terminal against a running Hangman server.

    python3 terminal_client.py [--server URL]

The client only handles input and display. The server decides whether each
guess is correct and when the game is won or lost.
"""

import argparse
import os

from hangman_client import (
    DEFAULT_SERVER_URL,
    ApiError,
    ClientError,
    HangmanClient,
    ServerUnavailableError,
)

DIFFICULTY_CHOICES = {
    "1": "easy",
    "e": "easy",
    "easy": "easy",
    "2": "medium",
    "m": "medium",
    "medium": "medium",
    "3": "hard",
    "h": "hard",
    "hard": "hard",
}

QUIT_WORDS = {"q", "quit", "exit"}

# One drawing per number of incorrect guesses, from 0 to 6.
GALLOWS = [
    ["  +---+", "  |   |", "      |", "      |", "      |", "=======",],
    ["  +---+", "  |   |", "  O   |", "      |", "      |", "=======",],
    ["  +---+", "  |   |", "  O   |", "  |   |", "      |", "=======",],
    ["  +---+", "  |   |", "  O   |", " /|   |", "      |", "=======",],
    ["  +---+", "  |   |", "  O   |", " /|\\  |", "      |", "=======",],
    ["  +---+", "  |   |", "  O   |", " /|\\  |", " /    |", "=======",],
    ["  +---+", "  |   |", "  O   |", " /|\\  |", " / \\  |", "=======",],
]


class QuitRequested(Exception):
    """The player asked to leave (typed quit, Ctrl-C, or end of input)."""


def gallows_stage(incorrect_count, max_incorrect):
    """Map incorrect guesses onto the 0-6 drawings, whatever the server's limit."""
    if max_incorrect <= 0:
        return len(GALLOWS) - 1
    stage = round(incorrect_count * (len(GALLOWS) - 1) / max_incorrect)
    return max(0, min(stage, len(GALLOWS) - 1))


def guesses_phrase(count):
    return f"{count} incorrect guess{'' if count == 1 else 'es'}"


def is_single_letter(text):
    return len(text) == 1 and text.isascii() and text.isalpha()


class TerminalGame:
    def __init__(self, client, input_fn=input, output_fn=print):
        self.client = client
        self._input = input_fn
        self._output = output_fn

    def say(self, text=""):
        self._output(text)

    def ask(self, prompt):
        try:
            return self._input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            self.say()
            raise QuitRequested

    def run(self):
        self.say("Welcome to Hangman!")
        try:
            while True:
                self.play_game(self.choose_difficulty())
                if not self.ask_yes_no("Play again? [y/n] "):
                    break
        except QuitRequested:
            pass
        self.say("Goodbye!")

    def choose_difficulty(self):
        while True:
            choice = self.ask(
                "Choose a difficulty: 1) Easy  2) Medium  3) Hard  (q to quit): "
            ).lower()
            if choice in QUIT_WORDS:
                raise QuitRequested
            if choice in DIFFICULTY_CHOICES:
                return DIFFICULTY_CHOICES[choice]
            self.say("Please enter 1, 2, or 3.")

    def ask_yes_no(self, prompt):
        while True:
            answer = self.ask(prompt).lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no") or answer in QUIT_WORDS:
                return False
            self.say("Please answer y or n.")

    def play_game(self, difficulty):
        try:
            state = self.client.create_game(difficulty)
        except ClientError as err:
            self.say(f"Could not start a game: {err}")
            return

        game_id = state["game_id"]
        # A fresh game has no misses, so its remaining guesses are the limit.
        max_incorrect = state["remaining_guesses"]
        self.say(f"\nNew {difficulty} game started.")

        while state["status"] == "playing":
            self.show(state, max_incorrect)
            letter = self.prompt_letter(state)
            try:
                state = self.client.guess(game_id, letter)
            except ServerUnavailableError as err:
                self.say(f"{err}. Try again, or type quit to leave.")
            except ApiError as err:
                self.say(f"Server rejected the guess: {err.message}")
                state = self.refresh(game_id, state)
                if state is None:
                    return

        self.show(state, max_incorrect)
        self.show_result(state)

    def refresh(self, game_id, state):
        """Re-read the game from the server after an error; None if it is gone."""
        try:
            return self.client.get_game(game_id)
        except ApiError as err:
            if err.code == "game_not_found":
                self.say("The server no longer has this game (was it restarted?).")
                return None
            return state
        except ServerUnavailableError:
            return state

    def prompt_letter(self, state):
        while True:
            text = self.ask("Guess a letter (or quit): ").lower()
            if text in ("quit", "exit"):
                raise QuitRequested
            if not is_single_letter(text):
                self.say("Please enter a single letter a-z.")
            elif text in state["guessed_letters"]:
                self.say(f"You already guessed '{text}'.")
            else:
                return text

    def show(self, state, max_incorrect):
        incorrect = state["incorrect_letters"]
        self.say()
        for line in GALLOWS[gallows_stage(len(incorrect), max_incorrect)]:
            self.say(line)
        self.say()
        self.say(f"Word:       {state['pattern']}")
        self.say(f"Guessed:    {', '.join(state['guessed_letters']) or '(none)'}")
        self.say(f"Incorrect:  {', '.join(incorrect) or '(none)'}")
        self.say(f"Remaining:  {guesses_phrase(state['remaining_guesses'])} left")

    def show_result(self, state):
        word = state.get("word", "?")
        self.say()
        if state["status"] == "won":
            spare = guesses_phrase(state["remaining_guesses"])
            self.say(f"You won! The word was '{word}' ({spare} to spare).")
        else:
            self.say(f"You lost. The word was '{word}'.")
        self.say()


def main():
    parser = argparse.ArgumentParser(description="Play Hangman in the terminal.")
    parser.add_argument(
        "--server",
        default=os.environ.get("HANGMAN_SERVER", DEFAULT_SERVER_URL),
        help="server URL (default: $HANGMAN_SERVER or %(default)s)",
    )
    args = parser.parse_args()
    try:
        TerminalGame(HangmanClient(args.server)).run()
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
