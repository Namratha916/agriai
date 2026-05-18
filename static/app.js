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
const recordBtn = document.querySelector("#recordBtn");
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
let mediaRecorder = null;
let recordedChunks = [];
let detectedAutoLanguage = "en";

const UI_TEXT = {
  en: {
    eyebrow: "Chemical decontamination alert system",
    language: "Language",
    helpline: "India poison helpline: 1800-116-117",
    chemicalTitle: "Chemical Identifier",
    chemicalDesc: "Enter the pesticide or chemical name from the bottle, bag, or label.",
    chemicalPlaceholder: "Example: chlorpyrifos, paraquat, glyphosate",
    check: "Check",
    chemicalResult: "Chemical risk details will appear here.",
    imageTitle: "Pesticide Photo Analyzer",
    imageDesc: "Upload or capture the pesticide label. Type visible label text if OCR cannot read the image.",
    imageNotes: "Optional: type any label text you can read, e.g. chlorpyrifos 20% EC",
    analyzePhoto: "Analyze photo",
    imageResult: "Image analysis result will appear here.",
    checklistTitle: "Decontamination Checklist",
    checklistDesc: "Choose exposure type and follow each step before entering the home.",
    skin: "Skin/clothes",
    eyes: "Eyes",
    breathing: "Breathing",
    symptomsTitle: "Symptom Checker",
    symptomsDesc: "Select symptoms or type your own observations.",
    symptomText: "Other symptoms or what happened...",
    analyzeSymptoms: "Analyze symptoms",
    emergencyTitle: "Emergency Alert",
    emergencyDesc: "Create a one-tap message with chemical, symptoms, and location.",
    contact: "Emergency contact phone number",
    location: "Use location",
    createAlert: "Create alert",
    emergencyMessage: "Emergency message will be generated here.",
    hospitalTitle: "Nearby Hospital Finder",
    hospitalDesc: "Open a map search for hospitals or poison support near your position.",
    nearestHospital: "Nearest hospital",
    poisonCenter: "Poison control center",
    callPoison: "Call 1800-116-117",
    chatTitle: "AgriAI Chatbot",
    chatDesc: "Powered by your local Ollama model when Ollama is running.",
    chatWelcome: "Tell me the chemical name, how exposure happened, and symptoms. I will guide the next step.",
    voiceInput: "Voice input",
    recordVoice: "Record voice",
    speakReplies: "Speak replies",
    voiceStatus: "Voice uses your browser speech tools.",
    chatPlaceholder: "Ask: I sprayed chlorpyrifos and feel dizzy, what should I do?",
    send: "Send",
    symptomLabels: ["Headache", "Vomiting", "Dizziness", "Eye irritation", "Breathing difficulty", "Heavy sweating", "Muscle twitching", "Confusion"],
  },
  hi: {
    eyebrow: "रासायनिक डी-कंटैमिनेशन अलर्ट सिस्टम",
    language: "भाषा",
    helpline: "भारत poison helpline: 1800-116-117",
    chemicalTitle: "रसायन पहचान",
    chemicalDesc: "बोतल, बैग या label पर लिखा pesticide/chemical नाम डालें.",
    chemicalPlaceholder: "उदाहरण: chlorpyrifos, paraquat, glyphosate",
    check: "जांचें",
    chemicalResult: "रसायन risk details यहां दिखेंगे.",
    imageTitle: "Pesticide फोटो analyzer",
    imageDesc: "Pesticide label upload/capture करें. OCR न पढ़ पाए तो visible label text type करें.",
    imageNotes: "Optional: label पर दिख रहा text लिखें, जैसे chlorpyrifos 20% EC",
    analyzePhoto: "फोटो analyze करें",
    imageResult: "Image analysis result यहां दिखेगा.",
    checklistTitle: "Decontamination checklist",
    checklistDesc: "Exposure type चुनें और घर जाने से पहले steps follow करें.",
    skin: "त्वचा/कपड़े",
    eyes: "आंखें",
    breathing: "सांस",
    symptomsTitle: "Symptom checker",
    symptomsDesc: "Symptoms select करें या अपनी observation type करें.",
    symptomText: "अन्य symptoms या क्या हुआ...",
    analyzeSymptoms: "Symptoms analyze करें",
    emergencyTitle: "Emergency alert",
    emergencyDesc: "Chemical, symptoms और location वाला one-tap message बनाएं.",
    contact: "Emergency contact phone number",
    location: "Location जोड़ें",
    createAlert: "Alert बनाएं",
    emergencyMessage: "Emergency message यहां बनेगा.",
    hospitalTitle: "Nearby hospital finder",
    hospitalDesc: "Nearby hospital या poison support map search खोलें.",
    nearestHospital: "नजदीकी hospital",
    poisonCenter: "Poison control center",
    callPoison: "1800-116-117 call करें",
    chatTitle: "AgriAI chatbot",
    chatDesc: "Local Ollama model चल रहा हो तो उससे powered.",
    chatWelcome: "Chemical name, exposure कैसे हुआ, और symptoms बताइए. मैं next step बताऊंगा.",
    voiceInput: "Voice input",
    recordVoice: "Voice record",
    speakReplies: "Replies बोलें",
    voiceStatus: "Voice आपके browser speech tools का उपयोग करता है.",
    chatPlaceholder: "पूछें: मैंने chlorpyrifos spray किया और चक्कर आ रहा है, क्या करूं?",
    send: "भेजें",
    symptomLabels: ["सिरदर्द", "उल्टी", "चक्कर", "आंख में जलन", "सांस की दिक्कत", "ज्यादा पसीना", "मांसपेशी फड़कना", "भ्रम"],
  },
  kn: {
    eyebrow: "ರಾಸಾಯನಿಕ ಡೀಕಂಟಾಮಿನೇಶನ್ ಅಲರ್ಟ್ ವ್ಯವಸ್ಥೆ",
    language: "ಭಾಷೆ",
    helpline: "ಭಾರತ poison helpline: 1800-116-117",
    chemicalTitle: "ರಾಸಾಯನಿಕ ಗುರುತು",
    chemicalDesc: "ಬಾಟಲ್, ಚೀಲ ಅಥವಾ label‌ನಲ್ಲಿರುವ pesticide/chemical ಹೆಸರನ್ನು ನಮೂದಿಸಿ.",
    chemicalPlaceholder: "ಉದಾಹರಣೆ: chlorpyrifos, paraquat, glyphosate",
    check: "ಪರಿಶೀಲಿಸಿ",
    chemicalResult: "ರಾಸಾಯನಿಕ risk details ಇಲ್ಲಿ ಕಾಣುತ್ತವೆ.",
    imageTitle: "Pesticide ಫೋಟೋ analyzer",
    imageDesc: "Pesticide label upload/capture ಮಾಡಿ. OCR ಓದಲು ಆಗದಿದ್ದರೆ label text type ಮಾಡಿ.",
    imageNotes: "Optional: label‌ನಲ್ಲಿ ಕಾಣುವ text type ಮಾಡಿ, ಉದಾ: chlorpyrifos 20% EC",
    analyzePhoto: "ಫೋಟೋ analyze ಮಾಡಿ",
    imageResult: "Image analysis result ಇಲ್ಲಿ ಕಾಣುತ್ತದೆ.",
    checklistTitle: "Decontamination checklist",
    checklistDesc: "Exposure type ಆಯ್ಕೆ ಮಾಡಿ ಮತ್ತು ಮನೆಗೆ ಹೋಗುವ ಮೊದಲು steps follow ಮಾಡಿ.",
    skin: "ಚರ್ಮ/ಬಟ್ಟೆ",
    eyes: "ಕಣ್ಣುಗಳು",
    breathing: "ಉಸಿರಾಟ",
    symptomsTitle: "ಲಕ್ಷಣ checker",
    symptomsDesc: "ಲಕ್ಷಣಗಳನ್ನು ಆಯ್ಕೆಮಾಡಿ ಅಥವಾ ನಿಮ್ಮ observation type ಮಾಡಿ.",
    symptomText: "ಇತರೆ ಲಕ್ಷಣಗಳು ಅಥವಾ ಏನಾಯಿತು...",
    analyzeSymptoms: "ಲಕ್ಷಣ analyze ಮಾಡಿ",
    emergencyTitle: "Emergency alert",
    emergencyDesc: "Chemical, symptoms ಮತ್ತು location ಇರುವ one-tap message ರಚಿಸಿ.",
    contact: "Emergency contact phone number",
    location: "Location ಬಳಸಿ",
    createAlert: "Alert ರಚಿಸಿ",
    emergencyMessage: "Emergency message ಇಲ್ಲಿ generate ಆಗುತ್ತದೆ.",
    hospitalTitle: "ಹತ್ತಿರದ hospital finder",
    hospitalDesc: "ನಿಮ್ಮ ಸ್ಥಳದ ಹತ್ತಿರ hospital ಅಥವಾ poison support map search ತೆರೆಯಿರಿ.",
    nearestHospital: "ಹತ್ತಿರದ hospital",
    poisonCenter: "Poison control center",
    callPoison: "1800-116-117 ಕರೆ ಮಾಡಿ",
    chatTitle: "AgriAI chatbot",
    chatDesc: "Local Ollama model running ಇದ್ದರೆ ಅದರಿಂದ powered.",
    chatWelcome: "Chemical name, exposure ಹೇಗೆ ಆಯಿತು, ಮತ್ತು symptoms ಹೇಳಿ. ನಾನು next step ಹೇಳುತ್ತೇನೆ.",
    voiceInput: "Voice input",
    recordVoice: "Voice record",
    speakReplies: "Replies ಮಾತಾಡಲಿ",
    voiceStatus: "Voice ನಿಮ್ಮ browser speech tools ಬಳಸುತ್ತದೆ.",
    chatPlaceholder: "ಕೇಳಿ: ನಾನು chlorpyrifos spray ಮಾಡಿದೆ ಮತ್ತು ತಲೆ ಸುತ್ತುತ್ತಿದೆ, ಏನು ಮಾಡಲಿ?",
    send: "ಕಳುಹಿಸಿ",
    symptomLabels: ["ತಲೆನೋವು", "ವಾಂತಿ", "ತಲೆ ಸುತ್ತುವುದು", "ಕಣ್ಣು ಉರಿಯುವುದು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಹೆಚ್ಚು ಬೆವರು", "ಮಾಂಸಖಂಡ twitching", "ಗೊಂದಲ"],
  },
};

