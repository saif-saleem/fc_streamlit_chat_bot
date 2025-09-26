import streamlit as st
from app.rag_chat import get_answer
import base64
import os

# Logo
with open("app/assets/flora_carbon_logo.png", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

st.set_page_config(page_title="Flora Carbon GPT", layout="wide")

# Styling for Markdown lists
st.markdown("""
<style>
ul, ol {
    margin-left: 1.5em; 
    margin-bottom: 0.5em;
}
li {
    margin-bottom: 0.3em;
}
</style>
""", unsafe_allow_html=True)

defaults = {"chat_history": [], "main_query": "", "selected_standard": None, "ask_standard": False, "pending_query": None}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Reset chat
if st.button("🆕 New Chat"):
    for k in defaults:
        st.session_state[k] = defaults[k]
    st.rerun()

# Header
st.markdown(f"""
<div style="display:flex;align-items:center;gap:1em;">
  <img src="data:image/png;base64,{img_base64}" width="60">
  <h1 style="color:#00f5c8;">Flora Carbon GPT</h1>
</div>
""", unsafe_allow_html=True)

# Query
st.session_state.main_query = st.text_input("🔍 Ask a question:", value=st.session_state.main_query)

if st.button("🔎 Search") and st.session_state.main_query:
    if not st.session_state.selected_standard:
        st.session_state.ask_standard = True
        st.session_state.pending_query = st.session_state.main_query
    else:
        with st.spinner("Fetching answer..."):
            res = get_answer(query=st.session_state.main_query, selected_standard=st.session_state.selected_standard)
        if res.get("clarification"):
            st.session_state.ask_standard = True
            st.session_state.pending_query = st.session_state.main_query
        else:
            st.session_state.chat_history.append(("question", st.session_state.main_query))
            st.session_state.chat_history.append(("answer", res))
            st.session_state.selected_standard = res.get("standard", st.session_state.selected_standard)

# Standard chooser
if st.session_state.ask_standard:
    st.warning("👉 Please choose a standard for this query:")
    cols = st.columns(4)
    buttons = [("VCS", "vcs"), ("ICR", "icr"), ("PLAN_VIVO", "plan_vivo"), ("OTHER", "other")]
    for i, (label, val) in enumerate(buttons):
        if cols[i].button(label):
            st.session_state.selected_standard = val
            st.session_state.ask_standard = False
            with st.spinner(f"Answering using {label}..."):
                res = get_answer(query=st.session_state.pending_query, selected_standard=val)
            st.session_state.chat_history.append(("question", f"{st.session_state.pending_query} ({label})"))
            st.session_state.chat_history.append(("answer", res))
            st.session_state.pending_query = None
            st.rerun()

# Display chat
# Display chat
for etype, entry in st.session_state.chat_history:
    if etype == "question":
        st.markdown(f"🧑‍💬 **You:** {entry}")
    elif etype == "answer":
        if isinstance(entry, dict):
            st.markdown("🌍 **Carbon GPT:**", unsafe_allow_html=True)
            st.markdown(entry.get("answer", "No answer."), unsafe_allow_html=True)

            #if entry.get("sources"):
                #with st.expander("📚 Sources"):
                    #for src in entry["sources"]:
                        #st.write(f"- {src.get('file_name', 'Unknown Doc')} (Page {src.get('page','N/A')})")
        else:  # fallback if old history still has strings
            st.markdown("🌍 **Carbon GPT:**", unsafe_allow_html=True)
            st.markdown(str(entry), unsafe_allow_html=True)
