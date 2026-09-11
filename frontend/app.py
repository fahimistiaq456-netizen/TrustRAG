"""Professional two-mode interface for comparing local LLM behavior."""
from __future__ import annotations

import os
from typing import Any
import requests
import streamlit as st

API_URL = os.getenv("HALLUFIX_API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="Hallufix Local Lab", page_icon="🔬", layout="wide")

# Simple text icons (replacing non-working SVGs)
ICON_CHAT = "💬"
ICON_SEARCH = "🔍"
ICON_BOOK = "📚"
ICON_CHART = "📊"
ICON_LOCK = "🔒"
ICON_REFRESH = "🔄"
ICON_TARGET = "🎯"
ICON_CHECK = "✓"
ICON_SPEED = "⚡"
ICON_FILE = "📄"
ICON_CLOCK = "⏱️"
ICON_PERCENT = "📈"
ICON_BLOCK = "🚫"
ICON_HYBRID = "🔀"

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

* {
    font-family: 'JetBrains Mono', monospace;
    box-sizing: border-box;
}

.stApp {
    background: linear-gradient(135deg, #82193A 0%, #6B1530 50%, #521025 100%);
    color: #FEE3C5;
    min-height: 100vh;
}

[data-testid="stHeader"] {
    background: rgba(254, 227, 197, 0.1);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid rgba(254, 227, 197, 0.2);
    padding: 1rem 2rem;
}

[data-testid="stSidebar"] {
    background: rgba(254, 227, 197, 0.95);
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(254, 227, 197, 0.3);
    padding: 2rem 1.5rem;
}

/* Main content container */
.main-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

.hero {
    padding: 3rem 2rem 2rem;
    text-align: center;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-radius: 24px;
    margin: 2rem auto;
    max-width: 900px;
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.hero h1 {
    font-size: 3rem;
    margin: 0 0 1rem;
    letter-spacing: -0.02em;
    font-weight: 900;
    color: #FEE3C5;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    font-family: 'Playfair Display', serif;
}

.hero h1 span {
    color: #82193A;
}

.hero p {
    color: rgba(254, 227, 197, 0.9);
    font-size: 1.15rem;
    max-width: 700px;
    margin: 1rem auto 0;
    line-height: 1.7;
    font-weight: 400;
    font-family: 'Poppins', sans-serif;
}

.pill {
    display: inline-block;
    background: rgba(254, 227, 197, 0.2);
    color: #FEE3C5;
    padding: 0.5rem 1.25rem;
    border-radius: 999px;
    font-size: 0.85rem;
    margin-bottom: 1.5rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    border: 1px solid rgba(254, 227, 197, 0.3);
    backdrop-filter: blur(10px);
    font-family: 'Poppins', sans-serif;
}

/* Card Design */
.card {
    background: rgba(254, 227, 197, 0.95);
    border-radius: 20px;
    padding: 2rem;
    margin: 1.5rem 0;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: 1px solid rgba(254, 227, 197, 0.3);
    backdrop-filter: blur(20px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

[data-testid="stMetric"] {
    background: rgba(254, 227, 197, 0.95);
    border: 1px solid rgba(254, 227, 197, 0.3);
    border-radius: 20px;
    padding: 1.5rem;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
    margin: 0.5rem;
}

[data-testid="stMetric"]:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
}

[data-testid="stMetricValue"] {
    color: #82193A;
    font-weight: 700;
    font-size: 2rem;
}

[data-testid="stMetricDelta"] {
    display: none;
}

.metric-with-icon {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #82193A;
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    font-family: 'Poppins', sans-serif;
}

.metric-with-icon span {
    color: #82193A;
}

.source {
    border-left: 4px solid #82193A;
    padding: 1.5rem;
    margin: 1rem 0;
    color: #1a1a1a;
    background: rgba(254, 227, 197, 0.95);
    border-radius: 0 16px 16px 0;
    transition: all 0.3s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    font-family: 'Poppins', sans-serif;
}

.source b {
    color: #82193A;
    font-weight: 700;
}

.source code {
    color: #5A5A5A;
    background: rgba(130, 25, 58, 0.1);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.9em;
}

.source:hover {
    background: #FEE3C5;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    transform: translateX(4px);
}

/* Tab Design */
[data-testid="stTabs"] {
    background: rgba(254, 227, 197, 0.1);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    padding: 0.5rem;
    margin: 2rem 0;
    border: 1px solid rgba(254, 227, 197, 0.2);
}

[data-testid="stTab"] {
    background: transparent;
    color: rgba(254, 227, 197, 0.7);
    border-radius: 16px;
    padding: 1rem 1.5rem;
    font-weight: 600;
    transition: all 0.3s ease;
    border: none;
}

[data-testid="stTab"][aria-selected="true"] {
    background: rgba(254, 227, 197, 0.95);
    color: #82193A;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

[data-testid="stTab"]:hover:not([aria-selected="true"]) {
    background: rgba(254, 227, 197, 0.15);
    color: #FEE3C5;
}

/* Chat Messages */
[data-testid="stChatMessage"] {
    background: rgba(254, 227, 197, 0.95);
    border-radius: 20px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    transition: all 0.3s ease;
    border: 1px solid rgba(254, 227, 197, 0.3);
}

[data-testid="stChatMessage"]:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
}

[data-testid="stChatMessage"] p {
    color: #2D2D2D;
    line-height: 1.6;
    font-family: 'Poppins', sans-serif;
}

/* Buttons */
[data-testid="stButton"] > button {
    background: #FEE3C5;
    color: #82193A;
    border: none;
    border-radius: 12px;
    padding: 0.8rem 1.8rem;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.3s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    letter-spacing: 0.01em;
    font-family: 'Poppins', sans-serif;
}

[data-testid="stButton"] > button:hover {
    background: #F5D0A0;
    color: #6B1530;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

[data-testid="stButton"] > button:active {
    transform: translateY(0);
}

[data-testid="stButton"][kind="primary"] > button {
    background: #82193A;
    color: #FEE3C5;
}

[data-testid="stButton"][kind="primary"] > button:hover {
    background: #6B1530;
    color: #FEE3C5;
}

/* Input Fields */
[data-testid="stTextInput"] > div > div > input,
[data-testid="stTextArea"] > div > div > textarea {
    border-radius: 12px;
    border: 2px solid rgba(254, 227, 197, 0.3);
    background: rgba(254, 227, 197, 0.95);
    color: #2D2D2D;
    padding: 1rem;
    font-size: 1rem;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

[data-testid="stTextInput"] > div > div > input:focus,
[data-testid="stTextArea"] > div > div > textarea:focus {
    border-color: #82193A;
    box-shadow: 0 0 0 4px rgba(130, 25, 58, 0.1);
    background: #FEE3C5;
}

[data-testid="stTextInput"] > div > div > input::placeholder,
[data-testid="stTextArea"] > div > div > textarea::placeholder {
    color: #8A8A8A;
}

/* Chat Input */
[data-testid="stChatInput"] > div > div > input {
    border-radius: 24px;
    border: 2px solid rgba(254, 227, 197, 0.3);
    background: rgba(254, 227, 197, 0.95);
    color: #2D2D2D;
    padding: 1rem 1.5rem;
    font-size: 1rem;
    transition: all 0.3s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

[data-testid="stChatInput"] > div > div > input:focus {
    border-color: #82193A;
    box-shadow: 0 0 0 4px rgba(130, 25, 58, 0.1);
    background: #FEE3C5;
}

/* Headers and Text */
h1, h2, h3, h4, h5, h6 {
    color: #FEE3C5;
    font-weight: 700;
    font-family: 'Playfair Display', serif;
}

.stMarkdown {
    color: rgba(254, 227, 197, 0.9);
    font-family: 'Poppins', sans-serif;
}

.stCaption {
    color: rgba(254, 227, 197, 0.8);
    font-size: 0.95rem;
    line-height: 1.6;
    font-family: 'Poppins', sans-serif;
}

/* File Uploader */
[data-testid="stFileUploader"] {
    border-radius: 16px;
    border: 2px dashed rgba(254, 227, 197, 0.4);
    background: rgba(254, 227, 197, 0.1);
    padding: 2rem;
    transition: all 0.3s ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: #82193A;
    background: rgba(254, 227, 197, 0.15);
}

/* Loading animation */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading-spinner {
    display: inline-block;
    width: 24px;
    height: 24px;
    border: 3px solid rgba(254, 227, 197, 0.3);
    border-radius: 50%;
    border-top-color: #FEE3C5;
    animation: spin 0.8s linear infinite;
    margin-right: 12px;
    vertical-align: middle;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Streamlit spinner customization */
[data-testid="stSpinner"] {
    color: #FEE3C5;
}

[data-testid="stSpinner"] > div {
    border-color: rgba(254, 227, 197, 0.3);
    border-top-color: #FEE3C5;
}

/* Smooth transitions for all interactive elements */
[data-testid="stButton"], 
[data-testid="stTextInput"], 
[data-testid="stTextArea"],
[data-testid="stSelectbox"], 
[data-testid="stFileUploader"],
[data-testid="stChatInput"] {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Fade-in animation for content */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(16px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.fade-in {
    animation: fadeIn 0.6s ease-out;
}

/* Slide-in animation for tabs */
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(-16px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

[data-testid="stTab"] {
    animation: slideIn 0.4s ease-out;
}

/* Smooth transition for chat messages */
[data-testid="stChatMessage"] {
    animation: fadeIn 0.5s ease-out;
}

/* Hover effects for metrics */
[data-testid="stMetric"] {
    animation: fadeIn 0.6s ease-out;
}

/* Smooth transition for file uploader */
[data-testid="stFileUploader"] {
    transition: all 0.3s ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: #FF5B32;
    background: rgba(255, 255, 255, 0.15);
}

/* Success message styling */
[data-testid="stSuccess"] {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    border-radius: 16px;
    padding: 1.5rem;
    color: #FEE3C5;
    backdrop-filter: blur(10px);
}

/* Warning message styling */
[data-testid="stWarning"] {
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.4);
    border-radius: 16px;
    padding: 1.5rem;
    color: #FEE3C5;
    backdrop-filter: blur(10px);
}

/* Error message styling */
[data-testid="stError"] {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 16px;
    padding: 1.5rem;
    color: #FEE3C5;
    backdrop-filter: blur(10px);
}

/* Info message styling */
[data-testid="stInfo"] {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 16px;
    padding: 1.5rem;
    color: #FEE3C5;
    backdrop-filter: blur(10px);
}

/* Icon styling */
.icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.2em;
    height: 1.2em;
    margin-right: 0.5em;
    vertical-align: middle;
}

/* Divider */
[data-testid="stDivider"] {
    border-color: rgba(254, 227, 197, 0.2);
    margin: 2rem 0;
}

/* Selectbox */
[data-testid="stSelectbox"] > div > div > select {
    border-radius: 12px;
    border: 2px solid rgba(254, 227, 197, 0.3);
    background: rgba(254, 227, 197, 0.95);
    color: #2D2D2D;
    padding: 0.8rem;
    transition: all 0.3s ease;
}

[data-testid="stSelectbox"] > div > div > select:focus {
    border-color: #82193A;
    box-shadow: 0 0 0 4px rgba(130, 25, 58, 0.1);
}

/* Columns */
[data-testid="column"] {
    padding: 0.75rem;
}

/* Improve text visibility in white cards */
.card p, .card h1, .card h2, .card h3, .card h4, .card h5, .card h6 {
    color: #2D2D2D;
}

.card .stMarkdown {
    color: #2D2D2D;
}

/* Subheader styling */
[data-testid="stSubheader"] {
    color: #FEE3C5;
    font-weight: 700;
    font-size: 1.5rem;
    margin: 1.5rem 0 1rem;
    font-family: 'Playfair Display', serif;
}
</style>""", unsafe_allow_html=True)

def api_post(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with st.spinner("Processing your request..."):
            response = requests.post(f"{API_URL}{path}", json=payload, timeout=240)
        if not response.ok:
            st.error(f"API error ({response.status_code}): {response.json().get('detail', response.text)}")
            return None
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Cannot reach the local backend: {exc}")
        return None

def render_chat(history: list[dict[str, str]]) -> None:
    for message in history:
        with st.chat_message(message["role"]): st.markdown(message["content"])

st.markdown(f"""<div class="hero fade-in">
<div class="pill">
{ICON_LOCK}
LOCAL-FIRST · NO API KEY
</div>
<h1>Hallufix <span style="color:#FFF2CF">Local Lab</span></h1>
<p>Compare an everyday local conversation model with a source-ranked, verified RAG answer—without sending your documents to a cloud model.</p>
</div>""", unsafe_allow_html=True)

if "normal_history" not in st.session_state: st.session_state.normal_history = []
if "hallufix_history" not in st.session_state: st.session_state.hallufix_history = []
if "hybrid_history" not in st.session_state: st.session_state.hybrid_history = []
if "last_hallufix" not in st.session_state: st.session_state.last_hallufix = None
if "last_hybrid" not in st.session_state: st.session_state.last_hybrid = None

try:
    health = requests.get(f"{API_URL}/health", timeout=3).json()
    if health.get("selected_model_available"):
        st.success(f"Local model ready: **{health['selected_model']}**")
    else:
        st.warning(f"Ollama model not ready. Run `ollama pull {health.get('selected_model', 'llama3.2:3b')}` in Terminal.")
except (requests.RequestException, ValueError):
    st.warning("Backend unavailable. Start it with `uvicorn backend.api:app --reload`.")

normal_tab, hallufix_tab, hybrid_tab, data_tab, metrics_tab = st.tabs([
    "Normal conversation",
    "Hallufix answer",
    "Hybrid answer",
    "Sources & ranking",
    "Comparison metrics"
])

with normal_tab:
    st.markdown(f"""
    <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
        {ICON_CHAT}
        Everyday local conversation
    </h3>
    """, unsafe_allow_html=True)
    st.caption("The local model responds naturally. It does not retrieve or verify private source documents.")
    render_chat(st.session_state.normal_history)
    question = st.chat_input("Talk to the normal local model", key="normal_input")
    if question:
        st.session_state.normal_history.append({"role": "user", "content": question})
        result = api_post("/chat/normal", {"question": question, "history": st.session_state.normal_history[:-1]})
        if result:
            st.session_state.normal_history.append({"role": "assistant", "content": result["answer"]})
            st.session_state.normal_latency = result["latency_ms"]
            st.rerun()

with hallufix_tab:
    st.markdown(f"""
    <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
        {ICON_SEARCH}
        Verified, source-ranked answer
    </h3>
    """, unsafe_allow_html=True)
    st.caption("Retrieves the five strongest text chunks, abstains on weak evidence, then checks each generated claim.")
    render_chat(st.session_state.hallufix_history)
    question = st.chat_input("Ask about your indexed sources", key="hallufix_input")
    if question:
        st.session_state.hallufix_history.append({"role": "user", "content": question})
        result = api_post("/ask", {"question": question, "history": st.session_state.hallufix_history[:-1]})
        if result:
            st.session_state.hallufix_history.append({"role": "assistant", "content": result["answer"]})
            st.session_state.last_hallufix = result
            st.rerun()
    result = st.session_state.last_hallufix
    if result:
        stats = result["stats"]
        a, b, c, d = st.columns(4)
        with a:
            st.markdown(f"<div class='metric-with-icon'>{ICON_TARGET} <span>Retrieval confidence</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{result['confidence']:.2f}", label_visibility="collapsed")
        with b:
            st.markdown(f"<div class='metric-with-icon'>{ICON_CHECK} <span>Claims supported</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{stats['claims_supported']} / {stats['claims_checked']}", label_visibility="collapsed")
        with c:
            st.markdown(f"<div class='metric-with-icon'>{ICON_PERCENT} <span>Support rate</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{stats['support_rate']:.0%}", label_visibility="collapsed")
        with d:
            st.markdown(f"<div class='metric-with-icon'>{ICON_SPEED} <span>Local latency</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{stats['latency_ms'] / 1000:.1f}s", label_visibility="collapsed")
        if result["abstained"]: st.warning("Hallufix abstained because the retrieved evidence was below the configured threshold.")
        
        # Add ranking section at the bottom of Hallufix answers tab
        st.divider()
        st.markdown(f"""
        <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
            {ICON_BOOK}
            Source ranking for last question
        </h3>
        """, unsafe_allow_html=True)
        for rank, source in enumerate(result["sources"], start=1):
            st.markdown(f"<div class='source fade-in'><b>#{rank} · {source['citation']}</b> &nbsp; <code>similarity {source['similarity_score']:.3f}</code><br>{source['text']}</div>", unsafe_allow_html=True)

with hybrid_tab:
    st.markdown(f"""
    <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
        {ICON_HYBRID}
        Hybrid answer · source first, local model as fallback
    </h3>
    """, unsafe_allow_html=True)
    st.caption("Hallufix searches your source library first. When the source matches your question strongly, it returns a verified, cited answer from the sources. If the source does not contain the answer, it falls back to the local model for a natural answer.")
    render_chat(st.session_state.hybrid_history)
    question = st.chat_input("Ask anything — conversation or source question", key="hybrid_input")
    if question:
        st.session_state.hybrid_history.append({"role": "user", "content": question})
        result = api_post("/chat/hybrid", {"question": question, "history": st.session_state.hybrid_history[:-1]})
        if result:
            st.session_state.hybrid_history.append({"role": "assistant", "content": result["answer"]})
            st.session_state.last_hybrid = result
            st.rerun()
    result = st.session_state.last_hybrid
    if result:
        st.divider()
        mode = result.get("mode", "LLM")
        if mode == "RAG":
            st.success(f"Answer taken from your source library: the source matched your question strongly, and the answer was sentence-verified. ({result.get('latency_ms', 0) / 1000:.1f}s)")
            if result.get("abstained"):
                st.warning("The source matched, but the generated wording could not be verified against the retrieved evidence, so Hallufix abstained.")
            st.markdown(f"""
            <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
                {ICON_BOOK}
                Sources used for the answer
            </h3>
            """, unsafe_allow_html=True)
            for rank, source in enumerate(result.get("sources", [])[:5], start=1):
                st.markdown(f"<div class='source fade-in'><b>#{rank} · {source['citation']}</b> &nbsp; <code>similarity {source['similarity_score']:.3f}</code><br>{source['text']}</div>", unsafe_allow_html=True)
        elif mode == "ABSTAIN":
            st.warning("Neither the source library nor the local model could supply a reliable answer, so Hallufix abstained.")
        elif result.get("fallback_unavailable"):
            st.error("The source library is not indexed yet, so the local model answered directly. Upload sources in the 'Sources & ranking' tab to enable source-first answers.")
        else:
            st.info(f"The source library did not contain a strong match, so the local model answered from its own knowledge. ({result.get('latency_ms', 0) / 1000:.1f}s)")

with data_tab:
    st.markdown(f"""
    <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
        {ICON_BOOK}
        Source library
    </h3>
    """, unsafe_allow_html=True)
    st.caption("Upload multiple PDF or TXT files. They are embedded locally, stored on this Mac, and ranked together at question time.")
    uploads = st.file_uploader("Add source documents", type=["pdf", "txt"], accept_multiple_files=True)
    if st.button(f"{ICON_REFRESH} Build / refresh local index", type="primary", disabled=not uploads):
        try:
            with st.spinner("Indexing your documents..."):
                response = requests.post(f"{API_URL}/ingest", files=[("files", (file.name, file.getvalue(), file.type)) for file in uploads], timeout=300)
            if response.ok:
                payload = response.json(); st.success(f"Indexed {payload['chunk_count']} chunks from {payload['source_count']} sources.")
                st.json(payload)
            else: st.error(f"Indexing failed: {response.json().get('detail', response.text)}")
        except requests.RequestException as exc: st.error(f"Cannot upload sources: {exc}")

with metrics_tab:
    st.markdown(f"""
    <h3 style="display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem;">
        {ICON_CHART}
        Transparent comparison, not a claim of universal quality
    </h3>
    """, unsafe_allow_html=True)
    normal_latency = st.session_state.get("normal_latency")
    result = st.session_state.last_hallufix
    hybrid = st.session_state.last_hybrid
    left, right, hybrid_col = st.columns(3)
    with left:
        st.markdown(f"### {ICON_CHAT} Normal local model")
        st.markdown(f"<div class='metric-with-icon'>{ICON_CLOCK} <span>Last response latency</span></div>", unsafe_allow_html=True)
        st.metric("Value", f"{normal_latency / 1000:.1f}s" if normal_latency else "—", label_visibility="collapsed")
        st.write("Natural conversation, but no retrieval score, source citations, abstention control, or sentence verification.")
    with right:
        st.markdown(f"### {ICON_SEARCH} Hallufix local model")
        if result:
            stats = result["stats"]
            st.markdown(f"<div class='metric-with-icon'>{ICON_CLOCK} <span>Last response latency</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{stats['latency_ms'] / 1000:.1f}s", label_visibility="collapsed")
            st.markdown(f"<div class='metric-with-icon'>{ICON_PERCENT} <span>Evidence support rate</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{stats['support_rate']:.0%}", label_visibility="collapsed")
            st.markdown(f"<div class='metric-with-icon'>{ICON_BLOCK} <span>Abstained</span></div>", unsafe_allow_html=True)
            st.metric("Value", "Yes" if result["abstained"] else "No", label_visibility="collapsed")
        else: st.info("Ask a Hallufix question to populate verification metrics.")
    with hybrid_col:
        st.markdown(f"### {ICON_HYBRID} Hybrid mode")
        if hybrid:
            st.markdown(f"<div class='metric-with-icon'>{ICON_SPEED} <span>Last routed mode</span></div>", unsafe_allow_html=True)
            st.metric("Value", hybrid.get("mode", "—"), label_visibility="collapsed")
            st.markdown(f"<div class='metric-with-icon'>{ICON_CLOCK} <span>Last response latency</span></div>", unsafe_allow_html=True)
            st.metric("Value", f"{hybrid.get('latency_ms', 0) / 1000:.1f}s", label_visibility="collapsed")
            st.write("Source-first: answers from the source library when evidence is strong; falls back to the local model otherwise.")
        else: st.info("Ask a Hybrid question to populate routing metrics.")
    st.caption("For thesis reporting, compare answer quality using the provided 50-question set and include human review; these interface metrics measure pipeline behavior, not absolute truth.")
