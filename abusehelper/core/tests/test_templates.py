import unittest

from .. import templates, events


class TestTemplate(unittest.TestCase):
    def test_basic_format_errors(self):
        self.assertRaises(templates.TemplateError, templates.Template, '%(x)')
        self.assertRaises(templates.TemplateError, templates.Template, '%(x)d')
        self.assertRaises(templates.TemplateError, templates.Template, '%(x)s')


class TestConst(unittest.TestCase):
    def test_extra_parameters(self):
        self.assertRaises(templates.TemplateError, templates.Template, "%(const, a)s", const=templates.Const("test"))

    def test_const_formatting(self):
        template = templates.Template("This is a %(const)s!", const=templates.Const("test"))
        self.assertEqual("This is a test!", template.format(None, []))


class TestEvent(unittest.TestCase):
    def test_missing_parameter(self):
        self.assertRaises(templates.TemplateError, templates.Template, "%(event)s", event=templates.Event({}))

    def test_extra_parameters(self):
        self.assertRaises(templates.TemplateError, templates.Template, "%(event, a, b)s", event=templates.Event({}))

    def test_single_value(self):
        template = templates.Template("%(event, key)s", event=templates.Event({
            "key": "1"
        }))
        self.assertEqual("1", template.format(None, []))

    def test_multivalue(self):
        template = templates.Template("%(event, key)s", event=templates.Event({
            "key": ["1", "2"]
        }))
        self.assertTrue(template.format(None, []) in ["1, 2", "2, 1"])

    def test_no_value(self):
        template = templates.Template("%(event, key)s", event=templates.Event({}))
        self.assertEqual("", template.format(None, []))


class TestCSVFormatter(unittest.TestCase):
    def test_csv_formatting(self):
        template = templates.Template("Events:\r\n%(csv, |, a, b, c)s", csv=templates.CSVFormatter())
        event_list = [
            events.Event(a="1", b="2", c="3"),
            events.Event(a="4", b="5"),
            events.Event(a="6", c="7")
        ]
        self.assertEqual(
            template.format(None, event_list),
            u"Events:\r\n" +
            u"a|b|c\r\n" +
            u"1|2|3\r\n" +
            u"4|5|\r\n" +
            u"6||7\r\n")

    def test_csv_errors(self):
        self.assertRaises(templates.TemplateError, templates.Template, '%(csv)s', csv=templates.CSVFormatter())
        self.assertRaises(templates.TemplateError, templates.Template, '%(csv, abc)s', csv=templates.CSVFormatter())


class TestAttachZip(unittest.TestCase):
    def test_attach_zip_filenames(self):
        # Automatically add the .zip extension unless .zip extension is there already.
        # This logic is case-insensitive.

        formatter = templates.AttachZip(templates.CSVFormatter())

        template = templates.Template("%(attach_zip, events.csv, |)s", attach_zip=formatter)
        parts = []
        template.format(parts, [])
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "events.csv.zip")

        template = templates.Template("%(attach_zip, events.csv.zip, |)s", attach_zip=formatter)
        parts = []
        template.format(parts, [])
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "events.csv.zip")

        template = templates.Template("%(attach_zip, events.csv.ZIP, |)s", attach_zip=formatter)
        parts = []
        template.format(parts, [])
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "events.csv.ZIP")


class TemplateRegressionTests(unittest.TestCase):
    def test_csv_formatter_must_accept_comma_separator(self):
        template = templates.Template(
            '%(csv, ",", column_name)s',
            csv=templates.CSVFormatter())
        self.assertEqual("column_name", template.format(None, []).rstrip())
