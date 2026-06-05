/**
 * Tiny SQL syntax highlighter — hand-rolled, zero dependencies.
 *
 * The skill says a lightweight highlighter is fine but NOT a heavy code editor.
 * This ~70-line tokenizer keyword/string/number/comment-colors SQL into <span>s.
 * It is presentation-only and never throws on odd input (worst case: plain text).
 */
import { Fragment, type ReactNode } from "react";

const KEYWORDS = new Set(
  (
    "select from where group by order having limit offset join inner left right " +
    "full outer on as and or not in is null like ilike between distinct union all " +
    "case when then else end count sum avg min max coalesce cast over partition " +
    "asc desc with insert update delete into values set exists any using cross " +
    "lateral except intersect filter window rows range current row preceding following"
  ).split(/\s+/),
);

// One pass: comments, single-quoted strings, double-quoted idents, numbers, words, other.
const TOKEN = /(--[^\n]*)|('(?:''|[^'])*')|("(?:[^"])*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|([^\s])/g;

export function highlightSql(sql: string): ReactNode {
  if (!sql) return null;
  const out: ReactNode[] = [];
  let m: RegExpExecArray | null;
  let i = 0;
  TOKEN.lastIndex = 0;

  while ((m = TOKEN.exec(sql)) !== null) {
    const [, comment, str, dq, num, word, ws, other] = m;
    const key = i++;

    if (comment) {
      out.push(<span key={key} className="tok-comment">{comment}</span>);
    } else if (str || dq) {
      out.push(<span key={key} className="tok-str">{str ?? dq}</span>);
    } else if (num) {
      out.push(<span key={key} className="tok-num">{num}</span>);
    } else if (word) {
      const lower = word.toLowerCase();
      if (KEYWORDS.has(lower)) {
        out.push(<span key={key} className="tok-kw">{word}</span>);
      } else {
        // An identifier immediately followed by "(" reads as a function call.
        const next = sql[TOKEN.lastIndex];
        if (next === "(") {
          out.push(<span key={key} className="tok-fn">{word}</span>);
        } else {
          out.push(<Fragment key={key}>{word}</Fragment>);
        }
      }
    } else {
      out.push(<Fragment key={key}>{ws ?? other}</Fragment>);
    }
  }
  return out;
}
