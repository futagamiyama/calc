import re
import math

# 起動時に variables に展開される定数
CONSTANTS = {
    "E": 2.71828,
    "PI": 3.14159,
}

# eval() の globals として渡す組み込み関数
def _log(a, b=None):
    """log(a) → log10(a)、log(a, b) → 底aの対数b"""
    if b is None:
        return math.log10(a)
    return math.log(b, a)


_EVAL_GLOBALS = {
    "SIN": math.sin,
    "COS": math.cos,
    "TAN": math.tan,
    "LOG": _log,
    "LN": math.log,
    "EXP": math.exp,
    "POWER": pow,
}


def normalize_expr(expr):
    """数式内の変数を大文字化・^ を ** に変換"""
    expr = expr.replace('^', '**')
    return re.sub(r'\b[a-zA-Z_]\w*\b', lambda m: m.group(0).upper(), expr)


def _resolve_target(target, program, labels):
    """行番号またはラベル名をプログラムインデックスに変換"""
    if target.isdigit():
        line_no = int(target)
        for i, row in enumerate(program):
            if row["no"] == line_no:
                return i
    else:
        return labels.get(target.upper())
    return None


def _resolve_array_access(expr, variables):
    """
    式中の配列アクセス記法を変換する。
      A(5)    → A[5]
      B(1, 2) → B[1][2]
    variables 内でリスト型の変数のみ対象とする。
    """
    array_vars = {k for k, v in variables.items() if isinstance(v, list)}
    # 長い名前を優先して処理（部分一致を防ぐ）
    for var in sorted(array_vars, key=len, reverse=True):
        pattern = rf'\b{re.escape(var)}\b\s*\(([^)]+)\)'
        while True:
            match = re.search(pattern, expr, re.IGNORECASE)
            if not match:
                break
            indices = [i.strip() for i in match.group(1).split(',')]
            replacement = var + ''.join(f'[{i}]' for i in indices)
            expr = expr[:match.start()] + replacement + expr[match.end():]
    return expr


def _resolve_func_calls(expr, variables, functions, output):
    """式内の既知関数呼び出しを評価結果に置換する"""
    for fname in functions:
        pattern = rf'\b{re.escape(fname)}\b\s*\(([^)]*)\)'
        while True:
            match = re.search(pattern, expr, re.IGNORECASE)
            if not match:
                break
            raw_args = match.group(1).strip()
            if raw_args:
                args = [a.strip() for a in raw_args.split(',')]
                evaluated_args = [_eval_expr(a, variables, functions, output) for a in args]
            else:
                evaluated_args = []
            ret_val = _exec_func(fname, evaluated_args, functions, variables, output)
            if ret_val is None:
                ret_val = 0
            elif isinstance(ret_val, bool):
                ret_val = int(ret_val)
            expr = expr[:match.start()] + repr(ret_val) + expr[match.end():]
    return expr


def _eval_expr(expr, variables, functions, output):
    """式を評価する（関数呼び出し・配列アクセス・組み込み関数を含む）"""
    resolved = _resolve_func_calls(expr, variables, functions, output)
    resolved = _resolve_array_access(resolved, variables)
    return eval(normalize_expr(resolved), _EVAL_GLOBALS, variables)


def _exec_assign(lhs, rhs_expr, variables, functions, output):
    """
    代入を実行する。通常変数と配列要素の両方に対応。
      A = expr      → variables["A"] = val
      A(i) = expr   → variables["A"][i] = val
      B(i, j) = expr → variables["B"][i][j] = val
    """
    u_lhs = lhs.strip().upper()
    arr_match = re.match(r'^(\w+)\s*\(([^)]+)\)$', u_lhs)
    if arr_match:
        arr_name = arr_match.group(1)
        indices = [i.strip() for i in arr_match.group(2).split(',')]
        val = _eval_expr(rhs_expr.strip(), variables, functions, output)
        idx = [int(_eval_expr(i, variables, functions, output)) for i in indices]
        # ネスト配列を辿って最終要素に代入
        target = variables[arr_name]
        for i in idx[:-1]:
            target = target[i]
        target[idx[-1]] = val
    else:
        variables[u_lhs] = _eval_expr(rhs_expr.strip(), variables, functions, output)


