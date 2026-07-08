/* LATED line recovery — application logic.
   State lives in one object; every control re-renders from it; the fit
   config sent to /api/fit is exactly what the parameter board shows. */

import { fmt, renderCorner, renderCoverage, renderMainPlot, svgStandalone, turbo } from "./plot.js?v=12";

const $ = id => document.getElementById(id);
/* Segmented option switch: the house control for every option choice.
   options: [{value, label(html ok), title?, disabled?}] */
function segSwitch(host, options, current, onpick) {
  host.innerHTML = "";
  host.classList.add("mode-switch");
  for (const o of options) {
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = o.label;
    if (o.title) b.title = o.title;
    b.disabled = !!o.disabled;
    b.classList.toggle("on", o.value === current);
    b.onclick = () => onpick(o.value);
    host.appendChild(b);
  }
}
const state = {
  meta: null,
  zMode: "single",                 // 'single' | 'range'
  z: 3.05, zSigma: 0,
  zMin: 3.0, zMax: 3.2,
  preset: null,                    // preset id or null (custom)
  exampleId: null,                 // selected worked example, if any
  bands: [],                       // selected band names, sorted by pivot
  phot: {},                        // band -> {flux, err} in the chosen unit
  unit: "uJy",                     // 'uJy' | 'nJy' | 'mag'
  betaMode: "free", beta: -2.0, betaSigma: "",   // "" -> server default
  betaLo: -2.3, betaHi: -1.7,      // 'range' mode -> fixed at centre ± half
  gridMin: -3.5, gridMax: 1.0, gridN: 61,
  av: 0, avSigma: 0.01, dustLaw: "calzetti",
  lam0Um: 2,                       // pivot wavelength [um]; editable, always fixed
  recCase: "B", te: 10000, ne: 100,   // Balmer recombination conditions
  balmerLocked: true,              // ratios pinned to the chosen conditions
  showOff: false,                  // off lines collapsed behind a bar
  lines: [],                       // [{name, rest_wave, role, tied_to, ratio, custom}]
  ratios: [{ name: "R3", numerator: "OIII5007", denominator: "Hbeta" }],
  nmc: 300, seed: 9496, fast: false, mcMethod: "posterior",
  cornerShowBeta: true, cornerShowAv: false,
  result: null,
};

/* Effective (z, sigma_z): a z range maps to its centre with a Gaussian of
   half the range, matching the paper's slice-uncertainty convention. */
function effectiveZ() {
  if (state.zMode === "range") {
    const lo = Math.min(state.zMin, state.zMax), hi = Math.max(state.zMin, state.zMax);
    return { z: 0.5 * (lo + hi), zSigma: Math.max(0.5 * (hi - lo), 0) };
  }
  return { z: state.z, zSigma: state.zSigma };
}

/* Convert one photometry entry in the chosen input unit to (uJy, uJy). */
const UNIT_LABEL = { uJy: "µJy", nJy: "nJy", mag: "AB mag" };
function toUJy(flux, err) {
  if (state.unit === "nJy") return [flux / 1000, err / 1000];
  if (state.unit === "mag") {
    const f = Math.pow(10, -0.4 * (flux - 23.9));      // AB mag -> µJy
    return [f, f * 0.4 * Math.LN10 * err];             // symmetric approx
  }
  return [flux, err];
}

const curveCache = {};             // band -> {wave_aa, trans, pivot_aa}
const pivotOf = {};                // band -> pivot AA
const halfPower = {};              // band -> [lo, hi]
const bandColorOf = {};            // band -> color, normalised per instrument

/* ── helpers ─────────────────────────────────────────────────────────── */

async function fetchCurves(names) {
  const missing = names.filter(n => !curveCache[n]);
  await Promise.all(missing.map(async n => {
    const r = await fetch(`/api/filters/${n}`);
    curveCache[n] = await r.json();
    curveCache[n].color = bandColorOf[n];
  }));
  return names.map(n => curveCache[n]);
}

function enabledLines() { return state.lines.filter(l => l.role !== "off"); }

function sortBands() {
  state.bands.sort((a, b) => pivotOf[a] - pivotOf[b]);
}

const LINE_LABELS = {
  Halpha: "Hα", Hbeta: "Hβ", Hgamma: "Hγ", Hdelta: "Hδ", Hepsilon: "Hε",
  OIII5007: "[O III]5007", OIII4959: "[O III]4959", OII3727: "[O II]3727",
  NeIII3869: "[Ne III]", HeI10830: "He I 1.08µm", NII6584: "[N II]",
  SII6717: "[S II]6717", SII6731: "[S II]6731", PaBeta: "Paβ",
};
const label = n => LINE_LABELS[n] || n;

/* ── boot ────────────────────────────────────────────────────────────── */

async function boot() {
  const meta = await (await fetch("/api/meta")).json();
  state.meta = meta;
  $("version").textContent = `v${meta.version}`;
  for (const f of meta.filters) {
    pivotOf[f.name] = f.pivot_aa;
    halfPower[f.name] = f.half_power_aa;
  }
  // colours run blue -> red WITHIN each instrument (F070W bluest / F480M
  // reddest for NIRCam; F560W bluest / F2550W reddest for MIRI, ...)
  const byGroup = {};
  for (const f of meta.filters)
    (byGroup[f.group] = byGroup[f.group] || []).push(f);
  for (const fs of Object.values(byGroup)) {
    const lo = Math.log(Math.min(...fs.map(f => f.pivot_aa)));
    const hi = Math.log(Math.max(...fs.map(f => f.pivot_aa)));
    for (const f of fs) {
      const t = hi > lo ? (Math.log(f.pivot_aa) - lo) / (hi - lo) : 0.5;
      bandColorOf[f.name] = turbo(0.06 + 0.88 * t);
    }
  }
  state.lines = meta.default_lines.map(l => ({ ...l, custom: false }));
  restoreFromHash();
  renderPresets();
  renderBandGroups();
  renderAll();
  wireStatic();
  $("btn-run").disabled = false;
}

