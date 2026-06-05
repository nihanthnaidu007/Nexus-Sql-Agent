/**
 * Intelligence strip (Phase 10) — the system's reasoning, made glanceable.
 *
 * Every value here is a field the backend ALREADY returns in /run and that
 * normalize() used to discard. The strip stops discarding them and surfaces what
 * the system DID with the question: the intent it saw, whether it hit the semantic
 * cache (and how similar), the entities it extracted, how many few-shots it loaded,
 * how many self-corrections it took, and a COMPACT confidence read. This is the
 * trust model made glanceable — the full reasoning still lives in ConfidenceBanner
 * below; the strip is a one-look summary, consistent with it (same level + colors).
 *
 * Design: the Engineering Ledger language — warm paper, hairline rules, mono micro-
 * labels. A single compact strip of labeled cells, NOT a neon dashboard. Restraint
 * is the requirement: it must read at a glance without competing with the SQL /
 * result / insight for attention.
 *
 * Honesty over decoration: render ONLY populated fields. A null intent omits its
 * cell; empty entities omit the whole pills row (no empty container); similarity
 * shows only on a real cache hit (the backend reports 0.0 on a miss — never shown).
 */
import type { NormalizedResult } from "@/lib/api";

/** READ / WRITE / SCHEMA_QUESTION → a calm, human badge label. */
const INTENT_LABEL: Record<string, string> = {
  READ: "Read",
  WRITE: "Write",
  SCHEMA_QUESTION: "Schema",
};

/** Categorical level → the same accent family the ConfidenceBanner uses. */
const CONF: Record<string, { label: string; tone: string }> = {
  HIGH: { label: "High", tone: "ok" },
  MEDIUM: { label: "Medium", tone: "warn" },
  LOW: { label: "Low", tone: "low" },
};

const ENTITY_CAP = 8; // show the first ~8; the rest collapse into "+N more".

function fmtScore(n: number): string {
  return n.toFixed(2);
}

export function IntelligenceStrip({ result }: { result: NormalizedResult }) {
  const {
    intentClass,
    cacheHit,
    cacheSimilarity,
    confidence,
    confidenceScore,
    fewShotCount,
    correctionAttempts,
    extractedEntities,
  } = result;

  const confLevel = (confidence ?? "").toUpperCase();
  const conf = CONF[confLevel] ?? null;

  const shown = extractedEntities.slice(0, ENTITY_CAP);
  const moreCount = extractedEntities.length - shown.length;

  return (
    <div className="intel" aria-label="What the system did">
      <div className="intel-row">
        {/* INTENT — omitted entirely if the backend didn't classify one. */}
        {intentClass && (
          <div className="intel-cell">
            <span className="intel-key">Intent</span>
            <span className="intel-val">
              <span className="intel-badge">
                {INTENT_LABEL[intentClass] ?? intentClass}
              </span>
            </span>
          </div>
        )}

        {/* CACHE — hit shows the similarity score; a miss is a plain "computed". */}
        <div className="intel-cell">
          <span className="intel-key">Cache</span>
          <span className={`intel-val${cacheHit ? " is-hit" : ""}`}>
            {cacheHit ? (
              <>
                cached
                {cacheSimilarity != null && (
                  <span className="intel-sub"> · {fmtScore(cacheSimilarity)}</span>
                )}
              </>
            ) : (
              "computed"
            )}
          </span>
        </div>

        {/* CONFIDENCE — compact read (dot + level + score); the full reasons stay
            in the ConfidenceBanner below. Same level/colors → consistent. */}
        {conf && (
          <div className="intel-cell">
            <span className="intel-key">Confidence</span>
            <span className="intel-val">
              <span
                className={`intel-dot intel-dot-${conf.tone}`}
                aria-hidden
              />
              {conf.label}
              {confidenceScore != null && confidenceScore > 0 && (
                <span className="intel-sub"> · {fmtScore(confidenceScore)}</span>
              )}
            </span>
          </div>
        )}

        {/* FEW-SHOTS — count of similar examples loaded (0 is meaningful). */}
        <div className="intel-cell">
          <span className="intel-key">Few-shots</span>
          <span className="intel-val">
            {fewShotCount} {fewShotCount === 1 ? "example" : "examples"}
          </span>
        </div>

        {/* CORRECTIONS — 0 signals a clean first pass; the backend caps at 3. */}
        <div className="intel-cell">
          <span className="intel-key">Corrections</span>
          <span className="intel-val">
            {correctionAttempts === 0 ? "0" : `${correctionAttempts} / 3`}
          </span>
        </div>
      </div>

      {/* ENTITIES — omitted (not shown empty) when nothing was extracted. */}
      {shown.length > 0 && (
        <div className="intel-entities">
          <span className="intel-key">Entities</span>
          <span className="intel-pills">
            {shown.map((e, i) => (
              <span className="intel-pill" key={`${e}-${i}`}>
                {e}
              </span>
            ))}
            {moreCount > 0 && (
              <span className="intel-pill intel-pill-more">+{moreCount} more</span>
            )}
          </span>
        </div>
      )}
    </div>
  );
}
