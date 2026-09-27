/* ============ 粮情哨兵智能体 · 前端逻辑 ============ */
"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

const messagesEl = $("#messages");
const historyList = $("#historyList");
const agentsList = $("#agentsList");
const kpiRow = $("#kpiRow");
const statusBadge = $("#statusBadge");
const inputEl = $("#input");
const sendBtn = $("#send");

const QUICK_QUESTIONS = [
  { t: "粮情安全风险评估", s: "安全预警智能体 · 应急处置", q: "帮我评估储备库C的粮情安全风险，并给出处置预案" },
  { t: "粮食质量检测", s: "质量检测智能体 · 等级判定", q: "检测直属库A的粮食质量，判定储存品质" },
  { t: "粮情实时监测", s: "粮情监测智能体 · 发热结露", q: "监测直属库A的粮温、水分与粮堆气体，研判异常粮情" },
  { t: "虫霉监测与防治", s: "虫霉防治智能体 · 熏蒸气调", q: "分析储备库C的虫霉情况，给出防治方案" },
  { t: "储备粮轮换", s: "储备轮换智能体 · 宜存判定", q: "对储备库C做储存品质判定，给出轮换建议" },
  { t: "智能仓储管控", s: "智能仓储智能体 · 通风气调", q: "优化直属库B的仓储通风气调策略，降低损耗" },
];

/* ---------------- 状态与持久化 ---------------- */
const store = loadStore();
let busy = false;

function loadStore() {
  try {
    const raw = localStorage.getItem("grain_sentinel_store");
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore */ }
  return { currentId: null, order: [], conversations: {} };
}
function persist() {
  try { localStorage.setItem("grain_sentinel_store", JSON.stringify(store)); } catch (e) { /* ignore */ }
}
function currentConv() {
  return store.conversations[store.currentId];
}

