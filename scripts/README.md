# Scripts

## Dashboard bauen

Aus dem Projektordner:

```powershell
python scripts/build_dashboard.py
```

Das Skript importiert zuerst Garmin-CSVs mit `import_garmin_csv.py` und erzeugt
anschließend alle verarbeiteten Tabellen sowie `dashboard/index.html`. Unter Windows
führt `update_dashboard.bat` denselben Ablauf per Doppelklick aus.

Nur den Garmin-Import ausführen:

```powershell
python scripts/import_garmin_csv.py
```

Mit `--force` werden alle Rohdateien erneut geparst. Das ist vor allem nach einer
Änderung der Parserlogik nützlich; manuelle `rpe`- und `notes`-Werte bleiben erhalten.
