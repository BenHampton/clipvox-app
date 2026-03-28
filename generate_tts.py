"""Standalone script to generate and cache TTS audio clips."""

import argparse

from config_loader import load_config
from tts_generator import generate_single_tts, generate_intro_tts


def main():
    parser = argparse.ArgumentParser(description="Generate and cache TTS audio clips.")
    parser.add_argument(
        "--intro",
        action="store_true",
        help="Generate or promote a cached clip as the intro TTS instead of regular phrases.",
    )
    args = parser.parse_args()

    config = load_config()

    if args.intro:
        print("=== TTS Generator (Intro) ===\n")
        generate_intro_tts(config)
        print("\n=== Done ===")
        return

    print("=== TTS Generator ===")

    raw = input("How many clips to generate? (press Enter for 1): ").strip()
    count = int(raw) if raw.isdigit() and int(raw) > 0 else 1

    config["tts"]["useSavedTts"] = False

    generated = 0
    for i in range(count):
        print(f"\n--- Clip {i + 1} of {count} ---")
        result = generate_single_tts(config)
        if result is None:
            print("All phrases are cached — stopping early.")
            break
        audio_path, tts_data = result
        print(f"TTS cached: {audio_path}")
        print(f"Text: {tts_data['text']}")
        print(f"Chunks: {len(tts_data['chunks'])}")
        generated += 1

    print(f"\n=== Done: {generated} clip(s) generated ===")


if __name__ == "__main__":
    main()
