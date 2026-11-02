/* 函数白板 · 前端
   没有框架、没有构建步骤。节点是 DOM，连线是 SVG，坐标都在世界坐标系里。 */

const S = {
  root: "",
  comps: [],
  byId: {},
  cats: [],
  graph: { name: "未命名", nodes: [], edges: [] },
  view: { x: 60, y: 40, z: 1 },
  sel: null,          // {type:'node'|'edge', id}
  drag: null,
  engine: { ready: false, error: "", types: 0 },
  history: [],
  future: [],
  evalTimer: null,
  saveTimer: null,
  busy: false,
  pal: { open: false, at: { x: 0, y: 0 }, filter: "", index: 0, items: [] },
};

const $ = (s, r = document) => (r || document).querySelector(s);
const $$ = (s, r = document) => [...(r || document).querySelectorAll(s)];
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const txt = await r.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = { raw: txt }; }
  if (!r.ok) throw new Error("HTTP " + r.status + " " + (data && data.error ? data.error : ""));
  return data;
}

/* ------------------------------------------------------------ 图的操作 -- */

let seq = 0;
const newId = () => "n" + Date.now().toString(36).slice(-4) + (seq++).toString(36);

function snapshot() {
  S.history.push(JSON.stringify(S.graph));
  if (S.history.length > 60) S.history.shift();
  S.future.length = 0;
}

function undo() {
  if (!S.history.length) return;
  S.future.push(JSON.stringify(S.graph));
  S.graph = JSON.parse(S.history.pop());
  S.sel = null;
  renderAll();
  scheduleEval(60);
  scheduleSave();
}

function redo() {
  if (!S.future.length) return;
  S.history.push(JSON.stringify(S.graph));
  S.graph = JSON.parse(S.future.pop());
  S.sel = null;
  renderAll();
  scheduleEval(60);
  scheduleSave();
}

function addNode(compId, x, y, extra = {}) {
  const c = S.byId[compId];
  if (!c) return null;
  snapshot();
  const n = {
    id: newId(), comp: compId,
    x: Math.round(x / 8) * 8, y: Math.round(y / 8) * 8,
    ...(c.kind === "value" ? { value: c.sample || "" } : {}),
    ...extra,
  };
  S.graph.nodes.push(n);
  S.sel = { type: "node", id: n.id };
  renderAll();
  scheduleEval(120);
  scheduleSave();
  flash(n.id);
  return n;
}

function removeNode(id) {
  snapshot();
  S.graph.nodes = S.graph.nodes.filter((n) => n.id !== id);
  S.graph.edges = S.graph.edges.filter((e) => e.from !== id && e.to !== id);
  S.sel = null;
  renderAll();
  scheduleEval(60);
  scheduleSave();
}

function duplicateNode(id) {
  const n = S.graph.nodes.find((x) => x.id === id);
  if (!n) return;
  snapshot();
  const copy = { ...n, id: newId(), x: n.x + 28, y: n.y + 28 };
  S.graph.nodes.push(copy);
  S.sel = { type: "node", id: copy.id };
  renderAll();
  scheduleEval(120);
  scheduleSave();
}

function inEdges(nodeId) {
  return S.graph.edges.filter((e) => e.to === nodeId);
}

function connect(from, to, toPort) {
  const a = S.graph.nodes.find((n) => n.id === from);
  const b = S.graph.nodes.find((n) => n.id === to);
  if (!a || !b || from === to) return false;
  const ca = S.byId[a.comp], cb = S.byId[b.comp];
  const outT = ca.kind === "value" ? ca.vtype : ca.output;
  const inT = (cb.inputs || [])[toPort];
  if (!compatible(outT, inT)) {
    toast(`接不上：${outT} 不是 ${inT || "?"}`);
    flashPort(to, toPort);
    return false;
  }
  if (reaches(to, from)) {
    toast("接不上：会绕成环");
    flashPort(to, toPort);
    return false;
  }
  snapshot();
  S.graph.edges = S.graph.edges.filter((e) => !(e.to === to && (e.toPort || 0) === toPort));
  S.graph.edges.push({ from, to, toPort });
  renderWires();
  scheduleEval(80);
  scheduleSave();
  return true;
}

function reaches(start, target, seen = new Set()) {
  if (start === target) return true;
  if (seen.has(start)) return false;
  seen.add(start);
  return S.graph.edges.filter((e) => e.from === start).some((e) => reaches(e.to, target, seen));
}

/* ------------------------------------------------------------ 类型匹配 -- */

