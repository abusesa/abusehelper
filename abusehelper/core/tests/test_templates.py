import unittest

from .. import templates


class TemplateRegressionTests(unittest.TestCase):
    def test_csv_formatter_must_accept_comma_separator(self):
        template = templates.Template(
            '%(csv, ",", column_name)s',
            csv=templates.CSVFormatter())
        self.assertEqual("column_name", template.format(None, []).rstrip())
