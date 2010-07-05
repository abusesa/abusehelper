import commands
import re

__zcw_path__ = "/usr/local/bin/zcw"

class AbuseInfo():
    """
        Store Abuse Contact Info
    """
    abuseMail   = None
    countryCode = None
    countryName = None
    sourceName  = None
    networkName = None
    networkInfo = None
    ipRange     = None
    
    def __init__(self, string=None):
        if string != None:
            self.parse(string)
        return

    def parseAbuseMail(self, string):
        m = re.search('Abuse\s+E\-mail\s+:\s+(.+\@.+)', string)    
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def getAbuseMail(self, string=None):
        if string == None:
            return self.abuseMail
        else:
            return self.parseAbuseMail(string)

    def parseCountry(self, string):
        m = re.search('Country\s+:\s+(.+)\s+\((\w+)\)', string)
        if m != None and m.lastindex == 2:
            return [m.group(1), m.group(2)]
        return None

    def getCountryCode(self, string=None):
        if string == None:
            return self.countryCode
        else:
            return self.getCountry(string)[1]

    def getCountryName(self, string=None):
        if string == None:
            return self.countryName
        else:
            return self.getCountry(string)[0]
    
    def getCountry(self, string=None):
        if string == None:
            return [self.countryName, self.countryCode]
        else:
            country = self.parseCountry(string)
            if country != None and len(country) >= 2:
                self.countryName = country[0]
                self.countryCode = country[1]
                return[country[0], country[1]]
            else:
                return [None, None]

    def parseSource(self, string):
        m = re.search('Source\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def getSource(self, string=None):
        if string == None:
            return self.sourceName
        else:
            return self.parseSource(string)
 
    def parseNetworkName(self, string):
        m = re.search('Network\s+name\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def getNetworkName(self, string=None):
        if string == None:
            return self.networkName
        else:
            return self.parseNetworkName(string)

    def parseInfos(self, string):
        m = re.search('Infos\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def getInfos(self, string=None):
        if string == None:
            return self.networkInfo
        else:
            return self.parseInfos(string)

    def parseIPRange(self, string):
        p = 'IP\s+range\s+:\s+(?P<IP1>([0-2]?\d{1,2}\.){3}([0-2]?\d{1,2}))\s+\-\s+(?P<IP2>([0-2]?\d{1,2}\.){3}([0-2]?\d{1,2}))'
        m = re.search(p, string)
        if m != None:
            return [m.group('IP1'), m.group('IP2')]
        return None

    def getIPRange(self, string=None):
        if string == None:
            return self.ipRange
        else:
            return self.parseIPRange(string)

    def parse(self, string):
        self.abuseMail = self.parseAbuseMail(string)
        
        country = self.parseCountry(string)
        self.countryCode = country[0]
        self.countryName = country[1]
        
        self.networkName = self.parseNetworkName(string)
        self.networkInfo = self.parseInfos(string)
        self.ipRange = self.parseIPRange(string)
 
        self.sourceName = self.parseSource(string)
 

def searchAbuseInfo(ip):
    (status, output) = commands.getstatusoutput(__zcw_path__ + " " + ip)
    if status == 0:
        abuseInfo = AbuseInfo(output)
        return abuseInfo
    else:
        return None

