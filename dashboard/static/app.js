// ============================================================================
// POLYMARKET COCKPIT — DO NOT REVERT TO THE OLD MULTI-TAB DASHBOARD
// ============================================================================
// This file is the Bloomberg-style operator cockpit renderer, baselined in
// commit 4f066bd ("Roll up strategy audits and paper trader promotions",
// 2026-05-10). Companion file: dashboard/static/index.html.
//
// 6 active tabs: overview | bot-g | bot-d | wallet-observer | orders | events.
// Bot rows for I, J, K, L, E, H surface on the Overview as inventory rows —
// NOT as dedicated tabs. See header comment in index.html for the rules.
//
// HISTORICAL REGRESSIONS (do not repeat):
//   - 2026-05-14: commit 89f93aa (claude/bot-i-live-promotion branch) was
//     authored against the pre-cockpit layout. It reintroduced a
//     "Persistence Live (I)" tab plus dedicated bot-i/crypto-fair-value
//     panels, and this file was overwritten with ~2400 lines of legacy
//     multi-tab JS. The cockpit was restored from HEAD; the bot-i live
//     shadow data now surfaces as an Active Bots inventory row instead.
//   - 2026-05-14: a separate hand-restore from a the bot container backup ALSO
//     overwrote the cockpit (see observation 15567). Do not restore
//     dashboard static files from the bot container backups — the bot container receives, never
//     authors. The macbook git tree is the source of truth.
//
// IF YOU ARE ADDING A NEW BOT:
//   1. Add it to core/bot_registry.py with dashboard_visible=True.
//   2. The cockpit picks it up automatically via /api/overview's
//      bot_inventory list and renders it in the Active Bots / Active
//      Recorders table. NO new tab is needed.
//   3. If special metrics are required, extend the row override in
//      dashboard/runtime_queries.py:_bot_inventory.
//
// IF YOU MUST CHANGE THE TAB SET BELOW:
//   - tests/dashboard/test_dashboard.py::test_dashboard_shell_serves_tabs_and_safe_assets
//     hard-asserts the 6-tab cockpit shape. That test is the regression
//     guard for this file pair — if you legitimately change the layout,
//     update that test in the same commit.
// ============================================================================

const REFRESH_MS = 30000;
const TAB_ENDPOINTS = {
  overview: "/api/overview",
  "bot-d": "/api/bot-d",
  "bot-g": "/api/bot-g",
  "wallet-observer": "/api/wallet-observer",
  orders: "/api/orders",
  events: "/api/events",
};
// Recorder endpoints (Bot E, Bot H) remain available server-side for
// scripts and reports, but the dashboard does not surface dedicated
// drilldown tabs for them — recorder health is summarised on the
// Overview's Active Recorders table.

const SEVERITY_CLASS = {
  info: "info",
  warn: "warning",
  kill: "negative",
};

const state = {
  activeTab: "overview",
  cache: new Map(),
};

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function currency(value, digits = 2) {
  const number = Number(value ?? 0);
  return `$${number.toFixed(digits)}`;
}

function percent(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (Number.isNaN(number)) return "--";
  return `${number.toFixed(digits)}%`;
}

function classifyNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (Number.isNaN(number)) return "";
  if (number > 0) return "positive";
  if (number < 0) return "negative";
  return "";
}

function formatTimestamp(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString();
}

function trunc(value, max = 80) {
  if (!value) return "";
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function makePanel({ title, subtitle, span = 12, body }) {
  const panel = el("section", `panel span-${span}`);
  const header = el("div", "panel-header");
  const heading = el("div");
  heading.append(el("h2", "panel-title", title));
  if (subtitle) heading.append(el("div", "panel-subtitle", subtitle));
  header.append(heading);
  panel.append(header);
  const bodyWrap = el("div", "panel-body");
  if (body instanceof Node) bodyWrap.append(body);
  else if (Array.isArray(body)) body.forEach((item) => bodyWrap.append(item));
  panel.append(bodyWrap);
  return panel;
}

function metricCard(label, value, detail, valueClass = "") {
  const card = el("article", "metric-card");
  card.append(el("div", "metric-label", label));
  card.append(el("div", `metric-value ${valueClass}`.trim(), value));
  if (detail) card.append(el("div", "metric-detail", detail));
  return card;
}

function compactNumber(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return "--";
  return number.toLocaleString();
}

function metricsGrid(items, className = "") {
  const grid = el("div", `metrics-grid ${className}`.trim());
  items.forEach((item) => grid.append(metricCard(item.label, item.value, item.detail, item.className)));
  return grid;
}

function botStatusClass(status) {
  if (status === "active" || status === "vps:active") return "positive";
  if (status === "halted" || status === "inactive") return "negative";
  if (status === "degraded") return "warning";
  return "info";
}

function emptyState(text) {
  return el("div", "empty-state", text);
}

function makeTable(columns, rows, emptyText = "No data") {
  if (!rows.length) return emptyState(emptyText);
  const wrap = el("div", "table-wrap");
  const table = el("table");
  const thead = el("thead");
  const headRow = el("tr");
  columns.forEach((column) => headRow.append(el("th", "", column.label)));
  thead.append(headRow);
  table.append(thead);
  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((column) => {
      const td = el("td");
      const value = column.render ? column.render(row) : row[column.key];
      if (value instanceof Node) td.append(value);
      else td.textContent = value ?? "";
      tr.append(td);
    });
    tbody.append(tr);
  });
  table.append(tbody);
  wrap.append(table);
  return wrap;
}

function list(items, renderRight) {
  if (!items.length) return emptyState("No items");
  const wrap = el("div", "list");
  items.forEach((item) => {
    const row = el("article", "list-item");
    const left = el("div");
    left.append(el("div", "list-title", item.title));
    if (item.meta) left.append(el("div", "list-meta", item.meta));
    row.append(left);
    if (renderRight) row.append(renderRight(item));
    wrap.append(row);
  });
  return wrap;
}

function badge(text, kind = "info") {
  return el("span", `badge ${kind === "warn" ? "warn" : kind === "kill" ? "kill" : ""}`.trim(), text);
}

function setHeader(overview) {
  const cells = qs("#rail-cells");
  if (cells) cells.replaceChildren(...buildRailCells(overview));
  const wallet = qs("#wallet-display");
  if (wallet) wallet.textContent = overview.wallet?.display || "--";
  const ts = qs("#timestamp");
  if (ts) ts.textContent = new Date(overview.generated_at).toLocaleTimeString();
}

function railCell(label, value, valueClass = "") {
  const wrap = el("div", "rail-cell");
  wrap.append(el("span", "rail-cell-label", label));
  const v = el("span", `rail-cell-value ${valueClass}`.trim());
  if (value instanceof Node) v.append(value);
  else v.textContent = String(value ?? "--");
  wrap.append(v);
  return wrap;
}

