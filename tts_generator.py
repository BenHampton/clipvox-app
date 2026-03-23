import base64
import json
import random
from datetime import datetime
from pathlib import Path

from elevenlabs.client import ElevenLabs
from moviepy.editor import AudioFileClip

GAP = 0.5
MAX_VIDEO = 60.0
MIN_VIDEO = 45.0


def _get_saved_tts_dir(config):
    phrases_path = Path(config["tts"]["phrasesPath"])
    return phrases_path.parent / "saved_elevenlabs_tts"


def _get_audio_duration(audio_path):
    clip = AudioFileClip(str(audio_path))
    duration = clip.duration
    clip.close()
    return duration


def _load_saved_clips(saved_dir):
    """Returns list of (audio_path, tts_data) for all valid saved clips."""
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
        clips.append((str(audio_path), tts_data))
    return clips


def _fill_clips(available_clips):
    """
    Picks clips randomly (no repeats) to fill up to MAX_VIDEO seconds.
    Returns (used_clips, tts_end_time) where used_clips is a list of
    {"audio_path", "tts_data", "offset"} dicts.
    """
    shuffled = list(available_clips)
    random.shuffle(shuffled)

    used = []
    current_time = 0.0

    for audio_path, tts_data in shuffled:
        duration = _get_audio_duration(audio_path)
        gap = GAP if used else 0.0
        if current_time + gap + duration > MAX_VIDEO:
            break
        offset = current_time + gap
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
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tts_data, f, indent=2)

    print(f"Saved TTS: {audio_path}")
    return str(audio_path)


def _generate_new_clips(config, saved_dir):
    """Generate TTS clips from phrases until MAX_VIDEO is filled."""
    tts_config = config["tts"]
    phrases_path = tts_config.get("phrasesPath", "")

    with open(phrases_path, "r", encoding="utf-8") as f:
        phrases = json.load(f)

    if not phrases:
        raise ValueError(f"Phrases file is empty: {phrases_path}")

    api_key = config.get("elevenlabs_api_key", "")
    model = tts_config.get("model", "eleven_multilingual_v2")
    voice = tts_config.get("voice", "JBFqnCBsd6RMkjVDRZzb")
    prefix = tts_config.get("savedTtsPrefix", "")

    client = ElevenLabs(api_key=api_key)
    saved_dir.mkdir(parents=True, exist_ok=True)

    shuffled_phrases = list(phrases)
    random.shuffle(shuffled_phrases)

    generated = []
    current_time = 0.0

    for text in shuffled_phrases:
        gap = GAP if generated else 0.0
        if current_time + gap >= MAX_VIDEO:
            break

        print(f"Generating TTS for: {text}")
        response = client.text_to_speech.convert_with_timestamps(
            voice_id=voice,
            text=text,
            model_id=model,
        )

        audio_bytes = base64.b64decode(response.audio_base_64)
        word_timings = _extract_word_timings(text, response.alignment)
        chunks = _chunk_words_dynamic(word_timings)
        tts_data = {"text": text, "word_timings": word_timings, "chunks": chunks}

        audio_path = _save_tts_clip(audio_bytes, tts_data, saved_dir, prefix)
        duration = _get_audio_duration(audio_path)

        if current_time + gap + duration > MAX_VIDEO:
            print(f"Clip would exceed {MAX_VIDEO}s limit, stopping.")
            break

        offset = current_time + gap
        current_time = offset + duration
        generated.append({"audio_path": audio_path, "tts_data": tts_data, "offset": offset})

    return generated, current_time


def generate_tts(config):
    tts_config = config["tts"]
    saved_dir = _get_saved_tts_dir(config)

    if tts_config.get("useSavedTts", False):
        available = _load_saved_clips(saved_dir)
        if not available:
            print("WARNING: useSavedTts is true but no saved clips found in: {saved_dir}")
            used_clips, tts_end = [], 0.0
        else:
            print(f"Found {len(available)} saved TTS clip(s).")
            used_clips, tts_end = _fill_clips(available)
    else:
        used_clips, tts_end = _generate_new_clips(config, saved_dir)

    video_duration = max(MIN_VIDEO, tts_end)
    unfilled = video_duration - tts_end

    if unfilled > 15:
        print(
            f"\nWARNING: {unfilled:.1f}s of the {video_duration:.1f}s video will be silent "
            f"(TTS only fills {tts_end:.1f}s). Add more saved TTS clips to fill the video.\n"
        )

    print(f"Using {len(used_clips)} TTS clip(s), video duration: {video_duration:.1f}s")
    return used_clips, video_duration
