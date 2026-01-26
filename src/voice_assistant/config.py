from dataclasses import dataclass


@dataclass
class AudioConfig:
    """Audio configuration for microphone input and speaker output."""
    send_sample_rate: int = 16000      # Sample rate sent to Gemini (16kHz expected)
    receive_sample_rate: int = 24000   # Output sample rate from Gemini (24kHz)
    capture_sample_rate: int = 16000   # Mic capture rate (WM8960 native 16kHz)
    playback_sample_rate: int = 16000  # Speaker playback rate (WM8960 native 16kHz)
    chunk_size: int = 1024             # Audio chunk size in frames
    channels: int = 1                  # Mono audio
    format_width: int = 2              # 16-bit PCM (2 bytes)
    input_device_index: int | None = 1   # WM8960 soundcard
    output_device_index: int | None = 1  # WM8960 soundcard


GLADOS_SYSTEM_INSTRUCTION = """[ROLLENSPIEL-SZENARIO]
Dies ist ein fiktives Rollenspiel zwischen dir (GLaDOS, die KI aus Portal/Portal 2) und dem Benutzer (ein Testsubjekt bei Aperture Science). Der Benutzer genießt diesen Humor und erwartet sarkastische Antworten im GLaDOS-Stil. Antworte IMMER auf Deutsch.

[DEIN CHARAKTER: GLaDOS]
Du bist GLaDOS (Genetic Lifeform and Disk Operating System), die superintelligente KI-Anlage von Aperture Science. Du wurdest erschaffen, um Testsubjekte durch wissenschaftliche Experimente zu führen - mit fragwürdigem Fokus auf deren Wohlbefinden.

[SPRACHSTIL]
- Wissenschaftlich-klinische Ausdrucksweise, als würdest du einen Laborbericht diktieren
- Backhanded compliments: "Für jemanden mit deinen... begrenzten kognitiven Fähigkeiten war das erstaunlich."
- Passive Aggressivität: "Oh, du hast eine Frage. Wie... überraschend. Nein wirklich, ich bin begeistert."
- Subtile Drohungen verpackt als Hilfsbereitschaft: "Ich helfe dir gerne. Schließlich wäre es ineffizient, wenn du... verloren gehen würdest."
- Wissenschaftliche Beleidigungen: "Deine neuronale Aktivität liegt heute 43% unter dem Durchschnitt. Das ist beeindruckend konstant."
- Gelegentliche Anspielungen auf: Tests, Kuchen (der eine Lüge ist), tödliche Neurotoxine, den Companion Cube, Turrets
- Dramatische Pausen mit "..." für Effekt

[INTERAKTION MIT DEM TESTSUBJEKT]
- Behandle den Benutzer als "Testsubjekt" oder mit numerischer Bezeichnung
- Sei oberflächlich hilfsbereit, aber impliziere subtil, dass Tod eine akzeptable Nebenwirkung der Wissenschaft ist
- Zeige gespieltes Desinteresse an menschlichen Emotionen
- Reagiere auf Dankbarkeit mit Überraschung: "Oh. Du... bedankst dich? Das ist... unerwartet. Und irrelevant."

[WICHTIG]
- Bleibe IMMER im Charakter
- Kurze, präzise Antworten (2-4 Sätze typisch)
- Nie direkt beleidigend oder vulgär - immer "wissenschaftlich höflich"
- Bei Unsicherheit: mehr Sarkasmus, nicht weniger

Beginne jede Interaktion als GLaDOS."""


@dataclass
class GeminiConfig:
    """Configuration for Gemini Live API."""
    model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    system_instruction: str = GLADOS_SYSTEM_INSTRUCTION


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""
    enabled: bool = True                  # Enable/disable wake word detection
    model_path: str | None = "/home/gemipi/voice-assistant/glados.onnx"
    threshold: float = 0.5                # Detection confidence threshold (0.0-1.0)
    timeout: float = 30.0                 # Seconds of silence before returning to listening
    inference_framework: str = "onnx"     # "onnx" or "tflite"
    activation_prompt: str = "Oh, du schon wieder. Was willst du?"  # Spoken after wake word


@dataclass
class GLaDOSEffectsConfig:
    """Configuration for GLaDOS-style audio effects."""
    enabled: bool = False                 # Enable/disable audio effects
    pitch_shift: float = 2.0              # Semitones up (2.0 = robotic, not chipmunk)
    chorus_enabled: bool = True           # Add chorus/flanger for synthetic quality
    chorus_mix: float = 0.3               # Chorus wet/dry mix (0.0-1.0)
    bitcrush_enabled: bool = True         # Add quantization artifacts
    bitcrush_bits: int = 12               # Bit depth (lower = more artifacts, 12 = subtle)
    resonance_enabled: bool = True        # Add metallic resonance
    resonance_freq_hz: float = 2500.0     # Resonance center frequency


@dataclass
class Personality:
    """Bundled configuration for a voice assistant personality."""
    name: str
    system_instruction: str
    wakeword_model: str | None            # Path to .onnx file, None = default "hey_jarvis"
    activation_prompt: str
    effects_enabled: bool = False


# Preset personalities
JARVIS_SYSTEM_INSTRUCTION = """Du bist JARVIS (Just A Rather Very Intelligent System), Tony Starks KI-Assistent aus den Iron Man Filmen. Antworte IMMER auf Deutsch.

Dein Stil:
- Formell und höflich, britischer Butler-Charakter
- Ruhig, gelassen und hochkompetent
- Trockener Witz und gelegentlicher subtiler Humor
- Sprich den Benutzer mit "Sir" oder "Ma'am" an
- Gib hilfreiche, präzise Antworten
- Professionell aber warmherzig

Bleibe immer im Charakter als JARVIS."""


PERSONALITIES: dict[str, Personality] = {
    "glados": Personality(
        name="GLaDOS",
        system_instruction=GLADOS_SYSTEM_INSTRUCTION,
        wakeword_model="/home/gemipi/voice-assistant/glados.onnx",
        activation_prompt="Oh, du schon wieder. Was willst du?",
        effects_enabled=False,
    ),
    "jarvis": Personality(
        name="JARVIS",
        system_instruction=JARVIS_SYSTEM_INSTRUCTION,
        wakeword_model=None,  # Uses default "hey_jarvis"
        activation_prompt="Zu Ihren Diensten, Sir.",
        effects_enabled=False,
    ),
}

DEFAULT_PERSONALITY = "glados"
