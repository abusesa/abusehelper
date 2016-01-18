# Changelog

## 3.0.0 (not released)

### Features

 * Move ```abusehelper.core.roomgraph``` rule matching to separate worker processes. The new startup option ```concurrency=[integer]``` defines how many worker processes should get launched, defaulting to ```1```.
 * Add a rotating and compressing JSON archivebot ```abusehelper.bots.archivebot.archivebot```.
 * Add ```abusehelper.tools.sender``` and ```abusehelper.tools.receiver```. ```sender``` is a tool for sending JSON formatted data as events to a XMPP room while ```receiver``` is for receiving events from a room as JSON. See [abusehelper/tools/README.md](abusehelper/tools/README.md) for reference.

### Fixes

 * Support HTTPS URLs in mails processed by ```abusehelper.core.shadowservermail```.
 * Set socket timeouts for ```abusehelper.core.imapbot```'s IMAP connections, controlled with the ```mail_connection_timeout=[seconds]``` option and defaulting to 60 seconds.
 * Set socket timeouts for ```abusehelper.core.mailer```'s SMTP connections, controlled with the ```smtp_connection_timeout=[seconds]``` option and defaulting to 60 seconds.

### Deprecations

 * Legacy rules from ```abusehelper.core.rules.compat``` (```AND```, ```OR```, ```NOT```, ```MATCH```, ```ANYTHING``` and ```NETBLOCK```) have been removed after a deprecation period. Please use corresponding ```abusehelper.core.rules``` functionality (```And```, ```Or```, ...).
 *  The migration period for the contrib package removal has ended. Please change all references of ```abusehelper.contrib``` package to ```abusehelper.bots```. Several bots also migrated to the AbuseHelper community repository in [https://bitbucket.org/ahcommunity/ahcommunity](https://bitbucket.org/ahcommunity/ahcommunity):

    * contrib.arbor.atlassrf
    * contrib.arbor.ssh
    * contrib.bgp-xmpp.bgprankingbot
    * contrib.csv2xmpp.csv2xmpp
    * contrib.experts.bgpexpert
    * contrib.experts.bgpquaggaexpert
    * contrib.experts.iscpdnsexpert
    * contrib.experts.iso3166expert
    * contrib.experts.observerexpert
    * contrib.experts.malwarehash
    * contrib.experts.passivedns
    * contrib.experts.rtexpert
    * contrib.experts.sshkeyscan
    * contrib.experts.url2domain
    * contrib.iplist.iplist
    * contrib.logcollector.logcollectorbot
    * contrib.malwareblacklist.malwareblacklistbot
    * contrib.mailextras.iodef
    * contrib.mailextras.signingmailer
    * contrib.urllistmailbot.urllistmailbot
    * contrib.opencollab.crypto
    * contrib.opencollab.downloader
    * contrib.opencollab.virtualboxsandbox
    * contrib.opencollab.webshot
    * contrib.opencollab.wikicryptostartup
    * contrib.opencollab.wikiruntime
    * contrib.opencollab.wikistartup

## 2.1.0 (2015-08-13)

Historical release.
