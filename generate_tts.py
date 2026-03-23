"""Standalone script to generate and cache TTS audio."""

from config_loader import load_config
from tts_generator import generate_tts


def main():
    print("=== TTS Generator ===")
    config = load_config()
    config["tts"]["useSavedTts"] = False

    audio_path, tts_data = generate_tts(config)
    print(f"\nTTS cached: {audio_path}")
    print(f"Text: {tts_data['text']}")
    print(f"Chunks: {len(tts_data['chunks'])}")


if __name__ == "__main__":
    main()
