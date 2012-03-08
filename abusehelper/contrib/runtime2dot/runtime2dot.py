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

        if self.show_startups:
            missing = lambda x: x not in services
        else:
            missing = lambda x: False

        for session in sessions:
            conf = dict(session.conf)
            path = session.path
            src = conf.pop("src_room", None)
            dst = conf.pop("dst_room", None)

            node = None
            if session.service != "roomgraph":
                node = "node " + session.service + " " + (src or "@") + " " + (dst or "@")
                if missing(session.service):
                    print '"%s" [ label="%s", shape=ellipse, fontsize=12, fontcolor=white, color=red ];' % (node, session.service)
                else:
                    print '"%s" [ label="%s", shape=ellipse, fontsize=12, style="" ];' % (node, session.service)

            name = session.service

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
                    print '"%s"->"%s" [ label="%s", fontsize=10, color="%s" ];' % (node, dst, label, color)
            else:
                if node is not None and dst is None:
                    print '"%s"->"%s" [ label="%s", fontsize=10, color="%s" ];' % (src, node, label, color)
                elif node is None and dst is not None:
                    print '"%s"->"%s" [ label="%s", fontsize=10, color="%s" ];' % (src, dst, label, color)
                elif node is not None and dst is not None:
                    print '"%s"->"%s" [ label="%s", fontsize=10, color="%s" ];' % (src, node, "", color)
                    print '"%s"->"%s" [ label="%s", fontsize=10, color="%s" ];' % (node, dst, label, color)

        print '}'

if __name__ == "__main__":
    DotBot.from_command_line().execute()
