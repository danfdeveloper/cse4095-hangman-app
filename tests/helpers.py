"""Shared test fixtures."""

import socket
import tempfile
import threading
import unittest
from pathlib import Path

from werkzeug.serving import make_server

from server import create_app
from word_manager import WordManager


def make_word_manager(directory, easy="cat", medium="rabbit", hard="rhythm"):
    """A WordManager with one word per difficulty so tests know the answer."""
    directory = Path(directory)
    for name, word in [("easy", easy), ("medium", medium), ("hard", hard)]:
        (directory / f"{name}.txt").write_text(word + "\n", encoding="utf-8")
    return WordManager(directory)


def unused_port_url():
    """A URL on localhost where nothing is listening."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class LiveServerTestCase(unittest.TestCase):
    """Runs the real Flask app over HTTP in a background thread."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.app = create_app(make_word_manager(cls._tmp.name))
        cls._server = make_server("127.0.0.1", 0, cls.app, threaded=True)
        cls.server_url = f"http://127.0.0.1:{cls._server.server_port}"
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._thread.join()
        cls._tmp.cleanup()
