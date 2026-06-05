"use client";

/**
 * The result set as a real <table>: semantic header, aligned columns, right-
 * aligned numerics, a clear empty state, and column/row-overflow handling (the
 * table scrolls horizontally inside its frame rather than blowing out the page).
 *
 * Phase 13 (B9): rows are PAGED client-side over the data already in the response —
 * prev/next + "Page X of Y", no refetch. We page over `rows` (what was actually
 * returned). On a cache PREVIEW the response carries only a subset of the true total:
 * we page that subset and label it as a preview, never implying more rows than came
 * back. The header still names the true `rowCount` and the cache-preview origin.
 */

import { useEffect, useState } from "react";

const PAGE_SIZE = 50; // rows per page — keeps the DOM light and the table scannable.

function isNumeric(v: unknown): boolean {
  return typeof v === "number" || (typeof v === "string" && v.trim() !== "" && !isNaN(Number(v)));
}

function display(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function ResultTable({
  columns,
  rows,
  rowCount,
  cached,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  cached?: boolean;
}) {
  const [page, setPage] = useState(1);
  // Reset to the first page whenever the underlying rows change — e.g. an edited
  // re-run (B6) patches in a new result set, or a fresh query replaces this one.
  useEffect(() => {
    setPage(1);
  }, [rows]);

  // Empty state — distinct from an error: the query ran and returned nothing.
  if (!rows || rows.length === 0) {
    return (
      <div className="empty">
        The query ran successfully and returned no rows.
      </div>
    );
  }

  const cols = columns.length > 0 ? columns : Object.keys(rows[0]);
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), totalPages);
  const start = (current - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, rows.length);
  const shown = rows.slice(start, end);
  const paged = rows.length > PAGE_SIZE;

  return (
    <>
      <div className="table-meta">
        {rowCount.toLocaleString()} row{rowCount === 1 ? "" : "s"}
        {" · "}
        {cols.length} column{cols.length === 1 ? "" : "s"}
        {cached ? " · result preview (served from cache)" : ""}
      </div>
      <div className="table-scroll">
        <table className="result">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, ri) => (
              <tr key={start + ri}>
                {cols.map((c) => {
                  const v = row[c];
                  const isNull = v === null || v === undefined;
                  const cls = isNull ? "null" : isNumeric(v) ? "num" : undefined;
                  return (
                    <td key={c} className={cls}>
                      {display(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {paged && (
        <nav className="pager" aria-label="Result pages">
          <button
            type="button"
            className="pager-btn"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={current <= 1}
          >
            ‹ Prev
          </button>
          <span className="pager-status">
            Page {current} of {totalPages}
            <span className="pager-range">
              {" · "}rows {(start + 1).toLocaleString()}–{end.toLocaleString()}
              {cached ? " of preview" : ` of ${rows.length.toLocaleString()}`}
            </span>
          </span>
          <button
            type="button"
            className="pager-btn"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={current >= totalPages}
          >
            Next ›
          </button>
        </nav>
      )}
    </>
  );
}
