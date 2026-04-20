# esp-brookesia ↔ Aleph Integration Guide

## Overview

This document outlines how to integrate Aleph into esp-brookesia with minimum changes to brookesia itself. The integration replaces brookesia's built-in agent/LLM framework with Aleph cloud orchestration, enabling multi-client agent switching, persistent memory layers, and real-time voice interaction via Stage 2 bidirectional WebSocket audio.

## Architecture Layers

```
Device (esp-brookesia)                    Cloud (Aleph)
────────────────────────────────────────────────────────

HAL / ESP-IDF services
        ↓
System Services (Audio, UI)
        ↓
brookesia_agent_aleph (C++ component)
        ↓ (WebSocket audio frames)
                              AlephAudioAdapter
                                    ↓
                              AlephEngine
                                    ↓
                    Multi-client orchestration
                    Memory layers (private/shared/handoff)
                    Event streaming (SSE + WebSocket)
```

## Component: brookesia_agent_aleph

A standalone C++ component repository (not part of esp-brookesia) that implements the `BrookesiaAgentBase` interface and communicates with Aleph via WebSocket.

### Repository Structure (MVP)

```
brookesia_agent_aleph/
├── CMakeLists.txt
├── idf_component.yml
├── include/
│   └── brookesia_agent_aleph.hpp         # Public AlephAgent class
├── src/
│   ├── agent.cpp                         # Lifecycle + message pump (ThreadSafe)
│   ├── websocket_client.cpp              # WebSocket connection handling
│   └── audio_codec.cpp                   # OPUS encode/decode (libopus)
└── docs/
    └── INTEGRATION.md                    # Detailed integration steps
```

### Key Classes

#### AlephAgent (agent.hpp)

```cpp
class AlephAgent : public BrookesiaAgentBase {
public:
    struct Config {
        const char* cloud_endpoint;       // "https://aleph.example.com"
        const char* device_token;         // Device auth token
        const char* device_id;            // Unique device ID
        void* audio_service;              // Pointer to brookesia AudioService
        void* ui_service;                 // Pointer to brookesia UIService
    };

    void init(void* config) override;
    void start() override;
    void stop() override;
    void sleep() override;
    void wakeup() override;
    void on_message(const char* text, uint32_t len) override;
    void on_audio_captured(const int16_t* pcm_data, uint32_t num_frames);
};
```

**Lifecycle:**
1. `init(config)` — Store config, prepare internal state
2. `start()` — Connect to cloud, launch message pump thread
3. `on_audio_captured()` — Called by brookesia AudioService callback (device audio → OPUS → cloud)
4. `sleep()` / `wakeup()` — Pause/resume audio processing
5. `stop()` — Disconnect, cleanup

**Message Pump (background thread):**
- Poll WebSocket for incoming SSE events
- Dispatch delta → UIService (display text)
- Dispatch tool_event with `tool_id: "device.*"` → invoke device action
- Receive audio response (TTS) → decode OPUS → call AudioService (playback)

### Wire Protocol: Stage 2 Bidirectional Audio

**Device → Cloud** (binary WebSocket frame):
```
[session_id:4 bytes]
[client_id:4 bytes]
[timestamp:8 bytes (ms since start)]
[opus_frame:N bytes]
```

**Cloud → Device** (binary WebSocket frame):
```
[audio_type:1 byte]  // 0x00 = TTS response
[opus_frame:N bytes]
```

**Sample Sequence:**
```
Device starts, connects to cloud, creates session
Device captures audio (PCM 16kHz 1ch)
Device → Cloud: WebSocket binary [sess][client][ts][opus_chunk_1]
Device → Cloud: WebSocket binary [sess][client][ts][opus_chunk_2]
[silence detected, ASR triggered]
Cloud → Aleph: POST /sessions/{id}/turns with transcribed text
Cloud → Device: SSE event: status
Cloud → Device: SSE event: delta ("Assistant is thinking...")
Cloud → Device: SSE event: delta ("...and here's the response")
Agent executes, generates reply
Cloud → Aleph: TTS synthesis of reply → OPUS
Cloud → Device: WebSocket binary [0x00][opus_tts_chunk_1]
Cloud → Device: WebSocket binary [0x00][opus_tts_chunk_2]
Cloud → Device: SSE event: final
Device → AudioService: playback TTS audio
Device → UIService: display final reply
```

## Device Action Convention

When an Aleph agent needs to trigger device-side actions (e.g., play alert, set brightness), it emits a `tool_event` with `tool_id` prefixed by `device.`:

**Example SSE event:**
```json
{
  "event_kind": "tool_event",
  "payload": {
    "tool_id": "device.play_alert",
    "status": "started",
    "summary": "Playing alert tone"
  }
}
```

**Device handler routing:**
```cpp
void AlephAgent::_on_device_event(const char* device_action) {
    if (strcmp(device_action, "play_alert") == 0) {
        AudioService* audio = (AudioService*)config_.audio_service;
        audio->play_sound(ALERT_TONE);
    }
    else if (strncmp(device_action, "set_brightness:", 15) == 0) {
        int level = atoi(device_action + 15);
        UIService* ui = (UIService*)config_.ui_service;
        ui->set_brightness(level);
    }
}
```

**Common device actions:**
- `device.play_alert` — Play alert sound
- `device.play_chime` — Play notification chime
- `device.set_brightness:<0-100>` — Adjust screen brightness
- `device.vibrate:<duration_ms>` — Trigger haptic feedback
- `device.show_notification:<text>` — Display notification

## Aleph-side Audio Adapter

The `AlephAudioAdapter` (new in v0.1.5) bridges device audio → Aleph session:

