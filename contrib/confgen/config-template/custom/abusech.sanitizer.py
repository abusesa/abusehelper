import sanitizer

class AbuseCHSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        yield event

if __name__ == "__main__":
    AbuseCHSanitizer.from_command_line().execute()
