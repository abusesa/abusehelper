from __future__ import with_statement
import threading
from idiokit import threado, util
from idiokit.xmlcore import Element

RULESET_NS = "idiokit#ruleset"

class RuleError(Exception):
    pass

def _find_rules(elements, _rules):
    results = list()
    for element in elements:
        for rule in _rules:
            try:
                results.append(rule.from_element(element, _rules))
            except RuleError:
                pass
            else:
                break
        else:
            raise RuleError(element)
    return results

class _Rule(object):
    def __init__(self, *args, **keys):
        self.arguments = tuple(args), frozenset(keys.items())

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self.arguments == other.arguments

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash(self.__class__) ^ hash(self.arguments)

class NOT(_Rule):
    @classmethod
    def from_element(cls, element, _rules):
        if element.name != "NOT" or len(element.children()) < 1:
            raise RuleError(element)
        return cls(*_find_rules(element.children(), _rules))

    def __init__(self, child):
        _Rule.__init__(self, child)
        self.child = child

    def to_element(self):
        element = Element("NOT")
        element.add(self.child.to_element())
        return element

    def __call__(self, *args, **keys):
        return not self.child(*args, **keys)

class OR(_Rule):
    @classmethod
    def from_element(cls, element, _rules):
        if element.name != "OR" or len(element.children()) < 1:
            raise RuleError(element)
        return cls(*_find_rules(element.children(), _rules))

    def __init__(self, first, *rest):
        _Rule.__init__(self, first, *rest)
        self.children = (first,) + rest

    def to_element(self):
        element = Element("OR")
        for child in self.children:
            element.add(child.to_element())
        return element

    def __call__(self, *args, **keys):
        for child in self.children:
            if child(*args, **keys):
                return True
        return False

class AND(_Rule):
    @classmethod
    def from_element(cls, element, _rules):
        if element.name != "AND" or len(element.children()) < 1:
            raise RuleError(element)
        return cls(*_find_rules(element.children(), _rules))

    def __init__(self, first, *rest):
        _Rule.__init__(self, first, *rest)
        self.children = (first,) + rest

    def to_element(self):
        element = Element("AND")
        for child in self.children:
            element.add(child.to_element())
        return element

    def __call__(self, *args, **keys):
        for child in self.children:
            if not child(*args, **keys):
                return False
            return True

class CONTAINS(_Rule):
    @classmethod
    def from_element(cls, element, _rules):
        if element.name != "CONTAINS" or len(element.children()) < 1:
            raise RuleError(element)
        keys = set()
        key_values = dict()
        for child in element.children("attr").with_attrs("key"):
            key = child.get_attr("key")
            value = child.get_attr("value", None)
            if value is None:
                keys.add(str(key))
            else:
                key_values[str(key)] = value
        return cls(*keys, **key_values)

    def __init__(self, *keys, **key_values):
        _Rule.__init__(self, *keys, **key_values)
        self.keys = keys
        self.key_values = key_values

    def to_element(self):
        element = Element("CONTAINS")
        for key in self.keys:
            element.add(Element("attr", key=key))
        for key, value in self.key_values.items():
            element.add(Element("attr", key=key, value=value))
        return element

    def __call__(self, event):
        for key in self.keys:
            if not event.contains_key(key):
                return False
        for key, value in self.key_values.items():
            if not event.contains_key_value(key, value):
                return False
        return True

class _TaggedRule(_Rule):
    @classmethod
    def from_element(cls, element, _rules):
        if element.name != "rule" or len(element.children()) != 1:
            raise RuleError(element)
        tag = element.get_attr("tag", None)
        if tag is None:
            raise RuleError(element)
        return cls(tag, *_find_rules(element.children(), _rules))

    def __init__(self, tag, child):
        _Rule.__init__(self, tag, child)
        self.tag = tag
        self.child = child

    def to_element(self):
        rule_element = Element("rule", tag=self.tag)
        rule_element.add(self.child.to_element())
        return rule_element

    def __call__(self, item):
        return self.child(item)

class RuleSet(object):
    _rules = [NOT, AND, OR, CONTAINS]

    @classmethod
    def from_element(cls, element):
        if not element.named("ruleset", RULESET_NS):
            raise RuleError(element)

        result = cls()
        for child in element.children():
            rule = _TaggedRule.from_element(child, cls._rules)
            result.add(rule.tag, rule.child)
        return result

    def __init__(self):
        self.lock = threading.Lock()
        self.rules = set()

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self.rules == other.rules

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def add(self, tag, rule):
        tagged_rule = _TaggedRule(tag, rule)
        with self.lock:
            self.rules.add(tagged_rule)
        return tagged_rule

    def discard(self, tagged_rule):
        with self.lock:
            self.rules.discard(tagged_rule)

    def tags_for(self, item):
        with self.lock:
            return set(rule.tag for rule in self.rules if rule(item))

    def tags(self):
        with self.lock:
            return set(rule.tag for rule in self.rules)

    def to_element(self):
        element = Element("ruleset", xmlns=RULESET_NS)
        with self.lock:
            for rule in sorted(self.rules, key=lambda x: x.tag):
                element.add(rule.to_element())
        return element
