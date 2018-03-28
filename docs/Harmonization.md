# Data Harmonization Ontology (TLP White)

What is data harmonization? What is an ontology? The purpose of this document is to help you better deal with the complexity that arises from processing threat intelligence from heterogeneous sources. Data harmonization is a contract to always call the same things by the same name and not to call different things by the same name, viz. an IP address is always referred to as an **ip** and a functional **type** always represents a functional classification of abuse, vulnerability or policy violation.

With data harmonization covered briefly, we move on to defining an ontology. An ontology in our case is a higher level abstraction of a language, where each lexeme addresses an observable characteristic of either an Indicator of Compromise (IOC), a vulnerable service discovered through actively scanning the Internet or policy violation defined by an information security policy. Our grammar is thus expressed as sets of key-value pairs, which are straightforward to serialize into events.

We reference events as collections of ontology driven key-value pairs. Please note that we use the term **key** to denote an event schema and the term **attribute** to denote an ontology lexeme.

## Ontology, Schema or Taxonomy

As stated above, an ontology is a higher level abstraction of the semantic characteristics of an observable item. A schema, on the other hand, is a technical contract to transfer or store data in a prescribed format. Both are needed, but we see schemas as derivatives of an underlying semantic representation, which for our purposes is an ontology. In contrast with hierarchical taxonomies, an ontology allows for lexemes outside the core language, provided the definition does not duplicate or redefine that of an already established one. This  calls for harmonization. Consequently, the traditional way of dealing with the unknown in taxonomies has been the introduction of the **other** category, which simply fails over time. We have worked to avoid this here.

# Core Attributes

For an abuse, vulnerable service or policy violation event to be actionable and able to reach the right end recipient, various keys need to be present and defined in the correct manner.

## Feed Attributes

|attribute|description|
--- | --- |
|feed|Lower case name for the feed, e.g. phishtank.|
|feed code|Alternative code name for the feed in case it cannot be shared e.g. dgfs, hsdag etc.|
|feeder|Name of the organization providing one or more data feeds, e.g. shadowserver.|
|feed url|The URL of a given abuse feed, where applicable.|
|source|Often a feed may be a collection of events from various sources. In this case it may be prudent to identify the different sources of which the feed is comprised.

## Time

All time stamps should be normalized to UTC. If the source reports only a date, you should not invent a time stamp.

|attribute|description|
--- | --- |
|observation time|The time a source bot saw the event. This timestamp becomes especially important should you perform your own attribution on a host DNS name. The mechanism to denote the attributed elements with reference to the source provided is detailed below under Reported Identity.|
|source time|Time reported by a source. Some sources only report a date, which may be used here if there is no better observation.|

