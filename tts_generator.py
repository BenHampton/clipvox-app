import base64
import json
import random
from datetime import datetime
from pathlib import Path

from elevenlabs.client import ElevenLabs


def _get_random_phrase(phrases_path):
    with open(phrases_path, "r", encoding="utf-8") as f:
        phrases = json.load(f)
    if not phrases:
        raise ValueError(f"Phrases file is empty: {phrases_path}")
    return random.choice(phrases)


def _get_existing_tts(config):
    saved_dir = Path(config["tts"].get("savedTtsDir", "talk_to_speak/saved_elevenlabs_tts"))
    if not saved_dir.exists():
        return None, None

    mp3_files = sorted(saved_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp3_files:
        return None, None

    audio_path = mp3_files[0]
    json_path = audio_path.with_suffix(".json")

    if not json_path.exists():
        return None, None

    return str(audio_path), str(json_path)


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


def generate_tts(config):
    tts_config = config["tts"]

    if tts_config.get("useSavedTts", True):
        audio_path, json_path = _get_existing_tts(config)
        if audio_path and json_path:
            print(f"Using existing TTS: {audio_path}")
            with open(json_path, "r", encoding="utf-8") as f:
                tts_data = json.load(f)
            return audio_path, tts_data
        print("No saved TTS found, generating new TTS...")

    phrases_path = tts_config.get("phrasesPath", "")
    if not phrases_path:
        raise ValueError("tts.phrasesPath must be set in config.json")

    text = _get_random_phrase(phrases_path)
    print(f"Selected phrase: {text}")

    api_key = tts_config.get("apiKey", "API_KEY")
    model = tts_config.get("model", "eleven_multilingual_v2")
    voice = tts_config.get("voice", "JBFqnCBsd6RMkjVDRZzb")

    print("Calling ElevenLabs API...")
    client = ElevenLabs(api_key=api_key)
    response = client.text_to_speech.convert_with_timestamps(
        voice_id=voice,
        text=text,
        model_id=model,
    )

    audio_bytes = base64.b64decode(response.audio_base_64)
    word_timings = _extract_word_timings(text, response.alignment)
    chunks = _chunk_words_dynamic(word_timings)

    tts_data = {
        "text": text,
        "word_timings": word_timings,
        "chunks": chunks
    }

    saved_dir = Path(tts_config.get("savedTtsDir", "talk_to_speak/saved_elevenlabs_tts"))
    saved_dir.mkdir(parents=True, exist_ok=True)

    prefix = tts_config.get("savedTtsPrefix", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{prefix}tts_elevenlabs_{timestamp}"

    audio_path = saved_dir / f"{base_name}.mp3"
    json_path = saved_dir / f"{base_name}.json"

    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tts_data, f, indent=2)

    print(f"Saved TTS audio: {audio_path}")
    print(f"Saved TTS data: {json_path}")

    return str(audio_path), tts_data
