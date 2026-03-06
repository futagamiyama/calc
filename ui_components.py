import os
import streamlit as st
import matplotlib.pyplot as plt
from engine import run_step, parse_program, CONSTANTS

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")


@st.dialog("ファイルを読み込む")
def _load_dialog(session_state):
    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".bas")) if os.path.isdir(SRC_DIR) else []
    if not files:
        st.warning("src/ に .bas ファイルがありません")
        if st.button("閉じる"):
            st.rerun()
        return
    selected = st.selectbox("ファイルを選択", files)
    col1, col2 = st.columns(2)
    if col1.button("読み込む", use_container_width=True):
        with open(os.path.join(SRC_DIR, selected), encoding="utf-8") as f:
            content = f.read()
        session_state.initial_text = content
        session_state.editor_key += 1
        session_state.variables = dict(CONSTANTS)
        session_state.pc_idx = 0
        session_state.output = []
        st.rerun()
    if col2.button("キャンセル", use_container_width=True):
        st.rerun()


@st.dialog("ファイルを保存")
def _save_dialog(code_input):
    filename = st.text_input("ファイル名", value="program.bas")
    col1, col2 = st.columns(2)
    if col1.button("保存", use_container_width=True):
        os.makedirs(SRC_DIR, exist_ok=True)
        filepath = os.path.join(SRC_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_input)
        st.success(f"保存しました: src/{filename}")
        st.rerun()
    if col2.button("キャンセル", use_container_width=True):
        st.rerun()

SAFETY_LIMIT = 1000


def render_editor(session_state):
    """
    エディタ列を描画し、パース済みプログラムを返す。

    Returns:
        program: [{"no": int, "cmd": str}, ...]
    """
    st.subheader("📝 Editor")

    num_col, edit_col = st.columns([0.1, 0.9])

    with edit_col:
        code_input = st.text_area(
            "Commands",
            value=session_state.initial_text,
            height=250,
            key=f"ed_{session_state.editor_key}",
        )
        session_state.initial_text = code_input

    # 行番号を左列に表示
    raw_lines = code_input.split("\n")
    line_nums_html = "".join(
        [f"<div>{(i + 1) * 10}</div>" for i in range(len(raw_lines))]
    )
    with num_col:
        st.markdown(
            f"<div class='line-number-container'>{line_nums_html}</div>",
            unsafe_allow_html=True,
        )

    program, labels, functions = parse_program(code_input)

    # --- ボタン群 ---
    btns = st.columns(6)

    if btns[0].button("▶ RUN"):
        session_state.variables = dict(CONSTANTS)
        session_state.output = ["--- Run Start ---"]
        session_state.pc_idx = 0
        safety_net = 0
        while session_state.pc_idx < len(program) and safety_net < SAFETY_LIMIT:
            session_state.pc_idx = run_step(
                program,
                session_state.pc_idx,
                session_state.variables,
                session_state.output,
                labels,
                functions,
            )
            safety_net += 1
        if safety_net >= SAFETY_LIMIT:
            session_state.output.append("ERR: Infinite Loop?")

    if btns[1].button("👣 STEP"):
        if session_state.pc_idx < len(program):
            session_state.pc_idx = run_step(
                program,
                session_state.pc_idx,
                session_state.variables,
                session_state.output,
                labels,
                functions,
            )
        else:
            session_state.output.append("End.")

    if btns[2].button("🔄 RESET"):
        session_state.variables = dict(CONSTANTS)
        session_state.pc_idx = 0
        session_state.output = []
        st.rerun()

    if btns[4].button("💾 SAVE"):
        _save_dialog(code_input)

    if btns[5].button("📂 LOAD"):
        _load_dialog(session_state)

    if btns[3].button("🗑️ CLEAR"):
        session_state.editor_key += 1
        session_state.initial_text = ""
        session_state.variables = dict(CONSTANTS)
        session_state.pc_idx = 0
        session_state.output = []
        st.rerun()

    return program, labels, functions


def render_debugger(program, session_state):
    """デバッガ列を描画する"""
    st.subheader("🐞 Debugger")

    if session_state.pc_idx < len(program):
        p = program[session_state.pc_idx]
        st.info(f"Next: **Line {p['no']}** → `{p['cmd']}`")
    else:
        st.success("Finished")

    st.write("**Variables:**")
    st.table(session_state.variables if session_state.variables else {"-": "-"})

    st.write("**Console:**")
    text_lines = [item for item in session_state.output if isinstance(item, str)]
    st.code("\n".join(text_lines) if text_lines else "Empty")

    for item in session_state.output:
        if isinstance(item, dict) and item.get("type") == "plot":
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.plot(item["xs"], item["ys"])
            ax.axhline(0, color="k", linewidth=0.5)
            ax.axvline(0, color="k", linewidth=0.5)
            ax.set_title(f"y = {item['expr']}")
            ax.set_xlabel("x")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)
