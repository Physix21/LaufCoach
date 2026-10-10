# Scripts

## Garmin direkt herunterladen

Die lokale Umgebung wurde mit `garminconnect==0.3.17` vorbereitet. Python ab 3.12
ist erforderlich. Erneute Einrichtung: `python scripts/setup_garmin.py`.
Umgebung und Zugangstokens liegen unter `%LOCALAPPDATA%\Laufcoach`, außerhalb
von Repository und OneDrive. Die Tokenablage erhält nur Rechte für das lokale
Benutzerkonto. Passwort und MFA-Code werden verdeckt und ausschließlich lokal eingegeben.

1. Einmal `garmin_login.bat` öffnen und anmelden, gegebenenfalls mit MFA.
2. Danach `sync_garmin.bat` öffnen; lädt Lauf- und Radaktivitäten der letzten
   30 Tage einschließlich Zwischenzeiten. Alternativ kann der Laufcoach dieses
   Skript nach eingerichteter Anmeldung selbst aufrufen.
3. Neue Dateien anschließend vom Laufcoach auswerten lassen. Der Abruf allein
   ändert weder Trainingsstatus noch Plan und veröffentlicht nichts.

Abweichender Zeitraum:

```powershell
& "$env:LOCALAPPDATA\Laufcoach\venv\Scripts\python.exe" scripts/garmin_sync.py sync --since 2026-10-01
```

Der Client verwendet inoffizielle Garmin-Webdienste. Ein echter Kontologin und
Download sind noch nicht geprüft. [Quellen und Grenzen](../plans/garmin_sync_recherche.md).
Kein Passwort im Chat oder Repository hinterlegen. Für erneute Anmeldung wieder
`garmin_login.bat` verwenden. Es ist kein Hintergrundzeitplan eingerichtet.

Downloads bleiben unverändert in `data/raw/garmin/csv/`; ergänzende
`.metadata.json`-Dateien liefern Datum, Sportart und Titel. Beide Dateitypen sind
von Git ausgeschlossen. Der Importer berücksichtigt Änderungen der Metadaten.
Metrische Kontoeinstellungen sowie CSV-Distanz und Dauer werden vor Ablage mit
den Aktivitätsmetadaten verglichen. Vorhandene Rohdateien werden nicht ersetzt.
Garmin-IDs verhindern erneute Downloads. Mögliche Dubletten alter manueller
Exporte werden anhand Datum, Sportart, Distanz und Dauer ausgelassen und gemeldet;
sie gelten nicht automatisch als bestätigte Zuordnung. Bei zwei tatsächlich
verschiedenen, nahezu identischen Einheiten ist eine manuelle Prüfung nötig.
Maximal 200 Aktivitäten pro Aufruf; beim Seitenlimit wird Unvollständigkeit gemeldet.
Einige Kraft-/Schwimmformate sind ausdrücklich nicht Teil dieses CSV-Abrufs.

Anonymisierte Prüfungen ohne Netzwerk:

```powershell
python -m unittest scripts.test_garmin_sync scripts.test_import_garmin_csv
```

## Dashboard bauen

Aus dem Projektordner:

```powershell
python scripts/build_dashboard.py
```

Das Skript importiert zuerst Garmin-CSVs mit `import_garmin_csv.py` und erzeugt
anschließend alle verarbeiteten Tabellen sowie `dashboard/index.html`. Unter Windows
führt `update_dashboard.bat` denselben Ablauf per Doppelklick aus.

Wenn verstrichene Zeit und Bewegungszeit deutlich voneinander abweichen, verwendet
die Auswertung die Bewegungszeit und -geschwindigkeit. Längere Pausen werden dadurch
nicht als aktive Trainingszeit gezählt.

Nur den Garmin-Import ausführen:

```powershell
python scripts/import_garmin_csv.py
```

Mit `--force` werden alle Rohdateien erneut geparst. Das ist vor allem nach einer
Änderung der Parserlogik nützlich; manuelle `rpe`- und `notes`-Werte bleiben erhalten.

Parser-Tests ausführen:

```powershell
python -m unittest scripts.test_import_garmin_csv
```

## Darstellung und Planprüfung

`dashboard_template.html` enthält die Seitenstruktur, `dashboard/app.js` die
Kalenderanzeige und `dashboard/style.css` das Layout. Der Build bettet die Daten
direkt in `dashboard/index.html` ein; die Seite funktioniert weiterhin offline.

Vor einem Build müssen aktuelle und nächste Kalenderwoche in
`plans/current_week.json` beziehungsweise `plans/upcoming_plan.json` konkret
geplant sein. Datum, Gesamtdauer und Trainingsabschnitte werden geprüft. Fehlende
Pläne werden nicht durch generische Jahresplan-Einheiten ersetzt.

`plans/season_goals.json` definiert den vollständigen Zeitraum und beide Rennen.
Der Build prüft jede Woche dieses Zeitraums auf Vollständigkeit, eindeutige
Einheits-IDs, höchstens zwei harte Einheiten und Abstand harter Tage. Hinterlegte
`duration_components_min` müssen zur Gesamtdauer passen; normale Läufe unter der
Woche dürfen die verfügbare Stunde nicht überschreiten. Beide Zielrennen müssen
am jeweiligen Termin mit `race_distance_km` vorhanden sein. Diese Renndistanz
ist von `target_distance_km` inklusive Ein- und Auslaufen getrennt.

Die JSON-Wochen sind redaktionell gepflegte Quelldaten und werden beim Build
nicht neu generiert. Änderungen aus Aktivitätsanalysen bleiben so erhalten.
Beim Wochenwechsel die alte aktuelle Woche in `upcoming_plan.json` bewahren,
die neue aktuelle Woche daraus nach `current_week.json` verschieben und
Duplikate vermeiden. Nach Saisonende den Zeitraum und die Ziele aktualisieren.

Die JavaScript-Prüfungen decken neben Kalendergrenzen auch alle Navigationswege,
die Sprünge zu beiden Rennen und die sichtbaren Voraussetzungen/Ersatzvorgaben ab.

Plan- und Kalenderprüfungen mit synthetischen Daten (für JavaScript ist Node.js
erforderlich; das Dashboard selbst benötigt weiterhin nur Python und Browser):

```powershell
python -m unittest scripts.test_build_dashboard scripts.test_import_garmin_csv
node --test scripts/test_dashboard.js
```
