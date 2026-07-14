#!/usr/bin/env python3
"""Baut das lokale Laufcoach-Dashboard vollständig aus Quelldaten neu."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from import_garmin_csv import import_all


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DASHBOARD = ROOT / "dashboard"
ACTIVITIES_FILE = PROCESSED / "activities.csv"
SPLITS_FILE = PROCESSED / "splits.csv"
WEEKLY_FILE = PROCESSED / "weekly_summary.csv"
METRICS_FILE = PROCESSED / "dashboard_metrics.json"
DATA_FILE = DASHBOARD / "dashboard_data.json"
INDEX_FILE = DASHBOARD / "index.html"
PLAN_FILE = ROOT / "plans" / "current_week.json"
UPCOMING_FILE = ROOT / "plans" / "upcoming_plan.json"

WEEKLY_FIELDS = [
    "week_start", "week_end", "run_km", "bike_hours", "run_sessions",
    "bike_sessions", "strength_sessions", "hard_endurance_sessions",
    "lit_sessions", "moderate_sessions", "hard_sessions", "total_duration_min",
]
HARD_WORDS = ("400", "800", "1000", "interval", "schwelle", "tempo", "bergsprint", "hiit", "30/30", "over/under", "wettkampf")
MODERATE_WORDS = ("zügig", "steady", "progressiv", "kraft")
COMPLAINT_WORDS = ("schmerz", "achilles", "knie", "schienbein", "hüfte", "beschwerden")
PROGRESSION_PHASES = [
    {
        "period": "Juli-August 2026",
        "start": "2026-07-01",
        "end": "2026-08-31",
        "phase": "Laufrobustheit und Routine",
        "focus": "Kontrollierte Qualitaet, Umfang stabilisieren, kurze Intervalle nicht erzwingen.",
        "markers": [
            {"distance": "400 m", "time": "87-90 s", "pace": "3:38-3:45 min/km", "set": "6-8 x 400 m"},
            {"distance": "1000 m", "time": "3:42-3:48", "pace": "3:42-3:48 min/km", "set": "4 x 1000 m"},
        ],
        "units": ["8 x 400 m kontrolliert", "4 x 1000 m kontrolliert", "Schwelle statt Zielpace"],
    },
    {
        "period": "September-November 2026",
        "start": "2026-09-01",
        "end": "2026-11-30",
        "phase": "Aerobe Basis und Schwelle",
        "focus": "Drei Laeufe stabilisieren, Schwelle verbessern, 400er fuer Oekonomie behalten.",
        "markers": [
            {"distance": "400 m", "time": "84-88 s", "pace": "3:30-3:40 min/km", "set": "10 x 400 m"},
            {"distance": "1000 m", "time": "3:38-3:48", "pace": "3:38-3:48 min/km", "set": "4-5 x 1000 m"},
        ],
        "units": ["4-5 x 1000 m", "10 x 400 m", "20-30 min Tempo/Cruise"],
    },
    {
        "period": "Dezember 2026-Januar 2027",
        "start": "2026-12-01",
        "end": "2027-01-31",
        "phase": "Kraft, Huegel, VO2max-Vorbereitung",
        "focus": "Huegelkraft und laengere Intervalle, noch keine volle 5-km-Schaerfe.",
        "markers": [
            {"distance": "400 m", "time": "82-87 s", "pace": "3:25-3:38 min/km", "set": "12 x 400 m"},
            {"distance": "800 m", "time": "2:48-2:56", "pace": "3:30-3:40 min/km", "set": "6 x 800 m"},
        ],
        "units": ["6 x 800 m", "12 x 400 m", "45-75 s bergauf"],
    },
    {
        "period": "Februar-Maerz 2027",
        "start": "2027-02-01",
        "end": "2027-03-31",
        "phase": "5-km-spezifischer Aufbau",
        "focus": "Einheiten in Richtung 17:xx stabilisieren, Formcheck unter 18:00 vorbereiten.",
        "markers": [
            {"distance": "400 m", "time": "82-85 s", "pace": "3:25-3:33 min/km", "set": "8-10 x 400 m"},
            {"distance": "1000 m", "time": "3:30-3:38", "pace": "3:30-3:38 min/km", "set": "5-6 x 1000 m"},
        ],
        "units": ["5-6 x 1000 m", "4 x 1200 m", "3 x 1600 m", "8-10 x 400 m"],
    },
    {
        "period": "April-Mai 2027",
        "start": "2027-04-01",
        "end": "2027-05-31",
        "phase": "Spezifische 5-km-Form",
        "focus": "Zielpace zunehmend integrieren, Tempohaerte aufbauen.",
        "markers": [
            {"distance": "400 m", "time": "82-85 s", "pace": "3:25-3:33 min/km", "set": "10 x 400 m"},
            {"distance": "800 m", "time": "2:44-2:50", "pace": "3:25-3:33 min/km", "set": "6 x 800 m"},
            {"distance": "1000 m", "time": "3:24-3:32", "pace": "3:24-3:32 min/km", "set": "5 x 1000 m"},
        ],
        "units": ["10 x 400 m", "6 x 800 m", "5 x 1000 m", "3 x 1600 m"],
    },
    {
        "period": "Juni 2027",
        "start": "2027-06-01",
        "end": "2027-06-30",
        "phase": "Peak und Taper",
        "focus": "Frisch werden, Intensitaet kurz erhalten, Umfang reduzieren.",
        "markers": [
            {"distance": "400 m", "time": "81-82 s", "pace": "3:24 min/km", "set": "5 x 400 m"},
            {"distance": "1000 m", "time": "3:24-3:30", "pace": "3:24-3:30 min/km", "set": "3 x 1000 m"},
        ],
        "units": ["5 x 400 m in Zielpace", "3 x 1000 m kontrolliert", "kurze Aktivierung"],
    },
]


def ensure_structure() -> None:
    for directory in (DASHBOARD, PROCESSED, ROOT / "data" / "raw" / "garmin" / "csv", ROOT / "plans"):
        directory.mkdir(parents=True, exist_ok=True)
    if not PLAN_FILE.exists():
        monday = week_start_for(date.today())
        write_json(PLAN_FILE, {
            "week_start": monday.isoformat(),
            "week_end": (monday + timedelta(days=6)).isoformat(),
            "phase": "Noch nicht geplant",
            "focus": "Wochenplan in plans/current_week.json ergänzen",
            "next_milestone": "5-km-Formcheck im Frühjahr 2027",
            "planned_sessions": [],
        })
        print("Hinweis: Fehlenden Plan plans/current_week.json als Vorlage angelegt.")
    if not UPCOMING_FILE.exists():
        write_json(UPCOMING_FILE, {"schema_version": 1, "weeks": []})
        print("Hinweis: Fehlenden Plan plans/upcoming_plan.json als Vorlage angelegt.")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNUNG: {path.relative_to(ROOT)} nicht lesbar: {exc}")
        return default


def load_plan(path: Path) -> dict[str, Any]:
    plan = load_json(path, {"planned_sessions": []})
    if not isinstance(plan, dict):
        print(f"WARNUNG: {path.relative_to(ROOT)} muss ein JSON-Objekt enthalten; leerer Plan verwendet.")
        return {"planned_sessions": []}
    if not isinstance(plan.get("planned_sessions", []), list):
        print(f"WARNUNG: planned_sessions in {path.relative_to(ROOT)} muss eine Liste sein; leere Liste verwendet.")
        plan["planned_sessions"] = []
    plan.setdefault("planned_sessions", [])
    return plan


def write_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def read_activities() -> list[dict[str, Any]]:
    if not ACTIVITIES_FILE.exists():
        return []
    numeric = {
        "duration_min", "distance_km", "avg_pace_sec_per_km", "avg_speed_kmh",
        "avg_hr", "max_hr", "avg_power", "max_power", "elevation_gain_m",
        "training_effect", "rpe",
    }
    with ACTIVITIES_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in numeric:
            try:
                row[field] = float(row[field]) if row.get(field, "").strip() else None
            except (ValueError, AttributeError):
                row[field] = None
        row["completed"] = str(row.get("completed", "")).lower() in {"true", "1", "yes", "ja"}
    return rows


def read_splits() -> list[dict[str, Any]]:
    if not SPLITS_FILE.exists():
        return []
    numeric = {
        "split_index", "distance_km", "duration_sec", "pace_sec_per_km",
        "avg_hr", "max_hr", "avg_power", "elevation_gain_m",
    }
    with SPLITS_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in numeric:
            try:
                row[field] = float(row[field]) if row.get(field, "").strip() else None
            except (ValueError, AttributeError):
                row[field] = None
    return rows


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def week_start_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


def classify_intensity(activity: dict[str, Any]) -> str:
    rpe = activity.get("rpe")
    text = f"{activity.get('session_name', '')} {activity.get('notes', '')}".lower()
    sport = activity.get("sport", "")
    if rpe is not None:
        if rpe >= 8:
            return "hard"
        if rpe >= 6:
            return "moderate"
        return "LIT"
    if "hiit" in text or (sport == "bike" and any(word in text for word in HARD_WORDS)):
        return "hard"
    if any(word in text for word in HARD_WORDS):
        return "hard"
    if any(word in text for word in MODERATE_WORDS):
        return "moderate"
    # Ohne belastbare RPE-/Namensinformation bewusst konservativ als locker einstufen.
    return "LIT"


def summarize_weeks(activities: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
    starts = {week_start_for(d) for item in activities if (d := parse_iso(item.get("date", "")))}
    plan_start = parse_iso(plan.get("week_start", ""))
    if plan_start:
        starts.add(week_start_for(plan_start))
    if starts:
        newest = max(starts)
        starts.update(newest - timedelta(weeks=i) for i in range(8))
    summaries = []
    for start in sorted(starts):
        end = start + timedelta(days=6)
        week_items = [item for item in activities if (d := parse_iso(item.get("date", ""))) and start <= d <= end]
        run_items = [item for item in week_items if item.get("sport") == "run"]
        endurance_items = [item for item in week_items if item.get("sport") in {"run", "bike"}]
        intensity = Counter(classify_intensity(item) for item in endurance_items)
        summaries.append({
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "week_label": f"KW {start.isocalendar().week}",
            "run_km": round(sum(item.get("distance_km") or 0 for item in week_items if item.get("sport") == "run"), 2),
            "bike_hours": round(sum(item.get("duration_min") or 0 for item in week_items if item.get("sport") == "bike") / 60, 2),
            "run_sessions": sum(item.get("sport") == "run" for item in week_items),
            "bike_sessions": sum(item.get("sport") == "bike" for item in week_items),
            "strength_sessions": sum(item.get("sport") == "strength" for item in week_items),
            "hard_endurance_sessions": sum(classify_intensity(item) == "hard" for item in endurance_items),
            "lit_sessions": intensity["LIT"],
            "moderate_sessions": intensity["moderate"],
            "hard_sessions": intensity["hard"],
            "total_duration_min": round(sum(item.get("duration_min") or 0 for item in run_items), 1),
        })
    return summaries


def write_weekly(rows: list[dict[str, Any]]) -> None:
    temporary = WEEKLY_FILE.with_suffix(WEEKLY_FILE.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WEEKLY_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(WEEKLY_FILE)


def comparable_sport(value: str) -> str:
    text = (value or "").lower()
    if text in {"running", "laufen", "run"}:
        return "run"
    if text in {"cycling", "rad", "bike", "virtual_cycling"}:
        return "bike"
    if text in {"strength", "kraft", "strength_training"}:
        return "strength"
    return text


def match_plan(plan: dict[str, Any], activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start = parse_iso(plan.get("week_start", ""))
    end = parse_iso(plan.get("week_end", ""))
    week_items = [item for item in activities if item.get("sport") in {"run", "bike"} and start and end and (d := parse_iso(item.get("date", ""))) and start <= d <= end]
    used: set[str] = set()
    sessions = sorted((dict(item) for item in plan.get("planned_sessions", [])), key=lambda item: item.get("priority", 99))
    for session in sessions:
        # Kraft bleibt reine Planinformation; Ausdauereinheiten werden über
        # importierte Aktivitätsdaten abgeglichen.
        if comparable_sport(session.get("type", "")) not in {"run", "bike"}:
            if session.get("status") == "completed":
                session["display_status"] = "erledigt"
            elif session.get("status") == "optional":
                session["display_status"] = "optional"
            else:
                session["display_status"] = "info"
            continue
        candidates = []
        for activity in week_items:
            if activity.get("activity_id") in used or comparable_sport(activity.get("sport", "")) != comparable_sport(session.get("type", "")):
                continue
            score = 3.0
            title = session.get("title", "").lower()
            actual = activity.get("session_name", "").lower()
            score += sum(1.5 for token in HARD_WORDS if token in title and token in actual)
            target_distance = session.get("target_distance_km")
            actual_distance = activity.get("distance_km")
            if target_distance and actual_distance:
                difference = abs(actual_distance - target_distance) / target_distance
                score += 2 if difference <= 0.2 else (1 if difference <= 0.35 else 0)
            target_duration = session.get("target_duration_min")
            actual_duration = activity.get("duration_min")
            if target_duration and actual_duration:
                difference = abs(actual_duration - target_duration) / target_duration
                score += 1.5 if difference <= 0.25 else (0.5 if difference <= 0.4 else 0)
            scheduled = parse_iso(session.get("scheduled_date", ""))
            actual_date = parse_iso(activity.get("date", ""))
            if scheduled and actual_date and abs((scheduled - actual_date).days) <= 1:
                score += 1
            candidates.append((score, activity))
        if candidates and max(candidates, key=lambda item: item[0])[0] >= 4:
            score, activity = max(candidates, key=lambda item: item[0])
            session["display_status"] = "erledigt"
            session["matched_activity_id"] = activity["activity_id"]
            session["match_reason"] = f"Sportart/Woche passend; Heuristik-Score {score:.1f}"
            used.add(activity["activity_id"])
        elif session.get("status") == "optional":
            session["display_status"] = "optional"
        else:
            session["display_status"] = "offen"
    unmatched = [item for item in week_items if item.get("activity_id") not in used]
    return sessions, unmatched


def detect_performances(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for item in activities:
        distance = item.get("distance_km")
        duration = item.get("duration_min")
        name = item.get("session_name", "").lower()
        if distance and duration and 4.9 <= distance <= 5.2 and any(word in name for word in ("5-km", "5 km", "wettkampf", "race", "parkrun", "test")):
            results.append({"date": item.get("date"), "seconds": round(duration * 60), "activity_id": item.get("activity_id")})
    return sorted(results, key=lambda item: item["date"] or "")


def format_time(seconds: int | float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_split(seconds: int | float) -> str:
    seconds = int(round(seconds))
    if seconds < 100:
        return f"{seconds} s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}:{remainder:02d}"


def format_pace(seconds_per_km: int | float) -> str:
    seconds = int(round(seconds_per_km))
    return f"{seconds // 60}:{seconds % 60:02d} min/km"


def goal_metrics(activities: list[dict[str, Any]]) -> dict[str, Any]:
    performances = detect_performances(activities)
    latest = performances[-1] if performances else {"date": "2026-06-17", "seconds": 18 * 60 + 49}
    current_seconds = latest["seconds"]
    goal_seconds = 16 * 60 + 59
    return {
        "current_5k": format_time(current_seconds),
        "current_5k_date": latest.get("date"),
        "previous_pb": "17:35",
        "target_5k": "16:59",
        "current_pace": format_time(current_seconds / 5) + "/km",
        "target_pace": format_time(goal_seconds / 5) + "/km",
        "gap_to_goal": format_time(max(0, current_seconds - goal_seconds)) + " min",
        "target_400m": "81,5 s (5-km-Renntempo)",
        "progress_percent": round(max(0, min(100, (1129 - current_seconds) / (1129 - goal_seconds) * 100)), 1),
    }


def interval_signal(
    activities: list[dict[str, Any]],
    splits: list[dict[str, Any]],
    distance_km: float,
    minimum_repetitions: int,
    max_pace_sec_per_km: float,
) -> dict[str, Any] | None:
    running_by_id = {item.get("activity_id"): item for item in activities if item.get("sport") == "run"}
    candidates: list[dict[str, Any]] = []
    for activity_id, activity in running_by_id.items():
        name = f"{activity.get('session_name', '')} {activity.get('notes', '')}".lower()
        if not any(word in name for word in ("interval", "400", "800", "1000", "tempo")):
            continue
        repetitions = [
            split for split in splits
            if split.get("activity_id") == activity_id
            and distance_km * 0.95 <= (split.get("distance_km") or 0) <= distance_km * 1.05
            and (split.get("pace_sec_per_km") or 9999) <= max_pace_sec_per_km
        ]
        if len(repetitions) >= minimum_repetitions:
            avg_seconds = sum(split["duration_sec"] for split in repetitions) / len(repetitions)
            best_seconds = min(split["duration_sec"] for split in repetitions)
            candidates.append({
                "date": activity.get("date"),
                "activity_id": activity_id,
                "label": activity.get("session_name", f"{int(distance_km * 1000)}-m-Intervalle"),
                "repetitions": len(repetitions),
                "avg_seconds": round(avg_seconds, 1),
                "best_seconds": round(best_seconds, 1),
            })
    return sorted(candidates, key=lambda item: item.get("date") or "")[-1] if candidates else None


def repetition_targets(activities: list[dict[str, Any]], splits: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [
        {
            "distance_km": 0.4,
            "target_seconds": (16 * 60 + 59) / 5 * 0.4,
            "minimum_repetitions": 6,
            "max_pace_sec_per_km": 260,
            "marker": "8-10 x 400 m zielnah",
        },
        {
            "distance_km": 0.8,
            "target_seconds": (16 * 60 + 59) / 5 * 0.8,
            "minimum_repetitions": 3,
            "max_pace_sec_per_km": 250,
            "marker": "5-6 x 800 m zielnah",
        },
        {
            "distance_km": 1.0,
            "target_seconds": (16 * 60 + 59) / 5,
            "minimum_repetitions": 3,
            "max_pace_sec_per_km": 245,
            "marker": "5 x 1000 m zielnah",
        },
    ]
    rows = []
    for target in targets:
        distance_km = target["distance_km"]
        target_seconds = target["target_seconds"]
        signal = interval_signal(
            activities,
            splits,
            distance_km,
            target["minimum_repetitions"],
            target["max_pace_sec_per_km"],
        )
        current_seconds = signal["avg_seconds"] if signal else None
        gap_seconds = current_seconds - target_seconds if current_seconds is not None else None
        rows.append({
            "distance_m": int(distance_km * 1000),
            "target_seconds": round(target_seconds, 1),
            "target_label": format_split(target_seconds),
            "target_pace_label": format_pace(target_seconds / distance_km),
            "marker": target["marker"],
            "current_seconds": round(current_seconds, 1) if current_seconds is not None else None,
            "current_label": format_split(current_seconds) if current_seconds is not None else "keine Serie",
            "gap_seconds": round(gap_seconds, 1) if gap_seconds is not None else None,
            "gap_label": f"{gap_seconds:+.1f} s" if gap_seconds is not None else "noch keine Daten",
            "progress_percent": round(max(0, min(100, target_seconds / current_seconds * 100)), 1) if current_seconds else 0,
            "source": signal,
        })
    return {
        "race_target": "16:59",
        "pace": "3:24 min/km Renntempo",
        "note": "Balken zeigen den Abstand aktueller Intervall-Serien zum sub-17-Renntempo; 72-s-400er sind Speedreserve, keine Pflicht fuer sub 17.",
        "rows": rows,
    }


def interval_keywords(session: dict[str, Any]) -> list[str]:
    text = " ".join(str(session.get(field, "")) for field in ("title", "main_set", "description", "target_pace")).lower()
    return [keyword for keyword in ("400", "800", "1000") if keyword in text]


def scheduled_interval_units(plan: dict[str, Any], upcoming: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    sources = [
        {
            "week_start": plan.get("week_start"),
            "week_end": plan.get("week_end"),
            "planned_sessions": plan.get("planned_sessions", []),
        }
    ]
    if isinstance(upcoming, dict):
        sources.extend(upcoming.get("weeks", []))
    for week in sources:
        for session in week.get("planned_sessions", []):
            keywords = interval_keywords(session)
            if not keywords:
                continue
            scheduled = session.get("scheduled_date") or week.get("week_start")
            entries.append({
                "date": scheduled,
                "week_start": week.get("week_start"),
                "week_end": week.get("week_end"),
                "title": session.get("title", ""),
                "main_set": session.get("main_set") or session.get("title", ""),
                "target": session.get("target_pace") or "noch keine Zielzeit hinterlegt",
                "status": session.get("display_status") or session.get("status") or "planned",
                "distances": keywords,
            })
    return sorted(entries, key=lambda item: item.get("date") or "")[:8]


def progression_roadmap(plan: dict[str, Any], upcoming: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    rows = []
    for index, phase in enumerate(PROGRESSION_PHASES):
        start = parse_iso(phase["start"])
        end = parse_iso(phase["end"])
        if start and end and start <= today <= end:
            status = "aktuell"
        elif start and today < start:
            status = "geplant"
        else:
            status = "abgeschlossen"
        rows.append({
            **phase,
            "index": index + 1,
            "status": status,
        })
    return {
        "note": "Orientierungsfenster aus dem langfristigen Plan; konkrete Wochenpaces bleiben vom aktuellen Leistungsanker und der Belastbarkeit abhaengig.",
        "rows": rows,
        "scheduled_units": scheduled_interval_units(plan, upcoming),
    }


def create_warnings(plan: dict[str, Any], sessions: list[dict[str, Any]], activities: list[dict[str, Any]], weekly: list[dict[str, Any]]) -> list[dict[str, str]]:
    start = parse_iso(plan.get("week_start", ""))
    end = parse_iso(plan.get("week_end", ""))
    current = next((item for item in weekly if item["week_start"] == (start.isoformat() if start else "")), None)
    previous = next((item for item in weekly if start and item["week_start"] == (start - timedelta(days=7)).isoformat()), None)
    week_activities = [item for item in activities if item.get("sport") in {"run", "bike"} and start and end and (d := parse_iso(item.get("date", ""))) and start <= d <= end]
    warnings: list[dict[str, str]] = []
    if current and current["hard_endurance_sessions"] > 2:
        warnings.append({"level": "warning", "text": "Diese Woche enthält mehr als 2 harte Ausdauerreize. Keine weitere Intensität ergänzen."})
    planned_hard = sum(item.get("target_intensity", "").lower() == "hard" and item.get("type") in {"run", "bike"} for item in sessions if item.get("display_status") != "optional")
    if planned_hard > 2:
        warnings.append({"level": "warning", "text": f"Der Plan enthält {planned_hard} harte Ausdauerreize; auf maximal 2 reduzieren."})
    hard_dates = sorted(
        (d, item.get("title", ""))
        for item in sessions
        if item.get("target_intensity", "").lower() == "hard"
        and item.get("type") in {"run", "bike"}
        and (d := parse_iso(item.get("scheduled_date", "")))
    )
    for (first_date, first_title), (second_date, second_title) in zip(hard_dates, hard_dates[1:]):
        if (second_date - first_date).days <= 1:
            warnings.append({
                "level": "warning",
                "text": f"Harte Einheiten liegen zu eng: {first_title} und {second_title}. Mindestens einen lockeren Tag dazwischen lassen.",
            })
    if current and previous and previous["run_km"] > 0 and current["run_km"] > previous["run_km"] * 1.2:
        increase = round((current["run_km"] / previous["run_km"] - 1) * 100)
        warnings.append({"level": "warning", "text": f"Der Laufumfang ist gegenüber der Vorwoche um {increase} % gestiegen."})
    if sum((item.get("rpe") or 0) >= 9 for item in week_activities) >= 2:
        warnings.append({"level": "warning", "text": "RPE ≥ 9 in mehreren Einheiten – nächste Einheit locker halten."})
    complaint_hits = [item for item in week_activities if any(word in (item.get("notes") or "").lower() for word in COMPLAINT_WORDS)]
    if complaint_hits:
        warnings.append({"level": "critical", "text": "Beschwerden dokumentiert – Laufimpact reduzieren und Verlauf prüfen."})
    today = date.today()
    if start and today >= start and current and current["run_sessions"] == 0:
        warnings.append({"level": "info", "text": "In der aktuellen Planwoche ist noch keine Laufeinheit erfasst."})
    priority = next((item for item in sessions if item.get("priority") == 1), None)
    if priority and priority.get("display_status") != "erledigt":
        prefix = "Geplante" if start and today < start else "Wichtigste"
        warnings.append({"level": "info", "text": f"{prefix} Prioritätseinheit noch offen: {priority.get('title', '')}."})
    if not warnings:
        warnings.append({"level": "ok", "text": "Keine automatischen Warnsignale aus den verfügbaren Daten."})
    return warnings


def next_session(sessions: list[dict[str, Any]]) -> dict[str, Any] | None:
    today = date.today()
    candidates = [item for item in sessions if item.get("display_status") in {"offen", "info"}]
    future = [item for item in candidates if (d := parse_iso(item.get("scheduled_date", ""))) and d >= today]
    if future:
        return min(future, key=lambda item: (item.get("scheduled_date", "9999-12-31"), item.get("priority", 99)))
    open_runs = [item for item in candidates if item.get("display_status") == "offen"]
    return min(open_runs, key=lambda item: (item.get("priority", 99), item.get("scheduled_date", "9999-12-31"))) if open_runs else None


def next_session_from_weeks(plan_weeks: list[dict[str, Any]]) -> dict[str, Any] | None:
    today = date.today()
    candidates: list[dict[str, Any]] = []
    for week in plan_weeks:
        plan = week.get("plan", {})
        week_start = plan.get("week_start", "")
        for session in plan.get("planned_sessions", []):
            if session.get("display_status") not in {"offen", "info"}:
                continue
            session_date = session.get("scheduled_date") or week_start
            parsed = parse_iso(session_date)
            if parsed and parsed >= today:
                candidates.append({**session, "scheduled_date": session_date})
    if candidates:
        return min(candidates, key=lambda item: (item.get("scheduled_date", "9999-12-31"), item.get("priority", 99)))
    return next_session(plan_weeks[0]["plan"].get("planned_sessions", [])) if plan_weeks else None


def plan_week_label(plan: dict[str, Any], today: date | None = None) -> str:
    start = parse_iso(plan.get("week_start", ""))
    end = parse_iso(plan.get("week_end", ""))
    today = today or date.today()
    if start and end and start <= today <= end:
        return "Diese Woche"
    if start and today < start and (start - today).days <= 7:
        return "Nächste Woche"
    if start:
        return f"KW {start.isocalendar().week}"
    return "Planwoche"


def select_plan_week(plan_weeks: list[dict[str, Any]], today: date | None = None) -> dict[str, Any] | None:
    today = today or date.today()
    dated = []
    for week in plan_weeks:
        plan = week.get("plan", {})
        start = parse_iso(plan.get("week_start", ""))
        end = parse_iso(plan.get("week_end", ""))
        if start and end:
            dated.append((start, end, week))
    current = [week for start, end, week in dated if start <= today <= end]
    if current:
        return current[0]
    future = [(start, week) for start, _, week in dated if start > today]
    if future:
        return min(future, key=lambda item: item[0])[1]
    past = [(end, week) for _, end, week in dated if end < today]
    if past:
        return max(past, key=lambda item: item[0])[1]
    return plan_weeks[0] if plan_weeks else None


def plan_week_payload(
    plan: dict[str, Any],
    activities: list[dict[str, Any]],
    weekly: list[dict[str, Any]],
    key: str,
    label: str,
) -> dict[str, Any]:
    sessions, unmatched = match_plan(plan, activities)
    summary = next((item for item in weekly if item["week_start"] == plan.get("week_start", "")), {})
    return {
        "key": key,
        "label": label,
        "plan": {**plan, "planned_sessions": sessions},
        "warnings": create_warnings(plan, sessions, activities, weekly),
        "unmatched_activities": unmatched,
        "week_summary": summary,
        "intensity": {
            "LIT": summary.get("lit_sessions", 0),
            "moderate": summary.get("moderate_sessions", 0),
            "hard": summary.get("hard_sessions", 0),
        },
    }


def build_data(plan: dict[str, Any], upcoming: dict[str, Any], activities: list[dict[str, Any]], splits: list[dict[str, Any]], weekly: list[dict[str, Any]]) -> dict[str, Any]:
    running_activities = [item for item in activities if item.get("sport") == "run"]
    source_weeks = [plan]
    if isinstance(upcoming, dict):
        source_weeks.extend(week for week in upcoming.get("weeks", []) if isinstance(week, dict))
    today = date.today()
    plan_weeks = [
        plan_week_payload(week, activities, weekly, f"week-{week.get('week_start', index)}", plan_week_label(week, today))
        for index, week in enumerate(source_weeks)
    ]
    active_week = select_plan_week(plan_weeks, today) or plan_weeks[0]
    plan_with_sessions = active_week["plan"]
    warnings = active_week["warnings"]
    recent = sorted(activities, key=lambda item: (item.get("date", ""), item.get("activity_id", "")), reverse=True)[:10]
    for item in recent:
        item["intensity"] = classify_intensity(item)
    plan_start = plan.get("week_start", "")
    current_summary = active_week["week_summary"]
    metrics = {
        "goal": goal_metrics(running_activities),
        "current_week": current_summary,
        "warning_count": sum(item["level"] in {"warning", "critical"} for item in warnings),
        "activities_total": len(running_activities),
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "today": date.today().isoformat(),
        "header": {
            "title": "Laufcoach Dashboard",
            "goal": "5 km sub 17 im Juni 2027",
            "phase": plan.get("phase", "Keine Phase hinterlegt"),
            "focus": plan.get("focus", ""),
            "next_milestone": plan.get("next_milestone", "5-km-Formcheck im Frühjahr 2027"),
        },
        "plan": plan_with_sessions,
        "plan_weeks": plan_weeks,
        "selected_plan_key": active_week["key"],
        "next_session": next_session_from_weeks(plan_weeks),
        "recent_activities": recent,
        "unmatched_activities": active_week["unmatched_activities"],
        "weekly_summary": weekly[-10:],
        "intensity": active_week["intensity"],
        "repetition_targets": repetition_targets(activities, splits),
        "progression_roadmap": progression_roadmap(plan_with_sessions, upcoming),
        "warnings": warnings,
        "metrics": metrics,
        "upcoming": upcoming.get("weeks", [])[:3] if isinstance(upcoming, dict) else [],
    }


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <title>Laufcoach Dashboard</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="hero">
    <div><p class="eyebrow">LOKAL · OFFLINE · AKTUELL</p><h1>Laufcoach Dashboard</h1><p class="hero-goal">5 km sub 17 im Juni 2027</p></div>
    <div class="hero-meta" id="hero-meta"></div>
  </header>
  <main>
    <section class="primary-plan"><div class="section-head plan-head"><div><p class="eyebrow">PLAN</p><h2 id="plan-title">Aktuelle Woche</h2></div><div class="plan-controls" id="plan-switcher" aria-label="Planwoche wählen"></div><p id="week-focus"></p></div><div class="session-grid" id="sessions"></div></section>
    <section id="next-session"></section>
    <section><div class="section-head"><div><p class="eyebrow">LEISTUNGSANKER</p><h2>Ziel-Fortschritt</h2></div><div id="progress-label"></div></div><div class="metric-grid" id="goal-metrics"></div></section>
    <section><div class="section-head"><div><p class="eyebrow">ZIELSPLITS</p><h2>Sub-17 Intervallmarker</h2></div><span class="muted" id="rep-target-note"></span></div><div class="target-grid" id="rep-targets"></div></section>
    <section><div class="section-head"><div><p class="eyebrow">ROADMAP</p><h2>Wann welche Marker relevant werden</h2></div><span class="muted" id="roadmap-note"></span></div><div class="roadmap" id="roadmap"></div><div class="scheduled-strip" id="scheduled-units"></div></section>
    <section class="two-column"><div class="panel"><div class="section-head"><div><p class="eyebrow">COACH CHECK</p><h2>Hinweise</h2></div></div><div id="warnings"></div></div><div class="panel"><div class="section-head"><div><p class="eyebrow">VERTEILUNG</p><h2>Intensität</h2></div><span class="muted">Lauf + Rad</span></div><div id="intensity"></div></div></section>
    <section><div class="section-head"><div><p class="eyebrow">VERLAUF</p><h2>Wochenumfang</h2></div><span class="muted">Laufkilometer · letzte 10 Wochen</span></div><div class="chart" id="weekly-chart"></div><div class="summary-row" id="weekly-summary"></div></section>
    <section><div class="section-head"><div><p class="eyebrow">HISTORIE</p><h2>Letzte Aktivitäten</h2></div></div><div class="table-wrap"><table><thead><tr><th>Datum</th><th>Sport</th><th>Einheit</th><th>Dauer</th><th>Distanz</th><th>Pace / Leistung</th><th>Puls</th><th>RPE</th><th>Notizen</th></tr></thead><tbody id="activities"></tbody></table></div><div id="unmatched"></div></section>
    <section><div class="section-head"><div><p class="eyebrow">AUSBLICK</p><h2>Nächste Wochen</h2></div></div><div class="upcoming-grid" id="upcoming"></div></section>
  </main>
  <footer>Generiert <span id="generated"></span> · Quelle: lokale Plan- und Garmin-Daten</footer>
  <script>window.DASHBOARD_DATA = {payload};</script>
  <script>
  (() => {{
    const d = window.DASHBOARD_DATA;
    const $ = id => document.getElementById(id);
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    const num = (value, digits=1) => value == null || value === '' ? '–' : Number(value).toLocaleString('de-DE', {{maximumFractionDigits:digits}});
    const pace = sec => sec ? `${{Math.floor(sec/60)}}:${{String(Math.round(sec%60)).padStart(2,'0')}}/km` : '–';
    const sport = value => ({{run:'Lauf',bike:'Rad',strength:'Kraft'}}[value] || value || '–');
    const fmtDate = value => value ? new Intl.DateTimeFormat('de-DE', {{dateStyle:'medium'}}).format(new Date(value+'T12:00:00')) : '–';
    const statusClass = value => ({{erledigt:'done',offen:'open',optional:'optional',info:'info'}}[value] || 'open');
    const planWeeks = d.plan_weeks && d.plan_weeks.length ? d.plan_weeks : [{{key:'current', label:'Aktuelle Woche', plan:d.plan, warnings:d.warnings, unmatched_activities:d.unmatched_activities, week_summary:d.metrics.current_week, intensity:d.intensity}}];
    const todayIso = () => {{
      const now = new Date();
      const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
      return local.toISOString().slice(0, 10);
    }};
    const currentDateIso = todayIso();
    const isoWeek = value => {{
      const dt = new Date(value + 'T12:00:00');
      dt.setDate(dt.getDate() + 4 - (dt.getDay() || 7));
      const yearStart = new Date(dt.getFullYear(), 0, 1);
      return Math.ceil((((dt - yearStart) / 86400000) + 1) / 7);
    }};
    const weekLabel = week => {{
      const plan = week.plan || {{}};
      if (plan.week_start && plan.week_end && plan.week_start <= currentDateIso && currentDateIso <= plan.week_end) return 'Diese Woche';
      if (plan.week_start && plan.week_start > currentDateIso) {{
        const daysUntil = (new Date(plan.week_start + 'T12:00:00') - new Date(currentDateIso + 'T12:00:00')) / 86400000;
        if (daysUntil <= 7) return 'Nächste Woche';
      }}
      return plan.week_start ? `KW ${{isoWeek(plan.week_start)}}` : (week.label || 'Planwoche');
    }};
    const selectInitialPlanKey = () => {{
      const current = planWeeks.find(week => {{
        const plan = week.plan || {{}};
        return plan.week_start && plan.week_end && plan.week_start <= currentDateIso && currentDateIso <= plan.week_end;
      }});
      if (current) return current.key;
      const future = planWeeks.filter(week => (week.plan || {{}}).week_start > currentDateIso).sort((a,b) => (a.plan.week_start || '').localeCompare(b.plan.week_start || ''));
      if (future.length) return future[0].key;
      const past = planWeeks.filter(week => (week.plan || {{}}).week_end < currentDateIso).sort((a,b) => (b.plan.week_end || '').localeCompare(a.plan.week_end || ''));
      if (past.length) return past[0].key;
      return d.selected_plan_key || planWeeks[0].key;
    }};
    let selectedPlanKey = selectInitialPlanKey();
    const activePlanWeek = () => planWeeks.find(week => week.key === selectedPlanKey) || planWeeks[0];
    $('hero-meta').innerHTML = `<div><span>Stand</span><strong>${{fmtDate(currentDateIso)}}</strong></div><div><span>Phase</span><strong>${{esc(d.header.phase)}}</strong></div><div><span>Nächste Marke</span><strong>${{esc(d.header.next_milestone)}}</strong></div>`;
    const g = d.metrics.goal;
    const cards = [['Aktuelle 5-km-Zeit',g.current_5k],['Frühere Bestzeit',g.previous_pb],['Zielzeit',g.target_5k],['Aktuelle Pace',g.current_pace],['Zielpace',g.target_pace],['Differenz zum Ziel',g.gap_to_goal],['400 m im 5-km-Tempo',g.target_400m]];
    $('goal-metrics').innerHTML = cards.map(([label,value],i) => `<article class="metric ${{i===2?'accent':''}}"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong>${{i===0?`<small>${{fmtDate(g.current_5k_date)}}</small>`:''}}</article>`).join('');
    $('progress-label').innerHTML = `<span class="progress-value">${{num(g.progress_percent)}} %</span><span class="muted">vom Startanker zum Ziel</span>`;
    const rt = d.repetition_targets;
    $('rep-target-note').textContent = rt.note;
    $('rep-targets').innerHTML = rt.rows.map(row => {{
      const source = row.source;
      const gapClass = row.gap_seconds == null ? 'missing' : (row.gap_seconds <= 0 ? 'ready' : 'gap');
      const gapText = row.gap_seconds == null ? 'noch keine Daten' : `${{row.gap_seconds > 0 ? '+' : ''}}${{Math.round(row.gap_seconds)}} s`;
      const targetText = `${{row.target_label}} · ${{row.target_pace_label}} · ${{row.marker}}`;
      return `<article class="target-card ${{gapClass}}"><div class="target-head"><span>${{row.distance_m}} m</span><strong>${{esc(gapText)}}</strong></div><div class="target-bar" title="${{num(row.progress_percent)}} %"><i style="width:${{row.progress_percent}}%"></i><b></b></div><dl><div><dt>Aktuell</dt><dd>${{esc(row.current_label)}}${{source ? ` Ø aus ${{source.repetitions}} Wdh.` : ''}}</dd></div><div><dt>Ziel</dt><dd>${{esc(targetText)}}</dd></div><div><dt>Quelle</dt><dd>${{source ? `${{esc(source.label)}} · ${{fmtDate(source.date)}}` : 'keine passende Intervallserie'}}</dd></div></dl></article>`;
    }}).join('');
    const pr = d.progression_roadmap;
    $('roadmap-note').textContent = pr.note;
    $('roadmap').innerHTML = pr.rows.map(row => `<article class="roadmap-card ${{esc(row.status)}}"><div class="roadmap-top"><span>${{esc(row.period)}}</span><b>${{esc(row.status)}}</b></div><h3>${{esc(row.phase)}}</h3><p>${{esc(row.focus)}}</p><div class="marker-list">${{row.markers.map(m => `<div><strong>${{esc(m.distance)}}</strong><span>${{esc(m.time)}} · ${{esc(m.pace)}}</span><small>${{esc(m.set)}}</small></div>`).join('')}}</div><ul>${{row.units.map(unit => `<li>${{esc(unit)}}</li>`).join('')}}</ul></article>`).join('');
    $('scheduled-units').innerHTML = pr.scheduled_units.length ? `<div><strong>Konkret im Plan</strong><span>${{pr.scheduled_units.map(unit => `${{fmtDate(unit.date)}}: ${{esc(unit.main_set)}} (${{esc(unit.target)}})`).join(' · ')}}</span></div>` : '';
    const planDetails = s => [
      ['Warm-up', s.warmup],
      ['Hauptteil', s.main_set],
      ['Pause', s.recovery],
      ['Cool-down', s.cooldown],
      ['Setup', s.setup],
      ['Alternativen', s.alternatives]
    ].filter(([,value]) => value != null && value !== '').map(([label,value]) => `<div><dt>${{esc(label)}}</dt><dd>${{esc(value)}}</dd></div>`).join('');
    if (d.next_session) {{ const s=d.next_session; $('next-session').innerHTML=`<article class="next-card"><div><p class="eyebrow">NÄCHSTE EMPFOHLENE EINHEIT · ${{fmtDate(s.scheduled_date)}}</p><h2>${{esc(s.title)}}</h2><p>${{esc(s.description)}}</p></div><div class="next-target"><span>${{esc(s.target_pace || 'Ziel gemäß Plan')}}</span><strong>RPE ${{esc(s.rpe_target || '–')}}</strong><small>Priorität ${{esc(s.priority)}} · ${{esc(s.target_intensity)}}</small></div></article>`; }}
    const weeks=d.weekly_summary, max=Math.max(1,...weeks.map(w=>w.run_km));
    $('weekly-chart').innerHTML=weeks.map(w=>`<div class="bar-column"><span>${{num(w.run_km)}} km</span><div class="bar-track"><i style="height:${{Math.max(2,w.run_km/max*100)}}%"></i></div><small>${{esc(w.week_label)}}</small></div>`).join('');
    const renderPlanSwitcher = () => {{
      $('plan-switcher').innerHTML = planWeeks.map(week => `<button type="button" class="${{week.key === selectedPlanKey ? 'active' : ''}}" data-plan-key="${{esc(week.key)}}">${{esc(weekLabel(week))}}</button>`).join('');
      $('plan-switcher').querySelectorAll('button').forEach(button => button.addEventListener('click', () => {{
        selectedPlanKey = button.dataset.planKey;
        renderPlanPanel();
      }}));
    }};
    const renderPlanPanel = () => {{
      const week = activePlanWeek();
      const plan = week.plan || {{}};
      const intensity = week.intensity || {{LIT:0, moderate:0, hard:0}};
      const summary = week.week_summary || {{}};
      $('plan-title').textContent = weekLabel(week);
      $('week-focus').textContent = `${{fmtDate(plan.week_start)}}–${{fmtDate(plan.week_end)}} · ${{plan.focus || ''}}`;
      $('sessions').innerHTML = (plan.planned_sessions || []).map(s => `<article class="session-card ${{statusClass(s.display_status)}}"><div class="card-top"><span class="priority">P${{esc(s.priority)}}</span>${{s.display_status==='info'?'':`<span class="badge ${{statusClass(s.display_status)}}">${{esc(s.display_status)}}</span>`}}</div><p class="sport">${{esc(sport(s.type))}} · ${{fmtDate(s.scheduled_date || plan.week_start)}}</p><h3>${{esc(s.title)}}</h3><p>${{esc(s.description || '')}}</p><dl>${{planDetails(s)}}<div><dt>Ziel</dt><dd>${{esc(s.target_pace || '–')}}</dd></div><div><dt>Umfang</dt><dd>${{s.target_duration_min?esc(s.target_duration_min)+' min':''}}${{s.target_duration_min&&s.target_distance_km?' · ':''}}${{s.target_distance_km?num(s.target_distance_km)+' km':''}}</dd></div><div><dt>Intensität</dt><dd>${{esc(s.target_intensity)}} · RPE ${{esc(s.rpe_target || '–')}}</dd></div></dl>${{s.match_reason?`<small>${{esc(s.match_reason)}}</small>`:''}}</article>`).join('');
      $('warnings').innerHTML = (week.warnings || []).map(w => `<div class="notice ${{esc(w.level)}}"><span></span><p>${{esc(w.text)}}</p></div>`).join('');
      const total = Math.max(1, Object.values(intensity).reduce((a,b)=>a+b,0));
      $('intensity').innerHTML = ['LIT','moderate','hard'].map(key => `<div class="intensity-row"><div><span class="dot ${{key}}"></span><strong>${{key==='moderate'?'Moderat':key}}</strong><b>${{intensity[key] || 0}}</b></div><div class="track"><i class="${{key}}" style="width:${{(intensity[key] || 0)/total*100}}%"></i></div></div>`).join('');
      $('weekly-summary').innerHTML=`<div><strong>${{num(summary.run_km)}} km</strong><span>Laufumfang</span></div><div><strong>${{summary.run_sessions||0}}</strong><span>Läufe</span></div><div><strong>${{summary.hard_endurance_sessions||0}}</strong><span>harte Ausdauer</span></div>`;
      const unmatched = week.unmatched_activities || [];
      $('unmatched').innerHTML = unmatched.length ? `<p class="unmatched"><strong>${{unmatched.length}} nicht zugeordnet:</strong> ${{unmatched.map(a=>esc(a.session_name)).join(', ')}}</p>` : '';
      renderPlanSwitcher();
    }};
    $('activities').innerHTML=d.recent_activities.length?d.recent_activities.map(a=>`<tr><td>${{fmtDate(a.date)}}</td><td><span class="badge neutral">${{esc(sport(a.sport))}}</span></td><td><strong>${{esc(a.session_name)}}</strong><small>${{esc(a.intensity)}}</small></td><td>${{num(a.duration_min)}} min</td><td>${{a.distance_km!=null?num(a.distance_km,2)+' km':'–'}}</td><td>${{a.avg_pace_sec_per_km?pace(a.avg_pace_sec_per_km):(a.avg_power?num(a.avg_power,0)+' W':'–')}}</td><td>${{a.avg_hr?num(a.avg_hr,0)+' / '+num(a.max_hr,0):'–'}}</td><td>${{num(a.rpe)}}</td><td>${{esc(a.notes||'–')}}</td></tr>`).join(''):'<tr><td colspan="9" class="empty">Noch keine Aktivitäten importiert.</td></tr>';
    const activityLabels = ['Datum','Sport','Einheit','Dauer','Distanz','Pace / Leistung','Puls','RPE','Notizen'];
    $('activities').querySelectorAll('tr').forEach(row => row.querySelectorAll('td:not(.empty)').forEach((cell, index) => cell.dataset.label = activityLabels[index]));
    const sessionDetails = s => [
      ['Priorität', s.priority],
      ['Intensität', s.target_intensity],
      ['Dauer', s.target_duration_min ? `${{s.target_duration_min}} min` : ''],
      ['Distanz', s.target_distance_km ? `${{num(s.target_distance_km)}} km` : ''],
      ['Warm-up', s.warmup],
      ['Hauptteil', s.main_set],
      ['Pause', s.recovery],
      ['Cool-down', s.cooldown],
      ['Setup', s.setup],
      ['Alternativen', s.alternatives],
      ['Pace / Leistung', s.target_pace],
      ['RPE', s.rpe_target],
      ['Status', s.status],
      ['Details', s.description]
    ].filter(([,value]) => value != null && value !== '').map(([label,value]) => `<div><dt>${{esc(label)}}</dt><dd>${{esc(value)}}</dd></div>`).join('');
    $('upcoming').innerHTML=d.upcoming.map(w=>`<article><p class="eyebrow">${{fmtDate(w.week_start)}} – ${{fmtDate(w.week_end)}}</p><h3>${{esc(w.focus)}}</h3><ul>${{(w.planned_sessions||[]).map(s=>`<li class="upcoming-session" tabindex="0"><span>${{esc(sport(s.type))}}</span><strong>${{esc(s.title)}}</strong><div class="session-popover"><p>${{esc(s.title)}}</p><dl>${{sessionDetails(s)}}</dl></div></li>`).join('')}}</ul></article>`).join('');
    renderPlanPanel();
    $('generated').textContent = new Intl.DateTimeFormat('de-DE', {{dateStyle:'medium',timeStyle:'short'}}).format(new Date(d.generated_at));
  }})();
  </script>
</body>
</html>'''


def main() -> int:
    ensure_structure()
    print("Laufcoach Dashboard Build")
    print("-------------------------")
    imported = import_all()
    for warning in imported["warnings"]:
        print(f"WARNUNG: {warning}")
    plan = load_plan(PLAN_FILE)
    upcoming = load_json(UPCOMING_FILE, {"weeks": []})
    if not isinstance(upcoming, dict):
        print(f"WARNUNG: {UPCOMING_FILE.relative_to(ROOT)} muss ein JSON-Objekt enthalten; leerer Ausblick verwendet.")
        upcoming = {"weeks": []}
    activities = read_activities()
    splits = read_splits()
    weekly = summarize_weeks(activities, plan)
    write_weekly(weekly)
    data = build_data(plan, upcoming, activities, splits, weekly)
    write_json(DATA_FILE, data)
    write_json(METRICS_FILE, data["metrics"])
    temporary_index = INDEX_FILE.with_suffix(INDEX_FILE.suffix + ".tmp")
    with temporary_index.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_html(data))
    temporary_index.replace(INDEX_FILE)
    completed = sum(item.get("display_status") == "erledigt" for item in data["plan"].get("planned_sessions", []))
    week_date = parse_iso(plan.get("week_start", ""))
    week_label = f"{week_date.isocalendar().year}-W{week_date.isocalendar().week:02d}" if week_date else "nicht gesetzt"
    print(f"Neue Garmin-Dateien importiert: {imported['imported']}")
    print(f"Laufaktivitäten gesamt: {sum(item.get('sport') == 'run' for item in activities)}")
    print(f"Aktuelle Woche: {week_label}")
    print(f"Geplante Einheiten: {len(data['plan'].get('planned_sessions', []))}")
    print(f"Erledigte Einheiten: {completed}")
    print(f"Warnungen: {data['metrics']['warning_count']}")
    print("Dashboard aktualisiert: dashboard/index.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("Abgebrochen.")
    except Exception as exc:
        print(f"FEHLER: Dashboard konnte nicht gebaut werden: {exc}", file=sys.stderr)
        raise SystemExit(1)
