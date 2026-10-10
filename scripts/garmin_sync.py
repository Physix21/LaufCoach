#!/usr/bin/env python3
"""Lädt Zwischenzeiten lesend herunter; Zugangsdaten bleiben außerhalb des Projekts."""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from getpass import getpass
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

if __package__:
    from . import import_garmin_csv as importer
else:
    import import_garmin_csv as importer


class SyncError(Exception):
    pass


def prompt_secret(label: str) -> str:
    print("Die Eingabe bleibt unsichtbar: Es erscheinen keine Zeichen oder Sternchen.", flush=True)
    print("Bitte eintippen und mit Enter bestaetigen.", flush=True)
    return getpass(f"{label}: ")


def local_home() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise SyncError("LOCALAPPDATA fehlt; dieses Hilfsprogramm ist für Windows eingerichtet.")
    result = (Path(base) / "Laufcoach").resolve()
    if result.is_relative_to(importer.ROOT.resolve()):
        raise SyncError("Tokenablage darf nicht im Projekt liegen.")
    return result


def secure_token_directory() -> Path:
    target = local_home() / "Garmin"
    target.mkdir(parents=True, exist_ok=True)
    # Lokales Benutzerkonto bekommt Zugriff, keine geerbten Leserechte.
    who = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], check=True,
                         capture_output=True, text=True)
    sid = next(csv.reader([who.stdout.strip()]))[1]
    if not re.fullmatch(r"S-1-[\d-]+", sid):
        raise SyncError("Windows-Benutzerkennung konnte nicht geprüft werden.")
    subprocess.run(["icacls", str(target), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"],
                   check=True, capture_output=True)
    return target


def activity_metadata(item: dict) -> dict | None:
    activity_id = str(item.get("activityId", ""))
    if not re.fullmatch(r"\d{8,}", activity_id):
        raise SyncError("Garmin lieferte eine ungültige Aktivitäts-ID.")
    day = importer.parse_date(item.get("startTimeLocal"))
    if not day:
        raise SyncError(f"Aktivität {activity_id}: lokales Startdatum fehlt.")
    kind = item.get("activityType", {}).get("typeKey", "")
    if "running" in kind:
        sport = "running"
    elif "cycling" in kind or kind in {"indoor_cycling", "virtual_ride"}:
        sport = "cycling"
    else:
        return None  # Kein neuer Parser für Kraft/Schwimmen aus metadatenarmen CSVs.
    return {"activity_id": activity_id, "date": day, "sport": sport,
            "session_name": str(item.get("activityName") or ("Lauf" if sport == "running" else "Radfahrt"))}


def possible_duplicates(item: dict, metadata: dict, existing: list[dict]) -> list[str]:
    distance = float(item.get("distance") or 0) / 1000
    durations = [float(item[key]) for key in ("duration", "movingDuration", "elapsedDuration") if item.get(key)]
    if distance <= 0 or not durations:
        return []
    matches = []
    for row in existing:
        if row.get("date") != metadata["date"] or row.get("sport") != importer.sport_code(metadata["sport"]):
            continue
        if (abs(float(row.get("distance_km") or 0) - distance) <= .02
                and any(abs(float(row.get("duration_min") or 0) * 60 - duration) <= 5 for duration in durations)):
            matches.append(row["activity_id"])
    return matches


def validate_download(path: Path, metadata: dict, item: dict) -> None:
    activities, splits, _ = importer.parse_file(path, {path.name: metadata})
    if len(activities) != 1 or not splits:
        raise SyncError(f"Aktivität {metadata['activity_id']}: keine eindeutige Aktivität mit Zwischenzeiten erkannt.")
    activity = activities[0]
    expected_km = float(item.get("distance") or 0) / 1000
    actual_km = float(activity.get("distance_km") or 0)
    durations = [float(item[key]) for key in ("duration", "movingDuration", "elapsedDuration") if item.get(key)]
    actual_sec = float(activity.get("duration_min") or 0) * 60
    if expected_km <= 0 or abs(actual_km - expected_km) > max(.03, expected_km * .005):
        raise SyncError(f"Aktivität {metadata['activity_id']}: CSV-Distanz passt nicht zu den Metern der Aktivitätsliste; Einheiten/Format prüfen.")
    if not durations or not any(abs(actual_sec - duration) <= 5 for duration in durations):
        raise SyncError(f"Aktivität {metadata['activity_id']}: CSV-Dauer passt nicht zur Aktivitätsliste.")
    if activity["date"] != metadata["date"]:
        raise SyncError(f"Aktivität {metadata['activity_id']}: widersprüchliches Datum.")


def download_new(api, csv_format, since: date, *, raw_dir: Path = importer.RAW_DIR,
                 existing: list[dict] | None = None, max_pages: int = 10) -> dict:
    if str(api.get_unit_system()).lower() != "metric":
        raise SyncError("Garmin-Konto verwendet keine metrischen Einheiten; keine Dateien heruntergeladen.")
    raw_dir.mkdir(parents=True, exist_ok=True)
    if existing is None:
        existing = importer.read_table(importer.ACTIVITIES_FILE)
    known_ids = {row["activity_id"] for row in existing}
    seen = set()
    result = {"downloaded": [], "known": 0, "possible_duplicates": [], "unsupported": 0}
    exhausted = False
    for page in range(max_pages):
        items = api.get_activities(start=page * 20, limit=20)
        if not isinstance(items, list):
            raise SyncError("Unerwartetes Format der Garmin-Aktivitätsliste.")
        if not items:
            exhausted = True
            break
        for item in items:
            day = importer.parse_date(item.get("startTimeLocal"))
            if not day:
                raise SyncError("Eine Garmin-Aktivität hat kein gültiges lokales Datum.")
            if day < since.isoformat():
                continue
            metadata = activity_metadata(item)
            if metadata is None:
                result["unsupported"] += 1
                continue
            activity_id = metadata["activity_id"]
            if activity_id in seen:
                continue
            seen.add(activity_id)
            filename = f"{day}_{importer.sport_code(metadata['sport'])}_activity_{activity_id}.csv"
            destination = raw_dir / filename
            if activity_id in known_ids:
                result["known"] += 1
                continue
            if destination.exists():
                # Ein unterbrochener Lauf kann die CSV schon abgelegt haben.
                validate_download(destination, metadata, item)
                if not destination.with_suffix(".metadata.json").exists():
                    importer.write_json(destination.with_suffix(".metadata.json"), metadata)
                result["known"] += 1
                continue
            duplicates = possible_duplicates(item, metadata, existing)
            if duplicates:
                result["possible_duplicates"].append({"date": day, "garmin_id": activity_id, "existing_ids": duplicates})
                continue  # Nicht still als identisch verbuchen; bei jedem Abruf erneut prüfbar.
            payload = api.download_activity(activity_id, csv_format)
            if not isinstance(payload, bytes) or not payload:
                raise SyncError(f"Aktivität {activity_id}: Download enthält keine CSV-Bytes.")
            with tempfile.TemporaryDirectory(prefix="garmin_check_", dir=local_home()) as temporary:
                candidate = Path(temporary) / filename
                candidate.write_bytes(payload)
                validate_download(candidate, metadata, item)
            # Exklusiv anlegen: bestehende Rohdateien niemals überschreiben.
            with destination.open("xb") as handle:
                handle.write(payload)
            importer.write_json(destination.with_suffix(".metadata.json"), metadata)
            result["downloaded"].append(filename)
        # Garmin liefert neueste zuerst; Randseite vollständig bearbeiten.
        if len(items) < 20 or all(importer.parse_date(item.get("startTimeLocal")) < since.isoformat() for item in items):
            exhausted = True
            break
    if not exhausted:
        raise SyncError("Seitenlimit erreicht; Abruf unvollständig. Bereits geprüfte Downloads bleiben erhalten. Zeitraum mit --since eingrenzen.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("login", "sync"))
    parser.add_argument("--since", type=date.fromisoformat, default=date.today() - timedelta(days=30),
                        help="Frühestes lokales Aktivitätsdatum YYYY-MM-DD; Standard letzte 30 Tage")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)  # Bibliotheksantworten/Tokens nicht in Konsolenausgaben.
    try:
        from garminconnect import Garmin
        token_dir = secure_token_directory()
        if args.command == "login":
            email = input("Garmin-E-Mail (nur lokal): ").strip()
            password = prompt_secret("Garmin-Passwort")
            api = Garmin(email=email, password=password, prompt_mfa=lambda: prompt_secret("Garmin MFA-Code"), retry_attempts=1)
            api.login(str(token_dir))
            api.client.dump(str(token_dir))
            print("Lokale Anmeldung gespeichert. Das Passwort wird vom Skript nicht gespeichert.")
        else:
            if not (token_dir / "garmin_tokens.json").exists():
                raise SyncError("Lokale Anmeldung fehlt. Zuerst garmin_login.bat ausführen.")
            api = Garmin(retry_attempts=1)
            api.login(str(token_dir))
            result = download_new(api, Garmin.ActivityDownloadFormat.CSV, args.since)
            api.client.dump(str(token_dir))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("Download beendet. Neue CSVs jetzt vom Laufcoach auswerten und Status, Tagebuch und Dashboard aktualisieren lassen.")
            print("Mögliche Dubletten wurden ausgelassen und nicht als bestätigte Zuordnung gespeichert.")
        return 0
    except SyncError as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
    except ImportError:
        print("Garmin-Paket fehlt. Zuerst python scripts/setup_garmin.py ausführen.", file=sys.stderr)
    except Exception as exc:
        # Keine Serverantworten oder Exception-Texte ausgeben: können Kontodaten enthalten.
        print(f"ABBRUCH: {type(exc).__name__}. Anmeldung/Netzwerk prüfen; kein erfolgreicher Abruf bestätigt.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
