"""Hangman REST server.

Run locally with:

    python3 server.py [--host HOST] [--port PORT]

or in production with:

    gunicorn --bind 0.0.0.0:$PORT --workers 1 server:app

All game logic lives in ``game.HangmanGame``; this module only stores games,
validates HTTP input, and translates engine results and errors into JSON.
"""

import argparse
import secrets
import threading

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from game import DuplicateGuessError, GameOverError, HangmanGame, InvalidGuessError
from word_manager import InvalidDifficultyError, WordManager, normalize_difficulty


class ApiError(Exception):
    """An error returned to the client as ``{"error": ..., "code": ...}``."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class GameStore:
    """Thread-safe in-memory storage for active games, keyed by game id."""

    def __init__(self):
        self._games = {}
        self._lock = threading.Lock()

    def add(self, game, difficulty):
        with self._lock:
            game_id = secrets.token_hex(8)
            while game_id in self._games:
                game_id = secrets.token_hex(8)
            self._games[game_id] = {"game": game, "difficulty": difficulty}
            return game_id

    def get(self, game_id):
        with self._lock:
            return self._games.get(game_id)

    @property
    def lock(self):
        return self._lock

    def __len__(self):
        with self._lock:
            return len(self._games)


def _json_body():
    """Return the request body as a dict, or raise ApiError for malformed input."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "malformed_request", "request body must be a JSON object")
    return body


def _game_response(game_id, entry, **extra):
    state = {"game_id": game_id, "difficulty": entry["difficulty"]}
    state.update(entry["game"].to_dict())
    state.update(extra)
    return state


def create_app(word_manager=None):
    app = Flask(__name__)
    app.json.sort_keys = False
    words = word_manager if word_manager is not None else WordManager()
    store = GameStore()
    app.config["GAME_STORE"] = store

    def lookup(game_id):
        entry = store.get(game_id)
        if entry is None:
            raise ApiError(404, "game_not_found", f"no game with id {game_id!r}")
        return entry

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(error=err.message, code=err.code), err.status

    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        code = err.name.lower().replace(" ", "_")
        return jsonify(error=err.description, code=code), err.code

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.post("/api/games")
    def create_game():
        body = _json_body()
        if "difficulty" not in body:
            raise ApiError(400, "invalid_difficulty", "difficulty is required")
        try:
            difficulty = normalize_difficulty(body["difficulty"])
        except InvalidDifficultyError as err:
            raise ApiError(400, "invalid_difficulty", str(err))

        game = HangmanGame(words.random_word(difficulty))
        game_id = store.add(game, difficulty)
        return jsonify(_game_response(game_id, store.get(game_id))), 201

    @app.get("/api/games/<game_id>")
    def get_game(game_id):
        entry = lookup(game_id)
        with store.lock:
            return jsonify(_game_response(game_id, entry))

    @app.post("/api/games/<game_id>/guess")
    def guess(game_id):
        entry = lookup(game_id)
        body = _json_body()
        if "letter" not in body:
            raise ApiError(400, "invalid_guess", "letter is required")

        # Lock so two simultaneous guesses on one game cannot interleave.
        with store.lock:
            try:
                correct = entry["game"].guess(body["letter"])
            except InvalidGuessError as err:
                raise ApiError(400, "invalid_guess", str(err))
            except DuplicateGuessError as err:
                raise ApiError(409, "duplicate_guess", str(err))
            except GameOverError as err:
                raise ApiError(409, "game_over", str(err))
            return jsonify(_game_response(game_id, entry, correct=correct))

    return app


# Module-level app for production servers, e.g. ``gunicorn server:app``.
# Games live in this process's memory, so run a single worker process.
app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Run the Hangman REST server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
