# Laufcoach – Projekt sub 17 auf 5 km

Die dauerhafte sportwissenschaftliche Evidenzbasis mit Quellen, Grenzen und konkreten Coachingregeln liegt in [`wissenschaftliche_grundlagen_5km.md`](wissenschaftliche_grundlagen_5km.md). Sie wird vor neuen mehrmonatigen Trainingsblöcken und bei relevanter neuer Evidenz überprüft.

Ziel: Im Juni 2027 5 km auf der Straße unter 17:00 Minuten laufen.

Dieses Projekt dient als lokales Trainingstagebuch und Planungsordner.  
ChatGPT/Codex soll als Laufcoach genutzt werden, um Trainingsdaten auszuwerten, Wochen zu planen und den Plan dynamisch anzupassen.

## Aktueller Stand

- Zielmonat: Juni 2027
- Zielstrecke: 5 km Straße
- Zielzeit: sub 17:00
- Zielpace: 3:24 min/km
- Letzter 5-km-Lauf: 18:49 min am 17.06.2026, flach, am Limit, ohne viel Training
- Frühere Bestzeit: 17:35 min im Jahr 2023
- Aktueller Laufumfang: ca. 10 km/Woche
- Aktuelle Laufhäufigkeit: 1–2 Läufe/Woche
- Zielstruktur: 2–3 Laufeinheiten, 1 Rad-HIIT, 1 Krafttraining pro Woche
- Optional: langer LIT-Lauf am Wochenende oder lockere Rennradausfahrt

## Ordnerstruktur

```text
Laufcoach/
├── README.md
├── athlete_profile.md
├── coach_instructions.md
├── annual_plan_2026_2027.md
├── plans/
│   ├── block_01_juli_2026.md
│   ├── current_week.json
│   └── upcoming_plan.json
├── logs/
│   └── training_diary_template.md
├── data/
│   ├── raw/
│   │   └── garmin/csv/
│   └── processed/          # automatisch erzeugte Tabellen und Kennzahlen
├── dashboard/
│   ├── index.html
│   ├── style.css
│   └── dashboard_data.json
└── scripts/
    ├── build_dashboard.py
    ├── import_garmin_csv.py
    └── update_dashboard.bat
```

## Arbeitsweise

1. Jede Trainingswoche wird dokumentiert.
2. Nach jeder Woche wird eine kurze Auswertung erstellt.
3. Der nächste Wochenplan wird auf Basis von Belastung, Gefühl, Schlaf, Stress, Beschwerden und Leistungsdaten angepasst.
4. Priorität hat das Ziel sub 17 im Juni 2027, aber ohne unnötiges Verletzungsrisiko.

## Dashboard aktualisieren

Das Dashboard läuft vollständig lokal und benötigt nur Python 3.10 oder neuer. Es gibt
keinen Server und keine zusätzlichen Python-Pakete.

1. Garmin Connect öffnen und die abgeschlossene Aktivität als CSV exportieren.
2. Die CSV nach dem Aktivitätsdatum benennen, bevorzugt `04072026.csv` für den
   04.07.2026. Eindeutige Zusätze sind erlaubt, zum Beispiel
   `04072026_intervalle.csv`. Alternativ wird auch `2026-07-04_run_intervalle.csv`
   erkannt. Enthält der Garmin-Export selbst keine Sportart, einen eindeutigen Zusatz
   verwenden: `04072026_kickr.csv` für Rad oder `04072026_kraft.csv` für Kraft.
3. Die Datei in `data/raw/garmin/csv/` ablegen. Die Standardendung ist `.csv`;
   `.cvs` wird aus Fehlertoleranz ebenfalls erkannt.
4. `scripts/update_dashboard.bat` doppelklicken oder im Projektordner ausführen:

   ```powershell
   python scripts/build_dashboard.py
   ```

5. `dashboard/index.html` im Browser öffnen oder die bereits geöffnete Seite neu
   laden.

### Dashboard auf dem Smartphone öffnen

