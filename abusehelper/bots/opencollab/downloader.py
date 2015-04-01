"""
Downloads files, follows up redirection chains and saves server
headers and document contents to wiki.

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import os
import socket
import idiokit
import urllib2
import httplib
import email

from abusehelper.core import bot, events
from abusehelper.bots.experts.combiner import Expert
import abusehelper.core.utils as utils

from random import choice
from StringIO import StringIO
from hashlib import md5

from opencollab.wiki import GraphingWiki
from opencollab.wiki import WikiFailure
from opencollab.util.file import uploadFile

class RedirectLogger(urllib2.HTTPRedirectHandler):
    def __init__(self, *args, **kw):
        self.headers = dict()
        self.redirect_chain = dict()
        self.previous = str()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        path = req.get_host() + req.get_selector()
        path = path.rstrip('/')
        self.headers[path] = headers
        self.redirect_chain[self.previous] = path
        self.previous = path
        return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp,
                                                            code, msg,
                                                            headers, newurl)

def make_dict(attr_list):
    attr_dict = dict()
    for key, val in attr_list.items():
        attr_dict[key] = [str(val)]
    return attr_dict

# FIXME: copied here because utils.fetch_url does not give the url we
# ended up with after redirections etc.
@idiokit.stream
def fetch_url(url, opener=None, chunk_size=16384):
    if opener is None:
        opener = urllib2.build_opener()

    try:
        output = StringIO()

        fileobj = yield idiokit.thread(opener.open, url)
        result_url = str()
        try:
            while True:
                data = yield idiokit.thread(fileobj.read, chunk_size)
                if not data:
                    break
                output.write(data)
        finally:
            result_url = fileobj.geturl()
            fileobj.close()

        info = fileobj.info()
        info = email.parser.Parser().parsestr(str(info), headersonly=True)

        output.seek(0)

        idiokit.stop(info, output, result_url)
    except urllib2.HTTPError as he:
        raise utils.HTTPError(he.code, he.msg, he.headers, he.fp)
    except (urllib2.URLError, httplib.HTTPException, socket.error) as error:
        raise utils.FetchUrlFailed(str(error))

class DownloadExpert(Expert):
    collab_url = bot.Param()
    collab_user = bot.Param()
    collab_password = bot.Param()
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)
    collab_template = bot.Param(default=[""])
    user_agent = bot.Param(default=[""])
    referrer = bot.Param(default=[""])
    template = bot.Param(default=[""])

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.cache = dict()

        self.collab = GraphingWiki(self.collab_url,
                                   ssl_verify_cert=not self.collab_ignore_cert,
                                   ssl_ca_certs=self.collab_extra_ca_certs)
        self.collab.authenticate(self.collab_user, self.collab_password)

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("url",)))

    def upload_headers(self, opener, md5sum, info, data, result_url):
        result_page = result_url.split('://')[-1]
        for page in opener.headers:
            metas = make_dict(opener.headers[page])

            next_page = opener.redirect_chain.get(page, '')
            if next_page:
                metas['redirects to'] = ["[[%s]]" % (next_page)]
            else:
                metas['redirects to'] = ["[[%s]]" % (result_page)]

            result = self.collab.setMeta(page, metas, True, self.template)
            for line in result:
                self.log.info("%r: %r", page, line)

        metas = make_dict(info)

        metas['content'] = ['[[%s]]' % (md5sum)]
        result = self.collab.setMeta(result_page, metas, True, self.template)
        for line in result:
            self.log.info("%r: %r", result_page, line)

        page = md5sum
        metas = {'source url': ['[[%s]]' % (result_page)],
                 'content': ['[[attachment:content.raw]]']}
        result = self.collab.setMeta(page, metas, True, self.template)
        for line in result:
            self.log.info("%r: %r", page, line)

        for data, fname in [(data, "content.raw")]:
            if not data:
                continue
            try:
                self.log.info("Uploading file: %r (data %r...)",
                              fname, repr(data[:10]))
                status = uploadFile(self.collab, page, '', fname, data=data)
            except (IOError, TypeError, RuntimeError), msg:
                self.log.error("Upload failed: %r", msg)
                return

        return self.collab_url + result_page

    @idiokit.stream
    def augment(self, key):
        while True:
            eid, event = yield idiokit.next()

            for url in event.values(key):
                new = events.Event()

                logger = RedirectLogger()
                opener = urllib2.build_opener(logger)

                addheaders = list()
                refer = event.value('referrer', self.referrer)
                if refer:
                    addheaders.append(('Referrer', refer))
                user_agent = event.values('user-agent')
                if not user_agent:
                    user_agent = self.user_agent
                if user_agent:
                    user_agent = choice(user_agent)
                    addheaders.append(('User-agent', user_agent))
                if addheaders:
                    opener.addheaders = addheaders

                try:
                    self.log.info("Downloading %r", url)
                    info, fileobj, r_url = yield fetch_url(url, opener=opener)
                    data = fileobj.read()
                    md5sum = md5(data).hexdigest()
                    success = yield idiokit.thread(self.upload_headers, logger,
                                                      md5sum, info, data, r_url)
                    new.add("md5", md5sum)
                except utils.FetchUrlFailed, fuf:
                    new.add("download", "Failed to download")
                else:
                    new.add("download", success)

                yield idiokit.send(eid, new)

if __name__ == "__main__":
    DownloadExpert.from_command_line().execute()