function renderAll() {
  syncBandChecks();
  renderZInputs();
  renderPhotTable();
  renderBetaDetail();
  renderLineTable();
  renderRatios();
  refreshCoverage();
  $("in-av").value = state.av;
  $("in-avsigma").value = state.avSigma;
  $("in-lam0").value = state.lam0Um;
  $("in-nmc").value = state.nmc;
  $("in-seed").value = state.seed;
  $("in-fast").checked = state.fast;
  renderSwitches();
  $("ck-corner-beta").checked = state.cornerShowBeta;
  $("ck-corner-av").checked = state.cornerShowAv;
  updateCaseBNote();
  for (const b of document.querySelectorAll("[data-switch='beta'] button"))
    b.classList.toggle("on", b.dataset.val === state.betaMode);
  for (const b of document.querySelectorAll("[data-switch='zmode'] button"))
    b.classList.toggle("on", b.dataset.val === state.zMode);
}

function updateZEcho() {
  const { z, zSigma } = effectiveZ();
  $("z-echo").textContent = `fitting at z = ${z.toFixed(3)}` +
    (zSigma > 0 ? ` ± ${zSigma.toFixed(3)} (propagated through the MC)` : "");
  $("echo-z").textContent = `z = ${z.toFixed(3)}` +
    (zSigma > 0 ? ` ± ${zSigma.toFixed(3)}` : "");
}

function renderZInputs() {
  const host = $("z-inputs");
  if (state.zMode === "range") {
    host.innerHTML = `
      <div class="field-grid">
        <label class="field"><span class="field-label">z<sub>min</sub></span>
          <input type="number" id="in-zmin" step="0.01" min="0.01" value="${state.zMin}"></label>
        <label class="field"><span class="field-label">z<sub>max</sub></span>
          <input type="number" id="in-zmax" step="0.01" min="0.01" value="${state.zMax}"></label>
      </div>`;
    $("in-zmin").oninput = e => {
      state.zMin = parseFloat(e.target.value) || state.zMin;
      onZChanged();
    };
    $("in-zmax").oninput = e => {
      state.zMax = parseFloat(e.target.value) || state.zMax;
      onZChanged();
    };
  } else {
    host.innerHTML = `
      <div class="field-grid">
        <label class="field"><span class="field-label">redshift <i>z</i></span>
          <input type="number" id="in-z" step="0.01" min="0.01" value="${state.z}"></label>
        <label class="field"><span class="field-label">&sigma;<sub>z</sub> (slice width)</span>
          <input type="number" id="in-zsigma" step="0.005" min="0" value="${state.zSigma}"></label>
      </div>`;
    $("in-z").oninput = e => {
      state.z = parseFloat(e.target.value) || state.z;
      state.preset = null;
      renderPresets();
      onZChanged();
    };
    $("in-zsigma").oninput = e => {
      state.zSigma = parseFloat(e.target.value) || 0;
      updateZEcho();
    };
  }
  updateZEcho();
}

function onZChanged() {
  updateZEcho();
  renderLineTable();
  refreshCoverage();
}

/* ── worked examples: published photometry of spectroscopic candidates ─ */

const EXAMPLES = [
  { id: "CR3", label: "CR3 (z=3.193), Cai+2025", z: 3.193,
    title: "MPG-CR3, metal-free candidate: F200W/F277W/F356W; spectroscopic [O III]/H\u03b2 < 0.89",
    phot: { F200W: [13.6, 1.9], F277W: [24.9, 1.6], F356W: [4.0, 1.4] } },
  { id: "AMORE6", label: "AMORE6 (z=5.725), Morishita+2025", z: 5.7253,
    title: "AMORE6: F356W/F410M/F444W; spectroscopic [O III]/H\u03b2 < 0.33",
    phot: { F356W: [16.8, 3.9], F410M: [10.0, 4.8], F444W: [26.6, 3.1] } },
  { id: "GLIMPSE", label: "GLIMPSE-16043 (z=6.203), Fujimoto+2025", z: 6.20285,
    title: "GLIMPSE-16043, Table 5 photometry: NIRCam bands covering H\u03b3\u2013He I; spectroscopic [O III]/H\u03b2 = 1.78 \u00b1 0.18",
    phot: { F356W: [3.08, 0.49], F410M: [0.78, 0.92],
            F444W: [4.07, 0.49], F480M: [10.95, 1.91] } },
];

function applyExample(ex) {
  state.preset = null;
  state.exampleId = ex.id;
  state.zMode = "single";
  state.z = ex.z;
  state.zSigma = 0;
  state.unit = "nJy";
  state.betaMode = "fixed";
  state.beta = -2.0;
  state.betaSigma = "";
  state.bands = Object.keys(ex.phot);
  sortBands();
  for (const [b, fe] of Object.entries(ex.phot))
    state.phot[b] = { flux: fe[0], err: fe[1] };
  renderPresets();
  renderAll();
  run();                       // clicking an example runs its fit
}

function renderExamples() {
  const row = $("example-row");
  row.innerHTML = "";
  for (const ex of EXAMPLES) {
    const it = document.createElement("span");
    it.className = "example-item" + (state.exampleId === ex.id ? " selected" : "");
    it.textContent = ex.label;
    it.title = ex.title;
    it.onclick = () => applyExample(ex);
    row.appendChild(it);
  }
}

/* ── presets ─────────────────────────────────────────────────────────── */

function renderPresets() {
  const row = $("preset-row");
  row.innerHTML = "";
  for (const p of state.meta.presets) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = p.id;
    b.title = `z = ${p.z}; bands ${p.bands.join(", ")}; slope fixed at \u03b2 = ${p.fix_beta}`;
    b.classList.toggle("on", state.preset === p.id);
    b.onclick = () => applyPreset(p);
    row.appendChild(b);
  }
  const c = document.createElement("button");
  c.type = "button";
  c.textContent = "custom";
  c.classList.toggle("on", state.preset === null);
  c.onclick = () => { state.preset = null; renderPresets(); };
  row.appendChild(c);
  renderExamples();
}