Nach erfolgreichem GitHub-Pages-Deployment ist das Dashboard öffentlich unter
<https://physix21.github.io/LaufCoach/> erreichbar.

PC und Smartphone müssen sich im selben vertrauenswürdigen WLAN befinden. Im
Projektordner auf dem PC starten:

```powershell
python -m http.server 8000 --bind 0.0.0.0
```

Die lokale IPv4-Adresse des PCs steht unter Windows in der Ausgabe von `ipconfig`.
Auf dem Smartphone anschließend `http://<IPv4-Adresse>:8000/dashboard/` öffnen,
zum Beispiel `http://192.168.1.25:8000/dashboard/`. Den Server danach mit
`Strg+C` beenden. Der Zugriff funktioniert nur, solange der PC und der Server
laufen; Port 8000 sollte nicht im Router für das Internet freigegeben werden.

Der Build importiert nur neue oder inhaltlich geänderte Dateien. Die Importhistorie
liegt in `data/processed/imported_files.json`. Danach werden `activities.csv`,
`splits.csv`, `weekly_summary.csv`, die Kennzahlen und das statische Dashboard neu
erzeugt. Bereits manuell in `activities.csv` ergänzte Werte für `rpe` und `notes`
bleiben bei einem erneuten Import derselben Aktivität erhalten.

### Plan und Garmin-Spalten

Die aktuelle Woche wird in `plans/current_week.json` gepflegt; weitere Wochen stehen
in `plans/upcoming_plan.json`. Diese JSON-Dateien sind die einzige Planquelle des
Dashboards.

Der Import erkennt deutsche und englische Varianten für Datum, Sportart, Titel,
Dauer/Zeit, Distanz, Pace, Geschwindigkeit, Herzfrequenz, Leistung, Höhenmeter,
Training Effect, RPE und Notizen. Garmin-Rundenexporte mit `Runden`/`Lap` und einer
Zeile `Übersicht`/`Summary` werden als eine Aktivität plus einzelne Splits gelesen.
Unbekannte Spalten werden ignoriert. Fehlen Datum oder Titel im CSV, stammen sie aus
dem Dateinamen beziehungsweise – für bereits dokumentierte Altdaten – aus dem
Trainingstagebuch. Kann kein Datum erkannt werden, verwendet der Import mit einer
Warnung das Änderungsdatum der Datei. Kann keine Sportart erkannt werden, wird mit
Warnung `run` angenommen; ein Zusatz wie `_kickr` oder `_kraft` verhindert diese
Mehrdeutigkeit.

`rpe` und `notes` sind freiwillige Felder. Sie können bei Bedarf direkt in
`data/processed/activities.csv` ergänzt werden. Rohdaten unter `data/raw/garmin/`
werden nie verändert.

### Automatische Coach-Hinweise

Ausgewertet und mit dem Wochenplan abgeglichen werden ausschließlich Laufeinheiten.
Rad- und Krafteinheiten bleiben im Plan sichtbar, erhalten aber keinen Status und
fließen nicht in Umfang, Intensitätsverteilung oder Coach-Hinweise ein. Dafür müssen
keine Garmin-Dateien exportiert werden.

Die Warnregeln sind bewusst einfach und im Build-Skript zentral definiert:

- mehr als zwei absolvierte oder geplante harte Laufeinheiten pro Woche
- harte Laufeinheiten an direkt aufeinanderfolgenden Tagen
- mehr als 20 % Laufumfangssteigerung gegenüber einer nicht leeren Vorwoche
- mindestens zwei Einheiten mit RPE 9 oder höher
- Beschwerdebegriffe in den freiwilligen Notizen
- noch kein Lauf in einer bereits begonnenen Planwoche
- offene Einheit mit Priorität 1

RPE hat bei der Intensitätsklassifikation Vorrang. Ohne RPE werden eindeutige Begriffe
wie `Intervalle`, `400`, `1000`, `Schwelle`, `Wettkampf` oder `HIIT` verwendet. Fehlt
auch diese Information, klassifiziert das Dashboard konservativ als LIT.
