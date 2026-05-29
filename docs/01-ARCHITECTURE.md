# Architecture — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [PRD](00-PRD.md) · [Multi-Agent](03-MULTI-AGENT-DESIGN.md) · [API Spec](06-API-SPEC.md)

---

## 1. System context

```
                          ┌──────────────────────────────────────────────┐
                          │            preet-voicebot-platform             │
                          │                                                │
   ☎ PSTN caller ──▶ Plivo ──WSS audio──▶ ┌───────────────────────────┐   │
                          │               │   Pipecat media pipeline   │   │
   🌐 Web caller ──▶ WebRTC ─────────────▶│  Transport → STT → Agents  │   │
   (Voice UI Kit)         │               │           → TTS → Transport │   │
                          │               └───────────┬───────────────┘   │
                          │                            │                    │
                          │            ┌───────────────┼───────────────┐    │
                          │            ▼               ▼               ▼    │
                          │         Soniox          LLM (OpenAI +      Cartesia│
                          │         STT             Gemini)           TTS    │
                          │                            │                    │
                          │                 ┌──────────┴──────────┐         │
                          │                 │   AgentBus (multi-  │         │
                          │                 │   agent handoff)    │         │
                          │                 └─────────────────────┘         │
                          └──────────────────────────────────────────────┘
```

Two ingress paths, **one shared pipeline core**:
- **Telephony path:** Plivo ↔ `WebSocketServerTransport` + `PlivoFrameSerializer` (8 kHz μ-law).
- **Web path:** Browser ↔ `SmallWebRTCTransport` (via Voice UI Kit `ConsoleTemplate`, `/api/offer`).

Both feed the same **STT → Agents → TTS** core.

---

## 2. Component breakdown

### 2.1 Ingress / transport layer
| Component | Responsibility |
|---|---|
| **Plivo** | PSTN call routing, audio streaming over WebSocket |
| `PlivoFrameSerializer` | μ-law ⇄ PCM conversion, DTMF → `InputDTMFFrame`, auto hang-up |
| `WebSocketServerTransport` | WS endpoint for Plivo media |
| `SmallWebRTCTransport` | Browser WebRTC ingress for the web console |
| **FastAPI app** | Hosts `/answer` (XML), `/ws` (Plivo media), `/api/offer` (WebRTC), `/start` (outbound) |

### 2.2 Perception layer
| Component | Responsibility |
|---|---|
| **Soniox `SonioxSTTService`** | Streaming multilingual STT, language ID, context terms |
| **VAD (Silero)** | Turn-endpoint detection feeding STT finalization |

### 2.3 Reasoning layer (multi-agent)
| Component | Responsibility |
|---|---|
| **Router agent** | Intent classification → specialist selection (default LLM: **Gemini**) |
| **Specialist agents** | Domain logic (Sales/Support/Billing/…) (default LLM: **OpenAI**) |
| **LLM adapter** | Provider abstraction over `OpenAILLMService` + `GoogleLLMService`; chooses provider per agent (`ROUTER_LLM` / `SPECIALIST_LLM`) and fails over between them |
| **AgentBus** (`pipecat-ai-subagents`) | Inter-agent message bus + handoff |
| **Pipecat Flows** (optional per specialist) | Deterministic state machines for structured tasks |
| **Context aggregator** | Shared conversation memory; summarize-on-handoff |

### 2.4 Speech output layer
| Component | Responsibility |
|---|---|
| **Cartesia TTS** (default) | Low-latency streamed speech synthesis |
| TTS adapter | Provider abstraction for swapping vendors |

### 2.5 Experience layer
| Component | Responsibility |
|---|---|
| **Voice UI Kit `ConsoleTemplate`** | Debug console: transcript, active agent, latency |
| **Embeddable widget** | Browser-based caller entry point |

### 2.6 Cross-cutting
- **Observability:** per-call trace ID, structured logs, latency metrics.
- **Config registry:** agent prompts/tools loaded from `agents/*.yaml|py`.
- **Secrets:** env vars (`.env` in dev, secret manager in prod).

---

## 3. Inbound call sequence (telephony)

