"""Standalone script to generate and cache a background video clip."""

from config_loader import load_config
from clip_generator import generate_clip


def main():
    print("=== Background Clip Generator ===")
    config = load_config()
    config["backgroundVideo"]["useExistingClip"] = False

    clip_path = generate_clip(config)
    print(f"\nClip cached: {clip_path}")


if __name__ == "__main__":
    main()
