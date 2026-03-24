"""Standalone script to generate and cache one TTS audio clip."""

from config_loader import load_config
from tts_generator import generate_single_tts


def main():
    print("=== TTS Generator ===")
    config = load_config()
    config["tts"]["useSavedTts"] = False

    result = generate_single_tts(config)
    if result is None:
        return

    audio_path, tts_data = result
    print(f"\nTTS cached: {audio_path}")
    print(f"Text: {tts_data['text']}")
    print(f"Chunks: {len(tts_data['chunks'])}")


if __name__ == "__main__":
    main()
