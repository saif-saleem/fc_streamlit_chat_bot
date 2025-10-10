import streamlit as st
from app.rag_chat import get_answer
import base64

# ============ Logo ============
with open("app/assets/flora_carbon_logo.png", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

st.set_page_config(page_title="Flora Carbon GPT", layout="centered")

# ============ Styling ============
st.markdown("""
<style>
/* Overall ChatGPT-like dark theme */
.stApp {
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Inter", sans-serif;
}

/* Title */
h1 {
    color: #ffffff !important;
    text-align: center;
    margin-bottom: 1rem;
    font-weight: 700;
}

/* Chat container */
.chat-container {
    max-width: 800px;
    margin: auto;
    padding: 1rem;
}

/* Chat bubbles */
.user-bubble {
    background-color: #343541;
    border-radius: 12px;
    padding: 12px 18px;
    margin: 8px 0;
    color: #fff;
    text-align: right;
}

.bot-bubble {
    background-color: #444654;
    border-radius: 12px;
    padding: 15px 20px;
    margin: 8px 0;
    color: #e6e6e6;
    text-align: left;
}

/* Input box */
div[data-baseweb="input"] > div {
    background-color: #1a1a1a !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 8px;
    color: #fff !important;
    padding: 0.6rem 0.8rem !important;
    width: 100%;
}

/* Buttons container BELOW input */
.button-row {
    display: flex;
    justify-content: space-between;  /* Push buttons to extreme ends */
    align-items: center;
    max-width: 800px;
    margin: 1rem auto 0 auto;
   
}

/* Modern realistic buttons */
div.stButton > button {
    background: linear-gradient(180deg, #fdfdfd, #dcdcdc);
    color: #000;
    border-radius: 20px;
    font-weight: 500;
    border: 1px solid #c0c0c0;
 
    min-width: 110px;
    box-shadow: 0 3px 6px rgba(255, 255, 255, 0.05), 0 3px 8px rgba(0, 0, 0, 0.25);
    transition: all 0.2s ease-in-out;
}

/* Hover and press effects */
div.stButton > button:hover {
    background: linear-gradient(180deg, #f5f5f5, #e5e5e5);
    box-shadow: 0 4px 10px rgba(255, 255, 255, 0.1), 0 4px 10px rgba(0, 0, 0, 0.35);
    transform: translateY(-1px);
}

div.stButton > button:active {
    background: linear-gradient(180deg, #e5e5e5, #d5d5d5);
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
    transform: translateY(1px);
}

/* Hide Streamlit defaults */
header {visibility: hidden;}
footer {visibility: hidden;}
#MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============ Session Defaults ============
defaults = {
    "chat_history": [],
    "main_query": "",
    "selected_standard": None,
    "ask_standard": False,
    "pending_query": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============ Header ============
st.markdown(f"""
<div style="display: flex; justify-content: center; align-items: center; flex-direction: column; margin-bottom: 1.5rem;">
    <img src="data:image/png;base64,{img_base64}" 
         style="width: 120px; height: auto; margin-bottom: 1rem; border-radius: 12px;">
</div>
""", unsafe_allow_html=True)

# ============ Chat Area ============
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
for etype, entry in st.session_state.chat_history:
    if etype == "question":
        st.markdown(f"<div class='user-bubble'>🧑 {entry}</div>", unsafe_allow_html=True)
    elif etype == "answer":
        if isinstance(entry, dict):
            st.markdown(f"<div class='bot-bubble'>🤖 {entry.get('answer', 'No answer.')}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='bot-bubble'>🤖 {str(entry)}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ============ Input Box ============
st.session_state.main_query = st.text_input(
    "Ask me anything about carbon standards...",
    value=st.session_state.main_query
)

# ============ Buttons Below Input (Perfectly Aligned Extremes) ============
st.markdown("<div class='button-row'>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 4, 1])  # spacing ratio

with col1:
    if st.button("New Chat", key="new_chat"):
        for k in defaults:
            st.session_state[k] = defaults[k]
        st.rerun()

with col3:
    if st.button("Send", key="send_button") and st.session_state.main_query:
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
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# ============ Standard Chooser ============
if st.session_state.ask_standard:
    st.warning("👉 Please choose a standard for this query:")
    cols = st.columns(5)
    buttons = [
        ("GS", "gs"),
        ("VCS", "vcs"),
        ("ICR", "icr"),
        ("PLAN_VIVO", "plan_vivo"),
        ("OTHER", "other")
    ]
    for i, (label, val) in enumerate(buttons):
        if cols[i].button(label):
            st.session_state.selected_standard = val
            st.session_state.ask_standard = False
            with st.spinner(f"⚡ Generating an accurate answer using {label} may take a few moments..."):
                res = get_answer(query=st.session_state.pending_query, selected_standard=val)
            st.session_state.chat_history.append(("question", f"{st.session_state.pending_query} ({label})"))
            st.session_state.chat_history.append(("answer", res))
            st.session_state.pending_query = None
            st.rerun()
