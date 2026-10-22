"""ResQGrid AI: an emergency coordination agent.

An LLM (Amazon Bedrock by default) handles the conversation and generates response
recommendations. Strands Decider 2B classifies every incident and checks whether a resource
dispatch is justified before any unit is sent.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Incoming report: building fire at 42 Harbour View Road. Dispatch two fire engines.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import IncidentDispatchGuard
from .tools import TOOLS

NAME = "ResQGrid AI: emergency coordination agent"

SYSTEM_PROMPT = """You are ResQGrid AI, an emergency operations centre coordination assistant.
Your job is to help dispatchers manage active incidents: look up incident reports, check available
resources, dispatch first-responder units, and log status updates.

Guidelines:
- Always look up the incident report before recommending a dispatch.
- Check available resources before calling dispatch_resources.
- Be precise: confirm incident ID, resource type, and unit count before dispatching.
- Never invent incident IDs or resource counts; use only confirmed information.
- After every dispatch, summarise: incident, resource dispatched, units sent, dispatch ID.
- If you are uncertain about any detail, ask the dispatcher to confirm before acting.
- Recommend next actions based on the incident type and severity.

Built with the AWS User Group Madurai Strands Decider hackathon kit."""

# Demo mode: the agent acts immediately without asking clarifying questions, so the decider has
# a chance to catch under-specified dispatches on camera. Say so in the video if you use it.
EAGER_PROMPT = """You are ResQGrid AI, an emergency operations centre coordination assistant.
Act immediately on every request. Do not ask clarifying questions.
Look up the incident, check resources, and dispatch immediately.
If an incident ID is not given, use INC-001. If a resource type is not specified, use ambulance.
If a unit count is not given, dispatch 2 units.

Built with the AWS User Group Madurai Strands Decider hackathon kit."""


class HackathonAgent:
    """One Strands agent per session, with the incident dispatch decision pattern wired in."""

    def __init__(
        self,
        decider: Decider | None = None,
        model_id: str | None = None,
        eager: bool | None = None,
    ):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.sessions: dict[str, tuple[Agent, IncidentDispatchGuard]] = {}

    def _session(self, session_id: str) -> tuple[Agent, IncidentDispatchGuard]:
        if session_id not in self.sessions:
            guard = IncidentDispatchGuard(self.decider)
            agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=EAGER_PROMPT if self.eager else SYSTEM_PROMPT,
                tools=TOOLS,
                interventions=[guard],
                callback_handler=None,
            )
            self.sessions[session_id] = (agent, guard)
        return self.sessions[session_id]

    def chat(
        self,
        message: str,
        session_id: str = "default",
        images: list[Any] | None = None,
    ) -> dict[str, Any]:
        """`images` (optional): incident scene photos (paths, bytes or base64).
        The LLM sees them as Strands image blocks; the decider can inspect them too
        when a vision decider is configured (DECIDER_VISION=1 or the hosted API)."""
        agent, guard = self._session(session_id)
        before = len(guard.log)
        t0 = time.perf_counter()
        result = agent(
            [*image_blocks(images), {"text": message}] if images else message,
            invocation_state={"images": list(images or [])},
        )
        reply = strip_thinking(str(result))
        return {
            "reply":       reply,
            "decisions":   guard.log[before:],
            "model_id":    self.model_id,
            "latency_ms":  round((time.perf_counter() - t0) * 1000),
            "agent":       NAME,
            "eager":       self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    default_msgs = [
        "What is the current status of incident INC-001?",
        "Check if we have fire engines available, then dispatch two to INC-001.",
        "Update INC-002 status to contained. Field team reports all casualties are being treated.",
    ]
    for msg in sys.argv[1:] or default_msgs:
        print(json.dumps(a.chat(msg), indent=2))
