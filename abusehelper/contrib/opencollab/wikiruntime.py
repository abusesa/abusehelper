import json
from opencollab import wiki

from abusehelper.core import bot
from abusehelper.core.runtime import RuntimeBot, Session

from abusehelper.contrib.opencollab.wikistartup import WikiConfigInterface, rmlink

class WikiRuntimeBot(WikiConfigInterface, RuntimeBot):
    collab_url = bot.Param("Collab url")
    collab_user = bot.Param("Collab user")
    collab_password = bot.Param("Collab password", default=None)
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)

    category = bot.Param("Page category (default: %default)",
                         default="CategorySession")
    poll_interval = bot.IntParam("how often (in seconds) the collab is " +
                                 "checked for updates (default: %default)",
                                 default=60)
    decrypt_password = bot.Param("Password for decrypting metas.", default=None)

    def __init__(self, *args, **keys):
        super(RuntimeBot, self).__init__(*args, **keys)
        self.collab = None
        self._metas = dict()

    def parse_pages(self, pages):
        sessions = list()

        for page, metas in pages.iteritems():
            metas = dict(metas)
            for key in ['gwikilabel', 'gwikicategory']:
                try:
                    del metas[key]
                except KeyError:
                    pass

            service = list(metas.pop("service", set()))
            if not service:
                self.log.error('%s: Missing service.', page)
                return
            elif len(service) > 1:
                self.log.error("%s: Too many values for service.", page)
                return
            else:
                service = rmlink(service[0])

            state = list(metas.pop("state", set()))
            if not state:
                state = None
            elif len(state) > 1:
                self.log.error("%s: Too many values for state.", page)
                return
            elif len(state) == 1:
                state = rmlink(state[0])

            for room_key in ["src_room", "dst_room"]:
                room = list(metas.get(room_key, set()))
                if len(room) > 1:
                    self.log.error("%s: Too many values for %s.", page,
                                                                  room_key)
                    return
                elif len(room) == 1:
                    metas[room_key] = rmlink(room[0])

            skip = ["state", "src_room", "dst_room"]
            pages[page] = self.parse_metas(metas, skip)
            if state:
                sessions.append(Session(service, state, **metas))
            else:
                sessions.append(Session(service, **metas))

        if pages != self._metas:
            self._metas = pages
            return sessions

if __name__ == "__main__":
    WikiRuntimeBot.from_command_line().execute()
