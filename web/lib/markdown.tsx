/**
 * Minimal inline-markdown renderer — hand-rolled, zero dependencies.
 *
 * The insight text (the `explanation` field) can contain markdown emphasis such
 * as **bold**, *italic*, and `code`. The requirement is to render that as
 * formatted text — never show raw `**` to the user — without pulling in a full
 * markdown library. This handles inline emphasis + paragraph breaks, which is all
 * the explanation uses. Anything it doesn't recognize renders as plain text.
 */
import { Fragment, type ReactNode } from "react";

// Matches **bold**, *italic* / _italic_, and `code` (bold checked before italic).
const INLINE = /(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(_([^_]+)_)|(`([^`]+)`)/g;

function renderInline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  INLINE.lastIndex = 0;

  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const key = `${keyBase}-${i++}`;
    if (m[2] !== undefined) {
      nodes.push(<strong key={key}>{m[2]}</strong>);
    } else if (m[4] !== undefined) {
      nodes.push(<em key={key}>{m[4]}</em>);
    } else if (m[6] !== undefined) {
      nodes.push(<em key={key}>{m[6]}</em>);
    } else if (m[8] !== undefined) {
      nodes.push(<code key={key}>{m[8]}</code>);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** Render markdown-ish prose: blank lines split paragraphs; inline emphasis applied. */
export function renderMarkdown(text: string): ReactNode {
  if (!text) return null;
  const paragraphs = text.trim().split(/\n{2,}/);
  return paragraphs.map((para, pi) => (
    <p key={pi} style={{ margin: pi === 0 ? 0 : "0.7em 0 0" }}>
      {renderInline(para.replace(/\n/g, " "), `p${pi}`)}
    </p>
  ));
}
