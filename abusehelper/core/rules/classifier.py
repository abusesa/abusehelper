class Classifier(object):
    def __init__(self):
        self._rules = dict()

    def inc(self, rule, class_id):
        classes = self._rules.get(rule, None)
        if classes is None:
            classes = dict()
            self._rules[rule] = classes
        classes[class_id] = classes.get(class_id, 0) + 1

    def dec(self, rule, class_id):
        classes = self._rules.get(rule, None)
        if classes is None:
            return

        count = classes.get(class_id, 0) - 1
        if count > 0:
            classes[class_id] = count
        else:
            classes.pop(class_id, None)
            if not classes:
                self._rules.pop(rule, None)

    def classify(self, obj):
        result = set()
        cache = dict()

        for rule, classes in self._rules.iteritems():
            if result.issuperset(classes):
                continue

            if rule.match(obj, cache):
                result.update(classes)

        return result

    def is_empty(self):
        return not self._rules
