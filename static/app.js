const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const el = {
  chemicalInput: $("#chemicalInput"),
  chemicalResult: $("#chemicalResult"),
  lookupBtn: $("#lookupBtn"),
  checklist: $("#checklist"),
  symptomBtn: $("#symptomBtn"),
  symptomResult: $("#symptomResult"),
  symptomText: $("#symptomText"),
  locationBtn: $("#locationBtn"),
  emergencyMessage: $("#emergencyMessage"),
  hospitalLink: $("#hospitalLink"),
  chatLog: $("#chatLog"),
  chatInput: $("#chatInput"),
  chatBtn: $("#chatBtn"),
  languageSelect: $("#languageSelect"),
  micBtn: $("#micBtn"),
  recordBtn: $("#recordBtn"),
  voiceToggleBtn: $("#voiceToggleBtn"),
  voiceStatus: $("#voiceStatus"),
  selectedLanguageStatus: $("#selectedLanguageStatus"),
  imageInput: $("#imageInput"),
  imagePreview: $("#imagePreview"),
  imageNotes: $("#imageNotes"),
  imageAnalyzeBtn: $("#imageAnalyzeBtn"),
  imageResult: $("#imageResult"),
};

let selectedLocation = "";
let recognition = null;
let mediaRecorder = null;
let recordedChunks = [];
let fallbackAudio = null;

const state = {
  chatHistory: [],
  detectedAutoLanguage: "en",
  voiceEnabled: localStorage.getItem("agriaiVoiceEnabled") !== "false",
  voiceAutoSend: localStorage.getItem("agriaiVoiceAutoSend") !== "false",
  voiceListening: false,
};

const UI_TEXT = {
  en: {
    language: "Language",
    helpline: "India poison helpline: 1800-116-117",
    voiceInput: "Voice input",
    recordVoice: "Record voice",
    voiceOn: "Voice ON",
    voiceOff: "Voice OFF",
    voiceReady: "Voice ready. Speak and I will send the transcript automatically.",
    voiceEdit: "Transcript heard and ready to send.",
    selectedLanguage: "English",
    send: "Send",
    analyzing: "Analyzing photo...",
    imageDefault: "Image analysis result will appear here.",
    imageAnalysis: "Image Analysis",
    noImage: "Choose or capture a pesticide label photo first.",
    imageHelp: "Tip: for best accuracy, crop the label so the product name and active ingredient are readable. If OCR misses it, type the visible text in the notes box.",
  },
  hi: {
    language: "भाषा",
    helpline: "विष हेल्पलाइन: 1800-116-117",
    voiceInput: "आवाज इनपुट",
    recordVoice: "आवाज रिकॉर्ड",
    voiceOn: "आवाज ON",
    voiceOff: "आवाज OFF",
    voiceReady: "आवाज तैयार है। पहले टेक्स्ट बॉक्स में transcript आएगा।",
    voiceEdit: "Transcript जुड़ गया। जांचकर Send दबाएं।",
    selectedLanguage: "हिन्दी",
    send: "भेजें",
    analyzing: "फोटो विश्लेषण हो रहा है...",
    imageDefault: "फोटो विश्लेषण यहां दिखेगा।",
    imageAnalysis: "फोटो विश्लेषण",
    noImage: "पहले कीटनाशक लेबल की फोटो चुनें या खींचें।",
    imageHelp: "सुझाव: सही पहचान के लिए लेबल में उत्पाद नाम और active ingredient साफ दिखना चाहिए। OCR छूटे तो दिखने वाला टेक्स्ट notes में लिखें।",
  },
  kn: {
    language: "ಭಾಷೆ",
    helpline: "ವಿಷ ಸಹಾಯವಾಣಿ: 1800-116-117",
    voiceInput: "ಧ್ವನಿ ಇನ್‌ಪುಟ್",
    recordVoice: "ಧ್ವನಿ ರೆಕಾರ್ಡ್",
    voiceOn: "ಧ್ವನಿ ON",
    voiceOff: "ಧ್ವನಿ OFF",
    voiceReady: "ಧ್ವನಿ ಸಿದ್ಧವಾಗಿದೆ. ಮೊದಲು transcript ಪಠ್ಯ ಬಾಕ್ಸ್‌ಗೆ ಬರುತ್ತದೆ.",
    voiceEdit: "Transcript ಸೇರಿಸಲಾಗಿದೆ. ಪರಿಶೀಲಿಸಿ Send ಒತ್ತಿರಿ.",
    selectedLanguage: "ಕನ್ನಡ",
    send: "ಕಳುಹಿಸಿ",
    analyzing: "ಫೋಟೋ ವಿಶ್ಲೇಷಣೆ ನಡೆಯುತ್ತಿದೆ...",
    imageDefault: "ಫೋಟೋ ವಿಶ್ಲೇಷಣೆ ಇಲ್ಲಿ ಕಾಣುತ್ತದೆ.",
    imageAnalysis: "ಫೋಟೋ ವಿಶ್ಲೇಷಣೆ",
    noImage: "ಮೊದಲು ಕೀಟನಾಶಕ ಲೇಬಲ್ ಫೋಟೋ ಆಯ್ಕೆ ಮಾಡಿ ಅಥವಾ ತೆಗೆದುಕೊಳ್ಳಿ.",
    imageHelp: "ಸಲಹೆ: ಸರಿಯಾದ ಗುರುತಿಗಾಗಿ ಲೇಬಲ್‌ನಲ್ಲಿ ಉತ್ಪನ್ನದ ಹೆಸರು ಮತ್ತು active ingredient ಸ್ಪಷ್ಟವಾಗಿ ಕಾಣಬೇಕು. OCR ತಪ್ಪಿದರೆ ಕಾಣುವ ಪಠ್ಯವನ್ನು notes ನಲ್ಲಿ ಬರೆಯಿರಿ.",
  },
};

