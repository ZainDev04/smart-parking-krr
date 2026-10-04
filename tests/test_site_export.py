"""The website's scenario clock and added drivers (krr/site_export.py)."""

import unittest

from krr.site_export import morning_rush_at


def decisions(result):
    return {q["driver"]: q["allocated"] for q in result["requests"]}


class ClockTest(unittest.TestCase):
    def test_report_run_unchanged(self):
        got = decisions(morning_rush_at(20261002, 10))
        self.assertEqual({d for d, ok in got.items() if ok}, {"ahmed", "sara", "bilal"})

    def test_night_closes_every_zone(self):
        self.assertFalse(any(decisions(morning_rush_at(20261002, 23)).values()))

    def test_arrivals_never_wrap_midnight(self):
        times = [q["time"] for q in morning_rush_at(20261002, 1)["requests"]]
        self.assertEqual(times, sorted(times))
        self.assertGreaterEqual(min(times), 2200)


class AddedDriverTest(unittest.TestCase):
    BASE = {"role": "student", "vehicle": "car", "badge": False, "permit": "valid",
            "space": "s_a4", "time": 930}

    def add(self, **kw):
        return decisions(morning_rush_at(20261002, 10, [{**self.BASE, "name": "omar", **kw}]))

    def test_valid_student_gets_free_bay(self):
        self.assertTrue(self.add(vehicle="motorbike")["omar"])

    def test_permit_states(self):
        for permit in ("expired", "not_started", "none"):
            self.assertFalse(self.add(space="s_a1", permit=permit)["omar"], permit)

    def test_badge_holder_who_came_first_wins(self):
        got = self.add(space="s_a1", badge=True, time=905)
        self.assertTrue(got["omar"])
        self.assertFalse(got["sara"])

    def test_bad_input_rejected(self):
        for bad in ({"name": "ali"}, {"name": "A B"}, {"space": "zone_a"}, {"role": "pilot"},
                    {"time": 961}):
            with self.assertRaises(ValueError, msg=bad):
                morning_rush_at(20261002, 10, [{**self.BASE, "name": "omar", **bad}])


if __name__ == "__main__":
    unittest.main()
