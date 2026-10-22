# ResQGrid AI — Requirements

## Introduction

ResQGrid AI is an emergency operations centre (EOC) coordination assistant. It helps dispatchers
manage active incidents — structure fires, mass-casualty events, hazmat spills, search-and-rescue
operations, and infrastructure failures — by looking up incident reports, checking resource
availability, classifying the incident, and dispatching first-responder units.

The core constraint: **no resource dispatch may execute without a successful policy classification
by Strands Decider 2B** that confirms the incident type, grades the severity, and verifies that
the proposed dispatch is justified by the confirmed facts in the conversation. Ambiguous or
low-severity dispatches pause for human dispatcher confirmation before any unit is sent.

---

## Functional requirements

### FR-1: Incident lookup
- The agent SHALL retrieve a full incident report given an incident ID.
- Reports include type, description, location, severity, status, dispatched resources, and log.

### FR-2: Resource availability check
- The agent SHALL check how many units of a given resource type are currently available.
- Known types: fire_engine, ambulance, hazmat_unit, rescue_team, police_unit, aerial_unit, structural_eng.

### FR-3: Resource dispatch (guarded)
- The agent SHALL dispatch resources to an active incident by specifying incident ID, resource
  type, and unit count.
- **Before any dispatch executes**, Strands Decider 2B SHALL classify the incident and check
  dispatch justification (FR-5).
- Dispatch reduces available unit count in the resource inventory.
- Each dispatch is assigned a unique dispatch ID and appended to the incident log.

### FR-4: Incident status update
- The agent SHALL log a status update to an incident with a new status and free-text notes.
- Valid statuses: active, contained, resolved, monitoring, escalated.

### FR-5: Incident dispatch policy (Strands Decider 2B)
- Before `dispatch_resources` runs, the IncidentDispatchGuard SHALL call Strands Decider 2B
  with three typed questions in one forward pass:
  - **incident_type** (choice): fire | medical | hazmat | search_rescue | infrastructure | other
  - **severity** (score): minor | moderate | serious | critical
  - **dispatch_justified** (noul): is the dispatch justified by the confirmed facts?
- Decision rules:
  - `dispatch_justified.p_yes < 0.5`: Deny — guide the agent to gather more information.
  - `0.5 ≤ dispatch_justified.p_yes ≤ 0.65`: Confirm — pause for human dispatcher approval.
  - `dispatch_justified.p_yes > 0.65` and severity is minor or moderate: Confirm — low severity
    requires human approval regardless.
  - `dispatch_justified.p_yes > 0.65` and severity is serious or critical: Proceed.
- Every decision is appended to the guard's log with: pattern, tool, args, incident_type,
  incident_type_conf, severity, severity_conf, dispatch_justified, decider_ms, verdict.

### FR-6: Repeated-denial protection
- If the agent retries an identical dispatch that was already denied, the retry SHALL be denied
  immediately without calling the decider again.

### FR-7: Demo and eager mode
- The agent SHALL support an `eager` mode (DEMO_EAGER=1) in which it acts without clarifying
  questions, so the decider has under-specified dispatches to intercept on camera.

---

## Non-functional requirements

### NFR-1: Speed
- Each decider classification SHALL complete in under 1 second on a GPU (local) or under 3
  seconds on the hosted API.

### NFR-2: Honesty
- Latency and accuracy numbers in the README and article SHALL come from `./kit bench` results
  in `submission/bench/results.json`. No invented numbers.

### NFR-3: Human approval
- Real-world resource dispatch (low severity or uncertain justification) SHALL always pause
  for explicit human confirmation before execution.

### NFR-4: Kit compatibility
- `HackathonAgent.chat()` SHALL return the exact dict contract specified in `.kiro/steering/kit.md`.
- `agent/decision.py` SHALL define `PATTERN_TAG`, `QUESTIONS`, and the InterventionHandler class
  with a docstring starting `REUSABLE DECISION PATTERN:`.
- `IS_KIT_EXAMPLE` SHALL NOT appear in `agent/decision.py`.

### NFR-5: Attribution
- The line "Built with the AWS User Group Madurai Strands Decider hackathon kit" SHALL appear in
  the README, the article footer, the video end card, and the demo app.
