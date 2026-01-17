# Voice Assistant mit Gemini Live API

Ein Echtzeit-Sprachassistent fuer Raspberry Pi mit WM8960 Soundkarte, entwickelt in Python mit der Google Gemini Live API.

## Inhaltsverzeichnis

1. [Ueberblick](#ueberblick)
2. [Systemanforderungen](#systemanforderungen)
3. [Installation](#installation)
4. [Konfiguration](#konfiguration)
5. [Verwendung](#verwendung)
6. [Architektur](#architektur)
7. [API-Referenz](#api-referenz)
8. [Fehlerbehebung](#fehlerbehebung)
9. [Entwicklung](#entwicklung)

---

## Ueberblick

Dieser Sprachassistent ermoeglicht eine natuerliche, bidirektionale Sprachkommunikation mit Google's Gemini KI-Modell. Die Anwendung nimmt Sprache ueber das Mikrofon auf, sendet sie in Echtzeit an die Gemini Live API und spielt die Antwort ueber den Lautsprecher ab.

### Hauptfunktionen

- **Echtzeit-Sprachverarbeitung**: Bidirektionale Audio-Streaming-Verbindung
- **Native Audio-Unterstuetzung**: Direkter Audio-Ein- und Ausgang ohne Transkription
- **WM8960-Optimierung**: Speziell fuer die WM8960 Soundkarte konfiguriert
- **Asynchrone Verarbeitung**: Nicht-blockierende Audio-Verarbeitung mit asyncio

### Technische Spezifikationen

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| Eingabe-Samplerate | 16.000 Hz | Mikrofon-Aufnahme |
| Ausgabe-Samplerate (Gemini) | 24.000 Hz | Audio von Gemini |
| Wiedergabe-Samplerate | 16.000 Hz | Lautsprecher-Ausgabe |
| Audio-Format | 16-bit PCM | Signed Integer, Little-Endian |
| Kanaele | Mono | 1 Kanal |
| Chunk-Groesse | 1024 Frames | Audio-Puffer |

---

## Systemanforderungen

### Hardware

- **Raspberry Pi** (getestet mit Pi 4/5)
- **WM8960 Audio HAT** oder kompatible Soundkarte
- **Mikrofon** (im WM8960 integriert oder extern)
- **Lautsprecher** (ueber WM8960 angeschlossen)

### Software

- **Betriebssystem**: Raspberry Pi OS (Debian Trixie oder neuer)
- **Python**: Version 3.10 oder hoeher
- **uv**: Moderner Python-Paketmanager

### Abhaengigkeiten

| Paket | Version | Beschreibung |
|-------|---------|--------------|
| google-genai | >= 1.0.0 | Google GenAI SDK |
| pyaudio | >= 0.2.14 | Audio-Ein/Ausgabe |
| python-dotenv | >= 1.0.0 | Umgebungsvariablen |

---

## Installation

### 1. System vorbereiten

```bash
# System aktualisieren
sudo apt-get update

# PortAudio-Entwicklungsbibliotheken installieren (fuer PyAudio)
sudo apt-get install -y portaudio19-dev
```

### 2. uv installieren (falls nicht vorhanden)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # oder Terminal neu starten
```

### 3. Projekt klonen oder erstellen

```bash
cd /home/gemipi/voice-assistant
```

### 4. Abhaengigkeiten installieren

```bash
uv sync
```

Dies installiert automatisch alle erforderlichen Python-Pakete in einer virtuellen Umgebung.

### 5. API-Schluessel einrichten

1. Besuchen Sie [Google AI Studio](https://aistudio.google.com/)
2. Erstellen Sie einen API-Schluessel
3. Tragen Sie den Schluessel in die `.env`-Datei ein:

```bash
echo "GEMINI_API_KEY=IhrApiSchluesselHier" > .env
```

**Wichtig**: Die `.env`-Datei niemals in Git einchecken!

---

## Konfiguration

### Umgebungsvariablen

| Variable | Erforderlich | Beschreibung |
|----------|--------------|--------------|
| GEMINI_API_KEY | Ja | Google Gemini API-Schluessel |

### Audio-Konfiguration

Die Audio-Einstellungen befinden sich in `src/voice_assistant/config.py`:

```python
@dataclass
class AudioConfig:
    send_sample_rate: int = 16000      # Mikrofon-Samplerate
    receive_sample_rate: int = 24000   # Gemini-Ausgabe-Samplerate
    playback_sample_rate: int = 16000  # Wiedergabe-Samplerate
    chunk_size: int = 1024             # Audio-Puffer-Groesse
    channels: int = 1                  # Mono
    format_width: int = 2              # 16-bit (2 Bytes)
    input_device_index: int = 1        # WM8960 Mikrofon
    output_device_index: int = 1       # WM8960 Lautsprecher
```

### Gemini-Konfiguration

```python
@dataclass
class GeminiConfig:
    model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    system_instruction: str = "You are a helpful, friendly voice assistant."
```

### Audio-Geraete ermitteln

Um die verfuegbaren Audio-Geraete anzuzeigen:

```bash
uv run python -c "
import pyaudio
pa = pyaudio.PyAudio()
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    print(f'[{i}] {info[\"name\"]} - Ein: {info[\"maxInputChannels\"]}, Aus: {info[\"maxOutputChannels\"]}')
pa.terminate()
"
```

Typische Ausgabe auf Raspberry Pi mit WM8960:

```
[0] bcm2835 Headphones - Ein: 0, Aus: 8
[1] wm8960-soundcard - Ein: 2, Aus: 2
[2] sysdefault - Ein: 0, Aus: 128
[3] default - Ein: 0, Aus: 128
```

Der WM8960 ist normalerweise Geraet `1`.

---

## Verwendung

### Sprachassistent starten

```bash
cd /home/gemipi/voice-assistant
uv run voice-assistant
```

Oder alternativ:

```bash
uv run python -m voice_assistant
```

### Erwartete Ausgabe

```
Starting voice assistant...
Model: gemini-2.5-flash-native-audio-preview-12-2025
Speak into your microphone. Press Ctrl+C to exit.

Connected to Gemini. Listening...
```

### Bedienung

1. **Sprechen**: Einfach ins Mikrofon sprechen
2. **Antwort hoeren**: Gemini antwortet automatisch per Sprache
3. **Unterbrechen**: Sie koennen Gemini jederzeit unterbrechen
4. **Beenden**: `Ctrl+C` druecken

### Als Systemdienst einrichten (optional)

Erstellen Sie eine systemd-Service-Datei:

```bash
sudo nano /etc/systemd/system/voice-assistant.service
```

Inhalt:

```ini
[Unit]
Description=Gemini Voice Assistant
After=network.target sound.target

[Service]
Type=simple
User=gemipi
WorkingDirectory=/home/gemipi/voice-assistant
Environment="PATH=/home/gemipi/.local/bin:/usr/bin"
ExecStart=/home/gemipi/.local/bin/uv run voice-assistant
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Dienst aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant
sudo systemctl start voice-assistant
```

---

## Architektur

### Projektstruktur

```
/home/gemipi/voice-assistant/
├── pyproject.toml              # Projekt-Metadaten und Abhaengigkeiten
├── uv.lock                     # Lockfile (automatisch generiert)
├── .env                        # API-Schluessel (nicht in Git!)
├── .gitignore                  # Git-Ignore-Regeln
├── README.md                   # Diese Dokumentation
├── src/
│   └── voice_assistant/
│       ├── __init__.py         # Paket-Exporte
│       ├── __main__.py         # CLI-Einstiegspunkt
│       ├── config.py           # Konfigurationsklassen
│       ├── audio.py            # Audio-Ein/Ausgabe
│       └── assistant.py        # Hauptlogik
└── tests/
    └── test_voice_assistant.py # Validierungstests
```

### Komponenten-Diagramm

```
┌─────────────────────────────────────────────────────────────────┐
│                        VoiceAssistant                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │ AudioCapture│───▶│  Gemini     │───▶│    AudioPlayer      │  │
│  │ (Mikrofon)  │    │  Live API   │    │    (Lautsprecher)   │  │
│  │  16kHz PCM  │    │  WebSocket  │    │     16kHz PCM       │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                                        │              │
│         │              Resampling                │              │
│         │            24kHz → 16kHz               │              │
│         └────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### Datenfluss

1. **Audio-Aufnahme**:
   - PyAudio erfasst Audio vom Mikrofon (16kHz, 16-bit, Mono)
   - Callback-Modus fuer zuverlaessige Aufnahme
   - Daten werden in einem Thread-sicheren Puffer gespeichert

2. **Senden an Gemini**:
   - Audio-Chunks werden asynchron aus dem Puffer gelesen
   - Verpackung als `LiveClientRealtimeInput` mit MIME-Type
   - Senden ueber WebSocket-Verbindung

3. **Empfangen von Gemini**:
   - Asynchrones Empfangen von `ServerContent`
   - Extraktion der `inline_data` aus `model_turn.parts`
   - Audio liegt im 24kHz PCM-Format vor

4. **Audio-Wiedergabe**:
   - Resampling von 24kHz auf 16kHz (lineare Interpolation)
   - Synchrone Wiedergabe ueber PyAudio-Stream

### Klassendiagramm

```
┌─────────────────────────────────────────┐
│            VoiceAssistant               │
├─────────────────────────────────────────┤
│ - _client: genai.Client                 │
│ - _capture: AudioCapture                │
│ - _player: AudioPlayer                  │
│ - _running: bool                        │
│ - audio_config: AudioConfig             │
│ - gemini_config: GeminiConfig           │
├─────────────────────────────────────────┤
│ + run() -> None                         │
│ + shutdown() -> None                    │
│ - _send_audio(session) -> None          │
│ - _receive_audio(session) -> None       │
└─────────────────────────────────────────┘
              │
              │ verwendet
              ▼
┌─────────────────────┐  ┌─────────────────────┐
│    AudioCapture     │  │    AudioPlayer      │
├─────────────────────┤  ├─────────────────────┤
│ - _pyaudio          │  │ - _pyaudio          │
│ - _stream           │  │ - _stream           │
│ - _buffer: deque    │  │ - _running: bool    │
│ - _running: bool    │  │ - config            │
├─────────────────────┤  ├─────────────────────┤
│ + start()           │  │ + start()           │
│ + stop()            │  │ + stop()            │
│ + stream() -> bytes │  │ + play_sync(data)   │
└─────────────────────┘  └─────────────────────┘
```

---

## API-Referenz

### AudioConfig

Konfiguration fuer Audio-Ein- und Ausgabe.

| Attribut | Typ | Standard | Beschreibung |
|----------|-----|----------|--------------|
| send_sample_rate | int | 16000 | Samplerate fuer Mikrofon |
| receive_sample_rate | int | 24000 | Samplerate von Gemini |
| playback_sample_rate | int | 16000 | Samplerate fuer Wiedergabe |
| chunk_size | int | 1024 | Frames pro Audio-Chunk |
| channels | int | 1 | Anzahl Audio-Kanaele |
| format_width | int | 2 | Bytes pro Sample (16-bit) |
| input_device_index | int | 1 | PyAudio Geraete-Index (Eingang) |
| output_device_index | int | 1 | PyAudio Geraete-Index (Ausgang) |

### GeminiConfig

Konfiguration fuer die Gemini Live API.

| Attribut | Typ | Standard | Beschreibung |
|----------|-----|----------|--------------|
| model | str | gemini-2.5-flash-native-audio-preview-12-2025 | Gemini-Modell |
| system_instruction | str | "You are a helpful..." | System-Anweisung |

### VoiceAssistant

Hauptklasse des Sprachassistenten.

#### Konstruktor

```python
VoiceAssistant(
    audio_config: AudioConfig | None = None,
    gemini_config: GeminiConfig | None = None
)
```

#### Methoden

| Methode | Beschreibung |
|---------|--------------|
| `async run()` | Startet den Sprachassistenten |
| `shutdown()` | Beendet den Sprachassistenten sauber |

### AudioCapture

Klasse fuer die Mikrofon-Aufnahme.

#### Methoden

| Methode | Beschreibung |
|---------|--------------|
| `start()` | Startet die Audio-Aufnahme |
| `stop()` | Stoppt die Audio-Aufnahme |
| `async stream()` | Async-Generator fuer Audio-Chunks |

### AudioPlayer

Klasse fuer die Audio-Wiedergabe.

#### Methoden

| Methode | Beschreibung |
|---------|--------------|
| `start()` | Startet den Wiedergabe-Stream |
| `stop()` | Stoppt den Wiedergabe-Stream |
| `play_sync(data)` | Spielt Audio-Daten synchron ab |

### Hilfsfunktionen

#### resample_linear

```python
def resample_linear(data: bytes, from_rate: int, to_rate: int) -> bytes
```

Resampelt 16-bit PCM-Audio mittels linearer Interpolation.

**Parameter:**
- `data`: PCM-Audiodaten als Bytes
- `from_rate`: Quell-Samplerate
- `to_rate`: Ziel-Samplerate

**Rueckgabe:** Resampelte PCM-Audiodaten

---

## Fehlerbehebung

### Haeufige Fehler

#### "GEMINI_API_KEY environment variable not set"

**Ursache**: API-Schluessel fehlt oder ist falsch konfiguriert.

**Loesung**:
```bash
echo "GEMINI_API_KEY=IhrSchluessel" > .env
```

#### "Invalid sample rate"

**Ursache**: Die WM8960 unterstuetzt nicht alle Samplerates.

**Loesung**: Stellen Sie sicher, dass `playback_sample_rate` gleich `send_sample_rate` ist (beide 16000).

#### "You exceeded your current quota"

**Ursache**: API-Kontingent erschoepft.

**Loesung**:
- Warten Sie auf Quota-Reset (normalerweise taeglich)
- Ueberpruefen Sie Ihr Kontingent in [Google AI Studio](https://aistudio.google.com/)
- Upgraden Sie ggf. auf einen kostenpflichtigen Plan

#### ALSA-Warnungen

```
ALSA lib pcm.c:2722:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.front
```

**Ursache**: Normale ALSA-Konfigurationsmeldungen, keine Fehler.

**Loesung**: Diese Warnungen koennen ignoriert werden. Um sie zu unterdruecken:

```bash
uv run voice-assistant 2>/dev/null
```

#### "jack server is not running"

**Ursache**: JACK Audio Server ist nicht installiert/gestartet.

**Loesung**: Diese Meldung kann ignoriert werden - PyAudio verwendet ALSA direkt.

### Audio-Probleme diagnostizieren

#### Mikrofon testen

```bash
uv run python -c "
from voice_assistant.audio import AudioCapture
from voice_assistant.config import AudioConfig
import asyncio

async def test():
    config = AudioConfig()
    capture = AudioCapture(config)
    capture.start()
    count = 0
    async for chunk in capture.stream():
        count += 1
        print(f'Chunk {count}: {len(chunk)} bytes')
        if count >= 10:
            break
    capture.stop()

asyncio.run(test())
"
```

#### Lautsprecher testen

```bash
uv run python -c "
from voice_assistant.audio import AudioPlayer
from voice_assistant.config import AudioConfig
import math, struct

config = AudioConfig()
player = AudioPlayer(config)
player.start()

# 440Hz Testton fuer 1 Sekunde
samples = []
for i in range(16000):
    value = int(16000 * math.sin(2 * math.pi * 440 * i / 16000))
    samples.append(struct.pack('<h', value))

player.play_sync(b''.join(samples))
player.stop()
print('Testton abgespielt')
"
```

### Logs einsehen

```bash
# Bei systemd-Service
sudo journalctl -u voice-assistant -f

# Debug-Ausgabe aktivieren
PYTHONUNBUFFERED=1 uv run voice-assistant
```

---

## Entwicklung

### Tests ausfuehren

```bash
uv run python tests/test_voice_assistant.py
```

Erwartete Ausgabe:

```
============================================================
Voice Assistant Validation Tests
============================================================

[TEST] Imports
----------------------------------------
Testing imports...
  All imports successful

...

============================================================
Test Results Summary
============================================================
  [PASS] Imports
  [PASS] Config Defaults
  [PASS] PyAudio Devices
  ...

Passed: 11/11
Failed: 0/11
```

### Code-Stil

Das Projekt verwendet:
- Type Hints (Python 3.10+)
- Dataclasses fuer Konfiguration
- Async/await fuer nicht-blockierende Operationen

### Erweiterungen

#### System-Anweisung aendern

Bearbeiten Sie `src/voice_assistant/config.py`:

```python
@dataclass
class GeminiConfig:
    model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    system_instruction: str = "Du bist ein freundlicher Assistent, der auf Deutsch antwortet."
```

#### Programmatische Verwendung

```python
import asyncio
from voice_assistant import VoiceAssistant, AudioConfig, GeminiConfig

# Eigene Konfiguration
audio_config = AudioConfig(
    input_device_index=1,
    output_device_index=1,
)

gemini_config = GeminiConfig(
    system_instruction="Du bist ein hilfreicher Kochassistent."
)

# Assistent erstellen und starten
assistant = VoiceAssistant(audio_config, gemini_config)
asyncio.run(assistant.run())
```

### Bekannte Einschraenkungen

1. **WM8960 Samplerate**: Eingabe und Ausgabe muessen die gleiche Samplerate verwenden
2. **Resampling**: Qualitaetsverlust durch lineare Interpolation (24kHz → 16kHz)
3. **Latenz**: Abhaengig von Netzwerkverbindung und API-Auslastung

### Beitragen

1. Fork des Repositories erstellen
2. Feature-Branch erstellen (`git checkout -b feature/NeuesFunktion`)
3. Aenderungen committen (`git commit -am 'Neue Funktion hinzugefuegt'`)
4. Branch pushen (`git push origin feature/NeuesFunktion`)
5. Pull Request erstellen

---

## Lizenz

Dieses Projekt ist fuer den privaten Gebrauch bestimmt.

## Ressourcen

- [Gemini Live API Dokumentation](https://ai.google.dev/gemini-api/docs/live)
- [Google GenAI SDK](https://googleapis.github.io/python-genai/)
- [PyAudio Dokumentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)
- [uv Projekthandbuch](https://docs.astral.sh/uv/guides/projects/)

---

*Zuletzt aktualisiert: Januar 2026*