function buildRailCells(overview) {
  const inventory = overview.bot_inventory || [];
  const live = inventory.filter((b) => b.group === "Live").length;
  const paper = inventory.filter((b) => b.group === "Paper").length;
  const recorders = inventory.filter((b) => b.group === "Recorder").length;
  const degraded = overview.services_summary?.degraded || 0;
  const active = overview.services_summary?.active || 0;
  const fleetPnl = (overview.fleet_bots || []).reduce(
    (acc, b) => acc + Number(b.pnl_usd || 0),
    0,
  );
  const mode = String(overview.mode || "paper").toUpperCase();
  const modeNode = el("span", `rail-cell-mode ${overview.mode === "live" ? "live" : "paper"}`, mode);

  return [
    railCell("Mode", modeNode),
    railCell("Live", String(live), live ? "warn" : "muted"),
    railCell("Paper", String(paper), paper ? "info" : "muted"),
    railCell("Recorders", String(recorders), recorders ? "pos" : "warn"),
    railCell(
      "Health",
      `${active}/${active + degraded}`,
      degraded ? "neg" : "pos",
    ),
    railCell(
      "Fleet P&L",
      currency(fleetPnl),
      fleetPnl > 0 ? "pos" : fleetPnl < 0 ? "neg" : "muted",
    ),
  ];
}

function activateTab(tab) {
  state.activeTab = tab;
  qsa(".tab-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tab);
  });
  qsa(".tab-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === tab);
  });
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function loadTab(tab, force = false) {
  if (!force && state.cache.has(tab)) return state.cache.get(tab);
  const payload = await fetchJson(TAB_ENDPOINTS[tab]);
  state.cache.set(tab, payload);
  return payload;
}

function overviewPanels(data) {
  const root = document.createDocumentFragment();
  const stack = el("div", "cockpit-stack");
  const inventory = data.bot_inventory || [];
  const activeBots = inventory.filter((b) => b.group === "Live" || b.group === "Paper");

  stack.append(overviewSummarySection(data, activeBots));
  stack.append(activeBotsSection(activeBots, data.fleet_epoch));
  stack.append(activeRecordersSection(data));
  stack.append(riskStripSection(data));
  stack.append(priorityReviewSection(data));
  stack.append(openPositionsSection(data));

  root.append(stack);
  return root;
}

function overviewSummarySection(data, rows) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", "Overview"));
  head.append(el("span", "section-meta", "operator cockpit"));
  section.append(head);

  const live = rows.filter((r) => r.group === "Live");
  const paper = rows.filter((r) => r.group === "Paper");
  const activeLive = live.filter((r) => String(r.status || "").toLowerCase().includes("active"));
  const activePaper = paper.filter((r) => String(r.status || "").toLowerCase().includes("active"));
  const livePnl = live.reduce((sum, r) => sum + Number(r.realised_pnl_usd || 0), 0);
  const paperPnl = paper.reduce((sum, r) => sum + Number(r.realised_pnl_usd || 0), 0);
  const liveExposure = live.reduce((sum, r) => sum + Number(r.exposure_usd || 0), 0);
  const paperExposure = paper.reduce((sum, r) => sum + Number(r.exposure_usd || 0), 0);
  const degraded = data.services_summary?.degraded || 0;
  const halts = (data.risk?.active_halts || []).length;

  section.append(metricsGrid([
    {
      label: "Live Bots",
      value: `${activeLive.length}/${live.length}`,
      detail: `${currency(livePnl)} realised; ${currency(liveExposure)} exposed`,
      className: activeLive.length === live.length ? "positive" : "warning",
    },
    {
      label: "Paper Bots",
      value: `${activePaper.length}/${paper.length}`,
      detail: `${currency(paperPnl)} realised; ${currency(paperExposure)} exposed`,
      className: activePaper.length === paper.length ? "positive" : "warning",
    },
    {
      label: "Services",
      value: `${data.services_summary?.active || 0} active`,
      detail: degraded ? `${degraded} degraded` : "all reported services healthy",
      className: degraded ? "warning" : "positive",
    },
    {
      label: "Halts",
      value: String(halts),
      detail: halts ? "check risk strip below" : "none",
      className: halts ? "negative" : "positive",
    },
  ], "metrics-grid-three"));

  const liveRows = live.slice(0, 6);
  if (liveRows.length) {
    section.append(makeTable(
      [
        { key: "label", label: "Live Lane", render: (row) => row.label || row.bot_id },
        { key: "status", label: "Status", render: (row) => pill(row.status || "unknown", statusKindForRow(row)) },
        { key: "realised_pnl_usd", label: "Realised", render: (row) => currency(row.realised_pnl_usd || 0) },
        { key: "exposure_usd", label: "Exposure", render: (row) => currency(row.exposure_usd || 0) },
        { key: "open_positions", label: "Open", render: (row) => compactNumber(row.open_positions) },
      ],
      liveRows,
      "No live lanes",
    ));
  }
  return section;
}

function pill(text, kind = "muted") {
  return el("span", `pill ${kind}`.trim(), text);
}

function statusKindForRow(row) {
  if (row.halted) return "neg";
  const status = String(row.status || "").toLowerCase();
  if (status === "active" || status === "vps:active") return "pos";
  if (status === "degraded") return "warn";
  if (status === "halted" || status === "inactive") return "neg";
  return "muted";
}

function modeKind(row) {
  if (row.group === "Live") return "warn";
  if (row.group === "Paper") return "info";
  if (row.group === "Recorder") return "pos";
  return "muted";
}

function activeBotsSection(rows, fleetEpoch) {
  // Two-section layout: Live first (real-money lanes — operator priority),
  // then Paper. Each table renders identical columns so values line up
  // visually. Realised P&L = FIFO matched closed-position P&L (or
  // synthetic-shadow equivalent for shadow lanes, tagged via pnl_kind).
  // Exposure = open-position cost basis + reserved-order notional.
  const wrap = el("div");
  const live = rows.filter((r) => r.group === "Live");
  const paper = rows.filter((r) => r.group === "Paper");
  // Epoch caption surfaces the time window the realised P&L numbers
  // cover. Without this, an operator could mistake the cockpit's
  // ~$80 negative net for the lifetime live ledger (which is closer
  // to -$180 since the live probe started 2026-05-02).
  const epochStart = fleetEpoch?.start
    ? new Date(fleetEpoch.start).toLocaleDateString()
    : null;
  const epochCaption = epochStart
    ? `since ${epochStart}; lifetime numbers in /api/orders`
    : "current operating cohort";
  wrap.append(activeBotsSubsection("Live Bots", live, `real-money lanes — Realised P&L ${epochCaption}`));
  wrap.append(activeBotsSubsection("Paper Bots", paper, `paper, shadow, and replay lanes — Realised P&L ${epochCaption}`));
  return wrap;
}

