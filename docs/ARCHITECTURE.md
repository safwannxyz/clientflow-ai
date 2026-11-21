# Architecture

## 1. System diagram

```mermaid
flowchart TB
    subgraph Sources["Triggers"]
        A1[Contact form]
        A2[WhatsApp]
        A3[Email]
        A4[Referral]
        A5[CV upload]
        A6[Campaign data]
        A7[Contract text]
    end

    subgraph WF["Workflows — business logic only"]
        W1[intake]
        W2[kyc]
        W3[cv_screen]
        W4[watchdog]
        W5[attribution]
        W6[clause review<br/>synchronous]
    end

    subgraph CORE["Core — no business logic"]
        C1[(SQLite<br/>10 tables)]
        C2[Queue<br/>retry · backoff · DLQ]
        C3[Audit<br/>append-only]
        C4[Security<br/>redact · roles · token]
    end

    subgraph SRV["Services"]
        S1[Approvals<br/>pending → decided]
        S2[Metrics]
        S3[Worker<br/>dispatch by kind]
        S4[Seed]
    end

    subgraph UI["Interfaces"]
        U1[Dashboard HTML]
        U2[JSON API]
        U3[CLI]
    end

    A1 & A2 & A3 & A4 & A5 --> W1
    A5 --> W3
    A6 --> W5
    A7 --> W6
    W2 --> S1
    W1 --> S1
    W3 --> S1
    W4 --> S1
    W1 & W2 & W3 & W4 & W5 --> C1
    W1 & W2 & W3 & W4 & W5 --> C3
    S3 --> W1 & W2 & W3 & W4 & W5
    C2 --> S3
    S1 & S2 --> C1
    S1 --> C3
    U1 & U2 & U3 --> C1
    U2 --> W6
```

## 2. Request lifecycle — an enquiry, end to end

```mermaid
sequenceDiagram
    participant Src as Webhook / test
    participant Q as Queue
    participant W as Worker
    participant R as rules.py
    participant DB as SQLite
    participant AP as Approvals
    participant AU as Audit

    Src->>Q: enqueue("intake", payload, key="intake:ENQ-1")
    Q->>Q: INSERT jobs (status=pending, idempotency_key UNIQUE)
    Note over Q: duplicate key → returns None, no second row
    W->>Q: claim("worker-1", limit=20)
    Q-->>W: UPDATE status=running WHERE id IN (...) AND status=pending
    W->>R: classify_area / urgency / language / missing_documents
    R-->>W: area, hits, confidence
    W->>DB: INSERT contacts
    W->>DB: INSERT enquiries (status routed | needs_human)
    W->>AU: log intake_triaged (redacted)
    alt confident and not Arabic
        W->>AP: create acknowledgement (status=pending)
        AP->>AU: log approval_requested
    else low confidence or Arabic
        W->>AU: log escalated_for_human
    end
    W->>Q: complete(job_id)
    Note over W,Q: on exception → fail() → backoff 30/120/600 s → dead letter
    Note over DB: nothing is transmitted at any point
```

## 3. Queue and retry state machine

```mermaid
stateDiagram-v2
    [*] --> pending: enqueue (key UNIQUE)
    pending --> running: claim (BEGIN IMMEDIATE)
    running --> done: handler returns
    running --> pending: fail(), attempts < max — run_after += 30/120/600 s
    running --> failed: fail(), attempts = max — dead letter
    failed --> pending: requeue_dead_letters()
    done --> [*]
    failed --> [*]
```

Failure semantics worth saying out loud: retries are **unconditional**. Idempotency is enforced per handler
via keys, not by the queue, which is why every handler writes with an `idempotency_key` or checks existence
first.

## 4. Approval gate

```mermaid
sequenceDiagram
    participant WF as Workflow
    participant AP as approvals table
    participant H as Human (approver role)
    participant AU as audit_log

    WF->>AP: INSERT (kind, entity, subject, body, status=pending)
    H->>AP: POST /api/approvals/7/decide {decision, note}<br/>header X-Clientflow-Token
    AP->>AP: token_ok() → require(role, "approve")
    AP->>AP: refuse if already decided
    AP->>AU: log approval_approved / approval_rejected
    Note over AP: status becomes approved|rejected — no send function exists
```

