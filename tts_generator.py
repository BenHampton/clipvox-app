import base64
import json
import random
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from elevenlabs.client import ElevenLabs
from moviepy.editor import AudioFileClip

MAX_VIDEO = 60.0
MIN_VIDEO = 45.0


def _get_saved_tts_dir(config):
    phrases_path = Path(config["tts"]["phrasesPath"])
    return phrases_path.parent / "saved_elevenlabs_tts"


def _get_intro_dir(config):
    phrases_path = Path(config["tts"]["phrasesPath"])
    return phrases_path.parent / "intro_tts"


def _get_past_phrases_path(config):
    phrases_path = Path(config["tts"]["phrasesPath"])
    return phrases_path.parent / "past_phrase_used.json"


def _load_excluded_texts(config):
    """Load past_phrase_used.json, prune entries outside the rolling window, return excluded text set."""
    path = _get_past_phrases_path(config)
    exclusion_days = int(config["tts"].get("phraseExclusionDays", 3))
    cutoff = date.today() - timedelta(days=exclusion_days)

    if not path.exists():
        return set()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    used_phrases = data.get("used_phrases", [])
    active = [e for e in used_phrases if date.fromisoformat(e["used_date"]) > cutoff]

    if len(active) < len(used_phrases):
        pruned = len(used_phrases) - len(active)
        data["used_phrases"] = active
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Pruned {pruned} expired phrase(s) from past_phrase_used.json (older than {exclusion_days} days).")

    return {e["text"] for e in active}


def _force_clear_past_phrases(config):
    """Wipe all entries from past_phrase_used.json, preserving the file structure."""
    path = _get_past_phrases_path(config)
    data = {"used_phrases": []}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("past_phrase_used.json has been cleared.")


def record_used_phrases(config, clips):
    """Append used phrases to past_phrase_used.json. Call this after a video is successfully written."""
    if not clips:
        return

    path = _get_past_phrases_path(config)
    today_str = date.today().isoformat()

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"used_phrases": []}

    existing_texts = {e["text"] for e in data["used_phrases"]}
    added = 0
    for clip in clips:
        text = clip["tts_data"].get("text", "")
        if text and text not in existing_texts:
            data["used_phrases"].append({"text": text, "used_date": today_str})
            existing_texts.add(text)
            added += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Recorded {added} used phrase(s) in past_phrase_used.json.")


def _get_audio_duration(audio_path):
    clip = AudioFileClip(str(audio_path))
    duration = clip.duration
    clip.close()
    return duration


def _duration(audio_path, tts_data, json_path=None):
    """Return duration from tts_data cache; fall back to AudioFileClip and backfill the JSON."""
    cached = tts_data.get("duration")
    if cached is not None:
        return cached
    duration = _get_audio_duration(audio_path)
    tts_data["duration"] = duration
    if json_path is not None:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(tts_data, f, indent=2)
        except OSError:
            pass
    return duration


