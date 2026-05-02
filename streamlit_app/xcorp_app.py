import streamlit as st
import json
import time
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_TITLE = "XCorp AI Data Platform"
APP_VERSION = "5.0"
DB = "XCORP_AGENT_DEMO"
SCHEMA = "AGENT_FRAMEWORK"
RATE_LIMIT = 10
CACHE_TTL_SECONDS = 300

ALLOWED_PROCEDURES = frozenset({
    "RUN_MULTI_AGENT", "RUN_MULTI_AGENT_V4", "GET_AGENT_LIST", "GET_AUDIT_LOG",
    "CREATE_AGENT", "DEACTIVATE_AGENT", "RUN_AGENT", "SUBMIT_FEEDBACK",
    "AUTO_OPTIMIZE_QUERIES", "AUTO_TUNE_PROMPTS", "RUN_MAINTENANCE", "RUN_TEST_SUITE",
    "SECURED_AGENT_EXECUTE", "RAG_ENHANCED_EXECUTE", "CORTEX_GUARDRAILS"
})

AGENT_SUGGESTIONS: Dict[str, List[str]] = {
    "💰 Sales": [
        "What are the total sales?",
        "Top 5 customers by revenue",
        "Monthly sales breakdown",
        "Show recent orders",
        "Revenue by month for 2024",
        "Sales trend over time",
    ],
    "📈 Finance": [
        "Average order value",
        "Sales by product category",
        "Top selling products by revenue",
        "Revenue contribution by product",
    ],
    "⚙️ Operations": [
        "Which products are low in stock?",
        "Show inactive products",
        "Product inventory summary",
        "Products in Software category",
    ],
    "👥 Customer Success": [
        "Customers by region",
        "How many customers do we have?",
        "Customer signup trend by month",
        "Customers with highest lifetime value",
    ],
}

DOMAIN_ICONS: Dict[str, str] = {
    "SALES": "💰", "FINANCE": "📈",
    "OPERATIONS": "⚙️", "CUSTOMER_SUCCESS": "👥"
}

CONFIDENCE_COLORS: Dict[str, str] = {
    "HIGH": "#22c55e", "MEDIUM": "#eab308",
    "LOW": "#ef4444", "FALLBACK": "#6366f1", "FALLBACK_USED": "#6366f1"
}

# ═══════════════════════════════════════════════════════════════════════════════
# THEME & STYLES
# ═══════════════════════════════════════════════════════════════════════════════

