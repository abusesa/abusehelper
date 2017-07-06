# Data Harmonization Ontology (TLP White)

What is data harmonization? What is an ontology? The purpose of this document is to help you better deal with the complexity that arises from processing threat intelligence from heterogeneous sources. Data harmonization is a contract to call same things always by the same name, i.e. an ip address is always referred to as an **ip**.

With data harmonization briefly visited, we move on to defining an ontology. An ontology in our case is a higher level abstraction of a language, where each lexeme addresses an observable characteristic of either an Indicator of Compromise, IoC, or a vulnerable service discovered through actively scanning the Internet. Our grammar is thus expressed as sets of key-value pairs, which are straightforward to serialize into AbuseHelper events.

Below, we will reference events as collections of ontology driven key-value pairs. Please note that we use the term **key** to denote an event schema and the term **attribute** to denote an ontology lexeme.

## Ontology, Schema or Taxonomy

As stated above, an ontology is a higher level abstraction of the semantic characteristics of an object. A schema, on the other hand, is a technical contract to transfer or store data in a prescribed format. Both are needed, but we see schemas as derivatives of an underlying semantic representation, which in our case is an ontology. In contrast with hierarchical taxonomies, an ontology allows for lexemes outside the core language, as long as the definition does not duplicate or redefine that of an already established one, which calls for harmonization. Consequently, the traditional way of dealing with the unknown in taxonomies has been the introduction of the **other** category, which simply fails over time.

# Core Attributes

For an abuse or vulnerable service event to be actionable and able to reach the right end point recipient, various keys need to be present.

## Feed Attributes

|attribute|description|
--- | --- |
|feed|Lower case name for the feed, e.g. phishtank.|
|feed code|Alternative code name for the feed in case it cannot be shared e.g. dgfs, hsdag etc.|
|feeder|Name of the organization providing one or more data feeds, e.g. shadowserver."|
|feed url|The URL of a given abuse feed, where applicable.|

## Time

All the timestamps should be normalized to UTC. If the source reports only a date, please do not invent timestamps.

|attribute|description|
--- | --- |
|observation time|The time a source bot saw the event. This timestamp becomes especially important should you perform your own attribution on a host DNS name for example. The mechanism to denote the attributed elements with reference to the source provided is detailed below in Reported Identity.|
|source time|Time reported by a source. Some sources only report a date, which may be used here if there is no better observation.|