const STATIC_TEXT = {
  hi: {
    "Dashboard": "डैशबोर्ड",
    "Chatbot": "चैटबॉट",
    "Identifier": "पहचान",
    "Analyzer": "फोटो विश्लेषक",
    "Checklist": "चेकलिस्ट",
    "Symptoms": "लक्षण",
    "Emergency": "आपातकाल",
    "Hospital": "अस्पताल",
    "Welcome to PestiSafe AI": "PestiSafe AI में आपका स्वागत है",
    "Select a tool below to get started with pesticide safety, identification, and emergency assistance.": "कीटनाशक सुरक्षा, पहचान और आपात मदद के लिए नीचे एक टूल चुनें।",
    "PestiSafe AI Chatbot": "PestiSafe AI सहायक",
    "Ask questions and get instant AI guidance on pesticide exposure and safety.": "कीटनाशक संपर्क और सुरक्षा पर सवाल पूछें और तुरंत AI मार्गदर्शन पाएं।",
    "Chemical Identifier": "रसायन पहचान",
    "Enter a chemical name to quickly check symptoms, precautions, and first aid steps.": "लक्षण, सावधानियां और प्राथमिक उपचार देखने के लिए रसायन का नाम डालें।",
    "Photo Analyzer": "फोटो विश्लेषक",
    "Upload a photo of a pesticide label to extract safety warnings and details.": "सुरक्षा चेतावनी और जानकारी निकालने के लिए कीटनाशक लेबल की फोटो अपलोड करें।",
    "Decontamination": "डी-कंटैमिनेशन",
    "Follow step-by-step instructions to safely wash off chemicals.": "रसायन को सुरक्षित रूप से धोने के लिए चरण-दर-चरण निर्देश अपनाएं।",
    "Symptom Checker": "लक्षण जांच",
    "Select your symptoms to determine if you need immediate medical help.": "तुरंत मेडिकल मदद चाहिए या नहीं, यह जानने के लिए लक्षण चुनें।",
    "Emergency Alert": "आपात मदद",
    "Hospital Finder": "अस्पताल खोजें",
    "Find the nearest hospital or poison control center on the map.": "मैप पर नजदीकी अस्पताल या विष नियंत्रण केंद्र खोजें।",
    "Ask naturally by text or voice. The answer stays focused on what you said.": "टेक्स्ट या आवाज से स्वाभाविक रूप से पूछें। जवाब आपकी बात पर ही केंद्रित रहेगा।",
    "Tell me the pesticide name, how exposure happened, and symptoms. I will guide the next step.": "कीटनाशक का नाम, संपर्क कैसे हुआ और लक्षण बताइए। मैं अगला कदम बताऊंगा।",
    "Pesticide Photo Analyzer": "कीटनाशक फोटो विश्लेषक",
    "Upload a clear pesticide label. If OCR misses text, type the visible product name or active ingredient.": "कीटनाशक लेबल की साफ फोटो अपलोड करें। OCR छूटे तो उत्पाद नाम या active ingredient लिखें।",
    "Analyze photo": "फोटो विश्लेषण",
    "Image analysis result will appear here.": "फोटो विश्लेषण यहां दिखेगा।",
    "Emergency Help": "आपात मदद",
    "Create emergency guidance with chemical, symptoms, and location. Use the call buttons for urgent help.": "रसायन, लक्षण और स्थान के साथ आपात मार्गदर्शन बनाएं। तुरंत मदद के लिए कॉल बटन इस्तेमाल करें।",
    "Use location": "स्थान लें",
    "Call 112": "112 कॉल करें",
    "Call poison helpline": "विष हेल्पलाइन कॉल करें",
    "Nearby Hospital Finder": "नजदीकी अस्पताल खोजें",
    "Nearest hospital": "नजदीकी अस्पताल",
    "Poison control center": "विष नियंत्रण केंद्र",
    "Call 1800-116-117": "1800-116-117 कॉल करें",
  },
  kn: {
    "Dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
    "Chatbot": "ಚಾಟ್‌ಬಾಟ್",
    "Identifier": "ಗುರುತು",
    "Analyzer": "ಫೋಟೋ ವಿಶ್ಲೇಷಕ",
    "Checklist": "ಚೆಕ್‌ಲಿಸ್ಟ್",
    "Symptoms": "ಲಕ್ಷಣಗಳು",
    "Emergency": "ತುರ್ತು",
    "Hospital": "ಆಸ್ಪತ್ರೆ",
    "Welcome to PestiSafe AI": "PestiSafe AI ಗೆ ಸ್ವಾಗತ",
    "Select a tool below to get started with pesticide safety, identification, and emergency assistance.": "ಕೀಟನಾಶಕ ಸುರಕ್ಷತೆ, ಗುರುತಿಸುವಿಕೆ ಮತ್ತು ತುರ್ತು ಸಹಾಯಕ್ಕಾಗಿ ಕೆಳಗಿನ ಟೂಲ್ ಆಯ್ಕೆಮಾಡಿ.",
    "PestiSafe AI Chatbot": "PestiSafe AI ಸಹಾಯಕ",
    "Ask questions and get instant AI guidance on pesticide exposure and safety.": "ಕೀಟನಾಶಕ ಸಂಪರ್ಕ ಮತ್ತು ಸುರಕ್ಷತೆ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ, ತಕ್ಷಣ AI ಮಾರ್ಗದರ್ಶನ ಪಡೆಯಿರಿ.",
    "Chemical Identifier": "ರಾಸಾಯನಿಕ ಗುರುತು",
    "Enter a chemical name to quickly check symptoms, precautions, and first aid steps.": "ಲಕ್ಷಣಗಳು, ಮುನ್ನೆಚ್ಚರಿಕೆಗಳು ಮತ್ತು ಮೊದಲ ನೆರವು ನೋಡಲು ರಾಸಾಯನಿಕದ ಹೆಸರು ನಮೂದಿಸಿ.",
    "Photo Analyzer": "ಫೋಟೋ ವಿಶ್ಲೇಷಕ",
    "Upload a photo of a pesticide label to extract safety warnings and details.": "ಸುರಕ್ಷತಾ ಎಚ್ಚರಿಕೆಗಳು ಮತ್ತು ವಿವರಗಳನ್ನು ಪಡೆಯಲು ಕೀಟನಾಶಕ ಲೇಬಲ್ ಫೋಟೋ ಅಪ್ಲೋಡ್ ಮಾಡಿ.",
    "Decontamination": "ಡೀಕಂಟಾಮಿನೇಶನ್",
    "Follow step-by-step instructions to safely wash off chemicals.": "ರಾಸಾಯನಿಕವನ್ನು ಸುರಕ್ಷಿತವಾಗಿ ತೊಳೆಯಲು ಹಂತ ಹಂತದ ಸೂಚನೆಗಳನ್ನು ಅನುಸರಿಸಿ.",
    "Symptom Checker": "ಲಕ್ಷಣ ಪರಿಶೀಲನೆ",
    "Select your symptoms to determine if you need immediate medical help.": "ತಕ್ಷಣ ವೈದ್ಯಕೀಯ ಸಹಾಯ ಬೇಕೇ ಎಂದು ತಿಳಿಯಲು ಲಕ್ಷಣಗಳನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
    "Emergency Alert": "ತುರ್ತು ಸಹಾಯ",
    "Hospital Finder": "ಆಸ್ಪತ್ರೆ ಹುಡುಕಿ",
    "Find the nearest hospital or poison control center on the map.": "ಮ್ಯಾಪ್‌ನಲ್ಲಿ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಅಥವಾ ವಿಷ ನಿಯಂತ್ರಣ ಕೇಂದ್ರ ಹುಡುಕಿ.",
    "Ask naturally by text or voice. The answer stays focused on what you said.": "ಟೆಕ್ಸ್ಟ್ ಅಥವಾ ಧ್ವನಿಯಿಂದ ಸಹಜವಾಗಿ ಕೇಳಿ. ಉತ್ತರ ನಿಮ್ಮ ಮಾತಿನ ಮೇಲೆಯೇ ಕೇಂದ್ರೀಕರಿಸುತ್ತದೆ.",
    "Tell me the pesticide name, how exposure happened, and symptoms. I will guide the next step.": "ಕೀಟನಾಶಕದ ಹೆಸರು, ಸಂಪರ್ಕ ಹೇಗೆ ಆಯಿತು ಮತ್ತು ಲಕ್ಷಣಗಳನ್ನು ಹೇಳಿ. ಮುಂದಿನ ಹಂತವನ್ನು ಹೇಳುತ್ತೇನೆ.",
    "Pesticide Photo Analyzer": "ಕೀಟನಾಶಕ ಫೋಟೋ ವಿಶ್ಲೇಷಕ",
    "Upload a clear pesticide label. If OCR misses text, type the visible product name or active ingredient.": "ಸ್ಪಷ್ಟ ಕೀಟನಾಶಕ ಲೇಬಲ್ ಫೋಟೋ ಅಪ್ಲೋಡ್ ಮಾಡಿ. OCR ತಪ್ಪಿದರೆ ಉತ್ಪನ್ನದ ಹೆಸರು ಅಥವಾ active ingredient ಬರೆಯಿರಿ.",
    "Analyze photo": "ಫೋಟೋ ವಿಶ್ಲೇಷಿಸಿ",
    "Image analysis result will appear here.": "ಫೋಟೋ ವಿಶ್ಲೇಷಣೆ ಇಲ್ಲಿ ಕಾಣುತ್ತದೆ.",
    "Emergency Help": "ತುರ್ತು ಸಹಾಯ",
    "Create emergency guidance with chemical, symptoms, and location. Use the call buttons for urgent help.": "ರಾಸಾಯನಿಕ, ಲಕ್ಷಣಗಳು ಮತ್ತು ಸ್ಥಳದೊಂದಿಗೆ ತುರ್ತು ಮಾರ್ಗದರ್ಶನ ರಚಿಸಿ. ತುರ್ತು ಸಹಾಯಕ್ಕೆ ಕರೆ ಬಟನ್ ಬಳಸಿ.",
    "Use location": "ಸ್ಥಳ ಬಳಸಿ",
    "Call 112": "112 ಕರೆ ಮಾಡಿ",
    "Call poison helpline": "ವಿಷ ಸಹಾಯವಾಣಿಗೆ ಕರೆ ಮಾಡಿ",
    "Nearby Hospital Finder": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಹುಡುಕಿ",
    "Nearest hospital": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ",
    "Poison control center": "ವಿಷ ನಿಯಂತ್ರಣ ಕೇಂದ್ರ",
    "Call 1800-116-117": "1800-116-117 ಕರೆ ಮಾಡಿ",
  },
};

