// End-to-end browser check for the Hangman page.
//
// Drives headless Chrome over the DevTools protocol with real clicks and key
// presses against a running server whose words are easy=cat, medium=rabbit,
// hard=rhythm (see tests/test_browser.py, which starts that server).
//
//   node tests/browser_check.mjs APP_URL CHROME_BINARY DEBUG_PORT [SCREENSHOT_DIR]
//
// Prints one PASS/FAIL line per check and exits non-zero if any check fails.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [, , APP_URL, CHROME, DEBUG_PORT, SHOT_DIR] = process.argv;
const profile = mkdtempSync(join(tmpdir(), "hangman-chrome-"));
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${DEBUG_PORT}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") =>
  results.push(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);

let ws;
try {
  await main();
} catch (err) {
  results.push(`FAIL browser check crashed — ${err.stack || err}`);
} finally {
  if (ws) ws.close();
  chrome.kill();
  await sleep(200);
  rmSync(profile, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);

async function main() {
  // --- DevTools connection ------------------------------------------------
  let targets;
  for (let i = 0; i < 75 && !targets; i++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)).json();
    } catch {
      await sleep(200);
    }
  }
  if (!targets) throw new Error("Chrome did not start");
  const page = targets.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });

  let nextId = 1;
  const pending = new Map();
  const pageErrors = [];
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
    if (msg.method === "Runtime.exceptionThrown") {
      pageErrors.push(msg.params.exceptionDetails.text);
    }
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      pageErrors.push(JSON.stringify(msg.params.args));
    }
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, (msg) =>
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result));
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(`${r.exceptionDetails.text}: ${expression}`);
    return r.result.value;
  };

  // --- Page helpers -------------------------------------------------------
  const load = async () => {
    await send("Page.navigate", { url: APP_URL });
    await waitFor(`document.querySelectorAll(".key").length === 26`);
    await sleep(300);
  };
  const waitFor = async (expression, timeoutMs = 5000) => {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      if (await evaluate(expression)) return true;
      await sleep(25);
    }
    return false;
  };
  const viewport = (width, height, mobile = false) =>
    send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  const screenshot = async (name) => {
    if (!SHOT_DIR) return;
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(join(SHOT_DIR, name), Buffer.from(data, "base64"));
  };
  const snapshot = () => evaluate(`({
    slots: [...document.querySelectorAll("#pattern .slot")].map((s) => s.textContent),
    message: document.getElementById("message").textContent,
    remaining: document.getElementById("remaining").textContent,
    guessed: document.getElementById("guessed").textContent,
    incorrect: document.getElementById("incorrect").textContent,
    parts: document.querySelectorAll("#drawing .part.shown").length,
    enabledKeys: [...document.querySelectorAll(".key")].filter((k) => !k.disabled)
      .map((k) => k.textContent).join(""),
    button: document.getElementById("new-game").textContent,
    html: document.documentElement.outerHTML,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  })`);
  // Each guess waits for the page to apply the server's response.
  const guessedCount = `document.getElementById("guessed").textContent.split(",").length`;
  const settled = `!document.getElementById("new-game").disabled`;
  const clickKey = async (letter) => {
    await evaluate(`[...document.querySelectorAll(".key")]
      .find((k) => k.textContent === "${letter}").click()`);
    await waitFor(`${settled} && [...document.querySelectorAll(".key")]
      .find((k) => k.textContent === "${letter}").disabled`);
  };
  const pressKey = async (key) => {
    await send("Input.dispatchKeyEvent", { type: "keyDown", key, text: key });
    await sleep(150);
    await waitFor(settled);
  };
  const newGame = async (difficulty) => {
    await evaluate(`document.getElementById("difficulty").value = "${difficulty}";
      document.getElementById("new-game").click();`);
    await waitFor(`${settled} && document.getElementById("remaining").textContent === "6"
      && document.getElementById("guessed").textContent === "None"`);
  };

  await send("Runtime.enable");
  await send("Page.enable");
  await viewport(1280, 800);
  await load();

  // --- Initial page -------------------------------------------------------
  let s = await snapshot();
  check("initial page prompts for a new game", /Choose a difficulty/.test(s.message), s.message);
  check("initial page keys are disabled", s.enabledKeys === "");
  await screenshot("initial.png");

  // --- Each difficulty starts a game with the right number of blanks ------
  for (const [difficulty, length] of [["easy", 3], ["medium", 6], ["hard", 6]]) {
    await newGame(difficulty);
    s = await snapshot();
    check(`${difficulty} game shows ${length} blanks`,
      s.slots.length === length && s.slots.every((c) => c === ""), JSON.stringify(s.slots));
    check(`${difficulty} game enables all 26 keys`, s.enabledKeys.length === 26);
  }

  // --- Winning game: easy word "cat", one miss ----------------------------
  // Marker survives only if the page is not reloaded.
  await evaluate(`window.__noReload = true`);
  await newGame("easy");
  const playing = [];
  for (const letter of ["z", "c", "a"]) {
    await clickKey(letter);
    playing.push(await snapshot());
  }
  s = playing[0];
  check("incorrect guess updates remaining, incorrect list, drawing",
    s.remaining === "5" && s.incorrect === "Z" && s.parts === 1,
    JSON.stringify({ r: s.remaining, i: s.incorrect, p: s.parts }));
  s = playing[1];
  check("correct guess reveals the letter", s.slots.join("") === "c", JSON.stringify(s.slots));
  check("guessed list follows guess order", playing[2].guessed === "Z, C, A", playing[2].guessed);
  check("guessed keys are disabled", !/[zca]/.test(playing[2].enabledKeys));
  check("hidden word absent from the page while playing",
    playing.every((p) => !/\bcat\b/i.test(p.html)));
  await clickKey("t");
  s = await snapshot();
  check("win message shown", s.message === 'You won! The word was "cat".', s.message);
  check("all keys disabled after win", s.enabledKeys === "");
  check("button offers Play again", s.button === "Play again", s.button);
  await screenshot("won.png");

  // --- Start another game without reloading -------------------------------
  await newGame("hard");
  s = await snapshot();
  check("new game after a win resets the board",
    s.slots.length === 6 && s.slots.every((c) => c === "") && s.parts === 0 && s.enabledKeys.length === 26);
  check("new game did not reload the page", await evaluate(`window.__noReload === true`));

  // --- Losing game: hard word "rhythm" -------------------------------------
  for (const letter of ["r", "q", "x", "j", "z", "v", "k"]) await clickKey(letter);
  s = await snapshot();
  check("loss message shown", s.message === 'You lost. The word was "rhythm".', s.message);
  check("loss shows full drawing and zero remaining", s.parts === 6 && s.remaining === "0");
  check("loss fills in the missed letters", s.slots.join("") === "rhythm", s.slots.join(""));
  check("all keys disabled after loss", s.enabledKeys === "");
  await screenshot("lost.png");

  // --- Physical keyboard, repeated letters, resume after reload ------------
  await newGame("medium");
  await pressKey("e");
  await pressKey("E");
  s = await snapshot();
  check("typed letter is guessed once", s.guessed === "E" && s.remaining === "5", s.guessed);
  await pressKey("1");
  check("non-letter key is ignored", (await snapshot()).guessed === "E");
  const before = s;
  await load();
  await waitFor(`document.getElementById("guessed").textContent === "E"`);
  s = await snapshot();
  check("reload resumes the same game", s.guessed === before.guessed && s.remaining === "5");
  check("reload shows welcome back", /Welcome back/.test(s.message), s.message);

  // --- Layout at phone widths and in dark mode ------------------------------
  for (const width of [390, 320]) {
    await viewport(width, 800, true);
    await sleep(150);
    s = await snapshot();
    check(`no horizontal scroll at ${width}px`, s.scrollWidth <= s.clientWidth,
      `${s.scrollWidth} > ${s.clientWidth}`);
  }
  await screenshot("mobile.png");
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await sleep(150);
  await screenshot("mobile-dark.png");

  check("no JavaScript errors", pageErrors.length === 0, pageErrors.join("; "));
}