**N.B.** a good way to represent timestamps is this [ISO 8601 combined date-time representation](http://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations): ```YYYY-MM-DD HH:MM:SSZ```. We have decided to omit the T for readability, since:

**ISO 8601:2004(E). ISO. 2004-12-01. 4.3.2 NOTE:** By mutual agreement of the partners in information interchange, the character [T] may be omitted in applications where there is no risk of confusing a date and time of day representation with others defined in this International Standard.

## Identity

The abuse type of an event defines the way these IOC needs to be interpreted. For a botnet drone they refer to the compromised machine, whereas for a command and control server they refer the server itself.

|attribute|description|
--- | --- |
|as name|The registered name for an autonomous system.|
|asn|Autonomous system number.|
|bgp prefix allocated|The date when a RIR such as RIPE NCC or ARIN allocated a given bgp prefix.|
|bgp prefix|A CIDR associated to an autonomous system.|
|domain name|DNS domain name. http://en.wikipedia.org/wiki/Domain_name|
|email address|An email address, whose interpretation is based on the abuse type.|
|ip|IPv4 or IPv6 address.|
|port|The port through which the abuse activity is taking place. For example a command and control server report will most likely contain a port, which is directly related to the reported ip or host.|
|registry|The IP registry, RIR, a given ip address is allocated by.|
|reverse dns|A Reverse DNS name acquired through a reverse DNS lookup on an IP address. N.B. Record types other than PTR records may also appear in the reverse DNS tree. http://en.wikipedia.org/wiki/Reverse_DNS_lookup|
|url|A URL denotes an IOC, which refers to a malicious resource, whose interpretation is defined by the abuse type. A URL with the abuse type phishing refers to a phishing resource.|

### Source Identity

|attribute|description|
--- | --- |
|source as name|The autonomous system name from which the connection originated.|
|source asn|The autonomous system number from which originated the connection.|
|source cc|The country code of the ip from which the connection originated.|
|source domain name|A DNS name related to the host from which the connection originated.|
|source ip|The ip observed to initiate the connection.|
|source port|The port from which the connection originated.|

### Destination Identity

Since many of the sources report events related to a compromised machines, such as a botnet drones, they may report relevant information about the command and control infrastructure as well. The meaning of each event needs to be interpreted with reference to the abuse type. A destination ip and port in the context of a botnet drone for example usually denotes the command and control server.

|attribute|description|
--- | --- |
|destination as name|The autonomous system name to which the connection was destined.|
|destination asn|The autonomous system number to which the connection was destined.|
|destination cc|The country code of the ip which was the end-point of the connection.|
|destination domain name|The DNS name related to the end-point of a connection.|
|destination ip|The end-point of the connection.|
|destination port|The destination port of the connection.|

### Local Identity

|attribute|description|
--- | --- |
|os name|Operating system name.|
|os version|Operating system version.|
|user agent|Some feeds report the user agent string used by the host to access a malicious resource, such as a command and control server.|

### Reported Identity

As stated above, each abuse handling organization should define a policy, which attributes to use as the primary elements describing a given event. Often, the sources have performed their attribution, but you may choose to correlate their attributive elements against your own or those of a third party. In practice, this means that your sanitation should prefix the keys with the **reported** keyword, to denote that you have decided to perform the attribution on your own. The list below is not comprehensive, rather than a list of common things you may want to correlate yourself. Moreover, if you choose to perform your own attribution, the **observation time** will become your authoritative point of reference in relation to the correlated attributes.

|attribute|description|
--- | --- |
|reported as name|The autonomous system name registered to the reported asn.|
|reported asn|The autonomous system number related to the resource, which was reported by the source.|
|reported cc|The country code of the reported ip.|
|reported ip|Should you perform your own attribution on a DNS name referred to by host, the ip reported by the source is replaced.|

### Geolocation

We recognize that ip geolocation is not an exact science and analysis of the abuse data has shown that different sources attribution sources have different opinions of the geolocation of an ip. This is why we recommend to enrich the data with as many sources as you have available and make the decision which value to use for the cc attribute based on those answers.

|attribute|description|
--- | --- |
|cc|Each abuse handling pipeline, should define a logic how to assign a value for this key. You may decide to trust the opinion of a single source or apply logical operations on multiple sources. The country code is expressed as an ISO 3166 two letter country code.|
|city|Some geolocation services refer to city-level geolocation.|
|country|The country name derived from the ISO 3166 country code (assigned to cc above).|
|latitude|Latitude coordinate derived from a geolocation service, such as MaxMind geoip db.|
|longitude|Longitude coordinate derived from a geolocation service, such as MaxMind geoip db.|

## Additional Attributes

The idea behind the additional attributes is to denote generic metadata about an event, which complements the identity or temporal information about the victim, vulnerable service or a piece of compromised infrastructure. The purpose of this information is to give more context to the abuse type denoted by the "type" attribute.

|attribute|description|
--- | --- |
|abuse contact|An abuse contact email address for an IP network.|
|additional information|Sometimes it may be necessary to relay a an additional piece of information to the report recipient related to the specific context at hand. So in a sense it is a placeholder for useful context dependent information, which would be otherwise difficult to convey without changing a schema.|
|comment|Free text commentary about the abuse event augmented by an analyst.|
|description url|A description URL is a link to a further description of threat in question.|
|description|A free-form textual description of an abuse or vulnerable service event.|
|http request|Some feeders report http requests instead of URLs. They may call them URLs, but for the sake of interoperability with automation, they should be placed under "http request" key, since there is no guarantee that the protocol specification is http://.|
|malware family|A malware family name in lower case.|
|missing data|If the harmonization is missing a known piece of data, such as an **ip** for example, the reference to this fact may be inserted here.|
|protocol|The protocol attribute describes the application protocol on top of the transport, which relates to the observed abuse or vulnerable service. I.e. protocol=ssh for SSH brute-forcing attacks is more descriptive than protocol=tcp. In this case the transport protocol should be referenced by that key, i.e. transport ptotocol=tcp.|
|source|Some of the aggregated feeds, i.e. feeds utilizing indicators not directly from the feeder report a source of this external information. This key can be used to denote those feeder external entities, in the case of blacklist aggregation for example. N.B. a source is external to a feeder or their feed offering.|
|status|Observed status of the malicious resource phishing URL, dropzone, c&c, e.g. online, offline.|
|target|Some sources such as phishing feeds denominate the target of a phishing campaign.|
|tracking id|Some sources and applications use an identifier to denote a context for an abuse event. Previously, we denoted these with provider specific id keys, such as rtir id, misp id and so on. Since traceability is the common communicative function, we have decided to bundle all these ids under the tracking id key. Please note that the purpose of the "tracking id" key is to link the event into an aggregate context. It is not a unique identifier for a single event. For this purpose you should use the "uuid" key instead.|
|transport protocol|Some feeds report a protocol, which often denotes the observed transport, e.g. tcp. This should be noted appropriately if the protocol attribute should denote the protocol of a vulnerable service for example.|
|uuid|[AbuseSA](http://www.abusesa.com) and AbuseHelper are using python uuids to identify abuse events. The python UUIDs are generated based on [RFC4122](http://tools.ietf.org/html/rfc4122) using the uuid.uuid4() function. Please note that the "uuid" serves a different communicative function than the tracking id. The purpose of the uuid is to denote a unique identifier, which uniquely identifies a single event.|
|vulnerability|Often, it is necessary to denote a short description of a vulnerable service reported by a source. This helps in correlating the vulnerabilities across sources.|

### Artifact Attributes

|attribute|description|
--- | --- |
|artifact hash type|The hashing algorithm used for artifact hash type above, be it MD5 or SHA-* etc.|
|artifact hash|A string depicting a checksum for a file, be it a malware sample for example.|
|artifact version|A version string for an identified artifact generation, e.g. a crime-ware kit.|

## Classification Attributes

Having a functional ontology to work with, especially for the abuse types is important for you to be able to classify, prioritize and report relevant actionable intelligence to the parties who need to be informed. Below, is a list of harmonized values for the **threat types** we have observed in our quality assurance efforts and collaborating with our AbuseSA customers and the AbuseHelper community. The driving idea for this ontology has been to use a minimal set of values with maximal usability. 


|attribute|description|
--- | --- |
|threat type|At present, we have two types of threats present in the data: **ioc** (Indicators of Compromise) and **vulnerable service**s. Moreover, on a functional level IoCs may be further categorized into **victim**s and **infrastructure**s. N.B. The threat type may very well be a multi-value attribute, e.g. "threat type"=ioc, "threat type"=infrastructure. At minimum, it should denote between "threat type"=ioc or "threat type"="vulnerable service", where additional tagging complements a given threat type.|
|type|The type is one of the most crucial pieces of information for any given threat event. The main idea of dynamic typing is to keep our ontology flexible, since we need to evolve with the evolving threatscape present in the data. Furthermore, the value data set for the type attribute should be kept as minimal as possible to avoid a **type explosion**, which in turn dilutes the business value of dynamic typing.

### Threat Type Values

The idea behind the **threat type** tagging is to enable the abuse handlers automate semantic filtering based on the type of observation in question. The basic dichotomy present in the data at present is between vulnerable services and abuse. Moreover, for sensoring purposes for example, it is easier to use IoC, which represent compromised criminal infrastructure, rather than victims.

|attribute|description|
--- | --- |
|infrastructure|Infrastructure indicators, such as c&c observations should be tagged with this threat type.|
|ioc|All abuse type events must be tagged with this threat type.|
|victim|Botnet drone observations should be tagged with this threat type.|
|vulnerable service|All vulnerable network service observations must be tagged with this threat type.|

### Type Values

The **type** values offer a data-backed taxonomy for classifying abuse and vulnerable services observations in a uniform manner. A concise, yet functional classification system enables you to make informed decisions about the state of your network estate in real-time.

|attribute|description|
--- | --- |
|artifact|Artifacts refer to host-based indicators, such as checksums, file paths.|
|attribution|Attribution refers to indicators, which can be attributed to malicious activity without a specific functional category such as a command and control server.|
|backdoor|Backdoor indicators refer to hosts, which have been compromised and/or backdoored by a third party.|
|blacklist|Some sources provide blacklists, which clearly refer to abusive behavior, such as spamming, but fail to denote the exact reason why a given identity has been blacklisted. The reason may be that the justification is anecdotal or missing entirely. This type should only be used if the typing fits the definition of a blacklist, but an event specific denomination is not possible for one reason or another.|
|botnet drone|This is the most numerous type of abuse, as it refers to compromised computers calling out to a command and control mechanism.|
|brute-force|This type refers to a machine, which has been observed to perform brute-force attacks over a given application protocol, e.g. ssh|
|c&c|This is a command and control server in charge of a given number of botnet drones.|
|compromised server|This server or service has been compromised by a third party.|
|ddos infrastructure|This type refers to various parts of DDoS botnet infrastructure.|
|ddos target|This type refers to the intended target of a DDoS attack, i.e. the intended domain name or ip address.|
|defacement|This type refers to hacktivism, which on a technical level is an indicator of a compromised service.|
|dropzone|This type refers to a resource, which is used to store stolen user data.|
|exploit url|An exploit or an exploit kit is often served through a malicious URL.|
|ids alert|Alerts from a heuristic sensor network. This is a generic classification, as often the taxonomy of these types of events leave a lot to wish for in terms of consistency.|
|malware configuration|This is a resource which updates botnet drones with a new configurations.|
|malware url|A URL is the most common resource with reference to malware binary distribution.|
|phishing|This type most often refers to a URL, which is trying to defraud the users of their credentials.|
|ransomware|This type refers to a specific type of compromised machine, where the computer has been hijacked for ransom by the criminals.|
|scanner|This type refers to port or vulnerability scanning attempts in general.|
|spam infrastructure|This type refers to resources, which make up SPAM infrastructure, be it a harvester, dictionary attacker, URL, spam etc.|
|test|This is a type for testing purposes.|
|vulnerable service|This type refers to poorly configured or vulnerable network service, which may be abused by a third party. For example, these services relate to open proxies, open dns resolvers, network time servers (ntp) or character generation services (chargen), simple network management services (snmp). In addition, to specify the network service and its potential abuse, one should use the protocol, port and description attributes for that purpose respectively.|

## Topic or Provider Specific Attributes

Since the basic idea of an ontology is to specify a core language, which is able to communicate the relevant aspects of a topic in an effective manner, it leaves room for topic specific lexemes outside the generic terminology. In the context of abuse reporting, this is especially true with emerging trends, where a single source may start reporting on a topic and other follow suit. Previously, we listed some of these keys such as "dns version" or "notified by" as part of the ontology.

At present, we have decided to leave them out of the ontology and only bring in terms, which represent a generic topic. This approach does not detract from the ontology or its communicative functions, since the core keys communicate the relevant aspects effectively. Topic or provider specific keys can thus be part of an event name space.

The important thing is just to avoid collision with the core ontology name space. In other words, topic or provider specific keys are the new emerging attributes, which may become part of the ontology if they get adopted to describe a facet of a generic topic. For example above, we have decided to use the "cc" key as the authoritative country code denominator.

For a given context, there may be other provider specific interpretations, which we have decided to prefix with the provider name. Example of such a prefix are "cymru cc" or "geoip cc", where the provider name is prepended to denote the source of this geolocation information.

## Harmonization Best Practices

There are a number of things, which you will have to take into account when harmonizing heterogeneous datasets. The established attributes in this ontology should help you on your way, when dealing with topic or provider specific attributes. In general, the attribute names should be **lower case** and instead of underscores, "\_", you should use white space " ". E.g. DNS\_Version would be harmonized into "dns version".

We recognize that for traditional database schemas this approach may be challenging, but converting spaces into underscores in the attribute names should not be an impossible undertaking. The idea of the ontology, after all, is to be a human readable abstraction. In the context of the serialized AbuseHelper XMPP events, white space in key names does not pose a problem. Moreover, the underlying AbuseHelper filtering rule language is perfectly capable of dealing with white space in key names.

On the note of human readability, we need to strike a balance between attribute name length and readability. "src port" may be natural for technical people, but "source port" is more readable. "reverse dns" instead of "reverse domain name system name" on the other hand  is more practical. As human readability is not an exact science, the important point is to have a clear naming convention and stick with it. For example, "destination domain name" is a bit wieldy, but "dst domain name" or "dst dns" would not use the same rationale as "domain name" for example.

In summary, the underlying idea of this ontology is to provide a good basis to build on, whether the use case is filtering, aggregation, reporting or alerting. Not having to deal with 32 names for an ip address for example, makes life a lot easier at the end of the pipeline.

# History of this Document

A public version of this document has been iterated over, since 2012. Originally, it was a collaboration between numerous CSIRT actors (CERT-EU, CERT-AT, CERT-FI, CERT.PT) and Codenomicon. The current version of this document represents the practical collaboration between CSIRT teams such as [CERT-EU](http://cert.europa.eu/), [CERT-EE](http://www.cert.ee/), [NCSC-FI](https://www.viestintavirasto.fi/en/cybersecurity.html) and [Synopsys](http://www.abusesa.com), a commercial company.

