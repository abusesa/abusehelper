import time
import json
import hashlib
import itertools
from abusehelper.core.events import Event


class Timestamp(object):
    def __init__(self, header="timestamp"):
        self._header = header

    def header(self):
        return self._header

    def parse(self, timestamp, event):
        yield time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(timestamp))


class EventSum(object):
    def __init__(self, header="eventsum"):
        self._header = header

    def header(self):
        return self._header

    def parse(self, timestamp, event):
        items = []
        for item in sorted(event.items()):
            items.extend(item)

        event_string = "\xc0".join(x.encode("utf-8") for x in items)
        yield hashlib.sha1(event_string).hexdigest()


class Key(object):
    def __init__(self, key, header=None, required=False):
        self._key = key
        self._header = header
        self._required = required

    def header(self):
        if self._header is None:
            return self._key
        return self._header

    def parse(self, timestamp, event):
        values = event.values(self._key)
        if not values and not self._required:
            return [None]
        return values


class Mogrifier(object):
    type_key = Key
    type_eventsum = EventSum
    type_timestamp = Timestamp

    def __init__(self, tables):
        self._tables = dict()

        for table_name, column_configs in tables.items():
            columns = []
            for column_config in column_configs:
                columns.append(self.create_column(column_config))
            self._tables[table_name] = columns

            column_names = [column.header() for column in columns]
            print "CREATE TABLE", table_name, "WITH COLUMNS", column_names

    def create_column(self, column_config):
        column_type = column_config.pop("type", None)
        if column_type is None:
            raise ValueError("no column type in column {0!r}".format(column_config))

        constructor = getattr(self, "type_" + column_type, None)
        if constructor is None:
            raise ValueError("unknown column type {0!r}".format(column_type))

        return constructor(**column_config)

    def insert(self, timestamp, event):
        for name, columns in self._tables.items():
            values = []

            for column in columns:
                values.append(list(column.parse(timestamp, event)))

            for row in itertools.product(*values):
                print "INSERT ROW", row, "TO TABLE", repr(name)


if __name__ == "__main__":
    # Define a custom mogrifier that has an additional column type
    # "number" that only lets through event values that can be parsed
    # as an integer.

    class Number(object):
        def __init__(self, key, header=None):
            self._key = key
            self._header = header

        def header(self):
            if self._header is None:
                return self._key
            return self._header

        def parse(self, timestamp, event):
            for value in event.values(self._key):
                try:
                    int(value)
                except ValueError:
                    continue

                yield value

    class MyMogrifier(Mogrifier):
        type_number = Number

    def demo(tables):
        mogrifier = MyMogrifier(json.loads(tables))

        mogrifier.insert(time.time(), Event({
            "ip": "1.2.3.4",
            "asn": "1"
        }))

        mogrifier.insert(time.time(), Event({
            "ip": "1.2.3.5",
            "feed": ["one", "two"],
            "asn": "2"
        }))

    demo('''{
        "log": [
            {"type": "timestamp"},
            {"type": "eventsum"},
            {"type": "number", "key": "asn"},
            {"type": "key", "key": "ip", "required": true},
            {"type": "key", "key": "feed", "required": false}
        ]
    }''')
