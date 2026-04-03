const chatEl = document.getElementById("chat");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const micBtn = document.getElementById("micBtn");
const createJungleBtn = document.getElementById("createJungleBtn");
const addDrummerBtn = document.getElementById("addDrummerBtn");
const playLatestBtn = document.getElementById("playLatestBtn");
const statusEl = document.getElementById("status");

let recognition = null;
let recognizing = false;

const defaultRequestTimeoutMs = 180000;
const configuredTimeout = Number.parseInt(document.documentElement.dataset.requestTimeoutMs || "", 10);
const requestTimeoutMs = Number.isFinite(configuredTimeout) && configuredTimeout > 0 ? configuredTimeout : defaultRequestTimeoutMs;
const requestTimeoutLabel = `${Math.round(requestTimeoutMs / 1000)}s`;
const voiceEnabled = (document.documentElement.dataset.voiceEnabled || "false").toLowerCase() === "true";
const ua = navigator.userAgent || "";
const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
const isMobile = /iPhone|iPad|Android|Mobile/i.test(ua);
const isMacDesktop = (/Mac/i.test(platform) || /Macintosh|Mac OS X/i.test(ua)) && !isMobile;

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  chatEl.appendChild(el);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

async function postJSON(url, body) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify(body || {}),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new Error(`Request timed out after ${requestTimeoutLabel}. Try a shorter step or increase UI_REQUEST_TIMEOUT_MS.`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;
  messageInput.value = "";
  addMessage("user", text);
  setStatus("Thinking...");
  try {
    const data = await postJSON("/api/chat", { message: text });
    if (!data.ok) throw new Error(data.error || "Chat failed");
    addMessage("assistant", data.text || "(empty response)");
  } catch (err) {
    addMessage("assistant", `Error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

async function resetChat() {
  await postJSON("/api/reset", {});
  chatEl.innerHTML = "";
  addMessage("assistant", "Chat history cleared.");
}

async function runCreateJungleWorkflow() {
  setStatus("Creating Jungle song...");
  try {
    const data = await postJSON("/api/workflow/create-jungle", {
      bars: 8,
      bpm: 120,
      key: "C",
      replace_current_project: true,
      auto_play_rendered_audio: false,
    });
    if (!data.ok) throw new Error(data.error || "Create Jungle workflow failed");
    const midiPath = data.composition && data.composition.midi_file_path ? data.composition.midi_file_path : "(missing midi path)";
    addMessage("assistant", `Jungle song created and opened in GarageBand.\nMIDI: ${midiPath}`);
  } catch (err) {
    addMessage("assistant", `Create Jungle error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

async function runAddDrummerWorkflow() {
  setStatus("Adding GarageBand Drummer tracks...");
  try {
    const data = await postJSON("/api/workflow/add-drummer-second-beat", { repeats: 2 });
    if (!data.ok) throw new Error(data.error || "Add drummer workflow failed");
    addMessage("assistant", "Added Drummer tracks (2x) via GarageBand Track menu defaults.");
  } catch (err) {
    addMessage("assistant", `Add Drummer error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

async function runPlayLatestWorkflow() {
  setStatus("Playing latest rendered song...");
  try {
    const data = await postJSON("/api/workflow/play-latest", {});
    if (!data.ok) throw new Error(data.error || "Play latest workflow failed");
    addMessage("assistant", `Playing: ${data.latest_audio}`);
  } catch (err) {
    addMessage("assistant", `Play latest error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

function setupSpeechRecognition() {
  if (!voiceEnabled) {
    micBtn.disabled = true;
    micBtn.textContent = "Mic Disabled";
    return;
  }
  if (!isMacDesktop) {
    micBtn.disabled = true;
    micBtn.textContent = "Mic Mac Only";
    return;
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.textContent = "Mic Unsupported";
    return;
  }
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    messageInput.value = transcript;
    sendMessage();
  };
  recognition.onend = () => {
    recognizing = false;
    micBtn.textContent = "Start Mic";
  };
}

function toggleMic() {
  if (!recognition) return;
  if (recognizing) {
    recognition.stop();
    recognizing = false;
    micBtn.textContent = "Start Mic";
    return;
  }
  recognition.start();
  recognizing = true;
  micBtn.textContent = "Stop Mic";
}

sendBtn.addEventListener("click", sendMessage);
resetBtn.addEventListener("click", resetChat);
micBtn.addEventListener("click", toggleMic);
createJungleBtn.addEventListener("click", runCreateJungleWorkflow);
addDrummerBtn.addEventListener("click", runAddDrummerWorkflow);
playLatestBtn.addEventListener("click", runPlayLatestWorkflow);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

setupSpeechRecognition();
addMessage("assistant", "Ready. Ask for production help, chords, or GarageBand actions.");
