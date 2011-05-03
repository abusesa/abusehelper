# By Jussi Eronen <exec@iki.fi> 2011
# MIT License

import hashlib

from abusehelper.core import templates

from xml.dom.minidom import Document, DocumentType, getDOMImplementation

# Some XML output helpers
def node_id_and_text(doc, parent, nodename, text='', **kw):
    node = doc.createElement(nodename)
    for key, value in kw.items():
        node.setAttribute(key, value)
    parent.appendChild(node)

    if text:
        text = doc.createTextNode(text)
        node.appendChild(text)

    return node

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
        impl = getDOMImplementation()
        doc = impl.createDocument(None, 'IODEF-Document', None)
        top = doc.documentElement
        top.setAttribute('lang', 'en')
        top.setAttribute('version', "1.00")
        top.setAttribute('xmlns', "urn:ietf:params:xml:ns:iodef-1.0")
        top.setAttribute('xmlns:xsi', 
                         "http://www.w3.org/2001/XMLSchema-instance")
        top.setAttribute('xsi:schemaLocation',
                         "https://www.cert.fi/autoreporter/IODEF-Document.xsd")

        def ts_to_xml(ts):
            return ts.replace(' ', 'T') + '+00:00'

        for inc in events:
            # Hardcoded purpose string, for now
            inc_tag = node_id_and_text(doc, top, 
                                       'Incident', purpose='mitigation')

            if not inc.contains('case'):
                hashlib.md5("".join(repr((k, v)) 
                                    for k in sorted(inc.keys()) for v in 
                                    sorted(inc.values(k)))).hexdigest()
            else:
                for ticket in inc.values('case'):
                    node_id_and_text(doc, inc_tag, 'IncidentID', 
                                     ticket, name=kw.get("irt_website", ''))

            if not inc.contains('time'):
                node_id_and_text(doc, inc_tag, 'ReportTime', 
                                 ts_to_xml(sanitizer.format_time()))
            else:
                for ts in inc.values('time'):
                    node_id_and_text(doc, inc_tag, 'ReportTime', 
                                     ts_to_xml(ts))

            inc_ass = node_id_and_text(doc, inc_tag, 'Assessment')
            impact = inc.value("impact", "unknown")
            for info in inc.values('info'):
                node_id_and_text(doc, inc_ass, 'Impact', info,
                                 lang='en', type=impact)
        
            # Provide contact details as described in config
            contact = node_id_and_text(doc, inc_tag, 'Contact',
                                       role="creator", type="organization")
            if kw.has_key("irt_name"):
                node_id_and_text(doc, contact, 'ContactName', kw["irt_name"])
            if kw.has_key("irt_email"):
                node_id_and_text(doc, contact, 'Email', kw["irt_email"])
            if kw.has_key("irt_phone"):
                node_id_and_text(doc, contact, 'Telephone', kw["irt_phone"])

            event = node_id_and_text(doc, inc_tag, 'EventData')

            # These are some default values for all entries, for now
            for value in inc.values('type'):
                node_id_and_text(doc, event, 'Description', value)
            node_id_and_text(doc, event, 'Expectation', action="investigate")
            event = node_id_and_text(doc, event, 'EventData')
            event = node_id_and_text(doc, event, 'Flow')

            # Category required, source is the default
            cat = inc.value('category', "source", filter=lambda x: 
                             x in ['source', 'target'])

            # Target system information is provided, whenever available
            system = node_id_and_text(doc, event, 'System', 
                                      category=cat)
            # Only show node if data exists
            if (inc.contains("ptr") or inc.contains("ip") or 
                inc.contains("asn")):
                node = node_id_and_text(doc, system, 'Node')
            for value in inc.values("ptr"):
                node_id_and_text(doc, node, 'NodeName', value)
            for value in inc.values("ip"):
                node_id_and_text(doc, node, 'Address', value, 
                                 category='ipv4-addr')
            for value in inc.values("asn"):
                node_id_and_text(doc, node, 'Address', value, 
                                 category='asn')

        return doc.toxml()
