"""Planprüfung mit synthetischen Einheiten, ohne persönliche Trainingsdaten."""

import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dashboard import complete_plan_weeks, render_html, validate_plan_horizon


def week(start):
    return {
        "week_start": start.isoformat(),
        "week_end": (start + timedelta(days=6)).isoformat(),
        "planned_sessions": [{
            "id": start.isoformat(), "type": "run", "title": "Testlauf",
            "scheduled_date": (start + timedelta(days=1)).isoformat(),
            "target_duration_min": 30, "warmup": "10 min", "main_set": "15 min",
            "recovery": "Keine", "cooldown": "5 min", "target_pace": "Locker",
            "alternatives": "Rad statt Lauf",
        }],
    }


class PlanHorizonTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2030, 12, 29)
        self.plans = [week(date(2030, 12, 23)), week(date(2030, 12, 30))]

    def test_two_concrete_weeks_across_year_boundary(self):
        validate_plan_horizon(self.plans, self.today)
        self.assertEqual(len(complete_plan_weeks(self.plans)), 2)

    def test_missing_next_week_rejected(self):
        with self.assertRaisesRegex(ValueError, "2030-12-30"):
            validate_plan_horizon(self.plans[:1], self.today)

    def test_monday_requires_new_following_week(self):
        with self.assertRaisesRegex(ValueError, "2031-01-06"):
            validate_plan_horizon(self.plans, date(2030, 12, 30))

    def test_generic_frame_is_not_a_concrete_plan(self):
        self.plans[1]["generated"] = True
        with self.assertRaisesRegex(ValueError, "Konkreter Trainingsplan fehlt"):
            validate_plan_horizon(self.plans, self.today)

    def test_invalid_or_incomplete_sessions_rejected(self):
        for field, value in [("scheduled_date", "2031-01-10"), ("main_set", ""), ("target_duration_min", 0), ("alternatives", "")]:
            with self.subTest(field=field):
                plans = copy.deepcopy(self.plans)
                plans[1]["planned_sessions"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_plan_horizon(plans, self.today)

    def test_duplicate_week_rejected(self):
        with self.assertRaisesRegex(ValueError, "Doppelte Planwoche"):
            complete_plan_weeks([*self.plans, self.plans[0]])

    def test_embedded_data_cannot_end_script(self):
        html = render_html({"title": "</script><script>bad()</script>"})
        self.assertNotIn("</script><script>bad()", html)
        self.assertIn("<\\/script>", html)


if __name__ == "__main__":
    unittest.main()
