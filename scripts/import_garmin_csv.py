#!/usr/bin/env python3
"""Importiert Garmin-CSV-Exporte robust in ein einheitliches Datenmodell."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "garmin" / "csv"
PROCESSED_DIR = ROOT / "data" / "processed"
ACTIVITIES_FILE = PROCESSED_DIR / "activities.csv"
SPLITS_FILE = PROCESSED_DIR / "splits.csv"
HISTORY_FILE = PROCESSED_DIR / "imported_files.json"
DIARY_FILE = ROOT / "logs" / "training_diary_2026.md"

ACTIVITY_FIELDS = [
    "activity_id", "source_file", "date", "sport", "session_name",
    "duration_min", "distance_km", "avg_pace_sec_per_km", "avg_speed_kmh",
    "avg_hr", "max_hr", "avg_power", "max_power", "elevation_gain_m",
    "training_effect", "rpe", "completed", "notes",
]
SPLIT_FIELDS = [
    "activity_id", "split_index", "distance_km", "duration_sec",
    "pace_sec_per_km", "avg_hr", "max_hr", "avg_power", "elevation_gain_m",
]

ALIASES = {
    "activity_id": ("activity id", "aktivitaets id", "id"),
    "date": ("date", "datum", "start time", "startzeit", "start time local"),
    "sport": ("activity type", "aktivitaetstyp", "sport", "type", "aktivitaetsart"),
    "session_name": ("title", "titel", "activity name", "aktivitaetsname", "name"),
    "duration": ("time", "zeit", "duration", "dauer", "elapsed time", "gesamtzeit"),
    "distance": ("distance", "distanz", "distance km", "distanz km"),
    "pace": ("average pace", "avg pace", "durchschnittspace", "pace", "o pace min km"),
    "speed": ("average speed", "avg speed", "durchschnittsgeschwindigkeit", "geschwindigkeit"),
    "avg_hr": ("average heart rate", "avg heart rate", "avg hr", "durchschnittliche herzfrequenz", "o herzfrequenz", "o herzfrequenz bpm"),
    "max_hr": ("maximum heart rate", "max heart rate", "max hr", "maximale herzfrequenz", "maximale herzfrequenz bpm"),
    "avg_power": ("average power", "avg power", "durchschnittliche leistung", "o leistung", "o leistung w"),
    "max_power": ("maximum power", "max power", "max leistung", "max leistung w"),
    "elevation": ("elevation gain", "total ascent", "anstieg gesamt", "anstieg gesamt m", "hoehenmeter"),
    "training_effect": ("training effect", "trainingseffekt", "aerobic te"),
    "rpe": ("rpe", "perceived exertion", "belastungsempfinden"),
    "notes": ("notes", "notizen", "comments", "kommentare"),
    "lap": ("lap", "laps", "runde", "runden", "split"),
}


def normalize(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("Ø", "O").replace("ø", "o").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def find_column(headers: Iterable[str], field: str) -> str | None:
    normalized = {normalize(header): header for header in headers}
    for alias in ALIASES[field]:
        alias_n = normalize(alias)
        if alias_n in normalized:
            return normalized[alias_n]
    # Einheitensuffixe und leicht variierende Garmin-Bezeichnungen tolerieren.
    for key, original in normalized.items():
        if any(key.startswith(normalize(alias) + " ") for alias in ALIASES[field]):
            return original
    return None


def clean_number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"--", "-", "n/a", "N/A"}:
        return None
    text = text.replace("\u00a0", " ")
    match = re.search(r"[-+]?\d[\d., ]*", text)
    if not match:
        return None
    number = match.group(0).replace(" ", "")
    if "," in number and "." in number:
        number = number.replace(".", "").replace(",", ".") if number.rfind(",") > number.rfind(".") else number.replace(",", "")
    else:
        number = number.replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def parse_seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"--", "-"}:
        return None
    if ":" not in text:
        return clean_number(text)
    try:
        parts = [float(part.replace(",", ".")) for part in text.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except ValueError:
        pass
    return None


def parse_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("T", " ").replace("Z", "")
    candidate = re.split(r"\s+", text, maxsplit=1)[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", text)
    if match:
        return "-".join(match.groups())
    compact = re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", text)
    if compact:
        try:
            return datetime.strptime("".join(compact.groups()), "%d%m%Y").date().isoformat()
        except ValueError:
            return ""
    return ""


def sport_code(value: Any, session_name: str = "") -> str:
    text = normalize(f"{value} {session_name}")
    if any(word in text for word in ("cycling", "radfahren", "virtual cycling", "bike", "kickr")):
        return "bike"
    if any(word in text for word in ("strength", "kraft", "weight training")):
        return "strength"
    if any(word in text for word in ("running", "laufen", "lauf", "trail run")):
        return "run"
    return normalize(value).replace(" ", "_") or "run"


def sport_is_explicit(value: Any, session_name: str) -> bool:
    text = normalize(f"{value} {session_name}")
    return any(word in text for word in (
        "running", "laufen", "lauf", "cycling", "radfahren", "bike", "kickr",
        "strength", "kraft", "weight training",
    ))


def infer_sport_from_headers(headers: Iterable[str], columns: dict[str, str | None]) -> str | None:
    header_text = " ".join(normalize(header) for header in headers)
    running_markers = (
        "pace min km", "schrittfrequenz laufen", "bodenkontaktzeit",
        "schrittlange", "vertikale bewegung",
    )
    cycling_markers = (
        "normalized power", "trittfrequenz", "gesamtzeit im stehen",
        "gesamtzeit im sitzen", "power phase", "pco durchschnitt",
        "verhaltnis links", "verhaltnis rechts",
    )
    if any(marker in header_text for marker in running_markers):
        return "run"
    if any(marker in header_text for marker in cycling_markers):
        return "bike"
    if columns.get("speed") and not columns.get("pace"):
        return "bike"
    return None


def title_from_filename(path: Path) -> str:
    title = re.sub(r"(?:20\d{2}[-_]?\d{2}[-_]?\d{2}|\d{2}[-_]?\d{2}[-_]?20\d{2})", "", path.stem)
    title = re.sub(r"^(?:activity|aktivitaet)[_-]*\d*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[_-]+", " ", title).strip()
    return title[:1].upper() + title[1:] if title else ""


def read_csv_flexible(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    raw = path.read_bytes()
    text = ""
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    headers = [header.strip() for header in (reader.fieldnames or []) if header]
    rows = [{str(k).strip(): str(v or "").strip() for k, v in row.items() if k is not None} for row in reader]
    return rows, headers


def diary_hints() -> dict[str, dict[str, str]]:
    """Nutzt bereits bestätigte Tagebuch-Metadaten für metadatenarme Runden-CSVs."""
    if not DIARY_FILE.exists():
        return {}
    text = DIARY_FILE.read_text(encoding="utf-8")
    hints: dict[str, dict[str, str]] = {}
    sections = re.split(r"(?=^## \d{2}\.\d{2}\.\d{4} [–-] )", text, flags=re.MULTILINE)
    for section in sections:
        heading = re.match(r"## (\d{2}\.\d{2}\.\d{4}) [–-] (.+)", section)
        if not heading:
            continue
        date = datetime.strptime(heading.group(1), "%d.%m.%Y").date().isoformat()
        for filename in re.findall(r"data/raw/garmin/csv/([^`\s]+\.csv)", section, flags=re.IGNORECASE):
            hints[filename] = {"date": date, "session_name": heading.group(2).strip()}
    return hints


def stable_id(path: Path, date: str, distance: float | None, duration_sec: float | None, provided: str = "") -> str:
    if provided.strip():
        return provided.strip()
    filename_id = re.search(r"(?:activity[_-])?(\d{8,})", path.stem, flags=re.IGNORECASE)
    if filename_id:
        return filename_id.group(1)
    seed = f"{path.name}|{date}|{distance or ''}|{duration_sec or ''}"
    return "local-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def rounded(value: float | None, digits: int = 2) -> str:
    return "" if value is None else str(round(value, digits))


def row_value(row: dict[str, str], columns: dict[str, str | None], field: str) -> str:
    column = columns.get(field)
    return row.get(column, "") if column else ""


def build_activity(path: Path, row: dict[str, str], columns: dict[str, str | None], hint: dict[str, str], warning: list[str]) -> dict[str, str]:
    duration_sec = parse_seconds(row_value(row, columns, "duration"))
    distance = clean_number(row_value(row, columns, "distance"))
    pace = parse_seconds(row_value(row, columns, "pace"))
    speed = clean_number(row_value(row, columns, "speed"))
    if pace is None and duration_sec and distance:
        pace = duration_sec / distance
    if speed is None and pace:
        speed = 3600 / pace
    date = parse_date(row_value(row, columns, "date")) or parse_date(path.stem) or hint.get("date", "")
    if not date:
        date = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        warning.append(f"{path.name}: Kein Aktivitätsdatum gefunden; Dateidatum {date} verwendet. Datei künftig mit YYYY-MM-DD beginnen.")
    session_name = row_value(row, columns, "session_name") or hint.get("session_name", "") or title_from_filename(path)
    source_sport = row_value(row, columns, "sport")
    sport = sport_code(source_sport, session_name)
    if not sport_is_explicit(source_sport, session_name):
        warning.append(f"{path.name}: Keine Sportart erkannt; 'run' angenommen. Für Rad/Kraft einen Zusatz wie '_kickr' oder '_kraft' verwenden.")
    activity_id = stable_id(path, date, distance, duration_sec, row_value(row, columns, "activity_id"))
    return {
        "activity_id": activity_id,
        "source_file": path.name,
        "date": date,
        "sport": sport,
        "session_name": session_name,
        "duration_min": rounded(duration_sec / 60 if duration_sec is not None else None),
        "distance_km": rounded(distance),
        "avg_pace_sec_per_km": rounded(pace, 1),
        "avg_speed_kmh": rounded(speed),
        "avg_hr": rounded(clean_number(row_value(row, columns, "avg_hr")), 0),
        "max_hr": rounded(clean_number(row_value(row, columns, "max_hr")), 0),
        "avg_power": rounded(clean_number(row_value(row, columns, "avg_power")), 0),
        "max_power": rounded(clean_number(row_value(row, columns, "max_power")), 0),
        "elevation_gain_m": rounded(clean_number(row_value(row, columns, "elevation")), 0),
        "training_effect": rounded(clean_number(row_value(row, columns, "training_effect")), 1),
        "rpe": rounded(clean_number(row_value(row, columns, "rpe")), 1),
        "completed": "true",
        "notes": row_value(row, columns, "notes"),
    }


def build_splits(activity_id: str, rows: list[dict[str, str]], columns: dict[str, str | None]) -> list[dict[str, str]]:
    result = []
    for position, row in enumerate(rows, start=1):
        label = row_value(row, columns, "lap")
        if label and not re.fullmatch(r"\d+", label.strip()):
            continue
        distance = clean_number(row_value(row, columns, "distance"))
        duration = parse_seconds(row_value(row, columns, "duration"))
        if distance is None and duration is None:
            continue
        pace = parse_seconds(row_value(row, columns, "pace"))
        if pace is None and distance and duration:
            pace = duration / distance
        result.append({
            "activity_id": activity_id,
            "split_index": str(int(label)) if label.strip().isdigit() else str(position),
            "distance_km": rounded(distance),
            "duration_sec": rounded(duration, 1),
            "pace_sec_per_km": rounded(pace, 1),
            "avg_hr": rounded(clean_number(row_value(row, columns, "avg_hr")), 0),
            "max_hr": rounded(clean_number(row_value(row, columns, "max_hr")), 0),
            "avg_power": rounded(clean_number(row_value(row, columns, "avg_power")), 0),
            "elevation_gain_m": rounded(clean_number(row_value(row, columns, "elevation")), 0),
        })
    return result


def infer_session_name(activity: dict[str, str], splits: list[dict[str, str]]) -> str:
    distance = clean_number(activity.get("distance_km"))
    duration = clean_number(activity.get("duration_min"))
    avg_hr = clean_number(activity.get("avg_hr"))
    repetitions = [
        split for split in splits
        if 0.35 <= (clean_number(split.get("distance_km")) or 0) <= 0.45
        and (clean_number(split.get("pace_sec_per_km")) or 999) < 270
    ]
    if len(repetitions) >= 4:
        rep_distance = round(sum(clean_number(item["distance_km"]) or 0 for item in repetitions) / len(repetitions) * 1000)
        return f"{len(repetitions)} × {rep_distance} m Intervalle"
    if distance and duration and 4.9 <= distance <= 5.2 and duration <= 30:
        return "5-km-Wettkampf" if (avg_hr or 0) >= 160 else "5-km-Testlauf"
    return "Laufaktivität" if activity.get("sport") == "run" else "Garmin-Aktivität"


def aggregate_split_rows(rows: list[dict[str, str]], columns: dict[str, str | None]) -> dict[str, str]:
    """Erzeugt bei Rundenexporten ohne Übersicht eine belastbare Summenzeile."""
    aggregate: dict[str, str] = {}
    distances = [clean_number(row_value(row, columns, "distance")) for row in rows]
    durations = [parse_seconds(row_value(row, columns, "duration")) for row in rows]
    total_distance = sum(value or 0 for value in distances)
    total_duration = sum(value or 0 for value in durations)
    if columns.get("distance"):
        aggregate[columns["distance"]] = str(total_distance)
    if columns.get("duration"):
        aggregate[columns["duration"]] = str(total_duration)
    if columns.get("pace") and total_distance > 0:
        aggregate[columns["pace"]] = str(total_duration / total_distance)

    for field in ("avg_hr", "avg_power"):
        column = columns.get(field)
        if not column:
            continue
        weighted = [(clean_number(row.get(column)), duration) for row, duration in zip(rows, durations)]
        valid = [(value, weight or 0) for value, weight in weighted if value is not None]
        weight_sum = sum(weight for _, weight in valid)
        if valid:
            aggregate[column] = str(sum(value * weight for value, weight in valid) / weight_sum) if weight_sum else str(sum(value for value, _ in valid) / len(valid))
    for field in ("max_hr", "max_power"):
        column = columns.get(field)
        values = [clean_number(row.get(column)) for row in rows] if column else []
        if column and any(value is not None for value in values):
            aggregate[column] = str(max(value for value in values if value is not None))
    column = columns.get("elevation")
    if column:
        aggregate[column] = str(sum(clean_number(row.get(column)) or 0 for row in rows))
    return aggregate


def parse_file(path: Path, hints: dict[str, dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    rows, headers = read_csv_flexible(path)
    if not headers or not rows:
        return [], [], [f"{path.name}: Keine verwertbaren CSV-Zeilen gefunden."]
    columns = {field: find_column(headers, field) for field in ALIASES}
    if not columns["duration"] and not columns["distance"]:
        return [], [], [f"{path.name}: Weder Dauer- noch Distanzspalte erkannt; Datei übersprungen."]
    inferred_header_sport = infer_sport_from_headers(headers, columns)

    lap_column = columns["lap"]
    summary_markers = {"ubersicht", "uebersicht", "summary", "total", "gesamt"}
    # Garmin platziert "Übersicht" je nach Exportvariante nicht zwingend in
    # der Rundenspalte. Die komplette Zeile prüfen, damit die Summenzeile nicht
    # als zusätzliche Runde in die selbst berechnete Gesamtsumme eingeht.
    summary_rows = [
        row for row in rows
        if any(normalize(value) in summary_markers for value in row.values())
    ]

    activities: list[dict[str, str]] = []
    splits: list[dict[str, str]] = []
    hint = hints.get(path.name, {})
    if summary_rows:
        activity = build_activity(path, summary_rows[-1], columns, hint, warnings)
        activities.append(activity)
        splits = build_splits(activity["activity_id"], rows, columns)
        if not activity["session_name"]:
            activity["session_name"] = infer_session_name(activity, splits)
    else:
        dated_rows = [row for row in rows if parse_date(row_value(row, columns, "date"))]
        is_activity_list = len(dated_rows) > 1
        source_rows = dated_rows if is_activity_list else [aggregate_split_rows(rows, columns) if len(rows) > 1 else rows[-1]]
        for row in source_rows:
            activities.append(build_activity(path, row, columns, hint, warnings))
        if not is_activity_list and len(rows) > 1:
            splits = build_splits(activities[0]["activity_id"], rows, columns)
            if not activities[0]["session_name"]:
                activities[0]["session_name"] = infer_session_name(activities[0], splits)

    for activity in activities:
        if inferred_header_sport:
            activity["sport"] = inferred_header_sport
        if activity["sport"] != "run":
            activity["avg_pace_sec_per_km"] = ""
        if activity["sport"] == "bike" and activity.get("session_name") in {"", "Laufaktivität", "LaufaktivitÃ¤t"}:
            activity["session_name"] = "Radausfahrt"
        if not activity["duration_min"] or not activity["distance_km"]:
            warnings.append(f"{path.name}: Dauer oder Distanz fehlt; unvollständige Aktivität wurde dennoch importiert.")
    if inferred_header_sport:
        warnings = [
            warning for warning in warnings
            if not warning.startswith(f"{path.name}: Keine Sportart erkannt;")
        ]
    return activities, splits, warnings


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_table(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_all(force: bool = False) -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    history: dict[str, Any] = {"files": {}}
    if HISTORY_FILE.exists():
        try:
            loaded = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("files"), dict):
                history = loaded
        except (json.JSONDecodeError, OSError):
            print("WARNUNG: imported_files.json war nicht lesbar und wird neu aufgebaut.")

    existing_activities = read_table(ACTIVITIES_FILE)
    existing_splits = read_table(SPLITS_FILE)
    activities_by_id = {row.get("activity_id", ""): row for row in existing_activities if row.get("activity_id")}
    splits_by_activity: dict[str, list[dict[str, str]]] = {}
    for row in existing_splits:
        splits_by_activity.setdefault(row.get("activity_id", ""), []).append(row)

    imported = 0
    skipped = 0
    warnings: list[str] = []
    hints = diary_hints()
    paths = {path for pattern in ("*.csv", "*.CSV", "*.cvs", "*.CVS") for path in RAW_DIR.glob(pattern)}
    for path in sorted(paths):
        digest = file_digest(path)
        old = history["files"].get(path.name, {})
        recorded_ids = old.get("activity_ids", [])
        records_still_exist = bool(recorded_ids) and all(activity_id in activities_by_id for activity_id in recorded_ids)
        if not force and old.get("sha256") == digest and old.get("status") == "imported" and records_still_exist:
            skipped += 1
            continue
        try:
            parsed_activities, parsed_splits, file_warnings = parse_file(path, hints)
            warnings.extend(file_warnings)
        except Exception as exc:  # Einzelne Fremdformate dürfen den Gesamtbuild nicht stoppen.
            message = f"{path.name}: Importfehler ({exc}); Datei übersprungen."
            warnings.append(message)
            history["files"][path.name] = {"sha256": digest, "status": "error", "message": str(exc)}
            continue
        if not parsed_activities:
            history["files"][path.name] = {"sha256": digest, "status": "skipped", "warnings": file_warnings}
            continue
        for activity in parsed_activities:
            old_row = activities_by_id.get(activity["activity_id"], {})
            # Freiwillige manuelle Ergänzungen bleiben bei erneutem Import erhalten.
            for field in ("rpe", "notes"):
                if old_row.get(field) and not activity.get(field):
                    activity[field] = old_row[field]
            activities_by_id[activity["activity_id"]] = activity
            splits_by_activity[activity["activity_id"]] = [row for row in parsed_splits if row["activity_id"] == activity["activity_id"]]
        history["files"][path.name] = {
            "sha256": digest,
            "status": "imported",
            "imported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "activity_ids": [item["activity_id"] for item in parsed_activities],
            "warnings": file_warnings,
        }
        imported += 1

    activities = sorted(activities_by_id.values(), key=lambda row: (row.get("date", ""), row.get("activity_id", "")))
    splits = [row for activity_id in sorted(splits_by_activity) for row in sorted(splits_by_activity[activity_id], key=lambda x: int(float(x.get("split_index") or 0)))]
    write_table(ACTIVITIES_FILE, activities, ACTIVITY_FIELDS)
    write_table(SPLITS_FILE, splits, SPLIT_FIELDS)
    write_json(HISTORY_FILE, history)
    return {"imported": imported, "skipped": skipped, "activities": len(activities), "splits": len(splits), "warnings": warnings}


def main() -> int:
    result = import_all(force="--force" in sys.argv)
    print(f"Neue oder geänderte Garmin-Dateien importiert: {result['imported']}")
    print(f"Aktivitäten gesamt: {result['activities']}; Splits gesamt: {result['splits']}")
    for warning in result["warnings"]:
        print(f"WARNUNG: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
