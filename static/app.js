const chatEl = document.getElementById("chat");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const micBtn = document.getElementById("micBtn");
const statusEl = document.getElementById("status");

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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify(body || {}),
    });
    return res.json();
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
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

setupSpeechRecognition();
addMessage("assistant", "Ready. Ask for production help, chords, or GarageBand actions.");
