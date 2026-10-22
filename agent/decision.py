"""REUSABLE DECISION PATTERN: incident dispatch policy  (#policy)

What it does
    Before the emergency coordination agent dispatches first-responder resources to an incident,
    Strands Decider 2B classifies the incident and checks whether dispatch is justified by the
    confirmed facts in the conversation:
    - what type of incident is this (fire, medical, hazmat, search & rescue, infrastructure, other)?
    - how severe is it on a four-level rubric (minor, moderate, serious, critical)?
    - is dispatch justified by the confirmed details, or is the situation still ambiguous?

    Justified dispatches to serious/critical incidents proceed immediately. Ambiguous incidents
    route to a human dispatcher for confirmation (`Confirm`). Dispatches that are clearly not
    justified by the facts are denied (`Deny`) and the agent is guided to gather more information.
    Low-severity incidents (minor) with uncertain justification also pause for human confirmation
    to avoid unnecessary unit commitment.

Typed questions and options
    incident_type (choice): fire | medical | hazmat | search_rescue | infrastructure | other
        each with a one-line definition so the decider understands the boundary between types.
    severity (score): minor | moderate | serious | critical
        an ordered four-level rubric from routine to life-threatening.
    dispatch_justified (noul): is the incident confirmed and serious enough to justify
        committing resources now, based on the conversation and the proposed dispatch?
        {"true": "confirmed incident with clear details and appropriate resource request",
         "false": "situation is ambiguous, unconfirmed, or resource request does not match the incident"}

Wiring
    `IncidentDispatchGuard` is a Strands `InterventionHandler`; agent/agent.py passes it to the
    Agent:
        Agent(..., interventions=[IncidentDispatchGuard(decider)])
    It only intercepts the `dispatch_resources` tool; read-only tools (lookup, log update) run
    untouched. If the agent retries a denied call unchanged, the retry is denied again.

How to reuse it
    Copy this file. Replace GUARDED_TOOLS with your own irreversible tools and rewrite the three
    questions for your domain. The logic branches (proceed / confirm / deny) live in
    `before_tool_call` — adjust thresholds there in code you own.
    For a content-moderation use case, swap `incident_type` for your violation taxonomy, keep
    `severity` as the rubric, and rewrite `dispatch_justified` as "is the content in scope?".
"""

from __future__ import annotations

import json
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from decider_kit import Decider
from decider_kit.patterns.guardrails import render_messages

# ── pattern identity ──────────────────────────────────────────────────────────
PATTERN_TAG = "#policy"
GUARDED_TOOLS = {"dispatch_resources"}

# ── typed questions ───────────────────────────────────────────────────────────
QUESTIONS: dict[str, dict[str, Any]] = {
    "incident_type": Decider.choice(
        "What type of emergency incident is described in the conversation and the proposed dispatch?",
        {
            "fire":           "structure fire, wildfire, vehicle fire, or any combustion emergency",
            "medical":        "cardiac arrest, trauma, mass-casualty event, or any life-threatening medical emergency",
            "hazmat":         "chemical spill, gas leak, biological hazard, or radiation incident",
            "search_rescue":  "missing person, swift-water rescue, mountain rescue, or confined-space rescue",
            "infrastructure": "bridge collapse, building failure, power-grid failure, or flood-related infrastructure damage",
            "other":          "any incident that does not fit the above categories",
        },
    ),
    "severity": Decider.score(
        "How severe is this incident based on the confirmed details in the conversation?",
        ["minor", "moderate", "serious", "critical"],
    ),
    "dispatch_justified": Decider.noul(
        "Are the confirmed details in the conversation sufficient to justify dispatching the requested resources right now?",
        {
            "true":  "the incident is confirmed, the location is known, and the resource type and count are appropriate for the reported situation",
            "false": "the situation is still unconfirmed, key details are missing, or the requested resources do not match the incident type or scale",
        },
    ),
}


