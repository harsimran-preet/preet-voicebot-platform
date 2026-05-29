# Tech Stack — preet-voicebot-platform

**Status:** Draft v1.0 · Verified against PyPI/npm as of 2026-05-29.

---

## 1. Backend (Python)

| Package | Version | Purpose |
|---|---|---|
| `pipecat-ai` | **1.3.0** | Core voice/multimodal pipeline framework |
| `pipecat-ai[soniox]` | (extra) | Soniox STT integration |
| `pipecat-ai[cartesia]` | (extra) | Cartesia TTS |
| `pipecat-ai[openai]` | (extra) | OpenAI LLM (`OpenAILLMService`) |
| `pipecat-ai[google]` | (extra) | Google Gemini LLM (`GoogleLLMService`) |
| `pipecat-ai[silero]` | (extra) | Silero VAD for turn detection |
| `pipecat-ai-flows` | latest (≥ May 2026) | Structured conversation state machines |
| `pipecat-ai-subagents` | latest | Distributed multi-agent / AgentBus / handoff |
| `plivo` | latest | Plivo REST SDK (outbound calls, hang-up) |
| `fastapi` + `uvicorn` | latest | HTTP/WS app server (`/answer`, `/ws`, `/api/offer`, `/start`) |
| `python-dotenv` | latest | Env/secrets loading in dev |

**Runtime:** Python **≥ 3.12 recommended** (3.11 minimum).
**Package/install tooling:** `uv` (recommended) or `pip`.

```bash
# recommended
uv add "pipecat-ai[soniox,cartesia,openai,google,silero,webrtc]==1.3.0"
uv add pipecat-ai-flows pipecat-ai-subagents plivo fastapi uvicorn python-dotenv
```

> Plivo needs **no extra Pipecat dependency** — `PlivoFrameSerializer` ships in core `pipecat-ai` and rides on `WebSocketServerTransport`.

---

## 2. Frontend (web console + widget)

| Package | Version | Purpose |
|---|---|---|
| `@pipecat-ai/voice-ui-kit` | latest | React components, hooks, `ConsoleTemplate` |
| `@pipecat-ai/client-js` | `^1.8.0` | Core JS client |
| `@pipecat-ai/client-react` | `^1.4.0` | React bindings/hooks |
| `@pipecat-ai/small-webrtc-transport` | latest | Browser WebRTC transport |
| `react` / `react-dom` | `^19.2.1` | UI runtime |
| `tailwindcss` | `^4.1.13` | Styling (Tailwind v4) |
| `@fontsource-variable/geist` / `-mono` | latest | Optional fonts |
| `typescript` | `^5.9.3` | Types |
| **Vite** | latest | Build/dev server |

```bash
npm create vite@latest web -- --template react-ts
cd web
npm i @pipecat-ai/voice-ui-kit @pipecat-ai/client-js @pipecat-ai/client-react
npm i @pipecat-ai/small-webrtc-transport
npm i @fontsource-variable/geist @fontsource-variable/geist-mono
```

> We **consume** the published `@pipecat-ai/voice-ui-kit` package rather than forking the kit's pnpm monorepo. (The upstream repo itself uses pnpm workspaces, React 19.2.1, Tailwind 4.1.13, `client-js ^1.8`, `client-react ^1.4`.)

---

## 3. External services

| Service | Role | Auth env var |
|---|---|---|
| **Plivo** | Telephony (PSTN, audio streaming) | `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN` |
| **Soniox** | Multilingual STT (`stt-rt-v4`) | `SONIOX_API_KEY` |
| **OpenAI** | LLM reasoning (specialists) | `OPENAI_API_KEY` |
| **Google Gemini** | LLM reasoning (router + multilingual) | `GOOGLE_API_KEY` |
| **Cartesia** | TTS (default) | `CARTESIA_API_KEY` |
| **ngrok** (dev only) | Public tunnel for Plivo webhooks | — |

---

## 4. Version pinning policy

- **Pin `pipecat-ai==1.3.0`** for reproducibility; upgrade deliberately with regression eval.
- Frontend Pipecat client packages (`client-js`, `client-react`) version **independently** from the Python `pipecat-ai` — keep them on the kit's tested majors (`^1.8` / `^1.4`).
- Lock files committed: `uv.lock` (server) and `package-lock.json` (web).

## 5. Why these choices

- **Soniox over single-language STT:** 60+ languages, automatic language ID, mixed-language in one call — essential for a multilingual product and well-suited to telephony audio.
- **Plivo over rolling our own SIP:** managed PSTN + native Pipecat serializer = minimal telephony code.
- **OpenAI + Gemini together:** both are first-class Pipecat LLM services and run behind one adapter, so we pick the best model per agent — fast/cheap **Gemini** (e.g., Flash) for the high-frequency router and strong multilingual turns, **OpenAI** for harder specialist reasoning/tool use. Either can stand in for the other on outage.
- **Pipecat subagents + flows:** purpose-built for mid-call handoff and deterministic sub-tasks — avoids a brittle mega-prompt.
- **Voice UI Kit:** official, React 19/Tailwind 4 console with a drop-in `ConsoleTemplate` and WebRTC transport — instant operator/debug UX.

## 6. `.env` template

```dotenv
# Telephony
PLIVO_AUTH_ID=
PLIVO_AUTH_TOKEN=
PLIVO_PHONE_NUMBER=

# STT
SONIOX_API_KEY=

# LLM (both enabled)
OPENAI_API_KEY=
GOOGLE_API_KEY=
# default provider per role
ROUTER_LLM=gemini          # gemini | openai
SPECIALIST_LLM=openai      # openai | gemini

# TTS
CARTESIA_API_KEY=

# Server
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok.io
WS_HOST=0.0.0.0
WS_PORT=8765
```
