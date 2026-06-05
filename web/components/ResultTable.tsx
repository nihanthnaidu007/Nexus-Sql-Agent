/**
 * The result set as a real <table>: semantic header, aligned columns, right-
 * aligned numerics, a clear empty state, and column/row-overflow handling (the
 * table scrolls horizontally inside its frame rather than blowing out the page).
 */

const ROW_CAP = 100; // keep the DOM sane; note the true total below.

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
  // Empty state — distinct from an error: the query ran and returned nothing.
  if (!rows || rows.length === 0) {
    return (
      <div className="empty">
        The query ran successfully and returned no rows.
      </div>
    );
  }

  const cols = columns.length > 0 ? columns : Object.keys(rows[0]);
  const shown = rows.slice(0, ROW_CAP);

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
              <tr key={ri}>
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
      {rows.length > ROW_CAP && (
        <div className="table-cap">
          Showing first {ROW_CAP} of {rowCount.toLocaleString()} rows.
        </div>
      )}
    </>
  );
}