def _exec_dim(cmd, variables):
    """
    DIM 命令を実行してゼロ初期化した配列を variables に登録する。
      DIM A(10)    → variables["A"] = [0]*10
      DIM B(3, 3)  → variables["B"] = [[0]*3 for _ in range(3)]
    """
    match = re.match(r'DIM\s+(\w+)\s*\((\d+)(?:\s*,\s*(\d+))?\)', cmd, re.IGNORECASE)
    if match:
        name = match.group(1).upper()
        size1 = int(match.group(2))
        size2 = match.group(3)
        if size2:
            variables[name] = [[0] * int(size2) for _ in range(size1)]
        else:
            variables[name] = [0] * size1


def _exec_func(fname, arg_vals, functions, global_vars, output):
    """
    関数を実行して戻り値を返す。
    ローカルスコープ = グローバル変数のコピー + パラメータ（呼び出し元には影響しない）
    """
    func = functions.get(fname.upper())
    if func is None:
        raise NameError(f"Undefined function: {fname}")

    local_vars = dict(global_vars)
    for param, val in zip(func["params"], arg_vals):
        local_vars[param] = val

    body = func["body"]
    func_labels = func["labels"]

    pc = 0
    safety = 0
    while pc < len(body) and safety < 1000:
        instr = body[pc]
        cmd = instr["cmd"].strip()
        u_cmd = cmd.upper()

        # RETURN
        if u_cmd.startswith("RETURN"):
            expr = cmd[6:].strip()
            return _eval_expr(expr, local_vars, functions, output) if expr else None

        # DIM
        if u_cmd.startswith("DIM"):
            _exec_dim(cmd, local_vars)

        # IF THEN
        elif u_cmd.startswith("IF"):
            match = re.search(r"IF\s+(.+?)\s+THEN\s+(?:GOTO\s+)?(\w+)", u_cmd)
            if match:
                if _eval_expr(match.group(1), local_vars, functions, output):
                    idx = _resolve_target(match.group(2), body, func_labels)
                    if idx is not None:
                        pc = idx
                        safety += 1
                        continue

        # GOTO
        elif u_cmd.startswith("GOTO"):
            match = re.search(r"GOTO\s+(\w+)", u_cmd)
            if match:
                idx = _resolve_target(match.group(1), body, func_labels)
                if idx is not None:
                    pc = idx
                    safety += 1
                    continue

        # PRINT
        elif u_cmd.startswith("PRINT"):
            res = _eval_expr(cmd[5:].strip(), local_vars, functions, output)
            output.append(f"  [{fname}:{instr['no']}] OUT: {res}")

        # 代入（配列要素への代入も含む） ※ 関数呼び出しチェックより先に評価する
        elif "=" in u_cmd:
            var_part, expr_part = cmd.split("=", 1)
            _exec_assign(var_part, expr_part, local_vars, functions, output)

        # 単独の関数呼び出し
        elif re.match(r'^[A-Z_]\w*\s*\(', u_cmd):
            fname_match = re.match(r'^([A-Z_]\w*)\s*\(', u_cmd)
            if fname_match and fname_match.group(1) in functions:
                _resolve_func_calls(cmd, local_vars, functions, output)

        pc += 1
        safety += 1

    return None


