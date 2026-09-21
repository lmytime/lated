/* SVG plotting for the LATED line-recovery app: wavelength-true filter
   colors (turbo colormap), the coverage strip, and the main fit figure. */

const SVGNS = "http://www.w3.org/2000/svg";

/* Turbo colormap (Google), polynomial approximation; t in [0, 1]. */
export function turbo(t) {
  t = Math.min(1, Math.max(0, t));
  const clamp01 = v => Math.min(1, Math.max(0, v));
  const r = clamp01((34.61 + t * (1172.33 + t * (-10793.56 + t * (33300.12
            + t * (-38394.49 + t * 14825.05))))) / 255);
  const g = clamp01((23.31 + t * (557.33 + t * (1225.33 + t * (-3574.96
            + t * (1073.77 + t * 707.56))))) / 255);
  const b = clamp01((27.2 + t * (3211.1 + t * (-15327.97 + t * (27814.0
            + t * (-22569.18 + t * 6838.66))))) / 255);
  const h = v => Math.round(v * 255).toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

/* Map a pivot wavelength [AA] to a display color.  Piecewise-log so the
   optical/NIR range (Roman + NIRCam, up to 5.6 um) keeps most of the
   colormap and the MIRI range (5.6-27 um) compresses into the red tail. */
export function bandColor(pivotAA) {
  const um = pivotAA / 1e4;
  const seg = (v, lo, hi) => (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo));
  const t = um <= 5.6
    ? 0.80 * Math.min(1, Math.max(0, seg(um, 0.3, 5.6)))
    : 0.80 + 0.20 * Math.min(1, Math.max(0, seg(um, 5.6, 27)));
  return turbo(0.06 + 0.88 * t);
}

function el(name, attrs = {}, parent = null) {
  const n = document.createElementNS(SVGNS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}

/* Darkened variant of a band color, for text: the raw curve colors (pale
   green/yellow around 2 um) have too little contrast against the background
   to carry a label. */
function darken(color, f = 0.60) {
  const m = /^#([0-9a-f]{6})$/i.exec(color || "");
  if (!m) return "var(--ink)";
  const v = parseInt(m[1], 16);
  const d = c => Math.round(c * f).toString(16).padStart(2, "0");
  return `#${d((v >> 16) & 255)}${d((v >> 8) & 255)}${d(v & 255)}`;
}

function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

export function fmt(v, sig = 3) {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-3) {
    const e = Math.floor(Math.log10(a));
    const m = v / 10 ** e;
    return `${m.toFixed(sig - 1)}e${e}`;
  }
  return Number(v.toPrecision(sig)).toString();
}

/* ── coverage strip ──────────────────────────────────────────────────── */

export function renderCoverage(svg, curves, z, lines) {
  clear(svg);
  const W = 320, H = 64, padB = 12;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "none");
  if (!curves.length) {
    const t = el("text", { x: W / 2, y: H / 2 + 3, "text-anchor": "middle",
      fill: "var(--ink-faint)", "font-size": 9, "font-family": "var(--plotfont)" }, svg);
    t.textContent = "no bands selected";
    return;
  }
  let lo = Infinity, hi = -Infinity;
  for (const c of curves) {
    lo = Math.min(lo, c.wave_aa[0]);
    hi = Math.max(hi, c.wave_aa[c.wave_aa.length - 1]);
  }
  lo *= 0.96; hi *= 1.04;
  const x = w => (Math.log(w) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * W;
  for (const c of curves) {
    const col = c.color || bandColor(c.pivot_aa);
    let d = `M ${x(c.wave_aa[0]).toFixed(1)} ${H - padB}`;
    for (let i = 0; i < c.wave_aa.length; i++) {
      d += ` L ${x(c.wave_aa[i]).toFixed(1)} ${(H - padB - c.trans[i] * (H - padB - 6)).toFixed(1)}`;
    }
    d += ` L ${x(c.wave_aa[c.wave_aa.length - 1]).toFixed(1)} ${H - padB} Z`;
    el("path", { d, fill: col, "fill-opacity": 0.28, stroke: col,
      "stroke-opacity": 0.75, "stroke-width": 0.7 }, svg);
  }
  for (const ln of lines) {
    const w = ln.rest_wave * (1 + z);
    if (w < lo || w > hi) continue;
    const xx = x(w);
    el("line", { x1: xx, y1: 4, x2: xx, y2: H - padB,
      stroke: ln.role === "free" ? "var(--amber)" : "var(--ink-dim)",
      "stroke-width": ln.role === "free" ? 1.2 : 0.7,
      "stroke-dasharray": ln.role === "free" ? "" : "2 2" }, svg);
  }
  el("line", { x1: 0, y1: H - padB, x2: W, y2: H - padB,
    stroke: "var(--line-strong)", "stroke-width": 0.6 }, svg);
  const t0 = el("text", { x: 2, y: H - 2, fill: "var(--ink-faint)",
    "font-size": 8, "font-family": "var(--plotfont)" }, svg);
  t0.textContent = `${(lo / 1e4).toFixed(1)} µm`;
  const t1 = el("text", { x: W - 2, y: H - 2, "text-anchor": "end",
    fill: "var(--ink-faint)", "font-size": 8, "font-family": "var(--plotfont)" }, svg);
  t1.textContent = `${(hi / 1e4).toFixed(1)} µm`;
}

/* ── main fit figure ─────────────────────────────────────────────────── */

