// Browser client for the Hangman REST API.
//
// The page only displays what the server sends back. It never receives the
// hidden word until the server reports that the game has ended.
"use strict";

(() => {
  const API = "/api/games";
  const STORAGE_KEY = "hangman.gameId";
  const LETTERS = "abcdefghijklmnopqrstuvwxyz".split("");

  const els = {
    form: document.getElementById("new-game-form"),
    difficulty: document.getElementById("difficulty"),
    newGame: document.getElementById("new-game"),
    parts: Array.from(document.querySelectorAll("#drawing .part")),
    pattern: document.getElementById("pattern"),
    message: document.getElementById("message"),
    remaining: document.getElementById("remaining"),
    guessed: document.getElementById("guessed"),
    incorrect: document.getElementById("incorrect"),
    keyboard: document.getElementById("keyboard"),
  };

  let state = null;
  let busy = false;
  const keys = new Map();

  // --- Server communication -------------------------------------------------

  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers: { "Content-Type": "application/json", Accept: "application/json" },
      });
    } catch {
      throw new Error("Could not reach the server.");
    }
    let body = null;
    try {
      body = await response.json();
    } catch {
      // Leave body as null; handled below.
    }
    if (!response.ok) {
      const err = new Error((body && body.error) || `Server error (HTTP ${response.status}).`);
      err.code = body && body.code;
      throw err;
    }
    if (!body || typeof body !== "object") {
      throw new Error("Unexpected response from the server.");
    }
    return body;
  }

  async function startGame() {
    if (busy) return;
    setBusy(true);
    try {
      const body = JSON.stringify({ difficulty: els.difficulty.value });
      setState(await api(API, { method: "POST", body }));
      showMessage("Guess a letter.");
    } catch (err) {
      showMessage(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function guess(letter) {
    if (busy || !state || state.status !== "playing") return;
    if (state.guessed_letters.includes(letter)) return;
    setBusy(true);
    try {
      const path = `${API}/${encodeURIComponent(state.game_id)}/guess`;
      const next = await api(path, { method: "POST", body: JSON.stringify({ letter }) });
      setState({ ...next, game_id: next.game_id || state.game_id });
      if (state.status === "playing") {
        showMessage(next.correct === false ? `No '${letter.toUpperCase()}'.` : "");
      }
    } catch (err) {
      showMessage(err.message, "error");
      await reload();
    } finally {
      setBusy(false);
    }
  }

  // Re-read the current game from the server, e.g. after an error or page reload.
  async function reload(gameId = state && state.game_id) {
    if (!gameId) return;
    try {
      setState(await api(`${API}/${encodeURIComponent(gameId)}`));
    } catch (err) {
      if (err.code === "game_not_found") {
        clearState();
        showMessage("That game is no longer on the server. Start a new game.", "error");
      }
    }
  }

  // --- State and rendering --------------------------------------------------

  function setState(next) {
    state = next;
    remember(state.game_id);
    render();
  }

  function clearState() {
    state = null;
    remember(null);
    render();
  }

  function remember(gameId) {
    try {
      if (gameId) sessionStorage.setItem(STORAGE_KEY, gameId);
      else sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage may be unavailable (private mode); resuming is optional.
    }
  }

  function storedGameId() {
    try {
      return sessionStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function setBusy(value) {
    busy = value;
    els.newGame.disabled = value;
    renderKeys();
  }

  function showMessage(text, kind = "") {
    els.message.textContent = text;
    els.message.className = `message ${kind}`.trim();
  }

  function render() {
    renderPattern();
    renderDrawing();
    renderKeys();

    if (!state) {
      els.remaining.textContent = "–";
      els.guessed.textContent = "–";
      els.incorrect.textContent = "–";
      els.newGame.classList.remove("attention");
      return;
    }

    els.remaining.textContent = String(state.remaining_guesses);
    els.guessed.textContent = letterList(state.guessed_letters);
    els.incorrect.textContent = letterList(state.incorrect_letters);

    const over = state.status !== "playing";
    els.newGame.textContent = over ? "Play again" : "New game";
    els.newGame.classList.toggle("attention", over);
    if (state.status === "won") {
      showMessage(`You won! The word was "${state.word}".`, "won");
    } else if (state.status === "lost") {
      showMessage(`You lost. The word was "${state.word}".`, "lost");
    }
  }

  function letterList(letters) {
    return letters.length ? letters.join(", ").toUpperCase() : "None";
  }

  function renderPattern() {
    els.pattern.replaceChildren();
    els.pattern.className = "pattern";
    if (!state) {
      els.pattern.setAttribute("aria-label", "No game in progress");
      return;
    }
    els.pattern.classList.add(state.status);

    // On a loss, fill in the missed letters from the revealed word.
    const shown = state.pattern.split(" ");
    const word = state.status === "lost" && state.word ? state.word : null;
    const spoken = [];
    shown.forEach((ch, i) => {
      const slot = document.createElement("span");
      slot.className = "slot";
      if (ch !== "_") {
        slot.textContent = ch;
        spoken.push(ch);
      } else if (word) {
        slot.textContent = word[i];
        slot.classList.add("missed");
        spoken.push(word[i]);
      } else {
        spoken.push("blank");
      }
      els.pattern.append(slot);
    });
    els.pattern.setAttribute("aria-label", `Word: ${spoken.join(" ")}`);
  }

  function renderDrawing() {
    let shown = 0;
    if (state) {
      const misses = state.incorrect_letters.length;
      const max = misses + state.remaining_guesses;
      shown = max > 0 ? Math.round((misses * els.parts.length) / max) : els.parts.length;
    }
    els.parts.forEach((part, i) => part.classList.toggle("shown", i < shown));
  }

  function renderKeys() {
    const playing = state && state.status === "playing";
    for (const [letter, key] of keys) {
      const guessed = !!state && state.guessed_letters.includes(letter);
      const wrong = guessed && state.incorrect_letters.includes(letter);
      key.disabled = busy || !playing || guessed;
      key.classList.toggle("correct", guessed && !wrong);
      key.classList.toggle("incorrect", wrong);
    }
  }

  // --- Setup ----------------------------------------------------------------

  function buildKeyboard() {
    for (const letter of LETTERS) {
      const key = document.createElement("button");
      key.type = "button";
      key.className = "key";
      key.textContent = letter;
      key.setAttribute("aria-label", `Guess ${letter.toUpperCase()}`);
      key.addEventListener("click", () => guess(letter));
      els.keyboard.append(key);
      keys.set(letter, key);
    }
  }

  function onKeyDown(event) {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target instanceof HTMLSelectElement) return;
    const letter = event.key.toLowerCase();
    if (letter.length === 1 && letter >= "a" && letter <= "z") {
      event.preventDefault();
      guess(letter);
    }
  }

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    startGame();
  });
  document.addEventListener("keydown", onKeyDown);

  buildKeyboard();
  render();
  showMessage("Choose a difficulty and start a new game.");
  const savedId = storedGameId();
  if (savedId) {
    reload(savedId).then(() => {
      if (state && state.status === "playing") showMessage("Welcome back. Guess a letter.");
    });
  }
})();
