"use client";

/**
 * ChartView — RE-PLOTS the backend's chart DECISION in this UI's design language.
 *
 * The backend (nixus/graph/nodes/classify_chart.py) already decided WHICH chart
 * fits the result and returned the primitives: chart_type + x/y/color columns +
 * a human reasoning. We do NOT re-decide and we do NOT parse its `plotly_json`
 * (that blob is a neon-cyan DARK Plotly theme with binary-typed-array y-values —
 * wrong palette, heavy, and lossy to deserialize). Instead we re-plot the SAME
 * decision from those primitives over the already-returned rows, using Recharts,
 * styled to match the warm-paper / oxblood "Engineering Ledger" language.
 *
 * chart_type live values: "bar" | "line" | "pie" | "scatter" | "none". When the
 * backend says "none" (or the data doesn't actually map to the named columns /
 * isn't numeric / has <2 rows), we show an HONEST "no visualization for this
 * result shape" panel — never a forced or broken chart. That honesty is part of
 * the trust model, so it is presented as a calm state, not an error.
 */

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { ChartConfig } from "@/lib/api";

/* Literal hex mirroring the tokens in app/globals.css. Kept literal (not var())
   because Recharts writes axis tick colors as SVG <text fill> ATTRIBUTES, where
   CSS custom properties don't resolve. The HTML tooltip can use the values too. */
const INK = "#1a1813";
const INK_SOFT = "#5a5446";
const INK_FAINT = "#8a8270";
const RULE = "#d9d1be";
const RULE_STRONG = "#c8bfa6";
const ACCENT = "#a8341b"; // oxblood — the single accent
const PAPER_RAISED = "#efeadc";
const FONT_MONO = "ui-monospace, monospace";

/* Warm, oxblood-led categorical palette for pie slices / multi-series scatter.
   Every entry is drawn from (or consistent with) the globals.css warm palette. */
const SERIES = [
  "#a8341b", // accent — oxblood
  "#9a6b16", // ochre  (--warn)
  "#4f6f3a", // olive  (--ok)
  "#9a5b3b", // terracotta (--low)
  "#842513", // deep accent
  "#c2683f", // lighter rust (derived)
  "#5a5446", // ink-soft
  "#7c6a3a", // muted gold (derived)
];

const CHART_HEIGHT = 360;
const MAX_CATEGORIES = 40; // keep bar/scatter layouts sane; note when truncated
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Coerce a cell to a finite number, or null. The backend hands numerics back as
 *  strings ("350.00"), so y-values must be coerced before plotting. */
