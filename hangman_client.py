"""Small HTTP client for the Hangman REST API.

Uses only the standard library so terminal players and bots need nothing
beyond Python itself. Every method returns the server's JSON response as a
dict, or raises a ClientError subclass.
"""

import json
import urllib.error
import urllib.request
from urllib.parse import quote

DEFAULT_SERVER_URL = "http://127.0.0.1:5000"


class ClientError(Exception):
    """Base class for errors talking to the Hangman server."""


class ServerUnavailableError(ClientError):
    """The server could not be reached."""


class ApiError(ClientError):
    """The server answered with an error response."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class HangmanClient:
    def __init__(self, base_url=DEFAULT_SERVER_URL, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_game(self, difficulty):
        return self._request("POST", "/api/games", {"difficulty": difficulty})

    def get_game(self, game_id):
        return self._request("GET", f"/api/games/{quote(game_id, safe='')}")

    def guess(self, game_id, letter):
        return self._request(
            "POST", f"/api/games/{quote(game_id, safe='')}/guess", {"letter": letter}
        )

    def _request(self, method, path, body=None):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
                status = response.status
        except urllib.error.HTTPError as err:
            error = _decode_json(err.read())
            if not isinstance(error, dict):
                error = {}
            raise ApiError(
                err.code,
                error.get("code", "http_error"),
                error.get("error", f"server returned HTTP {err.code}"),
            ) from None
        except OSError as err:
            # URLError, connection refused/reset, and timeouts are all OSErrors.
            reason = getattr(err, "reason", err)
            raise ServerUnavailableError(
                f"could not reach the server at {self.base_url} ({reason})"
            ) from None

        result = _decode_json(payload)
        if not isinstance(result, dict):
            raise ApiError(status, "bad_response", "server returned an unexpected response")
        return result


def _decode_json(payload):
    try:
        return json.loads(payload)
    except ValueError:
        return None
