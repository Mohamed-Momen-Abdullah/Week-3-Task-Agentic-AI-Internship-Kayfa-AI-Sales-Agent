import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from database.mongo import (
    get_all_usage_logs,
    get_cost_by_user,
    get_daily_cost_trend,
    get_sessions_with_logs,
    get_session_trace,
    get_logs_by_period,
)
from app.utils import inject_custom_css, render_header, get_theme_colors
from app.auth import require_auth, logout, get_current_user

st.set_page_config(
    page_title="Kayfa Monitor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_auth(role="agent")
c = inject_custom_css()
agent = get_current_user()

st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='padding:0.5rem 0 1rem;'>"
        f"<span style='font-size:0.8rem;color:{c['text_muted']};text-transform:uppercase;"
        f"letter-spacing:.05em;'>Sales Agent</span><br>"
        f"<strong style='font-size:1rem;color:{c['text']};'>👤 {agent['username']}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("📊  CRM Tickets", use_container_width=True):
        st.switch_page("pages/2_CRM_Tickets.py")
    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:0.5rem 0 1rem;'>",
        unsafe_allow_html=True,
    )
    if st.button("🚪  Sign Out", use_container_width=True):
        logout()

# ── Header ────────────────────────────────────────────────────────────────────
render_header(
    "Cost & Behaviour Monitor",
    "Real-time cost tracking · Agent trace inspection · Before vs After comparisons",
)

tab_a, tab_b, tab_c = st.tabs([
    "💰  Monitor A — Cost",
    "🔍  Monitor B — Behaviour Trace",
    "📊  Monitor C — Before vs After",
])


# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR A: COST TRACKING
# ═══════════════════════════════════════════════════════════════════════════════
with tab_a:
    logs = get_all_usage_logs()

    if not logs:
        st.markdown(
            f"<div style='text-align:center;padding:4rem 2rem;'>"
            f"<p style='font-size:2rem;'>📭</p>"
            f"<h3 style='color:{c['text']};'>No cost data yet</h3>"
            f"<p style='color:{c['text_muted']};'>Run a few chat sessions and refresh this page.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        df = pd.DataFrame(logs)

        total_cost   = df["total_cost"].sum()
        input_cost   = df["input_cost"].sum()
        output_cost  = df["output_cost"].sum()
        embed_cost   = df["embedding_cost"].sum()
        msg_count    = len(df)
        avg_latency  = df["latency"].mean()
        total_tokens = (df["input_tokens"] + df["output_tokens"]).sum()
        cost_per_msg = total_cost / msg_count if msg_count else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Total Cost (USD)", f"${total_cost:.5f}")
        k2.metric("📨 Total Messages",   f"{msg_count:,}")
        k3.metric("🔤 Total Tokens",     f"{total_tokens:,}")
        k4.metric("⏱ Avg Latency",      f"{avg_latency:.2f}s")

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("→ Chat Input",    f"${input_cost:.5f}",  help="Groq input token cost")
        b2.metric("→ Chat Output",   f"${output_cost:.5f}", help="Groq output token cost")
        b3.metric("→ Embedding/RAG", f"${embed_cost:.5f}",  help="Estimated embedding cost per tool call")
        b4.metric("→ Cost / Message",f"${cost_per_msg:.6f}")

        st.markdown(
            f"<hr style='border-color:{c['card_border']};margin:1.25rem 0;'>",
            unsafe_allow_html=True,
        )

        chart_col, user_col = st.columns([3, 2])

        with chart_col:
            st.markdown(
                f"<h4 style='color:{c['text']};margin-bottom:0.6rem;'>Daily Cost Trend</h4>",
                unsafe_allow_html=True,
            )
            trend_raw = get_daily_cost_trend()
            if trend_raw:
                trend_df = (
                    pd.DataFrame(trend_raw)
                    .rename(columns={"_id": "Date", "daily_cost": "Cost ($)"})
                    .set_index("Date")
                )
                st.bar_chart(trend_df[["Cost ($)"]], color=c["primary"], height=220)
            else:
                st.caption("Not enough data for the trend chart yet.")

        with user_col:
            st.markdown(
                f"<h4 style='color:{c['text']};margin-bottom:0.6rem;'>Cost by User</h4>",
                unsafe_allow_html=True,
            )
            user_raw = get_cost_by_user()
            if user_raw:
                for u in user_raw:
                    user_pct = (u["total_cost"] / total_cost * 100) if total_cost else 0
                    st.markdown(
                        f"<div style='background:{c['card_bg']};border:1px solid {c['card_border']};"
                        f"border-radius:10px;padding:10px 14px;margin-bottom:8px;'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                        f"<span style='font-weight:600;color:{c['text']};'>👤 {u['_id']}</span>"
                        f"<span style='color:{c['primary']};font-weight:700;'>${u['total_cost']:.5f}</span>"
                        f"</div>"
                        f"<div style='background:{c['card_border']};border-radius:4px;height:4px;margin:6px 0 4px;'>"
                        f"<div style='background:{c['primary']};width:{min(user_pct, 100):.1f}%;"
                        f"height:4px;border-radius:4px;'></div></div>"
                        f"<div style='display:flex;justify-content:space-between;'>"
                        f"<span style='font-size:0.75rem;color:{c['text_muted']};'>"
                        f"{u['total_tokens']:,} tokens</span>"
                        f"<span style='font-size:0.75rem;color:{c['text_muted']};'>"
                        f"{user_pct:.1f}% of spend</span>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown(
            f"<hr style='border-color:{c['card_border']};margin:1.25rem 0;'>",
            unsafe_allow_html=True,
        )

        ledger_col, _ = st.columns([6, 1])
        with ledger_col:
            st.markdown(
                f"<h4 style='color:{c['text']};margin-bottom:0.6rem;'>Message Ledger</h4>",
                unsafe_allow_html=True,
            )
            ledger = df[[
                "timestamp", "user_id", "provider", "input_tokens",
                "output_tokens", "embedding_tokens", "total_cost", "latency",
            ]].copy()
            ledger["timestamp"] = ledger["timestamp"].str[:19].str.replace("T", " ")
            ledger = ledger.rename(columns={
                "timestamp":        "Time",
                "user_id":          "User",
                "provider":         "Provider",
                "input_tokens":     "Input Tok",
                "output_tokens":    "Output Tok",
                "embedding_tokens": "Embed Tok",
                "total_cost":       "Cost",
                "latency":          "Latency",
            })
        st.dataframe(ledger, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR B: BEHAVIOUR & RESPONSE TRACE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_b:
    sessions = get_sessions_with_logs()

    if not sessions:
        st.markdown(
            f"<div style='text-align:center;padding:4rem 2rem;'>"
            f"<p style='font-size:2rem;'>🔎</p>"
            f"<h3 style='color:{c['text']};'>No sessions to trace</h3>"
            f"<p style='color:{c['text_muted']};'>Run a chat session first, then inspect it here.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        session_map = {s["_id"]: s for s in sessions}

        def _label(sid: str) -> str:
            s = session_map[sid]
            preview = (s.get("first_response") or "…")[:55].replace("\n", " ")
            return (
                f"👤 {s['user_id']}  ·  {s['message_count']} turn(s)"
                f"  ·  ${s['total_cost']:.5f}  ·  \"{preview}…\""
            )

        selected_id = st.selectbox(
            "Choose a conversation to inspect:",
            options=list(session_map.keys()),
            format_func=_label,
            label_visibility="collapsed",
        )

        if selected_id:
            s_info = session_map[selected_id]

            st.markdown(
                f"<div style='background:{c['card_bg']};border:1px solid {c['card_border']};"
                f"border-radius:10px;padding:12px 20px;margin:0.5rem 0 1.25rem;"
                f"display:flex;justify-content:space-around;flex-wrap:wrap;gap:12px;'>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;letter-spacing:.05em;'>User</div>"
                f"<div style='font-weight:700;color:{c['text']};'>👤 {s_info['user_id']}</div>"
                f"</div>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;letter-spacing:.05em;'>Turns</div>"
                f"<div style='font-weight:700;color:{c['text']};'>{s_info['message_count']}</div>"
                f"</div>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;letter-spacing:.05em;'>Total Cost</div>"
                f"<div style='font-weight:700;color:{c['primary']};'>${s_info['total_cost']:.5f}</div>"
                f"</div>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;letter-spacing:.05em;'>Avg Latency</div>"
                f"<div style='font-weight:700;color:{c['text']};'>{s_info.get('avg_latency', 0):.2f}s</div>"
                f"</div>"
                f"<div style='text-align:center;'>"
                f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;letter-spacing:.05em;'>Session ID</div>"
                f"<div style='font-size:0.78rem;color:{c['text_muted']};font-family:monospace;'>…{str(selected_id)[-14:]}</div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            trace_logs = get_session_trace(selected_id)

            for i, turn in enumerate(trace_logs, 1):
                steps        = turn.get("trace", [])
                tool_results = [s for s in steps if s.get("step") == "tool_result"]
                is_grounded  = len(tool_results) > 0

                grounding_color = c["success_text"] if is_grounded else c["warning_text"]
                grounding_label = "✅ Grounded in sources" if is_grounded else "⚠️ No sources consulted"

                ts       = str(turn.get("timestamp", ""))[:19].replace("T", " ")
                in_tok   = turn.get("input_tokens", 0)
                out_tok  = turn.get("output_tokens", 0)
                latency  = turn.get("latency", 0)
                cost     = turn.get("total_cost", 0)
                user_msg = turn.get("user_message", "")
                response = turn.get("final_response", "")

                with st.container(border=True):
                    h1, h2, h3, h4, h5 = st.columns([1, 3, 3, 2, 2])
                    h1.markdown(f"**Turn {i}**")
                    h2.caption(f"🕐 {ts}")
                    h3.caption(f"⚡ {in_tok + out_tok:,} tok  ({in_tok} in / {out_tok} out)")
                    h4.caption(f"⏱ {latency:.2f}s")
                    h5.markdown(f"**💰 ${cost:.6f}**")

                    st.markdown(
                        f"<hr style='border-color:{c['card_border']};margin:0.4rem 0 0.75rem;'>",
                        unsafe_allow_html=True,
                    )

                    if user_msg:
                        st.markdown(
                            f"<div style='background:{c['primary']}0d;"
                            f"border-left:3px solid {c['primary']}55;"
                            f"border-radius:0 8px 8px 0;padding:8px 14px;margin-bottom:10px;'>"
                            f"<span style='font-size:0.7rem;font-weight:600;color:{c['text_muted']};"
                            f"text-transform:uppercase;letter-spacing:.06em;'>👤 User</span>"
                            f"<p style='margin:4px 0 0;color:{c['text']};'>{user_msg}</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    call_steps   = [s for s in steps if s.get("step") == "tool_call"]
                    result_steps = [s for s in steps if s.get("step") == "tool_result"]

                    for idx, call in enumerate(call_steps):
                        tool_name = call.get("tool", "unknown")
                        args      = call.get("args", {})
                        with st.expander(f"🔧  Tool Call #{idx + 1}: `{tool_name}`", expanded=True):
                            st.json(args)
                        if idx < len(result_steps):
                            res = result_steps[idx]
                            with st.expander(f"📄  Source returned by `{tool_name}`", expanded=False):
                                st.text(res.get("content", ""))

                    if response:
                        st.markdown(
                            f"<div style='background:{c['bg_secondary']};"
                            f"border:1px solid {c['card_border']};"
                            f"border-radius:8px;padding:10px 14px;margin-top:6px;'>"
                            f"<div style='display:flex;justify-content:space-between;"
                            f"align-items:center;margin-bottom:8px;'>"
                            f"<span style='font-size:0.7rem;font-weight:600;color:{c['text_muted']};"
                            f"text-transform:uppercase;letter-spacing:.06em;'>🤖 Response</span>"
                            f"<span style='font-size:0.75rem;font-weight:600;"
                            f"background:{grounding_color}22;color:{grounding_color};"
                            f"padding:2px 10px;border-radius:12px;'>{grounding_label}</span>"
                            f"</div>"
                            f"<p style='margin:0;color:{c['text']};line-height:1.6;'>"
                            f"{response[:600]}{'…' if len(response) > 600 else ''}</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR C: BEFORE vs AFTER COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
with tab_c:

    st.markdown(
        f"<p style='color:{c['text_muted']};margin-bottom:1.5rem;'>"
        f"Pick a cutoff date — the day you deployed a change (new prompt, semantic caching, true RAG, etc.). "
        f"The dashboard will split all logged data into <strong>Before</strong> and <strong>After</strong> "
        f"and show you exactly what improved."
        f"</p>",
        unsafe_allow_html=True,
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    ctrl_col, _, label_col = st.columns([2, 1, 3])

    with ctrl_col:
        cutoff_date = st.date_input(
            "Change deployed on:",
            value=datetime.today() - timedelta(days=7),
            help="Set this to the date you made a change to the agent.",
        )
        change_label = st.text_input(
            "What changed? (optional label)",
            placeholder="e.g. Added semantic caching + true RAG",
        )

    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    with label_col:
        st.markdown(
            f"<div style='background:{c['card_bg']};border:1px solid {c['card_border']};"
            f"border-radius:10px;padding:14px 18px;margin-top:1.6rem;'>"
            f"<span style='font-size:0.75rem;color:{c['text_muted']};text-transform:uppercase;"
            f"letter-spacing:.05em;'>Comparing</span><br>"
            f"<strong style='color:{c['text']};'>Before</strong> "
            f"<span style='color:{c['text_muted']};'>— everything before {cutoff_str}</span><br>"
            f"<strong style='color:{c['primary']};'>After</strong> "
            f"<span style='color:{c['text_muted']};'>— everything from {cutoff_str} onward</span>"
            f"{'<br><span style=\"font-size:0.8rem;color:' + c['primary'] + ';margin-top:4px;display:block;\">🏷 ' + change_label + '</span>' if change_label else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:1.25rem 0;'>",
        unsafe_allow_html=True,
    )

    # ── Fetch data ────────────────────────────────────────────────────────────
    before_logs = get_logs_by_period(end=cutoff_str)
    after_logs  = get_logs_by_period(start=cutoff_str)

    if not before_logs and not after_logs:
        st.info("No usage logs found. Run some chat sessions first, then come back here.")
        st.stop()

    def _summarise(logs: list[dict]) -> dict:
        """Compute comparison metrics from a list of usage log dicts."""
        if not logs:
            return {
                "count": 0, "total_cost": 0, "avg_cost": 0,
                "avg_tokens": 0, "avg_latency": 0,
                "cache_hits": 0, "cache_rate": 0,
                "avg_input": 0, "avg_output": 0,
            }
        df = pd.DataFrame(logs)
        count       = len(df)
        total_cost  = df["total_cost"].sum()
        avg_cost    = df["total_cost"].mean()
        avg_tokens  = (df["input_tokens"] + df["output_tokens"]).mean()
        avg_latency = df["latency"].mean()
        cache_hits  = (df["provider"] == "semantic_cache").sum()
        cache_rate  = cache_hits / count * 100 if count else 0
        avg_input   = df["input_tokens"].mean()
        avg_output  = df["output_tokens"].mean()
        return {
            "count": count, "total_cost": total_cost, "avg_cost": avg_cost,
            "avg_tokens": avg_tokens, "avg_latency": avg_latency,
            "cache_hits": int(cache_hits), "cache_rate": cache_rate,
            "avg_input": avg_input, "avg_output": avg_output,
        }

    bef = _summarise(before_logs)
    aft = _summarise(after_logs)

    def _delta(before_val: float, after_val: float, lower_is_better: bool = True) -> str:
        """Return a coloured delta string."""
        if before_val == 0:
            return ""
        change = ((after_val - before_val) / before_val) * 100
        if lower_is_better:
            color  = c["success_text"] if change < 0 else c["danger_text"] if change > 0 else c["text_muted"]
            arrow  = "▼" if change < 0 else "▲" if change > 0 else "●"
        else:
            color  = c["success_text"] if change > 0 else c["danger_text"] if change < 0 else c["text_muted"]
            arrow  = "▲" if change > 0 else "▼" if change < 0 else "●"
        return f"<span style='color:{color};font-size:0.8rem;'>{arrow} {abs(change):.1f}%</span>"

    # ── KPI comparison cards ──────────────────────────────────────────────────
    def _kpi_card(label: str, before_val, after_val, fmt: str = "{:.5f}",
                  lower_is_better: bool = True, suffix: str = "") -> str:
        b_str = fmt.format(before_val) + suffix
        a_str = fmt.format(after_val)  + suffix
        delta = _delta(before_val, after_val, lower_is_better)
        return (
            f"<div style='background:{c['card_bg']};border:1px solid {c['card_border']};"
            f"border-radius:12px;padding:16px 18px;text-align:center;'>"
            f"<div style='font-size:0.72rem;color:{c['text_muted']};text-transform:uppercase;"
            f"letter-spacing:.06em;margin-bottom:8px;'>{label}</div>"
            f"<div style='display:flex;justify-content:space-around;align-items:flex-end;gap:8px;'>"
            f"<div>"
            f"<div style='font-size:0.68rem;color:{c['text_muted']};'>Before</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:{c['text']};'>{b_str}</div>"
            f"</div>"
            f"<div style='font-size:1.4rem;color:{c['card_border']};'>→</div>"
            f"<div>"
            f"<div style='font-size:0.68rem;color:{c['text_muted']};'>After</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:{c['primary']};'>{a_str}</div>"
            f"</div>"
            f"</div>"
            f"<div style='margin-top:8px;'>{delta}</div>"
            f"</div>"
        )

    g1, g2, g3, g4 = st.columns(4)
    g1.markdown(_kpi_card("Avg Cost / Message", bef["avg_cost"],    aft["avg_cost"],    "${:.6f}"), unsafe_allow_html=True)
    g2.markdown(_kpi_card("Avg Tokens / Message", bef["avg_tokens"], aft["avg_tokens"], "{:.0f}", suffix=" tok"), unsafe_allow_html=True)
    g3.markdown(_kpi_card("Avg Latency",         bef["avg_latency"],aft["avg_latency"],"{:.2f}", suffix="s"), unsafe_allow_html=True)
    g4.markdown(_kpi_card("Cache Hit Rate",       bef["cache_rate"], aft["cache_rate"], "{:.1f}", lower_is_better=False, suffix="%"), unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    g5, g6, g7, g8 = st.columns(4)
    g5.markdown(_kpi_card("Total Messages",   bef["count"],      aft["count"],      "{:.0f}", lower_is_better=False), unsafe_allow_html=True)
    g6.markdown(_kpi_card("Total Spend",      bef["total_cost"], aft["total_cost"], "${:.5f}"), unsafe_allow_html=True)
    g7.markdown(_kpi_card("Avg Input Tokens", bef["avg_input"],  aft["avg_input"],  "{:.0f}", suffix=" tok"), unsafe_allow_html=True)
    g8.markdown(_kpi_card("Avg Output Tokens",bef["avg_output"], aft["avg_output"], "{:.0f}", suffix=" tok"), unsafe_allow_html=True)

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:1.5rem 0;'>",
        unsafe_allow_html=True,
    )

    # ── Side-by-side bar chart ────────────────────────────────────────────────
    st.markdown(
        f"<h4 style='color:{c['text']};margin-bottom:0.6rem;'>Side-by-Side Comparison</h4>",
        unsafe_allow_html=True,
    )

    chart_df = pd.DataFrame({
        "Metric": [
            "Avg Cost/Msg ($×10⁻⁵)",
            "Avg Tokens/Msg (÷10)",
            "Avg Latency (s)",
            "Cache Hit Rate (%)",
        ],
        "Before": [
            bef["avg_cost"]    * 1e5,
            bef["avg_tokens"]  / 10,
            bef["avg_latency"],
            bef["cache_rate"],
        ],
        "After": [
            aft["avg_cost"]    * 1e5,
            aft["avg_tokens"]  / 10,
            aft["avg_latency"],
            aft["cache_rate"],
        ],
    }).set_index("Metric")

    st.bar_chart(chart_df, height=280)

    st.caption(
        "Cost is scaled ×10⁻⁵ and tokens ÷10 so all metrics fit on one axis. "
        "Cache Hit Rate — higher is better; all others — lower is better."
    )

    st.markdown(
        f"<hr style='border-color:{c['card_border']};margin:1.5rem 0;'>",
        unsafe_allow_html=True,
    )

    # ── Raw period summaries ──────────────────────────────────────────────────
    st.markdown(
        f"<h4 style='color:{c['text']};margin-bottom:0.6rem;'>Period Summaries</h4>",
        unsafe_allow_html=True,
    )

    sum_col_b, sum_col_a = st.columns(2)

    def _period_card(title: str, color: str, stats: dict) -> str:
        return (
            f"<div style='background:{c['card_bg']};border:1px solid {color}55;"
            f"border-radius:12px;padding:18px 20px;'>"
            f"<div style='font-weight:700;color:{color};font-size:1rem;"
            f"margin-bottom:12px;border-bottom:1px solid {color}33;padding-bottom:8px;'>{title}</div>"
            f"<p style='margin:5px 0;color:{c['text']};'>📨 <strong>{stats['count']:,}</strong> messages</p>"
            f"<p style='margin:5px 0;color:{c['text']};'>💰 Total spend: <strong>${stats['total_cost']:.5f}</strong></p>"
            f"<p style='margin:5px 0;color:{c['text']};'>📊 Avg cost/msg: <strong>${stats['avg_cost']:.6f}</strong></p>"
            f"<p style='margin:5px 0;color:{c['text']};'>🔤 Avg tokens/msg: <strong>{stats['avg_tokens']:.0f}</strong></p>"
            f"<p style='margin:5px 0;color:{c['text']};'>⏱ Avg latency: <strong>{stats['avg_latency']:.2f}s</strong></p>"
            f"<p style='margin:5px 0;color:{c['text']};'>⚡ Cache hits: <strong>{stats['cache_hits']} ({stats['cache_rate']:.1f}%)</strong></p>"
            f"</div>"
        )

    with sum_col_b:
        st.markdown(_period_card(f"⬛ Before  ({cutoff_str})", c["text_muted"], bef), unsafe_allow_html=True)
    with sum_col_a:
        st.markdown(_period_card(f"🟦 After  ({cutoff_str}+)", c["primary"], aft), unsafe_allow_html=True)