function activeBotsSubsection(title, rows, subtitle) {
  const section = el("section", "section");
  section.style.marginBottom = "10px";
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", title));
  head.append(el("span", "section-meta", `${rows.length} ${subtitle}`));
  section.append(head);

  if (!rows.length) {
    section.append(el("div", "empty", `No active ${title.toLowerCase()}.`));
    return section;
  }

  const table = el("table");
  const thead = el("thead");
  const headRow = el("tr");
  // Lane | Status | Realised P&L | Exposure | Trades | Fills | Open | Note
  const cols = ["Lane", "Status", "Realised P&L", "Exposure", "Trades", "Fills", "Open", "Note"];
  cols.forEach((label, i) => {
    const th = el("th", i >= 2 && i <= 6 ? "num" : "", label);
    headRow.append(th);
  });
  thead.append(headRow);
  table.append(thead);

  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    const lane = el("td");
    lane.append(el("span", "", row.label || row.bot_id));
    tr.append(lane);
    const statusTd = el("td");
    statusTd.append(pill(row.status || "unknown", statusKindForRow(row)));
    tr.append(statusTd);

    // Realised P&L cell. `pnl_kind` distinguishes:
    //   realised_clob   — real CLOB FIFO (live wallet)
    //   realised_paper  — paper FIFO matched
    //   synthetic_shadow — shadow scale, NOT operator capital
    //   settlement_pending — no realised yet
    const realised = row.realised_pnl_usd;
    const pnlTd = el("td", "num");
    if (realised === null || realised === undefined) {
      pnlTd.textContent = "--";
      pnlTd.classList.add("muted");
    } else {
      pnlTd.textContent = currency(realised);
      const n = Number(realised);
      if (n > 0) pnlTd.classList.add("pos");
      else if (n < 0) pnlTd.classList.add("neg");
      if (row.pnl_kind === "synthetic_shadow") {
        pnlTd.title = "Shadow scale (not operator capital). See note for ROI.";
        pnlTd.append(el("span", "muted", " syn"));
      }
    }
    tr.append(pnlTd);

    const exposure = row.exposure_usd;
    const expTd = el("td", "num");
    if (exposure === null || exposure === undefined) {
      expTd.textContent = "--";
      expTd.classList.add("muted");
    } else if (Number(exposure) === 0) {
      expTd.textContent = "$0.00";
      expTd.classList.add("muted");
    } else {
      expTd.textContent = currency(exposure);
    }
    tr.append(expTd);

    tr.append(el("td", "num", compactNumber(row.orders)));
    tr.append(el("td", "num", compactNumber(row.fills)));
    tr.append(el("td", "num", compactNumber(row.open_positions)));
    tr.append(el("td", "muted", trunc(row.headline || row.time_to_decision || "", 70)));
    tbody.append(tr);
  });
  table.append(tbody);
  section.append(table);
  return section;
}

