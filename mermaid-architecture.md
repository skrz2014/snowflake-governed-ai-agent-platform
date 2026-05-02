│                 🏛️ XCorp Governed AI Agent Platform — Production Architecture (v5.2)                    │

┌─────────────────────────────────────────────────────────────────┐
│  AI Console │ Query Editor │ Dashboard │ Agents │ Governance     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Top Bar: User | Role | Credits | Queries | Latency      │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                    SECURED_AGENT_EXECUTE                        │
│  ┌────────────────┐        ┌──────────────────────────┐         │
│  │ CORTEX_        │   →    │ GOVERNED_AGENT_EXECUTE   │         │
│  │ GUARDRAILS     │        │ (Identity + Scope +      │         │
│  │ (2-tier        │        │  Audit + Auto-Retry)     │         │
│  │  detection)    │        └──────────────────────────┘         │
│  └────────────────┘                                             │
├─────────────────────────────────────────────────────────────────┤
│               INTELLIGENCE LAYER                                │
│  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌────────────┐    │
│  │ Semantic │  │   Vector   │  │   Model   │  │    RAG     │    │
│  │  Cache   │  │   Memory   │  │  Routing  │  │  Context   │    │
│  └──────────┘  └────────────┘  └───────────┘  └────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│             SNOWFLAKE CORTEX AI                                 │
│  COMPLETE() │ EMBED_TEXT_768() │ SENTIMENT() │ VECTOR_COSINE    │
├─────────────────────────────────────────────────────────────────┤
│            GOVERNED DATA LAYER                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Dynamic Tables │  │  Semantic    │  │ ABAC + Masking +   │   │
│  │ (5-min auto)   │  │  Views       │  │ Row Access Policy  │   │
│  └────────────────┘  └──────────────┘  └────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│            OBSERVABILITY                                        │
│  Audit Log │ Guardrail Events │ SLO Dashboard │ Agent Health    │
│  Routing Analytics │ Feedback │ Test History │ Resource Monito  │
└─────────────────────────────────────────────────────────────────┘