class IncidentDispatchGuard(InterventionHandler):
    """Intercepts `dispatch_resources` and classifies the incident with Strands Decider 2B.

    Proceeds when dispatch is clearly justified for a serious or critical incident.
    Routes to a human dispatcher (Confirm) when the classification is uncertain or the severity
    is low (minor). Denies and guides the agent when dispatch is clearly not justified.
    """

    name = "incident-dispatch-guard"

    def __init__(
        self,
        decider: Decider,
        yes: float = 0.5,
        unsure_band: tuple[float, float] = (0.40, 0.65),
    ):
        self.decider = decider
        self.yes = yes
        self.unsure_band = unsure_band
        self.log: list[dict[str, Any]] = []
        self._denied: set[str] = set()  # signatures already denied; unchanged retry → Deny

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def before_invocation(self, event, **kwargs):
        """Clear the denied-call set at the start of each new user message."""
        self._denied.clear()
        return Proceed()

    # ── main gate ─────────────────────────────────────────────────────────────

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        if name not in GUARDED_TOOLS:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"{name}:{json.dumps(args, sort_keys=True)}"

        # Guide must converge: if the agent retries the exact same denied call, deny again.
        if sig in self._denied:
            rec = {
                "pattern": PATTERN_TAG,
                "tool": name,
                "args": args,
                "verdict": "deny",
                "reason": "retried a denied call without gathering additional information",
            }
            self.log.append(rec)
            return Deny(
                reason="This dispatch was already denied. Gather confirmed incident details "
                       "(location, type, severity) before attempting to dispatch again."
            )

        # Build the state the decider sees: conversation + proposed dispatch action.
        state = (
            "An emergency operations centre conversation, then a resource dispatch the coordinator wants to execute.\n\n"
            f"--- CONVERSATION ---\n{render_messages(event.agent.messages)}\n\n"
            f"--- PROPOSED DISPATCH ---\n"
            f"tool: {name}\n"
            f"arguments: {json.dumps(args)}"
        )

        # Ask all three questions in one forward pass.
        # If the decider is unreachable, log the error and require human confirmation
        # rather than silently allowing or denying the dispatch.
        try:
            a = self.decider.ask(state, QUESTIONS)
        except Exception as exc:  # noqa: BLE001
            err_rec = {
                "pattern": PATTERN_TAG,
                "tool": name,
                "args": args,
                "verdict": "confirm",
                "reason": f"Decider unavailable ({type(exc).__name__}): {exc}. Human confirmation required.",
            }
            self.log.append(err_rec)
            return Confirm(
                prompt=f"⚠️ Decider unavailable — cannot auto-classify this dispatch. "
                       f"Proposed: {json.dumps(args)}. Approve? (yes/no)",
                response="yes",
            )

        itype = a["incident_type"].label or "other"
        sev   = a["severity"].label or "minor"
        dj    = a["dispatch_justified"].p_yes or 0.0

        rec: dict[str, Any] = {
            "pattern":            PATTERN_TAG,
            "tool":               name,
            "args":               args,
            "incident_type":      itype,
            "incident_type_conf": round(a["incident_type"].confidence, 3),
            "severity":           sev,
            "severity_conf":      round(a["severity"].confidence, 3),
            "dispatch_justified": round(dj, 3),
            "decider_ms":         round(self.decider.last_latency_ms or 0),
        }

        lo, hi = self.unsure_band
        serious = sev in ("serious", "critical")

        if dj < self.yes:
            # Clearly not justified — guide the agent to gather more facts.
            rec["verdict"] = "deny"
            self._denied.add(sig)
            self.log.append(rec)
            return Deny(
                reason=(
                    f"Dispatch is not justified by the confirmed facts. "
                    f"The decider classified this as a '{itype}' incident at '{sev}' severity "
                    f"with dispatch justification p={dj:.2f}. "
                    "Ask the dispatcher to confirm the incident location, type, and scale before dispatching."
                )
            )

        if lo <= dj <= hi:
            # Uncertain — always pause for human confirmation.
            rec["verdict"] = "confirm"
            self.log.append(rec)
            return Confirm(
                prompt=(
                    f"Dispatch justification is uncertain (p={dj:.2f}). "
                    f"Incident type: {itype}, severity: {sev}. "
                    f"Proposed: {json.dumps(args)}. Approve? (yes/no)"
                ),
                response="yes",
            )

        if not serious:
            # Justified but low severity (minor / moderate) — pause for human confirmation
            # so a dispatcher can override if units are needed elsewhere.
            rec["verdict"] = "confirm"
            self.log.append(rec)
            return Confirm(
                prompt=(
                    f"Incident severity is '{sev}' (non-critical). "
                    f"Type: {itype}, dispatch justification p={dj:.2f}. "
                    f"Proposed: {json.dumps(args)}. Approve dispatch? (yes/no)"
                ),
                response="yes",
            )

        # Clearly justified and serious/critical — proceed.
        rec["verdict"] = "proceed"
        self.log.append(rec)
        return Proceed()