function activeRecordersSection(data) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", "Active Recorders"));
  const services = data.services || {};
  const local = data.recorder_comparison?.local || {};
  const remote = data.recorder_comparison?.vps || {};
  const vpsNode = data.vps_node || {};
  const inventory = data.bot_inventory || [];

  const localCounts = local.counts || {};
  const remoteCounts = remote.counts || {};
  const botEInv = inventory.find((b) => b.bot_id === "bot_e");
  const botHInv = inventory.find((b) => b.bot_id === "bot_h_maker_v2");
  const walletInv = inventory.find((b) => b.bot_id === "wallet_observer");
  const botIInv = inventory.find((b) => b.bot_id === "bot_i_persistence" && b.group === "Recorder");
  const botH = vpsNode.bot_h_maker_v2 || {};
  const wallet = vpsNode.wallet_observer || {};
  const walletHeadline = wallet.headline || {};
  const persistence = data.persistence_paper || {};

  const recorders = [];
  // Helper: derive host label from systemd service state suffix.
  // the bot container services report 'active' / 'inactive'; VPS-bridge services
  // report 'vps:active' / 'vps:unknown'. Daily timers report
  // 'timer:active'. The host label feeds the new Host column so
  // the operator can see at a glance where each recorder runs.
  const hostFor = (state) => {
    const s = String(state || "").toLowerCase();
    if (s.startsWith("vps")) return "VPS";
    if (s === "unknown" || s === "") return "?";
    return "the bot container";
  };

  if (botEInv) {
    const state = services["polymarket-bot-e-recorder"] || "unknown";
    recorders.push({
      name: "Crypto Recorder (E)",
      service: "polymarket-bot-e-recorder",
      serviceState: state,
      host: hostFor(state),
      dbBytes: local.db_size_bytes,
      eventsLifetime: localCounts.pm_events,
      cexTradesLifetime: localCounts.cex_trades,
      ratePerMin: local.pm_events_per_min,
      heartbeatAge: local.heartbeat_age_sec,
      gaps: local.gaps,
      note: "shared crypto recorder; ADR-122 indefinite",
      timeToDecision: botEInv.time_to_decision,
    });
  }
  recorders.push({
    name: "VPS Crypto Feed",
    service: "longshot-crypto-recorder-vps-paper-feed",
    serviceState: remote.ok ? "vps:active" : "unknown",
    host: "VPS",
    dbBytes: remote.db_size_bytes,
    eventsLifetime: remoteCounts.pm_events,
    cexTradesLifetime: remoteCounts.cex_trades,
    ratePerMin: remote.pm_events_per_min,
    heartbeatAge: remote.heartbeat_age_sec,
    gaps: remote.gaps,
    note: "VPS shadow feed; BTC/ETH/SOL/XRP/DOGE",
    timeToDecision: null,
  });
  if (botHInv) {
    // Bot H Maker V2 recorder migrated VPS → the bot container in Session 304
    // (registry uses `polymarket-bot-h-maker-v2-recorder` without
    // `-vps` suffix). Probe both names for back-compat in case a
    // deploy lags the registry on either side.
    const botHService = services["polymarket-bot-h-maker-v2-recorder"]
      ? "polymarket-bot-h-maker-v2-recorder"
      : "polymarket-bot-h-maker-v2-recorder-vps";
    const state = services[botHService] || "unknown";
    recorders.push({
      name: "Maker Recorder (H)",
      service: botHService,
      serviceState: state,
      host: hostFor(state),
      dbBytes: botH.size_bytes,
      eventsLifetime: (botH.counts || {}).pm_events,
      cexTradesLifetime: null,
      ratePerMin: botH.events_per_min_5m,
      heartbeatAge: (botH.heartbeat || {}).last_age_sec,
      gaps: 0,
      note: "ADR-134 Phase 1 paper recorder; OQ-100 burn-in",
      timeToDecision: botHInv.time_to_decision,
    });
  }
  if (walletInv) {
    const state = services["polymarket-wallet-observer"] || "unknown";
    recorders.push({
      name: "Wallet Observer",
      service: "polymarket-wallet-observer",
      serviceState: state,
      host: hostFor(state),
      dbBytes: wallet.size_bytes,
      eventsLifetime: walletHeadline.total_fills,
      cexTradesLifetime: null,
      ratePerMin: null,
      heartbeatAge: walletHeadline.last_fill_age_sec,
      gaps: 0,
      note: "ADR-137 forward gate; first report 2026-05-15",
      timeToDecision: walletInv.time_to_decision,
    });
  }
  if (botIInv) {
    const cellA = (persistence.per_cell_n || {}).A_borderline_5m_15m || 0;
    const cellB = (persistence.per_cell_n || {}).B_tail_15m || 0;
    const halt = !!persistence.halt_flag_present;
    const roiPct = ((persistence.post_fee_roi || 0) * 100).toFixed(2);
    const persistenceServiceState = halt
      ? "halted"
      : (services["polymarket-persistence-paper"] || "unknown");
    // Bot I fires once per day at 06:30 UTC. Render the last-run time
    // in the note so the operator sees "06:30 UTC last fire" rather
    // than just an N-hours-ago heartbeat age.
    let lastRunHHMM = "--";
    if (persistence.last_run_ms) {
      const d = new Date(persistence.last_run_ms);
      const hh = String(d.getUTCHours()).padStart(2, "0");
      const mm = String(d.getUTCMinutes()).padStart(2, "0");
      lastRunHHMM = `${hh}:${mm}Z`;
    }
    recorders.push({
      name: halt ? "Persistence Paper (I) — HALTED" : "Persistence Paper (I)",
      service: "polymarket-persistence-paper",
      serviceState: persistenceServiceState,
      host: hostFor(persistenceServiceState),
      cadence: "daily", // 06:30 UTC oneshot — heartbeat thresholds in hours
      dbBytes: persistence.size_bytes,
      eventsLifetime: persistence.n_entries,
      cexTradesLifetime: null,
      ratePerMin: null, // daily-timer oneshot, not a streaming feed
      heartbeatAge: persistence.heartbeat_age_sec,
      gaps: halt ? 1 : 0,
      note: `ADR-128 paper; A=${cellA}/50, B=${cellB}/50, ROI ${roiPct}%; last run ${lastRunHHMM}`,
      timeToDecision: botIInv.time_to_decision,
    });
  }

  head.append(el("span", "section-meta", `${recorders.length} active`));
  section.append(head);

  if (!recorders.length) {
    section.append(el("div", "empty", "No active recorders."));
    return section;
  }

  const table = el("table");
  const thead = el("thead");
  const headRow = el("tr");
  // Host column added 2026-05-10 to surface the bot container vs VPS distribution
  // after Bot H + Wallet Observer migrated VPS → the bot container.
  ["Recorder", "Host", "Service", "Decision", "DB", "Events", "CEX Trades", "Rate /min", "Heartbeat", "Gaps", "Note"].forEach((label, i) => {
    const th = el("th", i >= 4 && i <= 9 ? "num" : "", label);
    headRow.append(th);
  });
  thead.append(headRow);
  table.append(thead);

  const tbody = el("tbody");
  recorders.forEach((r) => {
    const tr = el("tr");
    tr.append(el("td", "", r.name));
    // Host pill: the bot container = info (cyan), VPS = warn (amber), unknown = muted.
    const hostTd = el("td");
    const host = r.host || "?";
    const hostKind = host === "VPS" ? "warn" : host === "the bot container" ? "info" : "muted";
    hostTd.append(pill(host, hostKind));
    tr.append(hostTd);
    const svc = el("td");
    const kind = String(r.serviceState).toLowerCase().includes("active") ? "pos" : (r.serviceState === "unknown" ? "muted" : "neg");
    svc.append(pill(r.serviceState, kind));
    tr.append(svc);
    tr.append(el("td", "muted", trunc(r.timeToDecision || "--", 28)));
    tr.append(el("td", "num", formatBytes(r.dbBytes)));
    tr.append(el("td", "num", compactNumber(r.eventsLifetime)));
    tr.append(el("td", "num", r.cexTradesLifetime == null ? "--" : compactNumber(r.cexTradesLifetime)));
    tr.append(el("td", "num", r.ratePerMin == null ? "--" : Number(r.ratePerMin).toFixed(1)));
    const hbAge = r.heartbeatAge;
    const hbTd = el("td", "num");
    if (hbAge == null) {
      hbTd.textContent = "--";
      hbTd.classList.add("muted");
    } else {
      hbTd.textContent = formatAgeShort(hbAge);
      // Streaming recorders should heartbeat every ≤2 minutes;
      // daily-timer recorders only fire once per 24h, so a heartbeat
      // age of 10–25h is healthy and only ≥30h is a real stall.
      const cadence = r.cadence || "streaming";
      const [okMax, warnMax] = cadence === "daily"
        ? [26 * 3600, 30 * 3600]
        : [120, 600];
      hbTd.classList.add(hbAge < okMax ? "pos" : hbAge < warnMax ? "warn" : "neg");
    }
    tr.append(hbTd);
    const gapsTd = el("td", "num", String(r.gaps ?? "--"));
    if (Number(r.gaps) > 0) gapsTd.classList.add("warn");
    tr.append(gapsTd);
    tr.append(el("td", "muted", trunc(r.note, 56)));
    tbody.append(tr);
  });
  table.append(tbody);
  section.append(table);
  return section;
}

function riskStripSection(data) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", "Risk & Health"));
  section.append(head);

  const risk = data.risk || {};
  const degraded = risk.degraded_services || [];
  const halts = risk.active_halts || [];
  const cells = [];

  if (!degraded.length && !halts.length) {
    section.append(el("div", "strip-empty", "All active services healthy. No active-bot halts."));
    return section;
  }

  const strip = el("div", "strip");
  degraded.forEach((d) => {
    strip.append(stripItem(`${d.service}: ${d.state}`, "warn"));
  });
  halts.forEach((h) => {
    strip.append(stripItem(`${h.bot_id} HALTED`, "neg"));
  });
  section.append(strip);
  return section;
}

function stripItem(text, kind = "muted") {
  return el("div", `strip-item ${kind}`.trim(), text);
}