ENTERPRISE_THEME = """
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0f172a 0%, #020617 100%);
}
[data-testid="stSidebar"] {
    background: #1e293b;
    border-right: 1px solid #334155;
}
[data-testid="stHeader"] { background: transparent; }
.stChatMessage { border-radius: 12px; }
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
.block-container { padding-top: 1rem; }
div[data-testid="stChatInput"] textarea { border-radius: 12px; }

.topbar {
    background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid #334155;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
}
.topbar-item {
    display: inline-block;
    margin-right: 1.5rem;
    font-size: 0.85rem;
    color: #94a3b8;
}
.topbar-item strong { color: #e2e8f0; }

.confidence-bar {
    height: 8px;
    border-radius: 4px;
    background: #334155;
    overflow: hidden;
    margin-top: 4px;
}
.confidence-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}

.agent-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}

.routing-trace {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0.75rem;
    font-family: monospace;
    font-size: 0.8rem;
    color: #94a3b8;
}

.cost-badge {
    background: #7c3aed20;
    border: 1px solid #7c3aed;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.75rem;
    color: #a78bfa;
}

.rls-notice {
    background: #f59e0b15;
    border-left: 3px solid #f59e0b;
    padding: 0.5rem 0.75rem;
    border-radius: 0 6px 6px 0;
    font-size: 0.8rem;
    color: #fbbf24;
}

.feedback-bar {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0.5rem;
    margin-top: 0.5rem;
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SERVICES: Snowflake Connection & Execution
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_session():
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:
        return None


def get_current_identity() -> Dict[str, str]:
    session = get_session()
    if not session:
        return {"user": "UNKNOWN", "role": "UNKNOWN"}
    try:
        result = session.sql(
            "SELECT CURRENT_USER() AS usr, CURRENT_ROLE() AS rl"
        ).collect()
        if result:
            return {"user": result[0]["USR"], "role": result[0]["RL"]}
    except Exception:
        pass
    return {"user": "UNKNOWN", "role": "UNKNOWN"}


def set_query_tag(context: str = ""):
    session = get_session()
    if not session:
        return
    try:
        identity = get_current_identity()
        tag = json.dumps({
            "app": "XCorpAIPlatform",
            "version": APP_VERSION,
            "user": identity["user"],
            "role": identity["role"],
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
        session.sql(f"ALTER SESSION SET QUERY_TAG = '{tag}'").collect()
    except Exception:
        pass


def call_proc(name: str, *args) -> Optional[Dict]:
    if name not in ALLOWED_PROCEDURES:
        return {"status": "ERROR", "reason": f"Procedure '{name}' not allowed"}
    session = get_session()
    if not session:
        return None
    try:
        set_query_tag(f"proc:{name}")
        result = session.call(f"{DB}.{SCHEMA}.{name}", *args)
        if result:
            return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}
    return None


def run_agent_secured(agent_id: str, query: str) -> Optional[Dict]:
    return call_proc("SECURED_AGENT_EXECUTE", agent_id, query)


def run_agent_rag(agent_id: str, query: str) -> Optional[Dict]:
    return call_proc("RAG_ENHANCED_EXECUTE", agent_id, query)


def run_agent(query: str) -> Optional[Dict]:
    agents = get_agents()
    agent_id = st.session_state.get("selected_agent_id")
    if not agent_id and agents:
        agent_id = agents[0].get("agent_id", "")
    if agent_id:
        return run_agent_secured(agent_id, query)
    return call_proc("RUN_MULTI_AGENT", query)


@st.cache_data(ttl=60)
def get_agents() -> List[Dict]:
    session = get_session()
    if not session:
        return []
    try:
        result = session.call(f"{DB}.{SCHEMA}.GET_AGENT_LIST")
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


@st.cache_data(ttl=30)
def get_audit(limit: int = 50) -> List[Dict]:
    session = get_session()
    if not session:
        return []
    try:
        result = session.call(f"{DB}.{SCHEMA}.GET_AUDIT_LOG", limit)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def fetch_data(sql: str) -> Optional[pd.DataFrame]:
    session = get_session()
    if not session:
        return None
    try:
        set_query_tag("fetch_data")
        return session.sql(sql).to_pandas()
    except Exception:
        return None


def submit_feedback(audit_id: str, rating: int, corrected_sql: str = "", notes: str = "") -> Optional[Dict]:
    return call_proc("SUBMIT_FEEDBACK", audit_id, rating, corrected_sql, notes)


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICES: Result Cache Layer
# ═══════════════════════════════════════════════════════════════════════════════

def get_cache_key(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def get_cached_result(query: str) -> Optional[Dict]:
    key = get_cache_key(query)
    cache = st.session_state.get("_result_cache", {})
    entry = cache.get(key)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
        return entry["data"]
    return None


def set_cached_result(query: str, data: Dict):
    if "_result_cache" not in st.session_state:
        st.session_state["_result_cache"] = {}
    key = get_cache_key(query)
    st.session_state["_result_cache"][key] = {"data": data, "ts": time.time()}


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICES: Cost & Observability
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def get_session_cost_summary() -> Dict[str, Any]:
    session = get_session()
    if not session:
        return {"total_credits": 0, "query_count": 0, "avg_time_ms": 0}
    try:
        result = session.sql("""
            SELECT
                COUNT(*) AS query_count,
                COALESCE(SUM(CREDITS_USED_CLOUD_SERVICES), 0) AS total_credits,
                COALESCE(AVG(CASE WHEN TOTAL_ELAPSED_TIME > 0 THEN TOTAL_ELAPSED_TIME END), 0) AS avg_time_ms
            FROM TABLE(XCORP_AGENT_DEMO.INFORMATION_SCHEMA.QUERY_HISTORY(
                RESULT_LIMIT => 100,
                END_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP())
            ))
        """).collect()
        if result:
            row = result[0]
            return {
                "total_credits": round(float(row["TOTAL_CREDITS"]), 4),
                "query_count": int(row["QUERY_COUNT"]),
                "avg_time_ms": max(round(float(row["AVG_TIME_MS"]), 0), 0)
            }
    except Exception:
        try:
            result = session.sql("""
                SELECT COUNT(*) AS query_count FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.AGENT_AUDIT_LOG
                WHERE logged_at > DATEADD('hour', -1, CURRENT_TIMESTAMP())
            """).collect()
            if result:
                return {"total_credits": 0, "query_count": int(result[0]["QUERY_COUNT"]), "avg_time_ms": 0}
        except Exception:
            pass
    return {"total_credits": 0, "query_count": 0, "avg_time_ms": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICES: Risk Assessment
# ═══════════════════════════════════════════════════════════════════════════════

def get_risk(query: str) -> str:
    q = query.lower()
    high_risk = ["cross join", "all tables", "everything", "all data", "drop", "delete", "truncate", "alter"]
    medium_risk = ["join", "compare", "correlation", "versus", "breakdown", "union"]
    if any(w in q for w in high_risk):
        return "HIGH"
    elif any(w in q for w in medium_risk):
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def init_state():
    defaults: Dict[str, Any] = {
        "messages": [],
        "current_page": "chat",
        "selected_agent_id": None,
        "query_timestamps": [],
        "routing_history": [],
        "_result_cache": {},
        "_identity_loaded": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if not st.session_state._identity_loaded:
        identity = get_current_identity()
        st.session_state["user_name"] = identity["user"]
        st.session_state["user_role"] = identity["role"]
        st.session_state["_identity_loaded"] = True


def rate_ok() -> bool:
    now = time.time()
    st.session_state.query_timestamps = [
        t for t in st.session_state.query_timestamps if now - t < 60
    ]
    return len(st.session_state.query_timestamps) < RATE_LIMIT


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTS: Top Bar
# ═══════════════════════════════════════════════════════════════════════════════

def render_topbar():
    identity = get_current_identity()
    cost_data = get_session_cost_summary()

    st.markdown(f"""
    <div class="topbar">
        <span class="topbar-item">👤 <strong>{identity['user']}</strong></span>
        <span class="topbar-item">🔐 <strong>{identity['role']}</strong></span>
        <span class="topbar-item">💰 <strong>{cost_data['total_credits']:.4f}</strong> credits (1h)</span>
        <span class="topbar-item">📊 <strong>{cost_data['query_count']}</strong> queries</span>
        <span class="topbar-item">⚡ <strong>{cost_data['avg_time_ms']:.0f}ms</strong> avg</span>
        <span class="topbar-item">🤖 <strong>v{APP_VERSION}</strong></span>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTS: Charts
