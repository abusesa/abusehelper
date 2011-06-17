# http://mynetwatchman.com/ListIncidentbyASSummary.asp

import xml.etree.cElementTree as etree
from idiokit import threado
from abusehelper.core import bot, events, utils

import httplib, urllib
from BeautifulSoup import BeautifulSoup

class netwatchmanbot(bot.PollingBot):
    asns = bot.ListParam("asns", default=[])

    # Really crappy fix for broken html and old versions of BS(<=3.1.0.1?) that fail to it
    def crappy_html_fix(self, html):
        html = '\n'.join(x for x in html.split('\n') if (not "'post' name='loginform'" in x) and not "iana.org/assignments/" in x)
        return html.replace("_blank''>", "_blank'>")


    @threado.stream
    def url_to_soup(inner, self, url):
        try:
            self.log.info('Downloading page from: "%s"', url)
            _, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, e:
            self.log.error('Failed to download page "%s": %r', url, e)
	    return

	response = self.crappy_html_fix(fileobj.read()) 
	soup = BeautifulSoup(response)
	inner.send(soup)

    def normalize(self, text):
        text = text.replace("\n"," ")
        text  = ' '.join( text.split()) # remove double-spacing

	dic = {"AttackerIp2":"ip","Target IP":"target"}
	for i, j in dic.iteritems():
	    if text == i:
	        text = j
	return text.strip()


    @threado.stream
    def poll(inner,self, asn):
        yield

        sites1 = []
        sites2 = []


	# Incident Lookup by AS Number
	params = urllib.urlencode({'origAS': asn, 'SUBMIT': 'SUBMIT'})
	headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

	conn = httplib.HTTPConnection("mynetwatchman.com:80")
	conn.request("POST", "/ListIncidentbyASSummary.asp", params, headers)
	data = conn.getresponse().read()
	data = self.crappy_html_fix(data)
	soup = BeautifulSoup(data)
	conn.close()

	soup = soup.find('table', border="1", bgcolor=None)
	if soup==None: return

	for urls in soup.findAll('a',target="_blank"):
	    if urls.contents[0] != "0":
	        sites1.append(urls['href'])

	# Incidents by IP Range
	for site in sites1:
	    soup = yield self.url_to_soup("http://mynetwatchman.com/"+site)
	    soup = soup.find('table', border="1", bgcolor=None)
	    if soup == None: break

	    for urls in soup.findAll('a',target="_blank"):
	        sites2.append(urls['href'])

	# Incident Details
	for site in sites2:
	    details = {"asn":asn}
            soup = yield self.url_to_soup("http://mynetwatchman.com/"+site)

	    for s in soup.find('table', border="1", bgcolor="ivory").findAll('td'):
	        if s != None and s.input != None:
                    details[ self.normalize(s.input["name"]) ]= self.normalize(s.input["value"])

            event = events.Event()
            event.add("feed", "netwatchman")

	    soup = soup.find(text='Most Recent Event')
	    if soup == None:
	        event.add("Problem with parsing site: ", site)
		inner.send(event)
		continue

	    names  = soup.findNext("tr").findAll("th")
	    values = soup.findAllNext("td")
	
	    for i in range(0, min(len(names), len(values)) ):
	        names[i]  = ' '.join( names[i].findAll(text=True))
	        values[i] = ' '.join(values[i].findAll(text=True))	
	        details[ self.normalize(names[i]) ] = self.normalize(values[i])
	

	    for key in details:
                event.add(key, details[key])

            inner.send(event)

    def feed_keys(self, asns=(), **keys):
        for asn in asns:
	        yield (str(asn),)

if __name__ == "__main__":
    netwatchmanbot.from_command_line().run()