/* ---------------- Markdown 渲染 ---------------- */
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function renderMarkdown(src) {
  const codeBlocks = [];
  src = src.replace(/```[^\n]*\n?([\s\S]*?)```/g, (m, code) => {
    codeBlocks.push("<pre><code>" + escapeHtml(code.replace(/\n$/, "")) + "</code></pre>");
    return "" + (codeBlocks.length - 1) + "";
  });
  const inline = (s) => {
    s = escapeHtml(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  };
  const out = [];
  let listType = null;
  let tableBuf = [];
  const flushList = () => { if (listType) { out.push("</" + listType + ">"); listType = null; } };
  const flushTable = () => {
    if (tableBuf.length) {
      let html = "<table>";
      tableBuf.forEach((row, i) => {
        const tag = i === 0 ? "th" : "td";
        html += "<tr>" + row.split("|").slice(1, -1).map(c => "<" + tag + ">" + inline(c.trim()) + "</" + tag + ">").join("") + "</tr>";
      });
      out.push(html + "</table>");
      tableBuf = [];
    }
  };
  for (const line of src.split("\n")) {
    const t = line.trim();
    if (t.startsWith("|") && t.endsWith("|")) {
      flushList();
      if (!/^\|[\s:|-]+\|$/.test(t)) tableBuf.push(t);
      continue;
    }
    flushTable();
    const h = t.match(/^(#{1,6})\s+(.*)/);
    if (h) { flushList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); continue; }
    const ul = t.match(/^[-*]\s+(.*)/);
    const ol = t.match(/^\d+[.)]\s+(.*)/);
    if (ul) { if (listType !== "ul") { flushList(); out.push("<ul>"); listType = "ul"; } out.push(`<li>${inline(ul[1])}</li>`); continue; }
    if (ol) { if (listType !== "ol") { flushList(); out.push("<ol>"); listType = "ol"; } out.push(`<li>${inline(ol[1])}</li>`); continue; }
    if (/^---+$/.test(t)) { flushList(); out.push("<hr>"); continue; }
    if (t === "") { flushList(); continue; }
    flushList(); out.push(`<p>${inline(t)}</p>`);
  }
  flushList(); flushTable();
  return out.join("\n").replace(/(\d+)/g, (m, i) => codeBlocks[+i]);
}

/* ---------------- 消息渲染 ---------------- */
function scrollDown() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function renderUser(text) {
  const row = el("div", "msg-row user");
  row.innerHTML = `<div class="msg-body"><div class="bubble">${escapeHtml(text)}</div></div>`;
  messagesEl.appendChild(row);
  scrollDown();
}

function renderAssistant(msg) {
  const row = el("div", "msg-row assistant");
  const body = el("div", "msg-body");
  const steps = msg.trace || [];
  if (steps.length) {
    body.appendChild(buildTrace(steps));
  }
  const content = el("div", "bubble assistant-content");
  content.innerHTML = renderMarkdown(msg.content || "");
  body.appendChild(content);
  row.innerHTML = `<div class="avatar bot">🌾</div>`;
  row.appendChild(body);
  messagesEl.appendChild(row);
  scrollDown();
}

function buildTrace(steps) {
  const wrap = el("div", "trace collapsed");
  const head = el("div", "trace-head");
  head.innerHTML = `<span class="chev">▾</span><span>🔎 思考过程 · ${steps.length} 步</span>`;
  head.onclick = () => wrap.classList.toggle("collapsed");
  const body = el("div", "trace-body");
  body.innerHTML = steps.map(renderTraceStep).join("");
  wrap.append(head, body);
  return wrap;
}

function renderTraceStep(s) {
  let icon, label = "", preview = "", ok = "";
  if (s.type === "agent") {
    icon = "🤖"; label = `<b>${escapeHtml(s.agent)}</b> · ${escapeHtml(s.content || "")}`;
  } else if (s.type === "tool") {
    icon = "🔧"; label = `<b>${escapeHtml(s.agent)}</b> 调用工具 <b>${escapeHtml(s.tool)}</b>`;
    preview = s.args ? `<div class="t-preview">${escapeHtml(JSON.stringify(s.args))}</div>` : "";
  }
  if (s.ok) ok = ` <span class="t-ok">✓</span>`;
  if (s.preview) preview = `<div class="t-preview">${escapeHtml(s.preview)}</div>`;
  return `<div class="trace-step"><span class="t-icon">${icon}</span><div><div class="t-label">${label}${ok}</div>${preview}</div></div>`;
}

function renderEmpty() {
  const wrap = el("div", "empty");
  const grid = el("div", "quick-grid");
  QUICK_QUESTIONS.forEach((q) => {
    const card = el("div", "quick");
    card.innerHTML = `<div class="q-title">${escapeHtml(q.t)}</div><div class="q-sub">${escapeHtml(q.s)}</div>`;
    card.onclick = () => sendMessage(q.q);
    grid.appendChild(card);
  });
  wrap.innerHTML = `<div class="empty-icon">🌾</div><div class="empty-title">今天想守护哪座粮仓？</div>
    <div class="empty-desc">面向粮食安全与粮情实时监测的多智能体系统，覆盖粮情监测、质量检测、虫霉防治、仓储管控、储备轮换与安全预警。</div>`;
  wrap.appendChild(grid);
  messagesEl.appendChild(wrap);
}

/* ---------------- 会话管理 ---------------- */
function newChat() {
  const id = "c" + Date.now();
  store.conversations[id] = { title: "新对话", messages: [] };
  store.order.push(id);
  store.currentId = id;
  persist();
  render();
}
function switchChat(id) {
  store.currentId = id;
  persist();
  render();
}
function render() {
  renderHistory();
  const conv = currentConv();
  $("#topbarTitle").textContent = conv && conv.title ? conv.title : "新对话";
  messagesEl.innerHTML = "";
  if (!conv || conv.messages.length === 0) { renderEmpty(); return; }
  conv.messages.forEach((m) => (m.role === "user" ? renderUser(m.content) : renderAssistant(m)));
}
function renderHistory() {
  historyList.innerHTML = "";
  if (!store.order.length) {
    historyList.appendChild(el("div", "history-empty", "暂无会话记录"));
    return;
  }
  [...store.order].reverse().forEach((id) => {
    const conv = store.conversations[id];
    const item = el("div", "history-item" + (id === store.currentId ? " active" : ""), conv.title || "新对话");
    item.onclick = () => switchChat(id);
    historyList.appendChild(item);
  });
}

/* ---------------- 发送与流式接收 ---------------- */
async function sendMessage(text) {
  text = (text || "").trim();
  if (!text || busy) return;
  if (!currentConv()) newChat();
  else if (currentConv().messages.length === 0) { /* 复用空会话 */ }

  const conv = currentConv();
  conv.messages.push({ role: "user", content: text });
  if (conv.title === "新对话") conv.title = text.slice(0, 22) + (text.length > 22 ? "…" : "");
  render();
  persist();

  const assistant = createStreamingMessage();
  busy = true; sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    if (!res.ok) {
      let detail = "请求失败（" + res.status + "）";
      try { detail = (await res.json()).detail || detail; } catch (e) { /* ignore */ }
      throw new Error(detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "", acc = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) !== -1) {
        const frame = buf.slice(0, i); buf = buf.slice(i + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "agent") assistant.addTrace({ type: "agent", agent: evt.agent, content: evt.content });
          else if (evt.type === "tool") assistant.addTrace({ type: "tool", agent: evt.agent, tool: evt.tool, args: evt.args });
          else if (evt.type === "tool_result") assistant.markToolDone(evt.tool, evt.preview);
          else if (evt.type === "text") { acc += evt.content; assistant.setText(acc); }
          else if (evt.type === "error") assistant.setError(evt.content);
        }
      }
    }
    conv.messages.push({ role: "assistant", content: acc, trace: assistant.steps });
  } catch (e) {
    assistant.setError(e.message);
    conv.messages.push({ role: "assistant", content: "⚠️ " + e.message, trace: assistant.steps });
  } finally {
    busy = false; sendBtn.disabled = false;
    assistant.finish();
    persist();
  }
}

