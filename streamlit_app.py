from __future__ import annotations

import requests
import streamlit as st


API_BASE = st.sidebar.text_input("Flask API URL", "http://127.0.0.1:5000")
LANGUAGE = st.sidebar.selectbox("Language", ["auto", "en", "hi", "kn"], index=0)

st.set_page_config(page_title="AgriAI", page_icon="AI", layout="wide")
st.title("AgriAI pesticide safety assistant")
st.caption("Streamlit companion UI for the existing Flask backend.")


def post_json(path: str, payload: dict):
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


tab_chat, tab_image = st.tabs(["Chatbot", "Pesticide image analysis"])

with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_message = st.chat_input("Ask about pesticide safety, symptoms, first aid, or farming help")
    if user_message:
        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            st.write(user_message)

        with st.chat_message("assistant"):
            with st.spinner("AgriAI is thinking..."):
                data = post_json(
                    "/api/chat",
                    {
                        "message": user_message,
                        "language": LANGUAGE,
                        "history": st.session_state.messages[-8:],
                    },
                )
                reply = data.get("reply", "No reply returned.")
                st.write(reply)
                st.caption(f"Model: {data.get('model', 'unknown')}")
        st.session_state.messages.append({"role": "assistant", "content": reply})

with tab_image:
    image = st.file_uploader("Upload pesticide label image", type=["png", "jpg", "jpeg", "webp"])
    notes = st.text_area("Optional visible label text")
    if st.button("Analyze image", disabled=image is None):
        with st.spinner("Running OCR and pesticide matching..."):
            files = {"image": (image.name, image.getvalue(), image.type)}
            data = {"language": LANGUAGE, "notes": notes}
            response = requests.post(f"{API_BASE}/api/analyze-image", files=files, data=data, timeout=180)
            response.raise_for_status()
            result = response.json()

        st.subheader("Safety report")
        st.write(result.get("reply", "No analysis returned."))
        details = result.get("details", {})
        if details:
            st.json(details)
        with st.expander("OCR text"):
            st.write(result.get("ocr_text", "No text extracted."))
            st.write("Engines:", ", ".join(result.get("ocr_engines", [])) or "None")