```
Caller       Plivo            FastAPI /answer      WS /ws (Pipecat)        Soniox   LLM/Agents   Cartesia
  │  dial ───▶ │                    │                    │                   │         │            │
  │            │ ── GET /answer ───▶│                    │                   │         │            │
  │            │ ◀── XML <Stream> ──│                    │                   │         │            │
  │            │ ════════ open WSS audio stream ════════▶│                   │         │            │
  │  speak ───▶│ ═══════ μ-law audio frames ════════════▶│ ── PCM ──────────▶│         │            │
  │            │                    │                    │ ◀── transcript ───│         │            │
  │            │                    │                    │ ── route + prompt ──────────▶│            │
  │            │                    │                    │ ◀──── tokens ────────────────│            │
  │            │                    │                    │ ── text ─────────────────────────────────▶│
  │            │                    │                    │ ◀──── audio ───────────────────────────────│
  │ ◀ hear ════│ ◀═══════ μ-law audio frames ═══════════│                   │         │            │
```

## 4. Multi-agent handoff (logical)

```
                ┌────────────┐
   transcript ─▶│   Router   │── classify intent ──┐
                └────────────┘                      │
                      ▲                              ▼
              fallback│                ┌──────────────────────────┐
                      │                ▼            ▼             ▼
                ┌─────┴─────┐    ┌──────────┐ ┌──────────┐ ┌──────────┐
                │  shared   │◀──▶│  Sales   │ │ Support  │ │ Billing  │
                │  context  │    │ (LLM)    │ │ (Flows)  │ │ (LLM)    │
                └───────────┘    └──────────┘ └──────────┘ └──────────┘
                                   handoff via AgentBus (context summarized)
```

Detail in [03-MULTI-AGENT-DESIGN.md](03-MULTI-AGENT-DESIGN.md).

---

## 5. Deployment topology

### 5.1 Development
- FastAPI + Pipecat on localhost.
- **ngrok** exposes HTTPS/WSS for Plivo answer URL + media stream.
- Vite dev server for the web console (`npm run dev`), proxying `/api/offer` to the backend.

### 5.2 Production (target)
```
            ┌─────────────────────────────────────────────┐
 Plivo ───▶ │  Load balancer (TLS termination, WSS)        │
 Browser ─▶ │            │                                 │
            │            ▼                                 │
            │   ┌────────────────────┐  (1 bot session     │
            │   │ Pipecat workers     │   per process/task) │
            │   │ (containers, N×)    │                     │
            │   └────────────────────┘                     │
            │   Web console: static build on CDN / S3       │
            └─────────────────────────────────────────────┘
                       │            │            │
                    Soniox        LLM API     Cartesia
```

- **Session affinity:** each call = one long-lived WS/WebRTC session pinned to a worker.
- **Scaling:** horizontal worker pool; scale on concurrent-call count.
- **Stateless front door, stateful sessions:** context lives in-process per call (+ optional Redis for cross-process AgentBus in distributed mode).

---

## 6. Data flow & state

- **Audio:** ephemeral, streamed, not persisted by default (recording is opt-in, see compliance).
- **Transcripts:** in-memory during call; optional persistence to DB for analytics (post-v1).
- **Context:** per-call object, summarized and passed on each handoff to bound token growth.
- **Config:** agent definitions loaded at startup (and hot-reload in dev).

---

## 7. Failure modes & resilience

| Failure | Behavior |
|---|---|
| STT vendor error | Retry/reconnect WS; fallback prompt asks caller to repeat |
| LLM timeout | Circuit-breaker; router plays graceful "one moment" filler |
| TTS error | Fallback voice/provider; degrade to shorter responses |
| Plivo stream drop | Detect WS close; mark call ended; cleanup pipeline |
| Specialist stuck | Timeout → return control to router (fallback path) |

---

## 8. Key design decisions

1. **Shared core, dual ingress** — telephony and web reuse the same STT/agent/TTS core; only the transport+serializer differ.
2. **Subagents over one mega-prompt** — maintainability, accuracy, independent evals per agent.
3. **Flows where determinism matters** — structured tasks (e.g., identity verification) use Pipecat Flows; open-ended chat stays free-form LLM.
4. **Provider abstraction** — STT/LLM/TTS behind adapters for vendor swap without pipeline rewrites. **Both OpenAI and Gemini are enabled** and chosen per agent (Gemini for the high-frequency router, OpenAI for specialists), each able to fail over to the other.
5. **Summarize-on-handoff** — keeps context bounded and cheap across many agents.
