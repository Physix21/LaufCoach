import unittest

from scripts.import_garmin_csv import clean_number, find_column, parse_date


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
