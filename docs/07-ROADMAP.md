# Roadmap — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [PRD](00-PRD.md) · [Architecture](01-ARCHITECTURE.md)

Milestones are vertical slices — each ends in something runnable and demoable.

---

## M0 — Planning & docs ✅ (this PR)
**Goal:** Shared understanding + verified tech choices.
- [x] Research Plivo / Soniox / subagents support in Pipecat.
- [x] PRD, Architecture, Tech Stack, Multi-Agent, Plivo, Soniox, API spec, NFRs.
**Exit:** Docs reviewed and approved.

---

## M1 — Single-agent web echo bot ✅
**Goal:** Prove the core pipeline over WebRTC with the Voice UI Kit.
- [x] Scaffold `server/` (FastAPI + Pipecat 1.3.0) and `web/` (Vite + Voice UI Kit).
- [x] `SmallWebRTCTransport` + `/api/offer`.
- [x] Soniox STT → LLM → Cartesia TTS, single hardcoded prompt.
- [x] **LLM adapter** wrapping `OpenAILLMService` + `GoogleLLMService` (env-selectable provider).
- [x] `ConsoleTemplate` connects and you can talk to the bot in the browser.
**Exit:** Browser conversation works; transcript + latency visible in console.
**Demo:** Open localhost console, hold a multilingual conversation.

---

## M2 — Multi-agent handoff (web) ✅
**Goal:** Router → 1 specialist with retained context.
- [x] Add `pipecat-ai-subagents`; stand up AgentBus + AgentRunner (local mode).
- [x] Router agent (intent classify + language ID wiring), default LLM **Gemini**.
- [x] Per-agent provider selection (`ROUTER_LLM`/`SPECIALIST_LLM`) + cross-provider failover.
- [x] One specialist (Support) as free-form LLM agent.
- [x] Implement `handoff` + `return_to_router` with summarize-on-handoff.
- [x] Active-agent indicator in the console.
**Exit:** Mid-call handoff works; context/slots survive; language sticky.
**Demo:** Ask a general question → router; ask support question → handoff.

---

## M3 — Telephony (Plivo) inbound
**Goal:** Same bot reachable by phone.
- [ ] `WebSocketServerTransport` + `PlivoFrameSerializer` + `/answer` XML + `/ws`.
- [ ] Plivo number, app, Audio Streaming; ngrok dev loop.
- [ ] DTMF handling; `auto_hang_up`.
- [ ] 8 kHz μ-law path verified end-to-end.
**Exit:** Call the number, talk to the multi-agent bot, clean hang-up.
**Demo:** Live phone call routed through router + specialist.

---

## M4 — Specialists + Flows + outbound
**Goal:** Production-shaped behavior.
- [ ] Add Sales + Billing specialists with scoped tools.
- [ ] Support specialist upgraded to a **Pipecat Flow** (verify → triage → resolve → close).
- [ ] `POST /start` outbound calls with custom context (`/answer-outbound`).
- [ ] Tool layer (catalog/account/refund stubs → real integrations).
- [ ] Per-agent eval sets + router accuracy harness.
**Exit:** 3 specialists, 1 Flow, outbound calls, evals green.

---

## M5 — Hardening & production
**Goal:** Reliability, observability, deploy.
- [ ] Metrics (`/metrics`), structured logs, per-call trace IDs.
- [ ] Circuit breakers + graceful fallbacks (STT/LLM/TTS).
- [ ] Latency budget validated (p50 ≤ 800 ms, p95 ≤ 1500 ms).
- [ ] Containerize; deploy worker pool behind TLS LB; CDN for web build.
- [ ] Secrets via secret manager; Plivo signature validation.
- [ ] Load test concurrent calls; autoscale policy.
**Exit:** Meets PRD KPIs under load; on-call runbook written.

---

## Dependency order

```
M0 ──▶ M1 ──▶ M2 ──▶ M3 ──▶ M4 ──▶ M5
            (web)   (agents) (phone) (specialists/   (prod)
                                      outbound)
```

## Tracking

Each milestone → a GitHub milestone; tasks → issues. Use vertical-slice issues (independently shippable). The repo `mp-to-issues` / `jira-pm` tooling can convert this roadmap into tickets when ready.

## Risks to watch per milestone

- **M1:** WebRTC/CORS plumbing; sample-rate mismatches.
- **M2:** context bloat across handoff → enforce summarization early.
- **M3:** ngrok/WSS config; μ-law accuracy → add confirm-on-critical.
- **M4:** tool integration scope creep → stub first, integrate later.
- **M5:** latency under concurrency → measure per-stage, scale workers.
