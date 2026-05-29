# API Specification — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [Plivo Telephony](04-PLIVO-TELEPHONY.md) · [Architecture](01-ARCHITECTURE.md)

The backend is a single FastAPI app exposing telephony, web-WebRTC, and control endpoints.

---

## 1. Endpoint summary

| Method | Path | Purpose | Consumer |
|---|---|---|---|
| GET | `/answer` | Return Plivo XML with `<Stream>` (inbound) | Plivo |
| GET | `/answer-outbound` | Answer XML for outbound calls (injects context) | Plivo |
| WS | `/ws` | Plivo media WebSocket (μ-law audio) | Plivo |
| POST | `/api/offer` | WebRTC SDP offer for browser console | Voice UI Kit |
| POST | `/start` | Originate an outbound call | Internal/ops |
| GET | `/health` | Liveness/readiness | Infra |
| GET | `/metrics` | Prometheus metrics (latency, calls) | Infra |

---

## 2. `GET /answer` (inbound telephony)

**Response:** `application/xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Stream bidirectional="true" keepCallAlive="true"
          contentType="audio/x-mulaw;rate=8000">
    wss://{PUBLIC_HOST}/ws
  </Stream>
</Response>
```

Query params from Plivo include `CallUUID`, `From`, `To` — logged against the call trace ID.

---

## 3. `WS /ws` (Plivo media)

Bidirectional WebSocket carrying Plivo's audio-streaming protocol.

**Inbound first message (`start` event)** — parse to obtain identifiers:
```jsonc
{
  "event": "start",
  "start": {
    "streamId": "abc123",     // → PlivoFrameSerializer.stream_id
    "callId":   "xyz789",     // → PlivoFrameSerializer.call_id
    "mediaFormat": { "encoding": "audio/x-mulaw", "sampleRate": 8000 }
  }
}
```

Subsequent frames are base64 μ-law media chunks (handled entirely by `PlivoFrameSerializer`). DTMF arrives as events → `InputDTMFFrame`.

**Lifecycle:** open → `start` → media frames ⇄ → `stop`/close → pipeline teardown + `auto_hang_up`.

---

## 4. `POST /api/offer` (web WebRTC)

Used by the Voice UI Kit `ConsoleTemplate` (`transportType="smallwebrtc"`, `connectParams.webrtcUrl="/api/offer"`).

**Request:**
```jsonc
{ "sdp": "<offer sdp>", "type": "offer" }
```
**Response:**
```jsonc
{ "sdp": "<answer sdp>", "type": "answer" }
```

Establishes a `SmallWebRTCTransport` session into the same STT→Agents→TTS core as telephony.

---

## 5. `POST /start` (outbound call)

**Request:**
```jsonc
{
  "to": "+15551234567",
  "context": {
    "customer_name": "José",
    "reason": "appointment_reminder",
    "slots": { "appointment_time": "2026-06-02T15:00:00-04:00" }
  }
}
```
**Response (202):**
```jsonc
{ "call_request_id": "req_8f2a", "status": "initiated" }
```

Server originates the call via the Plivo REST SDK with `answer_url=/answer-outbound`; `context` is stashed under `call_request_id` and loaded when the media WS opens so the bot can greet with it.

**Errors:** `400` invalid number · `429` concurrency cap · `502` Plivo API error.

---

## 6. `GET /answer-outbound`

Like `/answer` but the Stream URL includes a correlation token so `/ws` can load the stashed context:
```xml
<Stream bidirectional="true" keepCallAlive="true"
        contentType="audio/x-mulaw;rate=8000">
  wss://{PUBLIC_HOST}/ws?req=req_8f2a
</Stream>
```

---

## 7. `GET /health`
```jsonc
{ "status": "ok", "active_calls": 3, "pipecat": "1.3.0",
  "llm": { "router": "gemini", "specialist": "openai" } }
```

## 8. `GET /metrics` (Prometheus)
Exposes: `vb_call_total`, `vb_active_calls`, `vb_stt_latency_ms`, `vb_llm_first_token_ms{provider=…}`, `vb_llm_failover_total{from,to}`, `vb_tts_first_byte_ms`, `vb_handoff_total`, `vb_call_duration_seconds`, `vb_language_detected_total{lang=…}`.

---

## 9. Internal events (AgentBus, not HTTP)

Handoff messages on the bus (see [Multi-Agent Design §4](03-MULTI-AGENT-DESIGN.md)):
```jsonc
{ "type": "handoff", "from": "router", "to": "billing",
  "reason": "...", "language": "es",
  "context_summary": "...", "slots": { } }

{ "type": "return", "from": "billing", "to": "router", "reason": "out_of_scope" }
```

---

## 10. Auth & security (summary)

- `/start`, `/metrics` require an internal API key / network policy.
- `/answer*` and `/ws` validate Plivo signatures where available.
- All public traffic over TLS/WSS. Full detail in [08-NFR-SECURITY-COMPLIANCE.md](08-NFR-SECURITY-COMPLIANCE.md).
