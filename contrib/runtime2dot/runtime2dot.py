import uuid
from abusehelper.core import bot
from abusehelper.core.config import *

class Clusters(object):
    def __init__(self):
        self.names = dict()
        self.nodes = dict()

    def add(self, name, node):
        self.names.setdefault(name, set()).add(node)
        self.nodes.setdefault(node, set()).add(name)

    def __iter__(self):
        for name, nodes in self.names.items():
            nodes = set(node for node in nodes if len(self.nodes.get(node, ())) == 1)
            yield name, nodes

class DotBot(bot.Bot):
    bot_name = None
    ini_file = None
    ini_section = None

    runtime_config = bot.Param("runtime configuration module")
    startup_config = bot.Param("startup configuration module",
                               default=None)
    node_per_service = bot.BoolParam()
    show_attributes = bot.BoolParam()
    cluster_by_type = bot.BoolParam()
    cluster_by_name = bot.BoolParam()

    def run(self):
        print "digraph G {"
        print "node [ shape=box, style=filled, color=lightgrey ];"

        if self.startup_config is not None:
            services = set()
            for config in load_configs(self.startup_config):
                startup = getattr(config, "startup", None)
                if startup is None:
                    continue
                attrs = dict(startup())
                services.add(attrs.get("bot_name", None))
            services.discard(None)
            missing = lambda x: x not in services
        else:
            missing = lambda x: False

        types = Clusters()
        names = Clusters()
        type_names = dict()

        for config in load_configs(self.runtime_config):
            config_runtime = getattr(config, "runtime", lambda x: [])

            sessions = set()
            for container in config_runtime():
                sessions.update(container.sessions(config))

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

                name = config.name
                type_name = config.__class__.__name__

                if src is not None:
                    types.add(type_name, src)
                    names.add(name, src)
                    type_names.setdefault(type_name, Clusters()).add(name, src)
                if node is not None:
                    types.add(type_name, node)
                    names.add(name, node)
                    type_names.setdefault(type_name, Clusters()).add(name, node)
                if dst is not None:
                    types.add(type_name, dst)
                    names.add(name, dst)
                    type_names.setdefault(type_name, Clusters()).add(name, dst)

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

        if self.cluster_by_type:
            for type_name, type_nodes in types:
                type_nodes = set(type_nodes)

                print "subgraph cluster_type_%s {" % type_name
                print 'label="%s";' % type_name

                if self.cluster_by_name:
                    clusters = type_names.get(type_name, Clusters())
                    for name, nodes in clusters:
                        nodes = set(nodes) & type_nodes
                        type_nodes.difference_update(nodes)
                        print "subgraph cluster_name_%s {" % name
                        print 'label="%s"; style=rounded; color=gray;' % name
                        for node in nodes:
                            print '"%s";' % node
                        print "}"

                for node in type_nodes:
                    print '"%s";' % node
                print "}"
        elif self.cluster_by_name:
            for name, nodes in names:
                print "subgraph cluster_name_%s {" % name
                print 'label="%s";' % name
                for node in nodes:
                    print '"%s";' % node
                print "}"

        print '}'

if __name__ == "__main__":
    DotBot.from_command_line().execute()
