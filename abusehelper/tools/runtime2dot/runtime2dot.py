from abusehelper.core import bot, config, startup, runtime


def iter_dots(iterable):
    for obj in iterable:
        dot = getattr(obj, "__dot__", None)
        if callable(dot):
            yield dot()


class Dot(object):
    def __init__(self, *configs):
        self.configs = tuple(config.flatten(configs))

    def __dot__(self):
        return self

    def services(self):
        services = set()
        for dot in iter_dots(self.configs):
            services.update(dot.services())

        for conf in startup.iter_startups(self.configs):
            service = dict(conf.params).get("bot_name", None)
            services.add(service)

        services.discard(None)
        return services

    def sessions(self):
        sessions = set()
        for dot in iter_dots(self.configs):
            sessions.update(dot.sessions())

        for session in runtime.iter_runtimes(self.configs):
            sessions.add(session)

        return sessions


def _id(value):
    return u"\"" + unicode(value).replace(u"\"", u"\\\"") + u"\""


def line(*nodes, **keys):
    result = u"->".join(map(_id, nodes))

    attrs = []
    for key, value in keys.iteritems():
        attrs.append(_id(key) + u"=" + _id(value))

    if attrs:
        result += u" [ " + u", ".join(attrs) + u" ]"
    return (result + u";").encode("utf-8")


class DotBot(bot.Bot):
    bot_name = None

    config = bot.Param("configuration module")
    show_startups = bot.BoolParam()
    show_attributes = bot.BoolParam()

    def run(self):
        print "digraph G {"
        print "node [ shape=box, style=filled, color=lightgrey ];"

        dot = Dot(config.load_configs(self.config))
        services = dot.services()
        sessions = dot.sessions()

        def missing(x):
            return self.show_startups and x not in services

        for session in sessions:
            conf = dict(session.conf)
            path = session.path
            src = conf.pop("src_room", None)
            dst = conf.pop("dst_room", None)

            node = None
            if session.service != "roomgraph":
                node = "node " + session.service + " " + (src or "@") + " " + (dst or "@")
                if missing(session.service):
                    print line(node, label=session.service, shape="ellipse", fontsize=12, fontcolor="white", color="red")
                else:
                    print line(node, label=session.service, shape="ellipse", fontsize=12, style="")

            label_list = list()
            if path:
                label_list.append(".".join(path))
            if self.show_attributes:
                for item in conf.items():
                    label_list.append("  %r=%r" % item)
            label = "\\n".join(label_list)

            color = "red" if missing(session.service) else "black"
            if src is None:
                if node is not None and dst is not None:
                    print line(node, dst, label=label, color=color, fontsize=10)
            else:
                if node is not None and dst is None:
                    print line(src, node, label=label, color=color, fontsize=10)
                elif node is None and dst is not None:
                    print line(src, dst, label=label, color=color, fontsize=10)
                elif node is not None and dst is not None:
                    print line(src, node, label="", color=color, fontsize=10)
                    print line(node, dst, label=label, color=color, fontsize=10)

        print '}'

if __name__ == "__main__":
    DotBot.from_command_line().execute()