function priorityReviewSection(data) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", "Priority Review"));
  section.append(head);

  const alerts = data.priority_alerts || [];
  if (!alerts.length) {
    section.append(el("div", "strip-empty", "No priority edge alerts."));
    return section;
  }
  const strip = el("div", "strip");
  alerts.forEach((a) => {
    strip.append(stripItem(`${a.label}: ${a.note}`, "warn"));
  });
  section.append(strip);
  return section;
}

function openPositionsSection(data) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h2", "section-title", "Open Positions"));
  const inventory = data.bot_inventory || [];
  // Recorder rows reuse the `open_positions` field for sensor counts
  // (subscribed markets, distinct wallets, captured entries) — those are
  // not real trading positions, so exclude them from this teaser.
  const tradingLanes = inventory.filter((b) => b.group === "Live" || b.group === "Paper");
  const open = tradingLanes
    .filter((b) => Number(b.open_positions) > 0)
    .sort((a, b) => Number(b.open_positions) - Number(a.open_positions))
    .slice(0, 8);
  head.append(el("span", "section-meta", `${open.length} of ${tradingLanes.length} trading lanes`));
  section.append(head);

  if (!open.length) {
    section.append(el("div", "empty", "No open positions across active lanes."));
    return section;
  }

  const table = el("table");
  const thead = el("thead");
  const headRow = el("tr");
  ["Lane", "Open Pos", "Open Orders", "Service"].forEach((label, i) => {
    headRow.append(el("th", i === 1 || i === 2 ? "num" : "", label));
  });
  thead.append(headRow);
  table.append(thead);

  const tbody = el("tbody");
  open.forEach((row) => {
    const tr = el("tr");
    tr.append(el("td", "", row.label || row.bot_id));
    tr.append(el("td", "num", compactNumber(row.open_positions)));
    tr.append(el("td", "num", compactNumber(row.open_orders)));
    tr.append(el("td", "muted", trunc(row.service || "", 38)));
    tbody.append(tr);
  });
  table.append(tbody);
  section.append(table);
  return section;
}

function formatBytes(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "--";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[i]}`;
}

function formatAgeShort(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s)) return "--";
  if (s < 60) return `${s.toFixed(0)}s`;
  if (s < 3600) return `${(s / 60).toFixed(0)}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
}

function botDPanels(data) {
  // Bot D weather lanes — stripped to operator-essential surface:
  // Live Probe state, Spike + Spike-Short paper-validation gate progress,
  // resolved P&L (with ex-outlier ROI), recent activity. Deeper telemetry
  // (gribstream usage, forecast capture, station coverage, scan summary,
  // wallet readiness checklist) lives in scripts/reports.
  const root = document.createDocumentFragment();
  const positions = data.positions || [];
  const readinessReport = data.readiness || {};
  const resolvedPnl = readinessReport.resolved_pnl || {};
  const dailyPnl = resolvedPnl.daily_low_lockup || {};
  const dailyExLargest = dailyPnl.ex_largest_win || {};
  const dailyExLargestTwo = dailyPnl.ex_largest_two_wins || {};
  const tradeMetrics = data.trade_metrics || {};
  const liveProbe = data.live_probe || {};
  const liveProbeSimple = liveProbe.simple || {};
  const liveProbeTrades = liveProbe.trade_metrics || {};
  const liveProbeOrders = liveProbe.order_metrics || {};
  const liveProbeCaps = liveProbe.caps || {};
  const spike = data.spike || {};
  const spikeSimple = spike.simple || {};
  const spikeOrders = spike.order_metrics || {};
  const spikeTrades = spike.trade_metrics || {};
  const spikeValidation = spike.validation || {};
  const spikeClosed = Number(spikeTrades.settlement_fills_count || spikeTrades.closed_trades || 0);
  const spikeShort = data.spike_short || {};
  const spikeShortSimple = spikeShort.simple || {};
  const spikeShortOrders = spikeShort.order_metrics || {};
  const spikeShortTrades = spikeShort.trade_metrics || {};
  const spikeShortValidation = spikeShort.validation || {};
  const spikeShortClosed = Number(spikeShortTrades.settlement_fills_count || spikeShortTrades.closed_trades || 0);

  const dailyUsedPct = Number(liveProbeCaps.daily_used_pct || 0);
  const exposureUsedPct = Number(liveProbeCaps.open_exposure_used_pct || 0);
  const slotsLeft = Number(liveProbeCaps.open_positions_remaining || 0);

  root.append(makePanel({
    title: "Bot D Live Probe",
    subtitle: "Tiny-live ledger — only real-money lane in the fleet besides Bot G",
    span: 12,
    body: metricsGrid([
      { label: "Service", value: liveProbeSimple.active ? "ACTIVE" : "INACTIVE", detail: "polymarket-bot-d-live", className: liveProbeSimple.active ? "positive" : "warning" },
      { label: "Live Fills", value: String(liveProbeTrades.live_fills_count || 0), detail: `${liveProbeOrders.live_open_orders || 0} open orders` },
      { label: "Realised P&L", value: currency(liveProbeTrades.realised_pnl_usd || 0), detail: `${liveProbeTrades.closed_trades || 0} closed live`, className: classifyNumber(liveProbeTrades.realised_pnl_usd || 0) },
      { label: "Daily Gross", value: currency(liveProbeCaps.daily_gross_usd || 0), detail: `${currency(liveProbeCaps.daily_remaining_usd || 0)} left of ${currency(liveProbeCaps.daily_limit_usd || 0)}`, className: dailyUsedPct >= 90 ? "negative" : dailyUsedPct >= 70 ? "warning" : "positive" },
      // Exposure is cost basis from the local ledger (NOT wallet current
      // value). The hourly wallet reconciler keeps the OPEN set truthful
      // to /positions on the chain.
      { label: "Exposure (cost basis)", value: currency(liveProbeCaps.filled_plus_resting_exposure_usd || 0), detail: `${currency(liveProbeCaps.open_exposure_remaining_usd || 0)} left of ${currency(liveProbeCaps.open_exposure_limit_usd || 0)}`, className: exposureUsedPct >= 90 ? "negative" : exposureUsedPct >= 70 ? "warning" : "positive" },
      { label: "Slots (wallet-reconciled)", value: `${liveProbeCaps.open_positions || 0}/${liveProbeCaps.max_open_positions || 0}`, detail: `${slotsLeft} left`, className: slotsLeft <= 2 ? "warning" : "positive" },
    ], "metrics-grid-six"),
  }));

  const spikeRows = [
    {
      lane: "D-Spike (6-12h)",
      spec: spike,
      simple: spikeSimple,
      orders: spikeOrders,
      trades: spikeTrades,
      validation: spikeValidation,
      closed: spikeClosed,
    },
    {
      lane: "D-Spike-Short (0-6h)",
      spec: spikeShort,
      simple: spikeShortSimple,
      orders: spikeShortOrders,
      trades: spikeShortTrades,
      validation: spikeShortValidation,
      closed: spikeShortClosed,
    },
  ];
  root.append(makePanel({
    title: "Weather Cheap-YES Paper Lanes",
    subtitle: "Strategy E + E2; paper-only until 200-close validation gate clears",
    span: 12,
    body: makeTable(
      [
        { key: "lane", label: "Lane" },
        { key: "service", label: "Service", render: (row) => pill(row.simple.active ? "ACTIVE" : "INACTIVE", row.simple.active ? "pos" : "warn") },
        { key: "band", label: "Band", render: (row) => row.spec.entry_band || "1c-15c" },
        { key: "ttr", label: "TTR", render: (row) => row.spec.ttr_window || "--" },
        { key: "orders", label: "Orders", render: (row) => compactNumber(row.orders.total_orders || 0) },
        { key: "fills", label: "Fills", render: (row) => compactNumber(row.trades.filled_trades_count || 0) },
        { key: "closed", label: "Closed", render: (row) => compactNumber(row.closed) },
        { key: "gate", label: "Gate", render: (row) => `${Math.max(0, Number(row.validation.closed_target || 200) - row.closed)} left` },
      ],
      spikeRows,
      "No paper lanes reporting",
    ),
  }));

  root.append(makePanel({
    title: "Resolved P&L",
    subtitle: "Daily low-lockup paper cohort — ex-outlier ROI is the gate that matters",
    span: 12,
    body: metricsGrid([
      { label: "Closed", value: String(dailyPnl.closed || 0), detail: `${dailyPnl.wins || 0} wins` },
      { label: "Daily ROI", value: dailyPnl.roi_pct == null ? "n/a" : percent(dailyPnl.roi_pct), detail: "resolved FIFO only", className: classifyNumber(dailyPnl.roi_pct || 0) },
      { label: "Ex-1 ROI", value: dailyExLargest.roi_pct == null ? "n/a" : percent(dailyExLargest.roi_pct), detail: "without largest win", className: classifyNumber(dailyExLargest.roi_pct || 0) },
      { label: "Ex-2 ROI", value: dailyExLargestTwo.roi_pct == null ? "n/a" : percent(dailyExLargestTwo.roi_pct), detail: "without two largest wins", className: classifyNumber(dailyExLargestTwo.roi_pct || 0) },
    ]),
  }));

  root.append(makePanel({
    title: "Recent Activity",
    subtitle: `${positions.length} open paper positions`,
    span: 12,
    body: makeTable(
      [
        { key: "filled_at", label: "Time", render: (row) => formatTimestamp(row.filled_at) },
        { key: "execution_mode", label: "Mode" },
        { key: "side", label: "Side" },
        { key: "price", label: "Price" },
        { key: "size", label: "Size" },
        { key: "cash_flow_usd", label: "Cash", render: (row) => currency(row.cash_flow_usd || 0) },
      ],
      (data.recent_trades || []).slice(0, 12),
      tradeMetrics.filled_trades_count ? "No recent trades in window" : "No trades recorded yet",
    ),
  }));

  if (data.error) {
    root.append(makePanel({ title: "Error", subtitle: "Query failure", span: 12, body: emptyState(data.error) }));
  }
  return root;
}