def _get_current_intro_text(intro_dir):
    """Returns the text field from the existing intro tts_elevenlabs_* sidecar, or None."""
    if not intro_dir.exists():
        return None
    tts_subdirs = [d for d in intro_dir.iterdir() if d.is_dir() and d.name.startswith("tts_elevenlabs_")]
    if not tts_subdirs:
        return None
    json_files = list(tts_subdirs[0].glob("*.json"))
    if not json_files:
        return None
    with open(json_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("text")


def _load_intro_clip(config):
    """Load the single intro TTS clip from <phrasesPath parent>/intro_tts/. Exits on failure."""
    intro_dir = _get_intro_dir(config)

    if not intro_dir.exists():
        print(
            f"ERROR: intro_tts directory not found: {intro_dir}\n"
            f"Run 'python generate_tts.py --intro' to set one up."
        )
        sys.exit(1)

    tts_subdirs = [d for d in intro_dir.iterdir() if d.is_dir() and d.name.startswith("tts_elevenlabs_")]

    if not tts_subdirs:
        print(
            f"ERROR: intro_tts directory has no tts_elevenlabs_* clip: {intro_dir}\n"
            f"Run 'python generate_tts.py --intro' to set one up."
        )
        sys.exit(1)

    subdir = tts_subdirs[0]
    mp3_files = list(subdir.glob("*.mp3"))
    json_files = list(subdir.glob("*.json"))

    if not mp3_files or not json_files:
        print(
            f"ERROR: intro_tts clip directory is missing required files: {subdir}\n"
            f"Run 'python generate_tts.py --intro' to set one up."
        )
        sys.exit(1)

    audio_path = mp3_files[0]
    json_path = json_files[0]

    with open(json_path, "r", encoding="utf-8") as f:
        tts_data = json.load(f)

    print(f"Loaded intro clip: {audio_path}")
    return str(audio_path), tts_data, str(json_path)


def _load_saved_clips(saved_dir):
    """Returns list of (audio_path, tts_data, json_path) for all valid saved clips."""
    clips = []
    if not saved_dir.exists():
        return clips
    for subdir in sorted(saved_dir.iterdir()):
        if not subdir.is_dir():
            continue
        mp3_files = list(subdir.glob("*.mp3"))
        if not mp3_files:
            continue
        audio_path = mp3_files[0]
        json_path = audio_path.with_suffix(".json")
        if not json_path.exists():
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
        clips.append((str(audio_path), tts_data, str(json_path)))
    return clips


def _build_text_cache(saved_dir):
    """Returns a dict of {phrase_text: (audio_path, tts_data, json_path)} from saved clips."""
    cache = {}
    for audio_path, tts_data, json_path in _load_saved_clips(saved_dir):
        text = tts_data.get("text", "")
        if text:
            cache[text] = (audio_path, tts_data, json_path)
    return cache


def _fill_clips(available_clips, gap, start_time=0.0, max_video=MAX_VIDEO):
    """
    Picks clips randomly (no repeats) to fill up to max_video seconds.
    Returns (used_clips, tts_end_time) where used_clips is a list of
    {"audio_path", "tts_data", "offset"} dicts.
    """
    shuffled = list(available_clips)
    random.shuffle(shuffled)

    used = []
    current_time = start_time

    for audio_path, tts_data, json_path in shuffled:
        duration = _duration(audio_path, tts_data, json_path)
        extra_gap = gap if used else 0.0
        if current_time + extra_gap + duration > max_video:
            break
        offset = current_time + extra_gap
        current_time = offset + duration
        used.append({"audio_path": audio_path, "tts_data": tts_data, "offset": offset})

    return used, current_time


def _extract_word_timings(text, alignment):
    if hasattr(alignment, "characters"):
        characters = alignment.characters
        char_starts = alignment.character_start_times_seconds
        char_ends = alignment.character_end_times_seconds
    else:
        characters = alignment["characters"]
        char_starts = alignment["character_start_times_seconds"]
        char_ends = alignment["character_end_times_seconds"]

    full_text = "".join(characters)
    word_timings = []
    search_start = 0

    for word in text.split():
        pos = full_text.find(word, search_start)
        if pos == -1:
            continue
        word_timings.append({
            "word": word,
            "start": char_starts[pos],
            "end": char_ends[pos + len(word) - 1]
        })
        search_start = pos + len(word)

    return word_timings


def _chunk_words_dynamic(word_timings, max_chars=22):
    chunks = []
    current_words = []
    current_len = 0

    for wt in word_timings:
        word = wt["word"]
        word_len = len(word)
        space = 1 if current_words else 0

        if current_words and current_len + space + word_len > max_chars:
            chunks.append({
                "text": " ".join(w["word"] for w in current_words),
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"]
            })
            current_words = [wt]
            current_len = word_len
        else:
            current_words.append(wt)
            current_len += space + word_len

    if current_words:
        chunks.append({
            "text": " ".join(w["word"] for w in current_words),
            "start": current_words[0]["start"],
            "end": current_words[-1]["end"]
        })

    return chunks


def _save_tts_clip(audio_bytes, tts_data, saved_dir, prefix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{prefix}tts_elevenlabs_{timestamp}" if prefix else f"tts_elevenlabs_{timestamp}"
    clip_dir = saved_dir / base_name
    clip_dir.mkdir(parents=True, exist_ok=True)

    audio_path = clip_dir / f"{base_name}.mp3"
    json_path = clip_dir / f"{base_name}.json"

    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    tts_data["duration"] = _get_audio_duration(str(audio_path))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tts_data, f, indent=2)

    print(f"Saved TTS: {audio_path}")
    return str(audio_path)


def get_tts_status(config):
    """Prints remaining ElevenLabs monthly characters and the next reset date."""
    api_key = config.get("elevenlabs_api_key", "")
    client = ElevenLabs(api_key=api_key)
    sub = client.user.get().subscription
    used = sub.character_count
    limit = sub.character_limit
    remaining = limit - used
    reset_unix = getattr(sub, "next_character_count_reset_unix", None)
    if reset_unix:
        reset_dt = datetime.fromtimestamp(reset_unix, tz=timezone.utc)
        reset_str = reset_dt.strftime("%Y-%m-%d %H:%M UTC")
        print(f"ElevenLabs credits: {remaining:,} remaining of {limit:,}  |  resets {reset_str}")
    else:
        print(f"ElevenLabs credits: {remaining:,} remaining of {limit:,}")


def _log_elevenlabs_usage(client):
    """Logs remaining ElevenLabs characters and next reset date. Fails silently."""
    try:
        sub = client.user.get().subscription
        used = sub.character_count
        limit = sub.character_limit
        remaining = limit - used
        reset_unix = getattr(sub, "next_character_count_reset_unix", None)
        if reset_unix:
            reset_dt = datetime.fromtimestamp(reset_unix, tz=timezone.utc)
            reset_str = reset_dt.strftime("%Y-%m-%d %H:%M UTC")
            print(f"ElevenLabs credits: {remaining:,} remaining of {limit:,}  |  resets {reset_str}")
        else:
            print(f"ElevenLabs credits: {remaining:,} remaining of {limit:,}")
    except Exception:
        pass


def _strip_pause_markers(text):
    """Remove [pause] markers from text, collapsing any extra whitespace."""
    return re.sub(r'\s*\[pause\]\s*', ' ', text).strip()


def _call_elevenlabs(client, text, voice, model, pause_duration=0.5):
    """Calls ElevenLabs TTS API with logging.

    If the text contains [pause] markers they are converted to SSML <break> tags
    and SSML parsing is enabled for that request only.
    """
    if "[pause]" in text:
        escaped = text.replace("[pause]", f'<break time="{pause_duration}s"/>')
        api_text = f"<speak>{escaped}</speak>"
    else:
        api_text = text

    print(f"Calling ElevenLabs API for: \"{text}\"")
    response = client.text_to_speech.convert_with_timestamps(
        voice_id=voice,
        text=api_text,
        model_id=model,
    )
    print(f"ElevenLabs API response received for: \"{text}\"")
    return response


def _generate_new_clips(config, saved_dir, gap, start_time=0.0, max_video=MAX_VIDEO, excluded_texts=None):
    """Generate TTS clips from phrases until max_video is filled, using cache where available."""
    tts_config = config["tts"]
    phrases_path = tts_config.get("phrasesPath", "")

    with open(phrases_path, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    if not phrases:
        raise ValueError(f"Phrases file is empty: {phrases_path}")

    api_key = config.get("elevenlabs_api_key", "")
    model = tts_config.get("model", "eleven_multilingual_v2")
    voice = tts_config.get("voiceId", "JBFqnCBsd6RMkjVDRZzb")
    prefix = tts_config.get("savedTtsPrefix", "")
    pause_duration = float(tts_config.get("pauseDuration", 0.5))

    client = ElevenLabs(api_key=api_key)
    saved_dir.mkdir(parents=True, exist_ok=True)

    cache = _build_text_cache(saved_dir)
    excluded = excluded_texts or set()
    shuffled_phrases = [p for p in phrases if p not in excluded]
    if len(shuffled_phrases) < len(phrases):
        skipped = len(phrases) - len(shuffled_phrases)
        print(f"Skipping {skipped} recently used phrase(s) (phraseExclusionDays window).")
    random.shuffle(shuffled_phrases)

    generated = []
    api_count = 0
    current_time = start_time

    for text in shuffled_phrases:
        extra_gap = gap if generated else 0.0
        if current_time + extra_gap >= max_video:
            break

        if text in cache:
            print(f"Using cached TTS for: \"{text}\"")
            audio_path, tts_data, json_path = cache[text]
            api_calls_made = False
        else:
            response = _call_elevenlabs(client, text, voice, model, pause_duration)
            audio_bytes = base64.b64decode(response.audio_base_64)
            clean_text = _strip_pause_markers(text)
            word_timings = _extract_word_timings(clean_text, response.alignment)
            chunks = _chunk_words_dynamic(word_timings)
            tts_data = {"text": text, "word_timings": word_timings, "chunks": chunks}
            audio_path = _save_tts_clip(audio_bytes, tts_data, saved_dir, prefix)
            json_path = str(Path(audio_path).with_suffix(".json"))
            cache[text] = (audio_path, tts_data, json_path)
            api_calls_made = True
            _log_elevenlabs_usage(client)

        duration = _duration(audio_path, tts_data, json_path)

        if current_time + extra_gap + duration > max_video:
            print(f"Clip would exceed {max_video:.0f}s limit, stopping.")
            break

        offset = current_time + extra_gap
        current_time = offset + duration
        generated.append({"audio_path": audio_path, "tts_data": tts_data, "offset": offset})
        if api_calls_made:
            api_count += 1

    return generated, current_time, api_count


def generate_single_tts(config):
    """
    Generates one TTS clip for an uncached phrase. Intended for standalone use.
    Returns (audio_path, tts_data) or None if all phrases are already cached.
    After generating, moves the phrase from phrases.json to converted_phrases.json.
    """
    tts_config = config["tts"]
    phrases_path = Path(tts_config.get("phrasesPath", ""))

    with open(phrases_path, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    if not phrases:
        raise ValueError(f"Phrases file is empty: {phrases_path}")

    saved_dir = _get_saved_tts_dir(config)
    saved_dir.mkdir(parents=True, exist_ok=True)
    cache = _build_text_cache(saved_dir)

    converted_path = phrases_path.parent / "converted_phrases.json"
    converted = json.loads(converted_path.read_text(encoding="utf-8")) if converted_path.exists() else []
    converted_set = set(converted)

    shuffled = list(phrases)
    random.shuffle(shuffled)

    uncached = [p for p in shuffled if p not in cache and p not in converted_set]

    if not uncached:
        print("WARNING: All phrases are already cached. No new TTS generated.")
        return None

    text = uncached[0]
    api_key = config.get("elevenlabs_api_key", "")
    model = tts_config.get("model", "eleven_multilingual_v2")
    voice = tts_config.get("voiceId", "JBFqnCBsd6RMkjVDRZzb")
    prefix = tts_config.get("savedTtsPrefix", "")
    pause_duration = float(tts_config.get("pauseDuration", 0.5))

    client = ElevenLabs(api_key=api_key)
    response = _call_elevenlabs(client, text, voice, model, pause_duration)

    audio_bytes = base64.b64decode(response.audio_base_64)
    clean_text = _strip_pause_markers(text)
    word_timings = _extract_word_timings(clean_text, response.alignment)
    chunks = _chunk_words_dynamic(word_timings)
    tts_data = {"text": text, "word_timings": word_timings, "chunks": chunks}

    audio_path = _save_tts_clip(audio_bytes, tts_data, saved_dir, prefix)

    remaining = [p for p in phrases if p != text]
    phrases_path.write_text(json.dumps(remaining, indent=2, ensure_ascii=False), encoding="utf-8")

    if text not in converted_set:
        converted.append(text)
        converted_path.write_text(json.dumps(converted, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Moved phrase to converted_phrases.json: \"{text}\"")
    _log_elevenlabs_usage(client)

    return audio_path, tts_data


def generate_tts(config):
    tts_config = config["tts"]

    max_video = float(config.get("backgroundVideo", {}).get("backgroundVideoLength", MAX_VIDEO))
    min_video = max_video * 0.75

    phrase_gap = float(tts_config.get("phraseGap", 0.5))
    intro_phrase_gap_val = tts_config.get("introPhraseGap")
    if intro_phrase_gap_val is None or intro_phrase_gap_val == "":
        intro_phrase_gap = phrase_gap
    else:
        intro_phrase_gap = float(intro_phrase_gap_val)

    # Intro clip always plays first at offset 0
    intro_audio_path, intro_tts_data, intro_json_path = _load_intro_clip(config)
    intro_duration = _duration(intro_audio_path, intro_tts_data, intro_json_path)
    intro_clip = {"audio_path": intro_audio_path, "tts_data": intro_tts_data, "offset": 0.0}

    # Regular clips start after intro + introPhraseGap
    regular_start = intro_duration + intro_phrase_gap

    saved_dir = _get_saved_tts_dir(config)
    excluded_texts = _load_excluded_texts(config)

    if tts_config.get("useSavedTts", False):
        all_saved = _load_saved_clips(saved_dir)
        available = [(a, t, j) for a, t, j in all_saved if t.get("text", "") not in excluded_texts]

        if all_saved and not available:
            exclusion_days = int(tts_config.get("phraseExclusionDays", 3))
            print(
                f"\nWARNING: All {len(all_saved)} saved TTS phrase(s) are in past_phrase_used.json "
                f"and the {exclusion_days}-day exclusion window has not passed for all entries. "
                "Force-clearing past_phrase_used.json and restarting TTS selection.\n"
            )
            _force_clear_past_phrases(config)
            excluded_texts = set()
            available = all_saved

        if not available:
            print(f"WARNING: useSavedTts is true but no saved clips found in: {saved_dir}")
            used_clips, tts_end, api_count = [], regular_start, 0
        else:
            print(f"Found {len(available)} saved TTS clip(s) (after exclusion filter).")
            used_clips, tts_end = _fill_clips(available, phrase_gap, regular_start, max_video)
            api_count = 0
    else:
        used_clips, tts_end, api_count = _generate_new_clips(
            config, saved_dir, phrase_gap, regular_start, max_video, excluded_texts
        )

    all_clips = [intro_clip] + used_clips
    video_duration = max(min_video, tts_end)
    unfilled = video_duration - tts_end

    if unfilled > 15:
        print(
            f"\nWARNING: {unfilled:.1f}s of the {video_duration:.1f}s video will be silent "
            f"(TTS only fills {tts_end:.1f}s). Add more saved TTS clips to fill the video.\n"
        )

    print(f"Using {len(all_clips)} TTS clip(s) (1 intro + {len(used_clips)} regular), video duration: {video_duration:.1f}s")
    return all_clips, used_clips, video_duration, api_count


def generate_intro_tts(config):
    """
    Generate or promote a cached clip as the intro TTS.
    Called from generate_tts.py --intro and automatically from the main pipeline.

    Reads intro_phrase.json from intro_tts/, compares the phrase to the existing
    clip (if any), and skips if unchanged. Otherwise checks saved_elevenlabs_tts/
    for a cached match, then either promotes it or calls ElevenLabs for a new one.
    Any existing tts_elevenlabs_* in intro_tts/ is moved back to saved_elevenlabs_tts/ first.
    """
    tts_config = config["tts"]
    intro_dir = _get_intro_dir(config)
    saved_dir = _get_saved_tts_dir(config)

    intro_dir.mkdir(parents=True, exist_ok=True)

    # Read and validate intro_phrase.json
    intro_phrase_json = intro_dir / "intro_phrase.json"
    if not intro_phrase_json.exists():
        print(
            f"ERROR: intro_phrase.json not found: {intro_phrase_json}\n"
            f"Create the file with the content: {{\"phrase\": \"your intro text here\"}}"
        )
        sys.exit(1)

    with open(intro_phrase_json, "r", encoding="utf-8") as f:
        intro_phrase_data = json.load(f)

    phrase = intro_phrase_data.get("phrase")
    if not phrase:
        print(
            f"ERROR: intro_phrase.json is missing the 'phrase' key or its value is empty: {intro_phrase_json}\n"
            f"Expected format: {{\"phrase\": \"your intro text here\"}}"
        )
        sys.exit(1)

    # Skip if existing intro clip already matches the phrase
    current_text = _get_current_intro_text(intro_dir)
    if current_text == phrase:
        print(f"Intro TTS is up to date — phrase unchanged.")
        return "unchanged"

    if current_text is not None:
        print(f"Intro phrase has changed — updating intro TTS.")

    # Check for existing tts_elevenlabs_* dirs in intro_tts/
    existing_intro_clips = [
        d for d in intro_dir.iterdir()
        if d.is_dir() and d.name.startswith("tts_elevenlabs_")
    ]

    if len(existing_intro_clips) > 1:
        print(
            f"ERROR: Multiple tts_elevenlabs_* directories found in intro_tts/: {intro_dir}\n"
            f"Expected at most one. Remove the extras manually before running --intro."
        )
        sys.exit(1)

    existing_intro_clip = existing_intro_clips[0] if existing_intro_clips else None

    # Check if phrase is already cached in saved_elevenlabs_tts/
    cache = _build_text_cache(saved_dir)

    if phrase in cache:
        cached_audio_path, _, _jp = cache[phrase]
        cached_clip_dir = Path(cached_audio_path).parent

        # Move existing intro clip back to saved_elevenlabs_tts/ before promoting
        if existing_intro_clip:
            saved_dir.mkdir(parents=True, exist_ok=True)
            dest = saved_dir / existing_intro_clip.name
            shutil.move(str(existing_intro_clip), str(dest))
            print(f"Moved existing intro clip to saved_elevenlabs_tts/: {dest.name}")

        # Promote cached clip into intro_tts/
        dest = intro_dir / cached_clip_dir.name
        shutil.move(str(cached_clip_dir), str(dest))
        print(f"Promoted cached clip to intro_tts/: {dest.name}")

        print(f"\nIntro phrase: \"{phrase}\"")
        print("Intro TTS is set up and ready — videos will now start with this clip.")
        return "cached"
    else:
        # Move existing intro clip back to saved_elevenlabs_tts/ before generating
        if existing_intro_clip:
            saved_dir.mkdir(parents=True, exist_ok=True)
            dest = saved_dir / existing_intro_clip.name
            shutil.move(str(existing_intro_clip), str(dest))
            print(f"Moved existing intro clip to saved_elevenlabs_tts/: {dest.name}")

        # Generate new TTS from ElevenLabs
        api_key = config.get("elevenlabs_api_key", "")
        model = tts_config.get("model", "eleven_multilingual_v2")
        voice = tts_config.get("introVoiceId") or tts_config.get("voiceId", "JBFqnCBsd6RMkjVDRZzb")
        prefix = tts_config.get("savedTtsPrefix", "")
        pause_duration = float(tts_config.get("pauseDuration", 0.5))

        client = ElevenLabs(api_key=api_key)
        response = _call_elevenlabs(client, phrase, voice, model, pause_duration)

        audio_bytes = base64.b64decode(response.audio_base_64)
        clean_phrase = _strip_pause_markers(phrase)
        word_timings = _extract_word_timings(clean_phrase, response.alignment)
        chunks = _chunk_words_dynamic(word_timings)
        tts_data = {"text": phrase, "word_timings": word_timings, "chunks": chunks}

        audio_path = _save_tts_clip(audio_bytes, tts_data, intro_dir, prefix)
        print(f"New intro TTS saved: {audio_path}")
        _log_elevenlabs_usage(client)

        print(f"\nIntro phrase: \"{phrase}\"")
        print("Intro TTS is set up and ready — videos will now start with this clip.")
        return "api"