```python
from aleph.adapters import AlephAudioAdapter, MockASRService, MockTTSService

# Initialize with real or mock services
asr_service = MyGoogleASRService()  # TODO: Implement for your cloud
tts_service = MyGoogleTTSService()  # TODO: Implement for your cloud

adapter = AlephAudioAdapter(engine, asr_service, tts_service)

# Consume device audio, route to Aleph, yield TTS response
async for tts_frame in adapter.process_audio_stream(
    session_id="sess_123",
    device_id="device_abc",
    audio_frames=device_audio_stream,
):
    # Send tts_frame back to device
    await websocket.send_bytes(tts_frame.data)
```

**Interfaces (abstract):**

```python
class ASRService(ABC):
    async def transcribe(self, audio_data: bytes, codec: AudioCodec, sample_rate: int) -> str:
        """Encode audio → return transcribed text."""

class TTSService(ABC):
    async def synthesize(self, text: str) -> bytes:
        """Encode text → return OPUS audio."""
```

## Integration Steps (MVP)

### 1. Implement brookesia_agent_aleph Component

Create a new repository `brookesia_agent_aleph` with:
- `AlephAgent` class implementing `BrookesiaAgentBase`
- WebSocket client (using `esp_http_client` or equivalent)
- OPUS audio codec integration (libopus)
- Event mapper for SSE → device actions

**TODOs marked in implementation:**
- [ ] Confirm `BrookesiaAgentBase` interface signatures (init, start, stop, sleep, wakeup, on_message)
- [ ] Confirm `AudioService` interface (play_sound, start_record, stop_record)
- [ ] Confirm `UIService` interface (display_text, set_brightness)
- [ ] Select ASR/TTS service (Google Cloud, local Whisper, etc.)
- [ ] Implement WebSocket frame packing/unpacking
- [ ] Implement OPUS codec integration

### 2. Deploy Aleph Cloud Service

Run Aleph with audio adapter enabled:

```bash
# Install dependencies
pip install -e '.[service]'

# Start Aleph service with ASR/TTS support
python -m aleph.service.api \
  --host 0.0.0.0 \
  --port 8000 \
  --asr-service google-cloud-speech \
  --tts-service google-cloud-tts
```

### 3. Register Device Client in Aleph

Create a client blueprint for the device (e.g., `device_client.json`):

```json
{
  "id": "esp-device-1",
  "display_name": "Living Room Device",
  "handler": "builtin:direct-device-passthrough",
  "declared_capability": {
    "domains": ["device-control", "status"],
    "permissions": ["play_sound", "set_brightness", "show_notification"],
    "handoff_keywords": ["switch", "transfer", "connect"]
  },
  "shared_memory_policy": {
    "domain_writes": ["device-state", "user-preferences"]
  }
}
```

### 4. Device Setup (C++ Integration)

In brookesia app initialization:

```cpp
#include "brookesia_agent_aleph.hpp"

void app_main() {
    // ... existing brookesia setup ...

    // Get references to system services
    AudioService* audio = (AudioService*)system_service_get(AUDIO_SERVICE);
    UIService* ui = (UIService*)system_service_get(UI_SERVICE);

    // Create Aleph agent config
    AlephAgent::Config config = {
        .cloud_endpoint = "https://aleph.example.com",
        .device_token = "device_token_from_registration",
        .device_id = "esp-device-1",
        .audio_service = audio,
        .ui_service = ui,
    };

    // Register with agent manager
    AlephAgent* agent = new AlephAgent();
    agent->init((void*)&config);

    AgentManager::register_agent("aleph", agent);
    AgentManager::select_agent("aleph");
    AgentManager::start();
}
```

### 5. Audio Callback Wiring

Device audio capture must invoke `AlephAgent::on_audio_captured()`:

```cpp
void audio_capture_callback(const int16_t* pcm_data, uint32_t num_frames) {
    AlephAgent* agent = (AlephAgent*)AgentManager::get_active_agent();
    if (agent) {
        agent->on_audio_captured(pcm_data, num_frames);
    }
}

// Register callback with AudioService
AudioService::register_capture_callback(audio_capture_callback);
```

## Testing (MVP Phase)

### Unit Tests (C++)
- WebSocket connection / authentication
- Audio codec (PCM ↔ OPUS roundtrip)
- Event mapping (SSE JSON → device action dispatch)

### Integration Tests (Mock Cloud)
- Mock Aleph cloud endpoint
- Device ↔ cloud audio streaming
- Memory persistence across agent handoffs
- Device action invocation

### Hardware Tests (esp32 Device)
- End-to-end with real Aleph cloud
- Latency measurement (device input → recognition → response → playback)
- Audio quality verification

## Limitations & Future Work

**MVP Limitations:**
- [ ] Silence detection uses buffer-size heuristic; should use RMS-based VAD
- [ ] ASR/TTS default to mock implementations
- [ ] No session recovery on device reconnection
- [ ] No audio jitter buffer for playback smoothing

**Future Enhancements:**
- [ ] Voice activity detection (VAD) for smart silence detection
- [ ] Real ASR/TTS service integration
- [ ] Handoff memory bridge (ensure device context flows across agent switches)
- [ ] Telemetry / observability
- [ ] Adaptive audio frame sizing based on network conditions
- [ ] Multi-language support

## References

- **Aleph**: https://github.com/anthropics/aleph (cloud agent orchestration)
- **esp-brookesia**: https://github.com/espressif/esp-brookesia (hardware platform)
- **libopus**: https://opus-codec.org/ (audio codec)
- **Stage 2 Protocol**: Real-time bidirectional WebSocket audio (defined in this document)
