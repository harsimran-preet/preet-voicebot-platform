# Soniox STT Integration — preet-voicebot-platform

**Status:** Draft v1.0 · **Related:** [Architecture](01-ARCHITECTURE.md) · [Tech Stack](02-TECH-STACK.md)

---

## 1. Why Soniox

- **60+ languages**, real-time streaming over WebSocket.
- **Automatic language identification** — no need to ask the caller to pick a language.
- **Mixed-language speech** in a single conversation (e.g., Hinglish, code-switching).
- **Context / term biasing** to boost domain vocabulary accuracy.
- First-class Pipecat integration (`SonioxSTTService`).

This directly powers PRD goal **G2** (multilingual) and feeds the router's language-aware behavior (see [Multi-Agent Design §4](03-MULTI-AGENT-DESIGN.md)).

---

## 2. Install & auth

```bash
uv add "pipecat-ai[soniox]"
```

Environment variable:
```dotenv
SONIOX_API_KEY=your_key_here
```

---

## 3. Service configuration

| Param | Default | Notes |
|---|---|---|
| `api_key` | — (required) | From `SONIOX_API_KEY` |
| `url` | `wss://stt-rt.soniox.com/transcribe-websocket` | RT WS endpoint |
| `sample_rate` | pipeline default | Match transport (8 kHz for Plivo) |
| `audio_format` | `pcm_s16le` | PCM 16-bit LE |
| `num_channels` | 1 | Mono |
| `vad_force_turn_endpoint` | True | Local VAD finalization for turn-taking |
| `ttfs_p99_latency` | — | Expected latency threshold (s) |
| `settings.model` | `stt-rt-v4` | Current model (`stt-rt-v3-preview` deprecated) |
| `settings.enable_language_identification` | — | Turn on auto language ID |
| `settings.context` | — | Domain/term biasing |

---

## 4. Basic usage

```python
import os
from pipecat.services.soniox.stt import SonioxSTTService

stt = SonioxSTTService(
    api_key=os.getenv("SONIOX_API_KEY"),
    settings=SonioxSTTService.Settings(
        model="stt-rt-v4",
        enable_language_identification=True,
    ),
)
```

## 5. With domain context (recommended)

Bias the recognizer toward our product/brand vocabulary and call domain:

```python
from pipecat.services.soniox.stt import (
    SonioxSTTService, SonioxContextObject, SonioxContextGeneralItem,
)

stt = SonioxSTTService(
    api_key=os.getenv("SONIOX_API_KEY"),
    settings=SonioxSTTService.Settings(
        model="stt-rt-v4",
        enable_language_identification=True,
        context=SonioxContextObject(
            general=[SonioxContextGeneralItem(key="domain", value="telecom-support")],
            terms=["preet-voicebot", "Plivo", "Cartesia", "refund", "DTMF"],
        ),
    ),
)
```

---

## 6. Telephony tuning notes

- Plivo audio is **8 kHz μ-law**; the serializer converts to PCM. Set the pipeline/STT `sample_rate` consistently (8 kHz path) and let the serializer handle resampling.
- Keep `vad_force_turn_endpoint=True` for snappy turn-taking on phone calls.
- Add **confirm-on-critical** prompting (numbers, names) downstream — narrowband audio raises WER even with a strong model.
- Feed **detected language** into the agent context so responses match the caller's language.

---

## 7. Latency

STT finalization budget is **~150–300 ms** within the ≤800 ms p50 voice-to-voice target (see [PRD §7](00-PRD.md)). Tune VAD endpointing to balance responsiveness vs. premature finalization.

---

## 8. Language ID → agent routing

The detected language flows like this:

```
Soniox transcript + language tag
        │
        ▼
   Router agent  ── sets {{language}} in shared context ──▶ all specialists
```

Every agent responds in `{{language}}`; handoffs carry the language so it stays sticky across the call.

---

## 9. TTS note

Soniox advertises a TTS offering, but the Pipecat STT docs we verified cover **STT only**. **v1 default TTS = Cartesia.** Revisit Soniox TTS (single-vendor STT+TTS, one API key) as a fast-follow once its Pipecat support is confirmed. Tracked as an open question in the [PRD §10](00-PRD.md).

---

## 10. Reference

- Pipecat Soniox STT service docs.
- Soniox × Pipecat integration guide + multilingual voice-bot blog.
