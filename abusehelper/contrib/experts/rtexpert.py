"""
A simple bot for getting ticket ID numbers from a Request Tracker server.

Maintainer: "Juhani Eronen" <exec@iki.fi>


Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""
import re
import urllib
import httplib

import idiokit

from abusehelper.core import events, bot
from combiner import Expert

class RTExpert(Expert):
    rt_server = bot.Param("RT server (host:port)")
    rt_user = bot.Param("RT server username")
    rt_passwd = bot.Param("RT server user password")
    rt_queue = bot.Param("RT queue to create tickets to")
    ticket_subject = bot.Param("Subject text to use for the tickets")
    ticket_owner = bot.Param("RT ticket owner", default="")
    subject_key = bot.Param("Event key to use as ticket subject",
                            default="")
    content_key = bot.Param("Event key to use as ticket content",
                            default="")

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    def rt_ticket(self, **kw):
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        hostport = self.rt_server
        host, port = hostport.split(':')
        user = self.rt_user
        passwd = self.rt_passwd
        queue = self.rt_queue

        owner = self.ticket_owner
        if not owner:
            owner = self.rt_user

        params = urllib.urlencode({'user': user, 'pass': passwd}) + "&"
        text = kw.get('ticket_text', '')
        subject = kw.get('ticket_subject', '')
        urlpath =  "/REST/1.0/ticket/new"
        content = "id: ticket/new\nStatus: new\n" + \
            "Subject: %s\nQueue: %s\nText: %s\n" % (subject, queue, text) + \
            "Owner: %s\n" % (owner)

        params += urllib.urlencode({"content": content})

        try:
            if port == '80':
		conn = httplib.HTTPConnection(hostport)
            else:
		conn = httplib.HTTPSConnection(hostport)
            conn.request("POST", urlpath, params, headers)
            response = conn.getresponse()
            data = response.read()
            conn.close()
        except Exception, fuf:
            self.log.error("RT Connection failed: %r", fuf)
            return u""

        ticketno = re.findall("(\d+) created.", data, re.M)
        try:
            int(ticketno[0])
        except (TypeError, ValueError):
            self.log.error("Weird response from rt: %r", data)
            return u""

        return ticketno[0]

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            kw = {}
            subj = ""
            if self.subject_key:
                if event.contains(self.subject_key):
                    subj = event.value(self.subject_key)
            if not subj and self.ticket_subject:
                subj = self.ticket_subject

            kw['ticket_subject'] = subj
            if self.content_key:
                if event.contains(self.content_key):
                    kw['ticket_text'] = event.value(self.content_key)

            nro = yield idiokit.thread(self.rt_ticket, **kw)
            if nro:
                augment = events.Event()
                augment.add('ticket id', nro)
                yield idiokit.send(eid, augment)

if __name__ == "__main__":
    RTExpert.from_command_line().execute()
