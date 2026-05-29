# preet-voicebot-platform

A production-grade, **multi-agent voice AI platform** built on [Pipecat](https://github.com/pipecat-ai/pipecat), with phone-call support via **Plivo** and multilingual speech recognition via **Soniox**. The web/debug experience is powered by the [Pipecat Voice UI Kit](https://github.com/pipecat-ai/voice-ui-kit).

> **One sentence:** Call a phone number (or open the web console) → talk to a fleet of coordinating AI agents that understand 60+ languages and hand off between specialists seamlessly.

---

## Why this platform

| Pillar | What it gives us |
|---|---|
| **Telephony (Plivo)** | Inbound + outbound real phone calls over WebSocket audio streaming. |
| **Multilingual STT (Soniox)** | `stt-rt-v4`, 60+ languages, automatic language ID, mixed-language speech in a single call. |
| **Multi-agent orchestration** | A router agent dispatches to specialist sub-agents (sales, support, billing) with mid-call handoff via the Pipecat AgentBus, optionally driven by Pipecat Flows state machines. |
| **Web console (Voice UI Kit)** | React 19 + Tailwind 4 debug console and embeddable widget for browser-based calls and live observability. |

## Tech stack at a glance

- **Backend:** Python ≥ 3.12, `pipecat-ai` **1.3.0**, `pipecat-ai-flows`, `pipecat-ai-subagents`
- **Telephony:** Plivo (`PlivoFrameSerializer` + `WebSocketServerTransport`)
- **STT:** Soniox (`pipecat-ai[soniox]`, model `stt-rt-v4`)
- **LLM:** OpenAI + Google Gemini (both enabled, pluggable per-agent)
- **TTS:** Cartesia (default), pluggable
- **Frontend:** `@pipecat-ai/voice-ui-kit`, `@pipecat-ai/client-react` `^1.4`, `@pipecat-ai/client-js` `^1.8`, React `^19.2`, Tailwind `^4.1`, Vite
- **Transport (web):** `@pipecat-ai/small-webrtc-transport`

See [docs/02-TECH-STACK.md](docs/02-TECH-STACK.md) for pinned versions and rationale.

## Documentation

All planning docs live in [`docs/`](docs/):

| # | Document | Purpose |
|---|---|---|
| 00 | [PRD](docs/00-PRD.md) | Product requirements: vision, users, scope, success metrics |
| 01 | [Architecture](docs/01-ARCHITECTURE.md) | System design, data flow, deployment topology |
| 02 | [Tech Stack](docs/02-TECH-STACK.md) | Pinned versions, dependency rationale |
| 03 | [Multi-Agent Design](docs/03-MULTI-AGENT-DESIGN.md) | Router/specialist topology, prompting, handoff |
| 04 | [Plivo Telephony](docs/04-PLIVO-TELEPHONY.md) | Phone number setup, XML, inbound/outbound flow |
| 05 | [Soniox STT](docs/05-SONIOX-STT.md) | Multilingual STT config and tuning |
| 06 | [API Spec](docs/06-API-SPEC.md) | HTTP/WebSocket contracts |
| 07 | [Roadmap](docs/07-ROADMAP.md) | Phased milestones M0–M5 |
| 08 | [NFRs / Security / Compliance](docs/08-NFR-SECURITY-COMPLIANCE.md) | Latency budgets, security, data handling |

## Repository layout (target)

```
preet-voicebot-platform/
├── README.md
├── docs/                      # ← all planning documents (this PR)
├── server/                    # Python Pipecat backend (later milestone)
│   ├── agents/                # router + specialist agents
│   ├── pipeline/              # STT/LLM/TTS wiring
│   ├── telephony/             # Plivo serializer + answer XML
│   └── app.py                 # FastAPI: /answer, /api/offer, /start, /ws
└── web/                       # Vite + Voice UI Kit frontend (later milestone)
```

## Quick start

1. **Configure API Keys**: Open `server/.env` and add your vendor credentials:
   ```dotenv
   SONIOX_API_KEY=your_soniox_key
   CARTESIA_API_KEY=your_cartesia_key
   GOOGLE_API_KEY=your_gemini_key
   ```
2. **Start Both Servers**: Run the unified concurrent launcher command:
   ```bash
   ./run.sh
   ```
3. **Open Console**: Open your browser at `http://localhost:5173` to test the real-time multilingual voice assistant.

## Status

📋 **Milestone M1 Completed.** The core single-agent voice pipeline, FastAPI backend, and React dashboard console are fully scaffolded and operational.
- We are currently designing and implementing **Milestone M2 — Multi-Agent Handoff**.
- For active work checklists and file details, see the live [TRACKER.md](TRACKER.md).