document.addEventListener("DOMContentLoaded", init);

function init() {
  if (el.languageSelect) {
    el.languageSelect.value = localStorage.getItem("agriaiLanguage") || "auto";
    el.languageSelect.addEventListener("change", () => {
      localStorage.setItem("agriaiLanguage", el.languageSelect.value);
      applyLanguage();
    });
  }

  bindEvents();
  setupSpeechRecognition();
  applyLanguage();
  if (el.checklist) loadChecklist("skin");
}

function bindEvents() {
  on(el.lookupBtn, "click", lookupChemical);
  on(el.chemicalInput, "keydown", (event) => {
    if (event.key === "Enter" && el.lookupBtn) lookupChemical();
  });
  on(el.symptomBtn, "click", analyzeSymptoms);
  on(el.locationBtn, "click", useLocation);
  on(el.chatBtn, "click", sendChat);
  on(el.chatInput, "input", () => updateAutoLanguageFromText(el.chatInput.value));
  on(el.chatInput, "keydown", (event) => {
    if (event.key === "Enter") sendChat();
  });
  on(el.micBtn, "click", startVoiceInput);
  on(el.recordBtn, "click", toggleRecording);
  on(el.voiceToggleBtn, "click", toggleVoiceReply);
  on(el.imageInput, "change", previewImage);
  on(el.imageAnalyzeBtn, "click", analyzeImage);

  $$(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".segment").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      loadChecklist(button.dataset.exposure || "skin");
    });
  });
}

