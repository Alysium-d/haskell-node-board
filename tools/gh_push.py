#!/usr/bin/env python3
"""GitHub 设备码授权 + 建仓库 + 推送。

用法: python tools/gh_push.py [仓库名] [--private]

1. 向 GitHub 要一个设备码，打印出来；
2. 你在浏览器里打开 github.com/login/device，输入这个码，点授权；
3. 脚本拿到令牌后自动建仓库、推 main。
令牌只存在内存里，不落盘、不打印。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

CLIENT_ID = "178c6fc778ccc68e1d6a"  # GitHub CLI 的公开 client_id
API = "https://api.github.com"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
o = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(url, data, token=None):
    headers = {"Accept": "application/vnd.github+json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    return json.loads(o.open(req).read())


def main():
    name = "haskell-node-board"
    private = False
    args = [a for a in sys.argv[1:]]
    if args and not args[0].startswith("-"):
        name = args.pop(0)
    private = "--private" in args

    # ---- 设备码
    try:
        r = post("https://github.com/login/device/code", {"client_id": CLIENT_ID, "scope": "repo"})
    except Exception as exc:
        print(f"[!] 连不上 GitHub：{exc}", file=sys.stderr)
        return 1

    print()
    print("  ┌────────────────────────────────────────────────┐")
    print("  │  1. 在浏览器打开：  " + r["verification_uri"].ljust(24) + "│")
    print("  │  2. 输入这个码：    " + r["user_code"].ljust(24) + "│")
    print("  │  3. 点 Authorize 授权                          │")
    print("  └────────────────────────────────────────────────┘")
    print()
    sys.stdout.flush()

    # ---- 轮询
    interval = r.get("interval", 5)
    deadline = time.time() + 300
    token = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            t = post("https://github.com/login/oauth/access_token", {
                "client_id": CLIENT_ID, "device_code": r["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            })
        except Exception as exc:
            print(f"  [!] 网络错误：{exc}", file=sys.stderr)
            time.sleep(interval)
            continue
        if "access_token" in t:
            token = t["access_token"]
            break
        err = t.get("error", "")
        if err == "authorization_pending":
            print("  · 等你授权…", flush=True)
        elif err == "slow_down":
            interval += 5
        else:
            print(f"  [!] 授权失败：{t.get('error_description', err)}")
            return 1
    if not token:
        print("  [!] 五分钟内没有等到授权。重新跑一次这个脚本即可。")
        return 1
    print("  ✓ 已授权", flush=True)

    # ---- 拿用户名
    me = post(API + "/user", {}, token=token)
    login = me.get("login", "?")
    print(f"  ✓ 账号 {login}", flush=True)

    # ---- 建仓库（已存在就跳过）
    try:
        post(API + "/user/repos", {"name": name, "private": private,
                                   "description": "Haskell 函数白板：右键取元件、拖端口连线、常驻 GHCi 增量求值"},
             token=token)
        print(f"  ✓ 仓库 {login}/{name} 已创建（{'私有' if private else '公开'}）", flush=True)
    except Exception as exc:
        if "already exists" in str(exc):
            print(f"  · 仓库 {login}/{name} 已存在，直接推", flush=True)
        else:
            print(f"  [!] 建仓库失败：{exc}", file=sys.stderr)
            return 1

    # ---- 推送
    remote = f"https://x-access-token:{token}@github.com/{login}/{name}.git"
    env = dict(os.environ)
    def git(*a):
        r = subprocess.run(["git", *a], cwd=REPO_ROOT, env=env,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(r.stderr[-600:], file=sys.stderr)
            return False
        return True

    if not git("remote", "add", "origin", remote):
        if not git("remote", "set-url", "origin", remote):
            return 1
    # remote URL 含令牌，不能留在 config 里
    subprocess.run(["git", "remote", "remove", "origin"], cwd=REPO_ROOT, capture_output=True)
    if not git("push", "-u", remote, "main:main"):
        return 1
    print(f"  ✓ 推送完成 → https://github.com/{login}/{name}", flush=True)
    print(f"  （令牌只活在这次进程里；要再推就再跑一次本脚本）", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
