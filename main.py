"""Full pipeline: background clip + TTS + compose final video."""

from config_loader import load_config
from clip_generator import generate_clip
from tts_generator import generate_tts
from video_composer import compose_video


def main():
    print("=== ClipVox Generator ===\n")

    config = load_config()

    print("--- Step 1: Background Clip ---")
    clip_path = generate_clip(config)

    print("\n--- Step 2: Text-to-Speech ---")
    tts_audio_path, tts_data = generate_tts(config)

    print("\n--- Step 3: Composing Video ---")
    output_path = compose_video(config, clip_path, tts_audio_path, tts_data)

    print(f"\n=== Complete! ===")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
