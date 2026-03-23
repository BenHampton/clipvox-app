import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "backgroundVideo": {
        "videoName": "",
        "clipName": "saved_clip_",
        "useExistingClip": True,
        "existingClipName": ""
    },
    "tts": {
        "apiKey": "API_KEY",
        "model": "eleven_multilingual_v2",
        "voice": "JBFqnCBsd6RMkjVDRZzb",
        "phrasesPath": "talk_to_speak/hannibal_lecter/phrases.json",
        "useSavedTts": False,
        "savedTtsDir": "talk_to_speak/saved_elevenlabs_tts",
        "savedTtsPrefix": "",
        "font": "Arial",
        "fontColor": "white",
        "fontSize": 70
    },
    "output": {
        "name": "result_"
    }
}


def _find_default_video():
    bg_dir = Path("background_videos")
    mp4_files = list(bg_dir.glob("*.mp4"))
    if mp4_files:
        return mp4_files[0].name
    return ""


def _deep_merge(base, override):
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = json.load(f)

    config = _deep_merge(DEFAULT_CONFIG, user_config)

    if not config["backgroundVideo"]["videoName"]:
        config["backgroundVideo"]["videoName"] = _find_default_video()

    phrases_path = config["tts"]["phrasesPath"]
    if not phrases_path:
        raise ValueError("tts.phrasesPath must be set in config.json")
    if not os.path.exists(phrases_path):
        raise FileNotFoundError(f"Phrases file not found: {phrases_path}")

    return config
