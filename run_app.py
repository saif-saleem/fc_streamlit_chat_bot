import streamlit as st
from app.rag_chat import get_answer
import base64
import os

# Logo
with open("app/assets/flora_carbon_logo.png", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

st.set_page_config(page_title="Flora Carbon GPT", layout="wide")

# ==== Dark Theme Styling ====
st.markdown("""
<style>
/* Global background */
body, .stApp {
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: 'Segoe UI', sans-serif;
}

/* Title Styling */
h1, h2, h3 {
    color: #00f5c8 !important;
    font-weight: 600;
}

/* Chat bubbles */
.user-bubble {
    background-color: #1a1a1a;
    border-radius: 12px;
    padding: 12px 18px;
    margin: 8px 0;
    color: #ffffff;
    border: 1px solid #333;
}
.bot-bubble {
    background: linear-gradient(135deg, #111111, #1e1e1e);
    border-radius: 12px;
    padding: 15px 20px;
    margin: 8px 0;
    color: #e6e6e6;
    border-left: 4px solid #00f5c8;
    box-shadow: 0px 0px 12px rgba(0, 245, 200, 0.2);
}

/* Buttons */
div.stButton > button {
    background: linear-gradient(135deg, #1a1a1a, #333333);
    color: #00f5c8;
    border: 1px solid #00f5c8;
    border-radius: 8px;
    font-weight: bold;
    transition: all 0.2s ease-in-out;
}
div.stButton > button:hover {
    background: #00f5c8;
    color: #0d0d0d;
}

/* Text Input */
input[type="text"] {
    background-color: #1a1a1a !important;
    color: #f0f0f0 !important;
    border: 1px solid #00f5c8 !important;
    border-radius: 6px;
    padding: 10px;
}

/* Warning Box */
.stAlert {
    background-color: #1a1a1a;
    border-left: 5px solid #ff4b4b;
    color: #ffcccc;
}
</style>
""", unsafe_allow_html=True)

# ==== App Defaults ====
defaults = {"chat_history": [], "main_query": "", "selected_standard": None, "ask_standard": False, "pending_query": None}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Reset chat
if st.button("🆕 New Chat"):
    for k in defaults:
        st.session_state[k] = defaults[k]
    st.rerun()

# ==== Header ====
st.markdown(f"""
<div style="display:flex;align-items:center;gap:1em;">
  <img src="data:image/png;base64,{img_base64}" width="60" style="border-radius:10px;">
  <h1>Flora Carbon GPT</h1>
</div>
""", unsafe_allow_html=True)

# ==== Query Input ====
st.session_state.main_query = st.text_input("🔍 Ask a question:", value=st.session_state.main_query)

if st.button("🔎 Search") and st.session_state.main_query:
    if not st.session_state.selected_standard:
        st.session_state.ask_standard = True
        st.session_state.pending_query = st.session_state.main_query
    else:
        with st.spinner("⚡ Fetching answer..."):
            res = get_answer(query=st.session_state.main_query, selected_standard=st.session_state.selected_standard)
        if res.get("clarification"):
            st.session_state.ask_standard = True
            st.session_state.pending_query = st.session_state.main_query
        else:
            st.session_state.chat_history.append(("question", st.session_state.main_query))
            st.session_state.chat_history.append(("answer", res))
            st.session_state.selected_standard = res.get("standard", st.session_state.selected_standard)

# ==== Standard Chooser ====
if st.session_state.ask_standard:
    st.warning("👉 Please choose a standard for this query:")
    cols = st.columns(5)
    buttons = [("GS", "gs"), ("VCS", "vcs"), ("ICR", "icr"), ("PLAN_VIVO", "plan_vivo"), ("OTHER", "other")]
    for i, (label, val) in enumerate(buttons):
        if cols[i].button(label):
            st.session_state.selected_standard = val
            st.session_state.ask_standard = False
            with st.spinner(f"⚡ Answering using {label}..."):
                res = get_answer(query=st.session_state.pending_query, selected_standard=val)
            st.session_state.chat_history.append(("question", f"{st.session_state.pending_query} ({label})"))
            st.session_state.chat_history.append(("answer", res))
            st.session_state.pending_query = None
            st.rerun()

# ==== Chat Display ====
for etype, entry in st.session_state.chat_history:
    if etype == "question":
        st.markdown(f"<div class='user-bubble'>🧑‍💬 {entry}</div>", unsafe_allow_html=True)
    elif etype == "answer":
        if isinstance(entry, dict):
            st.markdown(f"<div class='bot-bubble'>🌍 {entry.get('answer', 'No answer.')}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='bot-bubble'>🌍 {str(entry)}</div>", unsafe_allow_html=True)
