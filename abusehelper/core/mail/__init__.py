import idiokit


class Handler(object):
    @idiokit.stream
    def handle(self, msg, log):
        handle_default = getattr(self, "handle_default", None)

        for part in msg.walk():
            content_type = part.get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is None:
                continue

            skip_rest = yield handler(part, log)
            if skip_rest:
                return
