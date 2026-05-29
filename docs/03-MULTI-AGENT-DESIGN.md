# Multi-Agent Design & Prompting — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [Architecture](01-ARCHITECTURE.md) · [PRD](00-PRD.md)

---

## 1. Goals

- Decompose the bot into a **router** + focused **specialists**, each independently maintainable and evaluable.
- Support **mid-call handoff** with retained context (via Pipecat `AgentBus`).
- Mix **free-form LLM agents** and **deterministic Pipecat Flows** agents.
- Keep context **bounded** (summarize on handoff) to control latency and cost.

---

## 2. Topology

```
                       ┌───────────────────────────┐
                       │   ROUTER AGENT  [Gemini]    │
   STT transcript ───▶ │  intent classification +   │
                       │  language-aware greeting   │
                       └───────────┬───────────────┘
                                   │ handoff(intent, ctx_summary)
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
 ┌─────────────┐          ┌─────────────────┐         ┌─────────────┐
 │ SALES        │          │ SUPPORT         │         │ BILLING      │
 │ [OpenAI]     │          │ (Flows,[OpenAI])│         │ [OpenAI]     │
 │ tools:      │          │ states:         │         │ tools:      │
 │  - catalog  │          │  verify→triage→ │         │  - lookup   │
 │  - quote    │          │  resolve→close  │         │  - refund   │
 └──────┬──────┘          └────────┬────────┘         └──────┬──────┘
        │   return_to_router(reason)        │                │
        └───────────────────────────────────┴────────────────┘
                                   ▲
                          shared context store
                       (summary + slots + language)
```

**Roles**
- **Router:** greets, detects language (from Soniox language ID), classifies intent, dispatches. Owns the transport-facing turn until it hands off.
- **Specialists:** own the conversation while active; can call tools; can `return_to_router` when out of scope or done.
- **Fallback:** if a specialist times out or declines, control returns to the router with a reason.

---

## 3. Why subagents (not one prompt)

| One mega-prompt | Multi-agent (this design) |
|---|---|
| Prompt grows unbounded | Each agent prompt is small + focused |
| Hard to eval | Eval each agent independently |
| Tool sprawl confuses the LLM | Scoped tools per specialist |
| Cross-domain hallucination | Specialists stay in lane; router gates |
| One model for everything | **Gemini** for the router, **OpenAI** for hard specialists (per-agent) |

Implemented with **`pipecat-ai-subagents`**: each agent connects to a shared **AgentBus** via an `AgentRunner`; handoff transfers control and capabilities mid-conversation. A **Main agent** owns the hardware transport (Audio/STT/TTS) and bridges to specialist sub-agents over the bus.

---

## 4. Handoff protocol

Each handoff carries a small, structured payload — **never the full transcript**:

```jsonc
{
  "from": "router",
  "to": "billing",
  "reason": "caller asked about a duplicate charge",
  "language": "es",                // from Soniox language ID
  "context_summary": "Caller José, acct #4471, sees two $20 charges on May 28.",
  "slots": { "account_id": "4471", "issue_type": "duplicate_charge" }
}
```

Rules:
1. **Summarize-on-handoff** — the active agent produces a ≤2-sentence summary + slots; the raw transcript is dropped from the new agent's prompt.
2. **Language is sticky** — detected language travels with the handoff so every agent responds in the caller's language.
3. **Single active speaker** — exactly one agent holds the TTS turn at a time; the bus enforces this.
4. **Return path** — specialists must support `return_to_router(reason)` for graceful fallback.

---

## 5. Prompt design

### 5.1 Router system prompt (sketch)
```
You are the ROUTER for preet-voicebot-platform.
Respond in the caller's detected language: {{language}}.
Your ONLY jobs:
1. Greet briefly (once).
2. Identify intent: one of [sales, support, billing, smalltalk, unknown].
3. As soon as intent is clear, call handoff(intent, summary, slots).
Do NOT attempt to resolve domain questions yourself.
If unclear after one clarifying question, handoff(intent="unknown").
Keep turns under 2 sentences. Never invent policies, prices, or account data.
```

