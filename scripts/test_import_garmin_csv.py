import unittest

from scripts.import_garmin_csv import clean_number


class CleanNumberTests(unittest.TestCase):
    def test_power_thousands_separator_is_not_decimal(self) -> None:
        self.assertEqual(clean_number("1,621", grouped_thousands=True), 1621.0)

    def test_decimal_comma_remains_supported_by_default(self) -> None:
        self.assertEqual(clean_number("1,621"), 1.621)


if __name__ == "__main__":
    unittest.main()