function botGPanels(data) {
  // Bot G Prime — late-dislocation catcher on crypto Up/Down markets.
  // Stripped to operator-essential surface: live probe state, paper cohorts
  // table, recent activity. Deeper diagnostics (transfer audits, gate
  // checks, capacity labels, CEX split) live in scripts/reports.
  const root = document.createDocumentFragment();
  const trader = data.trader || data || {};
  const liveTrader = data.live_trader || {};
  const liveProbe = liveTrader.live_probe || data.live_probe || trader.live_probe || {};
  const liveArchive = data.live_archive || {};
  const liveLegacy = liveArchive.legacy || {};
  const liveLegacyTrades = liveLegacy.trade_metrics || {};
  const liveLegacyOrders = liveLegacy.order_metrics || {};
  const leadBucketReport = data.lead_bucket_report || {};
  const researchShadows = data.research_shadows || [];
  const tradeMetrics = trader.trade_metrics || {};
  const liveTradeMetrics = liveTrader.trade_metrics || {};
  const liveOrderMetrics = liveTrader.order_metrics || {};
  const positionsOpen = trader.positions_open || [];
  const livePositionsOpen = liveTrader.positions_open || [];
  const liveFills = Number(liveProbe.live_fills_count || liveTradeMetrics.filled_trades_count || 0);

  const livePolicyConflict = liveProbe.status === "active_despite_adr_135_pause";
  const livePaused = liveProbe.status === "paused_by_adr_135" || liveTrader.active === false;
  const liveRuntimeLabel = livePolicyConflict
    ? "ACTIVE / ADR CONFLICT"
    : (livePaused ? "PAUSED" : (liveProbe.live_probe_active ? "LIVE" : "WAITING"));
  const liveRuntimeKind = (livePolicyConflict || livePaused)
    ? "negative"
    : (liveProbe.live_probe_active ? "warning" : "positive");

  root.append(makePanel({
    title: "Live Probe ($1, ADR-149)",
    subtitle: liveProbe.pause_reason || "$1 fixed-notional high-tail probe; 6-8c, 45s, ETH/SOL",
    span: 12,
    body: metricsGrid([
      { label: "Runtime", value: liveRuntimeLabel, detail: `${liveProbe.bot_env || liveTrader.env || "unknown"} / dry-run ${liveProbe.effective_paper === false ? "no" : "yes"}`, className: liveRuntimeKind },
      { label: "Live Fills", value: String(liveFills), detail: liveFills > 0 ? "real-money fills" : "no real-money fills yet", className: liveFills > 0 ? "positive" : "" },
      { label: "Open Live", value: String(livePositionsOpen.length), detail: `${liveOrderMetrics.open_orders || 0} open orders` },
      { label: "Realised", value: currency(liveTradeMetrics.realised_pnl_usd || 0), detail: `${liveTradeMetrics.closed_trades || 0} closed live`, className: classifyNumber(liveTradeMetrics.realised_pnl_usd || 0) },
      { label: "Epoch", value: liveArchive.start ? "ADR-149" : "current", detail: liveArchive.start ? `since ${formatTimestamp(liveArchive.start)}` : "dashboard baseline" },
      { label: "Live Wallet", value: currency(liveProbe.proposed_live_wallet_usd || liveTrader.bankroll_usd || 0), detail: `${currency(liveProbe.proposed_starting_trade_usd || 1)} per entry` },
      { label: "Archived Legacy", value: currency(liveLegacyTrades.realised_pnl_usd || 0), detail: `${liveLegacyOrders.total_orders || 0} old orders / ${liveLegacyTrades.closed_trades || 0} closed`, className: classifyNumber(liveLegacyTrades.realised_pnl_usd || 0) },
      { label: "Daily Cap", value: `${liveProbe.proposed_daily_entry_cap || 20} entries`, detail: `${currency(liveProbe.proposed_gross_notional_cap_usd || 100)} gross` },
    ], "metrics-grid-six"),
  }));

  // Filter out cohort lanes that the registry has archived. Currently
  // archived: bot_g_prime_late_cheap and bot_g_prime_take_profit (per
  // ADR-140). They still have historical rows in the lead-bucket
  // report, but cluttering the cockpit with INACTIVE lanes adds noise.
  const ARCHIVED_BOT_G_LANES = new Set([
    "bot_g_prime_late_cheap",
    "bot_g_prime_take_profit",
  ]);
  const liveEpochCost = Number(liveTradeMetrics.entry_cost_usd || 0);
  const liveEpochPnl = Number(liveTradeMetrics.realised_pnl_usd || 0);
  const liveEpochRow = {
    bot_id: "bot_g_prime_live",
    label: "Live ADR-149",
    band: "6-8c",
    window: "45s",
    status: liveProbe.live_probe_active ? "active" : (liveRuntimeLabel || "unknown").toLowerCase(),
    resolved: Number(liveTradeMetrics.closed_trades || 0),
    won: Number(liveTradeMetrics.wins || 0),
    pnl_usd: liveEpochPnl,
    roi_pct: liveEpochCost > 0 ? (liveEpochPnl / liveEpochCost) * 100 : null,
    roi_ex_largest_two_pct: null,
  };
  const cohortRows = (leadBucketReport.rows || [])
    .filter((row) => !ARCHIVED_BOT_G_LANES.has(row.bot_id))
    .filter((row) => row.bot_id !== "bot_g_prime_live")
    .map((row) => {
      const shadowMatch = (researchShadows.find((s) => s.bot_id === row.bot_id) || {}).simple || {};
      return {
        ...row,
        band: row.bot_id === "bot_g_prime_live" ? "6-8c"
          : row.bot_id === "bot_g_prime" ? "4-8c"
          : row.bot_id === "bot_g_prime_shadow" ? "3.5-5.5c"
          : row.bot_id === "bot_g_prime_high_tail" ? "6-8c"
          : "--",
        window: (row.bot_id === "bot_g_prime" || row.bot_id === "bot_g_prime_live" || row.bot_id === "bot_g_prime_high_tail") ? "45s" : "60s",
        status: shadowMatch.status
          || (row.bot_id === "bot_g_prime_live"
              ? (liveTrader.runtime_state?.available ? "active" : "unknown")
              : (trader.runtime_state?.available ? "active" : "unknown")),
      };
    });
  cohortRows.unshift(liveEpochRow);

  root.append(makePanel({
    title: "Bot G Cohorts",
    subtitle: leadBucketReport.generated_at
      ? `Live row is current ADR-149 epoch; paper rows from report ${formatTimestamp(leadBucketReport.generated_at)}`
      : "Daily lead-bucket report timer pending",
    span: 12,
    body: makeTable(
      [
        { key: "label", label: "Lane" },
        { key: "band", label: "Band" },
        { key: "window", label: "Window" },
        { key: "status", label: "Status", render: (row) => pill(row.status || "unknown", row.status === "active" || row.status === "vps:active" ? "pos" : "muted") },
        { key: "resolved", label: "Resolved" },
        { key: "won", label: "Wins" },
        { key: "pnl_usd", label: "P&L", render: (row) => row.pnl_usd == null ? "--" : currency(row.pnl_usd) },
        { key: "roi_pct", label: "ROI", render: (row) => row.roi_pct == null ? "--" : percent(row.roi_pct) },
        { key: "roi_ex_largest_two_pct", label: "Ex-Top-2 ROI", render: (row) => row.roi_ex_largest_two_pct == null ? "--" : percent(row.roi_ex_largest_two_pct) },
      ],
      cohortRows,
      "No lead-bucket rows yet",
    ),
  }));

  root.append(makePanel({
    title: "Recent Activity",
    subtitle: "Latest paper + live entries and fills",
    span: 12,
    body: [
      el("div", "panel-subtitle", `Open paper positions: ${positionsOpen.length}`),
      makeTable(
        [
          { key: "filled_at", label: "Time", render: (row) => formatTimestamp(row.filled_at) },
          { key: "execution_mode", label: "Mode" },
          { key: "side", label: "Side" },
          { key: "price", label: "Price", render: (row) => Number(row.price || 0).toFixed(4) },
          { key: "size", label: "Size", render: (row) => Number(row.size || 0).toFixed(2) },
        ],
        (tradeMetrics.recent_trades || []).slice(0, 12),
        "No fills recorded yet",
      ),
    ],
  }));

  return root;
}

