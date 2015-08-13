import time
import doctest
import calendar
import unittest

from .. import cron


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(cron))
    return tests


class TestCron(unittest.TestCase):
    def test_init_coercion(self):
        self.assertEqual(cron.Cron({
            "weekday": cron.value("sunday")
        }), cron.Cron({
            "weekday": "sunday"
        }))

        self.assertEqual(cron.Cron({
            "weekday": cron.value(0)
        }), cron.Cron({
            "weekday": 0
        }))

    def test_case_insensitivity(self):
        self.assertEqual(cron.Cron({
            "weekday": "SUNDAY",
        }), cron.Cron({
            "weekday": "sunday"
        }))

    def test_next(self):
        c = cron.Cron({
            "weekday": "sunday"
        })
        next_sunday = c.next(time.gmtime(0))
        self.assertEqual(calendar.timegm(next_sunday), 259200)

    def test_next_always_advances(self):
        c = cron.Cron({
            "weekday": "sunday"
        })
        sunday_after_that = c.next(time.gmtime(259200))
        self.assertEqual(calendar.timegm(sunday_after_that), 864000)

    def test_matches(self):
        c = cron.Cron({
            "weekday": "sunday"
        })
        self.assertFalse(c.matches(time.gmtime(0)))
        self.assertTrue(c.matches(time.gmtime(259200)))

    def test_day_or_weekday(self):
        c = cron.Cron({
            "day": 2,
            "weekday": "sunday"
        })
        next_day = c.next(time.gmtime(0))
        self.assertEqual(calendar.timegm(next_day), 86400)

        next_sunday = c.next(next_day)
        self.assertEqual(calendar.timegm(next_sunday), 259200)

    def test_year_change(self):
        c = cron.Cron(weekday="friday")
        next_year = c.next(time.gmtime(calendar.timegm((1970, 12, 31, 23, 59, 0))))
        self.assertEqual(calendar.timegm(next_year), calendar.timegm((1971, 1, 1, 0, 0, 0)))


class TestCronParsing(unittest.TestCase):
    def test_parsing_value(self):
        self.assertEqual(cron.parse("0 * * * *"), cron.Cron({
            "minute": cron.value(0)
        }))

    def test_parsing_range(self):
        self.assertEqual(cron.parse("10-20 * * * *"), cron.Cron({
            "minute": cron.range(10, 20)
        }))
        self.assertEqual(cron.parse("10-20/5 * * * *"), cron.Cron({
            "minute": cron.range(10, 20, step=5)
        }))

    def test_parsing_any(self):
        self.assertEqual(cron.parse("* * * * *"), cron.Cron({
            "minute": cron.any()
        }))
        self.assertEqual(cron.parse("*/5 * * * *"), cron.Cron({
            "minute": cron.any(step=5)
        }))

    def test_parsing_multiple(self):
        self.assertEqual(cron.parse("0,10-20/5,*/5 * * * *"), cron.Cron({
            "minute": cron.value(0).or_range(10, 20, step=5).or_any(step=5)
        }))

    def test_parsing_day_or_weekday(self):
        self.assertEqual(cron.parse("0 0 2 * *"), cron.Cron({
            "day": cron.value(2),
            "weekday": cron.any()
        }))
        self.assertEqual(cron.parse("0 0 * * sun"), cron.Cron({
            "day": cron.any(),
            "weekday": cron.value("sun")
        }))
        self.assertEqual(cron.parse("0 0 2 * sun"), cron.Cron({
            "day": cron.value(2),
            "weekday": cron.value("sun")
        }))

    def test_parsing_extra_spaces(self):
        self.assertEqual(cron.parse("1,2  3  4  *  *"), cron.parse("1,2 3 4 * *"))
        self.assertEqual(cron.parse("  1,2 3 4 * *  "), cron.parse("1,2 3 4 * *"))
        self.assertRaises(ValueError, cron.parse, "0, 1 * * *")
        self.assertRaises(ValueError, cron.parse, "0 ,1 * * *")
        self.assertRaises(ValueError, cron.parse, "0 , 1 * * *")

    def test_parsing_month_names(self):
        self.assertEqual(cron.parse("* * * jan *"), cron.parse("* * * 1 *"))
        self.assertEqual(cron.parse("* * * january *"), cron.parse("* * * 1 *"))
        self.assertEqual(cron.parse("* * * JANUARY *"), cron.parse("* * * 1 *"))

    def test_parsing_day_names(self):
        self.assertEqual(cron.parse("* * * * sun"), cron.parse("* * * * 0"))
        self.assertEqual(cron.parse("* * * * sunday"), cron.parse("* * * * 0"))
        self.assertEqual(cron.parse("* * * * SUNDAY"), cron.parse("* * * * 0"))

    def test_parsing_unknown_names(self):
        self.assertRaises(ValueError, cron.parse, "xyz * * * *")
        self.assertRaises(ValueError, cron.parse, "* xyz * * *")
        self.assertRaises(ValueError, cron.parse, "* * xyz * *")
        self.assertRaises(ValueError, cron.parse, "* * * xyz *")
        self.assertRaises(ValueError, cron.parse, "* * * * xyz")

    def test_parsing_out_of_bounds_values(self):
        self.assertRaises(ValueError, cron.parse, "61 * * * *")
        self.assertRaises(ValueError, cron.parse, "* 24 * * *")
        self.assertRaises(ValueError, cron.parse, "* * 0 * *")
        self.assertRaises(ValueError, cron.parse, "* * 32 * *")
        self.assertRaises(ValueError, cron.parse, "* * * 0 *")
        self.assertRaises(ValueError, cron.parse, "* * * 13 *")
        self.assertRaises(ValueError, cron.parse, "* * * * 7")

    def test_parsing_out_of_bounds_steps(self):
        self.assertRaises(ValueError, cron.parse, "*/0 * * * *")
        self.assertRaises(ValueError, cron.parse, "*/61 * * * *")
        self.assertRaises(ValueError, cron.parse, "*/0 * * *")
        self.assertRaises(ValueError, cron.parse, "* */25 * * *")
        self.assertRaises(ValueError, cron.parse, "* * */0 * *")
        self.assertRaises(ValueError, cron.parse, "* */32 * *")
        self.assertRaises(ValueError, cron.parse, "* * * */0 *")
        self.assertRaises(ValueError, cron.parse, "* * * */13 *")
        self.assertRaises(ValueError, cron.parse, "* * * * */0")
        self.assertRaises(ValueError, cron.parse, "* * * * */8")
