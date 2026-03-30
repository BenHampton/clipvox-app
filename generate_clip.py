"""Standalone script to generate and cache background video clips."""

from config_loader import load_config
from clip_generator import generate_clip


def main():
    print("=== Background Clip Generator ===")
    config = load_config()
    config["backgroundVideo"]["useExistingClip"] = False

    try:
        count_input = input("How many clips should be created? [1]: ").strip()
        count = int(count_input) if count_input else 1
    except ValueError:
        count = 1

    created = 0
    collisions = 0

    for i in range(count):
        if count > 1:
            print(f"\n--- Generating clip {i + 1} of {count} ---")
        clip_path, _, had_collision = generate_clip(config)
        if clip_path:
            created += 1
        if had_collision:
            collisions += 1
        print(f"\nClip cached: {clip_path}")

    print(f"\n=== Summary ===")
    print(f"Clips requested:        {count}")
    print(f"Clips created:          {created}")
    print(f"Clips with collisions:  {collisions}")


if __name__ == "__main__":
    main()
