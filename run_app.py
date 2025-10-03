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
/* Full dark background */
.stApp {
    background-color: #0d0d0d;
    color: #f0f0f0;
    font-family: "Inter", sans-serif;
}

/* Title */
h1 {
    color: #00f5c8 !important;
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
    background-color: #1a1a1a;
    border-radius: 12px;
    padding: 12px 18px;
    margin: 8px 0;
    color: #fff;
    border: 1px solid #333;
    text-align: right;
}

.bot-bubble {
    background: linear-gradient(135deg, #111, #1e1e1e);
    border-radius: 12px;
    padding: 15px 20px;
    margin: 8px 0;
    color: #e6e6e6;
    border-left: 4px solid #00f5c8;
    box-shadow: 0px 0px 12px rgba(0, 245, 200, 0.2);
    text-align: left;
}

/* Input box */
div[data-baseweb="input"] > div {
    background-color: #1a1a1a !important;
    border: 1px solid #00f5c8 !important;
    border-radius: 8px;
    color: #fff !important;
}

/* Buttons */
div.stButton > button {
    background: #00f5c8;
    color: #0d0d0d;
    border-radius: 8px;
    font-weight: bold;
    padding: 8px 18px;
}
div.stButton > button:hover {
    background: #00d3a9;
    color: #fff;
}
/* Hide Streamlit default header & footer */
header {visibility: hidden;}
footer {visibility: hidden;}
#MainMenu {visibility: hidden;}

/* Also hide the deploy button strip */
.css-18e3th9 {visibility: hidden;}  /* main top nav */
.css-1rs6os {visibility: hidden;}  /* deploy button area */
</style>
""", unsafe_allow_html=True)

# ============ Session Defaults ============
defaults = {"chat_history": [], "main_query": "", "selected_standard": None, "ask_standard": False, "pending_query": None}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============ Header ============
# ============ Header with Logo ============
st.markdown(f"""
<div style="display: flex; justify-content: center; align-items: center; flex-direction: column; margin-bottom: 1.5rem;">
    <img src="data:image/png;base64,{img_base64}" 
         style="width: 120px; height: auto; margin-bottom: 1rem; border-radius: 12px;">
    <h1>Flora Carbon GPT</h1>
</div>
""", unsafe_allow_html=True)


# Reset chat
if st.button("🆕 New Chat"):
    for k in defaults:
        st.session_state[k] = defaults[k]
    st.rerun()

# ============ Chat UI ============
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

# Show chat history
for etype, entry in st.session_state.chat_history:
    if etype == "question":
        st.markdown(f"<div class='user-bubble'>🧑 {entry}</div>", unsafe_allow_html=True)
    elif etype == "answer":
        if isinstance(entry, dict):
            st.markdown(f"<div class='bot-bubble'>🤖 {entry.get('answer', 'No answer.')}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='bot-bubble'>🤖 {str(entry)}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ============ Query Input ============
st.session_state.main_query = st.text_input("Ask me anything about carbon standards...", value=st.session_state.main_query)

if st.button("🔎 Send") and st.session_state.main_query:
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

# ============ Standard Chooser ============
if st.session_state.ask_standard:
    st.warning("👉 Please choose a standard for this query:")
    cols = st.columns(5)
    buttons = [("GS", "gs"), ("VCS", "vcs"), ("ICR", "icr"), ("PLAN_VIVO", "plan_vivo"), ("OTHER", "other")]
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
