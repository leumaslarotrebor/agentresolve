# AgentResolve

An autonomous customer-support resolution agent that understands a natural-language
request, gathers the facts it needs through tools, decides on a resolution grounded in
company policy, and executes a real (mock) business action — pausing for human approval
when the action is consequential enough to require it.

Built as a portfolio project for the **Salesforce AI Builder, Emerging Talent — UK & Ireland**
application.

---

## Problem

Support teams spend enormous time on requests that *are* policy-driven and repetitive —
"my order arrived damaged," "I want a refund," "where's my replacement" — but still require
looking up the customer, checking the order, checking policy, checking inventory, and making
a judgment call before acting. A plain chatbot can answer questions about policy; it can't
look anything up, decide anything, or do anything. AgentResolve is built to close that gap
safely.

## Solution

AgentResolve is a small but real agent: given a customer message, it plans a sequence of
tool calls (look up the customer, look up the order, retrieve the relevant policy, check
inventory), reasons about what resolution policy allows, and — if authorized — takes the
action itself (creates a replacement, issues a refund, opens a support ticket) through typed,
validated tools. High-risk actions (refunds over a threshold) stop and wait for a human to
approve or reject before anything happens. Every step is recorded in an audit trail.

## Why Agentic AI? (Not a chatbot, not RAG)

- **Autonomous decision-making** — the agent decides *whether* and *how* to act based on
  retrieved policy and live data (inventory, order status), not a scripted reply.
- **Dynamic tool selection** — the next tool to call is chosen at runtime based on what's
  already known (see `app/agent/planner.py` / `app/agent/llm_client.py`), not a hardcoded
  `if "damaged" in message: create_replacement()`. Swap in a real LLM (below) and the *same*
  tool registry is handed to the model, which chooses tool calls itself via structured
  function calling.
- **Multi-step workflow** — a single request can chain 5–8 tool calls: identify → retrieve →
  ground in policy → validate real-world constraints → act → notify.
- **Real business actions** — the agent doesn't just answer; it mutates state (creates a
  replacement order, decrements inventory, issues a refund, opens a ticket) against a mock
  system of record.
- **Human-in-the-loop** — refunds at or above threshold cannot execute without explicit human
  approval, enforced both in the planner *and* again inside the tool itself (defense in
  depth).
- **Validation, not blind trust** — the agent doesn't act on a tool result without checking
  `success`; a failed tool call is reported as a failure, never as an invented success.
- **Escalation** — anything outside policy, out of stock, or on a suspended account routes to
  a human support ticket instead of silently failing or over-reaching.

---

## Architecture

```text
Customer
   ↓
React + TypeScript (Vite)
   ↓  fetch (JSON over HTTP)
FastAPI
   ↓
Agent Orchestrator (app/agent/agent.py)
   ↓
LLMClient  →  AnthropicLLMClient (real tool calling)
           →  SimulatedPlanner   (deterministic offline fallback)
   ↓
┌──────────────┬──────────────┬──────────────┐
│ Customer     │ Order        │ Knowledge    │
│ Tools        │ Tools        │ Tools        │
├──────────────┼──────────────┼──────────────┤
│ Inventory    │ Action       │ Support      │
│ Tools        │ Tools        │ Tools        │
│ (check_inv.) │ (replacement,│ (ticket,     │
│              │  refund)     │  message)    │
└──────────────┴──────────────┴──────────────┘
                    ↓
          Business Action Layer
          (idempotency, business-rule enforcement)
                    ↓
          Audit / Observability
          (execution steps + structured audit log)
```

### Backend layout