def run_step(program, pc_idx, variables, output, labels=None, functions=None):
    """
    1ステップ実行する。

    Args:
        program  : 命令リスト [{"no": int, "cmd": str}, ...]
        pc_idx   : 現在のプログラムカウンタ（インデックス）
        variables: 変数辞書（破壊的に更新される）
        output   : 出力ログリスト（破壊的に追記される）
        labels   : ラベル辞書 {"LOOP": index, ...}
        functions: 関数辞書 {"ADD": {"params", "body", "labels"}, ...}

    Returns:
        next_idx : 次のプログラムカウンタ
    """
    if labels is None:
        labels = {}
    if functions is None:
        functions = {}
    if pc_idx >= len(program):
        return pc_idx

    p = program[pc_idx]
    cmd = p["cmd"].strip()
    u_cmd = cmd.upper()
    next_idx = pc_idx + 1

    try:
        # DIM
        if u_cmd.startswith("DIM"):
            _exec_dim(cmd, variables)

        # IF THEN
        elif u_cmd.startswith("IF"):
            match = re.search(r"IF\s+(.+?)\s+THEN\s+(?:GOTO\s+)?(\w+)", u_cmd)
            if match:
                if _eval_expr(match.group(1), variables, functions, output):
                    idx = _resolve_target(match.group(2), program, labels)
                    if idx is not None:
                        next_idx = idx
                        output.append(f"[{p['no']}] Jump to {match.group(2)}")
            else:
                output.append(f"[{p['no']}] Syntax Error in IF")

        # GOTO
        elif u_cmd.startswith("GOTO"):
            match = re.search(r"GOTO\s+(\w+)", u_cmd)
            if match:
                idx = _resolve_target(match.group(1), program, labels)
                if idx is not None:
                    next_idx = idx
                    output.append(f"[{p['no']}] GOTO {match.group(1)}")

        # PRINT
        elif u_cmd.startswith("PRINT"):
            res = _eval_expr(cmd[5:].strip(), variables, functions, output)
            output.append(f"[{p['no']}] OUT: {res}")

        # PLOT <式>, <x_min>, <x_max>
        elif u_cmd.startswith("PLOT"):
            parts = cmd[4:].strip().rsplit(',', 2)
            if len(parts) == 3:
                expr_str = parts[0].strip()
                x_min = float(_eval_expr(parts[1].strip(), variables, functions, output))
                x_max = float(_eval_expr(parts[2].strip(), variables, functions, output))
                xs, ys = [], []
                for k in range(301):
                    x = x_min + (x_max - x_min) * k / 300
                    local = dict(variables)
                    local["X"] = x
                    try:
                        ys.append(float(_eval_expr(expr_str, local, functions, output)))
                        xs.append(x)
                    except Exception:
                        pass
                output.append({"type": "plot", "expr": expr_str, "xs": xs, "ys": ys})
            else:
                output.append(f"[{p['no']}] Syntax: plot <expr>, <x_min>, <x_max>")

        # 代入（配列要素への代入も含む） ※ 関数呼び出しチェックより先に評価する
        elif "=" in u_cmd:
            var_part, expr_part = cmd.split("=", 1)
            _exec_assign(var_part, expr_part, variables, functions, output)

        # 単独の関数呼び出し（戻り値を捨てる）
        elif re.match(r'^[A-Z_]\w*\s*\(', u_cmd):
            fname_match = re.match(r'^([A-Z_]\w*)\s*\(', u_cmd)
            if fname_match and fname_match.group(1) in functions:
                _resolve_func_calls(cmd, variables, functions, output)

    except Exception as e:
        output.append(f"[{p['no']}] ERR: {e}")

    return next_idx


def parse_program(code_text):
    """
    テキストをプログラム命令リスト・ラベル辞書・関数辞書に変換する。

    関数定義構文:
        def name(param1, param2):
            ...
        end

    Returns:
        (program, labels, functions)
    """
    program = []
    labels = {}
    functions = {}

    lines = [l.rstrip() for l in code_text.split("\n")]
    line_no = 10
    i = 0

    while i < len(lines):
        raw = lines[i].strip()
        if not raw:
            i += 1
            continue

        # 関数定義の開始
        def_match = re.match(r'def\s+(\w+)\s*\((.*?)\)\s*:', raw, re.IGNORECASE)
        if def_match:
            fname = def_match.group(1).upper()
            params = [p.strip().upper() for p in def_match.group(2).split(',') if p.strip()]
            body_lines = []
            func_labels = {}
            body_line_no = 10
            i += 1
            while i < len(lines):
                body_raw = lines[i].strip()
                if body_raw.lower() == 'end':
                    i += 1
                    break
                if body_raw:
                    if body_raw.endswith(':'):
                        func_labels[body_raw[:-1].upper()] = len(body_lines)
                    else:
                        body_lines.append({"no": body_line_no, "cmd": body_raw})
                        body_line_no += 10
                i += 1
            functions[fname] = {"params": params, "body": body_lines, "labels": func_labels}
            continue

        # ラベル定義
        if raw.endswith(':'):
            labels[raw[:-1].upper()] = len(program)
            i += 1
            continue

        program.append({"no": line_no, "cmd": raw})
        line_no += 10
        i += 1

    return program, labels, functions
