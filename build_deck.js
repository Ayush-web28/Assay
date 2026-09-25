const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

// ---------- tokens ----------
const C = {
  ink: "1D1D1F", gold: "C98A1B", goldDk: "8A5A0B", goldLt: "F6E7C8", tint: "FBF6EC",
  slate: "5B6573", slateLt: "E6E9ED", white: "FFFFFF", warn: "B5482F", warnLt: "F7E3DE",
};
const HEAD = "Montserrat", BODY = "Calibri";
const D = JSON.parse(require("fs").readFileSync("assets/deck_data.json", "utf8"));

async function icon(Comp, color = "FFFFFF", px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: px }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
const shadow = () => ({ type: "outer", color: "000000", opacity: 0.12, blur: 10, offset: 3, angle: 90 });

(async () => {
  const pres = new pptxgen();
  pres.defineLayout({ name: "HIH", width: 20, height: 11.25 });
  pres.layout = "HIH";
  pres.title = "Assay - Hack in Hills '26";

  const thin = (s) => s.addImage({ path: "assets/banner_thin.png", x: 0, y: 0, w: 20, h: 1.317 });
  const title = (s, t) =>
    s.addText(t, { x: 0.9, y: 1.55, w: 18, h: 0.8, fontFace: HEAD, bold: true, fontSize: 38, color: C.ink, margin: 0, isTextBox: true });
  const card = (s, x, y, w, h, fill = C.white, line = C.slateLt) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.18, fill: { color: fill }, line: { color: line, width: 1 }, shadow: shadow() });
  const badge = async (s, Comp, x, y, d, bg = C.gold, fg = "FFFFFF") => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg, width: 0 } });
    const p = d * 0.5;
    s.addImage({ data: await icon(Comp, fg), x: x + (d - p) / 2, y: y + (d - p) / 2, w: p, h: p });
  };
  const arrow = (s, x, y, w = 0.5, h = 0.5, color = C.gold) =>
    s.addShape(pres.shapes.CHEVRON, { x, y, w, h, fill: { color }, line: { color, width: 0 } });
  const txt = (s, t, o) => s.addText(t, Object.assign({ fontFace: BODY, color: C.ink, margin: 0, isTextBox: true, valign: "middle" }, o));

  // ================= 1. TEAM =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addImage({ path: "assets/banner_big.png", x: 0, y: 0, w: 20, h: 4.475 });
    txt(s, "TEAM", { x: 1.3, y: 4.75, w: 8, h: 1.1, fontFace: HEAD, bold: true, fontSize: 54, valign: "top" });

    // team name card
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.3, y: 6.3, w: 6.9, h: 4.0, rectRadius: 0.2, fill: { color: C.ink }, line: { color: C.ink, width: 0 }, shadow: shadow() });
    s.addImage({ data: await icon(fa.FaGem, C.gold), x: 1.75, y: 6.75, w: 0.85, h: 0.85 });
    txt(s, "ASSAY", { x: 1.75, y: 7.7, w: 6.0, h: 1.2, fontFace: HEAD, bold: true, fontSize: 60, color: C.white });
    txt(s, "Is the gold spread real,\nor just noise?", { x: 1.75, y: 8.95, w: 6.0, h: 1.2, fontSize: 24, italic: true, color: C.goldLt, valign: "top" });

    // member cards
    const members = [
      [fa.FaDatabase, "[Member Name]", "Data pipeline & backtest"],
      [fa.FaChartLine, "[Member Name]", "Analytics & dashboard"],
      [fa.FaBullhorn, "[Member Name]", "Research & pitch"],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 8.6 + i * (3.2 + 0.25), y = 6.3;
      card(s, x, y, 3.2, 4.0, C.tint, C.goldLt);
      await badge(s, members[i][0], x + 0.9, y + 0.5, 1.4);
      txt(s, members[i][1], { x: x + 0.15, y: y + 2.2, w: 2.9, h: 0.6, fontSize: 22, bold: true, align: "center" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.2, y: y + 3.0, w: 2.8, h: 0.6, rectRadius: 0.3, fill: { color: C.goldLt }, line: { color: C.goldLt, width: 0 } });
      txt(s, members[i][2], { x: x + 0.2, y: y + 3.0, w: 2.8, h: 0.6, fontSize: 15, color: C.goldDk, bold: true, align: "center" });
    }
    s.addNotes("Replace the [Member Name] placeholders and adjust roles. Roles shown are suggestions.");
  }

  // ================= 2. PROBLEM =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "PROBLEM STATEMENT & THEME");

    // contracts diagram: circle area ~ grams (sqrt scale, illustrative)
    const cs = [["GOLDM", "100 g", 2.7], ["GOLDTEN", "10 g", 1.75], ["GOLDGUINEA", "8 g", 1.6], ["GOLDPETAL", "1 g", 0.95]];
    let cx = 1.0;
    const baseY = 5.75;
    for (const [n, g, d] of cs) {
      s.addShape(pres.shapes.OVAL, { x: cx, y: baseY - d, w: d, h: d, fill: { color: C.gold }, line: { color: C.goldDk, width: 2 }, shadow: shadow() });
      txt(s, g, { x: cx, y: baseY - d, w: d, h: d, fontSize: d > 1.2 ? 22 : 16, bold: true, color: C.white, align: "center" });
      txt(s, n, { x: cx - 0.3, y: baseY + 0.12, w: d + 0.6, h: 0.45, fontSize: 15, bold: true, align: "center", color: C.slate });
      cx += d + 0.5;
    }
    txt(s, "4 contracts · 1 metal", { x: 1.0, y: 2.45, w: 9, h: 0.45, fontSize: 22, bold: true, color: C.goldDk });

    // arrow + question panel
    arrow(s, 10.45, 4.0, 0.7, 0.9);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 11.5, y: 2.75, w: 7.6, h: 3.6, rectRadius: 0.2, fill: { color: C.ink }, line: { color: C.ink, width: 0 }, shadow: shadow() });
    s.addImage({ data: await icon(fa.FaBalanceScale, C.gold), x: 12.0, y: 3.1, w: 1.1, h: 1.1 });
    txt(s, "Same gold.", { x: 13.4, y: 3.05, w: 5.4, h: 0.6, fontSize: 28, bold: true, color: C.white });
    txt(s, "Same price?", { x: 13.4, y: 3.65, w: 5.4, h: 0.7, fontSize: 34, bold: true, color: C.gold });
    txt(s, "Unit  ·  purity  ·  quote base", { x: 12.0, y: 4.9, w: 6.8, h: 0.6, fontSize: 22, color: C.goldLt });
    txt(s, "differ across every contract", { x: 12.0, y: 5.45, w: 6.8, h: 0.6, fontSize: 22, color: C.goldLt });

    // three cards
    const cards = [
      [fa.FaExclamationTriangle, C.warn, "PROBLEM", "No rigorous way to tell a real mispricing from noise"],
      [fa.FaCoins, C.gold, "IMPACT", "False signals lose money to fees and thin liquidity"],
      [fa.FaBullseye, C.slate, "THEME ALIGNMENT", "Data product on India's public commodity data"],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.9 + i * (5.9 + 0.35), y = 7.0, w = 5.9, h = 3.5;
      card(s, x, y, w, h);
      await badge(s, cards[i][0], x + 0.4, y + 0.4, 1.0, cards[i][1]);
      txt(s, cards[i][2], { x: x + 1.65, y: y + 0.4, w: w - 2.0, h: 1.0, fontFace: HEAD, bold: true, fontSize: 22, color: cards[i][1] });
      txt(s, cards[i][3], { x: x + 0.4, y: y + 1.65, w: w - 0.8, h: 1.5, fontSize: 24, valign: "top" });
    }
    s.addNotes("Contract circle sizes are illustrative (sqrt-scaled by grams), not to scale. GOLDM 100 g / GOLDTEN 10 g / GOLDGUINEA 8 g / GOLDPETAL 1 g per the problem statement.");
  }

  // ================= 3. SOLUTION =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "SOLUTION");
    txt(s, "Assay turns MCX settlement data into cost-aware, validated relative-value signals.", { x: 0.9, y: 2.4, w: 18.2, h: 0.6, fontSize: 24, color: C.slate });

    // unique value pills
    const pills = [[fa.FaRupeeSign, "Net of costs"], [fa.FaBalanceScale, "Separated from gold beta"], [fa.FaCheckCircle, "Honest about “no edge”"]];
    for (let i = 0; i < 3; i++) {
      const x = 0.9 + i * (6.0 + 0.1), y = 3.3;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 6.0, h: 0.95, rectRadius: 0.47, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
      s.addImage({ data: await icon(pills[i][0], C.gold), x: x + 0.4, y: y + 0.27, w: 0.42, h: 0.42 });
      txt(s, pills[i][1], { x: x + 1.05, y, w: 4.8, h: 0.95, fontSize: 21, bold: true, color: C.white });
    }

    // real chart: GOLDTEN/GOLDPETAL spread with +/-3 sigma band from past data only
    card(s, 0.9, 4.65, 8.9, 5.85);
    txt(s, "GOLDTEN / GOLDPETAL spread (bps)  ·  real MCX data", { x: 1.3, y: 4.85, w: 8.3, h: 0.5, fontSize: 18, bold: true, color: C.slate });
    const S = D.series;
    s.addChart(pres.charts.LINE, [
      { name: "spread", labels: S.labels, values: S.spread },
      { name: "+3σ", labels: S.labels, values: S.hi },
      { name: "-3σ", labels: S.labels, values: S.lo },
    ], {
      x: 1.2, y: 5.35, w: 8.3, h: 4.3,
      chartColors: [C.gold, C.warn, C.warn], lineSize: 2, lineDataSymbol: "none",
      showLegend: false, catAxisHidden: true, valAxisLabelColor: C.slate, valAxisLabelFontSize: 12,
      valGridLine: { color: "EEEEEE", size: 0.5 }, catGridLine: { style: "none" },
    });
    txt(s, "Jun 2025 → Sep 2026  ·  red = ±3σ of past spreads  ·  Jan 2026 crash breaks the band", { x: 1.3, y: 9.75, w: 8.3, h: 0.55, fontSize: 14, italic: true, color: C.warn });

    // feature grid 2x3
    const feats = [
      [fa.FaLayerGroup, "Unit normalization"], [fa.FaChartLine, "Spread z-scores"],
      [fa.FaProjectDiagram, "Term structure & carry"], [fa.FaFlask, "Walk-forward backtest"],
      [fa.FaCalendarAlt, "Contract calendar"], [fa.FaBell, "Quiet alerts"],
    ];
    for (let i = 0; i < 6; i++) {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 10.2 + col * (4.4 + 0.3), y = 4.65 + row * (1.85 + 0.15), w = 4.4, h = 1.85;
      card(s, x, y, w, h, C.tint, C.goldLt);
      await badge(s, feats[i][0], x + 0.3, y + 0.42, 1.0);
      txt(s, feats[i][1], { x: x + 1.5, y, w: w - 1.7, h, fontSize: 20, bold: true });
    }
    s.addNotes("Chart is a synthetic illustration of the alert concept, not real MCX data. Replace with a real spread chart once the backtest exists.");
  }

  // ================= 4. ARCHITECTURE =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "ARCHITECTURE");
    const nodes = [
      [fa.FaCloudDownloadAlt, "MCX Bhavcopy", "public · no key"],
      [fa.FaShieldAlt, "Validated ingest", "date checked"],
      [fa.FaDatabase, "DuckDB store", "by expiry_date"],
      [fa.FaLayerGroup, "Normalize", "₹/g @ 999"],
      [fa.FaCogs, "Signal engine", "spread · curve · backtest"],
      [fa.FaDesktop, "Dashboard", "Streamlit · alerts"],
    ];
    const nw = 2.65, gap = 0.5, y0 = 2.85, nh = 3.2;
    for (let i = 0; i < 6; i++) {
      const x = 0.8 + i * (nw + gap);
      const dark = i === 4;
      card(s, x, y0, nw, nh, dark ? C.ink : C.tint, dark ? C.ink : C.goldLt);
      await badge(s, nodes[i][0], x + (nw - 1.1) / 2, y0 + 0.35, 1.1, dark ? C.gold : C.gold);
      txt(s, nodes[i][1], { x: x + 0.1, y: y0 + 1.7, w: nw - 0.2, h: 0.6, fontSize: 21, bold: true, align: "center", color: dark ? C.white : C.ink });
      txt(s, nodes[i][2], { x: x + 0.1, y: y0 + 2.3, w: nw - 0.2, h: 0.7, fontSize: 15, align: "center", color: dark ? C.goldLt : C.slate });
      if (i < 5) arrow(s, x + nw + 0.06, y0 + nh / 2 - 0.25, 0.38, 0.5);
    }

    // bottom three cards
    const bw = 5.9, by = 6.6, bh = 3.9;
    // tech stack
    card(s, 0.8, by, bw, bh);
    txt(s, "TECH STACK", { x: 1.2, y: by + 0.3, w: 5, h: 0.5, fontFace: HEAD, bold: true, fontSize: 20, color: C.goldDk });
    const chips = ["Python", "pandas", "DuckDB", "Streamlit", "Plotly"];
    chips.forEach((c, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 1.2 + col * 2.6, y = by + 1.15 + row * 0.85;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.4, h: 0.65, rectRadius: 0.32, fill: { color: C.goldLt }, line: { color: C.goldLt, width: 0 } });
      txt(s, c, { x, y, w: 2.4, h: 0.65, fontSize: 18, bold: true, color: C.goldDk, align: "center" });
    });
    // guard-rails
    const gx = 0.8 + bw + 0.35;
    card(s, gx, by, bw, bh);
    txt(s, "GUARD-RAILS", { x: gx + 0.4, y: by + 0.3, w: 5, h: 0.5, fontFace: HEAD, bold: true, fontSize: 20, color: C.goldDk });
    const rails = ["Returned date verified", "Keyed by expiry_date", "No look-ahead", "Costs on held contracts"];
    const ck = await icon(fa.FaCheckCircle, C.gold);
    rails.forEach((r, i) => {
      const y = by + 1.05 + i * 0.66;
      s.addImage({ data: ck, x: gx + 0.4, y: y + 0.08, w: 0.42, h: 0.42 });
      txt(s, r, { x: gx + 1.05, y, w: bw - 1.3, h: 0.58, fontSize: 19 });
    });
    // APIs
    const ax = gx + bw + 0.35;
    card(s, ax, by, bw, bh);
    txt(s, "DATA & APIs", { x: ax + 0.4, y: by + 0.3, w: 5, h: 0.5, fontFace: HEAD, bold: true, fontSize: 20, color: C.goldDk });
    await badge(s, fa.FaGlobe, ax + 0.4, by + 1.2, 1.0);
    txt(s, "MCX Daily Bhavcopy", { x: ax + 1.6, y: by + 1.2, w: bw - 1.9, h: 0.5, fontSize: 20, bold: true, valign: "top" });
    txt(s, "public · no API key", { x: ax + 1.6, y: by + 1.7, w: bw - 1.9, h: 0.5, fontSize: 16, color: C.slate, valign: "top" });
    await badge(s, fa.FaFileAlt, ax + 0.4, by + 2.5, 1.0, C.slate);
    txt(s, "MCX contract specs", { x: ax + 1.6, y: by + 2.5, w: bw - 1.9, h: 0.5, fontSize: 20, bold: true, valign: "top" });
    txt(s, "unit · purity · expiry window", { x: ax + 1.6, y: by + 3.0, w: bw - 1.9, h: 0.5, fontSize: 16, color: C.slate, valign: "top" });
  }

  // ================= 5. RESULTS =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "RESULTS: NO EDGE AFTER COSTS");
    const dg = D.diag["GOLDGUINEA/GOLDPETAL"];
    card(s, 0.9, 2.7, 9.6, 6.3);
    txt(s, "GOLDGUINEA / GOLDPETAL  ·  5-day reversion vs round-trip cost (bps)", { x: 1.3, y: 2.9, w: 8.9, h: 0.5, fontSize: 18, bold: true, color: C.slate });
    s.addChart(pres.charts.BAR, [
      { name: "reversion", labels: dg.map(d => "|z| " + d.z_bucket.replace("-inf", "+")), values: dg.map(d => d.mean_reversion_bps) },
      { name: "round-trip cost", labels: dg.map(d => "|z| " + d.z_bucket.replace("-inf", "+")), values: dg.map(d => d.roundtrip_cost_bps) },
    ], {
      x: 1.2, y: 3.45, w: 9.0, h: 5.4, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
      chartColors: [C.gold, C.slate], showLegend: true, legendPos: "b", legendFontSize: 15, legendColor: C.ink,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 15, dataLabelColor: C.ink, dataLabelFormatCode: "0",
      catAxisLabelColor: C.ink, catAxisLabelFontSize: 15, valAxisHidden: true,
      valGridLine: { style: "none" }, catGridLine: { style: "none" },
    });
    const fx = D.fixed;
    const tiles = [
      ["0.2×", "GOLDGUINEA / GOLDPETAL break-even cost. Costs erase the edge.", C.ink, C.gold, C.white],
      ["2.2–2.5×", "GOLDTEN pairs break-even, on ~20 trades and 9 months.", C.gold, C.ink, C.ink],
      ["−₹3.1M", "walk-forward net after costs (gross −₹2.3M, 1,000 g per leg).", C.ink, C.gold, C.white],
    ];
    for (let i = 0; i < 3; i++) {
      const y = 2.7 + i * 2.15;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.9, y, w: 8.2, h: 2.0, rectRadius: 0.2, fill: { color: tiles[i][2] }, line: { color: tiles[i][2], width: 0 }, shadow: shadow() });
      txt(s, tiles[i][0], { x: 11.2, y, w: 3.3, h: 2.0, fontFace: HEAD, bold: true, fontSize: 40, color: tiles[i][3], align: "center" });
      txt(s, tiles[i][1], { x: 14.6, y, w: 4.2, h: 2.0, fontSize: 18, color: tiles[i][4] });
    }
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.9, y: 9.4, w: 18.2, h: 1.2, rectRadius: 0.2, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
    s.addImage({ data: await icon(fa.FaCheckCircle, C.gold), x: 1.4, y: 9.8, w: 0.4, h: 0.4 });
    txt(s, "Mild deviations don't pay. Only the Jan 2026 crash cleared costs: one episode, not an edge.", { x: 2.1, y: 9.4, w: 16.8, h: 1.2, fontSize: 24, bold: true, color: C.gold });
    s.addNotes("Numbers from results/summary.json (data " + D.data.first + " to " + D.data.last + "). Reversion is measured from the next settlement over 5 trading days. Break-even cost = multiple of the ASSUMED cost model at which fixed-parameter P&L is zero. Walk-forward net -3.07M INR, gross -2.30M INR, 24 trades, 1,000 g per leg. Costs are modelled assumptions.");
  }

  // ================= 6. MARKET =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "MARKET RESEARCH / ANALYSIS");
    // stat tiles
    const stats = [
      ["₹64,407 Cr", "MCX futures avg. daily turnover, FY26"],
      ["2.4×", "growth vs FY25 (₹27,153 Cr)"],
      ["77%", "of futures turnover is gold + silver"],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.9 + i * (5.9 + 0.3), y = 2.7, w = 5.9, h = 2.9;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.2, fill: { color: i === 1 ? C.gold : C.ink }, line: { color: C.ink, width: 0 }, shadow: shadow() });
      txt(s, stats[i][0], { x: x + 0.3, y: y + 0.3, w: w - 0.6, h: 1.4, fontFace: HEAD, bold: true, fontSize: 48, color: i === 1 ? C.ink : C.gold, align: "center" });
      txt(s, stats[i][1], { x: x + 0.4, y: y + 1.75, w: w - 0.8, h: 0.95, fontSize: 19, color: i === 1 ? C.ink : C.white, align: "center", valign: "top" });
    }
    // target users
    txt(s, "TARGET USERS", { x: 0.9, y: 6.0, w: 9, h: 0.5, fontFace: HEAD, bold: true, fontSize: 20, color: C.goldDk });
    const users = [[fa.FaUser, "Retail traders"], [fa.FaGem, "Bullion dealers"], [fa.FaUniversity, "Quant desks"], [fa.FaHandshake, "Brokers & fintechs"]];
    for (let i = 0; i < 4; i++) {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.9 + col * 4.75, y = 6.6 + row * 2.0, w = 4.55, h = 1.8;
      card(s, x, y, w, h, C.tint, C.goldLt);
      await badge(s, users[i][0], x + 0.3, y + 0.4, 1.0);
      txt(s, users[i][1], { x: x + 1.55, y, w: w - 1.7, h, fontSize: 21, bold: true });
    }
    // revenue staircase
    txt(s, "REVENUE MODEL", { x: 11.0, y: 6.0, w: 8, h: 0.5, fontFace: HEAD, bold: true, fontSize: 20, color: C.goldDk });
    const steps = [["Free", "delayed data", 1.7, C.slateLt, C.ink], ["Pro", "alerts + history", 2.8, C.goldLt, C.goldDk], ["API / Enterprise", "desks & brokers", 3.9, C.gold, C.white]];
    steps.forEach((st, i) => {
      const w = 2.55, x = 11.0 + i * (w + 0.22), h = st[2], y = 10.4 - h;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.15, fill: { color: st[3] }, line: { color: st[3], width: 0 }, shadow: shadow() });
      txt(s, st[0], { x: x + 0.15, y: y + 0.15, w: w - 0.3, h: 0.7, fontSize: 20, bold: true, color: st[4], align: "center" });
      txt(s, st[1], { x: x + 0.15, y: y + 0.8, w: w - 0.3, h: 0.5, fontSize: 15, color: st[4], align: "center", valign: "top" });
    });
    txt(s, "Source: MCX FY26 disclosures via ICICI Direct MCX Q3 FY26 note. Verify before final submission.", { x: 0.9, y: 10.6, w: 18, h: 0.4, fontSize: 12, italic: true, color: C.slate });
    s.addNotes("Figures from web search: futures ADT Rs 64,407 cr in FY26 vs Rs 27,153 cr in FY25; gold+silver = 77% of futures turnover. 2.4x is computed (64,407/27,153). Source: https://www.icicidirect.com/mailcontent/idirect_mcx_q3fy26.pdf . Verify against the primary MCX filing before submission.");
  }

  // ================= 6. FUTURE SCOPE =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "FUTURE SCOPE");
    const st = [
      [fa.FaMobileAlt, "Mobile app", "push alerts", 2.3, C.slate],
      [fa.FaBrain, "AI model improvement", "regime-aware signals", 3.6, "8A6A2A"],
      [fa.FaPlug, "Enterprise integrations", "broker & desk APIs", 4.9, "B07A1F"],
      [fa.FaGlobe, "Scale to global users", "intl. bullion futures", 6.2, C.gold],
    ];
    const w = 4.3, gap = 0.4;
    for (let i = 0; i < 4; i++) {
      const x = 0.8 + i * (w + gap), h = st[i][3], y = 10.5 - h;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.2, fill: { color: st[i][4] }, line: { color: st[i][4], width: 0 }, shadow: shadow() });
      await badge(s, st[i][0], x + (w - 1.2) / 2, y - 0.6, 1.2, C.ink, C.gold);
      txt(s, st[i][1], { x: x + 0.25, y: y + 0.75, w: w - 0.5, h: 1.0, fontSize: 24, bold: true, color: C.white, align: "center" });
      txt(s, st[i][2], { x: x + 0.25, y: y + 1.75, w: w - 0.5, h: 0.5, fontSize: 17, color: C.goldLt, align: "center", valign: "top" });
    }
    s.addImage({ data: await icon(fa.FaFlag, C.ink), x: 0.8 + 3 * (w + gap) + w - 1.1, y: 3.45, w: 0.6, h: 0.6 });
  }

  // ================= 7. EXTRA =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    thin(s);
    title(s, "EXTRA: BUILT FOR RIGOR");
    const rows = [
      [fa.FaCalendarTimes, "Holiday returns latest day", "Verify returned date"],
      [fa.FaExchangeAlt, "Near-month series jumps", "Track by expiry_date"],
      [fa.FaTag, "Settlement ≠ fill price", "Cost model, held contracts"],
      [fa.FaTint, "Volume ≠ depth", "Liquidity-capped sizing"],
    ];
    txt(s, "DATA TRAP", { x: 2.5, y: 2.55, w: 6, h: 0.4, fontSize: 15, bold: true, color: C.warn, charSpacing: 3 });
    txt(s, "OUR FIX", { x: 11.3, y: 2.55, w: 6, h: 0.4, fontSize: 15, bold: true, color: C.goldDk, charSpacing: 3 });
    for (let i = 0; i < 4; i++) {
      const y = 3.05 + i * 1.6, h = 1.35;
      card(s, 0.9, y, 18.2, h);
      await badge(s, rows[i][0], 1.25, y + 0.17, 1.0, C.warn);
      txt(s, rows[i][1], { x: 2.5, y, w: 7.4, h, fontSize: 24, color: C.warn, bold: true });
      arrow(s, 9.9, y + 0.4, 0.55, 0.55);
      txt(s, rows[i][2], { x: 11.3, y, w: 7.6, h, fontSize: 24, bold: true });
    }
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.9, y: 9.55, w: 18.2, h: 1.1, rectRadius: 0.2, fill: { color: C.ink }, line: { color: C.ink, width: 0 } });
    s.addImage({ data: await icon(fa.FaCheckCircle, C.gold), x: 1.4, y: 9.9, w: 0.4, h: 0.4 });
    txt(s, "No persistent edge after costs? That is a valid result.", { x: 2.1, y: 9.55, w: 16.5, h: 1.1, fontSize: 26, bold: true, color: C.gold });
  }

  // ================= 8. THANK YOU =================
  {
    const s = pres.addSlide();
    s.background = { color: C.white };
    s.addImage({ path: "assets/thankyou.jpg", x: 0, y: 0, w: 20, h: 11.25 });
    txt(s, "ASSAY  ·  Is the gold spread real, or just noise?", { x: 0, y: 10.45, w: 20, h: 0.5, fontSize: 18, color: C.slate, align: "center" });
  }

  await pres.writeFile({ fileName: "Assay.pptx" });
  console.log("written");
})();
