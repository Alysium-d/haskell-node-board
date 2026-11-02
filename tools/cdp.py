#!/usr/bin/env python3
"""极小的 CDP 客户端：驱动无头 Edge 做交互检查。只用标准库。

先启动浏览器：
  msedge --headless=new --disable-gpu --remote-debugging-port=9222 about:blank

用法：
  python tools/cdp.py open "http://127.0.0.1:8770/?audit=1"
  python tools/cdp.py eval "document.querySelector('#btn-check').click()"
  python tools/cdp.py audit
  python tools/cdp.py shot out.png [width height]
"""
import base64
import json
import os
import socket
import struct
import sys
import time
import urllib.request

PORT = int(os.environ.get("CDP_PORT", "9222"))


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(path):
    with _OPENER.open(f"http://127.0.0.1:{PORT}{path}", timeout=10) as r:
        return json.loads(r.read().decode())


class WS:
    def __init__(self, url):
        assert url.startswith("ws://")
        host_port, path = url[5:].split("/", 1)
        host, port = host_port.split(":")
        self.s = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.mid = 0

    def send(self, obj):
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        head += mask
        self.s.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        b1, b2 = self._read(2)
        op = b1 & 0x0F
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read(8))[0]
        payload = self._read(length)
        if op == 0x8:
            raise ConnectionError("close frame")
        return json.loads(payload.decode())

    def call(self, method, params=None):
        self.mid += 1
        mid = self.mid
        self.send({"id": mid, "method": method, "params": params or {}})
        while True:
            msg = self.recv()
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(json.dumps(msg["error"])[:400])
                return msg.get("result", {})


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    targets = http_json("/json")
    page = next((t for t in targets if t["type"] == "page"), targets[0])
    ws = WS(page["webSocketDebuggerUrl"])

    if cmd == "open":
        ws.call("Page.enable")
        ws.call("Page.navigate", {"url": sys.argv[2]})
        time.sleep(float(os.environ.get("CDP_WAIT", "2.2")))
        print("ok")
    elif cmd == "eval":
        r = ws.call(
            "Runtime.evaluate",
            {"expression": sys.argv[2], "awaitPromise": True, "returnByValue": True, "userGesture": True},
        )
        res = r.get("result", {})
        print(json.dumps(res.get("value", res.get("description", res)), ensure_ascii=False))
    elif cmd == "audit":
        js = "document.getElementById('audit-json') ? document.getElementById('audit-json').textContent : 'NO AUDIT'"
        r = ws.call("Runtime.evaluate", {"expression": js, "returnByValue": True})
        print(r["result"].get("value", ""))
    elif cmd == "shot":
        path = sys.argv[2]
        if len(sys.argv) > 4:
            ws.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": int(sys.argv[3]), "height": int(sys.argv[4]), "deviceScaleFactor": 1, "mobile": False},
            )
            time.sleep(0.6)
        r = ws.call("Page.captureScreenshot", {"format": "png"})
        open(path, "wb").write(base64.b64decode(r["data"]))
        print(path)
    else:
        print("unknown command")


if __name__ == "__main__":
    main()
