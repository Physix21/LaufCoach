# Scripts

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

Plan- und Kalenderprüfungen mit synthetischen Daten (für JavaScript ist Node.js
erforderlich; das Dashboard selbst benötigt weiterhin nur Python und Browser):

```powershell
python -m unittest scripts.test_build_dashboard scripts.test_import_garmin_csv
node --test scripts/test_dashboard.js
```