### 5.2 Specialist system prompt template
```
You are the {{DOMAIN}} specialist. Language: {{language}}.
Scope: {{one-paragraph scope}}.
Tools: {{tool list}}. Use tools for any factual/account data — never guess.
If the request is outside {{DOMAIN}}, call return_to_router(reason).
Confirm critical details back to the caller (telephony audio is lossy).
Keep responses concise and speakable (no markdown, no lists read aloud).
```

### 5.3 Prompting principles (voice-specific)
- **Speakable output:** no markdown, bullet symbols, or long enumerations — they sound bad in TTS.
- **Confirm-on-critical:** repeat back numbers/names because 8 kHz telephony + accents raise WER.
- **Short turns:** lower latency, more natural barge-in.
- **Tool-first for facts:** prices, balances, account status come from tools, not the model.
- **Language fidelity:** always answer in `{{language}}` from Soniox language ID.

---

## 5.4 LLM provider per agent (OpenAI + Gemini)

Both providers are enabled and run behind one **LLM adapter** (`OpenAILLMService` + `GoogleLLMService`). Provider is chosen per agent via config (`ROUTER_LLM` / `SPECIALIST_LLM`):

| Agent | Default provider | Why |
|---|---|---|
| Router | **Gemini** (Flash-class) | Highest call frequency; fast + cheap classification; strong multilingual for language-aware greeting |
| Sales | **OpenAI** | Nuanced discovery + tool use |
| Support (Flows) | **OpenAI** | Reliable structured tool/step execution |
| Billing | **OpenAI** | Careful reasoning on sensitive account actions |

Rules:
- Provider is an **agent-level setting**, not global — change one agent without touching others.
- **Cross-provider failover:** if the primary provider errors/times out, the adapter retries the same turn on the other provider (prompts are kept provider-neutral).
- **Tool/function-calling parity:** tool schemas are defined once and mapped to each provider's function-calling format by the adapter.
- Model IDs are config, validated by the eval harness on change (see §8).

## 6. Free-form vs. Flows — when to use which

| Use **free-form LLM agent** when… | Use **Pipecat Flows** when… |
|---|---|
| Open-ended Q&A, sales discovery | Identity verification, OTP, structured intake |
| Conversation path is unpredictable | Steps are ordered & compliance-bound |
| Creativity/empathy matters | Determinism & auditability matter |

Flows agents are plugged into the same bus as free-form agents (mixed agent types are supported).

---

## 7. Tooling per specialist (v1)

| Agent | Tools |
|---|---|
| Router | `handoff` |
| Sales | `get_catalog`, `create_quote`, `return_to_router` |
| Support | `verify_identity` (Flow), `create_ticket`, `kb_search`, `return_to_router` |
| Billing | `lookup_account`, `list_charges`, `initiate_refund`, `return_to_router` |

Tools are plain functions registered with each agent; side-effectful tools require confirmation.

---

## 8. Evaluation strategy

- **Per-agent eval sets:** labeled transcripts → expected tool calls / handoffs.
- **Router classification accuracy:** target ≥ 90% (see PRD KPIs).
- **Handoff context retention:** assert slots/summary survive the transfer (≥ 95%).
- **Language fidelity:** detected language == response language.
- **Regression gate on `pipecat-ai` upgrades.**

---

## 9. Failure & fallback

| Situation | Behavior |
|---|---|
| Router unsure | One clarifying question, then `unknown` → general help |
| Specialist out of scope | `return_to_router(reason)` |
| Specialist timeout | Bus reclaims turn → router apologizes, re-routes |
| Tool failure | Specialist explains + offers alternative; logs error |

---

## 10. Implementation notes

- Start with **router + 1 specialist** (M2), prove handoff, then add specialists.
- Begin **local/in-process** AgentBus; move to distributed (cross-machine) only when scale demands.
- Keep agent definitions in a config registry so prompts/tools change without pipeline rewrites.
