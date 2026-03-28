"""Full pipeline: background clip + TTS + compose final video."""

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
    clip_path, _ = generate_clip(config)

    print("\n--- Step 2: Text-to-Speech ---")
    generate_intro_tts(config)
    tts_clips, video_duration = generate_tts(config)

    print("\n--- Step 3: Composing Video ---")
    output_path = compose_video(config, clip_path, tts_clips, video_duration)

    return output_path


def _run_upload(config, videos):
    uploader = YouTubeUploader(config)
    print(f"\n--- Uploading {len(videos)} video(s) to YouTube ---")
    for video in videos:
        url = uploader.upload(video)
        print(f"YouTube Short: {url}")


def main():
    print("=== ClipVox Generator ===\n")

    config = load_config()
    yt_config = config.get("youtube", {})
    should_upload = yt_config.get("upload", True)
    upload_only = yt_config.get("uploadOnly", True)
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

    if should_upload:
        _run_upload(config, videos)
    else:
        print("\nUpload skipped (youtube.upload is false).")

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
