"""Full pipeline: background clip + TTS + compose final video."""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clip_registry import clean_registry
from config_loader import load_config
from clip_generator import generate_clip
from tts_generator import generate_tts, generate_intro_tts, generate_single_tts
from video_composer import compose_video
from youtube_uploader import YouTubeUploader

TASK_NAME = "ClipVox"


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

    if not clip_from_cache and not config["backgroundVideo"].get("cacheClip", False):
        Path(clip_path).unlink(missing_ok=True)

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
    save_result = config.get("output", {}).get("saveResultOnUpload", False)
    print(f"\n--- Uploading {len(videos)} video(s) to YouTube ---")
    for video in videos:
        url = uploader.upload(video, save_result=save_result)
        print(f"YouTube Short: {url}")


def _run_clean_up_tts(config):
    phrases_path = Path(config["tts"].get("phrasesPath", ""))
    if not phrases_path.exists():
        print(f"Phrases file not found: {phrases_path}")
        return

    phrases = json.loads(phrases_path.read_text(encoding="utf-8"))

    # Build set of cached phrase texts from saved_elevenlabs_tts/
    saved_dir = phrases_path.parent / "saved_elevenlabs_tts"
    cached_texts = set()
    if saved_dir.exists():
        for subdir in saved_dir.iterdir():
            if not subdir.is_dir():
                continue
            for json_file in subdir.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    text = data.get("text", "")
                    if text:
                        cached_texts.add(text)
                except Exception:
                    continue

    converted_path = phrases_path.parent / "converted_phrases.json"
    converted = json.loads(converted_path.read_text(encoding="utf-8")) if converted_path.exists() else []
    converted_set = set(converted)

    remaining = []
    moved_count = 0
    for phrase in phrases:
        if phrase in cached_texts:
            if phrase not in converted_set:
                converted.append(phrase)
                converted_set.add(phrase)
                moved_count += 1
        else:
            remaining.append(phrase)

    phrases_path.write_text(json.dumps(remaining, indent=2, ensure_ascii=False), encoding="utf-8")
    converted_path.write_text(json.dumps(converted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Moved {moved_count} phrase(s) to {converted_path.name}.")
    print(f"Remaining in {phrases_path.name}: {len(remaining)}")


def _run_tts_mode(config, count):
    print("=== TTS Generator ===\n")
    for i in range(count):
        if count > 1:
            print(f"\n--- Generating TTS clip {i + 1} of {count} ---")
        result = generate_single_tts(config)
        if result is None:
            print("All phrases are already cached — stopping early.")
            break
    print("\n=== Done ===")


def _run_clip_mode(config, count):
    print("=== Background Clip Generator ===")
    config["backgroundVideo"]["useExistingClip"] = False
    config["backgroundVideo"]["cacheClip"] = True
    created = 0
    collisions = 0
    for i in range(count):
        if count > 1:
            print(f"\n--- Generating clip {i + 1} of {count} ---")
        clip_path, _, had_collision = generate_clip(config)
        if clip_path:
            created += 1
            print(f"\nClip saved: {clip_path}")
        if had_collision:
            collisions += 1
    print(f"\n=== Summary ===")
    print(f"Clips requested:        {count}")
    print(f"Clips created:          {created}")
    print(f"Clips with collisions:  {collisions}")


def _run_loop_mode(config, count):
    yt_config = config.get("youtube", {})
    should_upload = yt_config.get("shouldUpload", True)

    for i in range(count):
        print(f"\n{'=' * 50}")
        print(f"=== Run {i + 1} of {count} ===")
        print(f"{'=' * 50}\n")
        output_path = _run_pipeline(config)

        if should_upload:
            _run_upload(config, [Path(output_path)])
        else:
            print("\nUpload skipped (youtube.shouldUpload is false).")

    print(f"\n=== All {count} run(s) complete ===")


def _task_exists():
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True, text=True
    )
    return result.returncode == 0


def _unregister_schedule(log_result=True):
    if not _task_exists():
        if log_result:
            print(f"No scheduled task '{TASK_NAME}' found — nothing to remove.")
        return False
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to remove scheduled task '{TASK_NAME}':\n{result.stderr.strip()}")
        return False
    if log_result:
        print(f"Scheduled task '{TASK_NAME}' removed successfully.")
    return True


def _register_schedule(config):
    schedule_config = config.get("schedule", {})
    time_str = schedule_config.get("scheduleTime", "")
    if not time_str:
        print("ERROR: schedule.scheduleTime not set in config.json (e.g. \"14:30\")")
        sys.exit(1)

    if _task_exists():
        print(f"NOTE: An existing scheduled task '{TASK_NAME}' was found — it will be overwritten.")

    try:
        central = ZoneInfo("America/Chicago")
        local_tz = datetime.now().astimezone().tzinfo
        now_ct = datetime.now(central)
        h, m = map(int, time_str.split(":"))
        scheduled_ct = now_ct.replace(hour=h, minute=m, second=0, microsecond=0)
        scheduled_local = scheduled_ct.astimezone(local_tz)
        local_time_str = scheduled_local.strftime("%H:%M")
    except Exception as e:
        print(f"ERROR: Could not parse scheduleTime '{time_str}': {e}")
        sys.exit(1)

    python_exe = sys.executable
    script_path = Path(__file__).resolve()
    task_cmd = f'"{python_exe}" "{script_path}"'

    result = subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/tr", task_cmd,
         "/sc", "daily", "/st", local_time_str, "/f"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to register scheduled task:\n{result.stderr.strip()}")
        print("Attempting to unschedule any partial registration...")
        removed = _unregister_schedule(log_result=False)
        if removed:
            print(f"Unscheduled '{TASK_NAME}' after registration failure.")
        else:
            print(f"No partial task found for '{TASK_NAME}' — nothing to clean up.")
        sys.exit(1)

    print(f"Scheduled '{TASK_NAME}' to run daily at {time_str} CT ({local_time_str} local time).")
    print(f"Command: {task_cmd}")
    print(f"To remove: python main.py --unschedule")


def main():
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description=(
            "ClipVox — automated short-form vertical video pipeline.\n"
            "Combines a background clip, ElevenLabs TTS audio, and synced captions "
            "into a YouTube Shorts-ready video."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--tts", nargs="?", const=1, type=int, metavar="N",
        help=(
            "Generate and cache N TTS phrase clips via ElevenLabs (default: 1). "
            "Skips video composition and upload."
        )
    )
    mode.add_argument(
        "--clip", nargs="?", const=1, type=int, metavar="N",
        help=(
            "Extract and cache N background video clips (default: 1). "
            "Skips TTS generation and video composition."
        )
    )
    mode.add_argument(
        "--loop", nargs="?", const=1, type=int, metavar="N",
        help=(
            "Run the full pipeline N times end-to-end (default: 1). "
            "Each iteration generates a video and uploads if youtube.shouldUpload is true."
        )
    )
    mode.add_argument(
        "--upload", nargs="?", const=1, type=int, metavar="N",
        help=(
            "Skip generation and upload N existing video(s) from results/ to YouTube (default: 1). "
            "Overrides youtube.shouldUpload regardless of its value."
        )
    )
    mode.add_argument(
        "--schedule", action="store_true",
        help=(
            "Register a daily Windows Task Scheduler entry that runs main.py at the time "
            "set in config schedule.scheduleTime (stored in Central Time)."
        )
    )
    mode.add_argument(
        "--unschedule", action="store_true",
        help=f"Remove the '{TASK_NAME}' Windows Task Scheduler entry created by --schedule."
    )
    mode.add_argument(
        "--clean-up", action="store_true",
        help=(
            "Delete clip files and result videos referenced in results/used_clips.json. "
            "Registry entries are kept intact."
        )
    )
    mode.add_argument(
        "--clean-up-tts", action="store_true",
        help=(
            "Move phrases from phrasesPath that already have a cached TTS clip into "
            "converted_phrases.json, removing them from the active phrase pool."
        )
    )

    args = parser.parse_args()

    if args.tts is not None:
        config = load_config()
        _run_tts_mode(config, args.tts)
        return

    if args.clip is not None:
        config = load_config()
        _run_clip_mode(config, args.clip)
        return

    if args.schedule:
        config = load_config()
        _register_schedule(config)
        return

    if args.unschedule:
        _unregister_schedule()
        return

    if args.clean_up:
        try:
            deleted_clips, deleted_results = clean_registry()
        except FileNotFoundError:
            print("No registry found — nothing to clean up.")
            return
        print(f"Clips deleted ({len(deleted_clips)}):")
        if deleted_clips:
            for p in deleted_clips:
                print(f"  • {p}")
        else:
            print("  (none)")
        print(f"Result videos deleted ({len(deleted_results)}):")
        if deleted_results:
            for p in deleted_results:
                print(f"  • {p}")
        else:
            print("  (none)")
        return

    if args.clean_up_tts:
        config = load_config()
        _run_clean_up_tts(config)
        return

    config = load_config()
    yt_config = config.get("youtube", {})
    should_upload = yt_config.get("shouldUpload", True)

    if args.loop is not None:
        print("=== ClipVox Generator ===\n")
        _run_loop_mode(config, args.loop)
        return

    print("=== ClipVox Generator ===\n")

    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    upload_only = args.upload is not None
    upload_count = args.upload if upload_only else yt_config.get("uploadCount", 1)

    if upload_only:
        videos = _get_result_videos(results_dir)
        if not videos:
            print("No videos found in results/ — nothing to upload.")
            return
        videos = videos[:upload_count]
    else:
        output_path = _run_pipeline(config)
        videos = [Path(output_path)]

    if upload_only or should_upload:
        _run_upload(config, videos)
    else:
        print("\nUpload skipped (youtube.shouldUpload is false).")

    print("\n=== Complete! ===")


if __name__ == "__main__":
    main()