export function renderMainPlot(svg, tip, d, opts = {}) {
  // opts.print scales the margins AND the text together, so an exported
  // figure reproduced at a fraction of a page keeps its labels at body-text
  // size without them overflowing the axes.
  const K = Number(opts.fontScale) || (typeof window !== "undefined" && window.latedPrintK) || 1;
  svg.style.setProperty("--fs-k", K);   // CSS-driven label sizes follow K too

  // d: {bands:[{name,pivot,flux,err,model}], curves:[{name,pivot_aa,wave_aa,trans}],
  //     modelCurve:{wave_aa,total_uJy,continuum_uJy}, lineMarks:[{label,waveObs,free}]}
  clear(svg);
  // The DATA area is fixed and the margins scale with the type, so the
  // canvas grows with K instead of the plot being squeezed by its own
  // margins.  The top margin holds the rotated line-ID labels, which sit
  // OUTSIDE the frame so they can never collide with the model curve.
  // opts.dataWidth narrows the data area for print reproductions.
  const DW = Number(opts.dataWidth) || 660;
  const m = { l: 92*K, r: 16*K, t: 76*K, b: 66*K };
  const W = DW + m.l + m.r, H = 400 + m.t + m.b;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const iw = W - m.l - m.r, ih = H - m.t - m.b;

  const piv = d.bands.map(b => b.pivot);
  const xlo = Math.min(...piv) * 0.75, xhi = Math.max(...piv) * 1.2;
  const X = w => m.l + (w - xlo) / (xhi - xlo) * iw;

  const pos = [...d.bands.map(b => b.flux), ...d.bands.map(b => b.model),
               ...d.modelCurve.continuum_uJy].filter(v => v > 0);
  const dmax = Math.max(...pos);
  const dmin = Math.min(...d.bands.map(b => Math.abs(b.flux) || dmax));
  const ylo = Math.max(0.35 * Math.min(dmin, dmax), dmax * 1.5e-3);
  const yhi = dmax * 30;
  const Y = v => m.t + ih - (Math.log10(Math.max(v, ylo * 0.5)) - Math.log10(ylo))
                 / (Math.log10(yhi) - Math.log10(ylo)) * ih;

  // frame + grid
  el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "none",
    stroke: "var(--line-strong)", "stroke-width": 1 }, svg);
  const dec0 = Math.ceil(Math.log10(ylo)), dec1 = Math.floor(Math.log10(yhi));
  for (let e = dec0; e <= dec1; e++) {
    const y = Y(10 ** e);
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y, class: "gridline" }, svg);
    el("line", { x1: m.l - 6*K, y1: y, x2: m.l, y2: y,
      stroke: "var(--line-strong)", "stroke-width": K }, svg);
    const t = el("text", { x: m.l - 9*K, y: y + 4*K, "text-anchor": "end",
      fill: "var(--ink-dim)", "font-size": 17*K,
      "font-family": "var(--plotfont)" }, svg);
    t.textContent = e >= -1 && e <= 3 ? String(10 ** e) : `1e${e}`;
  }
  // minor log ticks between the decades
  for (let e = dec0 - 1; e <= dec1; e++) {
    for (let f = 2; f <= 9; f++) {
      const v = f * 10 ** e;
      if (v <= ylo || v >= yhi) continue;
      const y = Y(v);
      el("line", { x1: m.l - 3.5*K, y1: y, x2: m.l, y2: y,
        stroke: "var(--line-strong)", "stroke-width": 0.7*K }, svg);
    }
  }
  const umTicks = [];
  const lo_um = xlo / 1e4, hi_um = xhi / 1e4;
  const step = hi_um - lo_um > 2.4 ? 1.0 : 0.5;
  for (let u = Math.ceil(lo_um / step) * step; u <= hi_um; u += step) umTicks.push(u);
  for (const u of umTicks) {
    const x = X(u * 1e4);
    el("line", { x1: x, y1: m.t + ih, x2: x, y2: m.t + ih + 5*K,
      stroke: "var(--line-strong)", "stroke-width": K }, svg);
    const t = el("text", { x, y: m.t + ih + 24*K, "text-anchor": "middle",
      fill: "var(--ink-dim)", "font-size": 17*K, "font-family": "var(--plotfont)" }, svg);
    t.textContent = u.toFixed(step < 1 ? 1 : 0);
  }
  // minor wavelength ticks
  const mstep = step / 5;
  for (let u = Math.ceil(lo_um / mstep) * mstep; u <= hi_um; u += mstep) {
    if (Math.abs(u / step - Math.round(u / step)) < 1e-6) continue;
    const x = X(u * 1e4);
    el("line", { x1: x, y1: m.t + ih, x2: x, y2: m.t + ih + 3*K,
      stroke: "var(--line-strong)", "stroke-width": 0.7*K }, svg);
  }
  const xl = el("text", { x: m.l + iw / 2, y: H - 12*K, "text-anchor": "middle",
    fill: "var(--ink)", "font-size": 19*K, "font-family": "var(--plotfont)" }, svg);
  xl.textContent = "Observed wavelength  [µm]";
  // "f" italic with a true subscript nu.  Centred MANUALLY (anchor start +
  // measured length): text-anchor:middle on a multi-tspan text is mis-handled
  // by SVG-to-PDF converters, which centre each tspan about the cursor and
  // pile the fragments up, so the exported figure must not rely on it.
  const yl = el("text", { x: 24*K, y: m.t + ih / 2, fill: "var(--ink)",
    "font-size": 19*K, "font-family": "var(--plotfont)" }, svg);
  el("tspan", {}, yl).textContent = "Flux density ";
  el("tspan", { "font-style": "italic" }, yl).textContent = "f";
  el("tspan", { "baseline-shift": "sub", "font-size": "0.72em" }, yl).textContent = "\u03BD";
  el("tspan", {}, yl).textContent = ` [${d.yUnit || "\u00B5Jy"}]`;
  const ylLen = (yl.getComputedTextLength ? yl.getComputedTextLength() : 220*K);
  const ylY = m.t + ih / 2 + ylLen / 2;      // start so the midpoint sits at mid-axis
  yl.setAttribute("y", ylY);
  yl.setAttribute("transform", `rotate(-90 ${24*K} ${ylY})`);

  // filter curves along the floor (lower ~22%)
  for (const c of d.curves) {
    const col = c.color || bandColor(c.pivot_aa);
    let dd = "", started = false;
    for (let i = 0; i < c.wave_aa.length; i++) {
      const w = c.wave_aa[i];
      if (w < xlo || w > xhi) continue;
      const x = X(w), y = m.t + ih - c.trans[i] * ih * 0.22;
      dd += started ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${m.t + ih}`
            + ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
      started = true;
    }
    if (!started) continue;
    dd += ` L ${X(Math.min(c.wave_aa[c.wave_aa.length - 1], xhi)).toFixed(1)} ${m.t + ih} Z`;
    el("path", { d: dd, fill: col, "fill-opacity": 0.13, stroke: col,
      "stroke-opacity": 0.55, "stroke-width": 0.8 }, svg);
  }
  for (const b of d.bands) {
    const t = el("text", { x: X(b.pivot), y: m.t + ih - 8*K, "text-anchor": "middle",
      fill: darken(b.color || bandColor(b.pivot)), "font-size": 15*K,
      "font-weight": 700, "font-family": "var(--plotfont)" }, svg);
    t.textContent = b.name;
  }

  // line markers: every line keeps its dashed tick.  Labels are rotated and
  // sit ABOVE the frame, in the top margin, so they never overlap the model:
  // same-label neighbours (a doublet) share one label at their mean position,
  // crowded labels are nudged apart rather than dropped (a thin connector
  // re-attaches a nudged label to its line), and only labels closer than
  // half a pitch to an already-kept one are dropped (free lines first).
  // Marks flagged `hot` (the reported ratio's numerator complex) are drawn
  // in the highlight color.
  const marks = d.lineMarks
    .filter(lm => lm.waveObs >= xlo && lm.waveObs <= xhi)
    .map(lm => ({ ...lm, x: X(lm.waveObs) }))
    .sort((a, b) => a.x - b.x);
  for (const lm of marks)
    el("line", { x1: lm.x, y1: m.t, x2: lm.x, y2: m.t + ih * 0.72,
      class: "line-marker" + (lm.hot ? " hot" : "") }, svg);
  const sep = 17*K;                     // label pitch (label height + air)
  const groups = [];
  for (const lm of marks) {
    const g = groups[groups.length - 1];
    if (g && g.label === lm.label && lm.x - g.marks[g.marks.length - 1].x < 1.5 * sep)
      g.marks.push(lm);
    else groups.push({ label: lm.label, marks: [lm] });
  }
  const cands = groups.map(g => ({
    label: g.label,
    x: g.marks.reduce((a, mk) => a + mk.x, 0) / g.marks.length,
    free: g.marks.some(mk => mk.free),
    hot: g.marks.some(mk => mk.hot),
  }));
  const accepted = [];
  for (const wantFree of [true, false]) {
    for (const c of cands) {
      if (c.free !== wantFree) continue;
      if (accepted.some(a => Math.abs(a.x - c.x) < 0.5 * sep)) continue;
      accepted.push(c);
    }
  }
  accepted.sort((a, b) => a.x - b.x);
  // 1D squeeze: runs of overlapping labels spread at `sep` about the mean
  // of their desired positions, clamped to the frame
  const clusters = [];
  for (const c of accepted) {
    let cl = { items: [c], sum: c.x };
    clusters.push(cl);
    while (clusters.length > 1) {
      const prev = clusters[clusters.length - 2];
      const prevRight = prev.sum / prev.items.length
        + (prev.items.length - 1) / 2 * sep;
      const curLeft = cl.sum / cl.items.length
        - (cl.items.length - 1) / 2 * sep;
      if (curLeft - prevRight >= sep) break;
      prev.items.push(...cl.items);
      prev.sum += cl.sum;
      clusters.pop();
      cl = prev;
    }
  }
  for (const cl of clusters) {
    const n = cl.items.length;
    let c0 = cl.sum / n - (n - 1) / 2 * sep;
    c0 = Math.min(Math.max(c0, m.l + 4), m.l + iw - 4 - (n - 1) * sep);
    cl.items.forEach((c, idx) => {
      const lx = c0 + idx * sep;
      if (Math.abs(lx - c.x) > 2)
        el("line", { x1: lx, y1: m.t - 5*K, x2: c.x, y2: m.t,
          stroke: c.hot ? "var(--rose)" : "var(--ink-faint)",
          "stroke-width": 0.8*K }, svg);
      // anchor start, reading bottom-to-top; +0.28 em centres the glyph
      // column on the marker line
      const ax = lx + 4.5*K, ay = m.t - 6*K;
      const t = el("text", { x: ax, y: ay,
        class: "line-marker-label" + (c.hot ? " hot" : ""),
        "text-anchor": "start",
        transform: `rotate(-90 ${ax} ${ay})` }, svg);
      t.textContent = c.label;
    });
  }

  // model curve + continuum
  const path = key => {
    let dd = "", started = false;
    for (let i = 0; i < d.modelCurve.wave_aa.length; i++) {
      const w = d.modelCurve.wave_aa[i];
      if (w < xlo || w > xhi) continue;
      const v = d.modelCurve[key][i];
      const x = X(w), y = Math.max(m.t + 1, Y(v));
      dd += started ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${y.toFixed(1)}`;
      started = true;
    }
    return dd;
  };
  el("path", { d: path("continuum_uJy"), class: "cont-path" }, svg);
  el("path", { d: path("total_uJy"), class: "model-path" }, svg);
  // re-draw the model over each hot line in the highlight color: the display
  // Gaussians have sigma ~ 5e-4 of the observed wavelength, so a +-0.4%
  // window (~8 sigma) brackets one peak, and the above-continuum threshold
  // keeps the continuum between neighbouring peaks in the model color
  const hotWins = d.lineMarks.filter(lm => lm.hot)
    .map(lm => [lm.waveObs * (1 - 4e-3), lm.waveObs * (1 + 4e-3)]);
  if (hotWins.length) {
    let dd = "", started = false;
    for (let i = 0; i < d.modelCurve.wave_aa.length; i++) {
      const w = d.modelCurve.wave_aa[i];
      const on = w >= xlo && w <= xhi
        && hotWins.some(([a, b]) => w >= a && w <= b)
        && d.modelCurve.total_uJy[i] > d.modelCurve.continuum_uJy[i] * 1.02;
      if (!on) { started = false; continue; }
      const x = X(w), y = Math.max(m.t + 1, Y(d.modelCurve.total_uJy[i]));
      dd += `${started ? " L" : " M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      started = true;
    }
    if (dd) el("path", { d: dd, class: "model-path hot" }, svg);
  }

  // model-through-band squares + photometry
  for (const b of d.bands) {
    const x = X(b.pivot), y = Y(b.model);
    el("rect", { x: x - 5, y: y - 5, width: 10, height: 10, class: "band-square" }, svg);
  }
  for (const b of d.bands) {
    const x = X(b.pivot);
    const yv = Y(Math.max(b.flux, ylo * 0.5));
    const ylo_e = Y(Math.max(b.flux - b.err, ylo * 0.5));
    const yhi_e = Y(Math.max(b.flux + b.err, ylo * 0.5));
    el("line", { x1: x, y1: ylo_e, x2: x, y2: yhi_e, class: "datum", "stroke-width": 1.2 }, svg);
    el("line", { x1: x - 3.5, y1: ylo_e, x2: x + 3.5, y2: ylo_e, class: "datum" }, svg);
    el("line", { x1: x - 3.5, y1: yhi_e, x2: x + 3.5, y2: yhi_e, class: "datum" }, svg);
    el("circle", { cx: x, cy: yv, r: 4, class: "datum-dot" }, svg);
  }

  // legend (top-right; the line-ID labels live above the frame, so the
  // corner is free)
  const lg = el("g", { transform: `translate(${W - m.r - 212*K}, ${m.t + 20*K})` }, svg);
  const legend = [
    ["circle", "Observed photometry", "var(--ink)"],
    ["square", "Model photometry", "var(--amber)"],
    ["line", "Best-fit model", "var(--cyan)"],
  ];
  legend.forEach(([kind, label, col], i) => {
    const y = i * 25*K;
    if (kind === "circle") el("circle", { cx: 6*K, cy: y, r: 4.5*K, fill: col }, lg);
    if (kind === "square") el("rect", { x: 1*K, y: y - 5*K, width: 10*K, height: 10*K,
      fill: "none", stroke: col, "stroke-width": 1.6 }, lg);
    if (kind === "line") el("line", { x1: 0, y1: y, x2: 14*K, y2: y, stroke: col,
      "stroke-width": 2 }, lg);
    const t = el("text", { x: 20*K, y: y + 5*K, fill: "var(--ink-dim)",
      "font-size": 16*K, "font-family": "var(--plotfont)" }, lg);
    t.textContent = label;
  });

  // hover tooltip on nearest band
  svg.onmousemove = ev => {
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = null, bd = 40;
    for (const b of d.bands) {
      const dx = Math.abs(X(b.pivot) - p.x);
      if (dx < bd) { bd = dx; best = b; }
    }
    if (!best) { tip.hidden = true; return; }
    tip.hidden = false;
    tip.innerHTML = `<span class="tip-band">${best.name}</span><br>` +
      `<span class="tip-dim">observed</span> ${fmt(best.flux)} ± ${fmt(best.err)} µJy<br>` +
      `<span class="tip-dim">model</span> ${fmt(best.model)} µJy`;
    const host = svg.parentElement.getBoundingClientRect();
    tip.style.left = `${Math.min(ev.clientX - host.left + 14, host.width - 180)}px`;
    tip.style.top = `${ev.clientY - host.top - 10}px`;
  };
  svg.onmouseleave = () => { tip.hidden = true; };
}

/* ── posterior corner plot (publication style) ───────────────────────── */

/* One line of a stacked axis label, with true raised exponents: "^{...}"
   runs become smaller tspans of ordinary glyphs shifted up.  (Unicode
   superscript glyphs are avoided on purpose: Helvetica lacks most of that
   block, so a string like ×10⁻¹⁸ takes its 8 from a fallback font and the
   digits visibly clash.)  The line is one start-anchored chunk, centred
   manually about cx from measured widths, which SVG-to-PDF converters
   reproduce exactly. */
function richLine(host, str, cx, dyLine, size, attrs = {}) {
  const parts = [];
  const re = /\^\{([^}]*)\}/g;
  let last = 0, mm;
  while ((mm = re.exec(str)) !== null) {
    if (mm.index > last) parts.push([str.slice(last, mm.index), false]);
    if (mm[1]) parts.push([mm[1], true]);
    last = re.lastIndex;
  }
  if (last < str.length) parts.push([str.slice(last), false]);
  const supSize = 0.72 * size, rise = 0.38 * size;
  const spans = [];
  let up = false;
  parts.forEach(([txt, isSup], n) => {
    const a = { ...attrs, "text-anchor": "start",
      "font-size": (isSup ? supSize : size).toFixed(2) };
    let dy = n === 0 ? dyLine : 0;
    if (isSup && !up) dy -= rise;
    else if (!isSup && up) dy += rise;
    if (dy) a.dy = dy.toFixed(2);
    if (n === 0) a.x = cx;           // provisional; re-centred below
    const t = el("tspan", a, host);
    t.textContent = txt;
    spans.push(t);
    up = isSup;
  });
  if (up) el("tspan", { dy: rise.toFixed(2) }, host);   // restore baseline
  const w = spans.reduce((acc, s2) => acc
    + (s2.getComputedTextLength ? s2.getComputedTextLength() : 0), 0);
  spans[0].setAttribute("x", (cx - w / 2).toFixed(1));
}

/* marching-squares case table: which edge pairs to join (b,r,t,l). */
const MS_TABLE = { 1: [["l", "b"]], 2: [["b", "r"]], 3: [["l", "r"]],
  4: [["r", "t"]], 5: [["l", "t"], ["b", "r"]], 6: [["b", "t"]],
  7: [["l", "t"]], 8: [["t", "l"]], 9: [["t", "b"]],
  10: [["t", "r"], ["l", "b"]], 11: [["t", "r"]], 12: [["r", "l"]],
  13: [["r", "b"]], 14: [["b", "l"]] };

function marchingSquares(g, nx, ny, level, x0, y0, dx, dy) {
  let d = "";
  const val = (i, j) => g[j * nx + i];
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const v00 = val(i, j), v10 = val(i + 1, j),
            v01 = val(i, j + 1), v11 = val(i + 1, j + 1);
      const idx = (v00 > level ? 1 : 0) | (v10 > level ? 2 : 0) |
                  (v11 > level ? 4 : 0) | (v01 > level ? 8 : 0);
      if (idx === 0 || idx === 15) continue;
      const f = (a, b) => (b === a ? 0.5 : (level - a) / (b - a));
      const P = {
        b: [x0 + (i + f(v00, v10)) * dx, y0 + j * dy],
        r: [x0 + (i + 1) * dx, y0 + (j + f(v10, v11)) * dy],
        t: [x0 + (i + f(v01, v11)) * dx, y0 + (j + 1) * dy],
        l: [x0 + i * dx, y0 + (j + f(v00, v01)) * dy],
      };
      for (const [a, b] of MS_TABLE[idx]) {
        d += `M ${P[a][0].toFixed(1)} ${P[a][1].toFixed(1)} ` +
             `L ${P[b][0].toFixed(1)} ${P[b][1].toFixed(1)} `;
      }
    }
  }
  return d;
}

function quantile(sorted, q) {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

/* Round-number axis ticks: 2-3 interior ticks on a 1/2/2.5/5 x 10^k step,
   in the DISPLAY scaling (v*sc), never rotated.  Steps are tried coarse to
   fine; a step yielding too many ticks is thinned by twos (keeping round
   values and even spacing), and a candidate is accepted only when adjacent
   labels stay clear of each other across axisPx.  Returns unscaled values
   plus their formatted labels (decimals fixed by the generating step). */
function niceTicks(mn, mx, sc, fontPx, axisPx) {
  const lo = mn * sc, hi = mx * sc, span = hi - lo;
  if (!(span > 0)) return { vals: [], labels: [] };
  const inset = 0.04 * span;
  const kmag = Math.floor(Math.log10(span));
  const steps = [];
  for (const k of [kmag, kmag - 1, kmag - 2])
    for (const m of [5, 2.5, 2, 1]) steps.push(m * Math.pow(10, k));
  steps.sort((a, b) => b - a);
  // Helvetica advance widths: digits 0.556 em, "." 0.278, minus 0.584
  const est = s => [...s].reduce((a, c) =>
    a + (c === "." ? 0.278 : c === "−" ? 0.584 : 0.556), 0) * fontPx;
  const fmtOne = (v, dec) => (Math.abs(v) < 1e-12 ? 0 : v).toFixed(dec).replace("-", "−");
  for (const stp of steps) {
    if (span / stp > 25) break;               // finer would only re-thin
    const isHalf = Math.abs(stp / Math.pow(10, Math.floor(Math.log10(stp) + 1e-9)) - 2.5) < 1e-9;
    const dec = Math.max(0, -Math.floor(Math.log10(stp) + 1e-9)) + (isHalf ? 1 : 0);
    let vals = [];
    for (let v = Math.ceil((lo + inset) / stp - 1e-9) * stp;
         v <= hi - inset + 1e-9 * span; v += stp) vals.push(v);
    while (vals.length > 3) vals = vals.filter((_, n) => n % 2 === 0);
    if (vals.length === 3) {
      // drop the middle tick if three labels would crowd each other
      const need = Math.max(...vals.map(v => est(fmtOne(v, dec)))) + 0.4 * fontPx;
      if ((vals[1] - vals[0]) / span * axisPx < need)
        vals = [vals[0], vals[2]];
    }
    if (vals.length < 2) continue;
    const need = Math.max(...vals.map(v => est(fmtOne(v, dec)))) + 0.4 * fontPx;
    if ((vals[1] - vals[0]) / span * axisPx < need) continue;
    return { vals: vals.map(v => v / sc),
      labels: vals.map(v => fmtOne(v, dec)) };
  }
  // degenerate range: fall back to two 2-significant-figure quantile ticks
  const vals = [lo + 0.25 * span, lo + 0.75 * span];
  return { vals: vals.map(v => v / sc),
    labels: vals.map(v => Number(v.toPrecision(2)).toString().replace("-", "−")) };
}

export function renderCorner(svg, params, inset, opts = {}) {
  // opts.print scales the margins AND the text together, so an exported
  // figure reproduced at a fraction of a page keeps its labels at body-text
  // size without them overflowing the axes.
  const K = Number(opts.fontScale) || (typeof window !== "undefined" && window.latedPrintK) || 1;
  svg.style.setProperty("--fs-k", K);   // CSS-driven label sizes follow K too

  // params: [{label, values: number[], best: number, unit: string}]
  // inset (optional): the reported ratio, drawn in the empty top-right
  //   corner: {label, values, best, status, p975}
  clear(svg);
  const k = params.length;
  // Panels keep their native size; margins and gaps carry the scaled
  // text, and the canvas absorbs the difference.
  const mL = 120*K, mB = 86*K, mT = 52*K, mR = 18*K, gap = 16*K;
  const W = 4 * 124 + 3 * gap + mL + mR;
  const H = 4 * 119 + 3 * gap + mT + mB;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const cw = (W - mL - mR - gap * (k - 1)) / k;
  const ch = (H - mT - mB - gap * (k - 1)) / k;

  const prep = params.map(p => {
    let mn = Infinity, mx = -Infinity;
    for (const v of p.values) { if (v < mn) mn = v; if (v > mx) mx = v; }
    const pad = 0.05 * (mx - mn || Math.abs(mx) || 1);
    mn -= pad; mx += pad;
    const maxabs = Math.max(Math.abs(mn), Math.abs(mx));
    let e = maxabs > 0 ? Math.floor(Math.log10(maxabs)) : 0;
    if (e >= -2 && e <= 3) e = 0;
    const sc = Math.pow(10, -e);
    const sorted = [...p.values].sort((a, b) => a - b);
    return { ...p, mn, mx, sc,
      scaleLabel: e === 0 ? "" : `×10^{${String(e).replace("-", "−")}}`,
      q16: quantile(sorted, 0.16), q50: quantile(sorted, 0.50),
      q84: quantile(sorted, 0.84) };
  });

  const cellX = j => mL + j * (cw + gap);
  const cellY = i => mT + i * (ch + gap);
  const xpos = (pj, v, j) => cellX(j) + (v - pj.mn) / (pj.mx - pj.mn) * cw;
  const ypos = (pi, v, i) => cellY(i) + ch - (v - pi.mn) / (pi.mx - pi.mn) * ch;
  // one tick set per parameter, shared by its column and its row
  const tickFont = 15*K;
  for (const p of prep) {
    const t = niceTicks(p.mn, p.mx, p.sc, tickFont, cw);
    p.ticks = t.vals;
    p.tickLabels = t.labels;
    p.unitDisp = (p.unit || "").replace(/ /g, "\u2009");  // thin spaces keep the unit inside its column
  }
  const NPT = params[0].values.length;

  for (let i = 0; i < k; i++) {
    for (let j = 0; j <= i; j++) {
      const pi = prep[i], pj = prep[j];
      const x0 = cellX(j), y0 = cellY(i);

      if (i === j) {
        // ── diagonal: gapless step histogram + median ± sigma title ──
        const nb = 28;
        const hist = new Array(nb).fill(0);
        for (const v of pi.values) {
          const b = Math.min(nb - 1, Math.max(0,
            Math.floor((v - pi.mn) / (pi.mx - pi.mn) * nb)));
          hist[b]++;
        }
        const hmax = Math.max(...hist) || 1;
        const bw = cw / nb;
        let d = `M ${x0.toFixed(1)} ${(y0 + ch).toFixed(1)}`;
        for (let b = 0; b < nb; b++) {
          const hh = hist[b] / hmax * (ch - 8);
          const yTop = y0 + ch - hh;
          d += ` L ${(x0 + b * bw).toFixed(1)} ${yTop.toFixed(1)}` +
               ` L ${(x0 + (b + 1) * bw).toFixed(1)} ${yTop.toFixed(1)}`;
        }
        d += ` L ${(x0 + cw).toFixed(1)} ${(y0 + ch).toFixed(1)} Z`;
        el("path", { d, class: "corner-bar", stroke: "var(--amber)",
          "stroke-width": 1*K }, svg);
        // 16/50/84 markers
        for (const q of [pi.q16, pi.q50, pi.q84]) {
          const qx = xpos(pj, q, j);
          if (qx > x0 && qx < x0 + cw)
            el("line", { x1: qx, y1: y0 + 3, x2: qx, y2: y0 + ch - 1,
              stroke: "var(--ink-dim)", "stroke-width": 0.8*K,
              "stroke-dasharray": `${3*K} ${3*K}` }, svg);
        }
        if (isFinite(pi.best)) {
          const bx = xpos(pj, pi.best, j);
          if (bx >= x0 && bx <= x0 + cw)
            el("line", { x1: bx, y1: y0 + 2, x2: bx, y2: y0 + ch - 1,
              class: "corner-best", "stroke-width": 1.3*K }, svg);
        }
        // title: median with stacked +upper / -lower errors; decimals MATCH
        // the errors' (two significant figures): 2.00 +0.12 -0.30, never
        // 2 +0.12 -0.3.  A one-line title may overhang its column into the
        // flanking gap bands (always empty); only titles wider than that
        // split onto two lines.
        const s = pi.sc;
        const upv = (pi.q84 - pi.q50) * s;
        const lov = (pi.q50 - pi.q16) * s;
        const errDec = e2 => (e2 > 0)
          ? Math.max(0, 1 - Math.floor(Math.log10(e2))) : 0;
        const dec = Math.max(errDec(upv), errDec(lov));
        const medStr = (pi.q50 * s).toFixed(dec);
        const supStr = `+${upv.toFixed(dec)}`;
        const subStr = `\u2212${lov.toFixed(dec)}`;
        const titleSize = 15.5*K, errSize = 12*K;
        // glyphs are ~0.54 em wide on average; a one-line title may overhang
        // by at most one gap band per side (the bands are always empty)
        const wOneLine = (pi.label.length + 3 + medStr.length) * titleSize * 0.54
          + supStr.length * errSize * 0.58;
        const twoLine = wOneLine > cw + 2 * gap;
        const cxm = x0 + cw / 2;
        if (twoLine) {
          const lt = el("text", { x: cxm, y: y0 - 32*K,
            "text-anchor": "middle", class: "corner-title" }, svg);
          lt.textContent = pi.label;
        }
        // anchor start + measured centring: text-anchor on a multi-tspan text
        // is centred per-fragment by SVG-to-PDF converters, so it cannot be
        // used for the exported figure.
        const tt = el("text", { x: cxm, y: y0 - 12*K,
          class: "corner-title" }, svg);
        const main = el("tspan", {}, tt);
        main.textContent = twoLine ? `${medStr}` : `${pi.label} = ${medStr}`;
        const supT = el("tspan", { dy: -7*K, "font-size": errSize }, tt);
        supT.textContent = supStr;
        const subT = el("tspan", { dy: 13*K, "font-size": errSize }, tt);
        subT.textContent = subStr;
        el("tspan", { dy: -6*K }, tt);   // restore the baseline
        // measure the fragments, centre the whole title, and start the sub
        // at an ABSOLUTE x equal to the sup's start: a dx back-shift from an
        // estimated width leaves the two visibly misaligned in converters.
        const mW = main.getComputedTextLength ? main.getComputedTextLength() : 0;
        const sW = Math.max(
          supT.getComputedTextLength ? supT.getComputedTextLength() : 0,
          subT.getComputedTextLength ? subT.getComputedTextLength() : 0);
        const tx0 = cxm - (mW + sW) / 2;
        tt.setAttribute("x", tx0.toFixed(1));
        subT.setAttribute("x", (tx0 + mW).toFixed(1));
      } else {
        // ── off-diagonal: smoothed density, 1σ/2σ contours, outliers ──
        const N = 42;
        const grid = new Float64Array(N * N);
        const fx = v => (v - pj.mn) / (pj.mx - pj.mn);
        const fy = v => (pi.mx - v) / (pi.mx - pi.mn);   // screen-down
        const binOf = n => {
          const bi = Math.min(N - 1, Math.max(0, Math.floor(fx(pj.values[n]) * N)));
          const bj = Math.min(N - 1, Math.max(0, Math.floor(fy(pi.values[n]) * N)));
          return bj * N + bi;
        };
        for (let n = 0; n < NPT; n++) grid[binOf(n)]++;
        // separable gaussian smooth (sigma ~ 1 bin).  NOTE: must not be
        // named K -- that shadows the font-scale K and silently turns every
        // later `*K` in this block into NaN geometry (invisible cross-hairs
        // and outlier dots, default-width contours).
        const KERN = [0.054, 0.244, 0.404, 0.244, 0.054];
        const tmp = new Float64Array(N * N);
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          let s = 0;
          for (let m = -2; m <= 2; m++) {
            const cc = Math.min(N - 1, Math.max(0, c + m));
            s += KERN[m + 2] * grid[r * N + cc];
          }
          tmp[r * N + c] = s;
        }
        const sm = new Float64Array(N * N);
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          let s = 0;
          for (let m = -2; m <= 2; m++) {
            const rr = Math.min(N - 1, Math.max(0, r + m));
            s += KERN[m + 2] * tmp[rr * N + c];
          }
          sm[r * N + c] = s;
        }
        // mass-fraction levels: 1σ encloses 39.3%, 2σ encloses 86.5%
        const sortedD = [...sm].sort((a, b) => b - a);
        const total = sortedD.reduce((a, b) => a + b, 0);
        const levelFor = frac => {
          let cum = 0;
          for (const v of sortedD) { cum += v; if (cum >= frac * total) return v; }
          return sortedD[sortedD.length - 1];
        };
        const l1 = levelFor(0.393), l2 = levelFor(0.865);
        const dx = cw / (N - 1), dy = ch / (N - 1);
        // soft fill inside 2σ and 1σ (node rects, smoothed by opacity)
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          const v = sm[r * N + c];
          if (v <= l2) continue;
          el("rect", { x: (x0 + c * dx - dx / 2).toFixed(1),
            y: (y0 + r * dy - dy / 2).toFixed(1),
            width: (dx + 0.3).toFixed(1), height: (dy + 0.3).toFixed(1),
            fill: "var(--cyan)", opacity: v > l1 ? 0.22 : 0.10 }, svg);
        }
        el("path", { d: marchingSquares(sm, N, N, l2, x0, y0, dx, dy),
          stroke: "var(--cyan)", "stroke-width": 1.0*K, fill: "none",
          opacity: 0.75 }, svg);
        el("path", { d: marchingSquares(sm, N, N, l1, x0, y0, dx, dy),
          stroke: "var(--cyan)", "stroke-width": 1.5*K, fill: "none" }, svg);
        // outliers beyond the 2σ contour
        for (let n = 0; n < NPT; n++) {
          if (sm[binOf(n)] > l2) continue;
          el("circle", { cx: xpos(pj, pj.values[n], j).toFixed(1),
            cy: ypos(pi, pi.values[n], i).toFixed(1), r: 1.2*K,
            class: "corner-dot" }, svg);
        }
        if (isFinite(pi.best) && isFinite(pj.best)) {
          const bx = xpos(pj, pj.best, j), by = ypos(pi, pi.best, i);
          el("line", { x1: bx - 4.5*K, y1: by, x2: bx + 4.5*K, y2: by,
            class: "corner-best" }, svg);
          el("line", { x1: bx, y1: by - 4.5*K, x2: bx, y2: by + 4.5*K,
            class: "corner-best" }, svg);
        }
      }

      el("rect", { x: x0, y: y0, width: cw, height: ch,
        class: "corner-frame" }, svg);

      // ── ticks and stacked axis labels (round-number ticks, never rotated) ──
      if (i === k - 1) {
        pj.ticks.forEach((v, n) => {
          const tx = xpos(pj, v, j);
          el("line", { x1: tx, y1: y0 + ch, x2: tx, y2: y0 + ch + 4*K,
            stroke: "var(--line-strong)", "stroke-width": K }, svg);
          const t = el("text", { x: tx, y: y0 + ch + 20*K,
            "text-anchor": "middle", class: "corner-tick" }, svg);
          t.textContent = pj.tickLabels[n];
        });
        const lx = el("text", { x: x0 + cw / 2, y: y0 + ch + 44*K,
          "text-anchor": "middle", class: "corner-label" }, svg);
        const l1t = el("tspan", { x: x0 + cw / 2 }, lx);
        l1t.textContent = pj.label;
        // scale and unit on their own lines so neighbours never collide
        if (pj.scaleLabel)
          richLine(lx, pj.scaleLabel, x0 + cw / 2, 18*K, 13*K,
            { fill: "var(--ink-dim)", "font-weight": 400 });
        if (pj.unit)
          richLine(lx, pj.unitDisp, x0 + cw / 2, (pj.scaleLabel ? 16 : 18)*K,
            12.5*K, { fill: "var(--ink-dim)", "font-weight": 400 });
      }
      if (j === 0 && i > 0) {
        pi.ticks.forEach((v, n) => {
          const ty = ypos(pi, v, i);
          el("line", { x1: mL - 4*K, y1: ty, x2: mL, y2: ty,
            stroke: "var(--line-strong)", "stroke-width": K }, svg);
          const t = el("text", { x: mL - 8*K, y: ty + 5*K,
            "text-anchor": "end", class: "corner-tick" }, svg);
          t.textContent = pi.tickLabels[n];
        });
        // the rotated stack tracks the margin: its lines advance TOWARD the
        // axis, so the first baseline sits a fixed distance inside mL
        const cy = y0 + ch / 2;
        const sx = 34*K;
        const ly = el("text", { x: sx, y: cy, "text-anchor": "middle",
          class: "corner-label", transform: `rotate(-90 ${sx} ${cy})` }, svg);
        const l1t = el("tspan", { x: sx }, ly);
        l1t.textContent = pi.label;
        if (pi.scaleLabel)
          richLine(ly, pi.scaleLabel, sx, 18*K, 13*K,
            { fill: "var(--ink-dim)", "font-weight": 400 });
        if (pi.unit)
          richLine(ly, pi.unitDisp, sx, (pi.scaleLabel ? 16 : 18)*K,
            12.5*K, { fill: "var(--ink-dim)", "font-weight": 400 });
      }
    }
  }

  /* ── ratio histogram inset (top-right, always-empty corner) ── */
  if (inset && inset.values && inset.values.length > 9 && k >= 2) {
    const iw = k >= 4 ? cw * 1.5 + gap * 0.5 : cw;
    const ih2 = ch;
    const ix1 = cellX(k - 1) + cw;
    const ix0 = ix1 - iw;
    const iy0 = mT;
    const vals = inset.values;
    const sortedV = [...vals].sort((a, b) => a - b);
    // x-range from 0 (a ratio) to just past the bulk of the draws
    let mx = Math.min(Math.max(...vals), quantile(sortedV, 0.995) * 1.35);
    if (inset.status === "upper_limit") mx = Math.max(mx, inset.p975 * 1.25);
    if (!(mx > 0)) mx = 1;
    const xr = v => ix0 + Math.min(v, mx) / mx * iw;
    const nb = 26;
    const hist = new Array(nb).fill(0);
    for (const v of vals) {
      const b = Math.min(nb - 1, Math.max(0, Math.floor(v / mx * nb)));
      hist[b]++;
    }
    const hmax = Math.max(...hist) || 1;
    const bw = iw / nb;
    if (inset.status === "upper_limit") {
      // the 2-sigma allowed range, from 0 up to the 97.5th percentile
      el("rect", { x: ix0, y: iy0, width: (xr(inset.p975) - ix0).toFixed(1),
        height: ih2, fill: "var(--rose)", opacity: 0.07 }, svg);
    }
    let d = `M ${ix0.toFixed(1)} ${(iy0 + ih2).toFixed(1)}`;
    for (let b = 0; b < nb; b++) {
      const hh = hist[b] / hmax * (ih2 - 8);
      const yTop = iy0 + ih2 - hh;
      d += ` L ${(ix0 + b * bw).toFixed(1)} ${yTop.toFixed(1)}` +
           ` L ${(ix0 + (b + 1) * bw).toFixed(1)} ${yTop.toFixed(1)}`;
    }
    d += ` L ${(ix0 + iw).toFixed(1)} ${(iy0 + ih2).toFixed(1)} Z`;
    el("path", { d, class: "corner-bar", stroke: "var(--amber)",
      "stroke-width": 1*K }, svg);
    const disp = inset.disp || {};
    const tt = el("text", { x: ix1, y: iy0 - 12*K, "text-anchor": "end",
      class: "corner-title" }, svg);
    if (inset.status === "upper_limit") {
      // 2-sigma bound solid, 1-sigma bound dashed; no 16/50/84 quantiles
      const bx = xr(inset.p975);
      el("line", { x1: bx, y1: iy0 + 2, x2: bx, y2: iy0 + ih2 - 1,
        stroke: "var(--rose)", "stroke-width": 1.5*K }, svg);
      if (isFinite(inset.p84)) {
        const b1 = xr(inset.p84);
        el("line", { x1: b1, y1: iy0 + 2, x2: b1, y2: iy0 + ih2 - 1,
          stroke: "var(--rose)", "stroke-width": 1.1*K,
          "stroke-dasharray": `${5*K} ${4*K}` }, svg);
      }
      tt.setAttribute("fill", "var(--rose)");
      tt.textContent = `${inset.label} < ${disp.lim} (2\u03c3)`;
    } else {
      for (const q of [0.16, 0.5, 0.84]) {
        const qx = xr(quantile(sortedV, q));
        el("line", { x1: qx, y1: iy0 + 3, x2: qx, y2: iy0 + ih2 - 1,
          stroke: "var(--ink-dim)", "stroke-width": 0.8*K,
          "stroke-dasharray": `${3*K} ${3*K}` }, svg);
      }
      if (isFinite(inset.best)) {
        const bx = xr(inset.best);
        el("line", { x1: bx, y1: iy0 + 2, x2: bx, y2: iy0 + ih2 - 1,
          class: "corner-best", "stroke-width": 1.3*K }, svg);
      }
      // same stacked ^{+up}_{-lo} format as the diagonal titles, from the
      // SAME strings the verdict card shows
      const main = el("tspan", {}, tt);
      main.textContent = `${inset.label} = ${disp.med}`;
      const errSize = 12*K;
      const supT = el("tspan", { dy: -7*K, "font-size": errSize }, tt);
      supT.textContent = disp.up;
      const subT = el("tspan", { dy: 13*K, "font-size": errSize }, tt);
      subT.textContent = disp.lo;
      el("tspan", { dy: -6*K }, tt);
      // converter-safe right alignment; the sub starts at an ABSOLUTE x
      // equal to the sup's start (see the diagonal-title note)
      tt.setAttribute("text-anchor", "start");
      const mW = main.getComputedTextLength ? main.getComputedTextLength() : 0;
      const sW = Math.max(
        supT.getComputedTextLength ? supT.getComputedTextLength() : 0,
        subT.getComputedTextLength ? subT.getComputedTextLength() : 0);
      const tx0 = ix1 - (mW + sW);
      tt.setAttribute("x", tx0.toFixed(1));
      subT.setAttribute("x", (tx0 + mW).toFixed(1));
    }
    el("rect", { x: ix0, y: iy0, width: iw, height: ih2,
      class: "corner-frame" }, svg);
    // round-number inset ticks (the range starts at 0, a hard ratio floor)
    const it = niceTicks(0, mx, 1, 15*K, iw);
    it.vals.forEach((v, n) => {
      const tx = xr(v);
      el("line", { x1: tx, y1: iy0 + ih2, x2: tx, y2: iy0 + ih2 + 4*K,
        stroke: "var(--line-strong)", "stroke-width": K }, svg);
      const t = el("text", { x: tx, y: iy0 + ih2 + 20*K,
        "text-anchor": "middle", class: "corner-tick" }, svg);
      t.textContent = it.labels[n];
    });
    if (inset.xlabel) {
      // full-size label: the cells below the inset are always empty, so it
      // may run wider than the inset itself
      const xl2 = el("text", { x: ix0 + iw / 2, y: iy0 + ih2 + 44*K,
        "text-anchor": "middle", class: "corner-label",
        style: `font-size:${15*K}px` }, svg);
      xl2.textContent = inset.xlabel;
    }
  }
}

/* ── figure export: standalone SVG with computed styles inlined ──────── */

const SNAP_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width",
  "stroke-dasharray", "stroke-opacity", "opacity", "font-family",
  "font-size", "font-weight", "text-anchor"];

export function svgStandalone(svg, opts = {}) {
  // opts.fontScale  multiplies every font-size on the way out.  The on-screen
  // sizes are tuned for a plot drawn at the full width of the results panel;
  // a figure reproduced at half a journal text width needs them ~2x larger to
  // land at the ~9 pt of surrounding body text, so print exports pass ~2.
  const fontScale = Number(opts.fontScale) || 1;
  const clone = svg.cloneNode(true);
  const srcEls = [svg, ...svg.querySelectorAll("*")];
  const dstEls = [clone, ...clone.querySelectorAll("*")];
  srcEls.forEach((s, i) => {
    const cs = getComputedStyle(s);
    for (const prop of SNAP_PROPS) {
      const v = cs.getPropertyValue(prop);
      if (v && v !== "none" || prop === "fill" || prop === "stroke")
        dstEls[i].setAttribute(prop, v);
    }
    dstEls[i].removeAttribute("class");
    dstEls[i].removeAttribute("style");
    if (fontScale !== 1) {
      const fs = parseFloat(dstEls[i].getAttribute("font-size"));
      if (isFinite(fs)) dstEls[i].setAttribute("font-size", (fs * fontScale).toFixed(2));
    }
  });
  const vb = svg.viewBox.baseVal;
  clone.setAttribute("xmlns", SVGNS);
  clone.setAttribute("width", vb.width);
  clone.setAttribute("height", vb.height);
  const bg = document.createElementNS(SVGNS, "rect");
  bg.setAttribute("x", vb.x); bg.setAttribute("y", vb.y);
  bg.setAttribute("width", vb.width); bg.setAttribute("height", vb.height);
  bg.setAttribute("fill", "#ffffff");   // white export background (screen theme is cream)
  clone.insertBefore(bg, clone.firstChild);
  return { text: new XMLSerializer().serializeToString(clone),
           width: vb.width, height: vb.height };

}