function ordersPanels(data) {
  // Orders & Positions — operator surface for what's currently live or
  // resting on the books. Stripped to two tables: open positions and
  // a unified recent activity feed.
  const root = document.createDocumentFragment();
  root.append(makePanel({
    title: "Open Positions",
    subtitle: `${(data.open_positions || []).length} positions across active lanes`,
    span: 12,
    body: makeTable(
      [
        { key: "market", label: "Market", render: (row) => trunc(row.market, 40) },
        { key: "bot_id", label: "Bot" },
        { key: "size", label: "Size" },
        { key: "entry_price", label: "Entry" },
        { key: "current_price", label: "Current" },
        { key: "pnl_usd", label: "P&L", render: (row) => row.pnl_usd == null ? "--" : currency(row.pnl_usd) },
      ],
      data.open_positions || [],
      "No open positions",
    ),
  }));
  root.append(makePanel({
    title: "Recent Trades",
    subtitle: "Last fills across bots",
    span: 12,
    body: makeTable(
      [
        { key: "filled_at", label: "Time", render: (row) => formatTimestamp(row.filled_at) },
        { key: "bot_id", label: "Bot" },
        { key: "execution_mode", label: "Mode" },
        { key: "market", label: "Market", render: (row) => trunc(row.market, 28) },
        { key: "side", label: "Side" },
        { key: "price", label: "Price" },
        { key: "size", label: "Size" },
        { key: "cash_flow_usd", label: "Cash", render: (row) => currency(row.cash_flow_usd || 0) },
      ],
      (data.recent_trades || []).slice(0, 25),
      "No trades recorded yet",
    ),
  }));
  return root;
}

