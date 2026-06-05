"use client";

import { useState } from "react";
import { highlightSql } from "@/lib/sql-highlight";

/** The generated SQL — a first-class, dark slab with syntax color + copy. */
export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked (e.g. insecure context) — fail quietly, no crash */
    }
  }

  return (
    <div className="sql-slab">
      <button className="sql-copy" onClick={copy} aria-label="Copy SQL to clipboard">
        {copied ? "Copied" : "Copy"}
      </button>
      <pre>
        <code>{highlightSql(sql)}</code>
      </pre>
    </div>
  );
}
