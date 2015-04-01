"""
Bot that supposedly talks to RTIR. Originally written by Harri
Sylvander, hastily converted to i3k by Jussi. If anyone wants to
maintain this code, please feel free to do so in my stead.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

from collections import defaultdict
import idiokit
from abusehelper.core import events, taskfarm, bot
from abusehelper.bots.rtirbot import rt


class CollectorBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.events = dict()

    @idiokit.stream
    def collect(self, name):
        while True:
            event = yield idiokit.next()
            self.events[name].append(event)

    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)

        try:
            yield (room
                   | events.stanzas_to_events()
                   | self.collect(name))
        finally:
            self.log.info("Left room %r", name)


class RtirBot(CollectorBot):
    rt_url = bot.Param("URL of RT instance")
    rt_user = bot.Param("RT user with rights to create and modify tickets")
    rt_password = bot.Param("RT user's password")
    rt_use_ah_template = bot.Param(
        "Use AH templates for investigation content generation")

    rt_write_interval = bot.IntParam("write interval", default=60)

    def __init__(self, *args, **keys):
        CollectorBot.__init__(self, *args, **keys)
        self.rtirs = dict()

        # Create RT Client
        self.log.info("Connecting to RT %s" % self.rt_url)
        try:
            self.rt_client = rt.RtClient(self.rt_url, self.rt_user,
                                         self.rt_password)
        except:
            self.log.info("Failed connecting to RT")
            raise
        self.log.info("Connected to RT")

        # Create RT Workflow automator
        self.rt_wf = rt.RtirWorkflow(self.rt_client)

    def write_to_rt_ticket(self, room, events):
        rtir_params = self.rtirs.get(room, None)
        if not rtir_params or not events:
            return

        # If rt_requestor is empty, it is most likely because the user
        # wants to automate selection of Requestor from within RT-IR.
        rt_requestor, rt_cc, rt_admin_cc, rt_constituency = rtir_params

        content = dict()
        modified_incident_ids = defaultdict(list)

        for event in events:
            for ip in event.values("ip"):
                line = unicode()
                line_list = []

                ir_type = "unknown"
                ir_type_detail = ""

                line_list.append("%s " % ",".join(event.values("time")))
                line_list.append("%s " % ",".join(event.values("ip")))

                for key in event.keys():
                    values = event.values(key)
                    # Filter out some fields from the content. IP and time
                    # have already been added so ignore them as well.
                    if not key=="asn" and not key=="ip" and not key=="time":
                        line_list.append("%s " % (",".join(values)))

                    # Extract type for subject
                    if key=="type":
                        ir_type = "%s" % "".join(values)

                    # Extract info for subject
                    if key=="type_detail":
                        ir_type_detail = "%s" % "".join(values)

                line = " | ".join(line_list)

                if line:
                    # Create an empty ticket and populate with AH event data
                    ticket = rt.RtIncidentReport()
                    ticket.reported_ip = ip
                    ticket.status = "open"
                    ticket.owner = "nobody"
                    ticket.content = line

                    ticket.cf_classification = ir_type
                    if ir_type!="unknown":
                        subject_type = str(ir_type) + " "
                    else:
                        subject_type = "Unspecified "

                    if ir_type_detail!="":
                        subject_info = '"' + str(ir_type_detail).capitalize() +\
                            '" '
                    else:
                        subject_info = ""

                    subject = "Detected " + subject_type + \
                        subject_info + ": " + ip
                    ticket.subject = subject.capitalize()

                    # Convert ticket attributes to POST parameter format
                    # required by RT then create the ticket.
                    ticket_params = ticket.create_ticket_params()
                    ticket.ticket_id = \
                        self.rt_client.create_ticket(ticket_params)

                    # RTIR workflow automation
                    # If no parent ticket (Incident) exists create a new
                    # incident and link to it. If an open incident exists
                    # link the new ticket.
                    if ticket.ticket_id:
                        self.log.info("RT Events written to ticket %r",
                                      ticket.ticket_id)
                        parent_id, ticket_created, created_by_ah = \
                            self.rt_wf.link_or_create_and_link_parent(ticket)

                        # Keep track of all created IRs and modified
                        # incidents.  Generate investigations after
                        # all current events are processed.  Do NOT
                        # create/update investigations of incidents
                        # that have been manually updated
                        # (AbuseHelperCheck is set to No)
                        if created_by_ah:
                            self.log.info("Ticket generated by AH, " + \
                                              "updating incident")
                            modified_incident_ids[parent_id].append(
                                ticket.ticket_id)
                        else:
                            self.log.info("Ticket manually updated, " +\
                                              "only linking to incident")

                        if parent_id:
                            if ticket_created:
                                self.log.info("RT created parent ticket %r",
                                              parent_id)
                            else:
                                self.log.info("RT linked parent ticket %r",
                                              parent_id)
                        else:
                            self.log.info("RT Linking/creation of " + \
                                              "parent ticket failed")
                    else:
                        self.log.info("Could not write events to RT")
                else:
                    self.log.info("No event data to parse")

        # If new IRs ere created and incidents modified, process them
        # and create investigations with content from open IRs. Close
        # IRs once the investigation is successfully generated. Future
        # investigations will be populated with data only from open,
        # i.e. new IRs.
        if modified_incident_ids:
            for modified_incident_id in modified_incident_ids:
                self.rt_wf.create_and_link_investigation(
                    rt_requestor, self.rt_use_ah_template,
                    modified_incident_id,
                    modified_incident_ids[modified_incident_id])

    @idiokit.stream
    def send_to_rtir(self, interval):
        yield idiokit.sleep(interval)
        for room, events in self.events.iteritems():
            self.write_to_rt_ticket(room, events)
            self.events[room] = list()

        idiokit.stop()

    @idiokit.stream
    def main(self, state):
        while True:
            yield (self.send_to_rtir(self.rt_write_interval)
                   | idiokit.consume())

    @idiokit.stream
    def session(self, state, src_room,
                rt_url="", rt_user="", rt_password="",
                rt_requestor="", rt_cc="", rt_admin_cc="",
                rt_constituency="", rt_write_interval=60, **keys):

        self.rtirs[src_room] = (rt_requestor, rt_cc,
                                rt_admin_cc, rt_constituency)

        self.events.setdefault(src_room, list())

        try:
            yield self.rooms.inc(src_room)
        finally:
            del self.rtirs[src_room]
            del self.events[src_room]


if __name__ == "__main__":
    RtirBot.from_command_line().execute()
