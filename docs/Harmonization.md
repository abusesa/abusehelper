# Data Harmonization Ontology

The purpose of this document is to harmonize the heterogenous data sets processed by different source bots into a unified ontology. The unified ontology represents the outcome of a pragmatic collaboration between different CSIRT teams such as [CERT-EU](http://cert.europa.eu/), [CERT-EE](http://www.cert.ee/), [CERT-FI](http://www.cert.fi/en/index.html), [CERT.AT](http://www.cert.at/), [CERT.PT](http://www.cert.pt/en/), [CERT.BE](https://www.cert.be/) and [Codenomicon](http://www.codenomicon.com), a commercial company. We also present a common set of principles to use for IOC attribution not directly available through the data sources. Each organization should define their own policy with reference to IOC elements and their related attribution. This document defines key IOC to be used as basis for communicating abuse events within and between organizations. In other words, the aim of this document is to shift the focus of formats, schemas and transports, to having a uniform ontology to use for passing serialized abuse events through AbuseHelper from a number of sources to a number of destinations.

## Core Elements

For an abuse report to be actionable and able to reach the right end recipient, various key elements need to be present. Please turn to the section Minimum Requirements below, to find out more about for the minimum requirements for an actionable abuse event. The core fields enumerated below identify a given abuse feed either by name or feed code should you choose to anonymize your sources. In addition, keys related to time or the identity of the abused resource be it an ip, url, an email address or a geolocation are considered core elements of an abuse report.

### Feed

 **feed** Lower case name for the feeder, e.g. abusech or phishtank.

 **feed code** Code name for the feed, e.g. DFGS, HSDAG etc.

 **feed url** The URL of a given abuse feed, where applicable.

### Time

All the timestamps should be normalized to UTC. If the source reports only a date, please do not invent timestamps.

 **source time** Time reported by a source. Some sources only report a date, which '''may''' be used here if there is no better observation.

 **observation time** The time a source bot saw the event. This timestamp becomes especially important should you perform your own attribution on a host DNS name for example. The mechanism to denote the attributed elements with reference to the source provided is detailed below in Reported Identity IOC.

N.B. a good way to represent timestamps is this [ISO 8601 combined date-time representation](http://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations): ```YYYY-MM-DD HH:MM:SSZ```. We have decided to omit the T for readability, since:

```
ISO 8601:2004(E). ISO. 2004-12-01. 4.3.2 NOTE: By mutual agreement of the partners in 
information interchange, the character [T] may be omitted in applications where there 
is no risk of confusing a date and time of day representation with others defined in 
this International Standard.
```

### Identity

The abuse type of an event defines the way these IOC needs to be interpreted. For a botnet drone they refer to the compromized machine, whereas for a command and control server they refer the server itself.

 **ip** IPv4 or IPv6 address.

 **domain name** DNS domain name. http://en.wikipedia.org/wiki/Domain_name

 **port** The port through which the abuse activity is taking place. For example a command and control server report will most likely contain a port, which is directly related to the reported ip or host.

 **url** A URL denotes an IOC, which refers to a malicious resource, whose interpretation is defined by the abuse type. A URL with the abuse type phishing refers to a phishing resource.

 **email address** An email address, whose interpretation is based on the abuse type.

 **reverse dns** Reverse DNS name acquired through a reverse DNS query on an IP address. N.B. "Record types other than PTR records may also appear in the reverse DNS tree." http://en.wikipedia.org/wiki/Reverse_DNS_lookup

 **asn** Autonomous system number.

 **as name** The registered name for an autonomous system.

 **bgp prefix** A CIDR for an autonomous system.

 **bgp prefix allocated** The date when a RIR such as RIPE NCC or ARIN allocated a given bgp prefix.

 **registry** The IP registry, RIR, a given ip address is allocated by.

### Source Identity

 **source ip** The ip observed to initiate the connection.

 **source port** The port from which the connection originated.

 **source domain name** A DNS name related to the host from which the connection originated.

 **source email address** An email address, which has been identified to relate to the source of an abuse event.

 **source asn** The autonomous system number from which originated the connection.

 **source as name** The autonomous system name from which the connection originated.
 
 **source cc** The country code of the ip from which the connection originated.

### Destination Identity

Since many of the sources report IOC related to a compromized machine, such as a botnet drone, they may report relevant information in relation to the command and control infrastructure as well. The meaning of each IOC needs to be interpreted with reference to the abuse type. A destination ip and port in the context of a botnet drone for example usually denote the command and control server.

 **destination ip** The end-point of the connection.

 **destination port** The destination port of the connection.

 **destination domain name** The DNS name related to the end-point of a connection.

 **destination email address** An email address, which has been identified to relate to the destiantion of an abuse event.

 **destination asn** The autonomous system number to which the connection was destined.

 **destination as name** The autonomous system name to which the connection was destined.

 **destination cc** The country code of the ip which was the end-point of the connection.

### Local Identity

 **local ip** Some sources report a internal (NATed) IP address related a compromized system.

 **local hostname** Some sources report a internal hostname within a NAT related to the name configured for a compromized system.

 **os name** Operating system name.

 **os version** Operating system version.

 **user agent** Some feeds report the user agent string used by the host to access a malicious resource, such as a command and control server.

### Reported Identity

As stated above, each abuse handling organization should define a policy, which IOC to use as the primary elements describing an abuse event. Often the sources have done their attribution, but you may choose to correlate their attributive elements with your own. In practice this means that your sanitation should prefix the elements with the '''reported''' keyword, to denote that you've decided the attribute these yourself. The list below is not comprehensive, rather than a list of common things you may want to attribute yourself. Moreover, if you choose to perform your own attribution, the observation time will become your authoritative point of reference related to these IOC.

 **reported ip** Should you perform your own attribution on a DNS name referred to by host, the ip reported by the source is replaced.

 **reported asn** The autonomous system number related to the resource, which was reported by the source.

 **reported as name**  The autonomous system name registered to the reported asn above.

 **reported cc** The country codeof the reported IOC above.

### Geolocation

We recognize that ip geolocation is not an exact science and analysis of the abuse data has shown that different sources attribution sources have different opinions of the geolocation of an ip. This is why we recommend to enrich the data with as many sources as you have available and make the decision which value to use for the cc IOC based on those answers.

 **cc** Each abuse handling pipeline, should define a logic how to assign a value for this key. You may decide to trust the opinion of a single source or apply logical operations on multiple sources. The country code is expressed as an ISO 3166 two letter country code.

 **country** The country name derived from the ISO 3166 country code (assigned to cc above).

 **longitude** Longitude coordinates derived from a geolocation service, such as MaxMind geoip db.

 **latitude** Latitude coordinates derived from a geolocation service, such as MaxMind geoip db.

 **region** Some geolocation services refer to region-level geolocation (where applicable).

 **state** Some geolocation services refer to state-level geolocation (where applicable).

 **city** Some geolocation services refer to city-level geolocation.

## Additional Elements

The idea behind the additional elements is to denote generic metadata about the abuse event, which complements the identity or temporal information about the victim, vulnerable service or a piece of criminal infrastructure. The purpose of this information is to give more context to the abuse type denoted byt the "type" key.

 **abuse contact** An abuse contact email address for an IP network.

 **additional information** All anecdotal information, which cannot be parsed into the data harmonization elements. This information is there to complement the description and give better insigt into the context. It may also clarify to the topic specific keys, which are not part of the core ontology.

 **comment** Free text commentary about the abuse event inserted by an analyst.

 **description** A free-form textual description of an abuse event.

 **description url** A description URL is a link to a further description of the the abuse event in question.

 **event hash** Computed event hash with specific keys and values that identify a unique event. At present, the hash should default to using the SHA1 function. Please note that for an event hash to be able to match more than one event (deduplication) the receiver of an event should calculate it based on a minimal set of keys and values present in the event. Using for example the observation time in the calculation will most likely render the checksum useless for deduplication purposes.

 **http request** Some feeders report http requests instead of URLs. They may call them URLs, but for the sake of interoperability with automation, they should be placed under "http request" key, since there is no guarantee that the protocol specification is http://.

 **malware** A malware family name in lower case.

 **missing data** If the sanitation is missing a known piece of data, such as a description url for example, the reference to this fact may be inserted here.

 **protocol** Used for (brute forcing) bots, e.g. vnc, ssh, sip, irc, http or p2p, as well as to describe the transport protocol of a given commmand and control mechanism. N.B. the interpretation of the protocol field depends largely on the abuse type. For some abuse types, such as brute-force, this refers to the application protocol, which is the target of the brute-forcing and for botnet drones it may refer to the transport protocol of the control mechanism for example. If both protocol and transport protocol are needed, they should be noted separately.

 **scan count** Most of the abuse events denote single instances of an observation such as a malware infection or command and control server observation. Some sources, however, present aggregate information over a period of time, such as a host scanning the Internet for open services to exploit. For the scanner type of activity there may be a need to communicate the number of ports, ips or domain names scanned by a single host during a period of time. The "scan count" is used to denote this number.

 **screenshot url** Some source may report URLs related to a an image generated of a resource without any metadata.

 **shareable key** Sometimes it is necessary to communicate a set of IOC which can be passed on freely to the end recipient. The most effective way to use this is to make it a multi-value within an event.

 **status** Status of the malicious resource (phishing URL, dropzone, c&c etc), e.g. online, offline.

 **target** Some sources denominate the target (organization) of a an attack.

 **tracking id** Some sources and applications use an identifier to denote a context for an abuse event. Previously, we denoted these with provider specific id keys, such as "rtir id", "misp id" and so on. Since traceability is the common communicative function, we have decided to bundle all these ids under the "tracking id" key. Please note that the purpose of the "tracking id" key is to link the event into an aggregate context. It is not a unique identifier for a single event. For this purpose you should use the "uuid" key instead.

 **transport protocol** Some feeds report a protocol, which often denotes the observed transport. This should be noted appropriately if the protocol key should denote the vulnerable service for example.

 **uuid** [AbuseSA](https://www.clarifiednetworks.com/AbuseSA) and AbuseHelper are using python uuids to identify abuse events. The python UUIDs are generated based on [RFC4122](http://tools.ietf.org/html/rfc4122) using the uuid.uuid4() function. Please note that the "uuid" serves a different communicative function than the "tracking id". The purpose of the uuid is to denote a unique identifier, which uniquely identifies a single event. 

 **webshot url** A URL pointing to resource, which has been rendered into a webshot, e.g. a PNG image and the relevant metadata related to its retrieval/generation.

### Artifact Elements

 **artifact hash** A string depicting a checksum for a file, be it a malware sample for example.

 **artifact hash type** The hashing algorithm used for artifact hash type above, be it MD5 or SHA-* etc. At the moment, it seems that the hash type should default to SHA-1.

 **artifact version** A version string for an identified artifact generation, e.g. a crime-ware kit.

## Classification Elements

Having a functional ontology to work with, especially for the abuse types is important for you to be able to classify, prioritize and report relevant actionable intelligence to the parties who need to be informed. Below, is a list of harmonized values for the abuse types we have observed in our quality assurance efforts and collaborating with our AbuseSA customers and the AbuseHelper community. The driving idea for this ontology has been to use a minimal set of values with maximal usability. 

 **type** The abuse type IOC is one of the most crucial pieces of information for any given abuse event. The main idea of dynamic typing is to keep our ontology flexible, since we need to evolve with the evolving threatscape of abuse data. In contrast with the static taxonomy below, the dynamic typing is used to perform business decisions in the abuse handling pipeline. Furthermore, the value data set should be kept as minimal as possible to avoid "type explosion", which in turn dilutes the business value of the dynamic typing. In general, we normally have two types of abuse type IOC: ones referring to a compromized resource or ones referring to pieces of the criminal infrastructure, such as a command and control servers for example.

 **taxonomy** We recognize the need for the CSIRT teams to apply a static (incident) taxonomy to abuse data. With this goal in mind the type IOC will serve as a basis for this activity. Each value of the dynamic type mapping translates to a an element in the static taxonomy. The European CSIRT teams for example have decided to apply the ENISA incident classification. The value of the taxonomy key is thus a derivative of the dynamic type above. For more information about the ENISA taxonomy, please turn to http://www.enisa.europa.eu/activities/cert/support/incident-management/browsable/incident-handling-process/incident-taxonomy/existing-taxonomies Please note that the taxonomy represented below has been adapted to map an abuse type value to a single taxonomy value.

|Type|Taxonomy|Description|
|----|--------|-----------|
|backdoor|Intrusions|This refers to hosts, which have been compromized and backdoored with a remote administration software or trojan in the traditional sense.|
|blacklist|Other|Some sources provide blacklists, which clearly refer to abusive behavior, such as spamming, but fail to denote the exact reason why a given identity has been blacklisted. The reason may be that the justification is anecdotal or missing entirely. This type should only be used if the typing fits the definition of a blacklist, but an event specific denomination is not possible for one reason or another.|
|botnet drone|Malicious Code|This is a compromized machine, which has been observed to make a connection to a command and control server.|
|brute-force|Intrusion Attempts|This IOC refers to a resource, which has been observed to perform brute-force attacks over a given application protocol. Please see the IOC protocol below.|
|c&c|Malicious Code|This is a command and control server in charge of a given number of botnet drones.|
|compromised server|Intrusions|This server or service has been compromised by a third party.|
|ddos infrastructure|Availability|This type refers to various parts of the technical DDoS infrastructure.|
|ddos target|Availability|This type refers to the intended target of a DDoS attack, i.e. the intended victim resource.|
|defacement|Intrusions|This IOC refers to hacktivism related activity.|
|dropzone|Information Content Security|This IOC refers to place where the compromized machines store the stolen user data.|
|exploit|Intrusion Attempts|An exploit is often executed through a malicious URL.|
|ids alert|Intrusion Attempts|IOCs based on a sensor network. This is a generic IOC denomination, should it be difficult to reliably denote the exact type of activity involved for example due to an anecdotal nature of the rule that triggered the alert.|
|malware|Malicious Code|A URL is the most common resource with reference to malware binary distribution.|
|malware configuration|Malicious Code|This is a resource which updates botnet drones with a new configuration.|
|phishing|Fraud|This IOC most often refers to a URL, which is phishing for user credentials.|
|ransomware|Malicious Code|This IOC refers to a specific type of compromized machine, where the computer has been hijacked for ransom by the criminals.|
|scanner|Information Gathering|This IOC refers to port scanning activity specifically.|
|spam infrastructure|Abusive Content|This IOC refers to resources, which make up a SPAM infrastructure, be it a harvester, dictionary attacker, URL etc.|
|test|Test|This is a value for testing purposes.|
|vulnerable service|Vulnerable|This attribute refers to a badly configured or vulnerable network service, which may be abused by a third party. For example, these services relate to open proxies, open dns resolvers, network time servers (ntp) or character generation services (chargen), simple network management services (snmp). In addition, to specify the network service and its potential abuse, one should use the protocol, destination port and description attributes for that purpose respectively.|

## Topic or Provider Specific Elements

Since the basic idea of an ontology is to specify a core language, which is able to communicate the relevant aspects of a topic in an effective manner, it leaves room for topic specific lexemes outside the generic terminology. In the context of abuse reporting, this is especially true with emerging trends, where a single source may start reporting on a topic and other follow suit. Previously, we listed some of these keys such as "dns version" or "notified by" as part of the ontology. At present, we have decided to leave them out of the ontology and only bring in terms, which represent a generic topic. This approach does not detract from the ontology or its communicative functions, since the core keys communicate the relevant aspects effectively. Topic or provider specific keys can thus be part of an event name space. The important thing is just to avoid collision with the core ontology name space. In other words, lopic or provider specific elements are the new emerging terms, which may become part of the ontology if they become adopted to describe a facet of a generic topic. For example above, we have decided to use the "cc" key as the authoritative country code denominator. For a given context, there may be other provider specific interpretations, which we have decided to prefix with the provider name. Example of such a prefix are "cymru cc" or "geoip cc", where the provider name is prepended to denote the source of this geolocation information.

## Minimum Requirements

Below, we have enumerated the minimum requirements for an actionable abuse event. These keys need to be present for the abuse report to make sense for the end recipient. Please note that if you choose to anonymize your sources, you can substitute **feed** with **feed code** and that only one of the identity keys **ip**, **domain name**, **url**, **email address** must be present. All the rest of the keys enumerated above are **optional**. Timestamps are essential to automated abuse reporting, so **source time** and **observation time** should both be present if possible.

|Category|Key|Terminology|
|--------|---|-----------|
|Feed|feed|Must|
|Classification|type|Must|
|Classification|taxonomy|Must|
|Time|observation time|Must|
|Time|source time|Must|
|Identity|ip|Must|
|Identity|domain name|Must|
|Identity|url|Must|
|Identity|email address|Must|
