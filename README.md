# Hangman

A web-based Hangman game. A Flask server holds the hidden word and enforces
every rule. The browser client is plain HTML, CSS, and JavaScript, and talks
to the server only through a JSON REST API.

**Live app:** _add your Render URL here after deploying_

This project implements the server and browser client from
[`SPECIFICATION.md`](SPECIFICATION.md). Terminal clients, bots, evaluation,
and leaderboards are out of scope; see [`TODO.md`](TODO.md) for the plan
and progress.

## Project structure

```
hangman/
├── game.py              Game engine (HangmanGame), no Flask or UI code
├── word_manager.py      Loads word lists and picks random words by difficulty
├── server.py            Flask app: REST API and the browser page
├── static/
│   ├── index.html       Page layout
│   ├── style.css        Styles (light and dark, desktop and mobile)
│   └── app.js           Calls the API with fetch() and updates the page
├── words/
│   ├── easy.txt
│   ├── medium.txt
│   └── hard.txt
├── tests/               Automated tests (engine, words, API, browser)
├── requirements.txt     Python dependencies
├── render.yaml          Render deployment configuration
├── SPECIFICATION.md     Original project specification
└── TODO.md              Phased implementation plan
```

## Running locally

You need Python 3.9 or newer (developed with 3.12).

```bash
git clone <your-repo-url> hangman
cd hangman
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

Open <http://127.0.0.1:5000/> in a browser. Press Ctrl-C in the terminal to
stop the server. To use a different port, run `python server.py --port 8000`.

## How to play

1. Choose Easy, Medium, or Hard and press **New game**.
2. Guess letters by clicking the on-screen keys or typing on your keyboard.
3. Each wrong guess adds a part to the drawing. Six wrong guesses lose the game.
4. When the game ends, the word is revealed. Press **Play again** for a new game.

If you reload the page mid-game, the game resumes from the server.

## Running the tests

```bash
python -m unittest -v
```

| File | What it covers |
|---|---|
| `tests/test_game.py` | Game rules: guesses, duplicates, invalid input, wins, losses, answer disclosure |
| `tests/test_word_manager.py` | Loading and validating word lists, random selection, invalid difficulty |
| `tests/test_server.py` | Every API endpoint, status codes, error responses, no word leaks during play |
| `tests/test_browser.py` | Plays real games in headless Chrome and checks the page after each guess |

The browser test needs Node.js 22 or newer and Google Chrome or Chromium. It
is skipped automatically if either is missing. Set `CHROME_BIN` if Chrome is
installed somewhere unusual, and `HANGMAN_SCREENSHOTS=/some/folder` to save
screenshots of what it checked.

## REST API

All requests and responses use JSON. Send `Content-Type: application/json`
with request bodies.

### Create a game

`POST /api/games`

```json
{"difficulty": "medium"}
```

Response `201 Created`:

```json
{
  "game_id": "3f9c2a7b1d4e6f80",
  "difficulty": "medium",
  "pattern": "_ _ _ _ _ _",
  "guessed_letters": [],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing"
}
```

### Guess a letter

`POST /api/games/{game_id}/guess`

```json
{"letter": "e"}
```

Response `200 OK`:

```json
{
  "game_id": "3f9c2a7b1d4e6f80",
  "difficulty": "medium",
  "pattern": "_ e _ _ e _",
  "guessed_letters": ["e"],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing",
  "correct": true
}
```

### Get the current state

`GET /api/games/{game_id}` returns the same fields as above, without `correct`.

### When the game ends

`status` becomes `"won"` or `"lost"`, and the response includes the answer:

```json
{"status": "lost", "remaining_guesses": 0, "word": "rocket", "...": "..."}
```

`word` is never included while `status` is `"playing"`.

### Errors

Errors return an HTTP error status and a JSON body like
`{"error": "'e' has already been guessed", "code": "duplicate_guess"}`.

| Status | `code` | When |
|---|---|---|
| 400 | `malformed_request` | Body is not a JSON object |
| 400 | `invalid_difficulty` | Difficulty missing or not easy/medium/hard |
| 400 | `invalid_guess` | Letter missing or not a single letter a-z |
| 404 | `game_not_found` | Unknown game ID |
| 409 | `duplicate_guess` | Letter already guessed in this game |
| 409 | `game_over` | Guess sent after the game ended |
| 404 / 405 | `not_found` / `method_not_allowed` | Unknown URL or wrong HTTP method |

Rejected guesses do not change the game.

### Trying it with curl

```bash
curl -X POST http://127.0.0.1:5000/api/games \
     -H 'Content-Type: application/json' -d '{"difficulty": "easy"}'

curl -X POST http://127.0.0.1:5000/api/games/GAME_ID/guess \
     -H 'Content-Type: application/json' -d '{"letter": "e"}'

curl http://127.0.0.1:5000/api/games/GAME_ID
```

## What happens when you guess a letter

1. `app.js` sends `POST /api/games/{game_id}/guess` with `{"letter": "e"}`
   using `fetch()`.
2. Flask (`server.py`) looks up the game and calls `HangmanGame.guess()`
   in `game.py`, which decides whether the letter is in the word.
3. The server replies with the updated game state as JSON.
4. `app.js` redraws the pattern, letter lists, keyboard, and drawing from
   that response.

You can watch this in Chrome Developer Tools: open the **Network** tab,
guess a letter, and select the `guess` request to see its payload and
JSON response.

## Deploying to Render

The repository includes [`render.yaml`](render.yaml). On Render:

1. Push the project to GitHub.
2. In the Render dashboard choose **New → Blueprint** and select the
   repository. Render reads `render.yaml` and creates the web service.

Or create it by hand with **New → Web Service** and these settings:

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn --bind 0.0.0.0:$PORT --workers 1 server:app` |

Notes:

- **Use one worker.** Games are stored in the server process's memory, so
  several workers would each have their own separate set of games.
- **Games are not saved.** A restart or redeploy clears all games in
  progress. On Render's free plan the service also sleeps after a period
  without traffic. The first request afterwards takes a little longer to
  wake it, and any earlier games are gone.

## Deviations from the specification

`SPECIFICATION.md` is kept unchanged as the original reference. Where this
implementation goes beyond or fills in details the specification leaves open:

- **Extra response fields.** Every game response includes `game_id`,
  `difficulty`, `guessed_letters`, and `incorrect_letters`, and guess
  responses include `correct`. The specification's examples show fewer
  fields; all of the fields it lists are present.
- **Revealed word field.** The answer is returned as `word`, only once the
  game is over.
- **Duplicate guesses are rejected** with HTTP 409 rather than ignored.
- **Status codes and error format** (table above) are defined here; the
  specification does not list them.
- **`difficulty` is required** when creating a game. It is
  case-insensitive (`"Hard"` works) and returned in lowercase.
- **Guessed letters** are listed in the order they were guessed.
- **Game IDs** are random 16-character hex strings, so they cannot be guessed.
- **The browser remembers the current game ID** for the tab (in
  `sessionStorage`) so a page reload resumes the game. The hidden word is
  never stored in the browser.
- **Word module name.** Word loading lives in `word_manager.py`, which the
  specification's suggested structure does not list.
