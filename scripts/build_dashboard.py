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
SEASON_FILE = ROOT / "plans" / "season_goals.json"

WEEKLY_FIELDS = [
    "week_start", "week_end", "run_km", "bike_hours", "run_sessions",
    "bike_sessions", "strength_sessions", "hard_endurance_sessions",
    "lit_sessions", "moderate_sessions", "hard_sessions", "total_duration_min",
]
HARD_WORDS = ("200", "400", "800", "1000", "interval", "schwelle", "tempo", "bergsprint", "hiit", "30/30", "over/under", "wettkampf")
MODERATE_WORDS = ("zügig", "steady", "progressiv", "kraft", "pyramide")
COMPLAINT_WORDS = ("schmerz", "achilles", "knie", "schienbein", "hüfte", "beschwerden")


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
            "next_milestone": "10-km-Test im Frühjahr 2027",
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
            "total_duration_min": round(sum(item.get("duration_min") or 0 for item in week_items), 1),
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


def match_plan(plan: dict[str, Any], activities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    start = parse_iso(plan.get("week_start", ""))
    end = parse_iso(plan.get("week_end", ""))
    week_items = [item for item in activities if item.get("sport") in {"run", "bike"} and start and end and (d := parse_iso(item.get("date", ""))) and start <= d <= end]
    sessions = sorted((dict(item) for item in plan.get("planned_sessions", [])), key=lambda item: item.get("priority", 99))
    # Bestätigte Zuordnungen reservieren, bevor eine frühere Planposition
    # dieselbe Aktivität durch die Heuristik beanspruchen könnte.
    used: set[str] = {str(s["completed_activity_id"]) for s in sessions
                      if s.get("status") == "completed" and s.get("completed_activity_id")}
    for session in sessions:
        if session.get("status") == "cancelled":
            session["display_status"] = "entfällt"
            continue
        # Manuell dokumentierte Aktivitäten haben keine importierte Aktivitäts-ID,
        # können aber im Plan ausdrücklich als erledigt markiert sein.
        if session.get("status") == "completed":
            session["display_status"] = "erledigt"
            if session.get("completed_activity_id"):
                used.add(str(session["completed_activity_id"]))
                if any(str(a.get("activity_id")) == str(session["completed_activity_id"]) for a in week_items):
                    session["matched_activity_id"] = session["completed_activity_id"]
                    session["match_reason"] = "Nach Aktivitätsanalyse ausdrücklich zugeordnet"
            continue
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
            session_sport = comparable_sport(session.get("type", ""))
            activity_sport = comparable_sport(activity.get("sport", ""))
            is_bike_alternative = (
                session_sport == "run"
                and activity_sport == "bike"
                and "rad" in str(session.get("alternatives", "")).lower()
            )
            if activity.get("activity_id") in used or (activity_sport != session_sport and not is_bike_alternative):
                continue
            score = 3.0
            title = session.get("title", "").lower()
            actual = activity.get("session_name", "").lower()
            score += sum(1.5 for token in HARD_WORDS if token in title and token in actual)
            target_distance = session.get("target_distance_km")
            actual_distance = activity.get("distance_km")
            if target_distance and actual_distance and not is_bike_alternative:
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
            candidates.append((score, activity, is_bike_alternative))
        if candidates and max(candidates, key=lambda item: item[0])[0] >= 4:
            score, activity, is_bike_alternative = max(candidates, key=lambda item: item[0])
            session["display_status"] = "erledigt"
            session["matched_activity_id"] = activity["activity_id"]
            prefix = "Radalternative" if is_bike_alternative else "Sportart/Woche passend"
            session["match_reason"] = f"{prefix}; Heuristik-Score {score:.1f}"
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
        "note": "Zielsplit und letzte erfasste Intervallserie im Vergleich. Kurze schnelle Wiederholungen sind kein Nachweis der 5-km-Wettkampfform.",
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


def complete_plan_weeks(source_weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nur tatsächlich geplante Wochen ausliefern, keine Jahresplan-Platzhalter."""
    explicit: dict[str, dict[str, Any]] = {}
    for week in source_weeks:
        start = parse_iso(week.get("week_start", ""))
        if start:
            key = start.isoformat()
            if key in explicit:
                raise ValueError(f"Doppelte Planwoche: {key}")
            explicit[key] = week
    return [explicit[key] for key in sorted(explicit)]


def validate_plan_horizon(source_weeks: list[dict[str, Any]], today: date | None = None) -> None:
    """Ein Build braucht vollständige konkrete Pläne für diese und nächste Woche."""
    monday = week_start_for(today or date.today())
    weeks = {week.get("week_start"): week for week in complete_plan_weeks(source_weeks)}
    for start in (monday, monday + timedelta(days=7)):
        plan = weeks.get(start.isoformat(), {})
        validate_concrete_week(plan, start)


def validate_concrete_week(plan: dict[str, Any], start: date) -> None:
    if start.weekday() != 0:
        raise ValueError(f"Planwoche beginnt nicht montags: {start}")
    sessions = plan.get("planned_sessions", [])
    if plan.get("generated") or not sessions:
        raise ValueError(f"Konkreter Trainingsplan fehlt für {start.isoformat()}; aktuelle und nächste Woche müssen gepflegt sein.")
    end = start + timedelta(days=6)
    if plan.get("week_end") != end.isoformat():
        raise ValueError(f"Ungültiges Wochenende im Plan {start.isoformat()}")
    ids = set()
    for session in sessions:
        scheduled = parse_iso(session.get("scheduled_date", ""))
        if not scheduled or not start <= scheduled <= end:
            raise ValueError(f"Einheitsdatum außerhalb der Planwoche {start.isoformat()}")
        for field in ("id", "type", "title", "warmup", "main_set", "recovery", "cooldown", "target_pace"):
            if not session.get(field):
                raise ValueError(f"{session.get('title', 'Einheit')}: {field} fehlt")
        if session["type"] not in {"run", "strength", "rest"}:
            raise ValueError("Im Hauptplan stehen nur Lauf, Kraft oder Ruhetage; Rad bleibt Alternative.")
        if session["id"] in ids:
            raise ValueError(f"Doppelte Einheits-ID: {session['id']}")
        ids.add(session["id"])
        if not isinstance(session.get("target_duration_min"), (int, float)) or session["target_duration_min"] <= 0:
            raise ValueError(f"{session['title']}: positive Gesamtdauer fehlt")
        if session["type"] == "run" and not session.get("alternatives"):
            raise ValueError(f"{session['title']}: Radalternative fehlt")
        parts = session.get("duration_components_min")
        if parts and abs(sum(parts.values()) - session["target_duration_min"]) > 0.11:
            raise ValueError(f"{session['title']}: Teilzeiten passen nicht zur Gesamtdauer")
        if session["type"] == "run" and scheduled.weekday() < 5 and not session.get("race_distance_km") and session["target_duration_min"] > 60:
            raise ValueError(f"{session['title']}: überschreitet die verfügbare Stunde unter der Woche")


def validate_season_plan(source_weeks: list[dict[str, Any]], season: dict[str, Any]) -> None:
    """Lücken, unvollständige Fernplanung und fehlende Zielrennen verhindern."""
    start, end = parse_iso(season.get("plan_start", "")), parse_iso(season.get("plan_end", ""))
    if not start or not end or end < start:
        raise ValueError("Gültiger Saisonzeitraum fehlt in plans/season_goals.json")
    weeks = {w["week_start"]: w for w in complete_plan_weeks(source_weeks)}
    cursor = start
    all_sessions = []
    while cursor <= end:
        plan = weeks.get(cursor.isoformat(), {})
        validate_concrete_week(plan, cursor)
        sessions = plan["planned_sessions"]
        if sum(s.get("target_intensity") == "hard" for s in sessions) > 2:
            raise ValueError(f"Mehr als zwei harte Einheiten in {cursor}")
        all_sessions.extend(sessions)
        cursor += timedelta(days=7)
    ids = [s["id"] for s in all_sessions]
    if len(set(ids)) != len(ids):
        raise ValueError("Einheits-IDs sind über die Saison nicht eindeutig")
    hard_dates = sorted(date.fromisoformat(s["scheduled_date"]) for s in all_sessions if s.get("target_intensity") == "hard")
    if any((b-a).days < 2 for a,b in zip(hard_dates, hard_dates[1:])):
        raise ValueError("Harte Ausdauerreize liegen an aufeinanderfolgenden Tagen")
    for key in ("test_goal", "primary_goal"):
        goal = season.get(key, {})
        matching = [s for s in all_sessions if s.get("scheduled_date") == goal.get("date") and s.get("race_distance_km") == goal.get("distance_km") and s.get("type") == "run"]
        if len(matching) != 1:
            raise ValueError(f"Zielrennen {key} fehlt oder ist doppelt im konkreten Plan")


def progression_roadmap(plan: dict[str, Any], upcoming: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    rows = []
    for index, phase in enumerate(load_json(SEASON_FILE, {}).get("phases", [])):
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
    if plan.get("generated"):
        return [{"level": "info", "text": "Diese Woche ist noch ein automatisch erzeugter Planrahmen aus dem Jahresplan; konkrete Einheiten werden später geplant."}]
    start = parse_iso(plan.get("week_start", ""))
    end = parse_iso(plan.get("week_end", ""))
    current = next((item for item in weekly if item["week_start"] == (start.isoformat() if start else "")), None)
    previous = next((item for item in weekly if start and item["week_start"] == (start - timedelta(days=7)).isoformat()), None)
    week_activities = [item for item in activities if item.get("sport") in {"run", "bike"} and start and end and (d := parse_iso(item.get("date", ""))) and start <= d <= end]
    warnings: list[dict[str, str]] = []
    actual_hard_dates = sorted(
        d for item in activities
        if item.get("sport") in {"run", "bike"} and classify_intensity(item) == "hard"
        and start and end and (d := parse_iso(item.get("date", "")))
        and start - timedelta(days=1) <= d <= end
    )
    for first, second in zip(actual_hard_dates, actual_hard_dates[1:]):
        if second >= start and (second - first).days <= 1:
            warnings.append({"level": "warning", "text":
                f"Harte Ausdauerreize am {first:%d.%m.} und {second:%d.%m.} dokumentiert. Erholung priorisieren; künftig mindestens einen lockeren Tag dazwischen planen."})
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
    source_weeks = complete_plan_weeks(source_weeks)
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
        "season": load_json(SEASON_FILE, {}),
        "header": {
            "title": "Laufcoach Dashboard",
            "goal": "5 km sub 17 im Juni 2027",
            "phase": plan.get("phase", "Keine Phase hinterlegt"),
            "focus": plan.get("focus", ""),
            "next_milestone": plan.get("next_milestone", "10-km-Test im Frühjahr 2027"),
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
    template = (ROOT / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")
    return template.replace("__DASHBOARD_DATA__", payload)


def main() -> int:
    ensure_structure()
    print("Laufcoach Dashboard Build")
    print("-------------------------")
    plan = load_plan(PLAN_FILE)
    upcoming = load_json(UPCOMING_FILE, {"weeks": []})
    if not isinstance(upcoming, dict):
        print(f"WARNUNG: {UPCOMING_FILE.relative_to(ROOT)} muss ein JSON-Objekt enthalten; leerer Ausblick verwendet.")
        upcoming = {"weeks": []}
    source_weeks = [plan, *upcoming.get("weeks", [])]
    validate_plan_horizon(source_weeks)
    validate_season_plan(source_weeks, load_json(SEASON_FILE, {}))
    imported = import_all()
    for warning in imported["warnings"]:
        print(f"WARNUNG: {warning}")
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