A good way to represent timestamps is this [ISO 8601 combined date-time representation](http://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations): ```YYYY-MM-DD HH:MM:SSZ```. We have omitted the T for readability, since:

"By mutual agreement of the partners in information interchange, the character [T] may be omitted in applications where there is no risk of confusing a date and time of day representation with others defined in this International Standard." (ISO 8601:2004(E). ISO. 2004-12-01. 4.3.2 NOTE)

## Identity

The abuse type of an event defines the way an IOC needs to be interpreted. For a botnet drone it refers to the compromised machine, whereas for a command and control server it refers the server itself.

|attribute|description|
--- | --- |
|as name|The registered name for an autonomous system.|
|asn|Autonomous system number.|
|bgp prefix allocated|The date when a Regional Internet Registry (RIR) such as RIPE NCC or ARIN allocated a given BGP prefix.|
|bgp prefix|A CIDR associated to an autonomous system.|
|domain name|DNS domain name. http://en.wikipedia.org/wiki/Domain_name|
|email address|An email address, the interpretation of which is based on the abuse type.|
|ip|IPv4 or IPv6 address.|
|port|The port through which the abuse activity is taking place. For example a command and control server report will most likely contain a port which is directly related to the reported IP or host.|
|registry|The IP registry, RIR, whcih allocated a given IP address.|
|reverse dns|A Reverse DNS name acquired through a reverse DNS lookup on an IP address. Note: Record types other than PTR records may also appear in the reverse DNS tree. http://en.wikipedia.org/wiki/Reverse_DNS_lookup|
|url|A URL denotes an IOC, which refers to a malicious resource, whose interpretation is defined by the abuse type. A URL with the abuse type phishing refers to a phishing resource.|

### Source Identity

|attribute|description|
--- | --- |
|source as name|The autonomous system name from which the connection originated.|
|source asn|The autonomous system number from which originated the connection.|
|source cc|The country code of the IP from which the connection originated.|
|source domain name|A DNS name related to the host from which the connection originated.|
|source ip|The IP observed to initiate the connection.|
|source port|The port from which the connection originated.|

### Destination Identity

Since many of the feeds report events related to a compromised machines (such as a botnet drones), the feeds may report relevant information about the command and control infrastructure as well. The meaning of each event needs to be interpreted with reference to the abuse type. In the context of a botnet drone, for example, a destination IP and port usually denotes the command and control server.

|attribute|description|
--- | --- |
|destination as name|The autonomous system name of the destination of the connection.|
|destination asn|The autonomous system number of the destination of the connection.|
|destination cc|The country code of the IP which was the end-point of the connection.|
|destination domain name|The DNS name related to the end-point of a connection.|
|destination ip|The end-point of the connection.|
|destination port|The destination port of the connection.|

### Local Identity

|attribute|description|
--- | --- |
|os name|Operating system name.|
|os version|Operating system version.|
|user agent|Some feeds report the user agent string used by the host to access a malicious resource, such as a command and control server.|
|username|A username of a user account.|

### Reported Identity

Each abuse handling organization should define a policy which outlines those attributes used as primary elements of an observation. Often the source feeds perform their own attribution but you may choose to correlate their attributive elements against your own or those of a third party. In practice, this means that your harmonization process should prefix the keys with the **reported** keyword, to denote that you have decided to perform the attribution on your own. The list below is not comprehensive; rather it is a list of common things you may want to observe yourself. Moreover, if you choose to perform your own attribution, the **observation time** will become your authoritative point of reference in relation to the new attributes.

|attribute|description|
--- | --- |
|reported as name|The autonomous system name registered to the reported ASN.|
|reported asn|The autonomous system number related to the resource which was reported by the source feed.|
|reported cc|The country code of the reported IP.|
|reported ip|Should you perform your own attribution on a DNS name referred to by host, the IP reported by the source feed is replaced.|

### Geolocation

We acknowledge IP geolocation is not an exact science, and our analysis has shown that attribution sources have varying opinions about the physical location of an IP address at a given time. This is why we recommend to augment the data with as many sources as you have available and make a decision which source to use for the country code (cc) attribute based on those answers.

|attribute|description|
--- | --- |
|cc|Each abuse handling pipeline should define a logic how to assign a value for the cc key. You may decide to trust the opinion of a single source or apply logical operations on multiple sources. The country code is expressed as an ISO 3166 two-letter country code.|
|city|Some geolocation services refer to city-level geolocation.|
|country|The country name derived from the ISO 3166 country code (assigned to cc above).|
|latitude|Latitude coordinate derived from a geolocation service such as the MaxMind GeoIP database.|
|longitude|Longitude coordinate derived from a geolocation service such as the MaxMind GeoIP database.|

## Additional Attributes

The idea behind the additional attributes is to present generic event metadata which complements the identity or temporal information about the victim, vulnerable service or a piece of compromised infrastructure. In addition, the purpose of this information is to give more context to the abuse type denoted by the **type** attribute.

|attribute|description|
--- | --- |
|abuse contact|An abuse contact email address for an IP network.|
|additional information|Sometimes it may be necessary to relay a an additional piece of information to the report recipient related to the specific context at hand. So in a sense it is a placeholder for useful context dependent information, which would be otherwise difficult to convey without changing the schema.|
|comment|Free text commentary about the abuse event augmented by an analyst.|
|description url|A description URL is a link to a further description of threat in question.|
|description|A free-form textual description of an abuse or vulnerable service event.|
|http request|Some feeders report HTTP requests instead of URLs. The feeders may call them URLs but for the sake of interoperability with automation, such events should be placed under the "http request" key as there is no guarantee that the protocol specification is HTTP.|
|malware family|A malware family name, in lower case.|
|missing data|If the harmonization is missing a known piece of data (such as an **ip** for example), the reference to this fact may be inserted here.|
|protocol|The protocol attribute describes the application protocol on top of the transport which relates to the observed abuse or vulnerable service; that is, "protocol=ssh" for SSH brute-force attacks is more descriptive than "protocol=tcp". In this case the transport protocol should be referenced by that key, "transport protocol=tcp".|
|source|Aggregated feeds use indicators not obtained directly from the feeder. Some aggregated feeds report a source of this external information. This key can be used to denote those external feeder entities, such as in the case of blacklist aggregation. Note the source is external to a feeder or their feed offering.|
|status|Observed status of the malicious resource phishing URL, dropzone, command and control server; for example, online, offline.|
|target|Some sources such as phishing feeds designate the target of a phishing campaign.|
|tracking id|Some sources and applications use an identifier to denote a context for an abuse event. We previously denoted these with provider specific ID keys, such as "rtir id", "misp id" and so on. Since traceability is the common communicative function, we have bundled all these IDs under the tracking id key. Please note that the purpose of this key is to link the event into an aggregate context. It is not a unique identifier for a single event. For this purpose you should use the "uuid" key instead.|
|transport protocol|Some feeds report a protocol denoting the observed transport (for example, tcp, udp). This should be recorded appropriately should the protocol attribute denote the protocol of a vulnerable service.|
|uri|For various technical reasons feeders often present URI references in their feeds instead of URLs. A URI reference is sometimes missing the scheme element, even if the authority and path elements are present as defined by the RFC3986. For brevity, we use the uri attribute to denote URIs and URI references.|
|uuid|The purpose of the uuid is to denote a unique identifier, which uniquely identifies a single event. [AbuseSA](http://www.abusesa.com) and AbuseHelper use python UUIDs to identify abuse events. The python UUIDs are generated using the uuid.uuid4() function, based on [RFC4122](http://tools.ietf.org/html/rfc4122). Note that "uuid" serves a different function than the tracking id.|
|vulnerability|Sometimes it is necessary to provide a short description of a vulnerable service reported by a source feed. This helps in correlating the vulnerabilities across sources.|

### Artifact Attributes

Host-based artifacts play a role in incident handling, and having a means to relay these in a uniform manner through automation is essential. At present, we identify two main categories for artifacts:

 * hashes of malicious content
 * rule-based descriptions of malicious content.

|attribute|description|
--- | --- |
|artifact content|A formal or rule-based description of malicious content.|
|artifact content type|Formal description type for the artifact content in question, e.g. a Yara rule or a Suricata rule.|
|artifact hash|A string depicting a checksum or hash of a file, be it a malware or other sample.|
|artifact hash type|The hashing algorithm used for artifact hash type above, such as MD5 or SHA-* etc.|

## Classification Attributes

It is important to be able to classify, prioritize and report relevant actionable intelligence to parties who need to be informed; working with a functional ontology, especially for abuse types, is essential for this. A list of harmonized values for the **threat types** we have observed in our quality assurance efforts and collaborating with our AbuseSA customers and the AbuseHelper community is presented below. The driving idea for this ontology has been to use a minimal set of values with maximal usability. 

|attribute|description|
--- | --- |
|threat type|At present, we have three threat types present in the data: **ioc** (Indicators of Compromise), **vulnerable service**s and **policy violation**s. Moreover, indicators may be further categorized on a functional level into **victim**s and **infrastructure**s. Note that the threat type may very well be a multi-value attribute, for example "threat type=ioc" or "threat type=infrastructure". At a minimum we should tag an event with a single threat type to aid in automated decision making.|
|type|The "type" attribute is one of the most crucial pieces of information for any given threat event. The main idea of dynamic typing is to keep our ontology flexible, as we need to evolve with the evolving threat landscape presented through the data. Furthermore, the values set for the type attribute should be kept to a minimum to avoid a **type explosion**, which in turn dilutes the business value of dynamic typing.|

### Threat Type Values

The idea behind the **threat type** tagging is to enable abuse or incident handlers to automate semantic filtering based on the observation type in question. In practice, distinguishing between abuse, vulnerable services, policy violations or victims will help when writing rules to triage the events into the needed buckets. As we are talking about tagging, a single event may be tagged with multiple tags. For example, a botnet drone observation will most likely need to be tagged as victim and abuse; it is unlikely a victim of a DDoS attack will have been compromised, so the observation would be that of a victim.

|attribute|description|
--- | --- |
|infrastructure|Infrastructure indicators, such as command and control observations should be tagged with this threat type.|
|ioc|All abuse type events must be tagged with this threat type.|
|policy violation|Observations which do not directly qualify as abuse but are against a policy.|
|victim|Botnet drone observations should be tagged with this threat type.|
|vulnerable service|All vulnerable network service observations must be tagged with this threat type.|

### Type Values

The **type** values offer a data-backed taxonomy for classifying abuse and vulnerable network service observations in a uniform manner. A concise yet functional classification system enables you to make informed decisions about the state of your network estate in real-time.

|attribute|description|
--- | --- |
|artifact|Artifacts refer to host-based indicators, such as checksums, file paths.|
|attribution|Indicators which can be attributed to malicious activity without a specific functional category such as a command and control server.|
|backdoor|Backdoor indicators refer to hosts which have been compromised and/or backdoored by a third party.|
|blacklist|Some sources provide blacklists which clearly refer to abusive behavior (such as spamming) but fail to denote the exact reason why a given identity has been blacklisted. The justification may be anecdotal or missing entirely. This type should only be used if the typing fits the definition of a blacklist, but an event specific denomination is not possible for one reason or another.|
|botnet drone|The most numerous type of abuse, as it refers to compromised computers calling out to a command and control mechanism.|
|brute-force|A machine which has been observed to perform brute-force attacks over a given application protocol, e.g. ssh|
|c&c|A command and control server in charge of a given number of botnet drones.|
|compromised account|A user account which has been compromised byt a third party.|
|compromised server|This server or service has been compromised by a third party.|
|ddos infrastructure|This type refers to various parts of DDoS botnet infrastructure.|
|ddos target|This type refers to the intended target of a DDoS attack: the intended domain name or IP address.|
|defacement|This type refers to hacktivism, which on a technical level is an indicator of a compromised service.|
|dropzone|This type refers to a resource which is used to store stolen user data.|
|exploit url|An exploit or an exploit kit is often served through a malicious URL.|
|ids alert|Alerts from a heuristic sensor network. This is a generic classification, as often the taxonomy of these types of events lack consistency.|
|malware configuration|This is a resource which updates botnet drones with a new configurations.|
|malware url|A URL is the most common resource with reference to malware binary distribution.|
|phishing|This type most often refers to a URL which is trying to defraud the users of their credentials.|
|ransomware|This type refers to a specific type of compromised machine, where the computer has been hijacked for ransom by the criminals.|
|scanner|This type refers to port or vulnerability scanning attempts in general.|
|spam infrastructure|This type refers to resources which make up a spammer's infrastructure, be it a harvester, dictionary attacker, URL, spam etc.|
|test|Used for testing purposes.|
|vulnerable service|This type refers to poorly configured or vulnerable network service, which may be abused by a third party. For example, these services relate to open proxies, open DNS resolvers, network time servers (NTP), character generation services (CharGen) or simple network management services (SNMP). In addition, to specify the network service and its potential abuse, one should also use the protocol, port and description attributes.|

## Topic- or Provider-Specific Attributes

The basic premise of an ontology is to specify a core language which is able to communicate the relevant aspects of a topic in an effective manner. This leaves room for topic-specific lexemes outside the generic terminology; this is especially true in the context of reporting emerging trends, where a single source may start reporting on a topic and other follow suit. As part of the ontology we listed some of these keys previously as "dns version" or "notified by".

We have decided to leave them out of the ontology and only bring in terms which represent a generic topic. This approach does not detract from the ontology nor its communicative functions, as the core keys communicate the relevant aspects effectively. Topic- or provider-specific keys can thus be part of an event name space.

The important thing is to avoid collision with the core ontology name space. In other words, topic- or provider-specific keys are new emerging attributes which may in time become part of the ontology if they are adopted to describe a facet of a generic topic. For example, we have decided to use the "cc" key above as the authoritative country code denominator.

For a given context there may be other provider specific interpretations which we have prefixed with the provider name; examples are "cymru cc" or "geoip cc", where the provider name is prepended to denote the source of this geolocation information.

## Harmonization Best Practices

There are many things you have to take into account when harmonizing heterogeneous datasets. The established attributes in this ontology should help you on your way when dealing with topic- or provider-specific attributes. In general, the attribute names should be **lower case** and use white space, " ", instead of underscores, "\_"; for example, "DNS\_Version" should be harmonized into "dns version".

We recognize that for traditional database schemas this approach may be challenging, but converting spaces into underscores in the attribute names should not be an impossible undertaking. The idea of the ontology, after all, is to be a human readable abstraction. In the context of the serialized AbuseSA/AbuseHelper XMPP events, white space in key names does not pose a problem. Moreover, the underlying AbuseSA/AbuseHelper filtering rule language is perfectly capable of dealing with white space in key names.

On the note of human readability, we endeavour to strike a balance between attribute name length and readability. For technical people, "src port" may be natural, but "source port" is more readable; on the other hand, "reverse dns" instead of "reverse domain name system name" is more practical. The important point is to have a clear naming convention and adhere to it: "destination domain name" is unwieldy, but "dst domain name" or "dst dns" would not use the same rationale as "domain name".

In summary, the underlying idea of this ontology is to provide a good foundation on which to build, whether the use case is filtering, aggregation, reporting or alerting. Not having to deal with, say, 32 names for an IP address makes life a lot easier at the end of the pipeline.

# History of this Document

A public version of this document has been iterated over, since 2012. Originally, it was a collaboration between numerous CSIRT actors (CERT-EU, CERT-AT, CERT-FI, CERT.PT) and Codenomicon. The current version of this document represents the practical collaboration between CSIRT teams such as [CERT-EU](http://cert.europa.eu/), [CERT-EE](http://www.cert.ee/), [NCSC-FI](https://www.viestintavirasto.fi/en/cybersecurity.html) and [Arctic Security](http://www.arcticsecurity.com), a commercial company.
