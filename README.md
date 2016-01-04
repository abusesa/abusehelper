[![Circle CI](https://circleci.com/gh/abusesa/abusehelper.svg?style=shield)](https://circleci.com/gh/abusesa/abusehelper)

# AbuseHelper

AbuseHelper is an open-source framework for receiving and redistributing abuse feeds and threat intel.

## License

Files under contrib/ are (c) respective copyright holders if named in the specific file, everything else is current (c) by Codenomicon Ltd. Everything is licensed under MIT license (http://www.opensource.org/licenses/mit-license.php), see LICENSE.

## 2015-01-04 Contrib package removal

The migration period for the contrib package removal has ended. Please change all references of abusehelper.contrib package to abusehelper.bots. All the internal references within AbuseHelper have been updated to support the migration.

Some of the bots have also migrated to the new AbuseHelper community repository in: [https://bitbucket.org/ahcommunity/ahcommunity](https://bitbucket.org/ahcommunity/ahcommunity)

```
contrib.arbor.atlassrf
contrib.arbor.ssh
contrib.bgp-xmpp.bgprankingbot
contrib.csv2xmpp.csv2xmpp
contrib.experts.bgpexpert
contrib.experts.bgpquaggaexpert
contrib.experts.iscpdnsexpert
contrib.experts.iso3166expert
contrib.experts.observerexpert
contrib.experts.malwarehash
contrib.experts.passivedns
contrib.experts.rtexpert
contrib.experts.sshkeyscan
contrib.experts.url2domain
contrib.iplist.iplist
contrib.logcollector.logcollectorbot
contrib.malwareblacklist.malwareblacklistbot
contrib.mailextras.iodef
contrib.mailextras.signingmailer
contrib.urllistmailbot.urllistmailbot
contrib.opencollab.crypto
contrib.opencollab.downloader
contrib.opencollab.virtualboxsandbox
contrib.opencollab.webshot
contrib.opencollab.wikicryptostartup
contrib.opencollab.wikiruntime
contrib.opencollab.wikistartup
```
