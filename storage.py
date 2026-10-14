"""Pontuações e preferências locais, separadas da pasta de instalação."""
from datetime import datetime
import json
import os
from pathlib import Path

MODES = ("easy", "normal", "hard")


def data_file():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "AdrianoGames" / "SnakeGame" / "profile.json"


def empty_profile():
    return {"version": 1, "settings": {"difficulty": "normal", "fullscreen": False},
            "scores": {mode: {"record": 0, "best": [], "history": []} for mode in MODES}}


def clean_round(row):
    if not isinstance(row, dict):
        return None
    score, duration = row.get("score"), row.get("duration")
    if type(score) is not int or not 0 <= score <= 897 or type(duration) not in (int, float) or not 0 <= duration < 1_000_000:
        return None
    try:
        datetime.fromisoformat(row["date"])
    except (KeyError, ValueError, TypeError):
        return None
    if row.get("result") not in ("over", "won", "interrupted"):
        return None
    return {"score": score, "duration": duration, "date": row["date"], "result": row["result"]}


def load_profile(path):
    profile = empty_profile()
    try:
        source = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(source, dict):
            return profile
        settings = source.get("settings", {})
        if isinstance(settings, dict):
            if settings.get("difficulty") in MODES:
                profile["settings"]["difficulty"] = settings["difficulty"]
            if type(settings.get("fullscreen")) is bool:
                profile["settings"]["fullscreen"] = settings["fullscreen"]
        scores = source.get("scores", {})
        if not isinstance(scores, dict):
            return profile
        for mode in MODES:
            values = scores.get(mode, {})
            if not isinstance(values, dict):
                continue
            for key, limit in (("history", 20), ("best", 5)):
                rows = values.get(key, [])
                if isinstance(rows, list):
                    cleaned = [item for row in rows if (item := clean_round(row)) is not None]
                    profile["scores"][mode][key] = (sorted(cleaned, key=lambda row: row["score"], reverse=True) if key == "best" else cleaned)[:limit]
            record = values.get("record", 0)
            record = record if type(record) is int and 0 <= record <= 897 else 0
            rows = profile["scores"][mode]["history"] + profile["scores"][mode]["best"]
            profile["scores"][mode]["record"] = max([record] + [row["score"] for row in rows])
    except (OSError, ValueError, TypeError):
        pass
    return profile


def record_round(profile, mode, score, duration, result):
    scores = profile["scores"][mode]
    new_record = score > scores["record"]
    row = {"score": score, "duration": round(duration, 1), "result": result,
           "date": datetime.now().astimezone().isoformat(timespec="seconds")}
    scores["record"] = max(scores["record"], score)
    scores["history"] = [row, *scores["history"]][:20]
    scores["best"] = sorted([row, *scores["best"]], key=lambda item: item["score"], reverse=True)[:5]
    return new_record


def save_profile(path, profile):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
