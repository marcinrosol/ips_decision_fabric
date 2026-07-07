const POLL_MS = 2000;

function parseDate(s) {
  // Accepts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
  return new Date(s.replace(" ", "T"));
}

function renderSimStatus(status) {
  const dot = document.getElementById("running-dot");
  const text = document.getElementById("running-text");
  const dateEl = document.getElementById("sim-date");
  const daysEl = document.getElementById("days-processed");
  const speedEl = document.getElementById("speed-factor");
  const updatedEl = document.getElementById("updated-at");

  if (!status) {
    dot.className = "dot dot-stopped";
    text.textContent = "No simulation state";
    dateEl.textContent = "--";
    daysEl.textContent = "--";
    speedEl.textContent = "--";
    updatedEl.textContent = "--";
    return;
  }

  dot.className = "dot " + (status.running ? "dot-running" : "dot-stopped");
  text.textContent = status.running ? "Running" : "Stopped";
  dateEl.textContent = status.sim_now;
  daysEl.textContent = status.total_sim_days_processed;
  speedEl.textContent = `${status.speed_factor}x (1 sim-day / ${(86400 / status.speed_factor).toFixed(0)}s)`;
  updatedEl.textContent = status.updated_at;

  renderProgress(status);
}

function renderProgress(status) {
  const fill = document.getElementById("progress-fill");
  const marker = document.getElementById("progress-marker");
  const startLabel = document.getElementById("horizon-start");
  const endLabel = document.getElementById("horizon-end");

  if (!status.horizon_start || !status.horizon_end) {
    fill.style.width = "0%";
    marker.style.left = "0%";
    startLabel.textContent = "--";
    endLabel.textContent = "--";
    return;
  }

  const start = parseDate(status.horizon_start);
  const end = parseDate(status.horizon_end);
  const now = parseDate(status.sim_now);

  let pct = 0;
  if (end > start) {
    pct = ((now - start) / (end - start)) * 100;
  }
  pct = Math.max(0, Math.min(100, pct));

  fill.style.width = `${pct}%`;
  marker.style.left = `${pct}%`;
  startLabel.textContent = status.horizon_start;
  endLabel.textContent = status.horizon_end + (now > end ? ` (now: ${status.sim_now.split(" ")[0]})` : "");
}

function renderInventory(chemicals) {
  const grid = document.getElementById("inventory-grid");
  grid.innerHTML = "";

  for (const c of chemicals) {
    const card = document.createElement("div");
    card.className = `chem-card level-${c.level}`;

    const icons = [];
    if (c.needs_ordering) icons.push('<span class="icon" title="Needs ordering">\u{1F4E6}❗</span>');
    if (c.in_transit) icons.push('<span class="icon" title="On the way">\u{1F69A}</span>');
    if (c.delayed) icons.push('<span class="icon" title="Delayed / backordered">⚠️</span>');

    card.innerHTML = `
      <div class="chem-name">${c.name}</div>
      <div class="chem-category">${c.category}</div>
      <div class="chem-qty">${c.quantity_on_hand.toFixed(2)} ${c.unit_of_measure} <span style="color:var(--text-dim)">(reorder &le; ${c.reorder_threshold})</span></div>
      <div class="chem-icons">${icons.join("")}</div>
    `;
    grid.appendChild(card);
  }
}

const SVG_NS = "http://www.w3.org/2000/svg";
const TIMELINE_ROW_HEIGHT = 32;
const TIMELINE_AXIS_HEIGHT = 24;
const RISK_COLOR = {
  Low: "var(--status-good)",
  Moderate: "var(--status-warning)",
  High: "var(--status-serious)",
  Severe: "var(--status-critical)",
};
const tooltip = document.getElementById("chart-tooltip");

function showTooltip(evt, exp) {
  tooltip.innerHTML = "";
  const title = document.createElement("div");
  title.className = "tt-title";
  title.textContent = `${exp.experiment_code} — ${exp.title}`;
  tooltip.appendChild(title);

  const rows = [
    `Lead: ${exp.lead_chemist} · Site: ${exp.test_site || "--"}`,
    `Scheduled: ${exp.scheduled_date} · Duration: ${exp.duration_minutes ?? "--"} min`,
    `Risk: ${exp.risk_level} · Status: ${exp.status} (approval: ${exp.approval_status})`,
  ];
  if (exp.objective) rows.push(`Objective: ${exp.objective}`);
  for (const text of rows) {
    const div = document.createElement("div");
    div.className = "tt-row";
    div.textContent = text;
    tooltip.appendChild(div);
  }
  if (exp.ips_reference_citation) {
    const cite = document.createElement("div");
    cite.className = "tt-citation";
    cite.textContent = exp.ips_reference_citation;
    tooltip.appendChild(cite);
  }

  tooltip.style.display = "block";
  moveTooltip(evt);
}

