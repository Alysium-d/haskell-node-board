#!/usr/bin/env python3
"""函数白板的交互自检：真鼠标事件，读页面状态。

  python tools/nodetest.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

URL = "http://127.0.0.1:8771/"


def main():
    targets = cdp.http_json("/json")
    page = next((t for t in targets if t["type"] == "page"), targets[0])
    ws = cdp.WS(page["webSocketDebuggerUrl"])

    def js(expr, wait=0.0):
        r = ws.call("Runtime.evaluate", {
            "expression": expr, "awaitPromise": True, "returnByValue": True, "userGesture": True,
        })
        res = r.get("result", {})
        if res.get("subtype") == "error":
            raise RuntimeError(res.get("description", "")[:600])
        if wait:
            time.sleep(wait)
        return res.get("value")

    ws.call("Page.enable")
    ws.call("Emulation.setDeviceMetricsOverride", {
        "width": 1560, "height": 960, "deviceScaleFactor": 1, "mobile": False,
    })
    ws.call("Page.navigate", {"url": URL + "?audit=1&t=%d" % time.time()})
    time.sleep(4.0)

    out = {}
    a = json.loads(js("document.getElementById('audit-json').textContent"))
    out["boot"] = {
        "viewport": a["viewport"], "graph": a["graph"], "wires": a["wiresDrawn"],
        "overlaps": a["overlaps"], "status": a["status"], "docX": a["docOverflowX"],
    }

    # ---- 右键元件库
    js("""(()=>{const st=document.getElementById('stage');const r=st.getBoundingClientRect();
        st.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,
          clientX:r.left+700,clientY:r.top+600}));return 1})()""", 0.35)
    out["palette"] = {
        "open": js("!document.getElementById('palette').hidden"),
        "items": js("document.querySelectorAll('.nb-pal-item').length"),
        "box": js("JSON.stringify(document.getElementById('palette').getBoundingClientRect())"),
    }

    # ---- 搜「文本」并放一个
    js("""(()=>{const q=document.getElementById('pal-q');q.value='文本';
        q.dispatchEvent(new Event('input',{bubbles:true}));return document.querySelectorAll('.nb-pal-item').length})()""", 0.25)
    out["palette"]["filtered"] = js("document.querySelectorAll('.nb-pal-item').length")
    js("document.querySelector('.nb-pal-item').click()", 0.5)
    nid = js("S.graph.nodes[S.graph.nodes.length-1].id")
    out["added"] = js("JSON.stringify({nodes:S.graph.nodes.length, id:S.graph.nodes[S.graph.nodes.length-1].id, comp:S.graph.nodes[S.graph.nodes.length-1].comp})")

    # ---- 拖线：新文本 → g2 的输入（替换原来那条）
    drag = """(()=>{
      const from=document.querySelector('.node[data-id="%s"] .nb-port.out').getBoundingClientRect();
      const to=document.querySelector('.node[data-id="g2"] .nb-port.in').getBoundingClientRect();
      const a={x:from.left+from.width/2,y:from.top+from.height/2};
      const b={x:to.left+to.width/2,y:to.top+to.height/2};
      const mk=(x,y,t)=>new PointerEvent(t,{bubbles:true,cancelable:true,clientX:x,clientY:y,
        button:0,buttons:t==='pointerup'?0:1,pointerId:7,pointerType:'mouse',isPrimary:true});
      const el=document.querySelector('.node[data-id="%s"] .nb-port.out');
      el.dispatchEvent(mk(a.x,a.y,'pointerdown'));
      window.dispatchEvent(mk(a.x+30,a.y,'pointermove'));
      window.dispatchEvent(mk(b.x,b.y,'pointermove'));
      window.dispatchEvent(mk(b.x,b.y,'pointerup'));
      return 1})()""" % (nid, nid)
    js(drag, 1.0)
    out["wired"] = {
        "intoG2": js("JSON.stringify(S.graph.edges.filter(e=>e.to==='g2'))"),
        "g2": js("(document.querySelector('.nb-val[data-val=\"g2\"]')||{}).textContent")[:70],
        "g16": js("(document.querySelector('.nb-val[data-val=\"g16\"]')||{}).textContent")[:70],
        "status": js("document.getElementById('status-eval').textContent+' | '+document.getElementById('status-incr').textContent"),
    }

    # ---- 改文本节点的值，看下游跟着变
    js("""(()=>{const n=S.graph.nodes.find(x=>x.id==='%s');
        const ta=document.querySelector('.node[data-id="%s"] textarea');
        ta.value='def goal : forall (n : N), Eq N (add n n) n := id';
        n.value=ta.value; ta.dispatchEvent(new Event('input',{bubbles:true})); return 1})()""" % (nid, nid), 0.9)
    out["edited"] = {
        "g2err": js("(document.querySelector('.nb-val[data-val=\"g2\"]')||{}).textContent")[:70],
        "g16": js("(document.querySelector('.nb-val[data-val=\"g16\"]')||{}).textContent")[:90],
        "status": js("document.getElementById('status-eval').textContent+' | '+document.getElementById('status-incr').textContent"),
    }

    # ---- 撤销两次，回到原图
    js("undo(); undo();", 1.0)
    out["undo"] = {
        "nodes": js("S.graph.nodes.length"),
        "intoG2": js("JSON.stringify(S.graph.edges.filter(e=>e.to==='g2'))"),
        "g16": js("(document.querySelector('.nb-val[data-val=\"g16\"]')||{}).textContent")[:70],
    }

    # ---- 视角：缩小后节点框是否仍可用
    js("S.view.z=0.4; S.view.x=40; S.view.y=200; worldTransform();", 0.3)
    out["zoom"] = {
        "scale": js("S.view.z"),
        "portW": js("document.querySelector('.node[data-id=\"g1\"] .nb-port.out').getBoundingClientRect().width"),
    }

    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
