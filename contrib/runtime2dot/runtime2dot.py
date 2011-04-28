from abusehelper.core import bot
from abusehelper.core.config import *

class DotBot(bot.Bot):
    bot_name = None
    ini_file = None
    ini_section = None

    runtime_config = bot.Param("runtime configuration module")
    startup_config = bot.Param("startup configuration module",
                               default=None)
    show_attributes = bot.BoolParam()

    def run(self):
        print "digraph G {"
        print "node [ shape=box, style=filled, color=lightgrey ];"

        if self.startup_config is not None:
            services = set()
            for startup in load_configs(self.startup_config):
                attrs = dict(startup.params)
                services.add(attrs.get("bot_name", None))
            services.discard(None)
            missing = lambda x: x not in services
        else:
            missing = lambda x: False

        for session in load_configs(self.runtime_config):
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
