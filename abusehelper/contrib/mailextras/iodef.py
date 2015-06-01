"""
IODEF formatter for event data. Assumes some specific keys in the events.

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import time
import hashlib
from abusehelper.core import templates
from idiokit.xmlcore import Element

# Some XML output helpers
def node_id_and_text(parent, nodename, text=None, **kw):
    node = Element(nodename, **kw)
    if text is not None:
        node.text = text
    parent.add(node)

    return node

HEADER = """<?xml version=\"1.0\" ?>
<!DOCTYPE IODEF-Message PUBLIC "-//IETF//DTD RFC 5070 IODEF v1.0//EN" "IODEF-Document.dtd">
"""

def format_time(time_tuple=None):
    if time_tuple is None:
        time_tuple = time.gmtime()
    return time.strftime("%Y-%m-%d %H:%M:%SZ", time_tuple)

class XMLFormatter(templates.Formatter):
    def __init__(self, **kw):
        """
        Supported keys for kw (values all strings):
         * irt_website: Reporter website, eg. http://cert.example.com/
         * irt_name: Reporting team name, eg. EXAMPLE-CERT
         * irt_email: Reporter email address, eg. cert@cert.example.com
         * irt_phone: Reporter phone number
        If these are not provided, a report is generated nevertheless.
        """
        self.kw = kw

    def format(self, obj, events):
        """
        Make a IODEF XML output string out of the incidents in this
        collection

        Produces valid IODEF with regards to:
        http://xml.coverpages.org/draft-ietf-inch-iodef-14.txt

        Assumptions on the keys in the events:
         * 'time' contains the event timestamp in YY-MM-DD HH:MM:SS
         * 'ip' contains the ips related to the event
         * 'ptr' contains the domain names associated with the ips
         * 'asn' contains the as number of the ips
         * 'ticket' contains the ticket number related to the event
         * 'impact' contains the IODEF specified impact of the event
         * 'info' contains an informational string for humans
         * 'category' is either 'source' or 'target' as defined in IODEF
        """
        kw = self.kw

        # First, make the header
        top = Element('IODEF-Document')
        top.set_attr('lang', 'en')
        top.set_attr('version', "1.00")
        top.set_attr('xmlns', "urn:ietf:params:xml:ns:iodef-1.0")
        top.set_attr('xmlns:xsi',
                     "http://www.w3.org/2001/XMLSchema-instance")
        top.set_attr('xsi:schemaLocation',
                     "https://www.cert.fi/autoreporter/IODEF-Document.xsd")

        serialized = [HEADER, top.serialize_open()]

        def ts_to_xml(ts):
            return ts.replace(' ', 'T') + '+00:00'

        for inc in events:
            # Hardcoded purpose string, for now
            inc_tag = Element('Incident', purpose='mitigation')

            if not inc.contains('ticket id'):
                t_id = hashlib.md5("".join(repr((k, v))
                                           for k in sorted(inc.keys()) for v in
                                           sorted(inc.values(k)))).hexdigest()
                node_id_and_text(inc_tag, 'IncidentID',
                                 t_id, name=kw.get("irt_website", ''))
            else:
                for ticket in inc.values('ticket id'):
                    node_id_and_text(inc_tag, 'IncidentID',
                                     ticket, name=kw.get("irt_website", ''))

            if not inc.contains('source time'):
                node_id_and_text(inc_tag, 'ReportTime',
                                 ts_to_xml(format_time()))
            else:
                for ts in inc.values('source time'):
                    node_id_and_text(inc_tag, 'ReportTime',
                                     ts_to_xml(ts))

            inc_ass = node_id_and_text(inc_tag, 'Assessment')
            impact = inc.value("impact", "unknown")
            for info in inc.values('info'):
                node_id_and_text(inc_ass, 'Impact', info,
                                 lang='en', type=impact)

            # Provide contact details as described in config
            contact = node_id_and_text(inc_tag, 'Contact',
                                       role="creator", type="organization")
            if "irt_name" in kw:
                node_id_and_text(contact, 'ContactName', kw["irt_name"])
            if "irt_email" in kw:
                node_id_and_text(contact, 'Email', kw["irt_email"])
            if "irt_phone" in kw:
                node_id_and_text(contact, 'Telephone', kw["irt_phone"])

            event = node_id_and_text(inc_tag, 'EventData')

            # These are some default values for all entries, for now
            for value in inc.values('type'):
                node_id_and_text(event, 'Description', value)
            node_id_and_text(event, 'Expectation', action="investigate")
            event = node_id_and_text(event, 'EventData')
            event = node_id_and_text(event, 'Flow')

            # Category required, source is the default
            cat = inc.value('category', "source", filter=lambda x:
                             x in ['source', 'target'])

            # Target system information is provided, whenever available
            system = node_id_and_text(event, 'System',
                                      category=cat)
            # Only show node if data exists
            if (inc.contains("domain name") or inc.contains("ip") or
                inc.contains("asn")):
                node = node_id_and_text(system, 'Node')
            for value in inc.values("domain name"):
                node_id_and_text(node, 'NodeName', value)
            for value in inc.values("ip"):
                node_id_and_text(node, 'Address', value,
                                 category='ipv4-addr')
            for value in inc.values("asn"):
                node_id_and_text(node, 'Address', value,
                                 category='asn')

            serialized.append(inc_tag.serialize())

        serialized.append(top.serialize_close())
        serialized = "".join(serialized)
        serialized = serialized.decode("utf-8")
        return serialized