function uiLanguage() {
  const selected = currentLanguage();
  if (selected === "auto") return detectedAutoLanguage;
  return selected;
}

function detectInputLanguage(text) {
  if (containsKannada(text)) return "kn";
  if (containsDevanagari(text)) return "hi";
  return "en";
}

function updateAutoLanguageFromText(text) {
  if (currentLanguage() !== "auto") return;
  detectedAutoLanguage = detectInputLanguage(text);
  applyUILanguage();
}

function applyUILanguage() {
  const text = UI_TEXT[uiLanguage()] || UI_TEXT.en;
  document.documentElement.lang = uiLanguage();
  document.querySelector(".eyebrow").textContent = text.eyebrow;
  document.querySelector(".language-control").firstChild.textContent = `${text.language} `;
  document.querySelector(".helpline").textContent = text.helpline;
  chemicalInput.placeholder = text.chemicalPlaceholder;
  lookupBtn.textContent = text.check;
  if (chemicalResult.classList.contains("muted")) chemicalResult.textContent = text.chemicalResult;
  imageNotes.placeholder = text.imageNotes;
  imageAnalyzeBtn.textContent = text.analyzePhoto;
  if (imageResult.classList.contains("muted")) imageResult.textContent = text.imageResult;
  symptomText.placeholder = text.symptomText;
  symptomBtn.textContent = text.analyzeSymptoms;
  contactInput.placeholder = text.contact;
  locationBtn.textContent = text.location;
  alertBtn.textContent = text.createAlert;
  emergencyMessage.placeholder = text.emergencyMessage;
  hospitalLink.textContent = text.nearestHospital;
  document.querySelector('a[href="https://www.google.com/maps/search/poison+control+center"]').textContent = text.poisonCenter;
  document.querySelector(".hospital-actions a[href='tel:1800116117']").textContent = text.callPoison;
  micBtn.textContent = text.voiceInput;
  recordBtn.textContent = text.recordVoice;
  document.querySelector(".toggle-row").lastChild.textContent = ` ${text.speakReplies}`;
  voiceStatus.textContent = text.voiceStatus;
  chatInput.placeholder = text.chatPlaceholder;
  chatBtn.textContent = text.send;
  const headings = document.querySelectorAll("h2");
  headings[0].textContent = text.chemicalTitle;
  headings[1].textContent = text.imageTitle;
  headings[2].textContent = text.checklistTitle;
  headings[3].textContent = text.symptomsTitle;
  headings[4].textContent = text.emergencyTitle;
  headings[5].textContent = text.hospitalTitle;
  headings[6].textContent = text.chatTitle;
  const descriptions = document.querySelectorAll(".section-title p");
  descriptions[0].textContent = text.chemicalDesc;
  descriptions[1].textContent = text.imageDesc;
  descriptions[2].textContent = text.checklistDesc;
  descriptions[3].textContent = text.symptomsDesc;
  descriptions[4].textContent = text.emergencyDesc;
  descriptions[5].textContent = text.hospitalDesc;
  descriptions[6].textContent = text.chatDesc;
  document.querySelector('[data-exposure="skin"]').textContent = text.skin;
  document.querySelector('[data-exposure="eye"]').textContent = text.eyes;
  document.querySelector('[data-exposure="inhalation"]').textContent = text.breathing;
  document.querySelectorAll(".symptom-grid label").forEach((label, index) => {
    const input = label.querySelector("input");
    label.textContent = "";
    label.appendChild(input);
    label.append(` ${text.symptomLabels[index] || input.value}`);
  });
  const firstBot = chatLog.querySelector(".bot.bubble");
  if (chatHistory.length === 0 && firstBot) firstBot.textContent = text.chatWelcome;
}

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

  const phone = normalizePhone(contactInput.value.trim());
  const encoded = encodeURIComponent(data.message);
  const smsSeparator = /iPad|iPhone|iPod/.test(navigator.userAgent) ? "&" : "?";
  smsLink.href = phone ? `sms:${phone}${smsSeparator}body=${encoded}` : `sms:${smsSeparator}body=${encoded}`;
  whatsappLink.href = phone ? `https://api.whatsapp.com/send?phone=${phone}&text=${encoded}` : `https://api.whatsapp.com/send?text=${encoded}`;
  smsLink.target = "_self";
  whatsappLink.target = "_blank";
  smsLink.classList.remove("disabled");
  whatsappLink.classList.remove("disabled");
}

