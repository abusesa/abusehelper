"""
A sanitizer to remove augmentation keys.

Maintainer: "Jussi Eronen" <exec@iki.fi>
"""
import sanitizer
from abusehelper.contrib.experts.combiner import AUGMENT_KEY


class ExpertSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        event.clear(AUGMENT_KEY)
        return [event]

if __name__ == "__main__":
    ExpertSanitizer.from_command_line().execute()
