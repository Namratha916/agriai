const chemicalInput = document.querySelector("#chemicalInput");
const chemicalResult = document.querySelector("#chemicalResult");
const lookupBtn = document.querySelector("#lookupBtn");
const checklist = document.querySelector("#checklist");
const symptomBtn = document.querySelector("#symptomBtn");
const symptomResult = document.querySelector("#symptomResult");
const symptomText = document.querySelector("#symptomText");
const locationBtn = document.querySelector("#locationBtn");
const alertBtn = document.querySelector("#alertBtn");
const emergencyMessage = document.querySelector("#emergencyMessage");
const contactInput = document.querySelector("#contactInput");
const smsLink = document.querySelector("#smsLink");
const whatsappLink = document.querySelector("#whatsappLink");
const hospitalLink = document.querySelector("#hospitalLink");
const chatLog = document.querySelector("#chatLog");
const chatInput = document.querySelector("#chatInput");
const chatBtn = document.querySelector("#chatBtn");
const languageSelect = document.querySelector("#languageSelect");
const micBtn = document.querySelector("#micBtn");
const speakToggle = document.querySelector("#speakToggle");
const voiceStatus = document.querySelector("#voiceStatus");
const imageInput = document.querySelector("#imageInput");
const imagePreview = document.querySelector("#imagePreview");
const imageNotes = document.querySelector("#imageNotes");
const imageAnalyzeBtn = document.querySelector("#imageAnalyzeBtn");
const imageResult = document.querySelector("#imageResult");

let selectedLocation = "";
const chatHistory = [];
let recognition = null;

function dangerClass(level) {
  if (level === "Extreme" || level === "High") return "danger";
  if (level === "Moderate" || level === "Low to Moderate") return "warning";
  return "safe";
}

function selectedSymptoms() {
  const checked = [...document.querySelectorAll(".symptom-grid input:checked")].map((input) => input.value);
  if (symptomText.value.trim()) checked.push(symptomText.value.trim());
  return checked;
}

function renderChemical(data) {
  if (!data.found) {
    chemicalResult.innerHTML = `<strong>Not found.</strong> ${data.message}`;
    return;
  }

  const chemical = data.chemical;
  chemicalResult.innerHTML = `
    <strong>${chemical.name}</strong>
    <div>Category: ${chemical.category}</div>
    <div>Danger level: <span class="${dangerClass(chemical.danger_level)}">${chemical.danger_level}</span></div>
    <div>Common symptoms: ${chemical.symptoms.join(", ")}</div>
    <div>First aid: ${chemical.first_aid}</div>
    <div class="muted">${chemical.notes}</div>
  `;
}

async function lookupChemical() {
  const name = chemicalInput.value.trim();
  if (!name) {
    chemicalResult.textContent = "Enter the chemical name first.";
    return;
  }

  const response = await fetch(`/api/chemical?name=${encodeURIComponent(name)}`);
  const data = await response.json();
  renderChemical(data);
}

async function loadChecklist(type = "skin") {
  const response = await fetch(`/api/decontamination?type=${encodeURIComponent(type)}`);
  const data = await response.json();
  checklist.innerHTML = data.steps
    .map((step) => `<li><strong>${step.title}</strong><span>${step.detail}</span></li>`)
    .join("");
}

async function analyzeSymptoms() {
  const symptoms = selectedSymptoms();
  if (!symptoms.length) {
    symptomResult.textContent = "Select or type at least one symptom.";
    return;
  }

  const response = await fetch("/api/symptoms", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chemical: chemicalInput.value, symptoms }),
  });
  const data = await response.json();
  const className = data.level === "Emergency" ? "danger" : data.level === "High concern" ? "warning" : "safe";
  symptomResult.innerHTML = `
    <strong class="${className}">${data.level}</strong>
    <div>${data.action}</div>
    <div class="muted">Matched symptoms: ${data.matched_symptoms.length ? data.matched_symptoms.join(", ") : "none from high-risk list"}</div>
  `;
}

function updateMapLinks(latitude, longitude) {
  const query = `${latitude},${longitude} nearest hospital`;
  hospitalLink.href = `https://www.google.com/maps/search/${encodeURIComponent(query)}`;
}

