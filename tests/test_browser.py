"""Runs tests/browser_check.mjs in headless Chrome against a live test server.

Skipped automatically when Node.js 22+ or Chrome/Chromium is not installed.
Set HANGMAN_SCREENSHOTS=/some/dir to save screenshots of the checked states.
"""

import os
import re
import shutil
import socket
import subprocess
import unittest
from pathlib import Path

from tests.helpers import LiveServerTestCase

SCRIPT = Path(__file__).resolve().parent / "browser_check.mjs"
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def find_chrome():
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]
    return next((path for name in CHROME_NAMES if (path := shutil.which(name))), None)


def node_major_version(node):
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    except OSError:
        return 0
    match = re.match(r"v(\d+)", version)
    return int(match.group(1)) if match else 0


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


NODE = shutil.which("node")
CHROME = find_chrome()


@unittest.skipUnless(NODE and node_major_version(NODE) >= 22, "needs Node.js 22 or newer")
@unittest.skipUnless(CHROME, "needs Chrome or Chromium (or set CHROME_BIN)")
class TestBrowserClient(LiveServerTestCase):
    def test_browser_client(self):
        command = [NODE, str(SCRIPT), self.server_url + "/", CHROME, str(free_port())]
        if os.environ.get("HANGMAN_SCREENSHOTS"):
            command.append(os.environ["HANGMAN_SCREENSHOTS"])
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        report = completed.stdout + completed.stderr
        self.assertIn("PASS", report)
        self.assertEqual(completed.returncode, 0, "\n" + report)


if __name__ == "__main__":
    unittest.main()
