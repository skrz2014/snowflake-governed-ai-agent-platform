## 🏛️ Architecture (v5.2)

```mermaid
flowchart TD
    %% Top Layer - UI
    UI[Streamlit in Snowflake UI<br/>AI Console • Query Editor • Dashboard • Agents • Governance] 
    UI --> TopBar[Top Bar: User | Role | Credits | Queries | Latency]

    %% Execution Pipeline
    subgraph SECURED["SECURED_AGENT_EXECUTE"]
        direction TB
        Guard[CORTEX_GUARDRAILS<br/><small>2-tier Prompt Injection Detection</small>] 
        Gov[GOVERNED_AGENT_EXECUTE<br/><small>Identity + Scope + Audit + Auto-Retry</small>]
        Guard --> Gov
    end

    %% Intelligence Layer
    subgraph INTEL["INTELLIGENCE LAYER"]
        direction TB
        Cache[Semantic Cache]
        Memory[Vector Memory]
        Router[Model Routing]
        RAG[RAG Context]
        Cache & Memory & Router & RAG
    end

    %% Cortex AI
    Cortex[Snowflake Cortex AI<br/>COMPLETE() • EMBED_TEXT_768() • SENTIMENT() • VECTOR_COSINE_SIMILARITY()]

    %% Data Layer
    subgraph DATA["GOVERNED DATA LAYER"]
        DT[Dynamic Tables<br/><small>5-min auto refresh</small>]
        Views[Semantic Views]
        ABAC[ABAC + Masking +<br/>Row Access Policies]
    end

    %% Observability
    Obs[Observability Layer<br/>Audit Log • Guardrail Events • SLO Dashboard • Agent Health<br/>Routing Analytics • Feedback • Test History • Resource Monitor]

    %% Flow Connections
    UI --> SECURED
    SECURED --> INTEL
    INTEL --> Cortex
    Cortex --> DATA
    SECURED --> Obs
    DATA --> Obs