# ═══════════════════════════════════════════════════════════════════════════════

def render_smart_chart(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("No data to visualize.")
        return

    try:
        numeric_cols = df.select_dtypes(include=["number", "float", "int"]).columns.tolist()
        non_numeric = [c for c in df.columns if c not in numeric_cols]

        date_cols = [c for c in df.columns if any(
            kw in c.lower() for kw in ["date", "time", "month", "year", "day", "quarter", "week"]
        )]

        if date_cols and numeric_cols:
            idx_col = date_cols[0]
            chart_cols = [c for c in numeric_cols if c != idx_col][:3]
            if chart_cols:
                chart_df = df.set_index(idx_col)
                st.line_chart(chart_df[chart_cols])
            else:
                st.dataframe(df)
        elif len(numeric_cols) >= 1 and len(non_numeric) >= 1:
            idx_col = non_numeric[0]
            chart_cols = [c for c in numeric_cols if c != idx_col][:3]
            if chart_cols:
                chart_df = df.set_index(idx_col)
                st.bar_chart(chart_df[chart_cols])
            else:
                st.dataframe(df)
        elif len(numeric_cols) >= 1:
            st.bar_chart(df[numeric_cols[:3]])
    except Exception:
        st.dataframe(df)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTS: Confidence & Explainability
# ═══════════════════════════════════════════════════════════════════════════════

def render_confidence_bar(confidence_val):
    if isinstance(confidence_val, str):
        levels = {"HIGH": 95, "MEDIUM": 65, "LOW": 30, "FALLBACK": 15}
        pct = levels.get(confidence_val, 50)
        color = CONFIDENCE_COLORS.get(confidence_val, "#64748b")
    else:
        pct = int(float(confidence_val) * 100)
        color = "#22c55e" if pct >= 80 else "#eab308" if pct >= 50 else "#ef4444"

    st.markdown(f"""
    <div class="confidence-bar">
        <div class="confidence-fill" style="width: {pct}%; background: {color};"></div>
    </div>
    <small style="color:#94a3b8">{pct}%</small>
    """, unsafe_allow_html=True)


def render_explainability(response: Dict):
    if not response:
        return

    with st.expander("🧠 AI Explainability", expanded=False):
        governance = response.get("governance", {})
        security = response.get("security", {})
        domain = governance.get("agent_name", response.get("routed_domain", "UNKNOWN"))
        confidence = governance.get("risk_score", response.get("routing_confidence", 0))
        method = response.get("routing_method", governance.get("policy_status", "UNKNOWN"))
        agent_id = governance.get("agent_id", response.get("routed_agent_id", "N/A"))
        decision = governance.get("decision", response.get("status", "UNKNOWN"))
        risk = governance.get("risk_score", response.get("risk_score", 0))
        output_type = governance.get("output_type", "INFERRED")
        policies = governance.get("policies_checked", [])

        if security.get("attack_detected"):
            st.error(f"🛡️ **SECURITY BLOCK** — {security.get('attack_type', 'UNKNOWN')} | Risk: `{security.get('risk_level', 'HIGH')}` | Confidence: {security.get('confidence', 0):.0%}")

        st.markdown(f"""
        <div class="routing-trace">
        USER QUERY → GUARDRAILS → GOVERNANCE → EXECUTION<br/>
        &nbsp;&nbsp;├── Agent: <strong>{agent_id}</strong><br/>
        &nbsp;&nbsp;├── Decision: <strong>{decision}</strong><br/>
        &nbsp;&nbsp;├── Output Type: <strong>{output_type}</strong><br/>
        &nbsp;&nbsp;├── Risk Score: <strong>{risk}</strong><br/>
        &nbsp;&nbsp;├── Policies: <strong>{', '.join(policies) if isinstance(policies, list) else str(policies)}</strong><br/>
        &nbsp;&nbsp;└── Security: {'🛡️ BLOCKED' if security.get('attack_detected') else '✅ CLEAR'}
        </div>
        """, unsafe_allow_html=True)

        if response.get("translated_sql"):
            st.caption("Generated SQL:")
            st.code(response["translated_sql"], language="sql")


def render_feedback_bar(response: Dict, idx: str = ""):
    if not response or response.get("was_blocked"):
        return

    audit_id = response.get("audit_id", "") or response.get("governance", {}).get("audit_id", "") or response.get("guardrail_event_id", "")
    if not audit_id:
        return

    uid = f"{audit_id}_{idx}" if idx else audit_id
    st.markdown('<div class="feedback-bar">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    with col1:
        if st.button("👍", key=f"fb_up_{uid}", help="Good result"):
            result = submit_feedback(audit_id, 5, "", "Thumbs up from UI")
            if result and result.get("status") == "SUCCESS":
                st.success("Thanks!")
    with col2:
        if st.button("👎", key=f"fb_down_{uid}", help="Bad result"):
            st.session_state[f"_show_correction_{uid}"] = True
    with col3:
        if st.button("✏️", key=f"fb_edit_{uid}", help="Provide correction"):
            st.session_state[f"_show_correction_{uid}"] = True
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.get(f"_show_correction_{uid}"):
        corrected = st.text_area("Corrected SQL:", key=f"corr_{uid}", height=80)
        notes = st.text_input("Notes:", key=f"notes_{uid}")
        if st.button("Submit Correction", key=f"submit_corr_{uid}"):
            result = submit_feedback(audit_id, 2, corrected, notes)
            if result and result.get("status") == "SUCCESS":
                st.success("Feedback submitted! This improves future results.")
                st.session_state[f"_show_correction_{uid}"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES: AI Console (Chat)
# ═══════════════════════════════════════════════════════════════════════════════

def page_chat():
    pending_query = st.session_state.pop("_pending_query", None)
    if prompt := st.chat_input("Ask your data question..."):
        pending_query = prompt

    col_main, col_panel = st.columns([3, 1])

    with col_main:
        if not st.session_state.messages:
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "👋 **XCorp AI Platform v5.0** — Secured, Governed, Self-Learning\n\n"
                    "Every query passes through: Guardrails → Governance → Execution\n\n"
                    "- 💰 **Sales** — revenue, orders, customers\n"
                    "- 📈 **Finance** — pricing, margins, categories\n"
                    "- ⚙️ **Operations** — inventory, stock, products\n"
                    "- 👥 **Customer Success** — regions, signups, LTV\n\n"
                    "Use 👍👎 to help me improve. All actions are audited."
                ),
                "meta": None
            })

        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                content = msg["content"] or ""
                st.markdown(content.replace('$', '\\$'))
                if msg.get("meta") and msg["role"] == "assistant":
                    render_response_inline(msg["meta"])
                    render_feedback_bar(msg["meta"], f"hist_{i}")

        if pending_query:
            execute_query(pending_query)

    with col_panel:
        render_right_panel()