function on(node, eventName, handler) {
  if (node) node.addEventListener(eventName, handler);
}

function currentLanguage() {
  return el.languageSelect?.value || "auto";
}

function uiLanguage() {
  const selected = currentLanguage();
  return selected === "auto" ? state.detectedAutoLanguage : selected;
}

function applyLanguage() {
  const lang = uiLanguage();
  const text = UI_TEXT[lang] || UI_TEXT.en;
  document.documentElement.lang = lang;
  translateStaticText(lang);

  const languageControl = $(".language-control");
  if (languageControl?.firstChild) languageControl.firstChild.textContent = `${text.language} `;
  const helpline = $(".helpline");
  if (helpline) helpline.textContent = text.helpline;
  if (el.micBtn) el.micBtn.textContent = text.voiceInput;
  if (el.recordBtn && mediaRecorder?.state !== "recording") el.recordBtn.textContent = text.recordVoice;
  if (el.voiceToggleBtn) {
    el.voiceToggleBtn.textContent = state.voiceEnabled ? text.voiceOn : text.voiceOff;
    el.voiceToggleBtn.classList.toggle("off", !state.voiceEnabled);
    el.voiceToggleBtn.setAttribute("aria-pressed", String(state.voiceEnabled));
  }
  if (el.selectedLanguageStatus) {
    el.selectedLanguageStatus.textContent = currentLanguage() === "auto" ? `Auto: ${text.selectedLanguage}` : text.selectedLanguage;
  }
  if (el.voiceStatus && !el.voiceStatus.dataset.locked) el.voiceStatus.textContent = text.voiceReady;
  if (el.chatBtn) el.chatBtn.textContent = text.send;
  if (el.imageResult?.classList.contains("muted")) el.imageResult.textContent = text.imageDefault;
}

