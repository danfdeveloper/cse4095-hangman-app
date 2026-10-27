# TODO — Hangman Web Application

This file is the implementation roadmap for the Hangman web application.

The original system requirements are defined in `SPECIFICATION.md`. This
assignment uses a reduced scope: the Hangman server and the browser-based
client only. Terminal clients, automated bots, bot evaluation, scoring, and
leaderboards are out of scope (see the end of this file).

## Implementation Rules

- Implement one phase at a time.
- Complete and test all items in the current phase before moving to the next phase.
- Do not change the architecture or REST API defined in `SPECIFICATION.md` unless necessary.
- If a deviation is necessary, document it in the README. `SPECIFICATION.md` is kept unchanged as the original reference.
- Keep the game engine independent from Flask and the browser UI.
- The server must remain authoritative.
- Never expose the hidden word before a game ends.
- Add tests as each phase is implemented rather than postponing testing until the end.
- Commit to GitHub after each completed phase.

---

## Phase 1 — Project Skeleton and Core Game Engine

### Tasks

- [x] Create the project directory structure.
- [x] Add `words/easy.txt`.
- [x] Add `words/medium.txt`.
- [x] Add `words/hard.txt`.
- [x] Create `game.py`.
- [x] Implement a `HangmanGame` class.
- [x] Store the hidden word internally.
- [x] Track guessed letters.
- [x] Track incorrect letters.
- [x] Track the maximum number of incorrect guesses.
- [x] Implement single-letter guess validation.
- [x] Detect duplicate guesses.
- [x] Implement masked-word generation.
- [x] Implement win detection.
- [x] Implement loss detection.
- [x] Prevent further guesses after a game ends.
- [x] Implement game status values such as `playing`, `won`, and `lost`.
- [x] Implement a method that returns a client-safe game-state dictionary.
- [x] Reveal the answer only after the game ends.
- [x] Add unit tests for the game engine.

### Completion Criteria

The game engine can be tested entirely without running a web server.

All core rules are covered by unit tests.

---

## Phase 2 — Word Management

### Tasks

- [x] Create a word-loading module or helper functions.
- [x] Load Easy, Medium, and Hard word lists.
- [x] Validate that loaded words contain only alphabetic characters.
- [x] Remove accidental duplicates when loading.
- [x] Support random word selection by difficulty.
- [x] Return an error for an invalid difficulty.
- [x] Add tests for word loading and word selection.

### Completion Criteria

The program can request a random word from each difficulty level reliably.

Invalid difficulty values are rejected cleanly.

---

## Phase 3 — Flask Server and REST API

### Tasks

- [x] Create `server.py`.
- [x] Configure Flask.
- [x] Add in-memory storage for active games.
- [x] Generate unique game IDs.
- [x] Implement `POST /api/games`.
- [x] Implement `GET /api/games/{game_id}`.
- [x] Implement `POST /api/games/{game_id}/guess`.
- [x] Validate difficulty input.
- [x] Validate guess input.
- [x] Return JSON responses consistently.
- [x] Return appropriate HTTP status codes.
- [x] Handle unknown game IDs.
- [x] Handle malformed requests.
- [x] Ensure the hidden word is never leaked during an active game.
- [x] Add API tests.

### Completion Criteria

A complete Hangman game can be played using only `curl` or another HTTP client.

---

## Phase 4 — Browser Client

### Tasks

- [x] Create `static/index.html`.
- [x] Create `static/style.css`.
- [x] Create `static/app.js`.
- [x] Serve the page from the Flask server at `/`.
- [x] Add a difficulty selector.
- [x] Add a New Game button.
- [x] Display the masked word.
- [x] Display guessed letters.
- [x] Display incorrect letters.
- [x] Display remaining guesses.
- [x] Add an on-screen alphabet keyboard.
- [x] Support guessing with the physical keyboard.
- [x] Disable already-guessed letters.
- [x] Use `fetch()` to communicate with the REST API.
- [x] Draw the Hangman state visually.
- [x] Update the drawing after incorrect guesses.
- [x] Display win and loss messages.
- [x] Provide a restart/new-game flow without reloading the page.
- [x] Make the interface usable on common desktop and mobile browser sizes.

### Completion Criteria

A human player can play a complete game from a browser.

No hidden word is stored in browser-side JavaScript during active gameplay.

---

## Phase 5 — Testing and Debugging

### Tasks

- [x] Complete unit tests for `HangmanGame`.
- [x] Complete tests for word loading.
- [x] Complete REST API tests.
- [x] Test starting games at all three difficulty levels.
- [x] Test correct and incorrect guesses.
- [x] Test repeated (duplicate) guesses.
- [x] Test invalid letters.
- [x] Test invalid difficulty.
- [x] Test unknown game IDs and malformed requests.
- [x] Test win paths.
- [x] Test loss paths.
- [x] Test starting a new game after completing one.
- [x] Test answer disclosure rules (no hidden word during active play).
- [x] Add an automated browser test that checks the page updates after each guess.
- [ ] Run the Flask app locally and play several games in a browser.
- [ ] Inspect at least one REST API request and JSON response in Chrome Developer Tools.

### Completion Criteria

The major user flows and failure cases are covered by automated tests, and the
application has been played by hand locally.

---

## Phase 6 — Documentation and Deployment Configuration

### Tasks

- [x] Create `README.md`.
- [x] Document installation and how to run the app locally.
- [x] Document how to run the tests.
- [x] Document the REST API with example requests and responses.
- [x] Document deviations from `SPECIFICATION.md`.
- [x] Add dependency information in `requirements.txt`.
- [x] Add Gunicorn and expose `server:app` for production.
- [x] Add Render deployment configuration (`render.yaml`).
- [x] Verify that a fresh installation works from `requirements.txt`.

### Completion Criteria

A new user can clone the project, install dependencies, start the server, and
play in a browser using only the README.

---

## Phase 7 — Cloud Deployment

### Tasks

- [ ] Push the project to a GitHub repository.
- [ ] Create a Render web service from the repository.
- [ ] Confirm the build and start commands succeed in the Render logs.
- [ ] Open the public HTTPS URL and confirm the web interface loads.
- [ ] Confirm the REST API endpoints respond at the public URL.
- [ ] Play a complete game through the deployed browser interface.
- [ ] Add the deployed URL to the README.

### Completion Criteria

The application is reachable at a public HTTPS URL and a complete game can be
played without installing Python or running a local server.

---

## Phase 8 — Submission

### Tasks

- [ ] Confirm the repository contains the code, word lists, `SPECIFICATION.md`, this TODO, dependency and deployment configuration, tests, and README.
- [ ] Write the 1–2 page development report (PDF).
- [ ] Record the 2–3 minute demonstration video.
- [ ] Submit the repository URL, deployed URL, report, and video.

---

# Out of Scope for This Assignment

These parts of `SPECIFICATION.md` are not implemented:

- Human terminal client (`terminal_client.py`).
- Reference automated bots (`random_bot.py`, `frequency_bot.py`).
- Dictionary-based bot (`dictionary_bot.py`).
- Evaluation mode.
- Official scoring system.
- Leaderboard.
- Evaluation integrity and anti-cheating safeguards.
- Game logging and replay.
- Optional future phases: persistent storage, accounts and authentication,
  tournament mode, advanced bot analysis, and multiplayer.
