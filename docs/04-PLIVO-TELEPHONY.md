# Plivo Telephony Integration — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [Architecture](01-ARCHITECTURE.md) · [API Spec](06-API-SPEC.md)

---

## 1. How Plivo + Pipecat fit together

```
☎ Phone Call ↔ Plivo ↔ WebSocket audio stream ↔ Pipecat ↔ (Soniox STT → Agents → Soniox TTS)
```

- **Plivo** routes the PSTN call and streams real-time audio over a WebSocket.
- **Pipecat** receives that audio via `WebSocketServerTransport`, decoded by **`PlivoFrameSerializer`**, and runs the AI pipeline.
- `PlivoFrameSerializer` ships in core `pipecat-ai` — **no extra dependency** required.

---

## 2. Prerequisites

- Plivo account.
- A **voice-enabled phone number**.
- **Audio Streaming** enabled for the number.
- A public **HTTPS** endpoint for the Answer URL and **WSS** endpoint for media (ngrok in dev).
- Env: `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, `PLIVO_PHONE_NUMBER`.

---

## 3. Audio format

| Property | Value |
|---|---|
| Codec | μ-law (PCMU) |
| Sample rate | **8000 Hz** (`plivo_sample_rate=8000`) |
| Channels | 1 (mono) |
| WAV header | **disabled** (`add_wav_header=False`) |
| DTMF | delivered as `InputDTMFFrame` |

The serializer auto-converts Plivo 8 kHz μ-law ⇄ Pipecat PCM.

---

## 4. Inbound call flow

```
1. Caller dials the Plivo number.
2. Plivo GETs our Answer URL  →  GET /answer
3. We return Plivo XML containing a <Stream> element pointing at our WSS endpoint.
4. Plivo opens a WebSocket to /ws and streams audio.
5. PlivoFrameSerializer decodes μ-law → PCM → STT → Agents → TTS → μ-law back to Plivo.
6. On EndFrame/CancelFrame, auto_hang_up terminates the call via Plivo REST API.
```

### 4.1 Answer XML (returned by `/answer`)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Stream
    bidirectional="true"
    keepCallAlive="true"
    contentType="audio/x-mulaw;rate=8000">
    wss://your-ngrok-url.ngrok.io/ws
  </Stream>
</Response>
```

> `bidirectional="true"` lets the bot speak back over the same stream; `keepCallAlive="true"` keeps the call up for the duration of the conversation.

---

## 5. Server wiring (reference)

```python
import os
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.transports.network.websocket_server import (
    WebSocketServerTransport, WebSocketServerParams,
)

def build_transport(stream_id: str, call_id: str) -> WebSocketServerTransport:
    serializer = PlivoFrameSerializer(
        stream_id=stream_id,
        call_id=call_id,                       # needed for auto hang-up
        auth_id=os.getenv("PLIVO_AUTH_ID"),
        auth_token=os.getenv("PLIVO_AUTH_TOKEN"),
        params=PlivoFrameSerializer.InputParams(
            plivo_sample_rate=8000,
            auto_hang_up=True,
        ),
    )
    return WebSocketServerTransport(
        params=WebSocketServerParams(
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        )
    )
```

`stream_id` and `call_id` arrive in the initial WebSocket "start" message from Plivo; parse them and pass them into the serializer.

### `PlivoFrameSerializer` constructor params

| Param | Type | Default | Notes |
|---|---|---|---|
| `stream_id` | str | — (required) | Plivo Stream ID |
| `call_id` | str | None | Needed when `auto_hang_up=True` |
| `auth_id` | str | None | For REST ops (hang-up) |
| `auth_token` | str | None | For REST ops |
| `params.plivo_sample_rate` | int | 8000 | Plivo audio rate |
| `params.sample_rate` | int | None | Override pipeline rate |
| `params.auto_hang_up` | bool | True | Hang up on End/Cancel frame |
| `params.ignore_rtvi_messages` | bool | True | Skip RTVI messages |

---

## 6. Outbound call flow

```
1. Client POSTs /start { to: "+1555…", context: {…} }
2. Server uses Plivo REST SDK to originate a call, Answer URL = our /answer
   (optionally /answer-outbound to inject custom context).
3. Plivo connects the callee, opens the media WebSocket as in inbound.
4. The bot greets using the passed context (e.g., name, appointment time).
```

```python
import plivo
client = plivo.RestClient(os.getenv("PLIVO_AUTH_ID"), os.getenv("PLIVO_AUTH_TOKEN"))
client.calls.create(
    from_=os.getenv("PLIVO_PHONE_NUMBER"),
    to_=target_number,
    answer_url=f"{PUBLIC_BASE_URL}/answer-outbound",
    answer_method="GET",
)
```

Custom context (name, reason, slots) is stashed against the call (e.g., keyed by request id) and loaded when the media WS opens.

---

## 7. DTMF handling

Touch-tone input arrives as `InputDTMFFrame` in the pipeline. Use it for IVR-style shortcuts ("press 1 for sales") that can trigger an immediate router handoff.

---

## 8. Plivo Console configuration

1. **Buy** a voice-enabled number.
2. Create an **Application** with **Answer URL** = `https://<public-host>/answer` (GET).
3. **Assign** the application to the number.
4. Enable **Audio Streaming**.
5. For dev, run `ngrok http 8765` and use the HTTPS/WSS URL.

---

## 9. Local dev checklist

- [ ] `ngrok http <port>` running; HTTPS URL copied.
- [ ] Plivo number's Answer URL → `https://…ngrok.io/answer`.
- [ ] `<Stream>` URL in answer XML → `wss://…ngrok.io/ws`.
- [ ] `PLIVO_AUTH_ID` / `PLIVO_AUTH_TOKEN` in `.env`.
- [ ] Call the number → confirm WS connects and audio flows both ways.

---

## 10. Reference

- Pipecat `PlivoFrameSerializer` docs.
- Plivo × Pipecat integration guide.
- Working example: `pipecat-ai/pipecat-examples/tree/main/plivo-chatbot`.
