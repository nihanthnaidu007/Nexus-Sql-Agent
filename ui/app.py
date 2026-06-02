"""
NIXUS SQL — Streamlit UI
Quantum Terminal design: deep-space mission control.
"""
import base64
import html
import json
import struct
import streamlit as st
import requests
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nixus.utils.sql_formatter import highlight_sql, format_sql_pretty
from nixus.utils.confidence import confidence_badge

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

# Dtype → (struct fmt char, byte size) for Plotly typed-array decoding
_PLOTLY_DTYPE_MAP = {
    "f4": ("f", 4), "f8": ("d", 8),
    "i1": ("b", 1), "i2": ("h", 2), "i4": ("i", 4), "i8": ("q", 8),
    "u1": ("B", 1), "u2": ("H", 2), "u4": ("I", 4), "u8": ("Q", 8),
}


def _decode_plotly_typed_arrays(obj):
    """Recursively decode Plotly binary typed-array dicts to plain Python lists."""
    if isinstance(obj, dict):
        if "dtype" in obj and "bdata" in obj and obj["dtype"] in _PLOTLY_DTYPE_MAP:
            fmt, sz = _PLOTLY_DTYPE_MAP[obj["dtype"]]
            raw = base64.b64decode(obj["bdata"])
            n = len(raw) // sz
            return list(struct.unpack(f"<{n}{fmt}", raw))
        return {k: _decode_plotly_typed_arrays(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_plotly_typed_arrays(v) for v in obj]
    return obj


def _load_plotly_fig(plotly_json_str: str):
    """Safely load a Plotly figure from JSON, handling binary typed-array encoding."""
    import plotly.graph_objects as go
    fig_dict = _decode_plotly_typed_arrays(json.loads(plotly_json_str))
    return go.Figure(fig_dict)

st.set_page_config(
    page_title="NIXUS SQL",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

CSS_TOKENS = """
:root {
    --void:           #00000f;
    --deep:           #05071a;
    --surface:        #080c22;
    --surface-raised: #0c1030;
    --border-dim:     rgba(0, 212, 255, 0.08);
    --border-mid:     rgba(0, 212, 255, 0.20);
    --border-active:  rgba(0, 212, 255, 0.45);
    --border-glow:    rgba(0, 212, 255, 0.70);
    --cyan:           #00d4ff;
    --cyan-dim:       rgba(0, 212, 255, 0.12);
    --cyan-glow:      rgba(0, 212, 255, 0.30);
    --violet:         #7c3aed;
    --violet-dim:     rgba(124, 58, 237, 0.18);
    --violet-bright:  #a78bfa;
    --magenta:        #e879f9;
    --neon-green:     #00ff88;
    --green-dim:      rgba(0, 255, 136, 0.15);
    --amber:          #ffb800;
    --amber-dim:      rgba(255, 184, 0, 0.15);
    --red:            #ff4466;
    --red-dim:        rgba(255, 68, 102, 0.12);
    --text-primary:   #e0f4ff;
    --text-secondary: #7ba3c0;
    --text-muted:     #2d4a61;
    --code-keyword:   #c084fc;
    --code-fn:        #67e8f9;
    --code-string:    #86efac;
    --code-number:    #fde68a;
    --code-alias:     #f0abfc;
    --code-comment:   #4a6a7d;
}
"""

FULL_CSS = """
.stApp { background: var(--void) !important; }
.block-container { padding-top: 1rem !important; position: relative; z-index: 1; max-width: 1400px !important; }
[data-testid="stSidebar"] { display: none; }

.nixus-topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 0 20px; border-bottom: 1px solid var(--border-dim);
    margin-bottom: 24px;
}
.nixus-logo { font-family: 'Syne', sans-serif; font-size: 1.4rem; font-weight: 800;
    color: var(--cyan); letter-spacing: 0.08em; }
.nixus-tagline { font-family: 'Outfit', sans-serif; font-size: 0.75rem;
    color: var(--text-muted); letter-spacing: 0.15em; text-transform: uppercase; }
.nixus-status-dot { width: 8px; height: 8px; border-radius: 50%;
    background: var(--neon-green); box-shadow: 0 0 8px var(--neon-green);
    display: inline-block; margin-right: 6px; }
.nixus-status-dot.offline { background: var(--red); box-shadow: 0 0 8px var(--red); }

.nixus-command-wrap { position: relative; margin: 0 auto 32px; max-width: 820px; }
.nixus-command-wrap::before {
    content: '◈'; position: absolute; left: 18px; top: 50%;
    transform: translateY(-50%); color: var(--cyan); font-size: 1rem;
    z-index: 2; pointer-events: none;
}
.stTextInput input {
    background: var(--surface) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 12px !important; padding: 16px 18px 16px 46px !important;
    color: var(--text-primary) !important;
    font-family: 'Outfit', sans-serif !important; font-size: 1rem !important;
    box-shadow: 0 0 0 0 rgba(0,212,255,0), inset 0 1px 0 rgba(255,255,255,0.03) !important;
    transition: all 0.3s ease !important;
}
.stTextInput input:focus {
    border-color: var(--border-active) !important;
    box-shadow: 0 0 0 3px var(--cyan-dim), 0 0 24px var(--cyan-glow) !important;
}
.stTextInput label { color: var(--text-muted) !important; font-family: 'Outfit', sans-serif !important; }

.nixus-pill {
    display: inline-block; padding: 4px 12px; margin: 4px;
    border: 1px solid var(--border-dim); border-radius: 20px;
    font-family: 'Outfit', sans-serif; font-size: 0.72rem;
    color: var(--text-muted); cursor: pointer; transition: all 0.2s ease;
    background: transparent;
}

/* Example pill buttons */
div[data-testid="stHorizontalBlock"] .stButton > button {
    background: transparent !important;
    border: 1px solid var(--border-dim) !important;
    border-radius: 20px !important;
    color: var(--text-muted) !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 400 !important;
    letter-spacing: 0 !important;
    padding: 4px 10px !important;
    transition: all 0.2s ease !important;
    box-shadow: none !important;
    height: auto !important;
    min-height: 0 !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
    border-color: var(--border-active) !important;
    color: var(--cyan) !important;
    background: var(--cyan-dim) !important;
    box-shadow: none !important;
}

.intel-card {
    background: var(--surface); border: 1px solid var(--border-dim);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
    height: 100%;
}
.intel-label { font-family: 'Syne', sans-serif; font-size: 0.65rem;
    color: var(--text-muted); letter-spacing: 0.12em; text-transform: uppercase;
    margin-bottom: 12px; }

.sm-node {
    display: inline-block; padding: 5px 12px; border-radius: 6px;
    font-family: 'Fira Code', monospace; font-size: 0.68rem;
    border: 1px solid; transition: all 0.3s ease; margin: 3px;
}
.sm-node.done    { border-color: var(--neon-green); color: var(--neon-green); background: var(--green-dim); }
.sm-node.running { border-color: var(--cyan); color: var(--cyan); background: var(--cyan-dim);
    animation: nodePulse 1.0s ease-out infinite; }
.sm-node.pending { border-color: var(--border-dim); color: var(--text-muted); background: transparent; }
.sm-node.error   { border-color: var(--red); color: var(--red); background: var(--red-dim); }
.sm-node.skip    { border-color: rgba(45,74,97,0.5); color: var(--text-muted); background: transparent;
    opacity: 0.4; text-decoration: line-through; }
@keyframes nodePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0,212,255,0.5); }
    50%       { box-shadow: 0 0 0 6px rgba(0,212,255,0); }
}

/* Streaming pulse indicator */
@keyframes streamPulse {
    0%, 100% {
        opacity: 0.4;
        transform: scale(1);
    }
    50% {
        opacity: 1;
        transform: scale(1.05);
    }
}
.streaming-indicator {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border: 1px solid var(--cyan);
    border-radius: 20px;
    background: var(--cyan-dim);
    font-family: 'Fira Code', monospace;
    font-size: 0.72rem;
    color: var(--cyan);
    animation: streamPulse 1.2s ease-in-out infinite;
}
.streaming-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--cyan);
    box-shadow: 0 0 6px var(--cyan);
}

.sql-panel {
    background: var(--surface); border: 1px solid var(--border-mid);
    border-radius: 12px; overflow: hidden; margin-bottom: 16px;
}
.sql-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; background: rgba(0,212,255,0.04);
    border-bottom: 1px solid var(--border-dim); font-family: 'Syne', sans-serif;
    font-size: 0.65rem; color: var(--text-muted); letter-spacing: 0.12em;
}
.sql-body { padding: 16px; overflow-x: auto; }
.sql-line { display: flex; align-items: flex-start; min-height: 24px; }
.sql-lineno { color: var(--text-muted); font-size: 0.72rem; min-width: 28px;
    font-family: 'Fira Code', monospace; user-select: none; padding-right: 12px; }
.sql-code  { font-family: 'Fira Code', monospace; font-size: 0.82rem;
    color: var(--text-primary); line-height: 1.7; white-space: pre; }
.sql-keyword { color: var(--code-keyword); font-weight: 600; }
.sql-fn      { color: var(--code-fn); }
.sql-str     { color: var(--code-string); }
.sql-num     { color: var(--code-number); }
.sql-alias   { color: var(--code-alias); }
.sql-comment { color: var(--code-comment); font-style: italic; }

.conf-track { height: 4px; background: var(--border-dim); border-radius: 2px;
    overflow: hidden; margin: 8px 0; }
.conf-fill  { height: 100%; border-radius: 2px; }
.conf-fill.high   { background: var(--neon-green); box-shadow: 0 0 8px rgba(0,255,136,0.5); }
.conf-fill.medium { background: var(--amber); box-shadow: 0 0 8px rgba(255,184,0,0.4); }
.conf-fill.low    { background: var(--red); box-shadow: 0 0 8px rgba(255,68,102,0.4); }

.badge { display: inline-block; padding: 2px 10px; border-radius: 4px;
    font-family: 'Syne', sans-serif; font-size: 0.65rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase; border: 1px solid; }
.badge.high   { color: var(--neon-green); border-color: var(--neon-green); background: var(--green-dim); }
.badge.medium { color: var(--amber); border-color: var(--amber); background: var(--amber-dim); }
.badge.low    { color: var(--red); border-color: var(--red); background: var(--red-dim); }
.badge.cache  { color: var(--violet-bright); border-color: var(--violet); background: var(--violet-dim); }
.badge.read   { color: var(--cyan); border-color: var(--cyan); background: var(--cyan-dim); }
.badge.write  { color: var(--red); border-color: var(--red); background: var(--red-dim); }
.badge.schema { color: var(--amber); border-color: var(--amber); background: var(--amber-dim); }

.result-table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid var(--border-dim); }
.result-table { width: 100%; border-collapse: collapse; font-family: 'Outfit', sans-serif; font-size: 0.82rem; }
.result-table thead tr { background: rgba(0,212,255,0.06); border-bottom: 1px solid var(--border-mid); }
.result-table th { padding: 10px 14px; color: var(--cyan); font-family: 'Syne', sans-serif;
    font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; text-align: left; }
.result-table td { padding: 9px 14px; color: var(--text-primary); border-bottom: 1px solid var(--border-dim); }
.result-table tr { animation: cellMaterialize 0.2s ease-out both; }
.result-table tr:nth-child(1)  { animation-delay: 0.05s; }
.result-table tr:nth-child(2)  { animation-delay: 0.10s; }
.result-table tr:nth-child(3)  { animation-delay: 0.15s; }
.result-table tr:nth-child(4)  { animation-delay: 0.20s; }
.result-table tr:nth-child(5)  { animation-delay: 0.25s; }
.result-table tr:nth-child(6)  { animation-delay: 0.30s; }
.result-table tr:nth-child(7)  { animation-delay: 0.35s; }
.result-table tr:nth-child(8)  { animation-delay: 0.40s; }
.result-table tr:nth-child(9)  { animation-delay: 0.45s; }
.result-table tr:nth-child(10) { animation-delay: 0.50s; }
.result-table tr:hover { background: rgba(0,212,255,0.04); }
@keyframes cellMaterialize {
    from { opacity: 0; transform: translateY(-6px); filter: blur(2px); }
    to   { opacity: 1; transform: translateY(0);    filter: blur(0); }
}

.chart-panel { animation: chartEmerge 0.6s cubic-bezier(0.34,1.56,0.64,1) 0.1s both; }
@keyframes chartEmerge {
    from { opacity: 0; transform: translateY(32px) scale(0.97); }
    60%  { transform: translateY(-3px) scale(1.004); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}

.insight-card {
    background: var(--surface); border: 1px solid rgba(0,212,255,0.25);
    border-radius: 12px; padding: 20px 24px;
    box-shadow: 0 0 32px rgba(0,212,255,0.06);
    animation: insightGlow 0.8s ease-out 0.3s both; margin-top: 16px;
}
@keyframes insightGlow {
    from { opacity: 0; box-shadow: 0 0 0 rgba(0,212,255,0); border-color: rgba(0,212,255,0); }
    to   { opacity: 1; box-shadow: 0 0 32px rgba(0,212,255,0.08); border-color: rgba(0,212,255,0.25); }
}
.insight-label { font-family: 'Syne', sans-serif; font-size: 0.65rem; color: var(--cyan);
    letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px; }
.insight-text  { font-family: 'Outfit', sans-serif; font-size: 0.92rem;
    color: var(--text-primary); line-height: 1.7; }

.correction-item { border-left: 2px solid var(--red); padding-left: 14px; margin-bottom: 14px; }
.correction-attempt { font-family: 'Syne', sans-serif; font-size: 0.65rem; color: var(--red);
    letter-spacing: 0.1em; margin-bottom: 4px; }
.correction-reason { font-family: 'Outfit', sans-serif; font-size: 0.8rem;
    color: var(--text-secondary); font-style: italic; margin-bottom: 6px; }

.intel-strip {
    margin-top: 40px; padding: 14px 20px;
    background: rgba(5,7,26,0.8); border-top: 1px solid var(--border-dim);
    display: flex; align-items: center; justify-content: space-between;
    font-family: 'Fira Code', monospace; font-size: 0.72rem; color: var(--text-muted);
}
.intel-strip span.val { color: var(--cyan); }

.error-card { background: var(--red-dim); border: 1px solid var(--red);
    border-radius: 12px; padding: 16px 20px; }
.error-title { font-family: 'Syne', sans-serif; color: var(--red);
    font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; }
.error-msg { font-family: 'Fira Code', monospace; font-size: 0.8rem; color: var(--text-primary); }

.safety-warning { background: rgba(255,68,102,0.08); border: 1px solid var(--red);
    border-radius: 12px; padding: 20px 24px; text-align: center;
    animation: dangerPulse 2s ease-in-out infinite; }
@keyframes dangerPulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(255,68,102,0.3); }
    50%      { box-shadow: 0 0 0 12px rgba(255,68,102,0); }
}

.stButton > button {
    background: var(--cyan-dim) !important; border: 1px solid var(--border-active) !important;
    color: var(--cyan) !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; letter-spacing: 0.08em !important; border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: rgba(0,212,255,0.2) !important;
    box-shadow: 0 0 16px var(--cyan-glow) !important;
}
.stTextArea textarea {
    background: var(--surface) !important; border: 1px solid var(--border-mid) !important;
    color: var(--text-primary) !important; font-family: 'Fira Code', monospace !important;
    border-radius: 8px !important;
}
.stExpander { border: 1px solid var(--border-dim) !important; border-radius: 8px !important; background: var(--surface) !important; }
.stExpander summary { color: var(--text-secondary) !important; font-family: 'Outfit', sans-serif !important; }
div[data-testid="column"] { padding: 0 8px; }
h1, h2, h3 { color: var(--text-primary) !important; font-family: 'Syne', sans-serif !important; }
p, li { color: var(--text-secondary) !important; font-family: 'Outfit', sans-serif !important; }

.trace-link {
    font-family: 'Fira Code', monospace;
    font-size: 0.72rem;
    color: var(--cyan);
    text-decoration: none;
    border-bottom: 1px solid rgba(0,212,255,0.3);
    padding-bottom: 1px;
    transition: all 0.2s ease;
}
.trace-link:hover {
    color: var(--magenta);
    border-bottom-color: var(--magenta);
}
.trace-id-text {
    font-family: 'Fira Code', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
}
.trace-disabled {
    font-family: 'Fira Code', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    font-style: italic;
}
.insight-footer {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--border-dim);
    font-family: 'Fira Code', monospace;
    font-size: 0.68rem;
}

/* Write approval modal */
.approval-modal {
    background: rgba(255, 68, 102, 0.05);
    border: 1px solid var(--red);
    border-radius: 12px;
    padding: 24px 28px;
    margin: 24px 0;
    animation: dangerPulse 2s ease-in-out infinite;
}
.approval-modal-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--red);
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.approval-modal-sub {
    font-family: 'Outfit', sans-serif;
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-bottom: 16px;
}
.approval-operation {
    display: inline-block;
    font-family: 'Fira Code', monospace;
    font-size: 0.85rem;
    color: var(--red);
    background: var(--red-dim);
    border: 1px solid var(--red);
    border-radius: 6px;
    padding: 4px 14px;
    margin-bottom: 20px;
}
"""

PARTICLE_HTML = """
<canvas id="nixus-particles" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:0.5;"></canvas>
<script>
(function() {
  const canvas = document.getElementById('nixus-particles');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W = canvas.width = window.innerWidth;
  let H = canvas.height = window.innerHeight;
  const CYAN = {r:0, g:212, b:255};
  const VIOLET = {r:124, g:58, b:237};
  const N = 70;
  const CONNECT_DIST = 120;
  const particles = Array.from({length: N}, () => ({
    x: Math.random() * W, y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25,
    r: Math.random() * 1.5 + 0.5, opacity: Math.random() * 0.4 + 0.15,
    color: Math.random() > 0.7 ? VIOLET : CYAN
  }));
  function draw() {
    ctx.clearRect(0, 0, W, H);
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < CONNECT_DIST) {
          const alpha = (1 - dist / CONNECT_DIST) * 0.15;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(0,212,255,${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
    particles.forEach(p => {
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.color.r},${p.color.g},${p.color.b},${p.opacity})`;
      ctx.shadowBlur = 6; ctx.shadowColor = `rgba(${p.color.r},${p.color.g},${p.color.b},0.4)`;
      ctx.fill(); ctx.shadowBlur = 0;
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
    });
    requestAnimationFrame(draw);
  }
  window.addEventListener('resize', () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; });
  draw();
})();
</script>
"""

# ── Inject fonts + CSS ──────────────────────────────────────────────────────
st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Outfit:wght@300;400;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS_TOKENS}{FULL_CSS}</style>
""")

# ── Particle background ─────────────────────────────────────────────────────
st.iframe(PARTICLE_HTML, height=1)

# ── Session state ───────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "result" not in st.session_state:
    st.session_state.result = None
if "show_chart" not in st.session_state:
    st.session_state.show_chart = False
if "edit_sql_mode" not in st.session_state:
    st.session_state.edit_sql_mode = False
if "edited_sql" not in st.session_state:
    st.session_state.edited_sql = ""
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "query_input" not in st.session_state:
    st.session_state.query_input = ""
if "streaming" not in st.session_state:
    st.session_state.streaming = False
if "partial_state" not in st.session_state:
    st.session_state.partial_state = {}
if "trigger_run" not in st.session_state:
    st.session_state.trigger_run = False
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None


@st.cache_data(ttl=60)
def get_health():
    try:
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=3)
        return r.json()
    except Exception:
        return {"status": "error", "db_connected": False}


@st.cache_data(ttl=30)
def get_stats():
    try:
        cache_r = requests.get(f"{API_BASE}/api/v1/cache-stats", timeout=3)
        fewshot_r = requests.get(f"{API_BASE}/api/v1/fewshot-stats", timeout=3)
        return cache_r.json(), fewshot_r.json()
    except Exception:
        return {"entries": 0, "total_hits": 0, "hit_rate": 0}, {"total": 0, "seeded": 0, "auto_learned": 0}


def run_query_streaming(user_query: str, session_id: str):
    """
    Calls /api/v1/stream and yields partial state dicts as each SSE event arrives.
    Each yielded dict represents one node completing.
    Final dict has is_complete=True.
    """
    url = f"{API_BASE}/api/v1/stream"

    try:
        with requests.post(
            url,
            json={"user_query": user_query, "session_id": session_id},
            stream=True,
            timeout=120,
            headers={"Accept": "text/event-stream"}
        ) as response:
            response.raise_for_status()

            current_event_type = "message"

            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("event:"):
                    current_event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                        data["_event_type"] = current_event_type
                        yield data
                        if data.get("is_complete"):
                            return
                    except json.JSONDecodeError:
                        continue
                elif line == "":
                    current_event_type = "message"

    except requests.exceptions.ConnectionError:
        yield {
            "error": f"Cannot connect to API server at {API_BASE}. Is FastAPI running?",
            "is_complete": True
        }
    except Exception as e:
        yield {"error": str(e), "is_complete": True}


def render_intelligence_strip(state: dict):
    """Renders intent, cache, entities, confidence from any state dict."""
    intent = state.get("intent_class", "—") or "—"
    entities = state.get("extracted_entities", [])
    cache = state.get("cache_result") or {}
    cache_hit = cache.get("hit", False)
    fewshots = state.get("similar_examples", [])
    conf = state.get("confidence_score", 0.0) or 0.0
    corrections = state.get("correction_attempts", 0) or 0

    intent_cls = intent.lower() if intent in ["READ", "WRITE", "SCHEMA_QUESTION"] else "schema"
    badge_label, badge_cls = confidence_badge(conf)

    entity_pills = " ".join(
        f'<span style="background:rgba(0,212,255,0.08);border:1px solid var(--border-dim);'
        f'padding:2px 8px;border-radius:12px;font-size:0.7rem;color:var(--text-secondary);'
        f'font-family:Outfit,sans-serif;margin:2px;display:inline-block">{html.escape(str(e))}</span>'
        for e in entities[:8]
    )

    cache_badge = (
        '<span class="badge cache" style="margin-left:8px">CACHED</span>'
        if cache_hit else
        '<span style="color:var(--text-muted);font-size:0.72rem;font-family:Fira Code,monospace">MISS</span>'
    )

    st.markdown(f"""
    <div class="intel-card">
        <div class="intel-label">◈ QUERY INTELLIGENCE</div>
        <div style="margin-bottom:12px;">
            <span style="color:var(--text-muted);font-family:Outfit,sans-serif;font-size:0.78rem;">Intent: </span>
            <span class="badge {intent_cls}">{html.escape(intent)}</span>
            &nbsp;
            <span style="color:var(--text-muted);font-family:Outfit,sans-serif;font-size:0.78rem;">Cache: </span>
            {cache_badge}
        </div>
        <div style="margin-bottom:12px;">{entity_pills if entity_pills else '<span style="color:var(--text-muted);font-size:0.75rem">No entities extracted</span>'}</div>
        <div style="color:var(--text-muted);font-family:Fira Code,monospace;font-size:0.72rem;margin-bottom:8px;">
            Few-shots: <span style="color:var(--cyan)">{len(fewshots)}</span> loaded &nbsp;·&nbsp;
            Corrections: <span style="color:{'var(--red)' if corrections > 0 else 'var(--neon-green)'}">{corrections}/3</span>
        </div>
        <div style="color:var(--text-muted);font-family:'Syne',sans-serif;font-size:0.65rem;letter-spacing:0.1em;margin-bottom:4px;">
            CONFIDENCE &nbsp;<span class="badge {badge_cls}">{badge_label}</span>
        </div>
        <div class="conf-track">
            <div class="conf-fill {badge_cls}" style="width:{conf*100:.0f}%"></div>
        </div>
        <div style="color:var(--text-muted);font-family:Fira Code,monospace;font-size:0.7rem;">{conf:.1%}</div>
    </div>
    """, unsafe_allow_html=True)


def render_node_status(state: dict):
    """Renders the state machine node badges from any state dict."""
    ALL_NODES = [
        "parse_intent", "safety_check", "check_cache", "retrieve_schema",
        "retrieve_fewshot", "generate_sql", "validate_syntax", "execute_query",
        "check_result", "self_correct", "classify_chart", "explain_result"
    ]
    CACHE_SKIPPED = {"retrieve_schema", "retrieve_fewshot", "generate_sql",
                     "validate_syntax", "execute_query", "check_result", "self_correct"}

    completed = set(state.get("completed_nodes", []))
    current_node = state.get("current_node", "")
    served_from_cache = state.get("served_from_cache", False)
    is_complete = state.get("is_complete", False)
    corrections = state.get("correction_attempts", 0) or 0

    node_html = '<div class="intel-card"><div class="intel-label">◈ STATE MACHINE</div>'
    for node in ALL_NODES:
        if node in completed:
            cls = "done"
        elif node == current_node and not is_complete:
            cls = "running"
        elif served_from_cache and node in CACHE_SKIPPED:
            cls = "skip"
        else:
            cls = "pending"
        node_html += f'<span class="sm-node {cls}">{node}</span>'

    if corrections > 0:
        node_html += f'<div style="margin-top:8px;color:var(--red);font-family:Fira Code,monospace;font-size:0.68rem;">↩ {corrections} correction(s)</div>'

    node_html += '</div>'
    st.markdown(node_html, unsafe_allow_html=True)


# ── Top bar ─────────────────────────────────────────────────────────────────
health = get_health()
db_ok = health.get("db_connected", False)
dot_class = "nixus-status-dot" if db_ok else "nixus-status-dot offline"
db_label = "DB CONNECTED" if db_ok else "DB OFFLINE"

st.markdown(f"""
<div class="nixus-topbar">
    <div>
        <div class="nixus-logo">◈ NIXUS SQL</div>
        <div class="nixus-tagline">Neural Query Intelligence</div>
    </div>
    <div style="display:flex;align-items:center;gap:16px;">
        <span style="font-family:'Fira Code',monospace;font-size:0.72rem;color:var(--text-muted);">
            <span class="{dot_class}"></span>{db_label}
        </span>
        <span style="font-family:'Fira Code',monospace;font-size:0.72rem;color:var(--text-muted);">
            LangGraph 12-NODE STATE MACHINE
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Command bar ─────────────────────────────────────────────────────────────
QUICK_EXAMPLES = [
    "Top 5 artists by total revenue",
    "Monthly invoice totals by country",
    "Tracks longer than 5 minutes",
    "Customers by country",
    "Average track length by genre",
    "Which playlists have the most tracks?"
]

st.markdown('<div class="nixus-command-wrap">', unsafe_allow_html=True)
user_query = st.text_input(
    "Query",
    value=st.session_state.query_input,
    placeholder="Ask anything about the Chinook music database...",
    key="query_field",
    label_visibility="collapsed"
)
st.markdown('</div>', unsafe_allow_html=True)

# Quick example pills — functional st.button() rows
st.markdown('<div style="margin:-16px 0 20px;">', unsafe_allow_html=True)
pill_cols = st.columns(len(QUICK_EXAMPLES))
for i, example in enumerate(QUICK_EXAMPLES):
    with pill_cols[i]:
        if st.button(example, key=f"pill_{i}", use_container_width=True):
            st.session_state.query_input = example
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

col_run, col_spacer = st.columns([1, 5])
with col_run:
    run_clicked = st.button("▶ RUN QUERY", use_container_width=True)

# ── Streaming run handler ───────────────────────────────────────────────────
if (run_clicked or st.session_state.get("trigger_run")) and user_query.strip():
    st.session_state.trigger_run = False
    st.session_state.show_chart = False
    st.session_state.edit_sql_mode = False
    st.session_state.result = None
    st.session_state.pending_approval = None
    st.session_state.streaming = True
    st.session_state.last_query = user_query
    st.session_state.partial_state = {
        "completed_nodes": [],
        "current_node": "parse_intent",
        "stream_updates": [],
        "intent_class": "",
        "extracted_entities": [],
        "tables_identified": [],
        "served_from_cache": False,
        "similar_examples": [],
        "correction_attempts": 0,
        "confidence_score": 0.0,
        "is_complete": False
    }

    # Streaming indicator
    st.markdown(
        '<div class="streaming-indicator">'
        '<div class="streaming-dot"></div>'
        'NIXUS SQL is thinking...'
        '</div>',
        unsafe_allow_html=True
    )

    # Live-updating placeholders
    intel_placeholder = st.empty()
    status_placeholder = st.empty()

    for partial in run_query_streaming(user_query, st.session_state.session_id):
        if partial.get("error") and not partial.get("is_complete"):
            st.session_state.partial_state.update(partial)
            continue

        # WRITE interrupt — graph paused waiting for approval
        if partial.get("_event_type") == "interrupted":
            st.session_state.pending_approval = partial
            st.session_state.streaming = False
            break

        st.session_state.partial_state.update(partial)

        with intel_placeholder.container():
            render_intelligence_strip(st.session_state.partial_state)

        with status_placeholder.container():
            render_node_status(st.session_state.partial_state)

        if partial.get("is_complete"):
            st.session_state.result = partial
            st.session_state.streaming = False
            break

    st.rerun()

# ── Write approval modal ────────────────────────────────────────────────────
if st.session_state.pending_approval:
    pa = st.session_state.pending_approval
    operation = pa.get("write_operation_type", "WRITE")

    st.markdown(f"""
    <div class="approval-modal">
        <div class="approval-modal-title">⚠ WRITE OPERATION REQUIRES APPROVAL</div>
        <div class="approval-modal-sub">
            The agent has generated a <strong>{html.escape(operation)}</strong> statement.
            NIXUS SQL requires explicit human approval before executing any write operation.
            Review the intent, then approve or deny below.
        </div>
        <div class="approval-operation">{html.escape(operation)}</div>
    </div>
    """, unsafe_allow_html=True)

    col_approve, col_deny, _ = st.columns([1, 1, 4])
    with col_approve:
        if st.button("✓ APPROVE", use_container_width=True):
            with st.spinner("Resuming execution with approval..."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/v1/approve-write",
                        json={"session_id": st.session_state.session_id, "approved": True},
                        timeout=60
                    )
                    result = resp.json()
                    st.session_state.result = result
                    st.session_state.pending_approval = None
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with col_deny:
        if st.button("✕ DENY", use_container_width=True):
            with st.spinner("Resuming execution with denial..."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/v1/approve-write",
                        json={"session_id": st.session_state.session_id, "approved": False},
                        timeout=60
                    )
                    result = resp.json()
                    st.session_state.result = result
                    st.session_state.pending_approval = None
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


# ── Intelligence strip + results ────────────────────────────────────────────
if st.session_state.result:
    r = st.session_state.result
    col_intel, col_nodes = st.columns(2)

    with col_intel:
        render_intelligence_strip(r)

    with col_nodes:
        render_node_status(r)

    # ── Error / WRITE safety card ──────────────────────────────────────────
    if r.get("error"):
        error_msg = html.escape(r["error"])
        if "operation blocked" in r["error"] or "approval was denied" in r["error"]:
            st.markdown(f"""
            <div class="safety-warning">
                <div style="font-family:'Syne',sans-serif;color:var(--red);font-size:1rem;font-weight:800;margin-bottom:8px;">
                    ⚠ WRITE OPERATION BLOCKED
                </div>
                <div style="font-family:'Outfit',sans-serif;color:var(--text-secondary);font-size:0.85rem;">
                    {error_msg}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="error-card">
                <div class="error-title">◈ ERROR</div>
                <div class="error-msg">{error_msg}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Results zone ───────────────────────────────────────────────────────
    sql = r.get("generated_sql", "")
    exec_result = r.get("execution_result") or {}
    rows = exec_result.get("rows", [])
    columns = exec_result.get("columns", [])
    row_count = exec_result.get("row_count", 0)
    exec_ms = exec_result.get("execution_time_ms", 0)

    if r.get("served_from_cache") and r.get("cache_result"):
        cr = r["cache_result"]
        rows = cr.get("result_preview", [])
        row_count = cr.get("row_count", 0) or len(rows)
        columns = list(rows[0].keys()) if rows else []

    if sql:
        pretty_sql = format_sql_pretty(sql)
        highlighted = highlight_sql(pretty_sql)
        tables_str = " · ".join(r.get("tables_identified", []))

        cache_indicator = ""
        if r.get("served_from_cache"):
            sim = (r.get("cache_result") or {}).get("similarity", 0)
            cache_indicator = f'<span class="badge cache" style="margin-left:8px">CACHED {sim:.2f}</span>'

        badge_label2, badge_cls2 = confidence_badge(r.get("confidence_score", 0))

        st.markdown(f"""
        <div class="sql-panel">
            <div class="sql-header">
                <span>◈ SQL &nbsp;·&nbsp; {html.escape(tables_str or 'generated query')} {cache_indicator}</span>
                <span class="badge {badge_cls2}">{badge_label2}</span>
            </div>
            {highlighted}
        </div>
        """, unsafe_allow_html=True)

        # Edit SQL
        col_edit, col_rerun, _ = st.columns([1, 1, 4])
        with col_edit:
            if st.button("✎ EDIT SQL"):
                st.session_state.edit_sql_mode = not st.session_state.edit_sql_mode
                st.session_state.edited_sql = pretty_sql
        with col_rerun:
            if st.session_state.edit_sql_mode:
                if st.button("▶ RE-RUN"):
                    with st.spinner("Executing edited SQL..."):
                        try:
                            resp2 = requests.post(
                                f"{API_BASE}/api/v1/run-sql",
                                json={"sql": st.session_state.edited_sql,
                                      "session_id": st.session_state.session_id},
                                timeout=30
                            )
                            mini = resp2.json()
                            if mini.get("execution_result"):
                                st.session_state.result["execution_result"] = mini["execution_result"]
                                st.session_state.result["chart_config"] = mini.get("chart_config")
                                st.session_state.result["generated_sql"] = st.session_state.edited_sql
                                st.rerun()
                        except Exception as e:
                            st.error(str(e))

        if st.session_state.edit_sql_mode:
            st.session_state.edited_sql = st.text_area(
                "Edit SQL",
                value=st.session_state.edited_sql,
                height=200,
                label_visibility="collapsed"
            )

    # ── View toggle (include empty successful results so headers / chart panel still render)
    show_results_panel = bool(rows) or (exec_result.get("success") and bool(columns))
    if show_results_panel:
        col_t, col_c, _ = st.columns([1, 1, 6])
        with col_t:
            if st.button("◫ TABLE", use_container_width=True):
                st.session_state.show_chart = False
        with col_c:
            if st.button("◈ CHART", use_container_width=True):
                st.session_state.show_chart = True
                st.rerun()

        if not st.session_state.show_chart:
            page_size = 50
            page = st.number_input("Page", min_value=1, max_value=max(1, (row_count + page_size - 1) // page_size),
                                   value=1, step=1) if row_count > page_size else 1
            page_rows = rows[(page-1)*page_size : page*page_size]

            colnames = columns or (list(page_rows[0].keys()) if page_rows else [])
            th_html = "".join(f"<th>{html.escape(str(c))}</th>" for c in colnames)
            if page_rows:
                td_rows = "".join(
                    "<tr>" + "".join(f"<td>{html.escape(str(v)[:100])}</td>" for v in row.values()) + "</tr>"
                    for row in page_rows
                )
            else:
                span = max(1, len(colnames))
                td_rows = (
                    f'<tr><td colspan="{span}" style="text-align:center;padding:20px;'
                    f'color:var(--text-muted);font-family:Outfit,sans-serif;">'
                    "No rows returned — if you expect demo data, run "
                    "<code style='color:var(--accent);'>python scripts/migrate_chinook.py</code>"
                    " (loads Chinook from GitHub into this database).</td></tr>"
                )
            st.markdown(f"""
            <div class="result-table-wrap">
                <table class="result-table">
                    <thead><tr>{th_html}</tr></thead>
                    <tbody>{td_rows}</tbody>
                </table>
            </div>
            <div style="color:var(--text-muted);font-family:'Fira Code',monospace;font-size:0.72rem;
                        margin-top:8px;text-align:right;">
                {row_count} rows · {exec_ms:.0f}ms
                {f'· Page {page}/{max(1,(row_count+page_size-1)//page_size)}' if row_count > page_size else ''}
            </div>
            """, unsafe_allow_html=True)
        else:
            chart_cfg = r.get("chart_config") or {}
            plotly_json = chart_cfg.get("plotly_json")
            if plotly_json:
                try:
                    fig = _load_plotly_fig(plotly_json)
                    st.markdown('<div class="chart-panel">', unsafe_allow_html=True)
                    st.markdown(f'<div style="color:var(--text-muted);font-family:Fira Code,monospace;font-size:0.72rem;margin-bottom:8px;">◈ {html.escape(chart_cfg.get("chart_type","").upper())} — {html.escape(chart_cfg.get("reasoning",""))}</div>', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    st.markdown('</div>', unsafe_allow_html=True)
                except Exception as chart_err:
                    st.markdown(
                        f'<div class="error-card"><div class="error-title">◈ CHART RENDER ERROR</div>'
                        f'<div class="error-msg">{html.escape(str(chart_err))}</div></div>',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown(
                    '<div style="color:var(--text-muted);font-family:Outfit,sans-serif;padding:24px;text-align:center;">'
                    '◈ No visualization available for this result shape</div>',
                    unsafe_allow_html=True
                )

    # ── No-rows note (table above may already show the migrate hint) ───────
    if not rows and not r.get("error") and sql and exec_result.get("success"):
        st.info(
            "◈ Query ran successfully with zero rows. If you expected demo numbers, load the "
            "Chinook sample into this database (see README: `python scripts/migrate_chinook.py`)."
        )

    # ── Insight card ──────────────────────────────────────────────────────
    explanation = r.get("explanation", "")
    if explanation:
        trace_url = r.get("trace_url")
        trace_id = r.get("trace_id")
        if trace_url:
            insight_footer = (
                f'<div class="insight-footer">'
                f'<a href="{trace_url}" target="_blank" class="trace-link">View full trace ↗</a>'
                f'</div>'
            )
        elif trace_id:
            insight_footer = (
                f'<div class="insight-footer">'
                f'<span class="trace-id-text">Trace ID: {trace_id[:8]}...</span>'
                f'</div>'
            )
        else:
            insight_footer = ""

        st.markdown(f"""
        <div class="insight-card">
            <div class="insight-label">◈ INSIGHT</div>
            <div class="insight-text">{html.escape(explanation)}</div>
            {insight_footer}
        </div>
        """, unsafe_allow_html=True)

    # ── Correction history ─────────────────────────────────────────────────
    corrections_hist = r.get("correction_history", [])
    if corrections_hist:
        with st.expander(f"Self-Correction Log ({len(corrections_hist)} attempt{'s' if len(corrections_hist) > 1 else ''})"):
            for corr in corrections_hist:
                st.markdown(f"""
                <div class="correction-item">
                    <div class="correction-attempt">ATTEMPT {corr.get('attempt',0)}</div>
                    <div class="correction-reason">{html.escape(corr.get('fix_reasoning',''))}</div>
                    <pre style="font-family:'Fira Code',monospace;font-size:0.75rem;color:var(--text-primary);
                                background:var(--surface);padding:8px;border-radius:4px;overflow-x:auto;">
{html.escape(corr.get('corrected_sql','')[:300])}</pre>
                </div>
                """, unsafe_allow_html=True)

    # ── Stream log ────────────────────────────────────────────────────────
    updates = r.get("stream_updates", [])
    if updates:
        with st.expander("Agent Execution Log"):
            for u in updates:
                status = u.get("status", "done")
                color = {"done": "var(--neon-green)", "error": "var(--red)",
                         "running": "var(--cyan)", "waiting": "var(--amber)"}.get(status, "var(--text-muted)")
                st.markdown(
                    f'<div style="font-family:Fira Code,monospace;font-size:0.72rem;margin:2px 0;">'
                    f'<span style="color:var(--text-muted)">[{u.get("timestamp","")}]</span> '
                    f'<span style="color:{color}">[{html.escape(u.get("node",""))}]</span> '
                    f'<span style="color:var(--text-secondary)">{html.escape(u.get("message",""))}</span></div>',
                    unsafe_allow_html=True
                )

# ── Bottom intelligence strip ───────────────────────────────────────────────
cache_stats_data, fewshot_stats_data = get_stats()

_result = st.session_state.get("result") or {}
_trace_url = _result.get("trace_url")
_trace_id  = _result.get("trace_id")

if _trace_url:
    trace_html = f'<a href="{_trace_url}" target="_blank" style="color:#00d4ff;text-decoration:none;border-bottom:1px solid rgba(0,212,255,0.3);padding-bottom:1px;">◈ View LangSmith Trace ↗</a>'
elif _trace_id:
    trace_html = f'<span style="color:#2d4a61">◈ Trace ID: {_trace_id[:8]}...</span>'
else:
    trace_html = '<span style="color:#2d4a61;font-style:italic">◈ Set LANGCHAIN_TRACING_V2=true for traces</span>'

st.iframe(f"""
<style>
  .intel-strip {{
    margin-top: 24px; padding: 14px 20px;
    background: rgba(5,7,26,0.9); border-top: 1px solid rgba(0,212,255,0.08);
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
    font-family: 'Fira Code', monospace; font-size: 0.72rem; color: #2d4a61;
  }}
  .intel-strip .val {{ color: #00d4ff; }}
</style>
<div class="intel-strip">
    <span>Cache: <span class="val">{cache_stats_data.get('entries',0)}</span> entries
    &nbsp;·&nbsp; <span class="val">{cache_stats_data.get('total_hits',0)}</span> hits
    &nbsp;·&nbsp; <span class="val">{cache_stats_data.get('hit_rate',0)}%</span> hit rate</span>

    <span>Few-shots: <span class="val">{fewshot_stats_data.get('seeded',0)}</span> seeded
    &nbsp;+&nbsp; <span class="val">{fewshot_stats_data.get('auto_learned',0)}</span> auto-learned</span>

    <span>{trace_html}</span>
</div>
""", height=60)