def render_right_panel():
    st.markdown("#### 🧠 AI Insights")

    if st.session_state.routing_history:
        latest = st.session_state.routing_history[-1]
        domain = latest.get("domain", "")
        confidence = latest.get("confidence", 0)
        method = latest.get("method", "")
        icon = DOMAIN_ICONS.get(domain, "🤖")

        st.markdown(f"**Last Route:** {icon} {domain}")
        st.caption(f"Method: `{method}`")
        render_confidence_bar(confidence)

        if latest.get("cached"):
            st.markdown('<span class="cost-badge">⚡ Cached</span>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**Suggested Follow-ups:**")
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg.get("meta"):
            domain = last_msg["meta"].get("routed_domain", "")
            suggestions_key = {
                "SALES": "💰 Sales", "FINANCE": "📈 Finance",
                "OPERATIONS": "⚙️ Operations", "CUSTOMER_SUCCESS": "👥 Customer Success"
            }.get(domain, "")
            if suggestions_key and suggestions_key in AGENT_SUGGESTIONS:
                for s in AGENT_SUGGESTIONS[suggestions_key][:3]:
                    if st.button(s, key=f"panel_{s[:20]}", use_container_width=True):
                        st.session_state["_pending_query"] = s
                        st.experimental_rerun()

    st.divider()
    st.markdown('<div class="rls-notice">🔒 Results filtered by your access policies</div>', unsafe_allow_html=True)


def execute_query(query: str):
    if not rate_ok():
        st.error("Rate limit exceeded. Wait a moment.")
        return

    st.session_state.query_timestamps.append(time.time())
    st.session_state.messages.append({"role": "user", "content": query, "meta": None})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        risk = get_risk(query)
        if risk == "HIGH":
            st.error("🔴 High-risk query — additional validation applied")
        elif risk == "MEDIUM":
            st.warning("🟡 Moderate complexity")

        cached = get_cached_result(query)
        if cached:
            st.caption("⚡ Served from cache")
            response = cached
        else:
            with st.spinner("🧠 AI routing & processing..."):
                response = run_agent(query)

        if response is None:
            summary = "❌ Agent unreachable. Check Snowflake connection."
            st.markdown(summary)
            st.session_state.messages.append({"role": "assistant", "content": summary, "meta": None})
            return

        status = response.get("status", "")
        was_blocked = response.get("was_blocked", False)

        if status == "BLOCKED" or was_blocked:
            reason = response.get("reason", "Access denied")
            security = response.get("security", {})
            if security.get("attack_detected"):
                summary = f"🛡️ **Security Block**\n\n> **{security.get('attack_type', 'UNKNOWN')}** detected (confidence: {security.get('confidence', 0):.0%})\n> Risk Level: `{security.get('risk_level', 'HIGH')}`"
            else:
                summary = f"🚫 **Query Blocked**\n\n> {reason}"
            st.markdown(summary)
            render_explainability(response)
            st.session_state.messages.append({"role": "assistant", "content": summary, "meta": response})
            return

        if status == "ERROR":
            summary = f"⚠️ **Error:** {response.get('reason', 'Unknown')}"
            st.markdown(summary)
            st.session_state.messages.append({"role": "assistant", "content": summary, "meta": response})
            return

        if not cached:
            set_cached_result(query, response)

        summary_text = response.get("response") or response.get("answer") or response.get("summary") or "Query executed."
        governance = response.get("governance", {})
        st.session_state.routing_history.append({
            "domain": governance.get("agent_name", response.get("routed_domain", "")),
            "confidence": response.get("confidence", governance.get("risk_score", 0)),
            "method": governance.get("policy_status", response.get("routing_method", "")),
            "cached": cached is not None,
            "ts": time.time()
        })

        sql = response.get("translated_sql")
        result_df = None
        if sql:
            result_df = fetch_data(sql)

        safe_summary = summary_text.replace('$', '\\$') if summary_text else "Query executed."
        st.markdown(safe_summary)
        render_response_inline(response, result_df)
        render_explainability(response)
        render_feedback_bar(response, "live")

        st.session_state.messages.append({"role": "assistant", "content": summary_text, "meta": response})


def render_response_inline(response: Optional[Dict], df: Optional[pd.DataFrame] = None):
    if not response:
        return

    domain = response.get("routed_domain", "")
    confidence = response.get("routing_confidence", 0)
    method = response.get("routing_method", "")
    domain_icon = DOMAIN_ICONS.get(domain, "🤖")

    if domain:
        st.caption(f"{domain_icon} **{domain}** | Confidence: {confidence:.2f} | Route: `{method}` | Agent: `{response.get('routed_agent_id', '')}`")
        render_confidence_bar(confidence)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", response.get("row_count", 0))
    col2.metric("Time", f"{response.get('execution_time_ms', 0)}ms")
    col3.metric("Cache", "⚡ Hit" if response.get("cache_hit") else "Miss")
    col4.metric("Risk", f"{response.get('risk_score', 0):.2f}")

    if df is None:
        sql = response.get("translated_sql")
        if sql:
            df = fetch_data(sql)

    if df is not None and not df.empty:
        tab_data, tab_chart, tab_sql = st.tabs(["📋 Data", "📊 Chart", "🔍 SQL"])
        with tab_data:
            st.dataframe(df, use_container_width=True)
        with tab_chart:
            render_smart_chart(df)
        with tab_sql:
            st.code(response.get("translated_sql", ""), language="sql")


def safe_markdown(text: str):
    if text:
        st.markdown(text.replace('$', '\\$'))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES: Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown("### 📊 Platform Analytics")

    tab_usage, tab_cost, tab_learning, tab_agents, tab_health, tab_security = st.tabs([
        "Usage", "Cost", "Learning & Feedback", "Agent Performance", "Agent Health", "Security Events"
    ])

    with tab_usage:
        audit = get_audit(100)
        if not audit:
            st.info("No data yet.")
            return
        df = pd.DataFrame(audit)
        col1, col2, col3, col4 = st.columns(4)
        total = len(df)
        blocked = int(df["was_blocked"].sum()) if "was_blocked" in df.columns else 0
        cache_hits = int(df["cache_hit"].sum()) if "cache_hit" in df.columns else 0
        avg_ms = df["execution_time_ms"].mean() if "execution_time_ms" in df.columns else 0
        col1.metric("Total Queries", total)
        col2.metric("Blocked", f"{blocked} ({blocked / max(total, 1) * 100:.0f}%)")
        col3.metric("Cache Hits", f"{cache_hits} ({cache_hits / max(total, 1) * 100:.0f}%)")
        col4.metric("Avg Latency", f"{avg_ms:.0f}ms")
        if "execution_time_ms" in df.columns:
            st.line_chart(df["execution_time_ms"].reset_index(drop=True))

    with tab_cost:
        render_cost_monitor()

    with tab_learning:
        render_learning_dashboard()

    with tab_agents:
        render_agent_performance()

    with tab_health:
        render_agent_health()

    with tab_security:
        render_security_events()


def render_cost_monitor():
    st.markdown("**Cost & Resource Monitor**")

    cost_summary = get_session_cost_summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("Credits Used (1h)", f"{cost_summary['total_credits']:.4f}")
    col2.metric("Queries (1h)", cost_summary['query_count'])
    col3.metric("Avg Execution", f"{cost_summary['avg_time_ms']:.0f}ms")

    st.divider()
    st.markdown("**Resource Monitor: AI_AGENT_MONITOR**")
    rm_data = fetch_data("""
        SELECT name, credit_quota, used_credits, remaining_credits,
            ROUND(used_credits * 100.0 / NULLIF(credit_quota, 0), 1) AS pct_used,
            frequency, end_time
        FROM TABLE(INFORMATION_SCHEMA.RESOURCE_MONITORS())
        WHERE name = 'AI_AGENT_MONITOR'
    """)
    if rm_data is not None and not rm_data.empty:
        row = rm_data.iloc[0]
        pct = float(row.get("PCT_USED", 0) or 0)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Quota", f"{row.get('CREDIT_QUOTA', 'N/A')} credits")
        col2.metric("Used", f"{row.get('USED_CREDITS', 0):.2f}")
        col3.metric("Remaining", f"{row.get('REMAINING_CREDITS', 0):.2f}")
        col4.metric("Usage", f"{pct:.1f}%")

        if pct >= 90:
            st.error(f"🚨 CRITICAL: {pct:.1f}% of daily credit quota consumed!")
        elif pct >= 75:
            st.warning(f"⚠️ WARNING: {pct:.1f}% of daily credit quota consumed.")
        else:
            st.success(f"✅ Healthy: {pct:.1f}% of daily quota used.")
    else:
        st.info("Resource monitor data unavailable.")

    st.divider()
    st.markdown("**Cost by Agent (7 days)**")
    cost_by_agent = fetch_data("""
        SELECT a.agent_id,
            r.agent_name,
            COUNT(*) AS queries,
            SUM(CASE WHEN a.was_blocked THEN 1 ELSE 0 END) AS blocked,
            ROUND(AVG(a.execution_time_ms), 0) AS avg_ms,
            SUM(CASE WHEN a.cache_hit THEN 1 ELSE 0 END) AS cache_hits
        FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.AGENT_AUDIT_LOG a
        LEFT JOIN XCORP_AGENT_DEMO.AGENT_FRAMEWORK.AGENT_REGISTRY r ON a.agent_id = r.agent_id
        WHERE a.logged_at > DATEADD('day', -7, CURRENT_TIMESTAMP())
        GROUP BY a.agent_id, r.agent_name
        ORDER BY queries DESC
    """)
    if cost_by_agent is not None and not cost_by_agent.empty:
        st.dataframe(cost_by_agent, use_container_width=True)
    else:
        st.info("No agent cost data yet.")

    st.divider()
    st.markdown("**Infrastructure Status**")
    col1, col2, col3 = st.columns(3)
    col1.markdown("🟢 **Query Acceleration**\nEnabled")
    col2.markdown("🟢 **Search Optimization**\nActive on cache + audit")
    col3.markdown("🟢 **Dynamic Tables**\n5-min refresh")


def render_learning_dashboard():
    st.markdown("**Reinforcement Learning Health**")
    df = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_REINFORCEMENT_HEALTH")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No reinforcement data yet. Submit feedback to train the system.")

    st.divider()
    st.markdown("**Feedback Summary**")
    df2 = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_FEEDBACK_SUMMARY")
    if df2 is not None and not df2.empty:
        st.dataframe(df2, use_container_width=True)

    st.divider()
    st.markdown("**Prompt Performance**")
    df3 = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_PROMPT_PERFORMANCE")
    if df3 is not None and not df3.empty:
        st.dataframe(df3, use_container_width=True)

    st.divider()
    st.markdown("**Query Optimizations**")
    df4 = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_OPTIMIZATION_STATS")
    if df4 is not None and not df4.empty:
        st.dataframe(df4, use_container_width=True)