## 5. Entity relationship diagram

```mermaid
erDiagram
    CONTACTS ||--o{ ENQUIRIES : "raises"
    MATTERS ||--o{ DOCUMENTS : "requires"
    ENQUIRIES ||--o{ DOCUMENTS : "attaches"
    ENQUIRIES ||--o{ APPROVALS : "drafts"
    MATTERS ||--o{ APPROVALS : "chases"
    CANDIDATES ||--o{ APPROVALS : "shortlists"
    ENQUIRIES ||--o{ AUDIT_LOG : "records"
    JOBS ||--o{ AUDIT_LOG : "reports"

    CONTACTS {
        int id PK
        text name
        text email
        text phone
    }
    ENQUIRIES {
        text id PK
        int contact_id FK
        text source
        text practice_area
        text priority
        real confidence
        int needs_human
        int needs_arabic_review
        text status
        text documents_missing "JSON"
        text idempotency_key "UNIQUE"
    }
    MATTERS {
        text id PK
        text client
        text practice_area
        text status
        text last_activity
        real fee_estimate
    }
    DOCUMENTS {
        int id PK
        text matter_id FK
        text doc_type
        text received_at
        int verified
    }
    CANDIDATES {
        int id PK
        text role_ref
        real score
        text reasons "JSON"
        text decision
        text idempotency_key "UNIQUE"
    }
    CAMPAIGN_WEEKS {
        int id PK
        text campaign
        text week
        real spend
        int leads
        real revenue
    }
    JOBS {
        text id PK
        text kind
        text status
        int attempts
        int max_attempts
        text run_after
        text idempotency_key "UNIQUE"
    }
    APPROVALS {
        int id PK
        text kind
        text entity
        text status
        text decided_by
        text decision_note
    }
    AUDIT_LOG {
        int id PK
        text ts
        text actor
        text action
        text entity
        text detail
    }
    SYSTEMS_REGISTER {
        int id PK
        text name
        text owner
        text data_touched
        text permissions
        text approval_gate
        text status
    }
```

## 6. API architecture

```mermaid
flowchart LR
    C[Client] -->|GET /, /health, /api/*| H[Handler.do_GET]
    C -->|POST /api/approvals/id/decide| P[Handler.do_POST]
    P --> T{token_ok?}
    T -- no --> R401[401 refused<br/>closed by default]
    T -- yes --> A[Approvals.decide]
    A --> RB{require approve}
    RB -- fails --> R400[400 PermissionDenied]
    RB -- ok --> DB[(SQLite)]
    H --> DB
    H --> M[metrics]
    H --> V[render_dashboard]
```

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/` | dashboard, optional `?review=N&compare=1` | none (localhost) |
| GET | `/health` | liveness + schema version | none |
| GET | `/api/stats` | overview, hours saved, findings | none |
| GET | `/api/enquiries` | enquiry list | none |
| GET | `/api/approvals` | pending approvals | none |
| GET | `/api/jobs` | queue health | none |
| GET | `/api/register` | systems register | none |
| GET | `/api/attribution` | campaign spend vs revenue | none |
| GET | `/api/review` | clause review (`?idx=` or `?text=`) | none |
| POST | `/api/approvals/<id>/decide` | record decision | **token** |

Read endpoints are unauthenticated because the server binds to `127.0.0.1`. That is a deliberate bound, not
an oversight — and it is the first thing to change before deploying.

## 7. Why the boundaries are where they are

- **Workflows know business rules, never retries, never HTTP.** A new automation is ~80 lines and inherits
  the queue, audit and approval behaviour for free.
- **Core knows nothing about law, CVs or campaigns.** It could run any group's processes.
- **Services hold the policy** (who may approve, how hours are estimated, what seed data looks like).
- **Interfaces are thin** — the dashboard renders from the same functions the API returns, so a number
  cannot differ between the two.
