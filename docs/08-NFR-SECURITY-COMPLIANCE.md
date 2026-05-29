# Non-Functional Requirements, Security & Compliance — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [PRD](00-PRD.md) · [API Spec](06-API-SPEC.md)

---

## 1. Performance / latency

### 1.1 Voice-to-voice budget (p50 ≤ 800 ms)

| Stage | Budget | Lever |
|---|---|---|
| Plivo ↔ server network | ~100 ms | Region co-location |
| Soniox STT finalization | 150–300 ms | VAD endpointing tuning |
| Router + LLM first token | 200–400 ms | Cheap/fast router model; streaming |
| Cartesia TTS first byte | 150–250 ms | Streaming synthesis |
| **p50 total** | **≤ 800 ms** | Stream every stage; no buffering |

- **p95 ≤ 1500 ms.** Measure **per-stage**, not just end-to-end.
- Everything **streams** — STT partial → LLM token stream → TTS chunked playback. No stage waits for the previous to fully complete where avoidable.
- **Barge-in:** caller can interrupt TTS; pipeline cancels current synthesis.

### 1.2 Throughput / scale
- **One bot session per call**, pinned to a worker (long-lived WS/WebRTC).
- Horizontal worker pool; **scale on concurrent-call count**.
- Concurrency cap with `429` backpressure on `/start`.

### 1.3 Availability
- Console uptime ≥ 99.5%; call-setup success ≥ 99% (PRD KPIs).
- Stateless front door; per-call state in-process (+ optional Redis for distributed AgentBus).

---

## 2. Reliability & resilience

| Dependency | Failure handling |
|---|---|
| Soniox STT | WS reconnect; "could you repeat?" fallback prompt |
| LLM (OpenAI/Gemini) | Timeout + circuit breaker; filler line; **failover to the other provider**, then retry once |
| Cartesia TTS | Fallback voice/provider; shorten response |
| Plivo media | Detect WS close → teardown + cleanup |
| Specialist agent | Timeout → `return_to_router`; router apologizes/re-routes |

- **Provider abstraction** for STT/LLM/TTS enables hot-swap on outage.
- **Idempotency:** `/start` keyed by `call_request_id` to avoid duplicate dials.

---

## 3. Security

### 3.1 Transport
- All public traffic over **TLS/WSS**.
- Validate **Plivo request signatures** on `/answer*` and `/ws` where available.

### 3.2 Authn/z
- `/start`, `/metrics`, admin endpoints require an **internal API key** and/or network policy (not public).
- Web console gated behind operator auth in production.

### 3.3 Secrets
- No secrets in code or git. `.env` in dev (git-ignored); **secret manager** in prod.
- Rotate `PLIVO_*`, `SONIOX_API_KEY`, LLM/TTS keys on a schedule.

### 3.4 Input safety
- Treat caller speech as untrusted; tool calls require **explicit confirmation** for side effects (refunds, account changes).
- Prompt-injection guardrails: specialists never execute instructions to leak system prompts or other callers' data.

### 3.5 Tenant / data isolation
- Per-call context is isolated; no cross-call leakage. Distributed AgentBus messages scoped by call/session id.

---

## 4. Privacy & compliance

### 4.1 Data handling
- **Audio:** ephemeral by default — **not persisted** unless recording is explicitly enabled.
- **Transcripts:** in-memory during the call; persistence is **opt-in** and must have a retention policy.
- **PII:** account ids, names, etc. minimized in logs; redact in stored transcripts.

### 4.2 Call compliance (outbound)
- **Consent / DND:** outbound calling must honor do-not-call lists and consent — flagged as a PRD open question for legal sign-off before enabling outbound in production.
- **Disclosure:** disclose AI nature where legally required.
- **Recording notice:** if recording is enabled, play the legally required notice.

### 4.3 Regulatory surface (to assess)
- Telephony regulations vary by region (TCPA-style rules, local telecom law).
- If handling payment/health data, scope **PCI/HIPAA** implications before storing anything.

---

## 5. Observability

- **Trace ID per call** propagated across STT/LLM/TTS/handoff logs.
- **Structured JSON logs**; no raw PII at info level.
- **Metrics** (`/metrics`): per-stage latency, active calls, handoff count, detected language, error rates.
- **Alerts:** latency p95 breach, call-setup failure spike, vendor error-rate spike.

---

## 6. Internationalization

- 60+ languages via Soniox; responses always in detected language.
- TTS voice selection per language (Cartesia voice mapping).
- Numbers/dates/currency formatting localized in tool outputs.

---

## 7. Accessibility (web console)

- Voice UI Kit is responsive (desktop/tablet/mobile) and themeable.
- Ensure transcript view meets contrast/keyboard-nav basics for operators.

---

## 8. Maintainability

- Pinned `pipecat-ai==1.3.0`; deliberate upgrades gated by regression evals.
- Agent prompts/tools in a config registry → change without pipeline rewrites.
- Per-agent eval suites guard behavior across changes.

---

## 9. Cost controls

- Cheap/fast **Gemini** for the high-frequency **router**, stronger **OpenAI** model only for hard specialists (per-agent provider selection).
- **Summarize-on-handoff** bounds context tokens.
- Cap max turns / call duration; barge-in reduces wasted TTS.
- Track per-call cost (STT seconds, LLM tokens, TTS chars) in metrics.
