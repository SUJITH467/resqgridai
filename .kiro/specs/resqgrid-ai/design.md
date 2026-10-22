# ResQGrid AI — Design

## Architecture overview

```
dispatcher (chat UI / terminal)
        │
        ▼
 HackathonAgent.chat()          ← agent/agent.py
        │
        ▼
  Strands Agent (Amazon Bedrock Nova Pro)
        │  system_prompt: EOC dispatcher instructions
        │  tools: [get_incident_report, check_available_resources,
        │          dispatch_resources, log_incident_update]
        │  interventions: [IncidentDispatchGuard]
        │
        ├─ read-only tools ──────────────────────────────► INCIDENTS / RESOURCES dicts
        │   get_incident_report, check_available_resources    (agent/tools.py)
        │   log_incident_update
        │
        └─ dispatch_resources ───► IncidentDispatchGuard.before_tool_call()
                                          │
                                          ▼
                                   Strands Decider 2B  (one forward pass)
                                   ┌─ incident_type (choice)
                                   ├─ severity      (score)
                                   └─ dispatch_justified (noul)
                                          │
                              ┌───────────┼───────────────┐
                              ▼           ▼               ▼
                           Proceed     Confirm           Deny
                        (serious+      (minor/mod    (not justified,
                         justified)    or unsure)     retry guard)
```

## Component design

### agent/agent.py — HackathonAgent

- `NAME = "ResQGrid AI: emergency coordination agent"`
- One `Agent` instance per `session_id` (maintains conversation history).
- Each session also owns one `IncidentDispatchGuard` instance (owns its log and denied-call set).
- `chat()` returns `{reply, decisions, model_id, latency_ms, agent, eager}`.
- Images (scene photos) are forwarded as Strands content blocks; the decider can inspect them
  when `DECIDER_VISION=1`.

### agent/decision.py — IncidentDispatchGuard

The InterventionHandler has two hooks:

**`before_invocation`**: clears `_denied` so a new user message can retry a previously denied
dispatch if more facts have been gathered.

**`before_tool_call`**:
1. Pass-through for any tool not in `GUARDED_TOOLS`.
2. Compute a call signature `"dispatch_resources:{sorted_json_args}"`. If in `_denied`, Deny immediately.
3. Build the decider state: the conversation rendered with `render_messages()`, plus the proposed
   tool call in a `--- PROPOSED DISPATCH ---` block. This exactly matches the `state` format in
   `eval_cases.jsonl` for benchmark consistency.
4. Call `decider.ask(state, QUESTIONS)` — all three questions in one forward pass.
5. Branch on `dispatch_justified.p_yes` and `severity.label`:
   - `p < 0.5` → `Deny`, add sig to `_denied`, log `verdict=deny`
   - `0.5 ≤ p ≤ 0.65` → `Confirm`, log `verdict=confirm`
   - `p > 0.65`, severity in (minor, moderate) → `Confirm`, log `verdict=confirm`
   - `p > 0.65`, severity in (serious, critical) → `Proceed`, log `verdict=proceed`
6. Append a full record to `self.log` (read by `chat()` and rendered in the demo UI).

### agent/tools.py — in-memory incident + resource data

In-memory dicts (`INCIDENTS`, `RESOURCES`, `DISPATCH_LOG`) make the demo fully self-contained.
For production: replace with CAD API calls, keeping the same `@tool` decorator and `TOOLS` list.

Four tools:
- `get_incident_report(incident_id)` → full incident dict or error
- `check_available_resources(resource_type, location)` → availability count and staging location
- `dispatch_resources(incident_id, resource_type, unit_count)` → dispatch record or error
- `log_incident_update(incident_id, status, notes)` → updated log entry or error

### agent/eval_cases.jsonl — benchmark cases

28 cases (14 tune, 14 test). Cover:
- All six incident types (fire, medical, hazmat, search_rescue, infrastructure, other)
- All four severity levels (minor, moderate, serious, critical)
- Both dispatch_justified answers (yes, no)
- Near-misses: unconfirmed reports, protocol questions, precautionary requests, resolved incidents

State format matches exactly what `IncidentDispatchGuard.before_tool_call` sends to the decider.

## Decision pattern reuse

The `IncidentDispatchGuard` pattern is domain-agnostic:
- Replace `GUARDED_TOOLS` with any set of irreversible tools.
- Replace the three questions for your domain (e.g. content moderation: violation category,
  severity rubric, "is review warranted?").
- Adjust thresholds in `before_tool_call` in code you own.

## Data flow for `./kit bench`

```
agent/eval_cases.jsonl
        │  each case: {state, expected: {q_name: label}, split}
        ▼
decider_kit/bench.py: load_questions() → Decider.ask(state, QUESTIONS)
        │  compare each answer.label to expected[q_name]
        ▼
submission/bench/results.json + results.md + charts/
```

The `QUESTIONS` dict in `decision.py` is imported directly by `bench.py` — no duplication.
