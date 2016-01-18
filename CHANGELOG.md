# Changelog

## 3.0.0 (not released)

### Deprecated

 * **(2015-01-05) Legacy rules removed:** Legacy rules from ```abusehelper.core.rules.compat``` (```AND```, ```OR```, ```NOT```, ```MATCH```, ```ANYTHING``` and ```NETBLOCK```) have now been removed after a deprecation period. Please use corresponding ```abusehelper.core.rules``` functionality (```And```, ```Or```, ...).

 *  **(2015-01-04) Contrib package removed:** The migration period for the contrib package removal has ended. Please change all references of ```abusehelper.contrib``` package to abusehelper.bots. All the internal references within AbuseHelper have been updated to support the migration.

    Some of the bots have migrated to the AbuseHelper community repository in [https://bitbucket.org/ahcommunity/ahcommunity](https://bitbucket.org/ahcommunity/ahcommunity), namely:

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
