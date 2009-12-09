from idiokit import threado,xmpp
import sys
import re
from opencollab.wiki import CLIWiki,WikiFault
from opencollab.meta import Meta
from idiokit.jid import JID
import time
from idiokit import timer
import abusehelper.thirdparty.urlre as urlre

class Txt2Collab(object):
    def __init__(self,collab,basePage,filename,overwrite=True,
                 timestampformat='%Y-%m-%d'):
        self.collab = collab
        self.basePage = basePage
        self.filename = filename
        self.events = list()
        self.overwrite = overwrite
        self.timestampformat = timestampformat
        self.urlrows = set()
    def add(self,event):
        self.events.append(event)

    def log(self):
        if len(self.events) == 0:
            return
        date = time.strftime(self.timestampformat,time.gmtime())
        page = "%s/%s" % (self.basePage, date)


        #does base exist
        try:
            wikipage = self.collab.getPage(self.basePage)
        except WikiFault:
            txt = """
= Latest Entry =

<<Include(^CollabChatLog/2.*,,sort=descending,items=1,editlink)>>

= Past Topics =
 
<<MetaTable(CollabChatLog Attachment=/.*/, >>Date, ||Date||CollabChatLog Attachment||<gwikiname=\"URLS\" gwikistyle=\"list\">url||)>>
"""

            self.collab.putPage(self.basePage,txt)
        #metas
        try:
            wikipage = self.collab.getPage(page)
        except WikiFault:
            meta = Meta()
            meta['CollabChatLog Attachment'].add('[[attachment:%s]]' % (self.filename))
            meta['CollabChatLog Inline'].add('{{attachment:%s}}' % (self.filename))
            meta['Date'].add(date)
            self.collab.setMeta(page,meta)
        #uploading log
        try:
            data = self.collab.getAttachment(page,self.filename)
        except WikiFault:
            data = ""
        meta = Meta()
        for k,v in self.events:
            v += '\n'
            v = re.sub(urlre.xmpp_url_all_re,"",v)
            if urlre.url_all_re.search(v):
                meta['url'].add('%s' % (v))

            data += v.encode('utf-8')

        if len(meta) > 0:
            self.collab.setMeta(page,meta)

        self.events = list()
        self.collab.putAttachment(page,self.filename,data,overwrite=True)


@threado.stream
def logger(inner,txt2collab, base_time, interval):
    sleeper = timer.sleep(interval / 2.0)
    
    while True:
        event = yield inner,sleeper
        if sleeper.was_source:
            sleeper = timer.sleep(interval)
            txt2collab.log()
        else:
            print 'adding', event
            txt2collab.add(event)

@threado.stream
def roomparser(inner,srcjid_re):
    srcjid_re = re.compile(srcjid_re)
    while True:
        message = yield inner
        print message.serialize()
        if True:
            if message.children("x", "jabber:x:delay"):
                continue
            if message.children("delay", "urn:xmpp:delay"):
                continue


            sender = message.get_attr("from")
            if not srcjid_re.search(sender):
                continue
            sender = JID(sender)

            for body in message.children("body"):
                text = "<%s> %s" % (sender.resource, body.text)
                timestamp = time.strftime("%Y-%m-%d %H:%M",time.gmtime())
            
                message = "%s %s" % ( timestamp, text )

                inner.send(sender, message)


@threado.stream
def main(inner,username,password):
    collabinstance = sys.argv[1]
    delay = float(sys.argv[2])
    if re.search('[^a-z|0-9|\.]',collabinstance):
        print 'non-allowed chars in collab instance'
        sys.exit(1)

        
    xmppuser = '%s@clarifiednetworks.com' % (re.sub('@','%',username))
    xmppmucs = "conference.clarifiednetworks.com"
    room = "%s@%s" % (collabinstance,xmppmucs)
    print 'joined room'
    myxmpp = yield xmpp.connect(xmppuser,password)
    myxmpp.core.presence()
    room = yield myxmpp.muc.join(room,"/collablogger")
                                                      
    collab = CLIWiki('https://www.clarifiednetworks.com/collab/%s/' %
                     (collabinstance))
    collab.authenticate(username=username,password=password)

    attachFilename = "log.txt"
    basePage = "CollabChatLog"
    
    txt2collab = Txt2Collab(collab,basePage,attachFilename,
                            timestampformat="%Y-%m-%d")
    srcjid_filter = "conference.clarifiednetworks.com"

    yield inner.sub(room |roomparser(srcjid_filter)|
                    logger(txt2collab,0,delay) )
        
if __name__ == "__main__":
    import getpass

    username = raw_input("Collab & XMPP Username (without the @domain): ")
    password = getpass.getpass()
    
    threado.run(main(username, password))
                
