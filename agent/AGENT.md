# Use case

- **Pitch:** an emergency coordination agent that classifies incoming incidents and cannot dispatch
  resources to the wrong priority level without human confirmation.
- **Who it is for:** emergency operations centre (EOC) dispatchers and first-responder coordinators
  who need to triage simultaneous incidents — wildfires, medical emergencies, hazmat spills,
  search-and-rescue — and route the right units without over-committing scarce resources.
- **Features:**
  - look up live incident reports, check available units and log status updates through chat;
  - classify every dispatch request with Strands Decider 2B: incident type, severity, and whether
    dispatch is justified by the confirmed facts — before any unit is sent;
  - hold ambiguous or low-severity dispatches for human confirmation instead of guessing;
  - show a live decision panel in the demo UI with the classification and confidence for every call;
  - deployed on Amazon Bedrock AgentCore Runtime.
- **The decision handed to Strands Decider 2B:** before the agent dispatches resources, is the
  incident type correctly identified, the severity graded, and the dispatch justified by the
  confirmed report? (`#policy`)
- **Why a decision model:** the check runs on every dispatch — multiple per incident in a busy EOC —
  so it must be fast (sub-second on a GPU), cheap (not an LLM call), and return calibrated
  probabilities the code can branch on without hallucinating a category.
- **Amazon Bedrock:** the conversation, tool use, and recommended next-action text
  (Amazon Nova Pro by default).
