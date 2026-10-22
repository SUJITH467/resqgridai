# ResQGrid AI — Tasks

## Task 1: Write agent/AGENT.md  ✅
Document the use case: pitch, target users, features, the decision handed to Strands Decider 2B,
why a decision model, and the Amazon Bedrock LLM.

## Task 2: Write agent/decision.py  ✅
Implement `IncidentDispatchGuard(InterventionHandler)` with:
- `PATTERN_TAG = "#policy"`
- `GUARDED_TOOLS = {"dispatch_resources"}`
- `QUESTIONS`: incident_type (choice), severity (score), dispatch_justified (noul)
- `before_invocation`: clear denied set
- `before_tool_call`: classify with decider, branch to Proceed / Confirm / Deny, append to log

## Task 3: Write agent/tools.py  ✅
Implement four `@tool`-decorated functions with clear docstrings:
- `get_incident_report`, `check_available_resources`, `dispatch_resources`, `log_incident_update`
In-memory `INCIDENTS` and `RESOURCES` dicts for demo self-containment.
Export `TOOLS` list.

## Task 4: Write agent/agent.py  ✅
Implement `HackathonAgent` with `NAME`, `SYSTEM_PROMPT`, `EAGER_PROMPT`, `chat()`.
Wire `IncidentDispatchGuard` as an intervention on the Strands Agent.

## Task 5: Write agent/eval_cases.jsonl  ✅
28 JSONL cases (14 tune, 14 test) covering all incident types, all severity levels, and both
dispatch_justified values. State format must match what the guard sends to the decider at runtime.

## Task 6: Write agent/demo_script.yaml  ✅
Four turns: unspecified dispatch (caught), confirmed dispatch (passes), precautionary request
(caught), confirmed critical incident (passes). Set `eager: true` for demo.

## Task 7: Write agent/features.yaml  ✅
Enable AgentCore Memory (resqgridmemory, SEMANTIC + SUMMARIZATION, 7-day expiry).
Leave Gateway disabled (enable when connecting to a real CAD API).

## Task 8: Write .kiro/specs/resqgrid-ai/  ✅
requirements.md, design.md, tasks.md.

## Task 9: Run ./kit test and ./kit run  ⬜
Run `.\kit.cmd test` and `.\kit.cmd run`. Fix any import errors or failing tests.

## Task 10: Run ./kit bench --split tune  ⬜
Tune question wording if accuracy is below 80% on the tune split.
Report held-out results with `.\kit.cmd bench --split test`.