function applyPreset(p) {
  state.preset = p.id;
  state.exampleId = null;
  state.zMode = "single";
  state.z = p.z;
  state.zSigma = 0;
  state.bands = [...p.bands];
  sortBands();
  for (const b of state.bands) if (!state.phot[b]) state.phot[b] = { flux: "", err: "" };
  state.betaMode = "fixed";
  state.beta = p.fix_beta;
  renderPresets();
  renderAll();
}

/* ── band picker ─────────────────────────────────────────────────────── */

function renderBandGroups() {
  const host = $("band-groups");
  host.innerHTML = "";
  const groups = {};
  for (const f of state.meta.filters)
    (groups[f.group] = groups[f.group] || []).push(f);
  const RANK = { "JWST NIRCam": 0, "JWST MIRI": 1, "Roman WFI": 2 };
  const order = Object.keys(groups).sort((a, b) =>
    (RANK[a] ?? 9) - (RANK[b] ?? 9) || a.localeCompare(b));
  for (const g of order) {
    const det = document.createElement("details");
    det.className = "band-group";
    det.open = g === "JWST NIRCam";
    const sum = document.createElement("summary");
    sum.dataset.group = g;
    det.appendChild(sum);
    const grid = document.createElement("div");
    grid.className = "band-grid";
    for (const f of groups[g]) {
      const lab = document.createElement("label");
      lab.className = "band-check";
      lab.dataset.band = f.name;
      lab.style.setProperty("--swatch", bandColorOf[f.name]);
      lab.title = `pivot ${(f.pivot_aa / 1e4).toFixed(2)} µm`;
      const inp = document.createElement("input");
      inp.type = "checkbox";
      inp.onchange = () => toggleBand(f.name, inp.checked);
      lab.append(inp, Object.assign(document.createElement("span"),
        { className: "swatch" }), document.createTextNode(f.name));
      grid.appendChild(lab);
    }
    det.appendChild(grid);
    host.appendChild(det);
  }
  syncBandChecks();
}

function syncBandChecks() {
  for (const lab of document.querySelectorAll(".band-check")) {
    const on = state.bands.includes(lab.dataset.band);
    lab.classList.toggle("on", on);
    lab.querySelector("input").checked = on;
  }
  for (const sum of document.querySelectorAll(".band-group summary")) {
    const g = sum.dataset.group;
    const n = state.bands.filter(b =>
      state.meta.filters.find(f => f.name === b)?.group === g).length;
    sum.innerHTML = `${g} ${n ? `<span class="band-group-count">· ${n}</span>` : ""}`;
  }
}

function toggleBand(name, on) {
  if (on) {
    if (!state.bands.includes(name)) state.bands.push(name);
    if (!state.phot[name]) state.phot[name] = { flux: "", err: "" };
    state.preset = null;
  } else {
    state.bands = state.bands.filter(b => b !== name);
  }
  sortBands();
  renderPresets();
  syncBandChecks();
  renderPhotTable();
  refreshCoverage();
}

async function refreshCoverage() {
  const curves = await fetchCurves(state.bands);
  renderCoverage($("coverage-strip"), curves, effectiveZ().z, enabledLines());
}

/* ── photometry table ────────────────────────────────────────────────── */