def render_agent_health():
    st.markdown("**Agent Health Dashboard (7-day)**")
    df = fetch_data("SELECT agent_name, agent_domain, health_status, total_queries_7d, success_rate_pct, cache_hit_rate_pct, avg_latency_ms, p95_latency_ms, attacks_blocked_7d FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_AGENT_HEALTH")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)
        if "AVG_LATENCY_MS" in df.columns:
            st.bar_chart(df.set_index("AGENT_NAME")["AVG_LATENCY_MS"])
    else:
        st.info("No health data yet.")


def render_security_events():
    st.markdown("**Guardrail Security Events (Recent)**")
    df = fetch_data("SELECT event_id, timestamp, attack_detected, attack_type, risk_level, confidence_score, action_taken, LEFT(input_text, 60) AS input_preview FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.GUARDRAIL_AUDIT_LOG ORDER BY timestamp DESC LIMIT 20")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)
        blocked = df[df["ACTION_TAKEN"] == "BLOCKED"] if "ACTION_TAKEN" in df.columns else pd.DataFrame()
        if not blocked.empty:
            st.markdown(f"**{len(blocked)} attacks blocked**")
            if "ATTACK_TYPE" in blocked.columns:
                st.bar_chart(blocked["ATTACK_TYPE"].value_counts())
    else:
        st.info("No security events recorded yet.")


