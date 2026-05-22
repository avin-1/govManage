# GovManage Agentic Workflow Architecture

This document contains the detailed Mermaid diagram representing the agentic workflow of the GovManage system.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '35px', 'primaryColor': '#1e293b', 'primaryTextColor': '#f8fafc', 'primaryBorderColor': '#334155', 'lineColor': '#64748b', 'secondaryColor': '#0f172a', 'tertiaryColor': '#334155', 'clusterBkg': '#0f172a', 'nodeBorder': '#64748b'}}}%%
flowchart TD
    %% Styling Classes
    classDef userNode fill:#4f46e5,stroke:#c7d2fe,stroke-width:2px,color:#fff,rx:5px,ry:5px;
    classDef apiNode fill:#0284c7,stroke:#bae6fd,stroke-width:2px,color:#fff;
    classDef orchestratorNode fill:#7c3aed,stroke:#ddd6fe,stroke-width:2px,color:#fff;
    classDef parallelAgent fill:#059669,stroke:#a7f3d0,stroke-width:2px,color:#fff;
    classDef dbNode fill:#ea580c,stroke:#fed7aa,stroke-width:2px,color:#fff,shape:cylinder;
    classDef decisionNode fill:#dc2626,stroke:#fecaca,stroke-width:2px,color:#fff;
    classDef queueNode fill:#475569,stroke:#94a3b8,stroke-width:1px,color:#fff,shape:rect,stroke-dasharray: 5 5;
    classDef processNode fill:#2563eb,stroke:#bfdbfe,stroke-width:2px,color:#fff;
    classDef humanNode fill:#d97706,stroke:#fde68a,stroke-width:3px,color:#fff,shape:hexagon;
    classDef finalNode fill:#16a34a,stroke:#bbf7d0,stroke-width:2px,color:#fff;
    classDef errorNode fill:#991b1b,stroke:#fecaca,stroke-width:2px,color:#fff;

    subgraph External["External Actors & Interfaces"]
        U([User / Administrator]):::userNode
        UI[React / Vite Dashboard]:::userNode
        Chat[Governance Command Center AI Chat]:::userNode
    end

    subgraph API_Layer["API Gateway (Flask app.py)"]
        API[Incoming Event API]:::apiNode
        GenPol[Policy Generation Trigger]:::apiNode
        API_Query[Data Query API]:::apiNode
    end

    subgraph Queues["Shared File System Queues (agents_micro/shared_queues)"]
        Q1[1_inbox]:::queueNode
        Q2P[2_policy]:::queueNode
        Q2C[2_compliance]:::queueNode
        Q2R[2_risk]:::queueNode
        Q3[3_decision]:::queueNode
        Q4[4_audit]:::queueNode
        Q5[5_report]:::queueNode
        Q6[6_feedback]:::queueNode
        Q7[7_complete]:::queueNode
    end

    subgraph Orchestration["Phase 1: Ingestion & Routing"]
        Orch[Orchestrator Agent\nmain.py]:::orchestratorNode
        OrchGenID{Generate\nevent_id?}:::orchestratorNode
    end

    subgraph Parallel_Agents["Phase 2: Parallel Analysis (LangGraph + LLM)"]
        subgraph Policy_Branch["Policy Analyst Agent"]
            PolAgent[Policy Analyst\nmain.py]:::parallelAgent
            PolRAG{ChromaDB\nSearch?}:::parallelAgent
            PolLLM[LLM: Analyze Conflict\n& Score]:::parallelAgent
        end
        
        subgraph Compliance_Branch["Compliance Agent"]
            CompAgent[Compliance Agent\nmain.py]:::parallelAgent
            CompRAG{ChromaDB\nSearch?}:::parallelAgent
            CompDB[Fetch Frameworks\n& Controls]:::parallelAgent
            CompLLM[LLM: Check Auth\n& Violations]:::parallelAgent
        end

        subgraph Risk_Branch["Risk Assessment Agent"]
            RiskAgent[Risk Assessment\nmain.py]:::parallelAgent
            RiskLLM[LLM: Dynamic Risk ID\n& TVI Scoring]:::parallelAgent
        end
    end

    subgraph Synthesis["Phase 3: Decision & Synthesis"]
        DecAgent[Decision Engine\nmain.py]:::decisionNode
        WaitAll{Wait for Policy,\nCompliance, Risk\nOutputs}:::decisionNode
        DecLLM[LLM: Synthesize Action Path]:::decisionNode
        DecLogic{Evaluate Path:\nSafe, Review, Block}:::decisionNode
    end

    subgraph Post_Processing["Phase 4: Post-Processing & Audit"]
        AudAgent[Audit Agent\nmain.py]:::processNode
        RepAgent[Reporting Agent\nmain.py]:::processNode
        FeedAgent[Feedback Agent\nmain.py]:::processNode
    end

    subgraph Persistence["Phase 5: Data Persistence"]
        PersAgent[Persistence Agent\nmain.py]:::processNode
        PersWrite[Write to MongoDB:\nActions, Audit, Reports]:::processNode
        TokenGen[Generate Completion Token]:::processNode
    end

    subgraph Databases["Persistent Storage"]
        Mongo[(MongoDB\n16 Collections)]:::dbNode
        Chroma[(ChromaDB\nVector Store)]:::dbNode
        LogFile[(feedback_log.json)]:::dbNode
    end

    subgraph Human_In_Loop["Human-in-the-Loop (HITL) Workflow"]
        HITL_Review{{Human Review Required\n(Review Path)}}:::humanNode
        HITL_Approve[Human Approves Action/Policy]:::humanNode
        HITL_Reject[Human Rejects/Modifies Action]:::humanNode
    end

    %% --- Connections & Flow ---

    %% External to API
    U -->|Interacts| UI
    U -->|Chats / Prompts| Chat
    UI -->|HTTP POST Events| API
    Chat -->|Uses Tools (e.g., trigger_policy_generation)| GenPol

    %% API to Queues
    API -->|Writes JSON Payload| Q1
    GenPol -->|Crafts custom 'policy_upload' payload| Q1

    %% Orchestrator Flow
    Q1 -->|Watchdog Trigger| Orch
    Orch --> OrchGenID
    OrchGenID -->|Yes/No| FanOut[Fan-out to Parallel Queues]
    FanOut -->|Duplicate Event| Q2P
    FanOut -->|Duplicate Event| Q2C
    FanOut -->|Duplicate Event| Q2R

    %% Parallel Agent 1: Policy
    Q2P -->|Watchdog Trigger| PolAgent
    PolAgent --> PolRAG
    PolRAG -->|Queries| Chroma
    Chroma -->|Returns Chunks| PolRAG
    PolRAG -.->|Fallback if empty| Mongo
    PolAgent --> PolLLM
    PolLLM -->|Outputs: conflict, score| Q3

    %% Parallel Agent 2: Compliance
    Q2C -->|Watchdog Trigger| CompAgent
    CompAgent --> CompRAG
    CompRAG -->|Queries| Chroma
    Chroma -->|Returns Chunks| CompRAG
    CompAgent --> CompDB
    CompDB -->|Queries| Mongo
    Mongo -->|Returns Controls| CompDB
    CompAgent --> CompLLM
    CompLLM -->|Outputs: auth, violation| Q3

    %% Parallel Agent 3: Risk
    Q2R -->|Watchdog Trigger| RiskAgent
    RiskAgent --> RiskLLM
    RiskLLM -->|Outputs: TVI, risk list| Q3

    %% Decision Engine Flow
    Q3 -->|Watchdog Trigger| DecAgent
    DecAgent --> WaitAll
    WaitAll -->|All 3 present| DecLLM
    DecLLM --> DecLogic
    DecLogic -->|Action Chosen| Q4

    %% Post Processing Flow
    Q4 -->|Watchdog Trigger| AudAgent
    AudAgent -->|Packages Audit Trace| Q5
    
    Q5 -->|Watchdog Trigger| RepAgent
    RepAgent -->|Generates Summary| Q6

    Q6 -->|Watchdog Trigger| FeedAgent
    FeedAgent -->|Appends| LogFile
    FeedAgent --> Q7_Int[Internal Queue Transition]

    Q7_Int -->|To Persistence| PersAgent
    PersAgent --> PersWrite
    PersWrite -->|Writes Action, Audit, Report| Mongo
    PersAgent --> TokenGen
    TokenGen -->|Writes {event_id}.json| Q7

    %% UI Polling / Webhook Completion
    API_Query -->|Polls/Checks| Q7
    Q7 -->|Token Found| API_Query
    API_Query -->|Returns Status| UI

    %% Human in the Loop Logic
    DecLogic -.->|Path == 'Review'| HITL_Review
    HITL_Review -->|Presented in UI| UI
    UI -->|User Decision| HITL_Approve
    UI -->|User Decision| HITL_Reject
    HITL_Approve -.->|Updates Status in DB| Mongo
    HITL_Reject -.->|Updates Status in DB| Mongo

    %% Styling lines for clarity
    linkStyle default stroke:#64748b,stroke-width:2px;
    linkStyle 33,34,35,36,37 stroke:#dc2626,stroke-width:2px,stroke-dasharray: 5 5; %% HITL lines

```
