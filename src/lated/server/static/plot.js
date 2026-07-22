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
      fill: "var(--ink-faint)", "font-size": 9, "font-family": "var(--mono)" }, svg);
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
    "font-size": 8, "font-family": "var(--mono)" }, svg);
  t0.textContent = `${(lo / 1e4).toFixed(1)} µm`;
  const t1 = el("text", { x: W - 2, y: H - 2, "text-anchor": "end",
    fill: "var(--ink-faint)", "font-size": 8, "font-family": "var(--mono)" }, svg);
  t1.textContent = `${(hi / 1e4).toFixed(1)} µm`;
}

/* ── main fit figure ─────────────────────────────────────────────────── */

export function renderMainPlot(svg, tip, d) {
  // d: {bands:[{name,pivot,flux,err,model}], curves:[{name,pivot_aa,wave_aa,trans}],
  //     modelCurve:{wave_aa,total_uJy,continuum_uJy}, lineMarks:[{label,waveObs,free}]}
  clear(svg);
  const W = 920, H = 480, m = { l: 92, r: 16, t: 22, b: 66 };
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
    const t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end",
      fill: "var(--ink-dim)", "font-size": 17,
      "font-family": "var(--mono)" }, svg);
    t.textContent = e >= -1 && e <= 3 ? String(10 ** e) : `1e${e}`;
  }
  const umTicks = [];
  const lo_um = xlo / 1e4, hi_um = xhi / 1e4;
  const step = hi_um - lo_um > 2.4 ? 1.0 : 0.5;
  for (let u = Math.ceil(lo_um / step) * step; u <= hi_um; u += step) umTicks.push(u);
  for (const u of umTicks) {
    const x = X(u * 1e4);
    el("line", { x1: x, y1: m.t + ih, x2: x, y2: m.t + ih + 5,
      stroke: "var(--line-strong)" }, svg);
    const t = el("text", { x, y: m.t + ih + 24, "text-anchor": "middle",
      fill: "var(--ink-dim)", "font-size": 17, "font-family": "var(--mono)" }, svg);
    t.textContent = u.toFixed(step < 1 ? 1 : 0);
  }
  const xl = el("text", { x: m.l + iw / 2, y: H - 12, "text-anchor": "middle",
    fill: "var(--ink)", "font-size": 19, "font-family": "var(--mono)" }, svg);
  xl.textContent = "Observed wavelength  [µm]";
  const yl = el("text", { x: 24, y: m.t + ih / 2, fill: "var(--ink)",
    "font-size": 19, "font-family": "var(--mono)",
    transform: `rotate(-90 24 ${m.t + ih / 2})` }, svg);
  yl.textContent = `Flux density fν  [${d.yUnit || "µJy"}]`;

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
    const t = el("text", { x: X(b.pivot), y: m.t + ih - 8, "text-anchor": "middle",
      fill: b.color || bandColor(b.pivot), "font-size": 16, "font-weight": 700,
      "font-family": "var(--mono)" }, svg);
    t.textContent = b.name;
  }

  // line markers: every line keeps its dashed tick, but labels are
  // decluttered (free lines get priority; tied labels appear only when
  // they clear the already-placed ones by >= 18px)
  const marks = d.lineMarks
    .filter(lm => lm.waveObs >= xlo && lm.waveObs <= xhi)
    .map(lm => ({ ...lm, x: X(lm.waveObs) }))
    .sort((a, b) => a.x - b.x);
  for (const lm of marks)
    el("line", { x1: lm.x, y1: m.t + 14, x2: lm.x, y2: m.t + ih * 0.72,
      class: "line-marker" }, svg);
  const placedX = [];
  const MINSEP = 18;
  for (const wantFree of [true, false]) {
    for (const lm of marks) {
      if (Boolean(lm.free) !== wantFree) continue;
      if (placedX.some(px => Math.abs(px - lm.x) < MINSEP)) continue;
      placedX.push(lm.x);
      const t = el("text", { x: lm.x - 3, y: m.t + 12,
        class: "line-marker-label", "text-anchor": "end",
        transform: `rotate(-90 ${lm.x - 3} ${m.t + 12})` }, svg);
      t.textContent = lm.label;
    }
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

  // legend (top-right, away from the line-marker labels)
  const lg = el("g", { transform: `translate(${W - m.r - 205}, ${m.t + 16})` }, svg);
  const legend = [
    ["circle", "Observed photometry", "var(--ink)"],
    ["square", "Model photometry", "var(--amber)"],
    ["line", "Best-fit model", "var(--cyan)"],
  ];
  legend.forEach(([kind, label, col], i) => {
    const y = i * 25;
    if (kind === "circle") el("circle", { cx: 6, cy: y, r: 4.5, fill: col }, lg);
    if (kind === "square") el("rect", { x: 1, y: y - 5, width: 10, height: 10,
      fill: "none", stroke: col, "stroke-width": 1.6 }, lg);
    if (kind === "line") el("line", { x1: 0, y1: y, x2: 14, y2: y, stroke: col,
      "stroke-width": 2 }, lg);
    const t = el("text", { x: 20, y: y + 5, fill: "var(--ink-dim)",
      "font-size": 16, "font-family": "var(--mono)" }, lg);
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

const SUP = { "-": "⁻", "0": "⁰", "1": "¹", "2": "²",
  "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷",
  "8": "⁸", "9": "⁹" };
const sup = s => String(s).split("").map(c => SUP[c] || c).join("");

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

export function renderCorner(svg, params, inset) {
  // params: [{label, values: number[], best: number, unit: string}]
  // inset (optional): the reported ratio, drawn in the empty top-right
  //   corner: {label, values, best, status, p975}
  clear(svg);
  const k = params.length;
  const W = 680, H = 684, mL = 120, mB = 92, mT = 68, mR = 18, gap = 16;
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
      scaleLabel: e === 0 ? "" : `×10${sup(e)}`,
      q16: quantile(sorted, 0.16), q50: quantile(sorted, 0.50),
      q84: quantile(sorted, 0.84) };
  });

  const cellX = j => mL + j * (cw + gap);
  const cellY = i => mT + i * (ch + gap);
  const xpos = (pj, v, j) => cellX(j) + (v - pj.mn) / (pj.mx - pj.mn) * cw;
  const ypos = (pi, v, i) => cellY(i) + ch - (v - pi.mn) / (pi.mx - pi.mn) * ch;
  const tickFmt = (v, sc) => {
    const s = v * sc;
    return Math.abs(s) < 1e-12 ? "0" : Number(s.toPrecision(2)).toString();
  };
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
          "stroke-width": 1 }, svg);
        // 16/50/84 markers
        for (const q of [pi.q16, pi.q50, pi.q84]) {
          const qx = xpos(pj, q, j);
          if (qx > x0 && qx < x0 + cw)
            el("line", { x1: qx, y1: y0 + 3, x2: qx, y2: y0 + ch - 1,
              stroke: "var(--ink-dim)", "stroke-width": 0.8,
              "stroke-dasharray": "3 3" }, svg);
        }
        if (isFinite(pi.best)) {
          const bx = xpos(pj, pi.best, j);
          if (bx >= x0 && bx <= x0 + cw)
            el("line", { x1: bx, y1: y0 + 2, x2: bx, y2: y0 + ch - 1,
              class: "corner-best", "stroke-width": 1.3 }, svg);
        }
        // title: median with stacked +upper / -lower errors; decimals MATCH
        // the errors' (two significant figures): 2.00 +0.12 -0.30, never
        // 2 +0.12 -0.3.  The title must stay within its own column (the
        // space above a diagonal panel is always empty; the neighbouring
        // columns are not), so wide titles split onto two lines.
        const s = pi.sc;
        const upv = (pi.q84 - pi.q50) * s;
        const lov = (pi.q50 - pi.q16) * s;
        const errDec = e2 => (e2 > 0)
          ? Math.max(0, 1 - Math.floor(Math.log10(e2))) : 0;
        const dec = Math.max(errDec(upv), errDec(lov));
        const medStr = (pi.q50 * s).toFixed(dec);
        const supStr = `+${upv.toFixed(dec)}`;
        const subStr = `\u2212${lov.toFixed(dec)}`;
        const errSize = 12;
        // mono glyphs are ~0.602 em wide
        const wOneLine = (pi.label.length + 3 + medStr.length) * 17 * 0.602
          + supStr.length * errSize * 0.602;
        const twoLine = wOneLine > cw + 10;
        const cxm = x0 + cw / 2;
        if (twoLine) {
          const lt = el("text", { x: cxm, y: y0 - 34,
            "text-anchor": "middle", class: "corner-title" }, svg);
          lt.textContent = pi.label;
        }
        const tt = el("text", { x: cxm, y: y0 - 12,
          "text-anchor": "middle", class: "corner-title" }, svg);
        const main = el("tspan", {}, tt);
        main.textContent = twoLine ? `${medStr}` : `${pi.label} = ${medStr}`;
        const supT = el("tspan", { dy: -8, "font-size": errSize }, tt);
        supT.textContent = supStr;
        const subT = el("tspan", { dy: 14,
          dx: -(supStr.length * errSize * 0.602).toFixed(1),
          "font-size": errSize }, tt);
        subT.textContent = subStr;
        el("tspan", { dy: -6 }, tt);   // restore the baseline
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
        // separable gaussian smooth (sigma ~ 1 bin)
        const K = [0.054, 0.244, 0.404, 0.244, 0.054];
        const tmp = new Float64Array(N * N);
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          let s = 0;
          for (let m = -2; m <= 2; m++) {
            const cc = Math.min(N - 1, Math.max(0, c + m));
            s += K[m + 2] * grid[r * N + cc];
          }
          tmp[r * N + c] = s;
        }
        const sm = new Float64Array(N * N);
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          let s = 0;
          for (let m = -2; m <= 2; m++) {
            const rr = Math.min(N - 1, Math.max(0, r + m));
            s += K[m + 2] * tmp[rr * N + c];
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
          stroke: "var(--cyan)", "stroke-width": 1.0, fill: "none",
          opacity: 0.75 }, svg);
        el("path", { d: marchingSquares(sm, N, N, l1, x0, y0, dx, dy),
          stroke: "var(--cyan)", "stroke-width": 1.5, fill: "none" }, svg);
        // outliers beyond the 2σ contour
        for (let n = 0; n < NPT; n++) {
          if (sm[binOf(n)] > l2) continue;
          el("circle", { cx: xpos(pj, pj.values[n], j).toFixed(1),
            cy: ypos(pi, pi.values[n], i).toFixed(1), r: 1.2,
            class: "corner-dot" }, svg);
        }
        if (isFinite(pi.best) && isFinite(pj.best)) {
          const bx = xpos(pj, pj.best, j), by = ypos(pi, pi.best, i);
          el("line", { x1: bx - 4.5, y1: by, x2: bx + 4.5, y2: by,
            class: "corner-best" }, svg);
          el("line", { x1: bx, y1: by - 4.5, x2: bx, y2: by + 4.5,
            class: "corner-best" }, svg);
        }
      }

      el("rect", { x: x0, y: y0, width: cw, height: ch,
        class: "corner-frame" }, svg);

      // ── ticks and two-line axis labels ──
      const tickVals = p => [0.15, 0.5, 0.85].map(f => p.mn + f * (p.mx - p.mn));
      if (i === k - 1) {
        // declutter: shrink crowded tick labels, rotate if still colliding
        const tvs = tickVals(pj);
        const labels = tvs.map(v => tickFmt(v, pj.sc));
        const maxLen = Math.max(...labels.map(s => s.length));
        const crowded = maxLen * 15 * 0.602 * 3 > cw * 0.95;
        const rotate = maxLen * 12 * 0.602 * 3 > cw * 1.08;
        tvs.forEach((v, n) => {
          const tx = xpos(pj, v, j);
          el("line", { x1: tx, y1: y0 + ch, x2: tx, y2: y0 + ch + 4,
            stroke: "var(--line-strong)" }, svg);
          const attrs = { x: tx, y: y0 + ch + 20,
            "text-anchor": "middle", class: "corner-tick" };
          if (crowded) attrs.style = "font-size:12px";
          if (rotate) {
            attrs["text-anchor"] = "end";
            attrs.transform = `rotate(-38 ${tx} ${y0 + ch + 20})`;
          }
          const t = el("text", attrs, svg);
          t.textContent = labels[n];
        });
        const lx = el("text", { x: x0 + cw / 2, y: y0 + ch + 44,
          "text-anchor": "middle", class: "corner-label" }, svg);
        const l1t = el("tspan", { x: x0 + cw / 2 }, lx);
        l1t.textContent = pj.label;
        // scale and unit on their own lines so neighbours never collide
        if (pj.scaleLabel) {
          const l2t = el("tspan", { x: x0 + cw / 2, dy: 19,
            "font-size": 13, fill: "var(--ink-dim)", "font-weight": 400 }, lx);
          l2t.textContent = pj.scaleLabel;
        }
        if (pj.unit) {
          const l3t = el("tspan", { x: x0 + cw / 2,
            dy: pj.scaleLabel ? 16 : 19,
            "font-size": 11.5, fill: "var(--ink-dim)", "font-weight": 400 }, lx);
          l3t.textContent = pj.unit;
        }
      }
      if (j === 0 && i > 0) {
        for (const v of tickVals(pi)) {
          const ty = ypos(pi, v, i);
          el("line", { x1: mL - 4, y1: ty, x2: mL, y2: ty,
            stroke: "var(--line-strong)" }, svg);
          const t = el("text", { x: mL - 7, y: ty + 3,
            "text-anchor": "end", class: "corner-tick" }, svg);
          t.textContent = tickFmt(v, pi.sc);
        }
        const cy = y0 + ch / 2;
        const ly = el("text", { x: 26, y: cy, "text-anchor": "middle",
          class: "corner-label", transform: `rotate(-90 26 ${cy})` }, svg);
        const l1t = el("tspan", { x: 26 }, ly);
        l1t.textContent = pi.label;
        if (pi.scaleLabel) {
          const l2t = el("tspan", { x: 26, dy: 19, "font-size": 13,
            fill: "var(--ink-dim)", "font-weight": 400 }, ly);
          l2t.textContent = pi.scaleLabel;
        }
        if (pi.unit) {
          const l3t = el("tspan", { x: 26, dy: pi.scaleLabel ? 16 : 19,
            "font-size": 11.5, fill: "var(--ink-dim)", "font-weight": 400 }, ly);
          l3t.textContent = pi.unit;
        }
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
      "stroke-width": 1 }, svg);
    const disp = inset.disp || {};
    const tt = el("text", { x: ix1, y: iy0 - 12, "text-anchor": "end",
      class: "corner-title" }, svg);
    if (inset.status === "upper_limit") {
      // 2-sigma bound solid, 1-sigma bound dashed; no 16/50/84 quantiles
      const bx = xr(inset.p975);
      el("line", { x1: bx, y1: iy0 + 2, x2: bx, y2: iy0 + ih2 - 1,
        stroke: "var(--rose)", "stroke-width": 1.5 }, svg);
      if (isFinite(inset.p84)) {
        const b1 = xr(inset.p84);
        el("line", { x1: b1, y1: iy0 + 2, x2: b1, y2: iy0 + ih2 - 1,
          stroke: "var(--rose)", "stroke-width": 1.1,
          "stroke-dasharray": "5 4" }, svg);
      }
      tt.setAttribute("fill", "var(--rose)");
      tt.textContent = `${inset.label} < ${disp.lim} (2\u03c3)`;
    } else {
      for (const q of [0.16, 0.5, 0.84]) {
        const qx = xr(quantile(sortedV, q));
        el("line", { x1: qx, y1: iy0 + 3, x2: qx, y2: iy0 + ih2 - 1,
          stroke: "var(--ink-dim)", "stroke-width": 0.8,
          "stroke-dasharray": "3 3" }, svg);
      }
      if (isFinite(inset.best)) {
        const bx = xr(inset.best);
        el("line", { x1: bx, y1: iy0 + 2, x2: bx, y2: iy0 + ih2 - 1,
          class: "corner-best", "stroke-width": 1.3 }, svg);
      }
      // same stacked ^{+up}_{-lo} format as the diagonal titles, from the
      // SAME strings the verdict card shows
      const main = el("tspan", {}, tt);
      main.textContent = `${inset.label} = ${disp.med}`;
      const errSize = 12;
      const supT = el("tspan", { dy: -8, "font-size": errSize }, tt);
      supT.textContent = disp.up;
      const subT = el("tspan", { dy: 14,
        dx: -(String(disp.up).length * errSize * 0.602).toFixed(1),
        "font-size": errSize }, tt);
      subT.textContent = disp.lo;
      el("tspan", { dy: -6 }, tt);
    }
    el("rect", { x: ix0, y: iy0, width: iw, height: ih2,
      class: "corner-frame" }, svg);
    const insetLabels = [0.15, 0.5, 0.85].map(f =>
      Number((f * mx).toPrecision(2)).toString());
    const iMaxLen = Math.max(...insetLabels.map(s => s.length));
    const iCrowded = iMaxLen * 15 * 0.602 * 3 > iw * 0.95;
    [0.15, 0.5, 0.85].forEach((f, n) => {
      const v = f * mx;
      const tx = xr(v);
      el("line", { x1: tx, y1: iy0 + ih2, x2: tx, y2: iy0 + ih2 + 4,
        stroke: "var(--line-strong)" }, svg);
      const attrs = { x: tx, y: iy0 + ih2 + 20, "text-anchor": "middle",
        class: "corner-tick" };
      if (iCrowded) attrs.style = "font-size:12px";
      const t = el("text", attrs, svg);
      t.textContent = insetLabels[n];
    });
    if (inset.xlabel) {
      const fsFit = Math.max(11, Math.min(19,
        Math.floor(iw / (inset.xlabel.length * 0.602))));
      const xl2 = el("text", { x: ix0 + iw / 2, y: iy0 + ih2 + 44,
        "text-anchor": "middle", class: "corner-label",
        style: `font-size:${fsFit}px` }, svg);
      xl2.textContent = inset.xlabel;
    }
  }
}

/* ── figure export: standalone SVG with computed styles inlined ──────── */

const SNAP_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width",
  "stroke-dasharray", "stroke-opacity", "opacity", "font-family",
  "font-size", "font-weight", "text-anchor"];

export function svgStandalone(svg) {
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
