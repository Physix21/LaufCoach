"""Planprüfung mit synthetischen Einheiten, ohne persönliche Trainingsdaten."""

import copy
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dashboard import complete_plan_weeks, create_warnings, match_plan, render_html, summarize_weeks, validate_plan_horizon, validate_season_plan


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

    def test_explicit_assignment_cannot_be_taken_by_an_earlier_session(self):
        plan = week(date(2030, 12, 23))
        first = plan["planned_sessions"][0]
        first["priority"] = 1
        second = {**first, "id": "confirmed", "priority": 2, "status": "completed",
                  "completed_activity_id": "anonymous-1"}
        plan["planned_sessions"].append(second)
        activity = {"activity_id": "anonymous-1", "date": "2030-12-24", "sport": "run",
                    "session_name": "Testlauf", "duration_min": 30}
        sessions, unmatched = match_plan(plan, [activity])
        self.assertNotIn("matched_activity_id", sessions[0])
        self.assertEqual(sessions[1]["matched_activity_id"], "anonymous-1")
        self.assertEqual(unmatched, [])

    def test_actual_bike_and_run_load_includes_consecutive_days(self):
        plan = week(date(2030, 12, 23))
        activities = [{"sport": "bike", "date": "2030-12-22", "session_name": "Schwelle", "duration_min": 40},
                      {"sport": "run", "date": "2030-12-23", "session_name": "Intervalle", "duration_min": 30},
                      {"sport": "bike", "date": "2030-12-25", "session_name": "Locker", "duration_min": 50}]
        weekly = summarize_weeks(activities, plan)
        self.assertEqual(weekly[-1]["total_duration_min"], 80)
        warnings = create_warnings(plan, [], activities, weekly)
        self.assertTrue(any("22.12." in warning["text"] and "23.12." in warning["text"] for warning in warnings))

    def test_embedded_data_cannot_end_script(self):
        html = render_html({"title": "</script><script>bad()</script>"})
        self.assertNotIn("</script><script>bad()", html)
        self.assertIn("<\\/script>", html)

    def test_inconsistent_segment_times_rejected(self):
        self.plans[1]["planned_sessions"][0]["duration_components_min"] = {"warmup":10, "main":30, "cooldown":5}
        with self.assertRaisesRegex(ValueError, "Teilzeiten"):
            validate_plan_horizon(self.plans, self.today)

    def test_full_season_includes_goals_and_checks_far_future(self):
        plans = [week(date(2030,12,23) + timedelta(weeks=i)) for i in range(8)]
        plans[3]["planned_sessions"][0]["race_distance_km"] = 10
        plans[7]["planned_sessions"][0]["race_distance_km"] = 5
        season = {"plan_start":"2030-12-23", "plan_end":"2031-02-16",
                  "test_goal":{"date":"2031-01-14", "distance_km":10},
                  "primary_goal":{"date":"2031-02-11", "distance_km":5}}
        validate_season_plan(plans, season)
        with self.assertRaisesRegex(ValueError, "Konkreter Trainingsplan fehlt"):
            validate_season_plan(plans[:4] + plans[5:], season)
        wrong = copy.deepcopy(plans)
        wrong[-1]["planned_sessions"][0]["race_distance_km"] = 10
        with self.assertRaisesRegex(ValueError, "Zielrennen"):
            validate_season_plan(wrong, season)
        plans[5]["planned_sessions"][0]["main_set"] = ""
        with self.assertRaisesRegex(ValueError, "main_set"):
            validate_season_plan(plans, season)


if __name__ == "__main__":
    unittest.main()