```text
backend/
├── app/
│   ├── main.py                 FastAPI app + routes
│   ├── config.py                Env-driven settings (thresholds, LLM provider, etc.)
│   ├── agent/
│   │   ├── agent.py             Orchestration loop: plan → tool call → validate → record
│   │   ├── llm_client.py        LLMClient interface + real Anthropic tool-calling client
│   │   ├── planner.py           Deterministic offline fallback (same interface)
│   │   ├── prompts.py           System prompt (isolated from app code)
│   │   └── state.py             Per-run mutable AgentState
│   ├── tools/
│   │   ├── registry.py          Tool schemas (for the LLM) + dispatch
│   │   ├── customer_tools.py    get_customer
│   │   ├── order_tools.py       get_order
│   │   ├── knowledge_tools.py   search_knowledge_base
│   │   ├── inventory_tools.py   check_inventory
│   │   └── action_tools.py      create_replacement, create_refund,
│   │                            create_support_ticket, send_customer_message
│   ├── models/                  Pydantic domain + API models
│   ├── services/
│   │   ├── data_store.py        In-memory mock CRM/order/inventory store (loaded from JSON)
│   │   ├── policy_service.py    Keyword-overlap search over the policy knowledge base
│   │   ├── audit_service.py     Run/approval registry + append-only audit log
│   │   └── action_registry.py   Idempotency-key tracking for created actions
│   └── data/                    Mock customers, orders, products, policy docs (JSON)
└── tests/                       pytest suite (see Testing below)
```

### Frontend layout

```text
frontend/
├── src/
│   ├── App.tsx                  Top-level state + layout
│   ├── components/               RequestPanel, StatusPanel, ExecutionTimeline,
│   │                              ApprovalCard, ResolutionCard, AuditLog, Header, ErrorBanner
│   ├── services/api.ts           Typed fetch client for the FastAPI backend
│   └── types/api.ts              TypeScript types mirroring the Pydantic API models
```

---

## Agent workflow

```text
Natural-language request
        ↓
Intent classification            (damaged_product / refund / warranty / general)
        ↓
Context retrieval                get_customer, get_order
        ↓
Policy evaluation                search_knowledge_base (grounds the decision in an
                                  actual policy document, not a guess)
        ↓
Tool selection                   check_inventory, then the agent decides which
                                  action tool applies
        ↓
Tool execution                   create_replacement / create_refund / create_support_ticket
        ↓
Validation                       every tool call's `success` field is checked before
                                  the agent treats it as having happened
        ↓
Business action                  mock inventory decremented, refund/replacement/ticket
                                  record created, idempotency key registered
        ↓
Audit                            step + tool-call event appended to the run's audit trail
        ↓
Customer response                send_customer_message + a short, safe decision summary
```

## Tools

| Tool                     | Purpose                                    | Action |
|---------------------------|---------------------------------------------|--------|
| `get_customer`            | Retrieve a customer by id / email / name     | Read   |
| `get_order`                | Retrieve an order by id, or latest for a customer | Read |
| `search_knowledge_base`   | Retrieve relevant support policy              | Read   |
| `check_inventory`         | Check stock + replacement eligibility         | Read   |
| `create_replacement`      | Create a replacement order                    | Write  |
| `create_refund`           | Issue a refund (gated by approval threshold)  | Write  |
| `create_support_ticket`   | Escalate to a human                           | Write  |
| `send_customer_message`   | Send the final customer-facing message        | Write  |

Every tool validates its own inputs with Pydantic, never raises past `registry.dispatch_tool`
(exceptions are caught and turned into a structured `{"success": false, ...}` result), and
returns a `detail`/`error` field explaining *why* on failure — the agent never has to guess.

---

## Human-in-the-loop

Refunds at or above `REFUND_AUTO_APPROVAL_THRESHOLD_EUR` (default **€100**) cannot be issued
autonomously. The planner detects this *before* calling `create_refund` and instead returns a
`request_approval` decision; the orchestrator creates an `ApprovalRequest`, marks the run
`awaiting_approval`, and returns immediately — no refund tool call has happened yet. The
frontend renders an approval card with the exact action and reason. Only after
`POST /api/approval/{id}/approve` does the orchestrator resume the same `AgentState` and call
`create_refund` with `approved=true`.

The threshold is also enforced a second time *inside* `create_refund` itself
(`amount >= threshold and not approved → error: approval_required`) — a deliberate
defense-in-depth check so a refund can never be issued above threshold even if the
orchestration logic above it had a bug.

Rejecting an approval does not silently drop the request: it's routed to
`create_support_ticket` for manual follow-up, and the customer is notified either way.

## Guardrails

- **Policy grounding** — `search_knowledge_base` is called before any resolution decision;
  nothing is hardcoded to a keyword match on the customer's message.
