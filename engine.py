"""常驻 GHCi 引擎。

一次 :load 之后，模块都留在内存里；图上每改一个节点，只重发那一个
`let` 绑定，不重新编译、不重新链接。这就是「无需全量编译」的实际含义。
"""

from __future__ import annotations

import hashlib
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path


class EngineDead(RuntimeError):
    pass


PREFIX = re.compile(r"\b(?:Opl\.[A-Z][A-Za-z]*\.|Ke\.|El\.|Ps\.|Pr\.|Ev\.|Mt\.|Sy\.|Dr\.|Pl\.|Js\.)")


def clean_type(t: str) -> str:
    t = PREFIX.sub("", t.replace("\n", " "))
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace("[Char]", "String")
    return t


def strip_forall(t: str) -> str:
    t = t.strip()
    if not t.startswith("forall"):
        return t
    depth = 0
    for i, ch in enumerate(t):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "." and depth == 0:
            return t[i + 1 :].strip()
    return t


def strip_context(t: str) -> str:
    depth = 0
    cut = -1
    i = 0
    while i < len(t):
        ch = t[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and t.startswith("=>", i):
            cut = i + 2
            i += 2
            continue
        i += 1
    return t[cut:].strip() if cut >= 0 else t


def split_arrows(t: str):
    parts, depth, cur = [], 0, []
    i = 0
    while i < len(t):
        ch = t[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and t.startswith("->", i):
            parts.append("".join(cur).strip())
            cur = []
            i += 2
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def parse_sig(t: str):
    """'a -> b -> (c, d)' → (['a','b'], '(c, d)')"""
    t = strip_context(strip_forall(clean_type(t)))
    parts = split_arrows(t)
    if not parts:
        return [], "?"
    return parts[:-1], parts[-1]


def hs_string(s: str) -> str:
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


class Engine:
    def __init__(self, root: Path, rt_dir: Path):
        self.root = Path(root)
        self.rt = Path(rt_dir)
        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue = queue.Queue()
        self.lock = threading.RLock()
        self.types: dict[str, dict] = {}
        self.cache: dict[str, dict] = {}
        self.cur: dict[str, str] = {}
        self.rev = 0
        self.ready = False
        self.error = ""
        self.started_at = 0.0
        self.load_ms = 0

    # ------------------------------------------------------------ 进程 --
    def _spawn(self):
        self.proc = subprocess.Popen(
            [
                os.environ.get("BOARD_GHC", "ghc"), "--interactive", "-v0",
                "-XHaskell2010", f"-i{self.root / 'src'}", f"-i{self.rt}",
                "-fno-ghci-history",
            ],
            cwd=str(self.root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self.q = queue.Queue()

        def pump():
            # GHC 的普通输出用 UTF-8，错误信息却跟着控制台代码页（GBK）；
            # 逐行试解码，两边都不丢字。
            try:
                while True:
                    raw = self.proc.stdout.readline()  # type: ignore[union-attr]
                    if not raw:
                        break
                    for enc in ("utf-8", "gbk"):
                        try:
                            self.q.put(raw.decode(enc) + "\n")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        self.q.put(raw.decode("utf-8", "replace") + "\n")
            except Exception:
                pass
            self.q.put(None)

        threading.Thread(target=pump, daemon=True).start()

    def _read_until(self, marker: str, timeout: float) -> list[str]:
        lines: list[str] = []
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(marker)
            try:
                line = self.q.get(timeout=left)
            except queue.Empty:
                raise TimeoutError(marker)
            if line is None:
                raise EngineDead("GHCi 退出了")
            s = line.rstrip("\r\n")
            if s.strip() == marker:
                return lines
            lines.append(s)

    def batch(self, cmds: list[str], timeout: float = 60.0) -> list[str]:
        """顺序发一批命令，每条后面跟一个唯一标记，返回逐条输出。"""
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                raise EngineDead("引擎未启动")
            tag = uuid.uuid4().hex[:8]
            for i, c in enumerate(cmds):
                assert self.proc.stdin and self.proc.stdout
                self.proc.stdin.write((c + "\n").encode("utf-8"))
                self.proc.stdin.write(f'putStrLn "@@{tag}-{i}@@"\n'.encode("utf-8"))
            self.proc.stdin.flush()
            outs = []
            for i in range(len(cmds)):
                outs.append("\n".join(self._read_until(f"@@{tag}-{i}@@", timeout)).strip())
            return outs

    def start(self) -> dict:
        t0 = time.time()
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return {"ok": True, "cached": True, "types": len(self.types)}
            self.ready = False
            self.error = ""
            self.cache.clear()
            self.cur.clear()
            self.types.clear()
            self._spawn()
            try:
                out = self.batch([":set prompt \"\"", ":load BoardRt"], timeout=240)
                # 必须在 :load 之后设：加载会重开交互句柄
                self.batch([
                    "import System.IO",
                    "hSetEncoding stdin utf8",
                    "hSetEncoding stdout utf8",
                    "hSetEncoding stderr utf8",
                ], timeout=60)
                load_out = out[0]
                if "error" in load_out.lower() and "Compiling" not in load_out:
                    if re.search(r"error:", load_out):
                        self.error = load_out[:800]
                        self.ready = False
                        return {"ok": False, "error": self.error}
                self.load_ms = int((time.time() - t0) * 1000)
                self._fetch_types()
                self.ready = True
                self.started_at = time.time()
                return {"ok": True, "loadMs": self.load_ms, "types": len(self.types)}
            except Exception as exc:  # noqa: BLE001
                self.error = str(exc)[:400]
                self.ready = False
                return {"ok": False, "error": self.error}

    def stop(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.stdin.write(":q\n")  # type: ignore[union-attr]
                    self.proc.stdin.flush()  # type: ignore[union-attr]
                    self.proc.wait(timeout=3)
                except Exception:
                    self.proc.kill()
            self.proc = None
            self.ready = False

    # ------------------------------------------------------------ 类型 --
    def _fetch_types(self, names: list[str] | None = None):
        import palette

        names = names or [c["rt"] for c in palette.COMPS if c.get("rt")]
        outs = self.batch([f":t {n}" for n in names], timeout=120)
        for name, out in zip(names, outs):
            m = re.search(r"::(.*)$", out, re.S)
            if not m or "error" in out.lower().split("::")[0]:
                continue
            ins, res = parse_sig(m.group(1))
            self.types[name] = {"inputs": ins, "output": res, "raw": clean_type(m.group(1))}

    # ------------------------------------------------------------ 求值 --
    def _expr(self, node: dict, comp: dict, ins: list[str | None]) -> str | None:
        if comp.get("kind") == "value":
            v = node.get("value", "") or ""
            if comp["vtype"] == "Int":
                v = v.strip() or "0"
                return v if re.fullmatch(r"-?\d+", v) else None
            return hs_string(v)
        rt = comp.get("rt")
        t = self.types.get(rt, {})
        arity = len(t.get("inputs", []))
        if arity == 0:
            return rt
        if any(x is None for x in ins[:arity]):
            return None
        return "(" + " ".join([rt] + [str(x) for x in ins[:arity]]) + ")"

    def eval_graph(self, nodes: list[dict], edges: list[dict]) -> dict:
        import palette

        t0 = time.time()
        comps = palette.by_id()
        by_id = {n["id"]: n for n in nodes}
        incoming: dict[str, dict[int, str]] = {n["id"]: {} for n in nodes}
        for e in edges:
            if e["to"] in incoming and e["from"] in by_id:
                incoming[e["to"]][int(e.get("toPort", 0))] = e["from"]

        # 拓扑序
        order, seen, stack = [], set(), set()
        cyclic = set()

        def visit(nid):
            if nid in seen:
                return
            if nid in stack:
                cyclic.add(nid)
                return
            stack.add(nid)
            for src in incoming.get(nid, {}).values():
                visit(src)
            stack.discard(nid)
            seen.add(nid)
            order.append(nid)

        for n in nodes:
            visit(n["id"])

        results: dict[str, dict] = {}
        names = dict(self.cur)
        hashes: dict[str, str] = {}
        binds: list[tuple[str, str, str]] = []  # (node id, name, expr)
        dirty: list[str] = []

        for nid in order:
            node = by_id[nid]
            comp = comps.get(node["comp"])
            if not comp:
                results[nid] = {"err": "未知元件"}
                continue
            if node.get("disabled"):
                results[nid] = {"err": "已禁用"}
                continue
            t = self.types.get(comp.get("rt", ""), {})
            ins = []
            missing = False
            for i in range(len(t.get("inputs", []))):
                src = incoming[nid].get(i)
                if src is None:
                    ins.append(None)
                    missing = True
                else:
                    ins.append(names.get(src))
                    if names.get(src) is None:
                        missing = True
            expr = self._expr(node, comp, ins)
            h = hashlib.sha1(
                (node["comp"] + "\x00" + str(node.get("value", "")) + "\x00" +
                 "|".join(hashes.get(s, "?") for s in incoming[nid].values())).encode()
            ).hexdigest()
            hashes[nid] = h
            if expr is None:
                results[nid] = {"err": "缺输入" if missing else "表达式无法构造", "hash": h}
                continue
            cached = self.cache.get(nid)
            if cached and cached.get("hash") == h and cached.get("ok"):
                results[nid] = {k: cached.get(k) for k in ("value", "type", "err", "warn", "note", "noteTitle")}
                results[nid]["cached"] = True
                continue
            self.rev += 1
            name = f"n_{re.sub(r'[^A-Za-z0-9]', '_', nid)}_{self.rev}"
            names[nid] = name
            binds.append((nid, name, expr))
            dirty.append(nid)
            results[nid] = {"pending": True, "hash": h}

        if not binds:
            return {
                "results": {k: {kk: vv for kk, vv in v.items() if kk != "hash"} for k, v in results.items()},
                "recomputed": 0, "total": len(nodes), "ms": int((time.time() - t0) * 1000),
                "cached": len(nodes),
            }

        # 第一遍：绑定
        try:
            outs = self.batch([f"let {name} = {expr}" for _, name, expr in binds], timeout=90)
        except (EngineDead, TimeoutError) as exc:
            self.stop()
            return {"fatal": f"引擎中断：{exc}", "results": results, "recomputed": 0}

        ok_binds = []
        failed_names = {}
        for (nid, name, expr), out in zip(binds, outs):
            bad = bool(re.search(r"error:", out)) or "Variable not in scope" in out
            if bad:
                self.cache.pop(nid, None)
                self.cur.pop(nid, None)
                failed_names[name] = nid
                results[nid] = {"err": tidy_error(out), "hash": hashes[nid]}
            else:
                self.cur[nid] = name
                ok_binds.append((nid, name))
                results[nid].pop("pending", None)

        # 下游引用了一个已经失败的绑定：直接说「上游失败」，别让用户去读 not in scope
        for nid, r in results.items():
            if "err" not in r or nid in failed_names.values():
                continue
            for bad_name, bad_nid in failed_names.items():
                if bad_name in r["err"]:
                    node = by_id.get(bad_nid, {})
                    label = comps.get(node.get("comp"), {}).get("label", bad_nid)
                    r["err"] = f"上游失败：{label}"
                    break

        # 第二遍：类型与值
        cmds, keys = [], []
        for nid, name in ok_binds:
            cmds.append(f":t {name}")
            keys.append((nid, "type"))
            cmds.append(f"print ({name})")
            keys.append((nid, "value"))
        if cmds:
            try:
                outs2 = self.batch(cmds, timeout=90)
            except (EngineDead, TimeoutError) as exc:
                self.stop()
                return {"fatal": f"引擎中断：{exc}", "results": results, "recomputed": len(binds)}
        else:
            outs2 = []

        for (nid, field), out in zip(keys, outs2):
            r = results[nid]
            if field == "type":
                m = re.search(r"::(.*)$", out, re.S)
                r["type"] = clean_type(m.group(1)) if m else ""
            else:
                r["value"], r["warn"] = tidy_value(out)
        for nid, _ in ok_binds:
            r = results[nid]
            r.setdefault("value", "")
            r.setdefault("type", "")
            if not r["value"] and r.get("warn"):
                r["note"], r["noteTitle"] = describe_opaque(r.get("type", ""), r["warn"])
            if r["value"]:
                v = unescape_hs(r["value"])
                if r["type"] in ("String", "[Char]") and len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                    v = v[1:-1]
                r["value"] = v
            self.cache[nid] = {
                "hash": hashes[nid], "ok": True,
                "value": r.get("value", ""), "type": r.get("type", ""), "warn": r.get("warn"),
                "note": r.get("note"), "noteTitle": r.get("noteTitle"),
            }

        clean = {}
        for k, v in results.items():
            if "hash" in v:
                v = {kk: vv for kk, vv in v.items() if kk != "hash"}
            clean[k] = v
        return {
            "results": clean,
            "recomputed": len(binds),
            "total": len(nodes),
            "ms": int((time.time() - t0) * 1000),
        }


def tidy_error(out: str) -> str:
    lines = [l for l in out.splitlines() if l.strip()]
    txt = "\n".join(lines)
    txt = re.sub(r"^<interactive>:\d+:\d+: ", "", txt)
    txt = re.sub(r"^<interactive>:\d+:\d+-\d+: ", "", txt)
    txt = txt.replace("error: [GHC-", "[GHC-")
    txt = txt.replace("\u2022", "·").replace("•", "·")
    txt = "\n".join(re.sub(r"^\s*\?\s+", "· ", l) for l in txt.splitlines())
    return txt.strip()[:1200]


def describe_opaque(t: str, warn: str):
    """不能 Show 的值：给一行短标签，长解释放进 title。"""
    t = (t or "").strip()
    if warn and "Show" in warn:
        if t.startswith("(") and t.endswith(")"):
            depth, n = 0, 1
            for ch in t:
                if ch in "([":
                    depth += 1
                elif ch in ")]":
                    depth -= 1
                elif ch == "," and depth == 1:
                    n += 1
            if n > 1:
                kind = {2: "二元组", 3: "三元组", 4: "四元组"}.get(n, f"{n} 元组")
                return f"⟨{n} 项结果⟩", f"没有 Show 实例 · 用「{kind}·1」到「{kind}·{n}」拆开"
        return f"⟨{t or '值'}⟩", "没有 Show 实例 · 可以继续连线，只是打印不出来"
    return warn, ""


def unescape_hs(s: str) -> str:
    """把 show 出来的 \\NNNN / \\n 还原成人看的字。"""
    if "\\" not in s:
        return s
    out, i = [], 0
    simple = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt.isdigit():
                j = i + 1
                while j < len(s) and s[j].isdigit():
                    j += 1
                try:
                    out.append(chr(int(s[i + 1:j])))
                except ValueError:
                    out.append(s[i:j])
                i = j
                continue
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def tidy_value(out: str) -> tuple[str, str | None]:
    s = out.strip()
    if not s:
        return "", None
    if "No instance for" in s and "Show" in s:
        return "", "无 Show 实例（值存在，只是打印不出来）"
    if "*** Exception" in s or "Prelude.error" in s:
        msg = s.split("*** Exception:", 1)[-1].strip()
        return "", msg or "运行时异常"
    if re.search(r"error:", s):
        return "", tidy_error(s)
    if len(s) > 1600:
        s = s[:1600] + " …"
    return s, None
