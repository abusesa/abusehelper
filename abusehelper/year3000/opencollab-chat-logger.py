# -*- coding: latin-1 -*-

import re
import getpass
from opencollab.wiki import CLIWiki,WikiFault
from opencollab.meta import Meta
import xmlrpclib
import sys
from idiokit import threado, util, throttle
from idiokit.xmpp import XMPP, Element
from idiokit.core import JID
from abusehelper.core import events

import time


from abusehelper.core import events
from idiokit.core import XMPPError
from idiokit.xmpp import XMPP, Element
from idiokit import threado


class Txt2Collab(object):
    def __init__(self,collab,basePage,filename,overwrite=True,
                 timestampformat='%Y-%m-%d'):
        self.collab = collab
        self.basePage = basePage
        self.filename = filename
        self.events = list()
        self.overwrite = overwrite
        self.timestampformat = timestampformat

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

<<MetaTable(CollabChatLog Attachment=/.*/, >>Date, ||Date||CollabChatLog Attachment||)>>
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
            data = self.collab.getAttachment(page,file)
        except WikiFault:
            data = ""
        for k,v in self.events:
#            v += '\n'
            data += v.encode('utf-8')
        self.events = list()
        self.collab.putAttachment(page,file,data,overwrite=True)

@threado.stream
def myqueue(inner, row):
    #for testing
    while True:
        mytime = time.strftime('%H-%M-%S')
        inner.send(None, mytime+'blah')
        inner.send(None, mytime+'bleh')
        time.sleep(2)
        yield

@threado.thread
def roomparser(inner,srcjid_re):
    srcjid_re = re.compile(srcjid_re)
    while True:
        try:
            message = inner.next(1)
        except threado.Timeout:
            pass
        else:
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


@threado.thread
def logger(inner, txt2collab, base_time, interval):
    while True:
        delay = interval - (time.time() - base_time) % interval
        try:
            event = inner.next(delay)
        except threado.Timeout:
            txt2collab.log()
        else:
            txt2collab.add(event)



def main():
    collabinstance = sys.argv[1]
    delay = float(sys.argv[2])
    if re.search('[^a-z|0-9|\.]',collabinstance):
        print 'non-allowed chars in collab instance'
        sys.exit(1)

    username = raw_input("Collab username: ")
    password = getpass.getpass()

    
    xmppuser = '%s@clarifiednetworks.com' % (re.sub('@','%',username))
    xmppmucs = "conference.clarifiednetworks.com"
    room = "%s@%s" % (collabinstance,xmppmucs)
    
    xmpp = XMPP(xmppuser,password)
    xmpp.connect()
    xmpp.core.presence()
    room = xmpp.muc.join(room,"/collablogger")


    collab = CLIWiki('https://www.clarifiednetworks.com/collab/%s/' % 
                     (collabinstance))
    collab.authenticate(username=username,password=password)

    attachFilename = "log.txt"
    basePage = "CollabChatLog"
    
    txt2collab = Txt2Collab(collab,basePage,attachFilename,
                            timestampformat="%Y-%m-%d")
    
    srcjid_filter = "conference.clarifiednetworks.com"
    for _ in room |roomparser(srcjid_filter)| logger(txt2collab,0,delay) | threado.throws():
        pass
if __name__ == "__main__":
    main()