function translateStaticText(lang) {
  const dictionary = STATIC_TEXT[lang] || {};
  $$("h2, h3, p, a.nav-tab, a.button-link, button.dashboard-card .card-title, .dashboard-card p, .bot.bubble").forEach((node) => {
    const original = node.dataset.i18nSource || node.textContent.trim();
    node.dataset.i18nSource = original;
    node.textContent = lang === "en" ? original : (dictionary[original] || original);
  });
  $$("button, a").forEach((node) => {
    const original = node.dataset.i18nSource || node.textContent.trim();
    node.dataset.i18nSource = original;
    node.textContent = lang === "en" ? original : (dictionary[original] || original);
  });
}

function updateAutoLanguageFromText(text) {
  if (currentLanguage() !== "auto") return;
  if (containsKannada(text)) state.detectedAutoLanguage = "kn";
  else if (containsDevanagari(text)) state.detectedAutoLanguage = "hi";
  else state.detectedAutoLanguage = "en";
  applyLanguage();
}

function selectedSymptoms() {
  const checked = $$(".symptom-grid input:checked").map((input) => input.value);
  if (el.symptomText?.value.trim()) checked.push(el.symptomText.value.trim());
  return checked;
}

function dangerClass(level = "") {
  if (["Extreme", "High", "Emergency"].includes(level)) return "danger";
  if (String(level).includes("Moderate") || level === "High concern") return "warning";
  return "safe";
}

