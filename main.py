"""Full pipeline: background clip + TTS + compose final video."""

import argparse
from pathlib import Path

from config_loader import load_config
from clip_generator import generate_clip
from tts_generator import generate_tts, generate_intro_tts
from video_composer import compose_video
from youtube_uploader import YouTubeUploader


def _get_result_videos(results_dir):
    return sorted(results_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)


def _run_pipeline(config):
    print("--- Step 1: Background Clip ---")
    clip_path, clip_from_cache, _ = generate_clip(config)

    print("\n--- Step 2: Text-to-Speech ---")
    intro_status = generate_intro_tts(config)
    tts_clips, video_duration, tts_api_count = generate_tts(config)

    print("\n--- Step 3: Composing Video ---")
    output_path, bg_audio_from_cache = compose_video(config, clip_path, tts_clips, video_duration)

    ba_config = config.get("backgroundAudio", {})
    include_audio = ba_config.get("includeAudio", False)

    if include_audio:
        audio_source = ba_config.get("audioPath", "")
        audio_cache_label = "cached trim" if bg_audio_from_cache else "new trim"
        audio_line = f"{audio_source}  ({audio_cache_label})"
    else:
        audio_line = "disabled"

    if intro_status == "unchanged":
        intro_label = "cached  (phrase unchanged)"
    elif intro_status == "cached":
        intro_label = "promoted from cache  (no API call)"
    else:
        intro_label = "generated via ElevenLabs API"

    tts_cache_label = "all cached" if tts_api_count == 0 else f"{tts_api_count} ElevenLabs API call(s)"

    print("\n--- Summary ---")
    print(f"  • Background clip:  {clip_path}  ({'cached' if clip_from_cache else 'newly extracted'})")
    print(f"  • Intro TTS:        {intro_label}")
    print(f"  • TTS clips:        {len(tts_clips)} clip(s)  |  {video_duration:.2f}s  |  {tts_cache_label}")
    print(f"  • Background audio: {audio_line}")
    print(f"  • Output:           {output_path}")

    return output_path


def _run_upload(config, videos):
    uploader = YouTubeUploader(config)
    print(f"\n--- Uploading {len(videos)} video(s) to YouTube ---")
    for video in videos:
        url = uploader.upload(video)
        print(f"YouTube Short: {url}")


def main():
    parser = argparse.ArgumentParser(description="ClipVox video pipeline")
    parser.add_argument("--upload", action="store_true",
                        help="Skip generation and upload existing videos from results/")
    args = parser.parse_args()

    print("=== ClipVox Generator ===\n")

    config = load_config()
    yt_config = config.get("youtube", {})
    should_upload = yt_config.get("shouldUpload", True)
    upload_only = args.upload
    upload_count = yt_config.get("uploadCount", 1)

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    results_forced_generation = False

    if upload_only:
        videos = _get_result_videos(results_dir)

        if not videos:
            print("WARNING: results/ is empty. Generating a new video to upload...\n")
            results_forced_generation = True
            output_path = _run_pipeline(config)
            videos = [Path(output_path)]
        else:
            videos = videos[:upload_count]
    else:
        output_path = _run_pipeline(config)
        videos = [Path(output_path)]

    if upload_only or should_upload:
        _run_upload(config, videos)
    else:
        print("\nUpload skipped (youtube.shouldUpload is false).")

    print("\n=== Complete! ===")

    if results_forced_generation:
        print(
            "\n" + "!" * 60 +
            "\n  NOTICE: results/ was empty — a new video was generated" +
            "\n  and uploaded. results/ is now empty again." +
            "\n" + "!" * 60
        )


if __name__ == "__main__":
    main()
