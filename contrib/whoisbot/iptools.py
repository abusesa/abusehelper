import commands
import re
import time
import string
import pgdb

__zcw_path__ = "/usr/local/bin/zcw"


class AbuseInfo(object):
    """
        Store Abuse Contact Info
    """

    # !! Use carrefully the possibility to set internal dict !!
    def __init__(self, dict=None):
        self._abuseinfo = {}

        if(dict is None):
            self._abuseinfo["abuseMail"]   = None
            self._abuseinfo["countryCode"] = None
            self._abuseinfo["countryName"] = None
            self._abuseinfo["sourceName"]  = None
            self._abuseinfo["networkName"] = None
            self._abuseinfo["networkInfo"] = None
            self._abuseinfo["ipRange"]     = None
            self._abuseinfo["customer"]    = None
            self._abuseinfo["asn"]         = None
            self._abuseinfo["asname"]      = None
            self._abuseinfo["acronym"]     = None
        else:
            self._abuseinfo = dict

    def __setKey(self, key, value):
        self._abuseinfo[key] = value

    def __getValue(self, key):
        if key in self._abuseinfo:
            return self._abuseinfo[key]
        else:
            return None 

    def getAbuseMail(self):
        return self.__getValue("abuseMail")

    def setAbuseMail(self, value):
        self.__setKey("abuseMail", value)

    def getCountryCode(self):
        return self.__getValue("countryCode")

    def setCountryCode(self, value):
        self.__setKey("countryCode", value)
    
    def getCountryName(self):
        return self.__getValue("countryName")

    def setCountryName(self, value):
        self.__setKey("countryName", value)

    def getSourceName(self):
        return self.__getValue("sourceName")

    def setSourceName(self, value):
        self.__setKey("sourceName", value)

    def getNetworkName(self):
        return self.__getValue("networkName")

    def setNetworkName(self, value):
        self.__setKey("networkName", value)

    def getNetworkInfo(self):
        return self.__getValue("networkInfo")

    def setNetworkInfo(self, value):
        self.__setKey("networkInfo", value)

    def getIPRange(self):
        return self.__getValue("ipRange")

    def setIPRange(self, value):
        self.__setKey("ipRange", value)

    def getCustomer(self):
        return self.__getValue("customer")

    def setCustomer(self, value):
        self.__setKey("customer", value)

    def getASN(self):
        return self.__getValue("asn")

    def setASN(self, value):
        self.__setKey("asn", value)

    def getASName(self):
        return self.__getValue("asname")

    def setASName(self, value):
        self.__setKey("asname", value)

    def getAcronym(self):
        return self.__getValue("acronym")

    def setAcronym(self, acronym):
        return self.__setValue("acronym", value)

    def getAll(self):
        return self._abuseinfo

    abuseMail = property(getAbuseMail, setAbuseMail, None, "abuseMail")
    countryCode = property(getCountryCode, setCountryCode, None, "countryCode")
    countryName = property(getCountryName, setCountryName, None, "countryName")
    sourceName = property(getSourceName, setSourceName, None, "sourceName")
    networkName = property(getNetworkName, setNetworkName, None, "networkName")
    networkInfo = property(getNetworkInfo, setNetworkInfo, None, "networkInfo")
    ipRange = property(getIPRange, setIPRange, None, "ipRange")
    customer = property(getCustomer, setCustomer, None, "customer")
    asn = property(getASN, setASN, None, "asn")
    asname = property(getASName, setASName, None, "asname")
    acronym = property(getAcronym, setAcronym, None, "acronym")