function normalizePhone(rawPhone) {
  const digits = rawPhone.replace(/\D/g, "");
  if (!digits) return "";
  if (digits.length === 10) return `91${digits}`;
  return digits;
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
  voiceStatus.textContent = `Speaking in ${utterance.lang}.`;
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.disabled = true;
    voiceStatus.textContent = "Browser voice input is not supported here. Use Record voice or type.";
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
    updateAutoLanguageFromText(transcript);
    voiceStatus.textContent = `Heard: ${transcript}`;
    chatInput.focus();
  };

  recognition.onerror = () => {
    voiceStatus.textContent = "Voice input failed. Try typing or allow microphone access.";
  };

  recognition.onend = () => {
    micBtn.textContent = "Voice input";
  };
}

async function toggleRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    voiceStatus.textContent = "Recording is not supported in this browser.";
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      recordBtn.textContent = "Record voice";
      await transcribeRecording();
    };
    mediaRecorder.start();
    recordBtn.textContent = "Stop recording";
    voiceStatus.textContent = "Recording... speak now.";
  } catch {
    voiceStatus.textContent = "Microphone permission denied or unavailable.";
  }
}

async function transcribeRecording() {
  const audioBlob = new Blob(recordedChunks, { type: "audio/webm" });
  const formData = new FormData();
  formData.append("audio", audioBlob, "voice.webm");
  formData.append("language", currentLanguage());
  voiceStatus.textContent = "Converting voice to text...";

  try {
    const response = await fetch("/api/speech-to-text", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok || !data.text) throw new Error(data.error || "No text");
    chatInput.value = data.text;
    updateAutoLanguageFromText(data.text);
    voiceStatus.textContent = `Heard: ${data.text}`;
  } catch {
    voiceStatus.textContent = "Server voice recognition is unavailable. Try browser Voice input or type.";
  }
}

async function sendChat() {
  const message = chatInput.value.trim();
  if (!message) return;
  updateAutoLanguageFromText(message);

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
  formData.append("chemical_hint", chemicalInput.value);
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
      <pre>${escapeHtml(data.ocr_text || "No text extracted")}</pre>
    </details>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
recordBtn.addEventListener("click", toggleRecording);
imageInput.addEventListener("change", previewImage);
imageAnalyzeBtn.addEventListener("click", analyzeImage);
languageSelect.addEventListener("change", applyUILanguage);
chatInput.addEventListener("input", () => updateAutoLanguageFromText(chatInput.value));
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendChat();
});

setupSpeechRecognition();
applyUILanguage();
loadChecklist();
