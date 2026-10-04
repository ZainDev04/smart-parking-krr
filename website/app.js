/* Smart Parking KRR website. All data comes from data.js, which
   tools/build_site.py exports from the reasoning engine. */
(() => {
  "use strict";
  document.documentElement.classList.add("js");
  const D = window.KRR;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const reduced = () => reducedQuery.matches;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // escape, then set ids (s_a1, p_ali, R25) in the code face: Poppins draws 1 and l alike
  const fmt = (s) => esc(s).replace(/\b(R\d{2}|IC\d|[a-z]+_[a-z0-9_]+)\b/g, '<span class="id">$1</span>');
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const hhmm = (t) => String(Math.floor(t / 100)).padStart(2, "0") + ":" + String(t % 100).padStart(2, "0");
  const ymd = (n) => {
    const s = String(n);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${Number(s.slice(6))} ${months[Number(s.slice(4, 6)) - 1]} ${s.slice(0, 4)}`;
  };
  const replay = (node, cls) => { node.classList.remove(cls); void node.getBoundingClientRect(); node.classList.add(cls); };

  /* ------------------------------------------------------------------ */
  /* Theme                                                              */
  /* ------------------------------------------------------------------ */
  const root = document.documentElement;
  const themeBtn = $("#theme-toggle");
  // Dark is the default whatever the device prefers: the 3D scene is designed
  // as a neon night. Light switches the scene to daylight that follows the clock.
  const currentTheme = () => root.getAttribute("data-theme") || "dark";
  const syncThemeButton = () => {
    themeBtn.setAttribute("aria-label", currentTheme() === "light" ? "Switch to dark theme" : "Switch to light theme");
  };
  if (!root.getAttribute("data-theme")) root.setAttribute("data-theme", currentTheme());
  syncThemeButton();
  themeBtn.addEventListener("click", () => {
    const next = currentTheme() === "light" ? "dark" : "light";
    const apply = () => {
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("krr-theme", next); } catch (err) { /* storage blocked */ }
      syncThemeButton();
    };
    if (!document.startViewTransition || reduced()) { apply(); return; }
    const r = themeBtn.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    const end = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    document.startViewTransition(apply).ready.then(() => {
      root.animate({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${end}px at ${x}px ${y}px)`] },
        { duration: 650, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)", pseudoElement: "::view-transition-new(root)" });
    }).catch(() => {});
  });

  /* ------------------------------------------------------------------ */
  /* Page-wide motion: headline, progress, scrollspy, reveals, ripple   */
  /* ------------------------------------------------------------------ */
  $$("[data-split]").forEach((h) => {
    const text = h.textContent.trim();
    h.setAttribute("aria-label", text);
    h.innerHTML = text.split(/\s+/).map((w, i) =>
      `<span class="word" aria-hidden="true"><span style="animation-delay:${80 + i * 70}ms">${esc(w)}</span></span>`).join(" ");
  });

  const progress = $("#progress");
  const links = $$("#navlinks a");
  const indicator = $("#nav-indicator");
  const sections = links.map((a) => $(a.getAttribute("href")));
  let ticking = false;
  function onScroll() {
    ticking = false;
    const max = document.documentElement.scrollHeight - innerHeight;
    progress.style.transform = `scaleX(${max > 0 ? scrollY / max : 0})`;
    let active = -1;
    sections.forEach((s, i) => { if (s && s.getBoundingClientRect().top < innerHeight * 0.35) active = i; });
    links.forEach((a, i) => a.classList.toggle("is-active", i === active));
    const ul = indicator.parentElement;
    if (active >= 0 && ul.offsetParent) {
      const a = links[active];
      indicator.style.width = `${a.offsetWidth}px`;
      indicator.style.transform = `translateX(${a.getBoundingClientRect().left - ul.getBoundingClientRect().left}px)`;
      indicator.style.opacity = "1";
    } else indicator.style.opacity = "0";
  }
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  addEventListener("resize", onScroll);

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in-view");
      e.target.querySelectorAll(".section__title").forEach((t) => t.classList.add("in-view"));
      revealObserver.unobserve(e.target);
      if (e.target._onView) e.target._onView();
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
  const observe = (node, fn) => { if (!node) return; if (fn) node._onView = fn; revealObserver.observe(node); };

  const modeBtn = $("#mode-toggle");
  if (modeBtn) {
    const on = root.classList.contains("is-3d");
    modeBtn.setAttribute("aria-pressed", String(on));
    modeBtn.setAttribute("aria-label", on ? "Switch to the simple 2D view" : "Switch to the 3D view");
    modeBtn.addEventListener("click", () => {
      try { localStorage.setItem("krr-3d", root.classList.contains("is-3d") ? "off" : "on"); } catch (e) { /* storage blocked */ }
      location.reload();
    });
  }

  document.addEventListener("pointerdown", (e) => {
    const b = e.target.closest(".btn");
    if (!b || b.disabled || reduced()) return;
    const r = b.getBoundingClientRect(), size = Math.max(r.width, r.height) * 2;
    const s = document.createElement("span");
    s.className = "ripple";
    s.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
    b.appendChild(s);
    setTimeout(() => s.remove(), 650);
  });

  if (!D) {
    $("#main").insertAdjacentHTML("afterbegin",
      '<div class="wrap" style="padding-top:40px"><p class="error-box">The data file did not load, so the car park and the examples cannot be shown. Run <code>python tools/build_site.py</code> to create <code>website/data.js</code>, then reload.</p></div>');
    $$(".reveal").forEach((r) => r.classList.add("in-view"));
    return;
  }
  const S = D.stats;
  const zoneName = { student_zone: "Student zone", employee_zone: "Employee zone", visitor_zone: "Visitor zone" };
  const zoneTitle = (id) => { const z = D.lot.zones.find((x) => x.id === id); return z ? zoneName[z.type] || id : id; };
  const decisionTime = () => hhmm(D.run.hour * 100);

  /* Plain-language reading of a root cause from the explainer. */
  function plainReason(req) {
    const r = req.reasons[0] || "";
    let m;
    if ((m = r.match(/fails at fits\((\w+), (\w+)\)/)))
      return `${cap(req.driver)}'s vehicle is a ${m[1].replace("_", " ")}, and a ${m[1].replace("_", " ")} does not fit a ${m[2]} bay. No rule allows it.`;
    if ((m = r.match(/loses\((\w+), (\w+)\) is provable by (R\d+); competing request: requests\((\w+)/)))
      return m[3] === "R26"
        ? `${cap(m[4])} also wants ${m[2]}, has the same priority as ${m[1]} and asked earlier (${m[3]}), so ${m[2]} goes to ${m[4]}.`
        : `${cap(m[4])} also wants ${m[2]} and outranks ${m[1]} on priority (${m[3]}), so ${m[2]} goes to ${m[4]}.`;
    if ((m = r.match(/permit_valid\((\w+)\) fails at (\d{8}) >= (\d{8})/)))
      return `The ${m[1].startsWith("vp_") ? "visitor pass" : "permit"} expired on ${ymd(m[2])}. Today is ${ymd(m[3])}.`;
    if ((m = r.match(/permit_valid\((\w+)\) fails at (\d{8}) =< (\d{8})/)))
      return `The ${m[1].startsWith("vp_") ? "visitor pass" : "permit"} only starts on ${ymd(m[2])}. Today is ${ymd(m[3])}.`;
    if ((m = r.match(/zone_open\((\w+)\) fails at (\d+) (>=|<) (\d+)/))) {
      const z = D.lot.zones.find((x) => x.id === m[1]) || {};
      return `The ${zoneTitle(m[1]).toLowerCase()} is open from ${hhmm(z.opens * 100)} to ${hhmm(z.closes * 100)}, so it is closed at ${hhmm(m[2] * 100)}.`;
    }
    if ((m = (req.reasons[1] || "").match(/holds_reservation\((\w+), (\w+)\) fails at current_date\((\d{8})\)/)))
      return `${cap(m[1])}'s reservation of ${m[2]} was for ${ymd(m[3])}, so it does not count today and the bay stays marked reserved.`;
    if ((m = r.match(/has_permit\((\w+), P\)/)))
      return `No permit or visitor pass is recorded for ${m[1]}.`;
    return "The request does not satisfy the allocation rule.";
  }
  const vehicleOf = (d) => (D.drivers[d] || {}).vehicle || "car";
  const roleText = (d) => {
    const p = D.drivers[d] || {};
    const v = (p.vehicle || "car").replace("_", " ");
    return `${p.role || "driver"}, ${v}${p.badge ? ", badge holder" : ""}`;
  };

  /* ------------------------------------------------------------------ */
  /* Car park                                                           */
  /* ------------------------------------------------------------------ */
  const SVGNS = "http://www.w3.org/2000/svg";
  const svg = $("#lot");
  const el = (name, attrs = {}, parent = svg, text) => {
    const n = document.createElementNS(SVGNS, name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    parent.appendChild(n);
    return n;
  };
  const CAR_W = 72, CAR_H = 26, ROAD_Y = 230, GATE_X = 172;
  const BAY_W = 110, TOP = { y0: 50, y1: 180 }, BOT = { y0: 280, y1: 410 }; // viewBox 1000 x 460
  const bays = {};
  const typeText = { standard: "standard", accessible: "accessible", ev_charging: "EV charging", motorbike: "motorbike" };
  let gateBar, gatePing, think, thinkText, thinkBar;

  function place(g, x, y) { g.style.transform = `translate(${x}px, ${y}px)`; g._x = x; g._y = y; return g; }

  function makeCar(name, cls = "", vehicle = "car") {
    const g = el("g", { class: `car ${cls}` });
    const inner = el("g", { class: "car__inner" }, g);
    if (vehicle === "motorbike") {
      // a slim body on two wheels, so a bike reads as a bike next to the cars
      [8, 64].forEach((cx) => el("circle", { class: "wheel", cx, cy: CAR_H / 2, r: 7 }, inner));
      el("rect", { class: "body", x: 13, y: CAR_H / 2 - 8, width: 46, height: 16, rx: 8 }, inner);
      el("rect", { class: "lamp", x: 70, y: CAR_H / 2 - 2, width: 3, height: 4, rx: 1 }, inner);
      el("text", { class: "bike-name", x: 36, y: CAR_H / 2 + 4, "text-anchor": "middle" }, inner, name);
      g._inner = inner;
      return g;
    }
    [[10, -2], [50, -2], [10, 24], [50, 24]].forEach(([x, y]) => el("rect", { class: "wheel", x, y, width: 12, height: 4, rx: 1.5 }, inner));
    el("rect", { class: "body", width: CAR_W, height: CAR_H, rx: 7 }, inner);
    el("rect", { class: "glass", x: 57, y: 4, width: 8, height: 18, rx: 3 }, inner);
    el("rect", { class: "lamp", x: 69, y: 3, width: 3, height: 5, rx: 1 }, inner);
    el("rect", { class: "lamp", x: 69, y: 18, width: 3, height: 5, rx: 1 }, inner);
    el("text", { x: 29, y: CAR_H / 2 + 4.5, "text-anchor": "middle" }, inner, name);
    g._inner = inner;
    return g;
  }

  const zoneLabels = {};
  // Grey out the zones that are shut at the hour the reasoner runs.
  function markClosedZones() {
    D.lot.zones.forEach((z) => {
      const t = zoneLabels[z.id];
      if (!t) return;
      const shut = D.run.hour < z.opens || D.run.hour >= z.closes;
      t.classList.toggle("is-closed", shut);
      t.textContent = `${zoneName[z.type] || z.id}, ${hhmm(z.opens * 100)} to ${hhmm(z.closes * 100)}${shut ? " (closed)" : ""}`;
    });
  }
  function drawLot() {
    el("rect", { class: "lane", x: 90, y: ROAD_Y - 42, width: 910, height: 84 });
    el("line", { class: "lane-dash", x1: GATE_X + 10, y1: ROAD_Y, x2: 990, y2: ROAD_Y });
    el("text", { class: "area-label", x: 6, y: 30 }, svg, "Queue");
    el("text", { class: "area-label", x: 86, y: 30 }, svg, "Turned away");
    el("circle", { cx: GATE_X, cy: ROAD_Y - 44, r: 6, fill: "#f2c230" });
    gatePing = el("circle", { class: "gate-ping", cx: GATE_X, cy: ROAD_Y, r: 40 });
    gateBar = el("line", { class: "gate-bar", x1: GATE_X, y1: ROAD_Y - 44, x2: GATE_X, y2: ROAD_Y + 42 });
    el("text", { class: "area-label", x: GATE_X - 14, y: ROAD_Y + 66 }, svg, "Gate");

    const layout = { zone_a: { x: 220, row: TOP }, zone_e: { x: 220, row: BOT }, zone_v: { x: 660, row: BOT } };
    let bayIndex = 0;
    D.lot.zones.forEach((z) => {
      const L = layout[z.id] || { x: 220, row: TOP };
      const top = L.row === TOP;
      const label = `${zoneName[z.type] || z.id}, ${hhmm(z.opens * 100)} to ${hhmm(z.closes * 100)}`;
      zoneLabels[z.id] = el("text", { class: "zone-label", x: L.x, y: top ? L.row.y0 - 16 : L.row.y1 + 30 }, svg, label);
      z.bays.forEach((b, i) => {
        const x = L.x + i * BAY_W;
        const g = el("g", { class: "bay", "data-bay": b.id });
        el("rect", { class: "bay-fill", x: x + 2, y: L.row.y0, width: BAY_W - 4, height: L.row.y1 - L.row.y0 }, g);
        const closedY = top ? L.row.y0 : L.row.y1;
        const openY = top ? L.row.y1 : L.row.y0;
        const line = el("path", { class: "bay-line", d: `M${x} ${openY} V${closedY} H${x + BAY_W} V${openY}` }, g);
        if (!reduced()) { g.classList.add("paint"); line.style.animationDelay = `${700 + bayIndex * 110}ms`; }
        bayIndex++;
        const ty = top ? L.row.y0 + 24 : L.row.y1 - 32;
        el("text", { class: "bay-label", x: x + 12, y: ty }, g, b.id);
        el("text", { class: "bay-type", x: x + 12, y: ty + 19 }, g, typeText[b.type] || b.type);
        if (b.reservedFor) {
          const ry = top ? L.row.y1 - 30 : L.row.y0 + 18;
          el("text", { class: "reserve-tag", x: x + 12, y: ry }, g, "reserved for");
          el("text", { class: "reserve-tag", x: x + 12, y: ry + 16 }, g, b.reservedFor);
        }
        const cx = x + BAY_W / 2, cy = (L.row.y0 + L.row.y1) / 2 + (top ? 14 : -14);
        bays[b.id] = { g, cx, cy };
        if (b.status === "occupied") place(makeCar("parked", "is-static"), cx - CAR_W / 2, cy - CAR_H / 2);
      });
    });
    const lx = 806, ly = 300;
    el("text", { class: "area-label", x: lx, y: ly - 14 }, svg, "Key");
    [["var(--car-wait)", "waiting"], ["var(--car-ok)", "allocated"], ["var(--car-no)", "refused"], ["var(--car-static)", "already parked"]]
      .forEach(([c, t], i) => {
        el("rect", { class: "legend-swatch", x: lx, y: ly + i * 26, width: 26, height: 14, rx: 3, style: `fill:${c}` });
        el("text", { class: "bay-type", x: lx + 36, y: ly + i * 26 + 12 }, svg, t);
      });
    think = el("g", { class: "think", "aria-hidden": "true" });
    el("rect", { class: "panel", x: 420, y: 196, width: 300, height: 68, rx: 10 }, think);
    thinkText = el("text", { x: 438, y: 224 }, think, "");
    el("rect", { class: "bar-bg", x: 438, y: 240, width: 264, height: 8, rx: 4 }, think);
    thinkBar = el("rect", { class: "bar", x: 438, y: 240, width: 0, height: 8, rx: 4 }, think);
  }

  const queueSlot = (i) => ({ x: 6, y: 44 + i * 34 });
  const awaySlot = (i) => ({ x: 86, y: 40 + i * 30 });

  async function move(g, points, speed = 0.42) {
    const pts = [[g._x, g._y], ...points];
    const lens = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
    const total = lens.reduce((a, b) => a + b, 0) || 1;
    let acc = 0;
    const frames = pts.map((p, i) => {
      if (i > 0) acc += lens[i - 1];
      return { transform: `translate(${p[0]}px, ${p[1]}px)`, offset: acc / total };
    });
    g.classList.add("is-moving");
    svg.classList.add("is-driving");
    const a = g.animate(frames, { duration: Math.max(380, total / speed), easing: "cubic-bezier(0.45, 0, 0.25, 1)", fill: "forwards" });
    await a.finished.catch(() => {});
    const [x, y] = points[points.length - 1];
    place(g, x, y);
    a.cancel();
    g.classList.remove("is-moving");
    svg.classList.remove("is-driving");
  }

  let runId = 0;
  let cars = [];
  const logEl = $("#log"), statusEl = $("#lot-status");
  const clockTime = $("#clock-time"), clockNote = $("#clock-note");
  const playBtn = $("#play");
  const setClock = (t) => { if (clockTime.textContent !== t) { clockTime.textContent = t; if (!reduced()) replay(clockTime, "tick"); } };

  function buildLog() {
    logEl.innerHTML = D.requests.map((q, i) => `
      <li class="log__item" id="log-${i}">
        <span class="log__time">${hhmm(q.time)}</span>
        <span class="log__who">${esc(q.driver)}${vehicleOf(q.driver) !== "car" ? ` <span>(${esc(vehicleOf(q.driver).replace("_", " "))})</span>` : ""} <span>asks for <span class="id">${esc(q.space)}</span></span></span>
        <span class="log__verdict" id="verdict-${i}"><span class="verdict verdict--wait">Waiting</span></span>
      </li>`).join("");
  }
  function setVerdict(i, q) {
    $(`#log-${i}`).classList.add("is-shown", "is-decided");
    $(`#verdict-${i}`).innerHTML = q.allocated
      ? `<span class="verdict verdict--ok">Allocated</span>${fmt(`Rule R28 holds for ${q.space}.`)}`
      : `<span class="verdict verdict--no">Refused</span>${fmt(plainReason(q))}`;
  }
  const parkedCount = () => D.requests.filter((q) => q.allocated).length;
  const summary = () => {
    const ok = D.requests.filter((q) => q.allocated).map((q) => `${q.driver} in ${q.space}`);
    return `Result: ${ok.join(", ")} parked. ${D.requests.length - ok.length} requests refused; see the decision log.`;
  };

  function resetLot() {
    cars.forEach((c) => c.g.remove());
    cars = [];
    Object.values(bays).forEach((b) => b.g.classList.remove("is-taken", "glow"));
    gateBar.classList.remove("is-open");
    think.classList.remove("is-on");
    svg.classList.remove("is-driving");
    buildLog();
  }
  function finished() {
    setClock(decisionTime());
    clockNote.textContent = `${D.run.fired.length} cycles, ${D.run.facts + D.run.derived} facts, ${parkedCount()} of ${D.requests.length} parked`;
    statusEl.textContent = summary();
    playBtn.textContent = "Replay the morning";
    playBtn.removeAttribute("aria-busy");
  }
  function finalState() {
    runId++;
    resetLot();
    let away = 0;
    D.requests.forEach((q, i) => {
      const car = makeCar(q.driver, q.allocated ? "is-allocated" : "is-denied", vehicleOf(q.driver));
      if (q.allocated) {
        const b = bays[q.space];
        place(car, b.cx - CAR_W / 2, b.cy - CAR_H / 2);
        b.g.classList.add("is-taken");
      } else {
        const s = awaySlot(away++);
        place(car, s.x, s.y);
      }
      cars.push({ g: car, q });
      setVerdict(i, q);
    });
    finished();
  }

  async function play() {
    if (reduced()) { finalState(); return; }
    const id = ++runId;
    const alive = () => id === runId;
    resetLot();
    playBtn.textContent = "Playing";
    playBtn.setAttribute("aria-busy", "true");
    statusEl.textContent = "Replaying the morning rush.";

    // 1. requests arrive in time order
    clockNote.textContent = "Requests arriving";
    for (const [i, q] of D.requests.entries()) {
      if (!alive()) return;
      setClock(hhmm(q.time));
      const s = queueSlot(i);
      const car = place(makeCar(q.driver, "", vehicleOf(q.driver)), -90, s.y);
      cars.push({ g: car, q });
      $(`#log-${i}`).classList.add("is-shown");
      await move(car, [[s.x, s.y]], 0.32);
    }
    if (!alive()) return;
    await sleep(300);

    // 2. the reasoner runs once over all requests
    setClock(decisionTime());
    think.classList.add("is-on");
    let known = D.run.facts;
    const n = D.run.fired.length;
    for (const [k, fired] of D.run.fired.entries()) {
      if (!alive()) return;
      known += fired;
      thinkText.textContent = `Reasoning: cycle ${k + 1} of ${n}, ${known} facts`;
      thinkBar.setAttribute("width", String(264 * (k + 1) / n));
      clockNote.textContent = `Forward chaining, cycle ${k + 1} of ${n}`;
      await sleep(190);
    }
    if (!alive()) return;
    await sleep(500);
    think.classList.remove("is-on");

    // 3. each car is checked at the gate, then parked or turned away
    let away = 0;
    for (const [i, { g, q }] of cars.entries()) {
      if (!alive()) return;
      clockNote.textContent = `Checking ${q.driver}`;
      await move(g, [[GATE_X - CAR_W - 8, ROAD_Y - CAR_H / 2]], 0.4);
      if (!alive()) return;
      replay(gatePing, "go");
      await sleep(320);
      if (q.allocated) {
        g.classList.add("is-allocated");
        clockNote.textContent = `${q.driver}: allocated ${q.space}`;
        gateBar.classList.add("is-open");
        await sleep(280);
        const b = bays[q.space];
        await move(g, [[GATE_X + 20, ROAD_Y - CAR_H / 2], [b.cx - CAR_W / 2, ROAD_Y - CAR_H / 2], [b.cx - CAR_W / 2, b.cy - CAR_H / 2]], 0.5);
        replay(g._inner, "settle");
        b.g.classList.add("is-taken");
        replay(b.g, "glow");
        gateBar.classList.remove("is-open");
      } else {
        g.classList.add("is-denied");
        clockNote.textContent = `${q.driver}: refused`;
        replay(g._inner, "shake");
        await sleep(520);
        const s = awaySlot(away++);
        await move(g, [[s.x, s.y]], 0.38);
      }
      if (!alive()) return;
      setVerdict(i, q);
      await sleep(160);
    }
    if (!alive()) return;
    finished();
  }
  let userActed = false;
  let want3D = root.classList.contains("is-3d");
  playBtn.addEventListener("click", () => {
    userActed = true;
    if (want3D) { if (window.KRR3D) window.KRR3D.play(); } else play();
  });
  $("#skip").addEventListener("click", () => {
    userActed = true;
    if (want3D) { if (window.KRR3D) window.KRR3D.final(); } else finalState();
  });

  function start2D() {
    if (reduced()) { finalState(); return; }
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); setTimeout(() => { if (!userActed) play(); }, 1900); }
    }, { threshold: 0.3 });
    io.observe(svg);
  }

  // The 3D scene (scene3d.js) drives the decision log through this object.
  window.KRRUI = {
    resetLog: () => { buildLog(); clockNote.textContent = "Requests arriving"; setClock(hhmm(D.requests[0].time)); },
    decisionTime: () => decisionTime(),
    showLog: (i) => $(`#log-${i}`).classList.add("is-shown"),
    setVerdict: (i) => setVerdict(i, D.requests[i]),
    setClock: (t) => setClock(t),
    setNote: (t) => { clockNote.textContent = t; },
    playing: () => { playBtn.textContent = "Playing"; playBtn.setAttribute("aria-busy", "true"); statusEl.textContent = "Replaying the morning rush."; },
    finished: () => finished(),
    userActed: () => userActed,
    plainReason: (i) => plainReason(D.requests[i]),
    currentCycle: () => cur,
    currentAnswer: () => Number(($("#pick input:checked") || { value: 0 }).value),
    fallback2D: () => {
      if (!want3D) return;
      want3D = false;
      root.classList.remove("is-3d");
      document.getElementById("loader")?.remove();
      if (modeBtn) modeBtn.setAttribute("aria-pressed", "false");
      start2D();
      onScroll();
    },
  };

  drawLot();
  markClosedZones();
  buildLog();
  if (!want3D) start2D();
  else setTimeout(() => { if (!window.KRR3D) window.KRRUI.fallback2D(); }, 12000);

  /* ------------------------------------------------------------------ */
  /* Key numbers                                                        */
  /* ------------------------------------------------------------------ */
  const numbers = [
    [S.facts, "", "facts at the start, from the frames, policy tables and today's requests"],
    [S.derived, "", "new facts derived by forward chaining"],
    [S.rules, "", `Horn rules, plus ${S.constraints} denial constraints`],
    [S.cycles, "", "inference cycles to reach the fixpoint"],
    [S.testsPassed, ` of ${S.tests}`, "test cases where both engines give the expected answer"],
  ];
  $("#numbers").innerHTML = numbers.map(([n, suffix, label]) =>
    `<li><strong data-count="${n}" data-suffix="${esc(suffix)}">${n}${esc(suffix)}</strong><span>${esc(label)}</span></li>`).join("");
  observe($(".numbers"), () => {
    if (reduced()) return;
    $$("[data-count]").forEach((node) => {
      const target = Number(node.dataset.count), suffix = node.dataset.suffix, t0 = performance.now();
      const step = (t) => {
        const p = Math.min(1, (t - t0) / 1400), e = 1 - Math.pow(1 - p, 3);
        node.textContent = Math.round(target * e) + suffix;
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  });

  /* ------------------------------------------------------------------ */
  /* Cycle stepper                                                      */
  /* ------------------------------------------------------------------ */
  const cyclesEl = $("#cycles"), detailEl = $("#cycle-detail");
  const total = S.facts + S.derived;
  const cycPlay = $("#cyc-play");
  let cur = 0, cycTimer = null;
  cyclesEl.innerHTML = D.cycles.map((c, i) =>
    `<li><button type="button" data-i="${i}" aria-label="Cycle ${c.n}, ${c.fired} new facts"><span>Cycle</span><strong>${c.n}</strong><span>+${c.fired}</span></button></li>`).join("");
  cyclesEl.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) { stopCycles(); showCycle(Number(b.dataset.i)); }
  });
  $("#cyc-prev").addEventListener("click", () => { stopCycles(); showCycle(cur - 1); });
  $("#cyc-next").addEventListener("click", () => { stopCycles(); showCycle(cur + 1); });
  function stopCycles() {
    if (cycTimer) clearInterval(cycTimer);
    cycTimer = null;
    cycPlay.textContent = "Play all cycles";
  }
  cycPlay.addEventListener("click", () => {
    if (cycTimer) { stopCycles(); return; }
    if (cur >= D.cycles.length - 1) showCycle(0);
    cycPlay.textContent = "Stop";
    cycTimer = setInterval(() => {
      if (cur >= D.cycles.length - 1) { stopCycles(); return; }
      showCycle(cur + 1);
    }, reduced() ? 600 : 1300);
  });

  function showCycle(i) {
    cur = Math.max(0, Math.min(D.cycles.length - 1, i));
    const c = D.cycles[cur];
    const known = S.facts + D.cycles.slice(0, cur + 1).reduce((s, x) => s + x.fired, 0);
    cyclesEl.querySelectorAll("button").forEach((b, j) => {
      if (j === cur) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      b.classList.toggle("is-done", j < cur);
    });
    $("#cyc-meter").style.width = `${(known / total) * 100}%`;
    $("#cyc-count").textContent = `${known} of ${total} facts known`;
    window.dispatchEvent(new CustomEvent("krr:cycle", { detail: { i: cur } }));
    $("#cyc-prev").disabled = cur === 0;
    $("#cyc-next").disabled = cur === D.cycles.length - 1;
    const facts = c.derived.length
      ? c.derived.map((f, k) => `<li style="animation-delay:${Math.min(k * 22, 700)}ms"><span>${esc(f.rule)}</span>${esc(f.fact)}</li>`).join("")
      : `<li class="is-empty">No new facts. Stratum ${c.stratum} has reached its fixpoint${c.stratum === 0 ? ", so the rule with negation (R28) can now run safely." : "."}</li>`;
    detailEl.innerHTML = `
      <div>
        <h3>Cycle ${c.n}, stratum ${c.stratum}</h3>
        <p class="muted">${c.conflict} rule instances matched the facts known at the start of the cycle. ${c.fired} of them produced a fact that was not known yet.</p>
        ${c.rules.length ? `<div class="chips" aria-label="Rules fired">${c.rules.map((r, k) => `<span class="chip" style="animation-delay:${k * 45}ms">${esc(r)}</span>`).join("")}</div>` : ""}
      </div>
      <div>
        <h3>${c.fired ? `New facts (${c.fired})` : "New facts"}</h3>
        <ul class="facts">${facts}</ul>
      </div>`;
  }
  showCycle(0);

  /* ------------------------------------------------------------------ */
  /* Ask why                                                            */
  /* ------------------------------------------------------------------ */
  const pick = $("#pick"), answer = $("#answer");
  const renderPick = (sel) => {
    pick.innerHTML = D.requests.map((q, i) => `
    <div class="pick__opt">
      <input type="radio" name="req" id="req-${i}" value="${i}" ${i === sel ? "checked" : ""}>
      <label for="req-${i}"><span>${esc(q.driver)}, <span class="id">${esc(q.space)}</span></span><span class="verdict ${q.allocated ? "verdict--ok" : "verdict--no"}">${q.allocated ? "Allocated" : "Refused"}</span></label>
    </div>`).join("");
  };
  renderPick(0);
  pick.addEventListener("change", (e) => showAnswer(Number(e.target.value), true));

  const howClass = (h) => (/^R\d+/.test(h) ? "how how--rule" : "how");
  function proofItem(n, depth) {
    const label = `<span class="node">${esc(n.t)}<span class="${howClass(n.how)}">${esc(n.how)}</span></span>`;
    if (!n.c.length) return `<li class="leaf">${label}</li>`;
    return `<li><details ${depth < 2 ? "open" : ""}><summary>${label}</summary><ul>${n.c.map((c) => proofItem(c, depth + 1)).join("")}</ul></details></li>`;
  }
  function reasonItem(r) {
    const text = r.rule ? `${r.rule} blocked at ${r.goal}` : r.goal;
    const det = r.detail ? `<span class="how how--fail">${esc(r.detail)}</span>` : "";
    const label = `<span class="node">${esc(text)}${det}</span>`;
    if (!r.c.length) return `<li class="leaf">${label}</li>`;
    return `<li><details open><summary>${label}</summary><ul>${r.c.map(reasonItem).join("")}</ul></details></li>`;
  }
  const countLeaves = (n) => (n.c.length ? n.c.reduce((s, c) => s + countLeaves(c), 0) : 1);
  const grow = (li, delay) => { li.style.setProperty("--d", `${delay}ms`); replay(li, "grow"); };
  function cascade(scope) {
    if (reduced()) return;
    let k = 0;
    scope.querySelectorAll(".tree li").forEach((li) => {
      if (li.closest("details:not([open]) > ul")) return;
      grow(li, Math.min(k++ * 45, 1100));
    });
  }

  function showAnswer(i, animate) {
    const q = D.requests[i];
    const who = `${cap(q.driver)} (${roleText(q.driver)}) asked for ${q.space} at ${hhmm(q.time)}.`;
    const plain = q.allocated
      ? `${who} The proof below uses ${countLeaves(q.proof)} stored facts and comparisons and took ${q.steps} backward-chaining steps.`
      : `${who} ${plainReason(q)}`;
    const tree = q.allocated ? `<ul class="tree">${proofItem(q.proof, 0)}</ul>` : `<ul class="tree">${reasonItem(q.whyNot)}</ul>`;
    answer.innerHTML = `
      <div class="answer__head">
        <span class="answer__goal">${esc(q.goal)}</span>
        <span class="verdict ${q.allocated ? "verdict--ok" : "verdict--no"}">${q.allocated ? "Proved" : "Cannot be proved"}</span>
      </div>
      <p class="answer__plain">${fmt(plain)}</p>
      <div class="answer__tools">
        <button class="btn btn--ghost btn--small" type="button" data-act="open">Expand all</button>
        <button class="btn btn--ghost btn--small" type="button" data-act="close">Collapse all</button>
      </div>
      <div class="tree-scroll">${tree}</div>`;
    if (animate && !reduced()) { replay(answer, "swap"); cascade(answer); }
    window.dispatchEvent(new CustomEvent("krr:answer", { detail: { i } }));
  }
  answer.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    answer.querySelectorAll("details").forEach((d, k) => { d.open = b.dataset.act === "open" || k === 0; });
    if (b.dataset.act === "open") cascade(answer);
  });
  answer.addEventListener("toggle", (e) => {
    const d = e.target;
    if (!d.open || reduced()) return;
    const ul = d.querySelector(":scope > ul");
    if (ul) [...ul.children].forEach((li, k) => grow(li, k * 50));
  }, true);
  showAnswer(0, false);
  observe($(".why"), () => cascade(answer));

  /* ------------------------------------------------------------------ */
  /* Scenario clock and added drivers                                   */
  /* ------------------------------------------------------------------ */
  // engine-worker.js runs the project's Python engine (krr/site_export.py) in the
  // browser through Pyodide, so every answer here is the engine's own output.
  const REF = { date: D.run.date, hour: D.run.hour };
  const BASE_DRIVERS = { ...D.drivers };
  const dateIn = $("#scn-date"), hourIn = $("#scn-hour"), hourOut = $("#scn-hour-out");
  const scnBox = $(".scenario"), scnNote = $("#scn-note"), scnReset = $("#scn-reset"), scnNow = $("#scn-now");
  const addedList = $("#added");
  const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const dayName = (n) => { const s = String(n); return DAYS[new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6)).getDay()]; };
  const toIso = (n) => { const s = String(n); return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}`; };
  const fromIso = (v) => (/^\d{4}-\d{2}-\d{2}$/.test(v) ? Number(v.replace(/-/g, "")) : null);
  const extras = [];
  let applyRun = null;
  if (dateIn && hourIn) {
    const cache = new Map([[`${REF.date}-${REF.hour}-[]`, { run: D.run, requests: D.requests }]]);
    let worker = null, asked = 0, timer = 0, engineLoaded = false;
    const pending = new Map();
    const engine = (date, hour, extra) => new Promise((resolve, reject) => {
      if (!worker) {
        worker = new Worker("engine-worker.js");
        worker.onmessage = (e) => { const p = pending.get(e.data.id); if (!p) return; pending.delete(e.data.id); e.data.ok ? p.resolve(e.data.data) : p.reject(new Error(e.data.error)); };
        worker.onerror = (e) => { pending.forEach((p) => p.reject(new Error(e.message || "worker failed"))); pending.clear(); worker = null; };
      }
      const id = ++asked;
      pending.set(id, { resolve, reject });
      worker.postMessage({ id, date, hour, extra });
    });
    const isRef = () => D.run.date === REF.date && D.run.hour === REF.hour && !extras.length;
    const describe = () => {
      scnReset.hidden = isRef();
      const who = extras.length ? ` with ${extras.length} added driver${extras.length > 1 ? "s" : ""}` : "";
      scnNote.innerHTML = isRef()
        ? "This is the run in the report and the tests. Pick any date or hour, or add a driver, and the Python engine re-decides every request in your browser."
        : `<b>${parkedCount()} of ${D.requests.length} parked</b> on ${dayName(D.run.date)} ${ymd(D.run.date)} at ${decisionTime()}${who}, decided by the Python engine running in this browser. Ask why below shows each proof.`;
      addedList.hidden = !extras.length;
      addedList.innerHTML = extras.map((x, i) => {
        const q = D.requests.find((r) => r.driver === x.name);
        const v = q ? (q.allocated ? "parked" : "refused") : "";
        return `<li><span>${esc(x.name)} wants ${esc(x.space)}${v ? `: ${v}` : ""}</span><button type="button" data-remove="${i}" aria-label="Remove ${esc(x.name)}">&#x2715;</button></li>`;
      }).join("");
    };
    const show = (v, focusDriver) => {
      D.requests = v.requests;
      D.run = v.run;
      D.drivers = { ...BASE_DRIVERS };
      extras.forEach((x) => { D.drivers[x.name] = { role: x.role, badge: x.badge, vehicle: x.vehicle }; });
      markClosedZones();
      userActed = true;
      if (want3D && window.KRR3D) window.KRR3D.final(); else finalState();
      let sel = Math.min(Number(($("#pick input:checked") || { value: 0 }).value), D.requests.length - 1);
      if (focusDriver) sel = Math.max(0, D.requests.findIndex((q) => q.driver === focusDriver));
      renderPick(sel);
      showAnswer(sel, Boolean(focusDriver));
      describe();
    };
    // Runs the engine for the current clock and drivers. With focusDriver set
    // (a driver was just added) an engine error is thrown back to the form.
    const run = async (focusDriver) => {
      const date = fromIso(dateIn.value), hour = Number(hourIn.value);
      if (!date) { scnNote.textContent = "Enter a full date to run the engine."; return false; }
      const key = `${date}-${hour}-${JSON.stringify(extras)}`;
      if (cache.has(key)) { show(cache.get(key), focusDriver); return true; }
      scnBox.classList.add("is-busy");
      scnNote.textContent = engineLoaded
        ? `Reasoning about ${dayName(date)} ${ymd(date)}, ${hhmm(hour * 100)}...`
        : "Loading the Python reasoning engine into this browser. This takes a few seconds the first time.";
      try {
        const v = await engine(date, hour, extras);
        engineLoaded = true;
        cache.set(key, v);
        if (key === `${fromIso(dateIn.value)}-${hourIn.value}-${JSON.stringify(extras)}`) show(v, focusDriver);
        return true;
      } catch (e) {
        if (focusDriver) throw e;
        scnNote.textContent = `The engine could not run here (${e.message}). The car park still shows the last answer.`;
        return false;
      } finally {
        scnBox.classList.remove("is-busy");
      }
    };
    applyRun = run;
    const schedule = () => { hourOut.value = hhmm(hourIn.value * 100); clearTimeout(timer); timer = setTimeout(() => run(), 250); };
    const setClockTo = (date, hour) => { dateIn.value = toIso(date); hourIn.value = hour; schedule(); };
    dateIn.value = toIso(REF.date);
    hourIn.value = REF.hour;
    hourIn.addEventListener("input", schedule);
    dateIn.addEventListener("change", schedule);
    scnReset.addEventListener("click", () => { extras.length = 0; setClockTo(REF.date, REF.hour); });
    scnNow.addEventListener("click", () => {
      const n = new Date();
      setClockTo(n.getFullYear() * 10000 + (n.getMonth() + 1) * 100 + n.getDate(), n.getHours());
    });
    addedList.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-remove]");
      if (!b) return;
      extras.splice(Number(b.dataset.remove), 1);
      run();
    });
    describe();
  }

  /* Add a driver: a form whose answers become facts in the knowledge base */
  const dlg = $("#driver-dialog"), form = $("#driver-form"), drvErr = $("#drv-error");
  const addBtn = $("#add-driver");
  if (dlg && form && addBtn && applyRun) {
    const typeName = { standard: "standard", accessible: "accessible", ev_charging: "EV charging", motorbike: "motorbike" };
    $("#drv-space").innerHTML = D.lot.zones.map((z) => `<optgroup label="${esc(zoneName[z.type] || z.id)}">${
      z.bays.map((b) => `<option value="${b.id}">${b.id}, ${typeName[b.type] || b.type}${b.reservedFor ? `, reserved for ${esc(b.reservedFor)}` : ""}${b.status === "occupied" ? ", occupied" : ""}</option>`).join("")}</optgroup>`).join("");
    addBtn.addEventListener("click", () => {
      drvErr.textContent = "";
      if (extras.length >= 4) { scnNote.textContent = "Up to four added drivers. Remove one to add another."; return; }
      form.reset();
      $("#drv-space").value = "s_a1";
      const t = Math.max(0, D.run.hour * 60 - 15);
      $("#drv-time").value = `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
      dlg.showModal();
      $("#drv-name").focus();
    });
    form.addEventListener("submit", async (e) => {
      if (e.submitter && e.submitter.value === "cancel") return;
      e.preventDefault();
      const f = new FormData(form);
      const name = String(f.get("name") || "").trim().toLowerCase();
      const time = String(f.get("time") || "");
      if (!/^[a-z][a-z0-9_]{1,15}$/.test(name)) { drvErr.textContent = "Name: 2 to 16 lower-case letters, digits or _, starting with a letter."; return; }
      if (BASE_DRIVERS[name] || extras.some((x) => x.name === name)) { drvErr.textContent = `${name} is already in the car park. Pick another name.`; return; }
      if (!/^\d{2}:\d{2}$/.test(time)) { drvErr.textContent = "Enter an arrival time."; return; }
      const x = { name, role: f.get("role"), vehicle: f.get("vehicle"), badge: f.get("badge") === "on",
        permit: f.get("permit"), space: f.get("space"), time: Number(time.replace(":", "")) };
      const submit = $("#drv-submit");
      submit.disabled = true;
      submit.textContent = "Reasoning...";
      extras.push(x);
      try {
        await applyRun(name);
        dlg.close();
      } catch (err) {
        extras.pop();
        drvErr.textContent = err.message;
      } finally {
        submit.disabled = false;
        submit.textContent = "Add and decide";
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Representations                                                    */
  /* ------------------------------------------------------------------ */
  const rule = (id) => (D.rules.find((r) => r.id === id) || {}).text || "";
  const models = [
    { title: "How the pieces fit",
      text: ["Knowledge enters through the frames. The frame system settles every default and writes one fact per slot value, so the rule base never types a fact twice.",
        "Two inference engines read the same facts and rules. The command line, the Streamlit app and this page all show their output."],
      figs: [["architecture.png", "System architecture and knowledge model"]] },
    { title: "Frames and a script",
      text: ["Fifteen class frames hold slots with facets: type, default, range, cardinality and if-needed procedures. AccessibleSpace inherits from ParkingSpace and overrides spaceType, so a bay is accessible without anyone storing it.",
        "The ParkingSession script runs the seven stages of a visit, from arriving at the gate to parking, and stops at the first stage that fails."],
      figs: [["frame_hierarchy.png", "Frame hierarchy with slots and links"], ["parking_script.png", "ParkingSession script scenes"]] },
    { title: "Semantic network",
      text: ["The network is generated from the frames, so its labels always match the rules. Paths answer questions: p_ali has-class student_permit, which grants student_zone, which is the type of zone_a. That path is rule R13 drawn as a graph."],
      figs: [["semantic_network_example.png", "Semantic network with individuals"], ["semantic_network.png", "Concept-level semantic network"]] },
    { title: "First-order logic and description logic",
      text: ["Every rule is written in FOL with explicit quantifiers, plus twelve statements that go beyond Horn form. A model checker tests them on every run.",
        "A DL TBox of 45 axioms gives the class hierarchy, restrictions and disjointness. The reasoner classifies it and catches contradictions, such as a student recorded as faculty."],
      code: "∀x ∀y ∀s ((allocate(x, s) ∧ allocate(y, s)) → x = y)\n\nAuthorizedStudent ≡ Student ⊓ ∃hasPermit.(ValidPermit ⊓ StudentPermit)\nAccessibleSpace ⊑ ∀allocatedTo.BadgeHolder\nStudent ⊓ Employee ⊑ ⊥" },
    { title: "Horn clauses and two engines",
      text: [`The policy that runs is ${S.rules} Horn rules and ${S.constraints} denial constraints. Forward chaining computes everything that follows; backward chaining proves one goal and explains a failure.`,
        "Both engines are plain Python, and they derive exactly the same facts in every scenario."],
      figs: [["reasoning_engine.png", "Inference engine architecture"]], rule: `% R13\n${rule("R13")}` },
  ];
  const figBtn = ([f, c]) => `<div class="figure-wrap"><button class="figure-btn" type="button" data-fig="${f}" data-cap="${esc(c)}" aria-label="Enlarge figure: ${esc(c)}"><img src="assets/${f}" alt="${esc(c)}" decoding="async"></button></div><p class="figure-cap">${esc(c)}</p>`;
  $("#model-list").innerHTML = models.map((m, i) => {
    const visual = m.figs
      ? m.figs.map((f, k) => `<div${k ? ' style="margin-top:20px"' : ""}>${figBtn(f)}</div>`).join("")
      : `<pre class="code rule" aria-label="Example formulas">${esc(m.code)}</pre>`;
    return `<article class="model reveal" aria-labelledby="model-${i}">
      <div class="model__text"><h3 id="model-${i}">${esc(m.title)}</h3>${m.text.map((t) => `<p>${fmt(t)}</p>`).join("")}${m.rule ? `<pre class="code rule">${esc(m.rule)}</pre>` : ""}</div>
      <div class="model__visual">${visual}</div>
    </article>`;
  }).join("");

  // gentle 3D tilt that follows the mouse
  const modelList = $("#model-list");
  modelList.addEventListener("pointermove", (e) => {
    const b = e.target.closest(".figure-btn");
    if (!b || reduced() || e.pointerType !== "mouse") return;
    const r = b.getBoundingClientRect();
    b.style.setProperty("--ry", `${((e.clientX - r.left) / r.width - 0.5) * 6}deg`);
    b.style.setProperty("--rx", `${-((e.clientY - r.top) / r.height - 0.5) * 6}deg`);
  });
  modelList.addEventListener("pointerout", (e) => {
    const b = e.target.closest(".figure-btn");
    if (b && !b.contains(e.relatedTarget)) { b.style.setProperty("--rx", "0deg"); b.style.setProperty("--ry", "0deg"); }
  });

  // lightbox that zooms out of the thumbnail
  const lb = $("#lightbox"), lbImg = $("#lightbox-img");
  modelList.addEventListener("click", async (e) => {
    const b = e.target.closest(".figure-btn");
    if (!b) return;
    $("#lightbox-title").textContent = b.dataset.cap;
    lbImg.src = `assets/${b.dataset.fig}`;
    lbImg.alt = b.dataset.cap;
    const from = b.querySelector("img").getBoundingClientRect();
    lb.showModal();
    if (reduced()) return;
    await lbImg.decode().catch(() => {});
    const to = lbImg.getBoundingClientRect();
    if (!to.width) return;
    const dx = from.left - to.left, dy = from.top - to.top, s = from.width / to.width;
    lbImg.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${s})`, transformOrigin: "0 0" },
      { transform: "none", transformOrigin: "0 0" }], { duration: 480, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
  });
  $("#lightbox-close").addEventListener("click", () => lb.close());
  lb.addEventListener("click", (e) => { if (e.target === lb) lb.close(); });

  /* ------------------------------------------------------------------ */
  /* Tests                                                              */
  /* ------------------------------------------------------------------ */
  $("#tests-intro").textContent =
    `Each case sets up a situation and states the expected answer for several goals. Both engines must agree with it. ${S.testsPassed} of ${S.tests} cases pass, and the ${S.unitTests} unit tests pass.`;
  const tick = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 5"/></svg>';
  $("#cases").innerHTML = D.testCases.map((t, i) => `
    <tr style="--i:${i}">
      <td>${esc(t.id)}</td>
      <td><strong>${fmt(t.title)}</strong><span class="muted">${fmt(t.description)}</span></td>
      <td>${t.checks}</td>
      <td><span class="${t.pass ? "pass" : "fail"}">${t.pass ? tick + "Pass" : "Fail"}</span></td>
    </tr>`).join("");
  const casesTable = $("#cases-table");
  if (reduced()) casesTable.classList.remove("animate");
  else observe(casesTable, () => window.dispatchEvent(new CustomEvent("krr:tests")));

  /* reveals and the team underline */
  $$(".reveal").forEach((r) => observe(r));
  observe($("#team-list"));
  onScroll();
})();
