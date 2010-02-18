from abusehelper.core.config import load_module

# Load module "sanitizer" from the same directory as this file.
sanitizer = load_module("sanitizer")

# sanitizer.Sanitizer is the base class for a simple sanitizer bot.
class DShieldSanitizer(sanitizer.Sanitizer):
    # .sanitize(event) is the hook method for sanitizing events. This
    # is the only method you have to implement to create a basic
    # normalizer, sanitizer, modifier or filter.
    def sanitize(self, event):
        # Modify and create events here.
        event.add("type", "unknown")

        # Return a list of events here. The list can contain 0-n events.
        return [event]

if __name__ == "__main__":
    # Execute the sanitizer bot based on the command line options.
    DShieldSanitizer.from_command_line().execute()