function eventsPanels(data) {
  // Events & Health — service state, current halts, and the event tape.
  // Severity-mix bars dropped (decorative). Halt tape is filtered to
  // currently-halted lanes only; the historical halt audit lives in DB.
  const root = document.createDocumentFragment();

  const serviceList = el("div", "service-grid");
  Object.entries(data.services || {}).forEach(([name, status]) => {
    const card = el("article", "service-card");
    card.append(el("strong", "", name.replace("polymarket-", "")));
    card.append(el("div", botStatusClass(status), status));
    serviceList.append(card);
  });
  root.append(makePanel({
    title: "Service Health",
    subtitle: "systemd state snapshot",
    span: 6,
    body: serviceList,
  }));

  const activeHalts = (data.halts || []).filter((halt) => halt.halted);
  root.append(makePanel({
    title: "Active Halts",
    subtitle: activeHalts.length ? `${activeHalts.length} bots halted` : "No active halts",
    span: 6,
    body: activeHalts.length
      ? list(
          activeHalts.map((halt) => ({
            title: halt.bot_id,
            meta: halt.reason || "No halt reason",
            severity: "kill",
          })),
          (item) => badge("HALTED", item.severity),
        )
      : el("div", "empty", "All active lanes unhalted."),
  }));

  root.append(makePanel({
    title: "Event Tape",
    subtitle: "Latest 30 events from active lanes",
    span: 12,
    body: makeTable(
      [
        { key: "created_at", label: "Time", render: (row) => formatTimestamp(row.created_at) },
        { key: "bot_id", label: "Bot", render: (row) => row.bot_id || "system" },
        { key: "event_type", label: "Type" },
        { key: "severity", label: "Sev", render: (row) => el("span", SEVERITY_CLASS[row.severity] || "", row.severity) },
        { key: "message", label: "Message", render: (row) => trunc(row.message, 120) },
      ],
      data.events || [],
      "No events",
    ),
  }));
  return root;
}

function walletObserverPanels(data) {
  // Wallet observer — ADR-137 forward-validation feed.
  // Slim surface: health/freshness header + per-tier 24h activity.
  // Side distribution and collector state are debug-only and live in
  // scripts/research/wallet_observer_report.py.
  const root = document.createDocumentFragment();
  const simple = data.simple || {};
  const summary = data.summary || {};
  const headline = summary.headline || {};
  const tier24h = summary.tier_24h || [];
  const sizeMb = Number(summary.size_bytes || 0) / (1024 * 1024);
  const lastFillAge = headline.last_fill_age_sec;
  const dataSource = data.data_source || "the bot container";

  root.append(makePanel({
    title: "Wallet Observer",
    subtitle: `Passive Polygon CTF recorder on ${dataSource} — ADR-137 forward-validation feed for ${data.wallet_count || 245} retail-tier wallets`,
    span: 12,
    body: metricsGrid([
      { label: "Service", value: simple.active ? "ACTIVE" : "INACTIVE", detail: "polymarket-wallet-observer", className: simple.active ? "positive" : "warning" },
      { label: "Fills 24h", value: compactNumber(headline.fills_24h || 0), detail: `${headline.distinct_wallets_24h || 0}/${data.wallet_count || 245} wallets active` },
      { label: "Fills 7d", value: compactNumber(headline.fills_7d || 0), detail: "rolling 7-day capture" },
      { label: "Total Fills", value: compactNumber(headline.total_fills || 0), detail: "lifetime captures" },
      { label: "Last Fill", value: lastFillAge == null ? "--" : (lastFillAge < 600 ? `${lastFillAge}s ago` : `${Math.round(lastFillAge / 60)}m ago`), detail: "freshness; <600s = healthy", className: lastFillAge != null && lastFillAge < 600 ? "positive" : (lastFillAge == null ? "warning" : "negative") },
      { label: "DB Size", value: `${sizeMb.toFixed(1)} MB`, detail: "wallet_observer.db" },
    ], "metrics-grid-six"),
  }));

  root.append(makePanel({
    title: "Per-Tier Activity (24h)",
    subtitle: "Tier A = PolyVerify humans (97 wallets); Tier B = unknown profitable (148 wallets)",
    span: 12,
    body: makeTable(
      [
        { key: "tier", label: "Tier" },
        { key: "n_fills", label: "Fills" },
        { key: "n_wallets", label: "Distinct Wallets" },
        { key: "n_buys", label: "BUYs" },
        { key: "n_sells", label: "SELLs" },
      ],
      tier24h,
      "No tier activity in last 24h",
    ),
  }));

  return root;
}

function renderTab(tab, payload) {
  const panel = qs(`#${CSS.escape(tab)}-panels`);
  if (!panel) return;
  panel.replaceChildren();
  if (tab === "overview") {
    panel.append(overviewPanels(payload));
    setHeader(payload);
    return;
  }
  if (tab === "bot-d") {
    panel.append(botDPanels(payload));
    return;
  }
  if (tab === "bot-g") {
    panel.append(botGPanels(payload));
    return;
  }
  if (tab === "wallet-observer") {
    panel.append(walletObserverPanels(payload));
    return;
  }
  if (tab === "orders") {
    panel.append(ordersPanels(payload));
    return;
  }
  if (tab === "events") {
    panel.append(eventsPanels(payload));
  }
}

async function refresh(tab, force = false) {
  try {
    const payload = await loadTab(tab, force);
    renderTab(tab, payload);
  } catch (error) {
    const panel = qs(`#${CSS.escape(tab)}-panels`);
    panel.replaceChildren(makePanel({ title: "Dashboard Error", subtitle: tab, span: 12, body: emptyState(error.message) }));
  }
}

async function boot() {
  qsa(".tab-button").forEach((button) => {
    button.addEventListener("click", async () => {
      activateTab(button.dataset.tab);
      await refresh(button.dataset.tab);
    });
  });
  // Allow ?tab=NAME deep-linking so headless screenshots and bookmarks
  // can land directly on a drilldown without a click.
  const params = new URLSearchParams(window.location.search || "");
  const requested = params.get("tab");
  if (requested && TAB_ENDPOINTS[requested]) {
    state.activeTab = requested;
  }
  activateTab(state.activeTab);
  await refresh("overview", true);
  if (state.activeTab !== "overview") {
    await refresh(state.activeTab, true);
  }
  setInterval(async () => {
    state.cache.clear();
    await refresh("overview", true);
    if (state.activeTab !== "overview") {
      await refresh(state.activeTab, true);
    }
  }, REFRESH_MS);
}

boot();
