from urllib import urlencode
from httplib import HTTPSConnection
from xml.dom.minidom import parseString

def encode(text):
    return text.encode("utf8")

class ProwlConnection:
    def __init__(self, apikeys, host="prowl.weks.net", port=443, 
                 providerkey=None):
        self.apikeys = apikeys
        self.host = host
        self.port = port
        self.providerkey = providerkey

    def __del__(self):
        self.connection.close()

    def add(self, application, event=None, description=None, priority=0):

        if len(self.apikeys.split(",")) > 5:
            raise ValueError, "Too many apikeys!"

        if not event and not description:
            raise ValueError, "Missing event or description!"

        parameters = {"apikey": self.apikeys,
                      "application": encode(application),
                      "priority": priority}

        if event:
            parameters["event"] = encode(event)

        if description:
            parameters["description"] = description

            parameters["description"] = encode(description)

        if self.providerkey:
            parameters["providerkey"] = self.providerkey

        headers = {"Content-type": "application/x-www-form-urlencoded"}
        connection = HTTPSConnection(self.host, self.port)
        connection.request("POST", "/publicapi/add",
                                urlencode(parameters), headers)

        response = connection.getresponse()
        connection.close()
        msg = "Sent: %s" % ( description )
        try:
            self._parse_response(response)
        except Exception, error:
            msg = "Could not send message: %s" % (error)
        return msg

    def _get_tag(self, xml, tag):
        return xml.getElementsByTagName(tag)[0].childNodes[0].nodeValue

    def _parse_response(self, response):
        output = response.read()
        xml = parseString(output)

        if response.status == 200:
            element = xml.getElementsByTagName("success")[0]
            return (element.attributes['remaining'].value,
                    element.attributes['resetdate'].value)
        elif response.status == 400:
            message = self._get_tag(xml,"error")
            raise Exception("%i: Bad request, %s" % (response.status, message))
        elif response.status == 401:
            message = self._get_tag(xml,"error")
            raise Exception("%i: Not authorized. %s" %
                            (response.status, message))
        elif response.status == 405:
            message = self._get_tag(xml,"error")
            raise Exception("%i: Method not allowed. %s" %
                            (response.status, message))
        elif response.status == 406:
            message = self._get_tag(xml,"error")
            raise Exception("%i: Not acceptable. %s" %
                            (response.status, message))
        elif response.status == 500:
            message = self._get_tag(xml,"error")
            raise Exception("%i: Internal server error. %s" %
                            (response.status, message))
        else:
            raise Exception("%i: %s" % (response.status, message))