- **Idempotency** — `create_replacement`, `create_refund`, and `create_support_ticket` accept
  an `idempotency_key`; a repeated call with the same key returns the original record
  (`idempotent_replay: true`) instead of creating a duplicate. The orchestrator also treats a
  repeated request with the same `idempotency_key` as a replay of the whole run.
- **Failure handling** — a failed tool call is recorded as `status: failed` with the real
  error, and the agent's final message never claims an action succeeded that didn't.
- **Escalation** — out-of-stock, suspended accounts, unknown customers/orders, and
  out-of-policy requests all route to either a plain explanation or a support ticket, never a
  fabricated action.
- **Action verification** — `AgentState.record_tool_call` only populates `context["action"]`
  from a tool result whose `success` field is `true`.
- **Max iteration cap** (`LLM_MAX_TOOL_ITERATIONS`) — a runaway planning loop fails safely
  instead of looping forever.

---

## Anthropic integration vs. deterministic fallback

`app/agent/llm_client.py` defines the seam:

- **`AnthropicLLMClient`** calls the real Anthropic Messages API
  (`https://api.anthropic.com/v1/messages`) with the tool registry as `tools`, and interprets
  `stop_reason: tool_use` / text responses to decide the next step. This is genuine
  model-driven structured tool calling — set `LLM_PROVIDER=anthropic` and
  `ANTHROPIC_API_KEY=...` to use it.
- **`SimulatedPlanner`** implements the exact same `LLMClient` interface with a deterministic,
  rule-based `decide_next_step`. It exists so the project is fully runnable and testable
  **without an API key** — every demo scenario, every pytest test, and the manually-verified
  end-to-end runs in this README were executed against this fallback.

Both paths go through the identical tool registry, validation, business-rule enforcement, and
approval workflow — only *which tool to call next* differs. This is a deliberate, disclosed
trade-off: it makes the project honestly runnable by a reviewer with no API key, at the cost
of the "reasoning" being rule-based rather than model-generated in the default mode. Swapping
providers requires no change to `agent.py`, the tools, or the frontend.

---

## "Real-time" execution experience

The backend agent loop is currently **synchronous**: `POST /api/agent/run` doesn't return
until the run reaches `completed`, `awaiting_approval`, or `failed`. There is no
WebSocket/SSE stream of intermediate state, because the run typically completes in well under
a second and adding a background-task + streaming layer to get partial state out mid-run would
have meant restructuring the orchestrator's synchronous return contract — a large change for
a demo project, and explicitly the kind of destabilizing rewrite this project's instructions
said to avoid.

What's implemented instead, honestly:

