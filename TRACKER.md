# Preet Voicebot Platform — Work Tracker

This document maintains the active context of work, tracking implemented features, milestones, and upcoming tasks for the **Preet Voicebot Platform**.

---

## 📋 Project Status Summary

* **Active Milestone**: [Milestone M3 — Telephony (Plivo) Inbound](#milestone-m3--telephony-plivo-inbound)
* **Active Branch**: `main`
* **GitHub Repository**: [harsimran-preet/preet-voicebot-platform](https://github.com/harsimran-preet/preet-voicebot-platform)
* **Last Verified Date**: 2026-05-29

---

## 🗺️ Roadmap & Milestone Tracker

### Milestone M0 — Planning & Docs
* **Goal**: Establish core architecture and vendor specifications.
* **Status**: 🟢 **COMPLETED** (2026-05-29)
* **Deliverables**: PRD, Architecture, Tech Stack, Multi-Agent Design, Telephony Specs, Soniox STT, API Specs, NFRs.

### Milestone M1 — Single-Agent Web Echo Bot
* **Goal**: Establish the base voice streaming pipeline and local development starter script.
* **Status**: 🟢 **COMPLETED** (2026-05-29)
* **Deliverables**:
  - Python FastAPI app running Pipecat 1.3.0.
  - Selectable LLM adapter supporting OpenAI and Google Gemini.
  - Soniox STT (`stt-rt-v4`) + Cartesia TTS (`sonic-english`).
  - WebRTC Transport with real-time SDP offer/answer exchange.
  - A premium, glowing dark-mode operator debug console (`web/`).
  - Unified `./run.sh` starter command.

### Milestone M2 — Multi-Agent Handoff (Web)
* **Goal**: Transition from a single bot to a router -> specialist multi-agent topology over the AgentBus.
* **Status**: 🟢 **COMPLETED** (2026-05-29)
* **Deliverables**:
  - Wired in-memory `AsyncQueueBus` and standard `AgentRunner`.
  - Created **RouterAgent** using fast Google Gemini for intent classification.
  - Created **SupportAgent** using OpenAI for complex customer help reasoning.
  - Established `handoff_to_support` and `return_to_router` mid-call handoff protocols.
  - Added real-time active agent telemetry (using `ServerMessage`) feeding the frontend console.
  - Designed beautiful glowing UI active agent indicators inside the operator dashboard.

### Milestone M3 — Telephony (Plivo) Inbound
* **Goal**: Connect phone lines to the multi-agent voicebot fleet.
* **Status**: 🟡 **IN PROGRESS**
* **Active Tasks**:
  - [ ] Implement `PlivoFrameSerializer` + `WebSocketServerTransport` for 8 kHz μ-law audio stream.
  - [ ] Setup `/answer` XML endpoint serving bidirectional streaming payload.
  - [ ] Setup `/ws` WebSocket pipeline handler for incoming phone media streams.
  - [ ] Verify DTMF digit collection as input pipeline events.
  - [ ] Verify auto call termination (`auto_hang_up`) upon pipeline end.

### Milestone M4 — Specialists + Flows + Outbound
* **Goal**: Add Sales, Billing, and structured Pipecat Flows for verification.
* **Status**: ⚪ **NOT STARTED**

### Milestone M5 — Hardening & Production
* **Goal**: Latency budget validation, horizontal worker scaling, and secure deployment.
* **Status**: ⚪ **NOT STARTED**

---

## 🛠️ File Inventory & Changes

| File | Purpose | Status |
|---|---|---|
| [run.sh](run.sh) | Starter command that launches both servers concurrently. | 🟢 Completed |
| [server/app.py](server/app.py) | FastAPI entrypoint + WebRTC signaling handshakes. | 🟢 Completed |
| [server/pipeline/core.py](server/pipeline/core.py) | Orchestrates AgentRunner, AsyncQueueBus, and bridge. | 🟢 Completed |
| [server/pipeline/llm_adapter.py](server/pipeline/llm_adapter.py) | Dynamic service adapter for OpenAI and Gemini. | 🟢 Completed |
| [server/agents/router.py](server/agents/router.py) | Gemini-based classification and routing agent. | 🟢 Completed |
| [server/agents/support.py](server/agents/support.py) | OpenAI-based technical troubleshooting specialist agent. | 🟢 Completed |
| [web/src/App.tsx](web/src/App.tsx) | Live dashboard with subagent and latency indicators. | 🟢 Completed |
| [web/src/index.css](web/src/index.css) | Glowing dark-mode visual theme and typography. | 🟢 Completed |