class ZCWWhois():
    """
        This class uses the ZCW tool to query
        abuse WHOIS to retrieve abuse info related
        to some IP address
    """

    def parseAbuseMail(self, string):
        m = re.search('Abuse\s+E\-mail\s+:\s+(.+\@.+)', string)    
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def parseCountry(self, string):
        """
            Parse country information
            Return an array where the 1st element is the country name
            and the 2nd element is the country code
        """
        m = re.search('Country\s+:\s+(.+)\s+\((\w+)\)', string)
        if m != None and m.lastindex == 2:
            return [m.group(1), m.group(2)]
        return None

    def parseSource(self, string):
        m = re.search('Source\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    def parseNetworkName(self, string):
        m = re.search('Network\s+name\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    #TODO: fix this method to support multi-line infos
    def parseInfos(self, string):
        m = re.search('Infos\s+:\s+(.+)', string)
        if m != None and m.lastindex == 1:
            return m.group(1)
        return None

    #TODO: IPv6 support?
    def parseIPRange(self, string):
        p = 'IP\s+range\s+:\s+(?P<IP1>([0-2]?\d{1,2}\.){3}([0-2]?\d{1,2}))\s+\-\s+(?P<IP2>([0-2]?\d{1,2}\.){3}([0-2]?\d{1,2}))'
        m = re.search(p, string)
        if m != None:
            return [m.group('IP1'), m.group('IP2')]
        return None

    def parse(self, string):
        ai = AbuseInfo()

        #Fill AbuseInfo object
        ai.abuseMail = self.parseAbuseMail(string)
        country = self.parseCountry(string)
        if(country is not None):
            ai.countryName = country[0]
            ai.countryCode = country[1]
        ai.networkName = self.parseNetworkName(string)
        ai.networkInfo = self.parseInfos(string)
        ai.ipRange = self.parseIPRange(string)
        ai.sourceName = self.parseSource(string)
        return ai

    def queryWhois(self, ip):
        (status, output) = commands.getstatusoutput(__zcw_path__ + " " + ip)
        if status == 0:
            abuseInfo = self.parse(output)
            return abuseInfo
        else:
            return None

    def getAbuseInfo(self, ip):
        return self.queryWhois(ip)
 

class CymruWhois():
    """
        This class uses the command line whois tool to query Team Cymru WHOIS
        to link an IP address with the ASN / ASName
    """

    def queryWhois(self, ip):
        """
            Convert an IP to a tuple [ASN, ASName] where ASN is an integer and ASName a string.
            The method uses whois.cymru.com to search this information.

            Hypothesis:
                - the whois return 2 line separeted by the standard '\n' character
                - the 2nd line contains ASN | IP | ASName with the character '|' for as separator

            Accepted values:
                - IPv4 / IPv6 address and ranges (with our without the netmask info)
        """
        ip = string.split(ip, "/")[0] #remove the mask
        (status, output) = commands.getstatusoutput("whois  -h whois.cymru.com" + " " + ip)
        if status == 0:
            # The output has the following format
            # AS      | IP               | AS Name
            # 2611    | 193.191.11.137   | BELNET AS for BELNET, The Belgian National Research and Education Network
            # 2nd line is interesting and we could split on the '|' char
            result = string.split(output, "\n")
            if(len(result) > 1):
                header = result[0]
                content = result[1]
                infos = string.split(content, "|")
                if(len(infos) == 3):
                    [asn, ip, asname] = infos
                    return [int(asn), string.strip(asname)]
        return None

    def getAbuseInfo(self, ip):
        infos = self.queryWhois(ip)
        if infos is not None:
            [asn, asname] = infos
            ai = AbuseInfo() 
            ai.asn = asn
            ai.asname = asname
            return ai
        else:
            return None

class SQLWhois():

    connection = None
    #SQL Queries
    __select_all = """     SELECT IPRanges.range, 
                                  IPRanges.netname, 
                                  IPRanges.asn,
                                  IPRanges.acronym,
                                  ASN.asname, 
                                  ASN.email,
                                  ASN.country_code, 
                                  Country.name 
                            FROM Country, ASN, IPRanges 
                            WHERE IPRanges.range >>= %s;
                        """
    __insert_asn__ = "INSERT INTO ASN (asn, asname, country_code, email) VALUES ( %d, %s , %s , %s );"
    __insert_organisation__ = "INSERT INTO Organisation (acronym, name, asn) VALUES ( %s, %s, %d );"
    __insert_ipranges__ = "INSERT INTO IPRanges (range, asn, netname, acronym, email) VALUES ( %s, %d, %s, %s, %s );"
    __insert_contact__ = "INSERT INTO Contact (fname, lname, email, phone, acronym) VALUES ( %s, %s, %s, %s, %s );"
    __select_asn__ = "SELECT asname FROM ASN WHERE ASN = %d;"
    __select_organisation__ = "SELECT acronym FROM Organisation WHERE acronym = %s;"
    __select_iprange__ = "SELECT range FROM IPRanges WHERE range = %s;"
    __select_contact__ = "SELECT fname, lname FROM Contact WHERE fname = %s AND lname = %s;"

    def executeAndCommit(self, query, *values):
        '''
            Execute the query given in parameter and commit transaction
        '''
        cursor = self.connection.cursor()
        cursor.execute(query, values)
        self.connection.commit()

    def executeAndReturnResult(self, query, *values):
        cursor = self.connection.cursor()
        cursor.execute(query, values)
        try:
            result = cursor.fetchall()
            return result
        except:
            return None

    def containsRow(self, query, *values):
        result = self.executeAndReturnResult(query, *values)
        if result == None or len(result) <= 0:
            return False
        else:
            return True

    def containsASN(self, asn):
        return self.containsRow(self.__select_asn__, asn)

    def containsOrganisation(self, acronym):
        return self.containsRow(self.__select_organisation__, acronym)

    def containsIPRange(self, iprange):
        if type(iprange) == list: 
            for range in iprange:
                if self.containsRow(self.__select_iprange__, range):
                    return True
        elif type(iprange) == str:
            return self.containsRow(self.__select_iprange__, range)
        return False

    def containsContact(self, fname, lname):
        return self.containsRow(self.__select_contact__, fname, lname)

    def getAllInfoForIP(self, ip):
        result = self.executeAndReturnResult(__select_all__, ip)
        if result == None or len(result) <= 0:
            return False
        else:
            return result[0]

    def insertASN(self, asn, asname, country_code, email):
        self.executeAndCommit(self.__insert_asn__, asn, asname, country_code, email)

    def insertOrganisation(self, acronym, name, asn):
        self.executeAndCommit(self.__insert_organisation__, acronym, name, asn)

    def insertIPRange(self, range, asn, netname, acronym, email):
        self.executeAndCommit(self.__insert_ipranges__, range, asn, netname, acronym, email)

    def insertContact(self, fname, lname, email, phone, acronym):
        self.executeAndCommit(self.__insert_contact__, fname, lname, email, phone, acronym)

    def close(self):
        self.connection.close()

    def storeAbuseInfo(self, ai):
        """
            Complete the database with information stored in ai object.
            Only update ASN and IPRange tables.  Information stored in Contacts
            and Organisation are supposed to be manually imported from Belnet CRM
            or any other information source available for the CERT
        """
        if(not self.containsASN(ai.asn)): 
            self.insertASN(ai.asn, ai.asname, ai.countryCode, ai.abuseMail)

        if(not self.containsIPRange(ai.ipRange)):
            self.insertIPRange(ai.ipRange, ai.asn, ai.networkName, ai.acronym, ai.abuseMail)

        return True    

    def getAbuseInfo(self, ip):
        if(self.containsIPRange(ip)):
            infos = self.getAllInfoForIP(ip)
            [range, netname, asn, asname, email, country_code, country_name] = infos

            abuseinfo = {}
            abuseinfo["abuseMail"]   = email
            abuseinfo["countryCode"] = country_code
            abuseinfo["countryName"] = country_name
            abuseinfo["networkName"] = netname
            abuseinfo["ipRange"]     = range
            abuseinfo["customer"]    = acronym
            abuseinfo["asn"]         = asn
            abuseinfo["asname"]      = asname
            return AbuseInfo(abuseinfo)
        else:
            return None

class PostgreSQLWhois(SQLWhois):

    def __init__(self, srv, db, usr, pwd):
        self.connection = pgdb.connect(srv + ":" + db + ":" + usr + ":" + pwd)

class IPTools():
    pgsql = None
    zcw   = None
    cymru = None
    
    def __init__(self, dbsrv=None, dbname=None, dbusr=None, dbpwd=None):
        self.cymru = CymruWhois()
        self.zcw = ZCWWhois()
        if(dbsrv is not None and dbname  is not None and dbusr is not None and dbpwd is not None):
            self.pgsql = PostgreSQLWhois(dbsrv, dbname, dbusr, dbpwd)
        return
 
    def lookup(self, ip):
        #try to query SQL backend
        #if something go wrong, let query other sources
        if(self.pgsql is not None):
            try:
                abuseInfo = self.__sqlSearchAbuseInfo(ip)
            except:
                abuseInfo = None
        #queries to other sources if no answer found
        #in SQL DB or something wrong previously
        if(abuseInfo is None):
            zcwAI = self.__zcwSearchAbuseInfo(ip)
            cymruAI = self.__cymruSearchAbuseInfo(ip)
            ai = self.__mergeAbuseInfo(zcwAI, cymruAI)
            if(self.pgsql is not None):
                try:
                    self.__sqlAddAbuseInfo(ai)
                except:
                    return ai
            return ai

    def __sqlSearchAbuseInfo(self, ip):
        if(self.pgsql is not None):
            return self.pgsql.getAbuseInfo(ip)
        else:
            return None

    def __sqlAddAbuseInfo(self, ai):
        if(self.pgsql is not None):
            return self.pgsql.storeAbuseInfo(ai)
        else:
            return False

    def __zcwSearchAbuseInfo(self, ip):
        return self.zcw.getAbuseInfo(ip)

    def __cymruSearchAbuseInfo(self, ip):
        return self.cymru.getAbuseInfo(ip)

    def __mergeAbuseInfo(self, info1, info2):
        if(info1 is None):
            return info2
        elif(info2 is None):
            return info1
        else:
            info1Dic = info1.getAll()
            info2Dic = info2.getAll()

            for k in info1Dic.keys():
                if info1Dic[k] is None and k in info2Dic and info2Dic[k] is not None:
                    info1Dic[k] = info2Dic[k]
            return AbuseInfo(info1Dic)
        return None
 
# for compatibility with previous release   
def searchAbuseInfo(ip):
    iptools = IPTools()
    return iptools.lookup(ip)