function createStreamingMessage() {
  const row = el("div", "msg-row assistant");
  const body = el("div", "msg-body");
  const traceWrap = el("div", "trace collapsed");
  const head = el("div", "trace-head");
  head.innerHTML = `<span class="chev">▾</span><span>🔎 思考过程</span>`;
  head.onclick = () => traceWrap.classList.toggle("collapsed");
  const traceBody = el("div", "trace-body");
  traceWrap.append(head, traceBody);
  const content = el("div", "bubble assistant-content");
  content.innerHTML = '<span class="cursor"></span>';
  body.append(traceWrap, content);
  row.innerHTML = `<div class="avatar bot">🌾</div>`;
  row.appendChild(body);
  messagesEl.appendChild(row);
  scrollDown();

  const a = { steps: [], content, traceWrap, traceBody, row, lastText: "" };
  a.addTrace = (step) => {
    a.steps.push(step);
    traceWrap.classList.remove("collapsed");
    head.innerHTML = `<span class="chev">▾</span><span>🔎 思考过程 · ${a.steps.length} 步</span>`;
    traceBody.innerHTML = a.steps.map(renderTraceStep).join("");
    scrollDown();
  };
  a.markToolDone = (tool, preview) => {
    for (let i = a.steps.length - 1; i >= 0; i--) {
      const s = a.steps[i];
      if (s.type === "tool" && s.tool === tool && !s.ok) { s.ok = true; s.preview = preview; break; }
    }
    traceBody.innerHTML = a.steps.map(renderTraceStep).join("");
    scrollDown();
  };
  a.setText = (t) => { a.lastText = t; content.innerHTML = renderMarkdown(t) + '<span class="cursor"></span>'; scrollDown(); };
  a.setError = (msg) => { content.classList.add("error"); content.innerHTML = "⚠️ " + escapeHtml(msg); traceWrap.style.display = "none"; };
  a.finish = () => { if (a.lastText) content.innerHTML = renderMarkdown(a.lastText); };
  return a;
}

