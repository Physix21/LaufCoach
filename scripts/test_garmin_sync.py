"""Anonymisierte Vertragsprüfungen ohne Netzwerk oder Kontozugang."""
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import garmin_sync as sync
from scripts import import_garmin_csv as importer


CSV = b"Lap,Time,Distance,Average Pace\n1,5:00,1.00,5:00\n2,5:00,1.00,5:00\nSummary,10:00,2.00,5:00\n"
ITEM = {"activityId": 12345678901, "activityName": "Anonymer Testlauf",
        "startTimeLocal": "2030-04-02 12:00:00", "activityType": {"typeKey": "running"},
        "distance": 2000, "duration": 600, "elapsedDuration": 600, "movingDuration": 599}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.home = patch.object(sync, "local_home", return_value=self.root)
        self.home.start()
        self.addCleanup(self.home.stop)
        self.api = Mock()
        self.api.get_unit_system.return_value = "metric"
        self.api.get_activities.return_value = [dict(ITEM)]
        self.api.download_activity.return_value = CSV

    def run_sync(self, **kwargs):
        return sync.download_new(self.api, "CSV", date(2030, 4, 1), raw_dir=self.raw,
                                 existing=kwargs.pop("existing", []), **kwargs)

    def test_bytes_metadata_and_repeat_download(self):
        result = self.run_sync()
        path = self.raw / result["downloaded"][0]
        self.assertEqual(path.read_bytes(), CSV)
        activities, splits, warnings = importer.parse_file(path, {})
        self.assertEqual(activities[0]["activity_id"], str(ITEM["activityId"]))
        self.assertEqual(activities[0]["date"], "2030-04-02")
        self.assertEqual(activities[0]["session_name"], ITEM["activityName"])
        self.assertEqual(len(splits), 2)
        self.assertEqual(warnings, [])
        self.assertEqual(self.run_sync()["known"], 1)
        self.api.download_activity.assert_called_once()

    def test_imperial_account_rejected_before_network_download(self):
        self.api.get_unit_system.return_value = "statute"
        with self.assertRaisesRegex(sync.SyncError, "metrischen"):
            self.run_sync()
        self.api.download_activity.assert_not_called()

    def test_wrong_distance_or_duration_never_reaches_raw_directory(self):
        for payload in (CSV.replace(b"2.00", b"1.24"), CSV.replace(b"10:00", b"20:00"), b"<html>login</html>"):
            with self.subTest(payload=payload):
                self.api.download_activity.return_value = payload
                with self.assertRaises(sync.SyncError):
                    self.run_sync()
                self.assertEqual(list(self.raw.glob("*.csv")), [])

    def test_manual_duplicate_is_reported_without_claiming_identity(self):
        existing = [{"activity_id": "local-anonymous", "date": "2030-04-02", "sport": "run",
                     "distance_km": "2.0", "duration_min": "10.0"}]
        result = self.run_sync(existing=existing)
        self.assertEqual(len(result["possible_duplicates"]), 1)
        self.assertEqual(result["known"], 0)
        self.api.download_activity.assert_not_called()

    def test_different_session_on_same_day_is_not_deduplicated(self):
        existing = [{"activity_id": "local-anonymous", "date": "2030-04-02", "sport": "run",
                     "distance_km": "4.0", "duration_min": "20.0"}]
        self.assertEqual(len(self.run_sync(existing=existing)["downloaded"]), 1)

    def test_api_failure_leaves_no_success_file(self):
        self.api.download_activity.side_effect = ConnectionError("synthetic")
        with self.assertRaises(ConnectionError):
            self.run_sync()
        self.assertEqual(list(self.raw.glob("*")), [])

    def test_resume_after_missing_metadata_preserves_raw(self):
        path = self.raw / self.run_sync()["downloaded"][0]
        path.with_suffix(".metadata.json").unlink()
        self.run_sync()
        self.assertEqual(path.read_bytes(), CSV)
        self.assertEqual(json.loads(path.with_suffix(".metadata.json").read_text())["sport"], "running")
        self.api.download_activity.assert_called_once()

    def test_pagination_limit_reports_incomplete_download(self):
        self.api.get_activities.return_value = [dict(ITEM) for _ in range(20)]
        with self.assertRaisesRegex(sync.SyncError, "Seitenlimit"):
            self.run_sync(max_pages=1)

    def test_unsupported_sport_is_not_guessed_as_run(self):
        self.api.get_activities.return_value = [{**ITEM, "activityType": {"typeKey": "swimming"}}]
        self.assertEqual(self.run_sync()["unsupported"], 1)
        self.api.download_activity.assert_not_called()


if __name__ == "__main__":
    unittest.main()