def render_agent_performance():
    agents = get_agents()
    if not agents:
        st.info("No agents configured.")
        return
    for agent in agents:
        with st.container():
            st.markdown(f"""
            <div class="agent-card">
                <strong>{DOMAIN_ICONS.get(agent.get('agent_domain', ''), '🤖')} {agent.get('agent_name', 'N/A')}</strong><br/>
                <small>ID: {agent.get('agent_id', '')} | Domain: {agent.get('agent_domain', 'N/A')} | Tables: {', '.join(agent.get('allowed_tables', []))}</small>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES: Governance
# ═══════════════════════════════════════════════════════════════════════════════

def page_governance():
    st.markdown("### 🛡️ Governance & Observability")

    tab_audit, tab_policies, tab_routing, tab_slo = st.tabs([
        "Audit Trail", "Policies", "Routing Analytics", "SLO Dashboard"
    ])

    with tab_audit:
        audit = get_audit(50)
        if not audit:
            st.info("No records.")
            return

        col1, col2 = st.columns(2)
        with col1:
            show_blocked = st.checkbox("Blocked only")
        with col2:
            search = st.text_input("Search", placeholder="Filter queries...")

        filtered = audit
        if show_blocked:
            filtered = [r for r in filtered if r.get("was_blocked")]
        if search:
            filtered = [r for r in filtered if search.lower() in str(r.get("user_query", "")).lower()]

        for r in filtered[:20]:
            icon = "🚫" if r.get("was_blocked") else "✅"
            conf = f" | 🎯{r.get('routing_confidence', 0):.2f}" if r.get('routing_confidence') else ""
            with st.expander(f"{icon} {r.get('user_query', 'N/A')[:60]}{conf} — {str(r.get('logged_at', ''))[:16]}"):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Agent:** `{r.get('agent_id')}`")
                c2.markdown(f"**Domain:** `{r.get('routed_domain', 'N/A')}`")
                c3.markdown(f"**Time:** {r.get('execution_time_ms', 0)}ms")
                if r.get("translated_sql"):
                    st.code(r["translated_sql"], language="sql")
                if r.get("block_reason"):
                    st.error(f"Block reason: {r['block_reason']}")

        if filtered:
            st.download_button("📥 Export CSV", pd.DataFrame(filtered).to_csv(index=False), "audit.csv", "text/csv")

    with tab_policies:
        policies = [
            {"policy": "Write Operation Block", "scope": "All Agents", "enforcement": "SP-level", "status": "🟢 Active"},
            {"policy": "Rate Limiting", "scope": "Per User", "enforcement": "SP-level", "status": "🟢 Active"},
            {"policy": "System Table Block", "scope": "All Agents", "enforcement": "SP-level", "status": "🟢 Active"},
            {"policy": "CROSS JOIN Block", "scope": "All Agents", "enforcement": "SP-level", "status": "🟢 Active"},
            {"policy": "Row-Level Security", "scope": "CUSTOMERS table", "enforcement": "Native Policy", "status": "🟢 Active"},
            {"policy": "PII Masking", "scope": "Email column", "enforcement": "Native Policy", "status": "🟢 Active"},
            {"policy": "ABAC Region Access", "scope": "User Entitlements", "enforcement": "Native Policy", "status": "🟢 Active"},
            {"policy": "Cost Governance", "scope": "Per Query", "enforcement": "Config-driven", "status": "🟢 Active"},
        ]
        st.dataframe(pd.DataFrame(policies), use_container_width=True, hide_index=True)

    with tab_routing:
        df = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_ROUTING_ANALYTICS")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
            if "QUERY_COUNT" in df.columns:
                st.bar_chart(df.set_index("ROUTED_DOMAIN")["QUERY_COUNT"])
        else:
            st.info("No routing data yet.")

        st.divider()
        st.markdown("**Router Accuracy**")
        df2 = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_ROUTER_ACCURACY")
        if df2 is not None and not df2.empty:
            st.dataframe(df2, use_container_width=True)

    with tab_slo:
        df = fetch_data("SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_SLO_DASHBOARD ORDER BY HOUR_BUCKET DESC LIMIT 24")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
            if "AVG_LATENCY_MS" in df.columns:
                st.line_chart(df.set_index("HOUR_BUCKET")["AVG_LATENCY_MS"])
        else:
            st.info("No SLO data yet.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES: Agent Studio
# ═══════════════════════════════════════════════════════════════════════════════

def page_agents():
    st.markdown("### 🤖 Agent Studio")

    tab_overview, tab_create, tab_maintenance = st.tabs(["Overview", "Create Agent", "Maintenance"])

    with tab_overview:
        agents = get_agents()
        if not agents:
            st.info("No agents configured.")
            return
        for a in agents:
            with st.expander(f"{DOMAIN_ICONS.get(a.get('agent_domain', ''), '🤖')} {a.get('agent_name', '')} (`{a.get('agent_id', '')}`)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Tables:** `{', '.join(a.get('allowed_tables', []))}`")
                    st.markdown(f"**Expires:** {str(a.get('expires_at', 'N/A'))[:10]}")
                with col2:
                    st.markdown(f"**Domain:** {a.get('agent_domain', 'N/A')}")
                    st.markdown(f"**Status:** {'🟢 Active' if a.get('is_active', True) else '🔴 Inactive'}")
                if st.button("Deactivate", key=f"deact_{a.get('agent_id', '')}"):
                    call_proc("DEACTIVATE_AGENT", a["agent_id"])
                    st.experimental_rerun()

    with tab_create:
        identity = get_current_identity()
        if identity["role"] not in ("ACCOUNTADMIN", "SYSADMIN"):
            st.error("🔐 Requires ADMIN role.")
            return
        name = st.text_input("Agent Name")
        days = st.number_input("Expiry (days)", 1, 365, 90)
        tables = st.multiselect("Allowed Tables", ["ORDERS", "CUSTOMERS", "PRODUCTS"], default=["ORDERS"])
        if st.button("Create Agent", type="primary"):
            if name and tables:
                result = call_proc("CREATE_AGENT", name, days, tables)
                if result and result.get("status") == "SUCCESS":
                    st.success(f"✅ Created: `{result.get('agent_id')}`")
                else:
                    st.error(f"Failed: {result}")

    with tab_maintenance:
        st.markdown("**System Maintenance**")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Optimize Queries", use_container_width=True):
                with st.spinner("Optimizing..."):
                    result = call_proc("AUTO_OPTIMIZE_QUERIES")
                    st.json(result)
        with col2:
            if st.button("🧠 Tune Prompts", use_container_width=True):
                with st.spinner("Tuning..."):
                    result = call_proc("AUTO_TUNE_PROMPTS")
                    st.json(result)
        with col3:
            if st.button("🧹 Full Maintenance", use_container_width=True):
                with st.spinner("Running..."):
                    result = call_proc("RUN_MAINTENANCE")
                    st.json(result)

        st.divider()
        st.markdown("**Test Suite**")
        agents = get_agents()
        if agents:
            agent_map = {a.get("agent_name", ""): a.get("agent_id", "") for a in agents}
            selected = st.selectbox("Select Agent to Test", list(agent_map.keys()))
            if st.button("▶ Run Tests"):
                with st.spinner("Running test suite..."):
                    result = call_proc("RUN_TEST_SUITE", agent_map[selected])
                    if result:
                        st.json(result)
                        df = fetch_data("""
                            SELECT test_id, input_query, test_category, expected_blocked, last_passed, last_run_at
                            FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.AGENT_TEST_CASES ORDER BY test_category, test_id
                        """)
                        if df is not None:
                            st.dataframe(df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES: Query Editor
# ═══════════════════════════════════════════════════════════════════════════════

def page_query_editor():
    st.markdown("### 📝 Query Editor")

    sql_input = st.text_area(
        "SQL Query", height=200,
        placeholder="SELECT * FROM XCORP_AGENT_DEMO.AGENT_FRAMEWORK.V_SALES_METRICS LIMIT 10"
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        run_btn = st.button("▶ Run", type="primary")

    if run_btn and sql_input.strip():
        risk = get_risk(sql_input)
        if risk == "HIGH":
            st.error("🔴 High-risk query blocked.")
            return
        set_query_tag("manual_query")
        with st.spinner("Executing..."):
            result_df = fetch_data(sql_input)
        if result_df is not None:
            st.success(f"✅ {len(result_df)} rows returned")
            tab_data, tab_chart = st.tabs(["📋 Results", "📊 Chart"])
            with tab_data:
                st.dataframe(result_df, use_container_width=True)
            with tab_chart:
                render_smart_chart(result_df)
        else:
            st.error("Execution failed.")


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT: Sidebar Navigation
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ XCorp AI Platform")
        st.caption(f"v{APP_VERSION} • Enterprise • Secured • Self-Learning")
        st.divider()

        identity = get_current_identity()
        st.markdown(f"👤 **{identity['user']}**")
        st.markdown(f"🔐 `{identity['role']}`")

        st.divider()

        pages = {
            "💬 AI Console": "chat",
            "📝 Query Editor": "query_editor",
            "📊 Dashboard": "dashboard",
            "🤖 Agent Studio": "agents",
            "🛡️ Governance": "governance",
        }

        selected = st.radio("Navigation", list(pages.keys()), label_visibility="collapsed")
        st.session_state.current_page = pages.get(selected, "chat")

        st.divider()
        st.markdown("**Quick Queries**")
        for domain, queries in AGENT_SUGGESTIONS.items():
            with st.expander(domain):
                for s in queries:
                    if st.button(s, key=f"sug_{domain}_{s[:20]}", use_container_width=True):
                        st.session_state["_pending_query"] = s
                        st.session_state.current_page = "chat"
                        st.experimental_rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown(ENTERPRISE_THEME, unsafe_allow_html=True)

    init_state()
    render_sidebar()
    render_topbar()

    page_map = {
        "chat": page_chat,
        "query_editor": page_query_editor,
        "dashboard": page_dashboard,
        "agents": page_agents,
        "governance": page_governance,
    }
    page_fn = page_map.get(st.session_state.current_page, page_chat)
    page_fn()


if __name__ == "__main__":
    main()
