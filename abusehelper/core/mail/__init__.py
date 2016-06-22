import idiokit


class Handler(object):
    def __init__(self, log):
        self.log = log

    @idiokit.stream
    def handle(self, msg):
        handle_default = getattr(self, "handle_default", None)

        stack = [msg]
        while stack:
            part = stack.pop()
            content_type = part.get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is not None:
                skip_rest = yield handler(part)
                if skip_rest:
                    idiokit.stop(True)
                continue

            if part.is_multipart():
                parts = yield part.get_payload()
                stack.extend(reversed(parts))

        idiokit.stop(False)