- The full `AgentRunResult` (with every step's real backend timestamp) comes back from a
  single request.
- The frontend's `ExecutionTimeline` then **reveals those already-completed steps
  progressively** (`App.tsx`, ~260ms apart) so the dashboard reads like a live trace instead of
  a wall of text appearing at once. This is a client-side animation over real data, not a
  server push — it is not a substitute for a genuine incremental stream, and is documented
  here as such.
- `GET /api/agent/{run_id}` is a real, working polling endpoint (used by the frontend after an
  approval decision, and tested directly in `tests/test_api.py`) and would be the basis for
  real polling-based progress if the orchestrator were made to persist intermediate state
  as it runs — noted under Production Roadmap.

---

## Testing

Backend: **pytest**, 38 tests, all passing, `0 warnings`, run time ~0.6s.

```text
$ pytest -v
======================== 38 passed in 0.61s ========================
```

Coverage (`tests/test_agent_scenarios.py`, `tests/test_api.py`, `tests/test_tools.py`):

| Scenario | Test |
|---|---|
| Autonomous replacement (happy path) | `test_happy_path_replacement` |
| Out-of-stock → escalation | `test_out_of_stock_escalates_to_ticket` |
| High-value refund → approval required | `test_high_value_refund_requires_approval_then_completes` |
| Approval **approved** → refund issued | same test, second half |
| Approval **rejected** → escalates to ticket, no refund issued | `test_high_value_refund_rejected_escalates_to_ticket` |
| Low-value refund → autonomous | `test_low_value_refund_is_autonomous` |
| Unknown customer | `test_unknown_customer_handled_gracefully` |
| Unknown order | `test_unknown_order_handled_gracefully` |
| Expired replacement/refund window | `test_expired_refund_window_rejected_without_approval` |
| Suspended account → escalation, not action | `test_suspended_account_is_escalated_not_actioned` |
| Duplicate/idempotent execution | `test_duplicate_execution_does_not_duplicate_action` |
| Tool failure never reported as success | `test_tool_failure_does_not_hallucinate_success` |
| Agent run retrieval | `test_agent_run_can_be_retrieved_after_completion`, `test_get_agent_run_after_run` |
| Invalid tool parameters (missing/wrong type) | `test_create_refund_invalid_parameters_missing_required_field`, `test_create_refund_invalid_parameter_type` |
| Unknown tool / tool exception (API-style failure) | `test_registry_unknown_tool_name_fails_safely`, `test_registry_tool_exception_is_caught_not_raised` |
| Full API integration (health, run, get, approve, reject) | `tests/test_api.py` (8 tests via `TestClient`) |

Frontend: TypeScript project build (`tsc -b && vite build`) and `eslint .` both pass with zero
errors. There is no frontend unit-test runner configured (no Jest/Vitest) — see Limitations.

---

## Demo scenarios

All four were run against the live FastAPI server via `curl` as well as through the pytest
suite; example prompts to paste into the UI:

1. **Autonomous replacement** — *"My laptop arrived damaged and I need a replacement before
   Friday."* (Customer ID `CUST-1001`, Order `ORD-5001`) → replacement created immediately.
2. **High-value refund, human approval** — *"I want a refund for my damaged laptop."*
   (`CUST-1002`, `ORD-5002`, price €1,349) → approval card appears; Approve issues the refund,
   Reject opens a support ticket instead.
3. **Out of stock** — *"My monitor arrived damaged. Send a replacement."* (`CUST-1003`,
   `ORD-5003`, `PROD-102` has 0 inventory) → escalated to a support ticket, no false success.
4. **Invalid / expired request** — *"Refund my order from three years ago."* (`CUST-1004`,
   `ORD-5004`) → explained as outside the refund window, no refund created, no approval
   requested.

The demo chips in the UI prefill each of these automatically.

---

## Technology

- **Backend**: Python 3.12, FastAPI, Pydantic v2, pytest, httpx (Anthropic HTTP client + test
  client)
- **Frontend**: React 18, TypeScript, Vite, plain CSS (no UI framework)
- **Agent**: Anthropic Messages API tool calling (optional) with a deterministic local
  fallback planner
- **Data**: local JSON mock data (no database) for customers/orders/products/policy docs
- **Infra**: Docker + Docker Compose for local multi-container run

No Salesforce technologies are used in this implementation — see the alignment section below.

---

## Local setup

```bash
git clone <this-repo>
cd agentresolve

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env      # optional — defaults work with no .env at all
uvicorn app.main:app --reload --port 8000

# In a second terminal — Frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The frontend defaults to `http://localhost:8000` for the API; override with
`VITE_API_BASE_URL` (e.g. in `frontend/.env.local`) if the backend runs elsewhere.

### Running tests

```bash
cd backend
pytest -v
```

```bash
cd frontend
npm run build     # tsc -b && vite build
npm run lint
```

## Docker setup

```bash
docker compose build
docker compose up
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8080` (nginx serving the Vite production build)

> **Honesty note:** Docker was not available in the sandbox this project was built in, so
> `docker compose build`/`up` could not actually be executed here. The `Dockerfile`s and
> `docker-compose.yml` were written carefully and reviewed by hand (standard multi-stage
> Python/Node + nginx setup, no exotic configuration), but they have not been run
> end-to-end. Please verify on your machine before relying on them for a live demo.

## Environment variables

See [`.env.example`](./.env.example):

```dotenv
LLM_PROVIDER=simulated          # "simulated" (default, no key needed) or "anthropic"
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=
LLM_MAX_TOKENS=1024
LLM_MAX_TOOL_ITERATIONS=8

REFUND_AUTO_APPROVAL_THRESHOLD_EUR=100.0
REPLACEMENT_WINDOW_DAYS=30
REFUND_WINDOW_DAYS=30

CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

No real API keys are committed anywhere in this repository; `.env` is git-ignored.

---

## Production roadmap

This is a local demo with mock data. Toward a production/enterprise deployment:

- Replace the JSON mock store with a real CRM/order-management/inventory backend
  (Salesforce Service Cloud objects, or any real order system) behind the same
  `DataStore` interface.
- Replace `search_knowledge_base`'s keyword-overlap search with real embedding-based
  retrieval over the actual knowledge base.
- Add authentication/authorization (who can approve refunds, role-based access) instead of
  an open `decided_by` string.
- Persist `AgentState` and audit events to a real database instead of in-process memory, so
  runs survive a restart and can be queried/reported on.
- Move the orchestrator to a background task + event stream (SSE/WebSocket) so the frontend
  can show genuinely incremental progress on long-running or multi-approval workflows, rather
  than the client-side reveal described above.
- Structured, centralized observability (OpenTelemetry traces per run, not just a JSONL file).
- Distributed execution / multiple workers instead of a single in-memory process — the current
  idempotency and approval registries are process-local dicts, not shared state.
- A real integration path onto Salesforce/Agentforce: the tool-calling architecture here maps
  directly onto Agentforce's action/topic model, but this project does not integrate with
  Salesforce or Agentforce today.

---

## Why this project demonstrates AI Builder skills

| Salesforce AI Builder capability | AgentResolve demonstration |
|---|---|
| Agentic solutions | Autonomous multi-step support resolution, not a scripted chatbot |
| Prompt engineering | Dedicated system prompt (`agent/prompts.py`) covering role, tools, policy, safety constraints |
| Reasoning | Decisions grounded in retrieved policy + live inventory/order state, not guesses |
| Tool calls | 8 typed, validated tools behind a single registry, callable by a real LLM via structured function calling |
| Python | FastAPI backend, agent orchestrator, Pydantic models, pytest suite |
| JavaScript / TypeScript | Fully typed React frontend, typed API client mirroring backend contracts |
| React | Enterprise dashboard: status, execution timeline, approval workflow, audit log |
| OOP | `Agent`, `AgentState`, `LLMClient`/`AnthropicLLMClient`/`SimulatedPlanner`, `DataStore` |
| Customer-facing problem solving | Every run ends in an honest, specific customer-facing message |
| Testing / debugging | 38 backend tests across scenarios, tools, and the API layer |
| Deployment mindset | Dockerfiles, docker-compose, env-driven configuration, `.gitignore` hygiene |
| Human collaboration | A real approve/reject workflow gating high-risk actions |

This project does **not** use Salesforce or Agentforce — it is presented as architecturally
relevant (the tool-calling + policy-grounded + human-in-the-loop pattern generalizes to
Agentforce-style agent design) and as evidence of hands-on agentic-engineering ability, not as
a Salesforce integration.

---

## Honest limitations

**Simulated / mock, clearly:**
- All customer/order/product/policy data is local JSON, not a real system of record.
- `search_knowledge_base` is keyword-overlap search, not embeddings/vector retrieval.
- By default (`LLM_PROVIDER=simulated`) tool *selection* is a deterministic rule-based
  planner, not an LLM — documented above, and switchable via one env var + a real API key.
- "Real-time" execution is a client-side, post-hoc reveal of already-completed steps, not a
  server-pushed stream (see above).
- State (runs, approvals, idempotency keys, inventory) lives in a single process's memory; it
  resets on restart and would not work correctly across multiple backend replicas.
- No authentication/authorization on any endpoint — anyone who can reach the API can approve
  a refund.
- Docker configuration was written but not executed in this environment (no Docker available)
  — see the Docker section above.
- No frontend automated test suite (Jest/Vitest/RTL) — frontend correctness here rests on
  TypeScript's type checking, ESLint, and manual/API-level verification, not component tests.

**Real and working:**
- The full agent loop — plan, call tool, validate, act, escalate, or pause for approval — is
  real code executing real business-rule logic against real (mock) data, not a hardcoded
  demo path.
- Business rules (replacement window, inventory, refund threshold, idempotency) are enforced
  inside the tools themselves, independent of whatever is calling them.
- The Anthropic tool-calling client is real, working integration code (not stubbed), simply
  not exercised in this README's test run because no API key was available in the build
  environment.
- All 38 backend tests and all four demo scenarios were actually executed against the running
  FastAPI server, not just described.
