import json
import os
import pandas as pd
from datetime import datetime
from graph.state import SQLAgentState

try:
    import plotly.express as px
    import numpy as np
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def now():
    return datetime.now().strftime("%H:%M:%S")


def _is_numeric(val) -> bool:
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def _fig_to_json(fig) -> str:
    """Serialize a Plotly figure to JSON without typed binary arrays.

    Plotly's default to_json() may emit {"dtype":"i2","bdata":"..."} for
    integer columns when orjson is installed. Standard json.dumps avoids
    that entirely; numpy scalars/arrays are converted to plain Python types.
    """
    def _make_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, dict):
            return {k: _make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_make_serializable(v) for v in obj]
        return obj

    return json.dumps(_make_serializable(fig.to_dict()), default=str)


async def classify_chart_node(state: SQLAgentState) -> SQLAgentState:
    state["current_node"] = "classify_chart"
    if state.get("served_from_cache") and state.get("cache_result"):
        cr = state["cache_result"]
        rows = cr.get("result_preview") or []
        columns = list(rows[0].keys()) if rows else []
    else:
        result = state.get("execution_result") or {}
        rows = result.get("rows", [])
        columns = result.get("columns", [])

    if not rows:
        reason = "No rows to visualize" if not columns else "No rows returned — chart needs at least one row"
        state["chart_config"] = {
            "chart_type": "none", "title": "", "x_column": None, "y_column": None,
            "color_column": None, "reasoning": reason, "plotly_json": None,
        }
        state["completed_nodes"].append("classify_chart")
        state["stream_updates"].append({
            "timestamp": now(), "node": "classify_chart",
            "message": f"No chart — {reason}", "status": "done",
        })
        return state

    if len(rows) < 2 or not HAS_PLOTLY:
        state["chart_config"] = {
            "chart_type": "none", "title": "", "x_column": None, "y_column": None,
            "color_column": None, "reasoning": "Insufficient data for chart", "plotly_json": None,
        }
        state["completed_nodes"].append("classify_chart")
        state["stream_updates"].append({
            "timestamp": now(), "node": "classify_chart",
            "message": "No chart — insufficient data", "status": "done",
        })
        return state

    df = pd.DataFrame(rows[:500])

    date_cols, numeric_cols, categorical_cols = [], [], []
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in [
            "date", "time", "year", "month", "day",
            "created", "updated", "timestamp",
        ]):
            date_cols.append(col)
            continue
        sample = df[col].dropna().head(20)
        if len(sample) == 0:
            categorical_cols.append(col)
            continue
        ratio = sum(_is_numeric(v) for v in sample) / len(sample)
        if ratio >= 0.8:
            numeric_cols.append(col)
        else:
            categorical_cols.append(col)

    # Cast identified numeric columns to float so plotly to_json() doesn't emit typed
    # binary arrays (dtype/bdata dicts) that pio.from_json() can't deserialize.
    for col in numeric_cols:
        try:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        except Exception:
            pass

    chart_type, x_col, y_col, color_col, reasoning = "none", None, None, None, ""

    if date_cols and numeric_cols:
        chart_type = "line"
        x_col = date_cols[0]
        y_col = numeric_cols[0]
        reasoning = f"Time-series: {x_col} × {y_col}"
    elif categorical_cols and numeric_cols:
        row_count = len(rows)
        unique_cat = df[categorical_cols[0]].nunique()

        # A result is "rank-like" if the numeric column is sorted descending
        # (i.e. it came from an ORDER BY ... DESC query — typical for TOP N queries)
        is_ranked = (
            len(numeric_cols) > 0
            and df[numeric_cols[0]].is_monotonic_decreasing
        )

        # A result is "distribution-like" (pie-appropriate) only if:
        # - It is NOT a ranked list
        # - It has few enough categories to be readable as slices
        # - All values are positive (negatives make no sense in a pie)
        # - Row count is small enough to be readable
        PIE_MAX_SLICES = int(os.environ.get("PIE_MAX_SLICES", "6"))

        is_distribution = (
            not is_ranked
            and len(categorical_cols) > 0
            and len(numeric_cols) > 0
            and unique_cat <= PIE_MAX_SLICES
            and row_count <= PIE_MAX_SLICES
            and df[numeric_cols[0]].min() >= 0
        )

        chart_type = "pie" if is_distribution else "bar"
        x_col = categorical_cols[0]
        y_col = numeric_cols[0]
        reasoning = f"{chart_type.capitalize()}: {x_col} × {y_col} ({row_count} rows)"
    elif len(numeric_cols) >= 2:
        chart_type = "scatter"
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]
        color_col = categorical_cols[0] if categorical_cols else None
        reasoning = f"Scatter: {x_col} × {y_col}"

    plotly_json = None
    if chart_type != "none":
        try:
            if chart_type == "pie":
                kw = dict(names=x_col, values=y_col)
            else:
                kw = dict(x=x_col, y=y_col)
            if color_col and color_col in df.columns and chart_type != "pie":
                kw["color"] = color_col
            fig = getattr(px, chart_type)(df, **kw, title=reasoning)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0f4ff", family="Outfit"),
                title_font=dict(color="#00d4ff", size=14),
                legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,212,255,0.2)"),
                xaxis=dict(gridcolor="rgba(0,212,255,0.08)", linecolor="rgba(0,212,255,0.2)", tickfont=dict(color="#7ba3c0")),
                yaxis=dict(gridcolor="rgba(0,212,255,0.08)", linecolor="rgba(0,212,255,0.2)", tickfont=dict(color="#7ba3c0")),
                margin=dict(l=20, r=20, t=40, b=20),
            )
            if chart_type == "bar":
                fig.update_traces(marker_color="#00d4ff", marker_line_color="rgba(0,212,255,0.3)", marker_line_width=1)
            elif chart_type == "line":
                fig.update_traces(line_color="#00d4ff", line_width=2)
            elif chart_type == "scatter":
                fig.update_traces(marker_color="#7c3aed", marker_size=8)
            plotly_json = _fig_to_json(fig)
        except Exception as e:
            chart_type = "none"
            reasoning = f"Chart failed: {e}"
            state["stream_updates"].append({
                "timestamp": now(), "node": "classify_chart",
                "message": f"Chart generation error: {e}",
                "status": "error",
            })

    state["chart_config"] = {
        "chart_type": chart_type, "x_column": x_col, "y_column": y_col,
        "color_column": color_col, "title": reasoning, "reasoning": reasoning,
        "plotly_json": plotly_json,
    }
    state["completed_nodes"].append("classify_chart")
    state["stream_updates"].append({
        "timestamp": now(), "node": "classify_chart",
        "message": f"Chart: {chart_type.upper()} — {reasoning}",
        "status": "done",
    })
    return state
