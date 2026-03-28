const chatEl = document.getElementById("chat");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const micBtn = document.getElementById("micBtn");
const ttsToggle = document.getElementById("ttsToggle");
const chordInput = document.getElementById("chordInput");
const previewChordBtn = document.getElementById("previewChordBtn");
const sampleQueryInput = document.getElementById("sampleQueryInput");
const sampleSearchBtn = document.getElementById("sampleSearchBtn");
const samplesEl = document.getElementById("samples");
const statusEl = document.getElementById("status");
const runtimeMetaEl = document.getElementById("runtimeMeta");

let recognition = null;
let recognizing = false;

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
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
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
    if (ttsToggle.checked && data.text) {
      await postJSON("/api/tts", { text: data.text });
    }
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

async function previewChord() {
  const chord = chordInput.value.trim() || "Cm7";
  setStatus(`Playing ${chord}...`);
  try {
    const data = await postJSON("/api/audio/preview-chord", { chord });
    if (!data.ok) throw new Error(data.error || "Preview failed");
    addMessage("assistant", `${chord}: MIDI ${data.chord.midi_notes.join(", ")}`);
  } catch (err) {
    addMessage("assistant", `Preview error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

function renderSamples(items) {
  samplesEl.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "sample";
    row.innerHTML = `
      <h4>${item.name || "Unnamed sample"}</h4>
      <div>Duration: ${Number(item.duration || 0).toFixed(2)}s</div>
      <div>License: ${item.license || "unknown"}</div>
      <div class="row">
        <button data-act="preview">Preview</button>
        <button data-act="download" class="secondary">Download</button>
      </div>
    `;
    row.querySelector('[data-act="preview"]').addEventListener("click", () => {
      if (item.preview_url) {
        const audio = new Audio(item.preview_url);
        audio.play();
      }
    });
    row.querySelector('[data-act="download"]').addEventListener("click", async () => {
      if (!item.preview_url) return;
      setStatus(`Downloading ${item.name}...`);
      try {
        const data = await postJSON("/api/samples/download", { url: item.preview_url });
        if (!data.ok) throw new Error(data.error || "Download failed");
        addMessage("assistant", `Downloaded: ${data.path}`);
      } catch (err) {
        addMessage("assistant", `Download error: ${err.message}`);
      } finally {
        setStatus("");
      }
    });
    samplesEl.appendChild(row);
  });
}

async function searchSamples() {
  const query = sampleQueryInput.value.trim();
  if (!query) return;
  setStatus(`Searching "${query}"...`);
  try {
    const res = await fetch(`/api/samples/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Search failed");
    renderSamples(data.results || []);
  } catch (err) {
    addMessage("assistant", `Sample search error: ${err.message}`);
  } finally {
    setStatus("");
  }
}

function setupSpeechRecognition() {
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

async function loadRuntimeMeta() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (!data.ok) return;
    runtimeMetaEl.textContent = `Model provider: ${data.provider}. Computer control: ${data.computer_control_enabled ? "on" : "off"}. AppleScript: ${data.applescript_enabled ? "on" : "off"}.`;
  } catch (_) {}
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
previewChordBtn.addEventListener("click", previewChord);
sampleSearchBtn.addEventListener("click", searchSamples);
micBtn.addEventListener("click", toggleMic);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

setupSpeechRecognition();
loadRuntimeMeta();
addMessage("assistant", "Ready. Ask for production help, chords, or GarageBand actions.");
