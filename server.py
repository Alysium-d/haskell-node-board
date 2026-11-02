#!/usr/bin/env python3
"""函数白板 · 服务端

一个常驻 GHCi、一张节点图、一套从工程导出函数生成的元件库。
只监听回环地址，只用标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import palette
from engine import Engine

APP = Path(__file__).resolve().parent
STATIC = APP / "static"
DATA = APP / "data"
RT = APP / "rt"
TYPO = Path("E:/wbws/typo_system/site/assets")
GRAPH_FILE = DATA / "graph.json"

ROOT = Path("E:/olib/verify/hask")
ENGINE = Engine(ROOT, RT)
BOOT_AT = time.time()


def comps_payload():
    out = []
    for c in palette.COMPS:
        item = {
            "id": c["id"],
            "label": c["label"],
            "cat": c["cat"],
            "kind": c.get("kind", "fn"),
            "desc": c.get("desc", ""),
        }
        if c.get("kind") == "value":
            item["vtype"] = c["vtype"]
            item["editor"] = c["editor"]
            item["inputs"] = []
            item["output"] = c["vtype"]
            item["sample"] = c.get("sample", "")
        else:
            t = ENGINE.types.get(c["rt"], {})
            item["inputs"] = t.get("inputs", [])
            item["output"] = t.get("output", "?")
            item["known"] = bool(t)
            item["rt"] = c["rt"]
        out.append(item)
    return out


def load_graph():
    if GRAPH_FILE.exists():
        try:
            return json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return palette.STARTER


def save_graph(g):
    DATA.mkdir(exist_ok=True)
    tmp = GRAPH_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(GRAPH_FILE)


class Handler(BaseHTTPRequestHandler):
    server_version = "HaskNodeBoard/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("BOARD_VERBOSE"):
            print("%s %s" % (self.address_string(), fmt % args))

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, p: Path):
        if not p.is_file():
            self.send_json({"error": "not found", "path": str(p)}, 404)
            return
        body = p.read_bytes()
        ext = p.suffix.lower()
        mime = {
            ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
            ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png",
        }.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self.send_file(STATIC / "index.html")
        if p.startswith("/static/"):
            return self.send_file(STATIC / p[len("/static/"):])
        if p.startswith("/typo/"):
            return self.send_file(TYPO / p[len("/typo/"):])

        if p == "/api/boot":
            return self.send_json({
                "root": str(ROOT).replace("\\", "/"),
                "comps": comps_payload(),
                "cats": palette.categories(),
                "graph": load_graph(),
                "engine": {"ready": ENGINE.ready, "error": ENGINE.error, "loadMs": ENGINE.load_ms,
                           "types": len(ENGINE.types)},
            })
        if p == "/api/engine":
            return self.send_json({
                "ready": ENGINE.ready, "error": ENGINE.error, "loadMs": ENGINE.load_ms,
                "types": len(ENGINE.types), "uptime": int(time.time() - ENGINE.started_at) if ENGINE.ready else 0,
            })
        if p == "/api/components":
            return self.send_json({"comps": comps_payload()})
        if p == "/api/graph":
            return self.send_json(load_graph())
        if p == "/api/samples":
            return self.send_json({"samples": [
                {"id": s["id"], "label": s["label"], "nodes": len(s["graph"]["nodes"])}
                for s in palette.SAMPLES
            ]})
        if p == "/api/sample":
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            sid = (q.get("id") or ["proof"])[0]
            for s in palette.SAMPLES:
                if s["id"] == sid:
                    return self.send_json(s["graph"])
            return self.send_json(palette.STARTER)
        return self.send_json({"error": "no route", "path": p}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        b = self.body()

        if p == "/api/eval":
            t0 = time.time()
            if not ENGINE.ready:
                r = ENGINE.start()
                if not r.get("ok"):
                    return self.send_json({"engine": r, "results": {}, "fatal": "引擎未能启动：" + (r.get("error") or "")})
            try:
                res = ENGINE.eval_graph(b.get("nodes") or [], b.get("edges") or [])
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                return self.send_json({"fatal": str(exc)[:400], "results": {}, "ms": int((time.time() - t0) * 1000)})
            res["serverMs"] = int((time.time() - t0) * 1000)
            return self.send_json(res)

        if p == "/api/graph":
            save_graph(b)
            return self.send_json({"ok": True})

        if p == "/api/restart":
            ENGINE.stop()
            r = ENGINE.start()
            return self.send_json({"engine": r, "comps": comps_payload()})



        return self.send_json({"error": "no route", "path": p}, 404)


def warm():
    t0 = time.time()
    r = ENGINE.start()
    print(f"[白板] 引擎 {'就绪' if r.get('ok') else '失败'} · {len(ENGINE.types)} 个元件有类型 · "
          f"{int((time.time()-t0)*1000)}ms", flush=True)
    if not r.get("ok"):
        print("[白板] " + (r.get("error") or "?"), flush=True)


def doctor(args) -> int:
    """双击启动时的体检：Python、GHC、工程、端口，一次说清。"""
    import subprocess
    import sys

    ok = True
    print("函数白板 · 体检", flush=True)
    print(f"  Python   {sys.version.split()[0]}  ({sys.executable})", flush=True)
    ghc = os.environ.get("BOARD_GHC") or "ghc"
    try:
        out = subprocess.run([ghc, "--numeric-version"], capture_output=True, text=True, timeout=20)
        ver = (out.stdout or "").strip()
        if out.returncode == 0 and ver:
            print(f"  GHC      {ver}  ({ghc})", flush=True)
        else:
            ok = False
            print(f"  GHC      ！跑不起来：{ghc}", flush=True)
    except Exception as exc:
        ok = False
        print(f"  GHC      ！{ghc}：{exc}", flush=True)
    print(f"  工程     {ROOT}  {'[ok]' if (ROOT / 'src').exists() else '！没有 src/'}", flush=True)
    if not (ROOT / "src").exists():
        ok = False
    print(f"  运行时   {(RT / 'BoardRt.hs')}  {'[ok]' if (RT / 'BoardRt.hs').exists() else '！缺 BoardRt.hs'}", flush=True)
    if not (RT / "BoardRt.hs").exists():
        ok = False
    busy = alive(f"http://{args.host}:{args.port}/")
    print(f"  端口     {args.port}  {'已被本白板占用（会复用）' if busy else '空闲'}", flush=True)
    print("  结论     " + ("可以启动" if ok else "有项目不可用，见上"), flush=True)
    return 0 if ok else 1


def alive(url: str) -> bool:
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(url + "api/engine", timeout=0.7) as r:
            return r.status == 200
    except Exception:
        return False


def open_window(url: str, app_mode: bool):
    import webbrowser

    if not app_mode:
        webbrowser.open(url)
        return
    cands = [
        r"C://Program Files (x86)//Microsoft//Edge//Application//msedge.exe",
        r"C://Program Files//Microsoft//Edge//Application//msedge.exe",
        r"C://Program Files//Google//Chrome//Application//chrome.exe",
    ]
    exe = next((c for c in cands if Path(c).exists()), None)
    w, h = 1560, 980
    try:  # 屏幕小就别开一个比屏幕还大的窗口
        import ctypes

        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        if sw and sh:
            w, h = min(w, max(1000, sw - 80)), min(h, max(700, sh - 120))
    except Exception:
        pass
    if exe:
        try:
            import subprocess

            # 不继承控制台：否则 Edge 自己的日志会以 GBK 混进这个窗口
            subprocess.Popen(
                [exe, f"--app={url}", f"--window-size={w},{h}"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return
        except Exception:
            pass
    webbrowser.open(url)


def main():
    global ROOT
    ap = argparse.ArgumentParser(description="函数白板 · Haskell 节点连线")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--port", type=int, default=8771)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--app", action="store_true", help="以独立窗口打开（Edge --app）")
    ap.add_argument("--doctor", action="store_true", help="只做体检，不启动服务")
    args = ap.parse_args()
    ROOT = Path(args.root).resolve()
    ENGINE.root = ROOT

    if args.doctor:
        return doctor(args)

    url = f"http://{args.host}:{args.port}/"
    if alive(url):
        print(f"[白板] {url} 已在运行，直接开窗口。", flush=True)
        open_window(url, args.app or args.open)
        return

    try:
        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"[白板] 端口 {args.port} 被占用：{exc}", flush=True)
        print(f"[白板] 换个端口：python server.py --port {args.port + 1}", flush=True)
        return

    threading.Thread(target=warm, daemon=True).start()
    print(f"[白板] {url}", flush=True)
    print("[白板] 关掉这个窗口即停止。", flush=True)
    if args.open or args.app:
        open_window(url, args.app)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[白板] 停。", flush=True)
        ENGINE.stop()


if __name__ == "__main__":
    main()