function useLocation() {
  if (!navigator.geolocation) {
    selectedLocation = "GPS not supported";
    return;
  }

  locationBtn.textContent = "Finding location...";
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const { latitude, longitude } = position.coords;
      selectedLocation = `https://www.google.com/maps?q=${latitude},${longitude}`;
      updateMapLinks(latitude, longitude);
      locationBtn.textContent = "Location added";
    },
    () => {
      selectedLocation = "Location permission denied";
      locationBtn.textContent = "Use location";
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

async function createAlert() {
  const symptoms = selectedSymptoms().join(", ") || "not provided";
  const response = await fetch("/api/emergency-message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chemical: chemicalInput.value || "unknown chemical",
      symptoms,
      location: selectedLocation || "location unavailable",
    }),
  });
  const data = await response.json();
  emergencyMessage.value = data.message;

  const phone = contactInput.value.trim();
  const encoded = encodeURIComponent(data.message);
  smsLink.href = phone ? `sms:${phone}?body=${encoded}` : `sms:?body=${encoded}`;
  whatsappLink.href = phone ? `https://wa.me/${phone.replace(/\D/g, "")}?text=${encoded}` : `https://wa.me/?text=${encoded}`;
  smsLink.classList.remove("disabled");
  whatsappLink.classList.remove("disabled");
}

function addMessage(text, type) {
  const bubble = document.createElement("div");
  bubble.className = `${type} bubble`;
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function currentLanguage() {
  return languageSelect.value;
}

function browserSpeechLanguage() {
  const language = currentLanguage();
  if (language === "kn") return "kn-IN";
  if (language === "hi") return "hi-IN";
  if (language === "en") return "en-IN";
  if (containsKannada(chatInput.value)) return "kn-IN";
  if (containsDevanagari(chatInput.value)) return "hi-IN";
  return "en-IN";
}

function containsKannada(text) {
  return /[\u0c80-\u0cff]/.test(text);
}

function containsDevanagari(text) {
  return /[\u0900-\u097f]/.test(text);
}

function speakText(text) {
  if (!speakToggle.checked || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const language = currentLanguage();
  utterance.lang = language === "kn" || containsKannada(text) ? "kn-IN" : language === "hi" || containsDevanagari(text) ? "hi-IN" : "en-IN";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    voiceStatus.textContent = "Voice input is not supported in this browser.";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    micBtn.textContent = "Listening...";
    voiceStatus.textContent = "Speak now.";
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    chatInput.value = transcript;
    voiceStatus.textContent = `Heard: ${transcript}`;
  };

  recognition.onerror = () => {
    voiceStatus.textContent = "Voice input failed. Try typing or allow microphone access.";
  };

  recognition.onend = () => {
    micBtn.textContent = "Voice input";
  };
}

async function sendChat() {
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage(message, "user");
  chatHistory.push({ role: "user", content: message });
  chatInput.value = "";
  chatBtn.disabled = true;
  chatBtn.textContent = "Sending";
  const pending = addMessage("Generating reply...", "bot");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 105000);

  try {
    const response = await fetch("/api/chat-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        message,
        chemical: chemicalInput.value,
        symptoms: selectedSymptoms().join(", "),
        history: chatHistory.slice(-8),
        language: currentLanguage(),
      }),
    });
    if (!response.ok || !response.body) {
      throw new Error("stream unavailable");
    }
    pending.textContent = "";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const event of events) {
        const line = event.split("\n").find((item) => item.startsWith("data: "));
        if (!line) continue;
        const dataText = line.slice(6);
        if (dataText === "[DONE]") continue;
        try {
          const data = JSON.parse(dataText);
          pending.textContent += data.token || "";
          chatLog.scrollTop = chatLog.scrollHeight;
        } catch {
          pending.textContent += dataText;
        }
      }
    }
    if (!pending.textContent.trim()) {
      pending.textContent = "I could not create a reply. Please enter the chemical name and symptoms again.";
    }
    chatHistory.push({ role: "assistant", content: pending.textContent });
    speakText(pending.textContent);
  } catch (error) {
    await sendChatFallback(message, pending);
  } finally {
    clearTimeout(timeout);
    chatBtn.disabled = false;
    chatBtn.textContent = "Send";
  }
}