async function lookupChemical() {
  const name = el.chemicalInput?.value.trim();
  if (!name) return setResult(el.chemicalResult, "Enter the chemical name first.", true);
  try {
    const response = await fetch(`/api/chemical?name=${encodeURIComponent(name)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Chemical not found.");
    const chemical = data.chemical;
    el.chemicalResult.className = "result-box";
    el.chemicalResult.innerHTML = `
      <strong>${escapeHtml(chemical.name)}</strong>
      <div>Category: ${escapeHtml(chemical.category || "Unknown")}</div>
      <div>Common symptoms: ${escapeHtml((chemical.symptoms || []).join(", ") || "Unknown")}</div>
      <div>First aid: ${escapeHtml(chemical.first_aid || "Seek medical advice if symptoms appear.")}</div>
    `;
  } catch (error) {
    setResult(el.chemicalResult, error.message, true);
  }
}

async function loadChecklist(type = "skin") {
  if (!el.checklist) return;
  try {
    const response = await fetch(`/api/decontamination?type=${encodeURIComponent(type)}`);
    const data = await response.json();
    el.checklist.innerHTML = data.steps.map((step) => `<li><strong>${escapeHtml(step.title)}</strong><span>${escapeHtml(step.detail)}</span></li>`).join("");
  } catch {
    el.checklist.innerHTML = "<li>Could not load checklist.</li>";
  }
}

async function analyzeSymptoms() {
  const symptoms = selectedSymptoms();
  if (!symptoms.length) return setResult(el.symptomResult, "Select or type at least one symptom.", true);
  try {
    const response = await fetch("/api/symptoms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chemical: el.chemicalInput?.value || "", symptoms }),
    });
    const data = await response.json();
    el.symptomResult.className = "result-box";
    el.symptomResult.innerHTML = `
      <strong>Safety guidance</strong>
      <div>${escapeHtml(data.action)}</div>
      <div class="muted">Matched symptoms: ${escapeHtml((data.matched_symptoms || []).join(", ") || "none from high-risk list")}</div>
    `;
  } catch (error) {
    setResult(el.symptomResult, error.message, true);
  }
}

function useLocation() {
  if (!navigator.geolocation) {
    selectedLocation = "GPS not supported";
    return;
  }
  if (el.locationBtn) el.locationBtn.textContent = "Finding location...";
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const { latitude, longitude } = position.coords;
      selectedLocation = `https://www.google.com/maps?q=${latitude},${longitude}`;
      if (el.hospitalLink) el.hospitalLink.href = `https://www.google.com/maps/search/${encodeURIComponent(`${latitude},${longitude} nearest hospital`)}`;
      if (el.locationBtn) el.locationBtn.textContent = "Location added";
    },
    () => {
      selectedLocation = "Location permission denied";
      if (el.locationBtn) el.locationBtn.textContent = "Use location";
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function addMessage(text, type) {
  const bubble = document.createElement("div");
  bubble.className = `${type} bubble`;
  bubble.textContent = text;
  el.chatLog.appendChild(bubble);
  el.chatLog.scrollTop = el.chatLog.scrollHeight;
  return bubble;
}

async function sendChat() {
  const message = el.chatInput?.value.trim();
  if (!message || !el.chatLog) return;
  updateAutoLanguageFromText(message);

  addMessage(message, "user");
  state.chatHistory.push({ role: "user", content: message });
  el.chatInput.value = "";
  el.chatBtn.disabled = true;
  el.chatBtn.textContent = "Sending...";
  const pending = addMessage("Thinking...", "bot");

  try {
    await streamChat(message, pending);
  } catch {
    await fallbackChat(message, pending);
  } finally {
    el.chatBtn.disabled = false;
    applyLanguage();
    state.chatHistory.push({ role: "assistant", content: pending.textContent });
    speakText(pending.textContent);
  }
}

async function streamChat(message, bubble) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch("/api/chat-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        message,
        chemical: el.chemicalInput?.value || "",
        symptoms: "",
        history: state.chatHistory.slice(-8),
        language: currentLanguage(),
      }),
    });
    if (!response.ok || !response.body) throw new Error("stream unavailable");
    bubble.textContent = "";
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
        const payload = line.slice(6);
        if (payload === "[DONE]") continue;
        try {
          bubble.textContent += JSON.parse(payload).token || "";
        } catch {
          bubble.textContent += payload;
        }
        el.chatLog.scrollTop = el.chatLog.scrollHeight;
      }
    }
    if (!bubble.textContent.trim()) throw new Error("empty stream");
  } finally {
    clearTimeout(timeout);
  }
}

async function fallbackChat(message, bubble) {
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        chemical: el.chemicalInput?.value || "",
        symptoms: "",
        history: state.chatHistory.slice(-8),
        language: currentLanguage(),
      }),
    });
    const data = await response.json();
    bubble.textContent = data.reply || "I could not create a reply. Please try again with the pesticide name and what happened.";
  } catch {
    bubble.textContent = "I could not reach the AI model. Tell me the pesticide name and symptoms, and for urgent symptoms call 112 or 1800-116-117.";
  }
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition || !el.micBtn) {
    if (el.voiceStatus) el.voiceStatus.textContent = "Browser voice input is not supported here. Use Record voice or type.";
    if (el.micBtn) el.micBtn.disabled = true;
    return;
  }
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 3;
  recognition.onstart = () => {
    state.voiceListening = true;
    el.micBtn.classList.add("listening");
    el.micBtn.textContent = "Stop listening";
    stopSpeaking();
    lockVoiceStatus("Speak now.");
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0]?.[0]?.transcript || "";
    if (!transcript.trim()) return;
    if (el.chatInput) {
      el.chatInput.value = transcript;
      el.chatInput.focus();
    }
    updateAutoLanguageFromText(transcript);
    lockVoiceStatus(`${(UI_TEXT[uiLanguage()] || UI_TEXT.en).voiceEdit} Heard: ${transcript}`);
    if (state.voiceAutoSend) sendChat();
  };
  recognition.onerror = (event) => lockVoiceStatus(`Voice input failed${event?.error ? `: ${event.error}` : ""}. Please try again or type.`);
  recognition.onend = () => {
    state.voiceListening = false;
    el.micBtn.classList.remove("listening");
    applyLanguage();
  };
}