/* ---------------- 概览面板（ECharts） ---------------- */
let chart = null;
function initChart() {
  if (window.echarts) chart = echarts.init($("#grainChart"), null, { renderer: "canvas" });
}
async function loadOverview(warehouse) {
  try {
    const ov = await (await fetch("/api/overview?warehouse=" + encodeURIComponent(warehouse))).json();
    const statusCls = "s-" + ov.status;
    statusBadge.innerHTML = `<span class="${statusCls}">储粮状态 · ${escapeHtml(ov.status)}</span>`;
    const pestWarn = ov.pest >= 5 ? " warn" : "";
    kpiRow.innerHTML =
      `<div class="kpi"><div class="k-label">库存</div><div class="k-value">${ov.stock}<em> 吨</em></div></div>` +
      `<div class="kpi"><div class="k-label">粮温均温</div><div class="k-value">${ov.avg_temp}<em> ℃</em></div></div>` +
      `<div class="kpi"><div class="k-label">水分</div><div class="k-value">${ov.moisture}<em> %</em></div></div>` +
      `<div class="kpi${pestWarn}"><div class="k-label">虫害密度</div><div class="k-value">${ov.pest}<em> 头/kg</em></div></div>`;
    if (!chart) { $("#grainChart").innerHTML = '<div class="history-empty">图表库未加载（需联网）</div>'; return; }
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const axis = { color: "#7f9489", fontSize: 9 };
    chart.setOption({
      grid: { left: 36, right: 34, top: 30, bottom: 20 },
      tooltip: { trigger: "axis" },
      legend: { data: ["仓温", "粮温", "仓湿"], textStyle: { color: "#9ab0a3" }, itemWidth: 12, itemHeight: 8, top: 0 },
      xAxis: { type: "category", data: hours, axisLabel: axis, axisLine: { lineStyle: { color: "rgba(255,255,255,.1)" } } },
      yAxis: [
        { type: "value", name: "℃", axisLabel: axis, nameTextStyle: axis, splitLine: { lineStyle: { color: "rgba(255,255,255,.06)" } } },
        { type: "value", name: "%RH", axisLabel: axis, nameTextStyle: axis, splitLine: { show: false } },
      ],
      series: [
        { name: "仓温", type: "line", smooth: true, symbol: "none", data: ov.temp_profile, yAxisIndex: 0, lineStyle: { width: 2, color: "#f59e0b" } },
        { name: "粮温", type: "line", smooth: true, symbol: "none", data: ov.grain_profile, yAxisIndex: 0, lineStyle: { width: 2, color: "#34d399" } },
        { name: "仓湿", type: "line", smooth: true, symbol: "none", data: ov.humidity_profile, yAxisIndex: 1, lineStyle: { width: 1.5, color: "#38bdf8" }, areaStyle: { opacity: 0.05 } },
      ],
    });
  } catch (e) { /* ignore */ }
}

/* ---------------- 初始化 ---------------- */
async function init() {
  initChart();
  try {
    const h = await (await fetch("/api/health")).json();
    $("#statusDot").className = "dot " + (h.llm_ready ? "ok" : "bad");
    $("#statusText").textContent = h.llm_ready ? h.model + " 就绪" : "未配置 API Key";
  } catch (e) {
    $("#statusText").textContent = "服务未连接";
  }
  try {
    const a = await (await fetch("/api/agents")).json();
    let html = `<div class="agent-item"><span class="agent-dot"></span><div><div class="a-name">总控 Supervisor</div><div class="a-role">${escapeHtml(a.supervisor)}</div></div></div>`;
    html += a.subagents.map((s) => `<div class="agent-item"><span class="agent-dot"></span><div><div class="a-name">${escapeHtml(s.name)}</div><div class="a-role">${escapeHtml(s.role)}</div></div></div>`).join("");
    agentsList.innerHTML = html;
  } catch (e) { agentsList.innerHTML = '<div class="history-empty">加载失败</div>'; }

  $("#warehouseSelect").onchange = (e) => loadOverview(e.target.value);
  loadOverview("直属库A");
  render();
}

$("#newChat").onclick = newChat;
$("#send").onclick = () => { const v = inputEl.value; inputEl.value = ""; autoResize(); sendMessage(v); };
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); const v = inputEl.value; inputEl.value = ""; autoResize(); sendMessage(v); }
});
function autoResize() { inputEl.style.height = "auto"; inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + "px"; }
inputEl.addEventListener("input", autoResize);
window.addEventListener("resize", () => chart && chart.resize());

init();
