# Product Requirements Document — preet-voicebot-platform

**Status:** Draft v1.0
**Author:** Harsimran Singh
**Last updated:** 2026-05-29
**Related:** [Architecture](01-ARCHITECTURE.md) · [Multi-Agent Design](03-MULTI-AGENT-DESIGN.md) · [Roadmap](07-ROADMAP.md)

---

## 1. Overview

**preet-voicebot-platform** is a real-time, multi-agent voice AI platform. Callers reach the system over a real phone line (via Plivo) or through a browser console (via WebRTC), speak in any of 60+ languages (transcribed by Soniox), and converse with a coordinated set of AI agents. A **router agent** classifies intent and hands the conversation off to **specialist agents** (e.g., Sales, Support, Billing), each with its own prompt, tools, and knowledge — without dropping the call or losing context.

### 1.1 Problem statement

Most voice bots are single-prompt, single-language, and brittle. They:
- Force every caller into one English-first model.
- Collapse all logic into one mega-prompt that becomes unmaintainable.
- Lack a clean handoff to specialized behavior, so they hallucinate outside their lane.
- Require bespoke telephony plumbing.

### 1.2 Solution

A platform that cleanly separates four concerns and makes each best-in-class:
1. **Telephony** — Plivo handles PSTN; Pipecat handles the media pipeline.
2. **Understanding** — Soniox handles multilingual, mixed-language STT.
3. **Reasoning** — a multi-agent topology routes to focused specialists.
4. **Experience** — the Voice UI Kit gives operators a live debug console and end-users an embeddable web widget.

---

## 2. Goals & non-goals

### 2.1 Goals
- **G1.** Answer inbound phone calls and place outbound calls via Plivo.
- **G2.** Transcribe speech in 60+ languages with automatic language identification (Soniox `stt-rt-v4`).
- **G3.** Route each conversation through a router → specialist multi-agent topology with mid-call handoff.
- **G4.** Maintain shared conversation context across handoffs.
- **G5.** Provide a web console (Voice UI Kit) for live monitoring, transcript inspection, and browser calls.
- **G6.** Keep voice-to-voice latency within target budgets (see §7).
- **G7.** Run **both OpenAI and Gemini** as enabled LLM providers, selectable per agent, behind a pluggable adapter (and swap TTS without rewrites).

### 2.2 Non-goals (v1)
- ❌ Building our own ASR/TTS models (we integrate vendors).
- ❌ A visual no-code flow builder (config is code/YAML in v1).
- ❌ Video calls (audio-only for v1).
- ❌ On-prem/air-gapped deployment (cloud-first; revisit later).
- ❌ Billing/payments product surface (platform plumbing only).

---

## 3. Target users & personas

| Persona | Need | How the platform serves it |
|---|---|---|
| **End caller** | Get help in their own language, fast | Multilingual STT, low latency, specialist accuracy |
| **Bot developer** | Define agents/flows without telephony pain | Declarative agents + Pipecat handles media |
| **Ops / support lead** | Watch live calls, debug failures | Voice UI Kit console, transcripts, metrics |
| **Business owner** | Deploy a phone-reachable assistant | Provision a Plivo number → live bot |

---

## 4. User stories

- **US1.** As a caller, I dial a number and the bot greets me and understands me in Hindi/English/Spanish without me choosing a language.
- **US2.** As a caller, when I ask a billing question mid-call, I'm seamlessly handed to the Billing specialist without repeating myself.
- **US3.** As a developer, I add a new specialist agent by writing one prompt + tool set and registering it with the router.
- **US4.** As an ops lead, I open the console and watch the live transcript, which agent is active, and TTS/STT latency.
- **US5.** As a business owner, I trigger an outbound reminder call to a customer with custom context (name, appointment time).
- **US6.** As a caller, I press a DTMF digit ("press 1 for sales") and the bot reacts correctly.

---

## 5. Functional requirements

### 5.1 Telephony (Plivo)
- **FR-T1.** Serve answer XML containing a `<Stream>` element on inbound calls.
- **FR-T2.** Establish a bidirectional WebSocket audio stream (8 kHz μ-law / PCMU) between Plivo and the Pipecat server.
- **FR-T3.** Support outbound calls via a `/start` endpoint that accepts a target number + context payload.
- **FR-T4.** Handle DTMF digits as pipeline events.
- **FR-T5.** Auto-terminate the call on conversation end (`auto_hang_up`).

