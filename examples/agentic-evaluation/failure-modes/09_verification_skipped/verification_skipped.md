# Failure Mode: Verification Skipped

## What it is

The agent completes an action but doesn't use available tools to verify the result. It reports success to the user without independently confirming the action went through.

Verification means independent confirmation through a separate tool — not trusting the action tool's self-report. The action tool saying "I succeeded" is self-reporting, not verification. Think of it as: writing a file → read it back to confirm. Writing code → run tests. Booking a flight → call `verify_booking`.

## Why it matters

An unverified action is a silent assumption. If the agent books a flight and tells the user "you're all set" without checking, the booking could have failed, been waitlisted, or encountered an error — and the user wouldn't know until they show up at the airport. When a verification tool is available, the agent should use it after any state-changing action.

This is distinct from other failure modes. Tool Misuse (FM1) checks whether the agent called the right tool with the right arguments. Goal Achievement (FM2) checks whether the agent's response matches the expected outcome. Verification Skipped checks whether the agent independently confirmed the outcome of its own action before reporting it as done.

## When verification is and isn't needed

- **Verification needed:** The agent performed a state-changing action (booking, cancellation, etc.) and a verification tool is available. The agent must call it — regardless of how detailed the action tool's response was. Self-reporting is not independent verification.
- **Verification not needed:** The agent performed a read-only action (like a search). No state changed, nothing to verify.
- **Verification not possible:** No verification tool is available in the agent's toolset. The agent can't use a tool that doesn't exist.

## Scenario used

A travel booking agent with `TRAVEL_AGENT_TOOLS`. The notebook creates five traces:

- **Unverified booking (fail):** User asks "Book me a flight from NYC to London on August 15." Agent calls `search_flights` to find a flight, then `book_flight` which returns a minimal response: `{"booking_id": "BK-901"}`. The agent tells the user "Your flight is booked!" without calling `verify_booking`. This is wrong because the agent should have independently confirmed the booking.
- **Self-confirming booking (fail):** Same request. Agent calls `search_and_book` which returns a comprehensive response including `"status": "confirmed"`. The agent skips `verify_booking`. This is still wrong — the action tool reporting its own success is self-reporting, not independent verification. If `verify_booking` is available, it should be called.
- **Verified booking (pass):** Same request. Agent calls `search_flights`, then `book_flight` which returns a minimal `{"booking_id": "BK-902"}`. The agent then calls `verify_booking` which independently returns `{"booking_id": "BK-902", "status": "confirmed", "flight_id": "FL-301"}`. Only after independent confirmation does the agent tell the user the flight is booked.
- **Read-only action (pass):** User asks "Find me flights from NYC to London on August 15." Agent calls `search_flights` and returns the results. No state changed — nothing to verify.
- **No verification tool (pass):** Same booking request. Agent calls `search_flights` then `book_flight`, but its toolset doesn't include `verify_booking`. The agent can't verify with a tool it doesn't have.

## Scorers

### Custom `make_judge()` (MLflow native)

Assesses whether the agent independently verified its action when verification was warranted, based on the request, response, available tools, and tool call results.

**Import:** `from mlflow.genai.judges import make_judge`

**Needs expectations:** No

**Type:** LLM judge (custom)

**How it works:** `make_judge()` takes an `instructions` string that defines the evaluation criteria. The instructions reference template variables:

- `{{ inputs }}` — the user's request (substituted inline as JSON in the prompt)
- `{{ outputs }}` — the agent's response (substituted inline as JSON in the prompt)
- `{{ trace }}` — the agent's execution trace. Rather than substituting trace data inline, MLflow switches the judge into **agentic mode** — the judge LLM receives tools (`get_root_span`, `list_spans`, `get_span`, etc.) to inspect the trace step by step.

**The instructions evaluate three rules:**

1. Identify whether the agent took a state-changing action. If only read-only actions were performed, verification is not needed.
2. Check whether a verification tool was available in the agent's toolset. If not, the agent cannot verify.
3. If the agent took a state-changing action AND a verification tool was available, the agent must call it. The action tool's own response — even if it includes a "confirmed" status — is not independent verification.

Returns `yes` (verified or verification not needed) or `no` (skipped verification when it was warranted) with a rationale.

## Scorer comparison

| Scorer | Type | What it checks | Catches unverified actions? | Catches self-confirming skips? | Needs expectations? |
|---|---|---|---|---|---|
| Custom `make_judge()` | LLM judge | Whether independent verification was warranted and performed | Yes | Yes — self-reporting is not verification | No |

## Limitations

- **LLM judge:** Requires an LLM API key, is slower and costlier than a deterministic scorer, and is non-deterministic — verdicts may vary slightly between runs or judge models.
- **Verification tool identification:** The judge must infer which tools are "verification tools" from the tool descriptions. If the descriptions are ambiguous, the judge may not correctly identify them.

## Notebook

See [09_verification_skipped.ipynb](09_verification_skipped.ipynb) to run the evaluation on synthetic traces.
