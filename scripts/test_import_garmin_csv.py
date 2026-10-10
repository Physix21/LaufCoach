import unittest
import json
from pathlib import Path
import tempfile

from scripts.import_garmin_csv import clean_number, find_column, parse_date, parse_file


class DirectExportTests(unittest.TestCase):
    def test_german_direct_export_excludes_summary_and_preserves_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "2030-04-02_run_activity_12345678901.csv"
            path.write_text("Zwischenzeit,Zeit,Distanz,Ø Pace,Ø Herzfrequenz,Max. HF,Positiver Höhenunterschied\n"
                            "1,00:05:00.000,1,0:05:00,120,135,4\n"
                            "2,00:05:10.000,1,0:05:10,122,138,5\n"
                            "Summary,00:10:10.000,2,0:05:05,121,138,9\n", encoding="utf-8")
            activities, splits, _ = parse_file(path, {})
            self.assertEqual(len(splits), 2)
            self.assertEqual(activities[0]["max_hr"], "138.0")
            self.assertEqual(activities[0]["elevation_gain_m"], "9.0")
            self.assertEqual(activities[0]["avg_pace_sec_per_km"], "305.0")

    def test_reviewed_metadata_corrects_filename_date_without_changing_local_id(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "2030-04-01_run.csv"
            path.write_text("Lap,Time,Distance\n1,5:00,1\nSummary,5:00,1\n", encoding="utf-8")
            path.with_suffix(".metadata.json").write_text(json.dumps({
                "date": "2030-04-02", "local_activity_id": "local-synthetic",
                "sport": "running", "session_name": "Anonymer Lauf"}), encoding="utf-8")
            activities, _, _ = parse_file(path, {})
            self.assertEqual(activities[0]["date"], "2030-04-02")
            self.assertEqual(activities[0]["activity_id"], "local-synthetic")


class CleanNumberTests(unittest.TestCase):
    def test_power_thousands_separator_is_not_decimal(self) -> None:
        self.assertEqual(clean_number("1,621", grouped_thousands=True), 1621.0)

    def test_decimal_comma_remains_supported_by_default(self) -> None:
        self.assertEqual(clean_number("1,621"), 1.621)


class ParseDateTests(unittest.TestCase):
    def test_compact_date_with_short_year_is_supported(self) -> None:
        self.assertEqual(parse_date("260926"), "2026-09-26")

    def test_invalid_compact_date_with_short_year_is_rejected(self) -> None:
        self.assertEqual(parse_date("320926"), "")


class ColumnSelectionTests(unittest.TestCase):
    def test_moving_time_has_a_dedicated_column(self) -> None:
        headers = ["Zeit", "Zeit in Bewegung"]
        self.assertEqual(find_column(headers, "duration"), "Zeit")
        self.assertEqual(find_column(headers, "moving_duration"), "Zeit in Bewegung")

    def test_moving_speed_has_a_dedicated_column(self) -> None:
        headers = ["Ø Geschwindigkeit", "Ø Geschwindigkeit in Bewegung"]
        self.assertEqual(find_column(headers, "speed"), "Ø Geschwindigkeit")
        self.assertEqual(find_column(headers, "moving_speed"), "Ø Geschwindigkeit in Bewegung")


if __name__ == "__main__":
    unittest.main()