function normType(t) {
  return String(t || "").replace(/\s+/g, " ").replace(/\[Char\]/g, "String").trim();
}
function isVar(t) {
  return /^[a-z][A-Za-z0-9_']*$/.test(t) && !["forall"].includes(t);
}
function topElements(t) {
  if (!(t.startsWith("(") && t.endsWith(")"))) return null;
  const inner = t.slice(1, -1);
  let depth = 0, cur = [], parts = [];
  for (const ch of inner) {
    if ("([{".includes(ch)) depth++;
    if (")]}".includes(ch)) depth--;
    if (ch === "," && depth === 0) { parts.push(cur.join("")); cur = []; continue; }
    cur.push(ch);
  }
  parts.push(cur.join(""));
  return parts.map((p) => p.trim());
}
function listOf(t) {
  if (t.startsWith("[") && t.endsWith("]")) return t.slice(1, -1).trim();
  return null;
}
function compatible(a, b) {
  a = normType(a); b = normType(b);
  if (!a || !b || a === "?" || b === "?") return true;
  if (a === b) return true;
  if (isVar(a) || isVar(b)) return true;
  const ta = topElements(a), tb = topElements(b);
  if (ta && tb) return ta.length === tb.length && ta.every((x, i) => compatible(x, tb[i]));
  const la = listOf(a), lb = listOf(b);
  if (la && lb) return compatible(la, lb);
  return false;
}

/* ------------------------------------------------------------ 渲染 -- */

function worldTransform() {
  const w = $("#world");
  w.style.transform = `translate(${S.view.x}px, ${S.view.y}px) scale(${S.view.z})`;
  // 端口在屏幕上保持可点：反向缩放
  w.style.setProperty("--pz", clamp(1 / S.view.z, 0.55, 2.4).toFixed(3));
  const st = $("#stage");
  st.style.setProperty("--gx", (S.view.x % (24 * S.view.z)) + "px");
  st.style.setProperty("--gy", (S.view.y % (24 * S.view.z)) + "px");
  st.style.backgroundSize = 24 * S.view.z + "px " + 24 * S.view.z + "px";
}

function renderAll() {
  renderNodes();
  renderWires();
  worldTransform();
  updateCounts();
  $("#empty").hidden = S.graph.nodes.length > 0;
}

function updateCounts() {
  $("#graph-name").textContent = S.graph.name || "未命名";
  $("#graph-count").textContent = `${S.graph.nodes.length} 节点 · ${S.graph.edges.length} 连线`;
}

function renderNodes() {
  const box = $("#nodes");
  box.innerHTML = "";
  for (const n of S.graph.nodes) box.appendChild(nodeEl(n));
  measurePorts();
}

function nodeEl(n) {
  const c = S.byId[n.comp];
  if (!c) {
    const box = document.createElement("div");
    box.className = "node err";
    box.dataset.id = n.id;
    box.style.left = n.x + "px";
    box.style.top = n.y + "px";
    box.innerHTML = `<div class="nb-h"><i class="d" style="--c:#ff6b4a"></i><span class="t">未知元件</span><span class="b">${esc(n.comp)}</span></div>
      <div class="nb-b"><div class="nb-val err">这张图里有一个元件不在当前库里（${esc(n.comp)}）。删掉它，或者把库补齐。</div></div>`;
    return box;
  }
  const cat = S.cats.find((x) => x.id === c.cat) || { color: "#9aa397", label: "" };
  const el = document.createElement("div");
  el.className = "node" + (n.disabled ? " disabled" : "");
  el.dataset.id = n.id;
  el.style.left = n.x + "px";
  el.style.top = n.y + "px";
  if (S.sel && S.sel.type === "node" && S.sel.id === n.id) el.classList.add("sel");

  const head = document.createElement("div");
  head.className = "nb-h";
  head.title = `${c.id}${c.desc ? " · " + c.desc : ""}`;
  head.innerHTML =
    `<i class="d" style="--c:${cat.color}"></i>` +
    `<span class="t">${esc(c.label)}</span>` +
    (n.disabled ? `<span class="off">off</span>` : `<span class="b">${esc(cat.label)}</span>`);
  el.appendChild(head);

  const body = document.createElement("div");
  body.className = "nb-b";
  (c.inputs || []).forEach((t, i) => {
    const row = document.createElement("div");
    row.className = "nb-prow";
    row.innerHTML =
      `<i class="nb-port in" data-port="in:${i}" title="输入 ${i + 1}：${esc(t)}"></i>` +
      `<span class="nb-ty${isVar(normType(t)) ? " var" : ""}" title="${esc(t)}">${esc(t)}</span>`;
    body.appendChild(row);
  });

  const orow = document.createElement("div");
  orow.className = "nb-prow out";
  const outT = c.kind === "value" ? c.vtype : c.output;
  orow.innerHTML =
    `<span class="nb-ty" title="${esc(outT)}">${esc(outT)}</span>` +
    `<i class="nb-port out" data-port="out:0" title="输出：${esc(outT)}"></i>`;
  body.appendChild(orow);

  if (c.kind === "value") {
    const ta = document.createElement("textarea");
    ta.className = "nb-lit" + (c.editor === "int" ? " num" : "");
    ta.value = n.value || "";
    ta.spellcheck = false;
    ta.placeholder = c.editor === "int" ? "0" : "文本…";
    ta.addEventListener("input", () => {
      n.value = ta.value;
      autoGrow(ta);
      scheduleEval(320);
      scheduleSave();
    });
    ta.addEventListener("pointerdown", (e) => e.stopPropagation());
    body.appendChild(ta);
    requestAnimationFrame(() => autoGrow(ta));
  } else {
    const val = document.createElement("div");
    val.className = "nb-val blank";
    val.dataset.val = n.id;
    val.textContent = n.disabled ? "已禁用" : S.engine.ready ? "…" : "等引擎";
    body.appendChild(val);
  }
  el.appendChild(body);
  return el;
}

function autoGrow(ta) {
  ta.style.height = "auto";
  ta.style.height = clamp(ta.scrollHeight, 40, 220) + "px";
}

function measurePorts() {
  S.portLocal = {};
  for (const el of $$(".node")) {
    const id = el.dataset.id;
    S.portLocal[id] = {};
    for (const p of $$(".nb-port", el)) {
      S.portLocal[id][p.dataset.port] = {
        x: p.offsetLeft + p.offsetWidth / 2,
        y: p.offsetTop + p.offsetHeight / 2,
      };
    }
  }
}

function portPos(nodeId, key) {
  const n = S.graph.nodes.find((x) => x.id === nodeId);
  const l = S.portLocal && S.portLocal[nodeId] && S.portLocal[nodeId][key];
  if (!n || !l) return null;
  return { x: n.x + l.x, y: n.y + l.y };
}

function renderWires() {
  const g = $("#wire-layer");
  g.innerHTML = "";
  const ns = "http://www.w3.org/2000/svg";
  S.graph.edges.forEach((e, i) => {
    const a = portPos(e.from, "out:0");
    const b = portPos(e.to, `in:${e.toPort || 0}`);
    if (!a || !b) return;
    const d = curve(a, b);
    const hit = document.createElementNS(ns, "path");
    hit.setAttribute("d", d);
    hit.setAttribute("class", "wire hit");
    hit.dataset.i = i;
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", d);
    p.setAttribute("class", "wire" + (S.sel && S.sel.type === "edge" && S.sel.id === i ? " sel" : ""));
    p.dataset.i = i;
    g.append(hit, p);
  });
  // 输入端口是否已连
  $$(".nb-port.in").forEach((p) => p.classList.remove("linked"));
  for (const e of S.graph.edges) {
    const el = $(`.node[data-id="${e.to}"] .nb-port[data-port="in:${e.toPort || 0}"]`);
    if (el) el.classList.add("linked");
  }
}

function curve(a, b) {
  const dx = Math.max(40, Math.abs(b.x - a.x) * 0.42);
  return `M${a.x.toFixed(1)} ${a.y.toFixed(1)} C${(a.x + dx).toFixed(1)} ${a.y.toFixed(1)} ${(b.x - dx).toFixed(1)} ${b.y.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}

function flash(id) {
  const el = $(`.node[data-id="${id}"]`);
  if (el) { el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 520); }
}
function flashPort(nodeId, port) {
  const el = $(`.node[data-id="${nodeId}"] .nb-port[data-port="in:${port}"]`);
  if (!el) return;
  el.classList.add("bad");
  setTimeout(() => el.classList.remove("bad"), 600);
}

/* ------------------------------------------------------------ 交互 -- */

function toWorld(clientX, clientY) {
  const r = $("#stage").getBoundingClientRect();
  return {
    x: (clientX - r.left - S.view.x) / S.view.z,
    y: (clientY - r.top - S.view.y) / S.view.z,
  };
}

function initStage() {
  const stage = $("#stage");

  stage.addEventListener("pointerdown", (e) => {
    if (e.button === 1) { /* 中键也平移 */ }
    if (e.button !== 0 && e.button !== 1) return;
    // 不 preventDefault 的话，浏览器会开始原生选择；一拖就成了「拖拽选中文本」，
    // 松手可能导航到别处（上一版就是这么跳走的）。输入框除外。
    const inField = e.target.closest("textarea, input");
    if (!inField) e.preventDefault();
    closePalette();
    $("#node-menu").hidden = true;

    const portEl = e.target.closest(".nb-port");
    if (portEl && portEl.classList.contains("out")) {
      const nodeEl2 = portEl.closest(".node");
      startWire(nodeEl2.dataset.id, e);
      return;
    }
    if (portEl && portEl.classList.contains("in")) {
      // 从输入端起：把这个输入上已有的线摘下来重接
      const nodeEl2 = portEl.closest(".node");
      const port = +portEl.dataset.port.split(":")[1];
      const existing = S.graph.edges.findIndex((x) => x.to === nodeEl2.dataset.id && (x.toPort || 0) === port);
      if (existing >= 0) {
        const from = S.graph.edges[existing].from;
        snapshot();
        S.graph.edges.splice(existing, 1);
        renderWires();
        startWire(from, e);
        scheduleEval(80);
        scheduleSave();
      }
      return;
    }

    if (e.target.closest(".wire")) {
      S.sel = { type: "edge", id: +e.target.dataset.i };
      renderWires();
      return;
    }

    const nodeEl2 = e.target.closest(".node");
    if (nodeEl2) {
      const id = nodeEl2.dataset.id;
      S.sel = { type: "node", id };
      selectNodeVisual();
      if (e.target.closest(".nb-h")) startNodeDrag(id, e);
      return;
    }

    S.sel = null;
    selectNodeVisual();
    startPan(e);
  });

  stage.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    if (e.target.closest(".wire")) {
      S.sel = { type: "edge", id: +e.target.dataset.i };
      renderWires();
      return;
    }

    const nodeEl2 = e.target.closest(".node");
    if (nodeEl2) {
      S.sel = { type: "node", id: nodeEl2.dataset.id };
      selectNodeVisual();
      openNodeMenu(e.clientX, e.clientY);
      return;
    }
    const w = toWorld(e.clientX, e.clientY);
    S.pal.at = w;
    openPalette(e.clientX, e.clientY);
  });

  stage.addEventListener("dragstart", (e) => e.preventDefault());
  stage.addEventListener("selectstart", (e) => {
    if (!e.target.closest("textarea, input")) e.preventDefault();
  });

  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const wx = (mx - S.view.x) / S.view.z, wy = (my - S.view.y) / S.view.z;
    const factor = Math.exp(-e.deltaY * 0.0016);
    S.view.z = clamp(S.view.z * factor, 0.3, 1.9);
    S.view.x = mx - wx * S.view.z;
    S.view.y = my - wy * S.view.z;
    worldTransform();
    if (S.pal.open) closePalette();
  }, { passive: false });

  stage.addEventListener("dblclick", (e) => {
    if (e.target.closest(".node")) return;
    const w = toWorld(e.clientX, e.clientY);
    S.pal.at = w;
    openPalette(e.clientX, e.clientY);
  });

  $("#wire-layer").addEventListener("click", (e) => {
    const p = e.target.closest(".wire");
    if (!p || p.classList.contains("temp")) return;
    S.sel = { type: "edge", id: +p.dataset.i };
    renderWires();
  });
}

function selectNodeVisual() {
  $$(".node").forEach((el) => {
    el.classList.toggle("sel", !!(S.sel && S.sel.type === "node" && S.sel.id === el.dataset.id));
  });
}

function startPan(e) {
  S.drag = { mode: "pan", sx: e.clientX, sy: e.clientY, vx: S.view.x, vy: S.view.y };
  $("#stage").classList.add("panning");
  const move = (ev) => {
    if (!S.drag || S.drag.mode !== "pan") return;
    S.view.x = S.drag.vx + (ev.clientX - S.drag.sx);
    S.view.y = S.drag.vy + (ev.clientY - S.drag.sy);
    worldTransform();
  };
  const up = () => {
    S.drag = null;
    $("#stage").classList.remove("panning");
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function startNodeDrag(id, e) {
  const n = S.graph.nodes.find((x) => x.id === id);
  if (!n) return;
  const start = { x: e.clientX, y: e.clientY, nx: n.x, ny: n.y };
  let moved = false;
  snapshot();
  S.drag = { mode: "node", id };
  const move = (ev) => {
    const dx = (ev.clientX - start.x) / S.view.z;
    const dy = (ev.clientY - start.y) / S.view.z;
    if (Math.hypot(dx, dy) > 2) moved = true;
    n.x = Math.round((start.nx + dx) / 8) * 8;
    n.y = Math.round((start.ny + dy) / 8) * 8;
    const el = $(`.node[data-id="${id}"]`);
    if (el) { el.style.left = n.x + "px"; el.style.top = n.y + "px"; }
    renderWires();
  };
  const up = () => {
    if (!moved && S.history.length) S.history.pop();
    S.drag = null;
    scheduleSave();
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function startWire(fromId, e) {
  const stage = $("#stage");
  stage.classList.add("wiring");
  let alive = true;
  const from = portPos(fromId, "out:0");
  if (!from) return;
  const temp = document.createElementNS("http://www.w3.org/2000/svg", "path");
  temp.setAttribute("class", "wire temp");
  $("#wire-layer").appendChild(temp);

  const fromComp = S.byId[(S.graph.nodes.find((n) => n.id === fromId) || {}).comp] || {};
  const outT = fromComp.kind === "value" ? fromComp.vtype : fromComp.output;
  // 能接的输入端口高亮
  $$(".nb-port.in").forEach((p) => {
    const nodeId = p.closest(".node").dataset.id;
    const port = +(p.dataset.port.split(":")[1]);
    if (nodeId === fromId) return;
    const c = S.byId[(S.graph.nodes.find((n) => n.id === nodeId) || {}).comp] || {};
    const inT = (c.inputs || [])[port];
    p.classList.add(compatible(outT, inT) ? "compat" : "bad");
  });

  const move = (ev) => {
    const w = toWorld(ev.clientX, ev.clientY);
    temp.setAttribute("d", curve(from, w));
  };
  move(e);

  S.drag = { mode: "wire", cancel: () => { alive = false; cleanup(); } };
  const cleanup = () => {
    stage.classList.remove("wiring");
    temp.remove();
    $$(".nb-port").forEach((p) => p.classList.remove("compat", "bad"));
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  const up = (ev) => {
    if (!alive) return;
    cleanup();
    S.drag = null;
    const hit = document.elementFromPoint(ev.clientX, ev.clientY);
    const portEl = hit && hit.closest && hit.closest(".nb-port");
    if (portEl && portEl.classList.contains("in")) {
      const nodeId = portEl.closest(".node").dataset.id;
      const port = +(portEl.dataset.port.split(":")[1]);
      connect(fromId, nodeId, port);
    }
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

/* ------------------------------------------------------------ 元件库 -- */

function openPalette(cx, cy) {
  const pal = $("#palette");
  pal.hidden = false;
  S.pal.open = true;
  S.pal.filter = "";
  S.pal.index = 0;
  $("#pal-q").value = "";
  renderPalette();
  const w = pal.offsetWidth, h = pal.offsetHeight;
  pal.style.left = clamp(cx, 8, window.innerWidth - w - 8) + "px";
  pal.style.top = clamp(cy, 8, window.innerHeight - h - 8) + "px";
  setTimeout(() => $("#pal-q").focus(), 0);
}

function closePalette() {
  if (!S.pal.open) return;
  S.pal.open = false;
  $("#palette").hidden = true;
  S.pal.items = [];
}

function paletteItems() {
  const q = S.pal.filter.trim().toLowerCase();
  const out = [];
  for (const c of S.comps) {
    const hay = [c.label, c.id, c.desc, c.output, ...(c.inputs || [])].join(" ").toLowerCase();
    if (q && !hay.includes(q)) continue;
    out.push(c);
  }
  return out;
}

function renderPalette() {
  const list = $("#pal-list");
  const items = paletteItems();
  S.pal.items = items;
  S.pal.index = clamp(S.pal.index, 0, Math.max(0, items.length - 1));
  const byCat = new Map();
  for (const it of items) {
    if (!byCat.has(it.cat)) byCat.set(it.cat, []);
    byCat.get(it.cat).push(it);
  }
  const html = [];
  for (const cat of S.cats) {
    const group = byCat.get(cat.id);
    if (!group || !group.length) continue;
    html.push(`<div class="nb-pal-cat"><i style="background:${cat.color}"></i>${esc(cat.label)} <span style="color:#3f4439">${group.length}</span></div>`);
    for (const it of group) {
      const idx = items.indexOf(it);
      html.push(
        `<button class="nb-pal-item${idx === S.pal.index ? " on" : ""}" data-idx="${idx}">` +
        `<span class="l">${esc(it.label)}</span>` +
        `<span class="ty">${esc(it.output || "?")}</span>` +
        `<span class="s">${esc(it.desc || it.id)}</span></button>`
      );
    }
  }
  list.innerHTML = html.length ? html.join("") : `<div class="nb-pal-empty">没有匹配。试试点「内核」「求值」这些分类名，或直接搜类型 Term。</div>`;
  $("#pal-count").textContent = `${items.length} 个`;
  const need = S.comps.filter((c) => c.known === false).length;
  $("#pal-foot").textContent = `${S.comps.length} 个元件 · 端口类型取自 GHC 的 :t` + (need ? ` · ${need} 个类型未取到` : "");

  $$(".nb-pal-item", list).forEach((b) => {
    b.addEventListener("click", () => {
      const it = S.pal.items[+b.dataset.idx];
      closePalette();
      addNode(it.id, S.pal.at.x, S.pal.at.y);
    });
    b.addEventListener("mouseenter", () => {
      S.pal.index = +b.dataset.idx;
      $$(".nb-pal-item", list).forEach((x) => x.classList.toggle("on", x === b));
    });
  });
}

function initPalette() {
  $("#pal-q").addEventListener("input", (e) => {
    S.pal.filter = e.target.value;
    S.pal.index = 0;
    renderPalette();
  });
  $("#pal-q").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); S.pal.index = clamp(S.pal.index + 1, 0, S.pal.items.length - 1); renderPalette(); scrollPal(); }
    if (e.key === "ArrowUp") { e.preventDefault(); S.pal.index = clamp(S.pal.index - 1, 0, S.pal.items.length - 1); renderPalette(); scrollPal(); }
    if (e.key === "Enter") {
      e.preventDefault();
      const it = S.pal.items[S.pal.index];
      if (it) { closePalette(); addNode(it.id, S.pal.at.x, S.pal.at.y); }
    }
    if (e.key === "Escape") closePalette();
  });
  document.addEventListener("pointerdown", (e) => {
    if (!S.pal.open) return;
    if (e.target.closest("#palette")) return;
    closePalette();
  }, true);
}

function scrollPal() {
  const el = $(".nb-pal-item.on");
  if (el) el.scrollIntoView({ block: "nearest" });
}

/* ------------------------------------------------------------ 节点菜单 -- */

function openNodeMenu(cx, cy) {
  const m = $("#node-menu");
  m.hidden = false;
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = clamp(cx, 8, window.innerWidth - w - 8) + "px";
  m.style.top = clamp(cy, 8, window.innerHeight - h - 8) + "px";
}

function initNodeMenu() {
  $("#node-menu").addEventListener("click", (e) => {
    const act = e.target.dataset.act;
    if (!act || !S.sel || S.sel.type !== "node") return;
    const id = S.sel.id;
    $("#node-menu").hidden = true;
    if (act === "del") removeNode(id);
    if (act === "dup") duplicateNode(id);
    if (act === "dis") {
      const n = S.graph.nodes.find((x) => x.id === id);
      if (n) {
        snapshot();
        n.disabled = !n.disabled;
        renderAll();
        scheduleEval(60);
        scheduleSave();
      }
    }
  });
  document.addEventListener("pointerdown", (e) => {
    if (!e.target.closest("#node-menu")) $("#node-menu").hidden = true;
    if (!e.target.closest("#sample-menu") && !e.target.closest("#btn-sample")) $("#sample-menu").hidden = true;
  }, true);
}

/* ------------------------------------------------------------ 求值 -- */

function scheduleEval(ms = 200) {
  clearTimeout(S.evalTimer);
  S.evalTimer = setTimeout(evaluate, ms);
}

async function evaluate() {
  if (!S.engine.ready) return;
  if (S.busy) { S.evalQueued = true; return; }
  if (!S.graph.nodes.length) {
    $("#status-eval").textContent = "空画布";
    $("#status-incr").textContent = "";
    return;
  }
  S.busy = true;
  $("#status-eval").textContent = "计算中…";
  $("#status-eval").className = "";
  try {
    const r = await api("/api/eval", { method: "POST", body: { nodes: S.graph.nodes, edges: S.graph.edges } });
    if (r.fatal) {
      toast(r.fatal);
      $("#status-eval").textContent = "引擎错误";
      $("#status-eval").className = "bad";
      return;
    }
    applyResults(r.results || {});
    const cached = (r.total || 0) - (r.recomputed || 0);
    $("#status-eval").textContent = `算完 · ${r.ms}ms`;
    $("#status-eval").className = "ok";
    $("#status-incr").textContent = `本次重算 ${r.recomputed} 个 · 沿用 ${cached} 个`;
  } catch (e) {
    $("#status-eval").textContent = "求值失败：" + e.message;
    $("#status-eval").className = "bad";
  } finally {
    S.busy = false;
    if (S.evalQueued) {
      S.evalQueued = false;
      scheduleEval(60);
    }
  }
}

function applyResults(res) {
  for (const [id, r] of Object.entries(res)) {
    const node = S.graph.nodes.find((n) => n.id === id);
    const box = $(`.nb-val[data-val="${id}"]`);
    if (!box) continue;
    const el = box.closest(".node");
    box.className = "nb-val";
    if (r.err) {
      box.classList.add("err");
      box.textContent = r.err;
      if (el) el.classList.add("err");
      continue;
    }
    if (el) el.classList.remove("err");
    if (r.note) {
      box.classList.add("blank");
      box.textContent = r.note;
      if (r.noteTitle) box.title = r.noteTitle;
    } else if (r.warn) {
      box.classList.add("warn");
      box.textContent = r.warn;
    } else if (r.value !== undefined && r.value !== "") {
      box.classList.add("ok");
      box.textContent = r.value;
    } else {
      box.classList.add("blank");
      box.textContent = r.type ? "（无值可显示）" : "…";
    }
    if (r.type) box.title = r.type;
  }
}

/* ------------------------------------------------------------ 存取 -- */

function scheduleSave() {
  clearTimeout(S.saveTimer);
  S.saveTimer = setTimeout(() => {
    api("/api/graph", { method: "POST", body: S.graph }).catch(() => {});
  }, 700);
}

async function pollEngine() {
  try {
    const r = await api("/api/engine");
    S.engine = { ready: r.ready, error: r.error, types: r.types };
    const chip = $("#engine");
    chip.className = "nb-engine " + (r.ready ? "ok" : r.error ? "bad" : "");
    $("#engine-text").textContent = r.ready ? `引擎 ${r.types} 类型` : r.error ? "引擎失败" : "预热中";
    $("#status-engine").textContent = r.ready ? `ghci 常驻 · ${r.types} 个元件已取类型` : "";
    if (r.ready) {
      const comps = await api("/api/components");
      S.comps = comps.comps;
      S.byId = Object.fromEntries(S.comps.map((c) => [c.id, c]));
      renderAll();
      scheduleEval(50);
      return;
    }
    if (r.error) {
      toast("引擎起不来：" + r.error.slice(0, 200));
      return;
    }
    setTimeout(pollEngine, 500);
  } catch (e) {
    setTimeout(pollEngine, 800);
  }
}

/* ------------------------------------------------------------ 其它 -- */

function toggleHelp(on) {
  const el = $("#help");
  if (!el) return;
  el.hidden = on === undefined ? !el.hidden : !on;
}

let toastTimer = null;
function toast(msg, ok = false) {
  const t = $("#toast");
  t.hidden = false;
  t.textContent = msg;
  t.className = "nb-toast" + (ok ? " ok" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3200);
}

function fit() {
  const nodes = S.graph.nodes;
  if (!nodes.length) {
    S.view = { x: 60, y: 40, z: 1 };
    worldTransform();
    return;
  }
  const stage = $("#stage").getBoundingClientRect();
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) {
    const el = $(`.node[data-id="${n.id}"]`);
    const w = el ? el.offsetWidth : 198;
    const h = el ? el.offsetHeight : 90;
    x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
    x1 = Math.max(x1, n.x + w); y1 = Math.max(y1, n.y + h);
  }
  const pad = 60;
  const sx = (stage.width - pad * 2) / Math.max(1, x1 - x0);
  const sy = (stage.height - pad * 2) / Math.max(1, y1 - y0);
  const z = clamp(Math.min(sx, sy), 0.35, 1.25);
  S.view.z = z;
  S.view.x = (stage.width - (x1 - x0) * z) / 2 - x0 * z;
  S.view.y = (stage.height - (y1 - y0) * z) / 2 - y0 * z;
  worldTransform();
}

function initKeys() {
  window.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
    if ((e.key === "Delete" || e.key === "Backspace") && !typing) {
      if (!S.sel) return;
      e.preventDefault();
      if (S.sel.type === "node") removeNode(S.sel.id);
      else {
        snapshot();
        S.graph.edges.splice(S.sel.id, 1);
        S.sel = null;
        renderWires();
        scheduleEval(60);
        scheduleSave();
      }
    }
    if (e.key === "Escape") {
      toggleHelp(false);
      closePalette();
      $("#node-menu").hidden = true;
      if (S.drag && S.drag.cancel) { S.drag.cancel(); S.drag = null; }
    }
    if (e.key === "?" && !typing) {
      e.preventDefault();
      toggleHelp();
    }
    if (e.code === "Space" && !typing && !S.pal.open) {
      e.preventDefault();
      const r = $("#stage").getBoundingClientRect();
      S.pal.at = toWorld(r.left + r.width / 2, r.top + r.height / 2);
      openPalette(r.left + r.width / 2 - 215, r.top + 90);
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      e.shiftKey ? redo() : undo();
    }
    if (!typing && (e.key === "f" || e.key === "F")) fit();
  });
}

function initButtons() {
  $("#btn-fit").addEventListener("click", fit);
  $("#btn-help").addEventListener("click", () => toggleHelp());
  $("#help-close").addEventListener("click", () => toggleHelp(false));
  help.addEventListener("click", (e) => { if (e.target === help) toggleHelp(false); });
  $("#btn-lib").addEventListener("click", () => {
    const r = $("#stage").getBoundingClientRect();
    S.pal.at = toWorld(r.left + r.width / 2, r.top + r.height / 2);
    openPalette(r.left + r.width / 2 - 215, r.top + 80);
  });
  $("#btn-empty-lib").addEventListener("click", () => $("#btn-lib").click());
  $("#btn-sample").addEventListener("click", async (e) => {
    const m = $("#sample-menu");
    if (!m.hidden) { m.hidden = true; return; }
    // currentTarget 在 await 之后就没了，先把位置量下来
    const rect = $("#btn-sample").getBoundingClientRect();
    const r = await api("/api/samples");
    m.innerHTML = r.samples
      .map((s) => `<button data-id="${esc(s.id)}">${esc(s.label)}<em>${s.nodes} 节点</em></button>`)
      .join("");
    m.hidden = false;
    m.style.left = Math.round(rect.left) + "px";
    m.style.top = Math.round(rect.bottom + 6) + "px";
    $$("button", m).forEach((b) =>
      b.addEventListener("click", async () => {
        m.hidden = true;
        const g = await api("/api/sample?id=" + encodeURIComponent(b.dataset.id));
        snapshot();
        S.graph = g;
        S.sel = null;
        renderAll();
        fit();
        scheduleEval(80);
        scheduleSave();
        toast("已载入：" + g.name, true);
      })
    );
  });
  $("#btn-clear").addEventListener("click", () => {
    if (!S.graph.nodes.length) return;
    snapshot();
    S.graph.nodes = [];
    S.graph.edges = [];
    S.graph.name = "空白画布";
    S.sel = null;
    renderAll();
    scheduleEval(60);
    scheduleSave();
  });
  $("#engine").addEventListener("click", async () => {
    toast("重启引擎…");
    const r = await api("/api/restart", { method: "POST", body: {} });
    S.engine = { ready: r.engine.ok, error: r.engine.error || "", types: r.engine.types || 0 };
    if (r.comps) {
      S.comps = r.comps;
      S.byId = Object.fromEntries(S.comps.map((c) => [c.id, c]));
      renderAll();
      scheduleEval(50);
    }
    pollEngine();
  });
}

/* ------------------------------------------------------------ 启动 -- */

async function boot() {
  const b = await api("/api/boot");
  S.root = b.root;
  S.cats = b.cats;
  S.comps = b.comps;
  S.byId = Object.fromEntries(S.comps.map((c) => [c.id, c]));
  S.engine = { ready: b.engine.ready, error: b.engine.error, types: b.engine.types };
  S.graph = b.graph && b.graph.nodes ? b.graph : { name: "未命名", nodes: [], edges: [] };
  $("#root-path").textContent = b.root;
  $("#root-path").title = b.root;

  initStage();
  initPalette();
  initNodeMenu();
  initKeys();
  initButtons();
  renderAll();
  fit();
  window.addEventListener("resize", () => worldTransform());
  window.addEventListener("beforeunload", () => {
    try {
      const blob = new Blob([JSON.stringify(S.graph)], { type: "application/json" });
      navigator.sendBeacon("/api/graph", blob);
    } catch {}
  });

  if (new URLSearchParams(location.search).has("audit")) setTimeout(layoutAudit, 1400);
  if (b.engine.ready) {
    scheduleEval(120);
    const chip = $("#engine");
    chip.className = "nb-engine ok";
    $("#engine-text").textContent = `引擎 ${b.engine.types} 类型`;
    pollEngine();
  } else {
    pollEngine();
  }
}

/* 版式自检：只在 ?audit=1 时跑，把可量的东西写成 JSON。 */
function layoutAudit() {
  const r = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };
  const rects = S.graph.nodes.map((n) => ({ id: n.id, ...r($(`.node[data-id="${n.id}"]`)) }));
  const overlaps = [];
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i], b = rects[j];
      if (a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y) overlaps.push([a.id, b.id]);
    }
  }
  const pal = $("#palette");
  const out = {
    viewport: { w: innerWidth, h: innerHeight },
    docOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    docOverflowY: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    engine: S.engine,
    graph: { nodes: S.graph.nodes.length, wires: S.graph.edges.length, name: S.graph.name },
    wiresDrawn: $$("#wire-layer path:not(.hit):not(.temp)").length,
    nodeRects: rects,
    overlaps,
    header: { w: $(".nb-bar").clientWidth, sw: $(".nb-bar").scrollWidth },
    status: { eval: $("#status-eval").textContent, incr: $("#status-incr").textContent },
    view: S.view,
    palette: pal.hidden ? null : { ...r(pal), items: $$(".nb-pal-item").length },
    values: Object.fromEntries(S.graph.nodes.map((n) => {
      const el = $(`.nb-val[data-val="${n.id}"]`);
      return [n.id, el ? el.textContent.slice(0, 40) : null];
    })),
  };
  document.querySelectorAll("#audit-json").forEach((el) => el.remove());
  const pre = document.createElement("pre");
  pre.id = "audit-json";
  pre.hidden = true;
  pre.textContent = JSON.stringify(out, null, 1);
  document.body.appendChild(pre);
}

boot().catch((e) => {
  console.error(e);
  $("#status-eval").textContent = "启动失败：" + e.message;
  $("#status-eval").className = "bad";
});
