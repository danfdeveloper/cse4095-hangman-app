"""Shared test fixtures."""

import tempfile
import threading
import unittest
from pathlib import Path

from werkzeug.serving import WSGIRequestHandler, make_server

from server import create_app
from word_manager import WordManager


def make_word_manager(directory, easy="cat", medium="rabbit", hard="rhythm"):
    """A WordManager with one word per difficulty so tests know the answer."""
    directory = Path(directory)
    for name, word in [("easy", easy), ("medium", medium), ("hard", hard)]:
        (directory / f"{name}.txt").write_text(word + "\n", encoding="utf-8")
    return WordManager(directory)


class QuietRequestHandler(WSGIRequestHandler):
    """Keeps per-request access logs out of test output."""

    def log_request(self, *args, **kwargs):
        pass


class LiveServerTestCase(unittest.TestCase):
    """Runs the real Flask app over HTTP in a background thread."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.app = create_app(make_word_manager(cls._tmp.name))
        cls._server = make_server(
            "127.0.0.1", 0, cls.app, threaded=True, request_handler=QuietRequestHandler
        )
        cls.server_url = f"http://127.0.0.1:{cls._server.server_port}"
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._thread.join()
        cls._tmp.cleanup()
