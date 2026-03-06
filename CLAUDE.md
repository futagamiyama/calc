# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
streamlit run app.py
```

## Architecture

Three-file structure:

- **`engine.py`** — Pure Python BASIC interpreter. `parse_program(code_text)` converts text to a list of `{"no": int, "cmd": str}` dicts (line numbers are auto-assigned as multiples of 10). `run_step(program, pc_idx, variables, output)` executes one instruction and returns the next `pc_idx`. No Streamlit dependency.

- **`ui_components.py`** — Streamlit UI split into two renderers: `render_editor()` draws the code editor with line numbers and control buttons (RUN/STEP/RESET/CLEAR), returning the parsed program; `render_debugger()` shows current PC, variable table, and console output.

- **`app.py`** — Entry point. Sets page config, initializes `st.session_state`, splits into two columns, and calls the two renderers.

## Key Design Notes

- All mutable state (variables, pc_idx, output, editor_key) lives in `st.session_state`.
- `run_step` uses `eval()` with `normalize_expr()` (uppercases variable names) — expressions are evaluated against the `variables` dict.
- Supported BASIC commands: assignment (`VAR = expr`), `IF <cond> THEN <lineno>`, `GOTO <lineno>`, `PRINT <expr>`.
- Infinite loop guard: `SAFETY_LIMIT = 1000` steps in RUN mode.
