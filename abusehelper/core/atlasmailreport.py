import xml.etree.cElementTree as etree
import re
from idiokit import threado
from abusehelper.core import events,bot,utils
from abusehelper.core.imapbot import IMAPService

class AtlasMailReportService(IMAPService):
    filter = bot.Param(default=r'(BODY "http://atlas" UNSEEN)')
    url_rex = bot.Param(default=r"http://atlas\S+")

    @threado.stream
    def handle_text_plain(inner, self, headers, fileobj):
        for match in re.findall(self.url_rex, fileobj.read()):
            self.log.info("Fetching URL %r", match)
            try:
                info, fileobj = yield inner.sub(utils.fetch_url(match))
            except utils.FetchUrlFailed, fail:
                self.log.error("Fetching URL %r failed: %r", match, fail)
                return
            self.log.info("Parsing IODEF data from the URL")
            first_iteration = True
            event = events.Event()

            for k,v in parse_iodef(fileobj):
                yield
                if k == 'incident' and not first_iteration:
                    inner.send(event)

                if k == 'incident':
                    event = events.Event()
                    first_iteration = False
                if v != '':
                    event.add(k,v)

            inner.send(event)

def parse_iodef(fileobj):
    txt = re.sub('iodef:','',fileobj.read())

    xmlcontent = etree.fromstring(txt)    
    for item in xmlcontent.getiterator():

        if item.text == None or item.text == '':
            item.text = '-'

        tag = re.sub("{urn:ietf:params:xml:ns:iodef}","",item.tag.lower())
        text = item.text.strip()
        
   
        yield tag, text

        # use also <tag a="x" b="y"> 
        for k,v in item.items():
            key = "%s.%s" % ( tag, k.lower() )
            yield key, v
            


def test():
    fileobj = open('report.xml','r')
    for k,v in parse_iodef(fileobj):
        if k == 'incident': print '------'
        print "%s=%s " % (k,v)

if __name__ == "__main__":
    #test()
    AtlasMailReportService.from_command_line().execute()



