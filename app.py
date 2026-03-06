import streamlit as st
from ui_components import render_editor, render_debugger
from engine import CONSTANTS

# --- ページ設定 ---
st.set_page_config(layout="wide")

st.markdown("""
    <style>
    .line-number-container {
        font-family: 'Source Code Pro', monospace;
        font-size: 1rem;
        color: #888;
        text-align: right;
        line-height: 1.6;
        padding-top: 2.5rem;
    }
    .stTextArea textarea {
        line-height: 1.6 !important;
        font-family: 'Source Code Pro', monospace !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📟 BASIC Debugger (Logic & Jump)")

# --- セッション状態の初期化 ---
defaults = {
    "variables": dict(CONSTANTS),
    "pc_idx": 0,
    "output": [],
    "editor_key": 0,
    "initial_text": (
        "total = 0\n"
        "i = 1\n"
        "total = total + i\n"
        "i = i + 1\n"
        "if i <= 10 then 30\n"
        "print total"
    ),
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- レイアウト ---
col_editor, col_debug = st.columns([1, 1])

with col_editor:
    program, labels, functions = render_editor(st.session_state)

with col_debug:
    render_debugger(program, st.session_state)