function renderPhotTable() {
  const tb = $("phot-table").querySelector("tbody");
  tb.innerHTML = "";
  if (!state.bands.length) {
    tb.innerHTML = `<tr class="phot-empty"><td colspan="3">select bands above</td></tr>`;
    return;
  }
  for (const b of state.bands) {
    const tr = document.createElement("tr");
    const td0 = document.createElement("td");
    td0.innerHTML = `<span class="phot-band" style="--swatch:${bandColorOf[b]}">
      <span class="swatch"></span>${b}</span>`;
    tr.appendChild(td0);
    for (const key of ["flux", "err"]) {
      const td = document.createElement("td");
      const inp = document.createElement("input");
      inp.type = "number";
      inp.step = state.unit === "mag" ? "0.01" : "0.001";
      inp.value = state.phot[b][key];
      inp.placeholder = key === "flux" ? UNIT_LABEL[state.unit] : "±";
      inp.oninput = () => { state.phot[b][key] = inp.value; };
      td.appendChild(inp);
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  const th = document.querySelectorAll("#phot-table thead th");
  th[1].innerHTML = state.unit === "mag" ? "mag" : `flux [${UNIT_LABEL[state.unit]}]`;
  th[2].innerHTML = "&plusmn; err";
}

/* ── continuum board ─────────────────────────────────────────────────── */

function renderBetaDetail() {
  const host = $("beta-detail");
  if (state.betaMode === "fixed") {
    host.innerHTML = `
      <label>β = <input type="number" id="in-beta" step="0.1" value="${state.beta}"></label>
      <label>σ<sub>β</sub> <input type="number" id="in-betasigma" step="0.05" min="0"
        placeholder="0.3" value="${state.betaSigma}" title="Gaussian slope prior folded into the Monte-Carlo; blank = default 0.3"></label>`;
    $("in-beta").oninput = e => { state.beta = parseFloat(e.target.value); };
    $("in-betasigma").oninput = e => { state.betaSigma = e.target.value; };
  } else if (state.betaMode === "range") {
    const echo = () => {
      const c = 0.5 * (state.betaLo + state.betaHi);
      const s = Math.abs(0.5 * (state.betaHi - state.betaLo));
      $("beta-range-echo").textContent =
        `→ fixed at β = ${c.toFixed(2)} with σβ = ${s.toFixed(2)} in the error budget`;
    };
    host.innerHTML = `
      <label>β<sub>min</sub> <input type="number" id="in-blo" step="0.1" value="${state.betaLo}"></label>
      <label>β<sub>max</sub> <input type="number" id="in-bhi" step="0.1" value="${state.betaHi}"></label>
      <span class="beta-echo" id="beta-range-echo"></span>`;
    $("in-blo").oninput = e => { state.betaLo = parseFloat(e.target.value); echo(); };
    $("in-bhi").oninput = e => { state.betaHi = parseFloat(e.target.value); echo(); };
    echo();
  } else {
    host.innerHTML = `
      <label>search range <input type="number" id="in-gmin" step="0.5" value="${state.gridMin}"> …</label>
      <label><input type="number" id="in-gmax" step="0.5" value="${state.gridMax}"></label>
      <label>× <input type="number" id="in-gn" step="10" min="2" max="1001" value="${state.gridN}"></label>`;
    $("in-gmin").oninput = e => { state.gridMin = parseFloat(e.target.value); };
    $("in-gmax").oninput = e => { state.gridMax = parseFloat(e.target.value); };
    $("in-gn").oninput = e => { state.gridN = parseInt(e.target.value); };
  }
}

/* ── line table ──────────────────────────────────────────────────────── */

function lineInCoverage(l) {
  const w = l.rest_wave * (1 + effectiveZ().z);
  return state.bands.some(b => halfPower[b] && w >= halfPower[b][0] && w <= halfPower[b][1]);
}

function lineRow(l) {
  const tr = document.createElement("tr");
  tr.className = l.role === "off" ? "is-off" : "";

  const tdName = document.createElement("td");
  tdName.innerHTML = `<span class="line-name">${label(l.name)}</span>`;
  tr.appendChild(tdName);

  const tdRest = document.createElement("td");
  tdRest.innerHTML = `<span class="line-wave">${l.rest_wave.toFixed(1)}</span>`;
  tr.appendChild(tdRest);

  const tdObs = document.createElement("td");
  tdObs.innerHTML = `<span class="line-wave">${(l.rest_wave * (1 + effectiveZ().z) / 1e4).toFixed(2)}\u00b5m</span>`;
  tr.appendChild(tdObs);

  const tdCov = document.createElement("td");
  const dot = document.createElement("span");
  dot.className = "cov-dot" + (lineInCoverage(l) ? " in" : "");
  dot.title = lineInCoverage(l)
    ? "falls inside a selected band (half-power)"
    : "outside every selected band \u2014 unconstrained";
  tdCov.appendChild(dot);
  tr.appendChild(tdCov);

  const tdRole = document.createElement("td");
  const sw = document.createElement("div");
  sw.className = "role-switch";
  for (const val of ["free", "tied", "off"]) {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.val = val;
    b.textContent = val;
    b.classList.toggle("on", l.role === val);
    b.onclick = () => setLineRole(l, val);
    sw.appendChild(b);
  }
  tdRole.appendChild(sw);
  tr.appendChild(tdRole);

  const tdTie = document.createElement("td");
  if (l.role === "tied") {
    const ed = document.createElement("span");
    ed.className = "tie-editor";
    const ratio = document.createElement("input");
    ratio.type = "number";
    ratio.step = "0.001";
    ratio.value = l.ratio ?? "";
    // ratios pinned to the chosen nebular conditions until unlocked
    ratio.disabled = state.balmerLocked && balmerManaged(l);
    if (ratio.disabled)
      ratio.title = "set by the nebular conditions above; unlock to edit";
    ratio.oninput = () => { l.ratio = parseFloat(ratio.value); };
    const times = document.createElement("span");
    times.textContent = "\u00d7";
    const sel = document.createElement("select");
    for (const t of state.lines.filter(x => x.name !== l.name && x.role !== "off")) {
      const o = document.createElement("option");
      o.value = t.name;
      o.textContent = label(t.name);
      o.selected = l.tied_to === t.name;
      sel.appendChild(o);
    }
    sel.disabled = state.balmerLocked && balmerManaged(l);
    sel.onchange = () => { l.tied_to = sel.value; };
    if (!l.tied_to) l.tied_to = sel.value;
    ed.append(ratio, times, sel);
    tdTie.appendChild(ed);
  } else {
    tdTie.innerHTML = `<span class="line-wave">${l.role === "free" ? "amplitude \u2265 0" : "\u2014"}</span>`;
  }
  tr.appendChild(tdTie);

  const tdDel = document.createElement("td");
  if (l.custom) {
    const del = document.createElement("button");
    del.className = "row-del";
    del.type = "button";
    del.textContent = "\u00d7";
    del.title = "remove custom line";
    del.onclick = () => {
      state.lines = state.lines.filter(x => x !== l);
      renderLineTable(); renderRatios(); refreshCoverage();
    };
    tdDel.appendChild(del);
  }
  tr.appendChild(tdDel);
  return tr;
}

function renderLineTable() {
  const tb = $("line-table").querySelector("tbody");
  tb.innerHTML = "";
  const on = state.lines.filter(l => l.role !== "off");
  const off = state.lines.filter(l => l.role === "off");
  for (const l of on) tb.appendChild(lineRow(l));
  if (off.length) {
    const bar = document.createElement("tr");
    bar.className = "off-bar";
    const names = off.slice(0, 4).map(x => label(x.name)).join(", ")
      + (off.length > 4 ? ", \u2026" : "");
    bar.innerHTML = state.showOff
      ? `<td colspan="7">\u25be <span class="off-count">${off.length} lines off</span> \u00b7 click to collapse</td>`
      : `<td colspan="7">\u25b8 <span class="off-count">${off.length} lines off</span> \u00b7 ${names} \u00b7 click to show</td>`;
    bar.onclick = () => { state.showOff = !state.showOff; renderLineTable(); };
    tb.appendChild(bar);
    if (state.showOff) for (const l of off) tb.appendChild(lineRow(l));
  }
  renderBalmerLock();
}

function setLineRole(l, role) {
  l.role = role;
  if (role === "tied" && !l.ratio) l.ratio = 1.0;
  // ties into this line break if it is switched off
  if (role === "off") {
    for (const x of state.lines)
      if (x.role === "tied" && x.tied_to === l.name) x.role = "off";
  }
  renderLineTable();
  renderRatios();
  refreshCoverage();
}

/* ── ratios ──────────────────────────────────────────────────────────── */

function renderRatios() {
  const host = $("ratio-rows");
  host.innerHTML = "";
  const opts = enabledLines().map(l => l.name);
  state.ratios.forEach((r, idx) => {
    const row = document.createElement("div");
    row.className = "ratio-row";
    const nm = document.createElement("input");
    nm.type = "text";
    nm.value = r.name;
    nm.oninput = () => { r.name = nm.value; };
    const mkSel = key => {
      const s = document.createElement("select");
      for (const n of opts) {
        const o = document.createElement("option");
        o.value = n; o.textContent = label(n); o.selected = r[key] === n;
        s.appendChild(o);
      }
      if (!opts.includes(r[key])) r[key] = opts[0];
      s.onchange = () => { r[key] = s.value; };
      return s;
    };
    const slash = document.createElement("span");
    slash.className = "ratio-slash";
    slash.textContent = "=";
    const slash2 = document.createElement("span");
    slash2.className = "ratio-slash";
    slash2.textContent = "/";
    const del = document.createElement("button");
    del.className = "row-del";
    del.type = "button";
    del.textContent = "×";
    del.onclick = () => { state.ratios.splice(idx, 1); renderRatios(); };
    row.append(nm, slash, mkSel("numerator"), slash2, mkSel("denominator"), del);
    host.appendChild(row);
  });
}

/* ── run fit ─────────────────────────────────────────────────────────── */

function buildConfig() {
  let continuum;
  if (state.betaMode === "fixed") {
    continuum = { beta_mode: "fixed", beta: state.beta,
                  beta_sigma: state.betaSigma === "" ? null
                    : parseFloat(state.betaSigma) };
  } else if (state.betaMode === "range") {
    continuum = { beta_mode: "fixed",
                  beta: 0.5 * (state.betaLo + state.betaHi),
                  beta_sigma: Math.abs(0.5 * (state.betaHi - state.betaLo)) };
  } else {
    continuum = { beta_mode: "free", grid_min: state.gridMin,
                  grid_max: state.gridMax, grid_n: state.gridN };
  }
  continuum.pivot_wavelength = state.lam0Um * 1e4;
  const { z, zSigma } = effectiveZ();
  const enabled = new Set(enabledLines().map(l => l.name));
  return {
    z,
    z_sigma: zSigma,
    continuum,
    lines: state.lines.map(l => ({
      name: l.name, rest_wave: l.rest_wave, role: l.role,
      tied_to: l.role === "tied" ? l.tied_to : null,
      ratio: l.role === "tied" ? l.ratio : null,
    })),
    dust: { av: state.av, av_sigma: state.avSigma, law: state.dustLaw },
    mc: { n: state.nmc, seed: state.seed, fast: state.fast,
          method: state.mcMethod, keep_draws: true },
    ratios: state.ratios.filter(r =>
      enabled.has(r.numerator) && enabled.has(r.denominator)),
  };
}

function buildPhotometry() {
  const phot = {};
  for (const b of state.bands) {
    const { flux, err } = state.phot[b];
    if (flux === "" || err === "") continue;
    phot[b] = toUJy(parseFloat(flux), parseFloat(err));
  }
  return phot;
}

async function run() {
  const btn = $("btn-run");
  const banner = $("error-banner");
  banner.hidden = true;
  const phot = buildPhotometry();
  if (Object.keys(phot).length < Math.min(3, state.bands.length || 3)) {
    banner.textContent = "enter flux and error for at least 3 bands";
    banner.hidden = false;
    return;
  }
  btn.disabled = true;
  btn.querySelector(".run-label").textContent = "fitting…";
  $("loading-bar").hidden = false;
  try {
    const r = await fetch("/api/fit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photometry: phot, config: buildConfig() }),
    });
    const body = await r.json();
    if (!r.ok) {
      const msg = typeof body.detail === "string" ? body.detail
        : JSON.stringify(body.detail, null, 2);
      throw new Error(msg);
    }
    state.result = body;
    saveToHash();
    await renderResults();
  } catch (err) {
    banner.textContent = String(err.message || err);
    banner.hidden = false;
  } finally {
    $("loading-bar").hidden = true;
    btn.disabled = false;
    btn.querySelector(".run-label").textContent = "Recover line fluxes";
  }
}

/* Shared display strings for a ratio result: used by BOTH the verdict card
   and the corner-plot inset so the numbers always agree.  Limits carry two
   significant figures; measured values show the median with errors at two
   significant figures and the median matched to the error decimals. */
function ratioDisplay(r) {
  const p = r.value.percentiles;
  const sig2 = v => Number(v.toPrecision(2)).toString();
  if (r.status === "upper_limit")
    return { kind: "upper", lim: sig2(p.p975), lim1: sig2(p.p84) };
  if (r.status === "lower_limit")
    return { kind: "lower", lim: sig2(p.p025), lim1: sig2(p.p16) };
  if (r.status === "unconstrained") return { kind: "none" };
  const up = p.p84 - p.p50, lo = p.p50 - p.p16;
  const errDec = e => (e > 0) ? Math.max(0, 1 - Math.floor(Math.log10(e))) : 0;
  const dec = Math.max(errDec(up), errDec(lo));
  return { kind: "measured", med: p.p50.toFixed(dec),
           up: "+" + up.toFixed(dec), lo: "\u2212" + lo.toFixed(dec) };
}

/* ── results ─────────────────────────────────────────────────────────── */

async function renderResults() {
  const res = state.result;
  if (!res) return;
  $("stage-empty").hidden = true;
  $("results").hidden = false;

  // warnings from the engine
  const wb = $("warn-banner");
  if (res.warnings && res.warnings.length) {
    wb.innerHTML = "<ul>" + res.warnings.map(w => `<li>${w}</li>`).join("") + "</ul>";
    wb.hidden = false;
  } else {
    wb.hidden = true;
  }

  // headline cards
  const hl = $("headline-row");
  hl.innerHTML = "";
  const card = (label_, value, flag, sub, accent = false) => {
    const d = document.createElement("div");
    d.className = "headline-card" + (accent ? " accent" : "");
    d.innerHTML = `<div class="hl-label">${label_}</div>
      <div class="hl-value"><span>${value}</span>${flag
        ? `<span class="limit-flag">${flag}</span>` : ""}</div>
      ${sub ? `<div class="hl-sub">${sub}</div>` : ""}`;
    hl.appendChild(d);
  };
  for (const r of res.ratios) {
    const name_ = `${r.name} = ${label(r.numerator)} / ${label(r.denominator)}`;
    const pin = r.pinned_fraction > 0.05
      ? ` · ${(r.pinned_fraction * 100).toFixed(0)}% draws pinned` : "";
    const d = ratioDisplay(r);
    if (d.kind === "upper") {
      card(name_, `&lt; ${d.lim}`, "2\u03c3 UPPER LIMIT",
        `1\u03c3: &lt; ${d.lim1}${pin}`, true);
    } else if (d.kind === "lower") {
      card(name_, `&gt; ${d.lim}`, "2\u03c3 LOWER LIMIT",
        `1\u03c3: &gt; ${d.lim1} (denominator undetected)${pin}`, true);
    } else if (d.kind === "none") {
      card(name_, "—", "UNCONSTRAINED",
        "neither line detected / no coverage", true);
    } else {
      card(name_,
        `${d.med}<span class="hl-stack"><span>${d.up}</span><span>${d.lo}</span></span>`,
        null, `best fit ${fmt(r.value.best, 3)}${pin}`, true);
    }
  }
  const bp = res.beta.percentiles;
  card(`β (${res.beta_role})`, fmt(res.beta.best, 3), null,
    res.beta_role === "free" ? `16–84%: ${fmt(bp.p16, 3)} – ${fmt(bp.p84, 3)}`
      : "slope pinned");
  card("χ² / dof", `${fmt(res.chi2, 3)} / ${res.ndof}`, null,
    `${res.bands.length} bands · ${res.n_free_parameters} free params`);

  // main plot (displayed in the chosen flux unit; mag input displays in µJy)
  const curves = await fetchCurves(res.bands);
  const phot = buildPhotometry();
  const dispF = state.unit === "nJy" ? 1000 : 1;
  const dispU = state.unit === "nJy" ? "nJy" : "µJy";
  renderMainPlot($("main-plot"), $("plot-tip"), {
    bands: res.bands.map(b => ({
      name: b, pivot: pivotOf[b], color: bandColorOf[b],
      flux: phot[b][0] * dispF, err: phot[b][1] * dispF,
      model: res.band_model_uJy[b] * dispF,
    })),
    curves,
    modelCurve: {
      wave_aa: res.model_curve.wave_aa,
      total_uJy: res.model_curve.total_uJy.map(v => v * dispF),
      continuum_uJy: res.model_curve.continuum_uJy.map(v => v * dispF),
    },
    yUnit: dispU,
    lineMarks: res.lines
      .filter(l => l.flux.best > 0 || l.role === "free")
      .map(l => ({ label: label(l.name), waveObs: l.obs_wave, free: l.role === "free" })),
  });

  // posterior corner plot
  const cc = $("corner-card");
  const bestOf = {
    C: res.continuum_flam_at_pivot.best,
    beta: res.beta.best,
  };
  for (const l of res.lines) bestOf[l.name] = l.flux.best;
  const FLUX_UNIT = "erg s⁻¹ cm⁻²";
  const params = [];
  if (res.posterior_draws) {
    const add = (key, lab, unit) => {
      const v = res.posterior_draws[key];
      if (!v || v.length < 10) return;
      let mn = Infinity, mx = -Infinity;
      for (const x of v) { if (x < mn) mn = x; if (x > mx) mx = x; }
      if (!(mx > mn)) return;               // constant parameter
      params.push({ label: lab, values: v, best: bestOf[key], unit });
    };
    add("C", "C", FLUX_UNIT + " Å⁻¹");
    if (state.cornerShowBeta) add("beta", "β", "");
    if (state.cornerShowAv) add("A_V", "A\u1d65", "mag");
    for (const l of res.lines)
      if (l.role === "free") add(l.name, label(l.name), FLUX_UNIT);
  }
  let inset = null;
  const r0 = res.ratios[0];
  if (r0 && res.posterior_draws && res.posterior_draws[r0.name]) {
    inset = { label: r0.name, values: res.posterior_draws[r0.name],
              best: r0.value.best, status: r0.status,
              p975: r0.value.percentiles.p975,
              p84: r0.value.percentiles.p84,
              disp: ratioDisplay(r0),
              xlabel: `${r0.name} = ${label(r0.numerator)}/${label(r0.denominator)}` };
  }
  if (params.length >= 2) {
    cc.hidden = false;
    renderCorner($("corner-plot"), params, inset);
  } else {
    cc.hidden = true;
  }

  // flux table
  const ft = $("flux-table");
  ft.innerHTML = `<tr><th>line</th><th>role</th><th class="num">flux</th>
    <th class="num">16–84%</th><th class="num" title="1σ depth for this line's amplitude given the band errors">depth σ</th>
    <th class="num">EW₀ [Å]</th><th class="num">EW₀ 16–84%</th></tr>`;
  for (const l of res.lines) {
    const p = l.flux.percentiles;
    const tr = document.createElement("tr");
    const roleBadge = l.role === "free"
      ? `<span class="role-badge role-free">free</span>`
      : `<span class="role-badge role-tied" title="${fmt(l.ratio_effective, 4)} × ${label(l.root)}">tied</span>`;
    const ewp = l.ew0_rest_percentiles;
    tr.innerHTML = `<td>${label(l.name)}${l.constrained ? "" :
        ` <span class="limit-flag" title="line falls outside every fitted band">NO COVERAGE</span>`}</td>
      <td>${roleBadge}</td>
      <td class="num">${fmt(l.flux.best)}</td>
      <td class="num dim">${fmt(p.p16)} – ${fmt(p.p84)}</td>
      <td class="num dim">${fmt(l.flux_sensitivity_1sig, 2)}</td>
      <td class="num">${l.ew0_rest === null ? "—" : fmt(l.ew0_rest, 3)}</td>
      <td class="num dim">${ewp ? `${fmt(ewp.p16, 3)} – ${fmt(ewp.p84, 3)}` : "—"}</td>`;
    ft.appendChild(tr);
  }

  // summary table
  const st = $("summary-table");
  const cp = res.continuum_flam_at_pivot;
  st.innerHTML = "";
  const rows = [
    ["z (fixed)", `${res.config.z}${res.config.z_sigma ? ` ± ${res.config.z_sigma}` : ""}`],
    ["β", `${fmt(res.beta.best, 3)} (${res.beta_role})`],
    [`C at λ₀=${res.config.continuum.pivot_wavelength / 1e4}µm`, `${fmt(cp.best)} erg s⁻¹ cm⁻² Å⁻¹`],
    ["A_V", `${res.config.dust.av} (${res.config.dust.law})`],
    ["χ² / dof", `${fmt(res.chi2, 4)} / ${res.ndof}`],
    ["MC", `${res.config.mc.method}, n=${res.config.mc.n} (seed ${res.config.mc.seed})`],
    ["bands", res.bands.join(", ")],
  ];
  for (const [k, v] of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="dim">${k}</td><td>${v}</td>`;
    st.appendChild(tr);
  }
}

/* ── share / persist ─────────────────────────────────────────────────── */

function snapshot() {
  const { meta, result, ...rest } = state;
  return rest;
}

function saveToHash() {
  try {
    location.hash = "s=" + btoa(unescape(encodeURIComponent(
      JSON.stringify(snapshot()))));
  } catch (e) { /* non-fatal */ }
}

function restoreFromHash() {
  if (!location.hash.startsWith("#s=")) return;
  try {
    const snap = JSON.parse(decodeURIComponent(escape(
      atob(location.hash.slice(3)))));
    Object.assign(state, snap, { meta: state.meta, result: null });
    // merge default lines added after the share link was made
    if (Array.isArray(state.lines)) {
      const have = new Set(state.lines.map(l => l.name));
      for (const l of state.meta.default_lines)
        if (!have.has(l.name)) state.lines.push({ ...l, custom: false });
    } else {
      state.lines = state.meta.default_lines.map(l => ({ ...l, custom: false }));
    }
  } catch (e) { /* ignore malformed hashes */ }
}

/* ── wiring ──────────────────────────────────────────────────────────── */

function balmerRow() {
  return state.meta?.balmer?.ratios?.[state.recCase]
    ?.[String(state.te)]?.[String(state.ne)];
}

function balmerManaged(l) {
  if (l.role !== "tied") return false;
  if (l.name === "Hbeta" && l.tied_to === "Halpha") return true;
  return ["Hgamma", "Hdelta", "Hepsilon", "H8", "H9", "H10"].includes(l.name)
    && l.tied_to === "Hbeta";
}

function renderBalmerLock() {
  const b = $("btn-balmer-lock");
  if (!b) return;
  b.classList.toggle("unlocked", !state.balmerLocked);
  b.innerHTML = state.balmerLocked
    ? "&#128274; locked"
    : "&#128275; editable";
  b.title = state.balmerLocked
    ? "Balmer tie ratios are pinned to the chosen conditions; click to unlock for manual edits"
    : "Balmer tie ratios are hand-editable; click to re-lock (re-applies the chosen conditions)";
}

function renderSwitches() {
  segSwitch($("sw-unit"), [
    { value: "uJy", label: "\u00b5Jy" },
    { value: "nJy", label: "nJy" },
    { value: "mag", label: "AB mag" },
  ], state.unit, v => { state.unit = v; renderPhotTable(); renderSwitches(); });

  segSwitch($("sw-method"), [
    { value: "posterior", label: "posterior" },
    { value: "bootstrap", label: "bootstrap" },
  ], state.mcMethod, v => { state.mcMethod = v; renderSwitches(); });

  segSwitch($("sw-dustlaw"), [
    { value: "calzetti", label: "Calzetti" },
    { value: "smc", label: "SMC-like" },
  ], state.dustLaw, v => { state.dustLaw = v; renderSwitches(); });

  segSwitch($("sw-case"), [
    { value: "B", label: "B (thick)" },
    { value: "A", label: "A (thin)" },
  ], state.recCase, v => {
    state.recCase = v;
    applyBalmer();
    renderSwitches();
  });

  const temps = state.meta.balmer.temperatures_K[state.recCase];
  if (!temps.includes(state.te)) state.te = 10000;
  segSwitch($("sw-te"),
    temps.map(t => ({ value: t,
      label: t.toLocaleString("en").replace(/,/g, "\u2009") })),
    state.te, v => { state.te = v; applyBalmer(); renderSwitches(); });

  segSwitch($("sw-ne"), [
    { value: 100, label: "10\u00b2", disabled: state.recCase === "A" },
    { value: 10000, label: "10\u2074", disabled: state.recCase === "A" },
    { value: 1000000, label: "10\u2076", disabled: state.recCase === "A" },
  ], state.ne, v => { state.ne = v; applyBalmer(); renderSwitches(); });
}

function applyBalmer() {
  const table = balmerRow();
  if (!table) return;
  state.balmerLocked = true;      // a chosen condition pins the ratios
  renderBalmerLock();
  for (const l of state.lines) {
    if (l.role !== "tied") continue;
    if (l.name === "Hbeta" && l.tied_to === "Halpha") l.ratio = table.Hbeta;
    else if (table[l.name] !== undefined && l.tied_to === "Hbeta")
      l.ratio = table[l.name];
  }
  updateCaseBNote();
  renderLineTable();
}

function updateCaseBNote() {
  const table = balmerRow();
  if (!table) return;
  const dens = state.recCase === "A"
    ? "low-density limit (n<sub>e</sub> ignored)"
    : `n<sub>e</sub> = 10<sup>${Math.round(Math.log10(state.ne))}</sup> cm\u207B\u00B3`;
  $("caseb-note").innerHTML =
    `H\u03B1/H\u03B2 = ${(1 / table.Hbeta).toFixed(2)} at T<sub>e</sub> = ${state.te} K, ` +
    `Case ${state.recCase}, ${dens}`;
}

const FONT_SIZES = [13, 14, 15, 16.5, 18];
function setFontSize(idx) {
  idx = Math.min(FONT_SIZES.length - 1, Math.max(0, idx));
  document.documentElement.style.fontSize = FONT_SIZES[idx] + "px";
  try { localStorage.setItem("lated-font-idx", String(idx)); } catch (e) {}
  return idx;
}

function wireStatic() {
  let fontIdx = 2;
  try { fontIdx = parseInt(localStorage.getItem("lated-font-idx") ?? "2"); } catch (e) {}
  fontIdx = setFontSize(isNaN(fontIdx) ? 2 : fontIdx);
  $("font-dec").onclick = () => { fontIdx = setFontSize(fontIdx - 1); };
  $("font-inc").onclick = () => { fontIdx = setFontSize(fontIdx + 1); };

  for (const b of document.querySelectorAll("[data-switch='zmode'] button")) {
    b.onclick = () => {
      state.zMode = b.dataset.val;
      for (const x of b.parentElement.children)
        x.classList.toggle("on", x === b);
      renderZInputs(); renderLineTable(); refreshCoverage();
    };
  }

  $("ck-corner-beta").onchange = e => {
    state.cornerShowBeta = e.target.checked;
    if (state.result) renderResults();
  };
  $("ck-corner-av").onchange = e => {
    state.cornerShowAv = e.target.checked;
    if (state.result) renderResults();
  };
  $("btn-balmer-lock").onclick = () => {
    state.balmerLocked = !state.balmerLocked;
    if (state.balmerLocked) applyBalmer();   // re-locking re-applies conditions
    else { renderBalmerLock(); renderLineTable(); }
  };

  $("in-av").oninput = e => { state.av = parseFloat(e.target.value) || 0; };
  $("in-avsigma").oninput = e => { state.avSigma = parseFloat(e.target.value) || 0; };
  $("in-lam0").oninput = e => { state.lam0Um = parseFloat(e.target.value) || 2; };
  $("in-nmc").oninput = e => { state.nmc = parseInt(e.target.value) || 300; };
  $("in-seed").oninput = e => { state.seed = parseInt(e.target.value) || 0; };
  $("in-fast").onchange = e => { state.fast = e.target.checked; };

  for (const b of document.querySelectorAll("[data-switch='beta'] button")) {
    b.onclick = () => {
      state.betaMode = b.dataset.val;
      for (const x of b.parentElement.children)
        x.classList.toggle("on", x === b);
      renderBetaDetail();
    };
  }

  $("btn-run").onclick = run;
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") run();
  });


  $("btn-paste").onclick = async () => {
    let text;
    try { text = await navigator.clipboard.readText(); }
    catch { text = prompt("paste rows: band flux err — or flux err per selected band"); }
    if (text) parsePaste(text);
  };

  $("btn-addline").onclick = () => {
    const name = prompt("line name (e.g. CIII1909):");
    if (!name) return;
    if (state.lines.some(l => l.name === name)) { alert("name already used"); return; }
    const wave = parseFloat(prompt("rest wavelength [Å]:") || "");
    if (!(wave > 0)) return;
    state.lines.push({ name, rest_wave: wave, role: "free",
      tied_to: null, ratio: null, custom: true });
    renderLineTable(); renderRatios(); refreshCoverage();
  };

  $("btn-addratio").onclick = () => {
    const opts = enabledLines().map(l => l.name);
    if (opts.length < 2) return;
    state.ratios.push({ name: `ratio${state.ratios.length + 1}`,
      numerator: opts[0], denominator: opts[1] });
    renderRatios();
  };

  const exportPdf = (svgEl, title) => {
    const snap = svgStandalone(svgEl);
    const w = window.open("", "_blank");
    if (!w) { alert("allow pop-ups to export figures"); return; }
    w.document.write(`<!DOCTYPE html><html><head><title>${title}</title>
      <style>@page { size: ${snap.width}px ${snap.height}px; margin: 0; }
        html, body { margin: 0; padding: 0; }
        svg { display: block; width: 100%; height: auto; }</style>
      </head><body>${snap.text}
      <scr` + `ipt>onload = () => setTimeout(() => print(), 150);</scr` + `ipt>
      </body></html>`);
    w.document.close();
  };
  $("btn-pdf-sed").onclick = () => exportPdf($("main-plot"), "lated_sed_fit");
  $("btn-pdf-corner").onclick = () => exportPdf($("corner-plot"), "lated_corner_plot");

  $("btn-json").onclick = () => {
    if (!state.result) return;
    const blob = new Blob([JSON.stringify(state.result, null, 2)],
      { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "lated_fit.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  $("btn-share").onclick = async () => {
    saveToHash();
    try {
      await navigator.clipboard.writeText(location.href);
      $("btn-share").textContent = "copied ✓";
      setTimeout(() => { $("btn-share").textContent = "copy share link"; }, 1500);
    } catch { /* clipboard unavailable */ }
  };
}

function parsePaste(text) {
  const rows = text.trim().split(/[\r\n]+/).map(r =>
    r.trim().split(/[,\t; ]+/).filter(Boolean));
  let assigned = 0;
  for (const row of rows) {
    if (row.length >= 3 && isNaN(parseFloat(row[0]))) {
      const [band, f, e] = row;
      const match = state.meta.filters.find(x =>
        x.name.toLowerCase() === band.toLowerCase());
      if (match) {
        if (!state.bands.includes(match.name)) toggleBand(match.name, true);
        state.phot[match.name] = { flux: parseFloat(f), err: parseFloat(e) };
        assigned++;
      }
    }
  }
  if (!assigned) {   // fall back: flux err pairs in selected-band order
    const nums = rows.flat().map(parseFloat).filter(v => !isNaN(v));
    state.bands.forEach((b, i) => {
      if (nums.length >= 2 * i + 2)
        state.phot[b] = { flux: nums[2 * i], err: nums[2 * i + 1] };
    });
  }
  renderPhotTable();
}

boot();