async function sendChatFallback(message, pending) {
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        chemical: chemicalInput.value,
        symptoms: selectedSymptoms().join(", "),
        history: chatHistory.slice(-8),
        language: currentLanguage(),
      }),
    });
    const data = await response.json();
    pending.textContent = data.reply || "I could not create a reply. Please enter the chemical name and symptoms again.";
  } catch {
    pending.textContent = "The AI model is unavailable. For urgent exposure: move to fresh air, remove contaminated clothes, wash exposed skin and hair with soap and water, rinse exposed eyes for 15 minutes, and call a hospital or 1800-116-117 if symptoms are present.";
  }
  chatHistory.push({ role: "assistant", content: pending.textContent });
  speakText(pending.textContent);
}

function previewImage() {
  const file = imageInput.files[0];
  if (!file) {
    imagePreview.removeAttribute("src");
    return;
  }
  imagePreview.src = URL.createObjectURL(file);
}

async function analyzeImage() {
  const file = imageInput.files[0];
  if (!file) {
    imageResult.textContent = "Choose or capture a pesticide label photo first.";
    return;
  }

  imageAnalyzeBtn.disabled = true;
  imageAnalyzeBtn.textContent = "Analyzing";
  imageResult.textContent = "Analyzing photo with local/offline tools...";

  const formData = new FormData();
  formData.append("image", file);
  formData.append("notes", imageNotes.value);
  formData.append("language", currentLanguage());

  try {
    const response = await fetch("/api/analyze-image", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    imageResult.innerHTML = renderImageAnalysis(data);
    speakText(data.reply);
  } catch (error) {
    imageResult.textContent = "Could not analyze the image. Type the pesticide name from the label and try chemical lookup.";
  } finally {
    imageAnalyzeBtn.disabled = false;
    imageAnalyzeBtn.textContent = "Analyze photo";
  }
}

function renderImageAnalysis(data) {
  const details = data.details || {};
  const toxicity = data.toxicity_level || details.harmfulness_level || "Unknown";
  const badgeClass = toxicity === "Extreme" || toxicity === "High" ? "danger" : toxicity === "Moderate" ? "warning" : "safe";
  const items = [
    ["Pesticide/Product", details.pesticide_name],
    ["Active ingredients", (details.active_ingredients || []).join(", ")],
    ["Usage", details.usage],
    ["Toxicity category", data.toxicity_category || details.toxicity_category],
    ["First aid", details.first_aid],
    ["Side effects", (details.side_effects || []).join(", ")],
    ["Safety precautions", (details.safety_precautions || []).join("; ")],
    ["Decontamination", (details.decontamination_steps || []).join("; ")],
    ["Environmental impact", details.environmental_impact],
  ];

  return `
    <div class="analysis-header">
      <strong>Image Analysis</strong>
      <span class="toxicity-badge ${badgeClass}">${toxicity}</span>
    </div>
    <div class="analysis-list">
      ${items.map(([label, value]) => `<div><b>${label}:</b> ${value || "Unknown"}</div>`).join("")}
    </div>
    <details>
      <summary>OCR details</summary>
      <div><b>Engines:</b> ${(data.ocr_engines || []).join(", ") || "None available"}</div>
      <pre>${data.ocr_text || "No text extracted"}</pre>
    </details>
  `;
}

lookupBtn.addEventListener("click", lookupChemical);
chemicalInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") lookupChemical();
});

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    loadChecklist(button.dataset.exposure);
  });
});

symptomBtn.addEventListener("click", analyzeSymptoms);
locationBtn.addEventListener("click", useLocation);
alertBtn.addEventListener("click", createAlert);
chatBtn.addEventListener("click", sendChat);
micBtn.addEventListener("click", () => {
  if (!recognition) return;
  recognition.lang = browserSpeechLanguage();
  recognition.start();
});
imageInput.addEventListener("change", previewImage);
imageAnalyzeBtn.addEventListener("click", analyzeImage);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendChat();
});

setupSpeechRecognition();
loadChecklist();
