# Garmin Connect: lokale Übernahme neuer Aktivitäten

**Stand:** 10.10.2026
**Umfang:** Quellen- und Codeprüfung, lokales Abrufskript mit synthetischen Tests. Am 10.10.2026 nach lokaler Anmeldung erfolgreicher realer Kontozugriff und CSV-Abruf. Bedienung in [Scripts](../scripts/README.md).

## Empfehlung

Das implementierte lokale Skript ermittelt neue Aktivitäten und lädt deren Zwischenzeiten-CSV nach Formatprüfung herunter. Der bestehende Importer verarbeitet sie beim anschließenden Coaching-/Dashboard-Schritt. Die verwendete Bibliothek ist `python-garminconnect` 0.3.17. Der erste reale Abruf hat funktioniert: sechs Downloads, davon nach Rundenvergleich vier bekannte Einheiten mit korrigierbarem Datum und zwei zuvor fehlende Aktivitäten. Neun weitere mögliche Dubletten wurden bereits anhand der Zusammenfassungen ausgelassen.

## Verfügbare Wege

| Weg | Befund | Eignung für dieses Projekt |
|---|---|---|
| Offizielle Garmin Connect Developer API | Garmin nennt ausdrücklich Unternehmensnutzung und ein Bewerbungs-/Freigabeverfahren; OAuth 2.0 wird unterstützt. | Kein öffentlich angebotener unkomplizierter Zugang für dieses private Einzelkonto. [Garmin FAQ](https://developer.garmin.com/gc-developer-program/program-faq/) |
| Lokaler Python-Client | `python-garminconnect` ist ein inoffizieller Client für Garmin-Webdienste. Seit Version 0.3.0 nutzt er eigene Authentifizierung und neue Tokens. | Bevorzugter Ansatz für einen kleinen lokalen Abruf. [Projektbeschreibung](https://github.com/cyberjunky/python-garminconnect) |
| Garth | Der Maintainer hat Garth eingestellt: Garmin änderte den Login, neue Anmeldungen funktionieren laut Projekt nicht mehr. Bestehende Tokens können vorübergehend weiter funktionieren. | Für eine neue Einrichtung ungeeignet. [Garth-Projektstatus](https://github.com/matin/garth) |
| Browserexport | Die bisherige manuelle Zwischenzeiten-CSV passt zum vorhandenen Importweg. | Rückfalloption bei Login- oder Schnittstellenproblemen; eine Browserautomatisierung wäre stärker von der Oberfläche abhängig. |

PyPI weist **garminconnect 0.3.17 vom 29.09.2026** und **Python ab 3.12** aus. Lokal wurde Python 3.12.2 festgestellt. Bei Umsetzung eine geprüfte Version festschreiben und Änderungen gezielt übernehmen. [PyPI-Paket](https://pypi.org/project/garminconnect/)

## Zwischenzeiten sind direkt abrufbar

Der geprüfte [Bibliotheksquellcode](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/__init__.py) bietet:

| Zweck | Methode / Ergebnis |
|---|---|
| Neueste Aktivitäten | `get_activities(start=0, limit=20)`; bei Bedarf seitenweise weiterlesen |
| Zwischenzeiten-CSV | `download_activity(str(activity_id), Garmin.ActivityDownloadFormat.CSV)`; rohe CSV-Bytes |
| Originaldatei | Gleiche Methode mit `ORIGINAL`; ZIP-Inhalt, typischerweise mit FIT-Datei, kein direktes FIT-Enum für den Download |
| TCX | Gleiche Methode mit `TCX`; für den bestehenden Importer wäre ein zusätzlicher Parser erforderlich |
| Runden als JSON | `get_activity_splits(str(activity_id))` |
| Ergänzende Rundenformen | `get_activity_typed_splits(...)` und `get_activity_split_summaries(...)` |

Der CSV-Aufruf verwendet `/download-service/export/csv/activity/{id}`; seine Dokumentation benennt ausdrücklich eine CSV der Splits. JSON-Runden kommen über `/activity-service/activity/{id}/splits`. Das sind vorhandene interne Webdienstpfade, keine zugesicherte offizielle Privatkunden-API. Verfügbarkeit, metrische Einheiten und die deutsche Spaltenvariante wurden beim ersten realen Download geprüft.

## Anschluss an den vorhandenen Importer

Die folgenden Punkte stammen aus der lokalen Prüfung von `scripts/import_garmin_csv.py`, `scripts/build_dashboard.py` und `.gitignore`:

- `data/raw/garmin/csv/` wird bereits eingelesen und von Git ausgeschlossen. Downloads unverändert dort ablegen, vorhandene Rohdateien nicht überschreiben.
- Der Parser erkennt deutsche und englische Spalten, numerische Runden und Summenzeilen. Er erwartet Distanzen in km und Zeiten in Sekunden beziehungsweise `min:s`/`h:min:s`. Ein metrisches Konto ist vor dem Import zu verifizieren; Meilen dürfen nicht als km importiert werden.
- Neue Dateien sollten aus geprüften Aktivitätsmetadaten benannt werden, beispielsweise `2026-10-10_run_activity_12345678901.csv`. Der Name liefert Datum, Sportart und die echte Garmin-ID. Für Rad `cycling` verwenden: Das isolierte Wort `bike` wird erkannt, `run` allein derzeit nicht als explizite Sportart. Bei Bedarf Metadaten in einer separaten Zuordnung übergeben.
- Der Importer erkennt Garmin-IDs im Muster `activity_12345678...`; frühere manuelle Dateien können stattdessen lokale Hash-IDs besitzen. Beim ersten Sync müssen Datum, Distanz und Dauer mit vorhandenen Einträgen abgeglichen und eindeutige Zuordnungen bestätigt werden, damit dieselbe Einheit nicht doppelt erscheint. Mehrere Aktivitäten am selben Tag bleiben möglich.
- CSVs enthalten gegebenenfalls kein Datum oder keinen Titel. Das Dateidatum ist dafür kein verlässlicher Ersatz; die Aktivitätsliste liefert den notwendigen Kontext.
- Zusätzliche JSON-Dateien wären außerhalb der bisher ausgeschlossenen CSV-/FIT-/TCX-Pfade nicht automatisch geschützt. Einen neuen lokalen Metadatenordner ausdrücklich ausschließen oder Metadaten außerhalb des Repositorys speichern.

## Minimale lokale Einrichtung

1. Eine eigene Python-Umgebung und ein kleines Skript ausschließlich mit lesenden Aktivitätsmethoden vorbereiten.
2. Die erste Anmeldung durch den Nutzer lokal ausführen: E-Mail, verdeckte Passworteingabe und gegebenenfalls MFA-Code. Das Projektbeispiel verwendet `getpass`, `prompt_mfa` und `login(tokenstore)`; spätere Aufrufe können gespeicherte Tokens wiederverwenden. [Authentifizierungsbeispiel](https://github.com/cyberjunky/python-garminconnect/blob/master/example.py)
3. Als Tokenablage beispielsweise `%LOCALAPPDATA%\Laufcoach\Garmin` wählen, mit Zugriff nur für das Benutzerkonto. Das liegt außerhalb von Repository und OneDrive-Arbeitsordner. Kein Passwort im Chat, in Skriptargumenten, `.env` im Projekt oder Git speichern. Tokens sind ebenfalls Zugangsdaten und gehören weder in Ausgaben noch ins öffentliche Dashboard.
4. Bei Abruf aktuelle Aktivitäts-IDs mit einer lokalen Erfolgsliste vergleichen, unbekannte Aktivitäten herunterladen, CSV und Metadaten prüfen und erst nach erfolgreichem Import als erledigt markieren. Begrenzte Seitenzahl und kleine Abrufmengen vorsehen.
5. Danach den vorhandenen Dashboard-Build ausführen. Veröffentlichung enthält ausschließlich die freigegebenen Auswertungen; Rohdaten und Tokens bleiben lokal. Coachingbewertung und Planänderungen erfolgen weiterhin anhand der neu importierten Einheiten.

Die neue Token-Datei heißt `garmin_tokens.json`. Alte Garth-Dateien `oauth1_token.json`/`oauth2_token.json` sind nicht direkt übernehmbar. Ein erneuter lokaler Login ist dann nötig. [Migrationshinweis des Projekts](https://github.com/cyberjunky/python-garminconnect#upgrading-from-02x-garth)

## Konkrete Betriebsgrenzen

Garmin kann interne Dienste und Anmeldung ändern. MFA, abgelaufene Tokens, HTTP 403 und HTTP 429 können einen Abruf stoppen; das Bibliotheksbeispiel behandelt Authentifizierungs-, Zugriffs- und Ratenfehler getrennt. Bei diesen Fehlern anhalten und den Grund melden, statt wiederholt Passwörter zu versuchen. [Fehlerbehandlung im Beispiel](https://github.com/cyberjunky/python-garminconnect/blob/master/example.py)

Ein lokales Skript läuft nur, wenn der Rechner und die Anmeldung verfügbar sind. Abruf auf Wunsch ist der kleinste sinnvolle Einstieg. Ein späterer Zeitplan über die Windows-Aufgabenplanung ist eine separate Erweiterung. Der erste reale Download und die Rundenübernahme sind geprüft; künftige Formatänderungen können neue Anpassungen erforderlich machen.