function toNumber(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Format a date-ish x label simply (no date library). "2024-01-01 00:00:00"
 *  -> "Jan 2024"; a non-first day keeps the day; non-dates pass through. */
function formatDateLabel(v: unknown): string {
  const s = String(v ?? "");
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return s;
  const [, year, month, day] = m;
  const mon = MONTHS[Number(month) - 1] ?? month;
  return day === "01" ? `${mon} ${year}` : `${mon} ${day}, ${year}`;
}

/** The honest no-chart state — a legitimate trust outcome, NOT an error. */
function NoChart({ reason }: { reason?: string }) {
  return (
    <div className="chart-empty" role="note">
      <span className="chart-empty-glyph" aria-hidden>
        ◇
      </span>
      <p className="chart-empty-title">No visualization for this result shape.</p>
      {reason ? <p className="chart-empty-note">{reason}</p> : null}
    </div>
  );
}

/** The "◈ {type} — {reasoning}" caption, in the ledger language. */
function ChartCaption({ type, reasoning }: { type: string; reasoning?: string }) {
  return (
    <p className="chart-caption">
      <span className="chart-caption-glyph" aria-hidden>
        ◈
      </span>
      <span className="chart-caption-type">{type}</span>
      {reasoning ? <span className="chart-caption-text"> — {reasoning}</span> : null}
    </p>
  );
}

const tooltipStyle = {
  contentStyle: {
    background: PAPER_RAISED,
    border: `1px solid ${RULE_STRONG}`,
    borderRadius: 0,
    fontFamily: FONT_MONO,
    fontSize: 12,
    color: INK,
    boxShadow: "3px 3px 0 rgba(26,24,19,0.08)",
  },
  itemStyle: { color: INK },
  labelStyle: { color: INK_SOFT, fontFamily: FONT_MONO, fontSize: 11, marginBottom: 2 },
};

const axisTick = { fill: INK_FAINT, fontFamily: FONT_MONO, fontSize: 11 };
const legendStyle = { fontFamily: FONT_MONO, fontSize: 11, color: INK_SOFT };

export function ChartView({
  config,
  rows,
}: {
  config: ChartConfig | null;
  rows: Record<string, unknown>[];
}) {
  // 1) The backend said there is no meaningful chart.
  if (!config || !config.chart_type || config.chart_type === "none") {
    return <NoChart reason={config?.reasoning || undefined} />;
  }

  const { chart_type, x_column, y_column, color_column, reasoning } = config;

  // 2) Guard the primitives: we need named x/y columns and ≥2 rows that map to them.
  if (!x_column || !y_column) {
    return <NoChart reason="The chart decision is missing its x or y column." />;
  }
  if (!rows || rows.length < 2) {
    return <NoChart reason="A chart needs at least two rows of data." />;
  }
  const sample = rows[0] ?? {};
  if (!(x_column in sample) || !(y_column in sample)) {
    return (
      <NoChart
        reason={`Columns "${x_column}" / "${y_column}" aren't present in this result.`}
      />
    );
  }

  const caption = <ChartCaption type={chart_type} reasoning={reasoning} />;

  // ---- SCATTER: x and y both numeric; optionally segment by color_column ------
  if (chart_type === "scatter") {
    const pts = rows
      .map((r) => ({
        x: toNumber(r[x_column]),
        y: toNumber(r[y_column]),
        c: color_column ? String(r[color_column] ?? "") : undefined,
      }))
      .filter((p) => p.x !== null && p.y !== null);
    if (pts.length < 2) {
      return <NoChart reason={`"${x_column}" / "${y_column}" aren't both numeric.`} />;
    }
    // Group into series when a color column is present, else a single accent series.
    const groups = color_column
      ? Array.from(
          pts.reduce((m, p) => {
            const k = p.c ?? "";
            (m.get(k) ?? m.set(k, []).get(k)!).push(p);
            return m;
          }, new Map<string, typeof pts>()),
        )
      : null;
    return (
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <ScatterChart margin={{ top: 12, right: 18, bottom: 12, left: 4 }}>
            <CartesianGrid stroke={RULE} strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="x"
              name={x_column}
              tick={axisTick}
              stroke={RULE_STRONG}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={y_column}
              tick={axisTick}
              stroke={RULE_STRONG}
              width={56}
            />
            <Tooltip cursor={{ stroke: RULE_STRONG, strokeDasharray: "3 3" }} {...tooltipStyle} />
            {groups ? (
              <>
                <Legend wrapperStyle={legendStyle} />
                {groups.map(([key, data], i) => (
                  <Scatter
                    key={key}
                    name={key || "—"}
                    data={data}
                    fill={SERIES[i % SERIES.length]}
                  />
                ))}
              </>
            ) : (
              <Scatter name={y_column} data={pts} fill={ACCENT} />
            )}
          </ScatterChart>
        </ResponsiveContainer>
        {caption}
      </div>
    );
  }

  // ---- BAR / LINE / PIE: coerce y to numeric over the x category ---------------
  const numeric = rows
    .map((r) => ({ ...r, [y_column]: toNumber(r[y_column]) }))
    .filter((r) => r[y_column] !== null);
  if (numeric.length < 2) {
    return <NoChart reason={`Column "${y_column}" isn't numeric — nothing to plot.`} />;
  }

  const truncated = numeric.length > MAX_CATEGORIES;
  const data = truncated ? numeric.slice(0, MAX_CATEGORIES) : numeric;
  const truncNote = truncated ? (
    <p className="chart-trunc">
      Showing first {MAX_CATEGORIES} of {numeric.length.toLocaleString()} categories.
    </p>
  ) : null;

  if (chart_type === "pie") {
    return (
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <Pie
              data={data}
              dataKey={y_column}
              nameKey={x_column}
              cx="50%"
              cy="50%"
              outerRadius={120}
              innerRadius={56}
              paddingAngle={1}
              stroke={PAPER_RAISED}
              strokeWidth={2}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={SERIES[i % SERIES.length]} />
              ))}
            </Pie>
            <Tooltip {...tooltipStyle} />
            <Legend wrapperStyle={legendStyle} />
          </PieChart>
        </ResponsiveContainer>
        {caption}
        {truncNote}
      </div>
    );
  }

  // Many categories: angle the labels and give the axis room.
  const many = data.length > 8;

  if (chart_type === "line") {
    return (
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
          <LineChart data={data} margin={{ top: 12, right: 18, bottom: many ? 56 : 12, left: 4 }}>
            <CartesianGrid vertical={false} stroke={RULE} strokeDasharray="2 4" />
            <XAxis
              dataKey={x_column}
              tickFormatter={formatDateLabel}
              tick={axisTick}
              stroke={RULE_STRONG}
              angle={many ? -35 : 0}
              textAnchor={many ? "end" : "middle"}
              height={many ? 64 : 30}
              interval={data.length > 16 ? "preserveStartEnd" : 0}
            />
            <YAxis tick={axisTick} stroke={RULE_STRONG} width={56} />
            <Tooltip
              cursor={{ stroke: RULE_STRONG, strokeDasharray: "3 3" }}
              labelFormatter={formatDateLabel}
              {...tooltipStyle}
            />
            <Line
              type="monotone"
              dataKey={y_column}
              stroke={ACCENT}
              strokeWidth={2}
              dot={data.length > 30 ? false : { r: 3, fill: ACCENT, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: ACCENT }}
            />
          </LineChart>
        </ResponsiveContainer>
        {caption}
      </div>
    );
  }

  // ---- BAR (default for categorical × numeric) --------------------------------
  return (
    <div className="chart-frame">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart data={data} margin={{ top: 12, right: 18, bottom: many ? 56 : 12, left: 4 }}>
          <CartesianGrid vertical={false} stroke={RULE} strokeDasharray="2 4" />
          <XAxis
            dataKey={x_column}
            tickFormatter={formatDateLabel}
            tick={axisTick}
            stroke={RULE_STRONG}
            angle={many ? -35 : 0}
            textAnchor={many ? "end" : "middle"}
            height={many ? 64 : 30}
            interval={data.length > 24 ? "preserveStartEnd" : 0}
          />
          <YAxis tick={axisTick} stroke={RULE_STRONG} width={56} />
          <Tooltip cursor={{ fill: "rgba(168,52,27,0.07)" }} {...tooltipStyle} />
          <Bar dataKey={y_column} fill={ACCENT} maxBarSize={56} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {caption}
      {truncNote}
    </div>
  );
}

/** A light check the result panel uses to annotate the Table/Chart toggle: does the
 *  backend's decision name a real chart type? (The deeper unmappable cases are still
 *  handled honestly inside ChartView when the user actually opens the Chart view.) */
export function hasChart(config: ChartConfig | null): boolean {
  return !!config && !!config.chart_type && config.chart_type !== "none";
}
