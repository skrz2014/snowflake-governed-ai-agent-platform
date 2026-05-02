## 🏛️ Architecture (v5.2)

Fully governed, self-learning, multi-agent NL-to-SQL platform built entirely within Snowflake Cortex.

> No external LLM APIs. No third-party vector databases. No infrastructure outside Snowflake.

```mermaid
flowchart TD

%% ---------------- UI Layer ----------------
UI["Streamlit in Snowflake UI\nAI Console | Query Editor | Dashboard | Agents | Governance"]
TopBar["Top Bar\nUser | Role | Credits | Queries | Latency"]
UI --> TopBar

%% ---------------- Secured Execution ----------------
subgraph SECURED["SECURED_AGENT_EXECUTE"]
    Guard["CORTEX_GUARDRAILS\n2-tier Prompt Injection Detection"]
    Gov["GOVERNED_AGENT_EXECUTE\nIdentity | Scope | Audit | Auto-Retry"]
    Guard --> Gov
end

%% ---------------- Intelligence Layer ----------------
subgraph INTEL["INTELLIGENCE LAYER"]
    Cache["Semantic Cache"]
    Memory["Vector Memory"]
    Router["Model Routing"]
    RAG["RAG Context"]
end

%% ---------------- Cortex ----------------
Cortex["Snowflake Cortex AI\nCOMPLETE() | EMBED_TEXT_768() | SENTIMENT() | VECTOR_COSINE_SIMILARITY()"]

%% ---------------- Data Layer ----------------
subgraph DATA["GOVERNED DATA LAYER"]
    DT["Dynamic Tables\n5-min Auto Refresh"]
    Views["Semantic Views"]
    ABAC["ABAC | Masking | Row Access Policies"]
end

%% ---------------- Observability ----------------
Obs["Observability Layer\nAudit Log | Guardrail Events | SLO Dashboard | Agent Health | Routing Analytics | Feedback | Test History | Resource Monitor"]

%% ---------------- Flow ----------------
UI --> SECURED
SECURED --> INTEL
INTEL --> Cortex
Cortex --> DATA
SECURED --> Obs
DATA --> Obs