### 5.2 Speech-to-Text (Soniox)
- **FR-S1.** Real-time streaming transcription via `SonioxSTTService` (model `stt-rt-v4`).
- **FR-S2.** Automatic language identification enabled by default.
- **FR-S3.** Domain/term context injection (e.g., product names) to boost accuracy.
- **FR-S4.** VAD-based finalization for natural turn-taking.

### 5.3 Multi-agent reasoning
- **FR-A1.** A router agent classifies intent and selects a specialist.
- **FR-A2.** Specialist agents each carry a focused system prompt + tool set.
- **FR-A3.** Handoff transfers control and shared context between agents mid-call (AgentBus).
- **FR-A4.** Specialists may be free-form LLM agents OR Pipecat Flows state machines.
- **FR-A5.** A fallback path returns to the router if a specialist cannot help.

### 5.4 Web experience (Voice UI Kit)
- **FR-W1.** `ConsoleTemplate` debug console connected over WebRTC for browser calls.
- **FR-W2.** Live transcript, active-agent indicator, and connection state.
- **FR-W3.** Themeable, responsive (desktop/tablet/mobile).

### 5.5 Platform / ops
- **FR-P1.** Structured logging + per-call trace ID.
- **FR-P2.** Metrics: STT/LLM/TTS latency, handoff count, call duration, language detected.
- **FR-P3.** Config-driven agent registry (no redeploy to tweak prompts in dev).

---

## 6. Success metrics (KPIs)

| Metric | Target (v1) |
|---|---|
| Voice-to-voice latency (p50) | ≤ 800 ms |
| Voice-to-voice latency (p95) | ≤ 1500 ms |
| STT word error rate (top 5 languages) | ≤ 8% |
| Correct router classification | ≥ 90% |
| Handoff success (context retained) | ≥ 95% |
| Call setup success rate | ≥ 99% |
| Console uptime | ≥ 99.5% |

---

## 7. Latency budget (voice-to-voice)

| Stage | Budget |
|---|---|
| Network / Plivo stream | ~100 ms |
| STT finalization (Soniox + VAD) | ~150–300 ms |
| Router + LLM first token | ~200–400 ms |
| TTS first byte (Cartesia) | ~150–250 ms |
| **Total p50 target** | **≤ 800 ms** |

See [08-NFR-SECURITY-COMPLIANCE.md](08-NFR-SECURITY-COMPLIANCE.md) for the full budget and mitigations.

---

## 8. Assumptions & dependencies

- Plivo account with a voice-enabled number and Audio Streaming enabled.
- Soniox API key (`SONIOX_API_KEY`).
- LLM provider keys for **both OpenAI (`OPENAI_API_KEY`) and Gemini (`GOOGLE_API_KEY`)**, and a TTS key (Cartesia).
- Public HTTPS/WSS endpoint (ngrok in dev; cloud + TLS in prod).
- Python ≥ 3.12 runtime; Node ≥ 20 for the web app.

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Cumulative latency exceeds budget | Poor UX | Streaming everything; measure per-stage; tune VAD |
| Router misclassifies intent | Wrong specialist | Confidence threshold + fallback to router; eval set |
| Vendor outage (STT/LLM/TTS) | Calls fail | Pluggable providers; circuit-breaker + graceful message |
| μ-law 8 kHz audio limits STT accuracy | Higher WER | Soniox tuned for telephony; context terms; confirmations |
| Multi-agent context bloat | Cost/latency | Summarize on handoff; scope context per specialist |

## 10. Open questions

- Default model per role — proposed: **Gemini (Flash-class)** for the router, **OpenAI** for specialists. Confirm exact model IDs and cost/latency tradeoff via eval.
- Do we need persistent call recordings/transcripts storage in v1 (compliance)?
- Outbound call compliance (consent, DND lists) — in scope for v1?
- Soniox TTS: confirm availability; otherwise Cartesia remains default TTS.

---

## 11. Out-of-scope backlog (post-v1)

- No-code flow builder UI.
- Video/multimodal.
- Analytics dashboard product.
- Warm transfer to human agents.
- Self-serve number provisioning UI.