function startVoiceInput() {
  if (!recognition) return;
  if (state.voiceListening) {
    recognition.stop();
    return;
  }
  recognition.lang = speechLang();
  try {
    recognition.start();
  } catch {
    lockVoiceStatus("Voice input is already active. Speak now.");
  }
}

async function toggleRecording() {
  if (mediaRecorder?.state === "recording") {
    mediaRecorder.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return lockVoiceStatus("Recording is not supported in this browser.");
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
      el.recordBtn.classList.remove("recording");
      applyLanguage();
      await transcribeRecording();
    };
    mediaRecorder.start();
    el.recordBtn.textContent = "Stop recording";
    el.recordBtn.classList.add("recording");
    lockVoiceStatus("Recording... speak now.");
  } catch {
    lockVoiceStatus("Microphone permission denied or unavailable.");
  }
}

async function transcribeRecording() {
  const formData = new FormData();
  formData.append("audio", new Blob(recordedChunks, { type: "audio/webm" }), "voice.webm");
  formData.append("language", currentLanguage());
  lockVoiceStatus("Converting voice to text...");
  try {
    const response = await fetch("/api/speech-to-text", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok || !data.text) throw new Error(data.error || "No speech detected.");
    el.chatInput.value = data.text;
    updateAutoLanguageFromText(data.text);
    lockVoiceStatus(`${(UI_TEXT[uiLanguage()] || UI_TEXT.en).voiceEdit} Heard: ${data.text}`);
    if (state.voiceAutoSend) sendChat();
  } catch (error) {
    lockVoiceStatus(error.message || "Server voice recognition is unavailable. Try browser Voice input or type.");
  }
}

function toggleVoiceReply() {
  state.voiceEnabled = !state.voiceEnabled;
  localStorage.setItem("agriaiVoiceEnabled", String(state.voiceEnabled));
  if (!state.voiceEnabled) stopSpeaking();
  applyLanguage();
}

function speakText(text) {
  if (!state.voiceEnabled || !text) return;
  const lang = uiLanguage();
  if (lang === "kn" || lang === "hi") {
    speakWithServerTTS(text, true);
    return;
  }
  if (!("speechSynthesis" in window)) return speakWithServerTTS(text, false);
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = speechLang(text);
  const voice = chooseVoice(utterance.lang);
  if (voice) utterance.voice = voice;
  utterance.rate = 0.95;
  utterance.onerror = () => speakWithServerTTS(text, false);
  window.speechSynthesis.speak(utterance);
  lockVoiceStatus(`Speaking in ${utterance.lang}.`);
}

async function speakWithServerTTS(text, fallbackToBrowser = true) {
  if (!state.voiceEnabled) return;
  try {
    const response = await fetch("/api/text-to-speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: uiLanguage() }),
    });
    if (!response.ok) return;
    const data = await response.json();
    if (!data.audio_base64) return;
    if (fallbackAudio) fallbackAudio.pause();
    fallbackAudio = new Audio(`data:${data.mime_type};base64,${data.audio_base64}`);
    fallbackAudio.play();
    lockVoiceStatus(`Speaking in ${data.language}.`);
  } catch {
    if (fallbackToBrowser && "speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = speechLang(text);
      const voice = chooseVoice(utterance.lang);
      if (voice) utterance.voice = voice;
      utterance.rate = 0.9;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
      lockVoiceStatus(`Browser voice fallback in ${utterance.lang}.`);
      return;
    }
    lockVoiceStatus("Voice output is unavailable in this browser.");
  }
}

function stopSpeaking() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  if (fallbackAudio) {
    fallbackAudio.pause();
    fallbackAudio.currentTime = 0;
  }
}

function speechLang(text = "") {
  const selected = currentLanguage();
  if (selected === "kn" || containsKannada(text)) return "kn-IN";
  if (selected === "hi" || containsDevanagari(text)) return "hi-IN";
  return "en-IN";
}

function chooseVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((voice) => voice.lang === lang)
    || voices.find((voice) => voice.lang.toLowerCase().startsWith(lang.slice(0, 2).toLowerCase()))
    || voices[0];
}

function previewImage() {
  const file = el.imageInput?.files?.[0];
  if (!file || !el.imagePreview) return;
  el.imagePreview.src = URL.createObjectURL(file);
}

async function analyzeImage() {
  const file = el.imageInput?.files?.[0];
  const text = UI_TEXT[uiLanguage()] || UI_TEXT.en;
  if (!file) return setResult(el.imageResult, text.noImage, true);
  el.imageAnalyzeBtn.disabled = true;
  el.imageAnalyzeBtn.textContent = text.analyzing;
  setResult(el.imageResult, text.analyzing);

  const formData = new FormData();
  formData.append("image", file);
  formData.append("language", currentLanguage());

  try {
    const browserOcrText = await runBrowserOCR(file);
    if (browserOcrText) formData.append("client_ocr_text", browserOcrText);
    const response = await fetch("/api/analyze-image", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok && data?.details) {
      el.imageResult.className = "result-box";
      el.imageResult.innerHTML = renderImageAnalysis(data);
      return;
    }
    if (!response.ok) throw new Error(data.reply || data.error || "Image analysis failed.");
    el.imageResult.className = "result-box";
    el.imageResult.innerHTML = renderImageAnalysis(data);
    speakText(data.reply || "");
  } catch (error) {
    setResult(el.imageResult, error.message, true);
  } finally {
    el.imageAnalyzeBtn.disabled = false;
    el.imageAnalyzeBtn.textContent = "Analyze photo";
    applyLanguage();
  }
}

async function runBrowserOCR(file) {
  if (!window.Tesseract?.recognize) return "";
  try {
    lockImageStatus("Reading label text from image...");
    const result = await window.Tesseract.recognize(file, "eng", {
      logger: (message) => {
        if (message?.status === "recognizing text" && typeof message.progress === "number") {
          lockImageStatus(`Reading label text... ${Math.round(message.progress * 100)}%`);
        }
      },
    });
    return (result?.data?.text || "").trim();
  } catch {
    return "";
  }
}

function lockImageStatus(message) {
  if (el.imageResult) setResult(el.imageResult, message);
}

function renderImageAnalysis(data) {
  const text = UI_TEXT[uiLanguage()] || UI_TEXT.en;
  const details = data.details || {};
  const items = [
    ["Product name from label", details.product_name],
    ["Detected pesticide/chemical", details.pesticide_name],
    ["Active ingredients", (details.active_ingredients || []).join(", ")],
    ["Usage", details.usage],
    ["First aid", details.first_aid],
    ["Side effects", (details.side_effects || []).join(", ")],
    ["Safety precautions", (details.safety_precautions || []).join("; ")],
    ["Decontamination", (details.decontamination_steps || []).join("; ")],
    ["Environmental impact", details.environmental_impact],
  ];
  return `
    <div class="analysis-header">
      <strong>${escapeHtml(text.imageAnalysis)}</strong>
    </div>
    <pre>${escapeHtml(data.reply || "")}</pre>
    <div class="analysis-list">
      ${items.map(([label, value]) => `<div><b>${escapeHtml(label)}:</b> ${escapeHtml(value || "Unknown")}</div>`).join("")}
    </div>
    <details>
      <summary>OCR details</summary>
      <div><b>Engines:</b> ${escapeHtml((data.ocr_engines || []).join(", ") || "None available")}</div>
      <pre>${escapeHtml(data.analyzed_text || data.ocr_text || "No text extracted")}</pre>
      ${(data.ocr_errors || []).length ? `<pre>${escapeHtml(data.ocr_errors.join("\n"))}</pre>` : ""}
    </details>
  `;
}

function lockVoiceStatus(message) {
  if (!el.voiceStatus) return;
  el.voiceStatus.dataset.locked = "1";
  el.voiceStatus.textContent = message;
  setTimeout(() => {
    if (el.voiceStatus) delete el.voiceStatus.dataset.locked;
  }, 3500);
}

function setResult(node, message, isError = false) {
  if (!node) return;
  node.className = `result-box ${isError ? "error" : "muted"}`;
  node.textContent = message;
}

function containsKannada(text) {
  return /[\u0c80-\u0cff]/.test(text || "");
}

function containsDevanagari(text) {
  return /[\u0900-\u097f]/.test(text || "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
