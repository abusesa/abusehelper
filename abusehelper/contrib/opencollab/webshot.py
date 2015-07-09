"""
Uses PhantomJS to grab screenshots of web pages, and saves the
resulting screenshot, server headers and HAR file of the grab to wiki.

Tested with PhantomJS 1.6.2.

Important notice:

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""
import os
import socket
import idiokit
import simplejson as json

from abusehelper.core import bot, events, taskfarm
from abusehelper.contrib.experts.combiner import Expert

from tempfile import mkstemp
from subprocess import Popen, PIPE, STDOUT
from random import choice
from time import strptime
from calendar import timegm

from opencollab.wiki import GraphingWiki
from opencollab.util.file import uploadFile

class WebshotExpert(Expert):
    collab_url = bot.Param()
    collab_user = bot.Param()
    collab_password = bot.Param()
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)
    collab_template = bot.Param(default=[""])
    phantomjs_binary = bot.Param(default="/usr/bin/phantomjs")
    phantomjs_script = bot.Param(default="netsniff-render.coffee")
    user_agent = bot.Param(default=[""])
    template = bot.Param(default=[""])

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)

        # log a notification about the abusehelper.contrib migration
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

        self.cache = dict()

        self.collab = GraphingWiki(self.collab_url,
                                   ssl_verify_cert=not self.collab_ignore_cert,
                                   ssl_ca_certs=self.collab_extra_ca_certs)
        self.collab.authenticate(self.collab_user, self.collab_password)

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("url",)))

    def jsongrab(self, url):
        tmp_fileno, tmp_name = mkstemp('.png')

        # The used script must exit, otherwise this call will block!
        p = Popen("%s %s %s %s %s" % (self.phantomjs_binary, self.phantomjs_script,
                                      url, tmp_name, choice(self.user_agent)),
                  shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        (_in, _out) = (p.stdin, p.stdout)
        _in.close()
        jsondata = _out.read()
        _out.close()

        try:
            # Sometimes you get warning messages before the json, ignore them
            if not jsondata.startswith('{'):
                new_data = list()
                data_start = False
                for line in jsondata.split('\n'):
                    if line.startswith('{'):
                        data_start = True
                    if data_start:
                        new_data.append(line)
                if data_start:
                    jsondata = '\n'.join(new_data)
            data = json.loads(jsondata)
        except:
            data = jsondata.replace('\n', ' ')[:100]
            self.log.error("Script returned with error: %r", data)
            return

        f = file(tmp_name)
        imgdata = f.read()
        os.close(tmp_fileno)
        os.remove(tmp_name)

        # Page name is the server/path section of the url without any
        # trailing attributes or slashes
        page = '/'.join(url.split('/')[2:])
        page = page.split('?')[0]
        page = page.split('#')[0]
        url_page = page.rstrip('/')

        metas = dict()

        check_url = url.rstrip('/')
        for entry in data['log']['entries']:
            if not entry['request']['url'].rstrip('/') == check_url:
                continue

            grab_epoch = timegm(strptime(entry['startedDateTime'].split('.')[0],
                                         "%Y-%m-%dT%H:%M:%S"))

            metas["creator"] = ["%s %s" % (data['log']['creator']['name'],
                                          data['log']['creator']['version'])]

            metas["started"] = ["%s" % entry['startedDateTime']]
            metas["grabtime"] = ["%s" % entry['time']]

            for header in entry['request']['headers']:
                metas[header['name'].lower()] = [header['value']]
            for header in entry['response']['headers']:
                metas[header['name'].lower()] = [header['value']]
            metas['mimetype'] = [entry['response']['content']['mimeType']]

        page = url_page + "/%s" % (grab_epoch)

        metas['gwikishapefile'] = ['{{attachment:screenshot.png||width=100}}']
        metas['screenshot'] = ['{{attachment:screenshot.png}}']
        metas['grabdetails'] = ['[[attachment:grabdetails.json]]']

        result = self.collab.setMeta(page, metas, True, self.template)
        for line in result:
            self.log.info("%r: %r", page, line)

        metas = dict()
        metas["latest webshot"] = ['[[%s]]' % page]
        result = self.collab.setMeta(url_page, metas, True, self.template)
        for line in result:
            self.log.info("%r: %r", page, line)

        for data, fname in [(jsondata, "grabdetails.json"),
                            (imgdata, "screenshot.png")]:
            if not data:
                continue
            try:
                self.log.info("Uploading file: %r (data %r...)",
                              fname, repr(data[:10]))
                status = uploadFile(self.collab, page, '', fname, data=data)
            except (IOError, TypeError, RuntimeError), msg:
                self.log.error("Upload failed: %r", msg)
                return

        return self.collab_url + page

    @idiokit.stream
    def augment(self, key):
        while True:
            eid, event = yield idiokit.next()

            for url in event.values(key):
                new = events.Event()

                self.log.info("Taking a webshot of %r", url)
                success = yield idiokit.thread(self.jsongrab, url)

                if success:
                    new.add("webshot", success)
                else:
                    new.add("webshot", "Failed to get a webshot")

                yield idiokit.send(eid, new)

if __name__ == "__main__":
    WebshotExpert.from_command_line().execute()
