/**
 * Confidence banner — the trust model made visible.
 *
 * Shows the categorical level (HIGH / MEDIUM / LOW) AND the legible reasons the
 * backend derived (nixus/utils/confidence.py). Framing matters: confidence is a
 * FEATURE, not a disclaimer. LOW/MEDIUM are honest, deliberate verdicts — NOT
 * errors — so none of these use an alarm tone. HIGH is reachable only by the clean
 * path (no clarification, no self-correction, grounded cleanly), so when there are
 * no downgrade reasons we state that clean path plainly rather than showing blank.
 */

const COPY: Record<string, { label: string; lede: string }> = {
  HIGH: {
    label: "High confidence",
    lede: "Answered on the clean path — no clarification needed, no self-correction, grounded cleanly.",
  },
  MEDIUM: {
    label: "Medium confidence",
    lede: "Answered, with one signal worth knowing:",
  },
  LOW: {
    label: "Low confidence",
    lede: "Answered, but the system is being upfront about its uncertainty:",
  },
  UNKNOWN: {
    label: "Confidence",
    lede: "",
  },
};

export function ConfidenceBanner({
  level,
  reasons,
  cached,
}: {
  level: string | null;
  reasons: string[];
  cached?: boolean;
}) {
  const norm = (level ?? "UNKNOWN").toUpperCase();
  const cls =
    norm === "HIGH"
      ? "conf-high"
      : norm === "MEDIUM"
        ? "conf-medium"
        : norm === "LOW"
          ? "conf-low"
          : "conf-unknown";
  const copy = COPY[norm] ?? COPY.UNKNOWN;
  const hasReasons = reasons.length > 0;

  return (
    <div className={`conf-banner ${cls}`}>
      <div className="conf-head">
        <span className="conf-marker" aria-hidden />
        <span className="conf-level">{copy.label}</span>
        {cached && <span className="tag">result preview · cached</span>}
      </div>
      {/* HIGH with no downgrade reasons → state the clean path; else list reasons. */}
      {!hasReasons ? (
        copy.lede && <p className="conf-lede">{copy.lede}</p>
      ) : (
        <>
          {copy.lede && <p className="conf-lede">{copy.lede}</p>}
          <ul className="conf-reasons">
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