function moveTooltip(evt) {
  const pad = 14;
  let x = evt.clientX + pad;
  let y = evt.clientY + pad;
  if (x + 320 > window.innerWidth) x = evt.clientX - 320 - pad;
  if (y + 140 > window.innerHeight) y = evt.clientY - 140 - pad;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip() {
  tooltip.style.display = "none";
}

function setRowHover(id, on) {
  const label = document.querySelector(`.timeline-label-row[data-id="${id}"]`);
  const mark = document.querySelector(`.timeline-mark[data-id="${id}"]`);
  if (label) label.classList.toggle("row-hover", on);
  if (mark) mark.setAttribute("r", on ? 8 : 6);
}

function renderTimeline(experiments, simStatus) {
  const labelsEl = document.getElementById("timeline-labels");
  const plotEl = document.getElementById("timeline-plot");
  const savedScrollTop = labelsEl.scrollTop;
  labelsEl.innerHTML = "";
  plotEl.innerHTML = "";

  if (!experiments || experiments.length === 0 || !simStatus || !simStatus.horizon_start) {
    labelsEl.textContent = "No experiments scheduled yet.";
    return;
  }

  const start = parseDate(simStatus.horizon_start);
  const end = parseDate(simStatus.horizon_end);
  const span = Math.max(1, end - start);
  const now = parseDate(simStatus.sim_now);

  const plotWidth = Math.max(plotEl.clientWidth, 400);
  const height = experiments.length * TIMELINE_ROW_HEIGHT + TIMELINE_AXIS_HEIGHT;

  const xOf = (dateStr) => {
    const pct = Math.max(0, Math.min(1, (parseDate(dateStr) - start) / span));
    return pct * (plotWidth - 20) + 10;
  };

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${plotWidth} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");

  // Date axis ticks (5 evenly spaced).
  const TICKS = 5;
  for (let i = 0; i <= TICKS; i++) {
    const t = start.getTime() + (span * i) / TICKS;
    const x = xOf(new Date(t).toISOString().slice(0, 10));
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", x);
    line.setAttribute("x2", x);
    line.setAttribute("y1", TIMELINE_AXIS_HEIGHT);
    line.setAttribute("y2", height);
    line.setAttribute("class", "timeline-tick-line");
    svg.appendChild(line);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", x);
    label.setAttribute("y", TIMELINE_AXIS_HEIGHT - 8);
    label.setAttribute("class", "timeline-tick-label");
    label.setAttribute("text-anchor", i === 0 ? "start" : i === TICKS ? "end" : "middle");
    label.textContent = new Date(t).toISOString().slice(0, 10);
    svg.appendChild(label);
  }

  experiments.forEach((exp, i) => {
    const rowLabel = document.createElement("div");
    rowLabel.className = "timeline-label-row";
    rowLabel.dataset.id = exp.schedule_id;
    const isDone = exp.status === "Completed" || exp.status === "Cancelled";
    if (isDone) rowLabel.classList.add("row-dim");
    rowLabel.innerHTML = `<span class="exp-code">${exp.experiment_code}</span><span class="exp-title">${exp.title}</span>`;
    labelsEl.appendChild(rowLabel);

    const cy = TIMELINE_AXIS_HEIGHT + i * TIMELINE_ROW_HEIGHT + TIMELINE_ROW_HEIGHT / 2;
    const cx = xOf(exp.scheduled_date);

    const hit = document.createElementNS(SVG_NS, "circle");
    hit.setAttribute("cx", cx);
    hit.setAttribute("cy", cy);
    hit.setAttribute("r", 14);
    hit.setAttribute("class", "timeline-mark-hit");
    hit.dataset.id = exp.schedule_id;

    const mark = document.createElementNS(SVG_NS, "circle");
    mark.setAttribute("cx", cx);
    mark.setAttribute("cy", cy);
    mark.setAttribute("r", 6);
    mark.setAttribute("fill", RISK_COLOR[exp.risk_level] || "var(--text-dim)");
    mark.setAttribute("class", "timeline-mark" + (isDone ? " row-dim" : ""));
    mark.dataset.id = exp.schedule_id;

    const onEnter = (evt) => {
      setRowHover(exp.schedule_id, true);
      showTooltip(evt, exp);
    };
    const onMove = (evt) => moveTooltip(evt);
    const onLeave = () => {
      setRowHover(exp.schedule_id, false);
      hideTooltip();
    };

    hit.addEventListener("pointerenter", onEnter);
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerleave", onLeave);
    rowLabel.addEventListener("pointerenter", onEnter);
    rowLabel.addEventListener("pointermove", onMove);
    rowLabel.addEventListener("pointerleave", onLeave);

    svg.appendChild(hit);
    svg.appendChild(mark);
  });

  // "Now" marker, drawn last so it sits on top of gridlines.
  if (now >= start && now <= end) {
    const nowLine = document.createElementNS(SVG_NS, "line");
    const x = xOf(simStatus.sim_now.split(" ")[0]);
    nowLine.setAttribute("x1", x);
    nowLine.setAttribute("x2", x);
    nowLine.setAttribute("y1", 0);
    nowLine.setAttribute("y2", height);
    nowLine.setAttribute("class", "timeline-now-line");
    svg.appendChild(nowLine);
  }

  plotEl.appendChild(svg);
  labelsEl.scrollTop = savedScrollTop;
  plotEl.scrollTop = savedScrollTop;

  // Keep the label column and plot area scrolled together.
  labelsEl.onscroll = () => { plotEl.scrollTop = labelsEl.scrollTop; };
  plotEl.onscroll = () => { labelsEl.scrollTop = plotEl.scrollTop; };
}

function renderEvents(events) {
  const log = document.getElementById("event-log");
  log.innerHTML = "";

  for (const e of events) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="event-date">${e.sim_date}</span><span class="event-type">${e.event_type}</span>${e.message}`;
    log.appendChild(li);
  }
}

// Reconciles container's children (keyed by data-id) against items instead
// of wiping innerHTML -- review cards hold in-progress text inputs (outcome
// notes) that a full rebuild on every 2s poll would erase mid-typing.
function reconcileList(container, items, idKey, buildCard) {
  const seen = new Set();
  for (const item of items) {
    const id = String(item[idKey]);
    seen.add(id);
    if (!container.querySelector(`[data-id="${id}"]`)) {
      container.appendChild(buildCard(item));
    }
  }
  for (const card of Array.from(container.children)) {
    if (!seen.has(card.dataset.id)) card.remove();
  }
}

function getReviewerName() {
  return document.getElementById("reviewer-name").value.trim();
}

async function postAction(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.error || "Action failed");
    return false;
  }
  return true;
}

function buildDecisionCard(d) {
  const card = document.createElement("div");
  card.className = "review-card";
  card.dataset.id = String(d.decision_id);
  card.innerHTML = `
    <div class="review-card-title">${d.decision_type}</div>
    <div class="review-card-detail">${d.triggering_event}</div>
    <div class="review-card-detail"><strong>Recommends:</strong> ${d.recommended_action}</div>
    ${d.confidence_score != null ? `<div class="review-card-detail">Confidence: ${(d.confidence_score * 100).toFixed(0)}%</div>` : ""}
    ${d.vector_store_citations ? `<div class="review-card-detail review-card-citations">${d.vector_store_citations}</div>` : ""}
    <input class="outcome-input" type="text" placeholder="Outcome notes (required to override)">
    <div class="review-card-actions">
      <button class="approve-btn">Approve</button>
      <button class="override-btn">Override</button>
    </div>
  `;
  card.querySelector(".approve-btn").addEventListener("click", async () => {
    const reviewer = getReviewerName();
    if (!reviewer) return alert("Enter your name first.");
    const outcome = card.querySelector(".outcome-input").value.trim();
    if (await postAction(`/api/decisions/${d.decision_id}/approve`, { reviewer, outcome: outcome || null })) poll();
  });
  card.querySelector(".override-btn").addEventListener("click", async () => {
    const reviewer = getReviewerName();
    if (!reviewer) return alert("Enter your name first.");
    const outcome = card.querySelector(".outcome-input").value.trim();
    if (!outcome) return alert("Outcome notes are required to override.");
    if (await postAction(`/api/decisions/${d.decision_id}/override`, { reviewer, outcome })) poll();
  });
  return card;
}

function buildSimpleCard(item, idField, titleHtml, detailHtml, approveUrl, rejectUrl) {
  const card = document.createElement("div");
  card.className = "review-card";
  card.dataset.id = String(item[idField]);
  card.innerHTML = `
    <div class="review-card-title">${titleHtml}</div>
    ${detailHtml}
    <div class="review-card-actions">
      <button class="approve-btn">Approve</button>
      <button class="reject-btn">Reject</button>
    </div>
  `;
  card.querySelector(".approve-btn").addEventListener("click", async () => {
    const reviewer = getReviewerName();
    if (!reviewer) return alert("Enter your name first.");
    if (await postAction(approveUrl(item), { reviewer })) poll();
  });
  card.querySelector(".reject-btn").addEventListener("click", async () => {
    const reviewer = getReviewerName();
    if (!reviewer) return alert("Enter your name first.");
    if (await postAction(rejectUrl(item), { reviewer })) poll();
  });
  return card;
}

function buildPOCard(po) {
  const detail = `
    <div class="review-card-detail">${po.chemical_name} &mdash; ${po.quantity_ordered} ${po.unit_of_measure}</div>
    <div class="review-card-detail">Supplier: ${po.supplier_name}</div>
    ${po.total_cost_usd != null ? `<div class="review-card-detail">Est. cost: $${po.total_cost_usd.toFixed(2)}</div>` : ""}
  `;
  return buildSimpleCard(
    po, "po_id", po.po_number, detail,
    (item) => `/api/purchase-orders/${item.po_id}/approve`,
    (item) => `/api/purchase-orders/${item.po_id}/reject`
  );
}

function buildExperimentCard(exp) {
  const detail = `
    <div class="review-card-detail">${exp.title}</div>
    <div class="review-card-detail">Lead: ${exp.lead_chemist} &middot; Scheduled: ${exp.scheduled_date} &middot; Risk: ${exp.risk_level}</div>
  `;
  return buildSimpleCard(
    exp, "schedule_id", exp.experiment_code, detail,
    (item) => `/api/experiments/${item.schedule_id}/approve`,
    (item) => `/api/experiments/${item.schedule_id}/reject`
  );
}

function renderReviewQueue(data) {
  reconcileList(document.getElementById("decisions-list"), data.pending_decisions || [], "decision_id", buildDecisionCard);
  reconcileList(document.getElementById("pos-list"), data.draft_purchase_orders || [], "po_id", buildPOCard);
  reconcileList(document.getElementById("experiments-list"), data.pending_experiments || [], "schedule_id", buildExperimentCard);
}

async function poll() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();
    renderSimStatus(data.sim_status);
    renderInventory(data.inventory);
    renderEvents(data.events);
    renderReviewQueue(data);
    renderTimeline(data.experiments_timeline, data.sim_status);
  } catch (err) {
    console.error("Failed to fetch /api/state", err);
  }
}

poll();
setInterval(poll, POLL_MS);

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSubmit = document.getElementById("chat-submit");

function appendChatMessage(role, text, extraClass) {
  const div = document.createElement("div");
  div.className = `chat-msg chat-${role}` + (extraClass ? ` chat-${extraClass}` : "");
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

function appendToolCalls(toolCalls) {
  if (!toolCalls || toolCalls.length === 0) return;
  appendChatMessage("assistant", "Tools used: " + toolCalls.map((t) => t.name).join(", "), "tools");
}

async function sendChatMessage(event) {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  appendChatMessage("user", message);
  chatInput.value = "";
  chatInput.disabled = true;
  chatSubmit.disabled = true;
  const thinking = appendChatMessage("assistant", "Thinking...", "thinking");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    thinking.remove();
    if (data.error) {
      appendChatMessage("assistant", "Error: " + data.error, "error");
    } else {
      appendToolCalls(data.tool_calls);
      appendChatMessage("assistant", data.response);
    }
  } catch (err) {
    thinking.remove();
    appendChatMessage("assistant", "Failed to reach the assistant.", "error");
    console.error("Chat request failed", err);
  } finally {
    chatInput.disabled = false;
    chatSubmit.disabled = false;
    chatInput.focus();
  }
}

if (chatForm) {
  chatForm.addEventListener("submit", sendChatMessage);
}

const chatReset = document.getElementById("chat-reset");
if (chatReset) {
  chatReset.addEventListener("click", async () => {
    chatReset.disabled = true;
    try {
      await fetch("/api/chat/reset", { method: "POST" });
      chatLog.innerHTML = "";
    } catch (err) {
      console.error("Failed to reset chat", err);
    } finally {
      chatReset.disabled = false;
    }
  });
}
