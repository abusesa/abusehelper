# Changelog

### Fixes

 * Fixed broken formatting for the Ontology document ([#67](https://github.com/abusesa/abusehelper/pull/67)).

## 4.1.0 (2016-06-22)

### Features

 * Switch to setuptools for packaging ([#37](https://github.com/abusesa/abusehelper/pull/37))
 * Transformation handlers ([#54](https://github.com/abusesa/abusehelper/pull/54))
  * See pull request ([#54](https://github.com/abusesa/abusehelper/pull/54)) for details.

### Fixes

 * Fixed abusehelper.bots.openbl.openblbot which failed to parse malformed lines. ([#63](https://github.com/abusesa/abusehelper/pull/63), [#64](https://github.com/abusesa/abusehelper/pull/64))

### Deprecations

 * Removed SpyEye tracker bots. ([#65](https://github.com/abusesa/abusehelper/pull/65))

## 4.0.1 (2016-05-19)

### Features

 * Add option to provide custom CA certificate file to abusehelper.core.imapbot, abusehelper.core.mail.imapbot and abusehelper.core.mailer. ([#57](https://github.com/abusesa/abusehelper/pull/57), [#58](https://github.com/abusesa/abusehelper/pull/58), [#62](https://github.com/abusesa/abusehelper/pull/62))

## 4.0.0 (2016-05-19)

### Features

 * New ```abusehelper.core.mail```package. ([#6](https://github.com/abusesa/abusehelper/pull/6))
  * See [abusehelper/core/mail/README.md](abusehelper/core/mail/README.md) for details.

### Fixes

 * Fixed TLS MITM vulnerability in abusehelper.core.imapbot, abusehelper.core.mailer and abusehelper.core.utils.fetch_url modules. See [docs/SECURITY-2016-01.md](docs/SECURITY-2016-01.md) for more information.
 * Simpler ```abusehelper.core.roomgraph``` multiprocessing implementation, which also boosts performance due to less idiokit overhead. ([#50](https://github.com/abusesa/abusehelper/pull/50))

### Deprecations

 * ```abusehelper.core.archivebot``` module now logs a deprecation warning. Archivebot, ```abusehelper.bots.archivebot.csvarchivebot```, and ```abusehelper.bots.archivebot.rolloverarchivebot``` will be replaced by ```abusehelper.bots.archivebot``` module.

## 3.1.0 (2016-04-06)

### Features

 * More extensive logging with tracebacks when ```abusehelper.core.startup``` and ```abusehelper.core.runtime``` fail to load the configuration file ([#36](https://github.com/abusesa/abusehelper/pull/36))
 * Add ```abusehelper.bots.abusesech.ransomwarebot``` ([#40](https://github.com/abusesa/abusehelper/pull/40))

## 3.0.0 (2016-02-10)

### Features

 * Add domain name patterns to the rule language ([#7](https://github.com/abusesa/abusehelper/pull/7))
 * Move ```abusehelper.core.roomgraph``` rule matching to separate worker processes ([5b524b1](https://github.com/abusesa/abusehelper/commit/5b524b18b5ccdd5559d749bd894a4f66075fc7e4))
   * The new startup option ```concurrency=[integer]``` defines how many worker processes should get launched, defaulting to ```1``` ([2b2ce65](https://github.com/abusesa/abusehelper/commit/2b2ce65356c331702a772fe7dcc7e3222be72685))
 * Add a rotating and compressing JSON archivebot ```abusehelper.bots.archivebot.archivebot``` ([13173cb](https://github.com/abusesa/abusehelper/commit/13173cb4f3d33dba896a7efdde64348911fb8090))
 * Add ```abusehelper.tools.sender``` and ```abusehelper.tools.receiver``` ([a75fae4](https://github.com/abusesa/abusehelper/commit/a75fae4dbb2d197e2d62e434a18dff562af02ce4), [5706398](https://github.com/abusesa/abusehelper/commit/5706398e736a758ff5cc0401b406aa657b195f28))
   * ```sender``` is a tool for sending JSON formatted data as events to a XMPP room.
   * ```receiver``` is for receiving events from a room as JSON.
   * See [abusehelper/tools/README.md](abusehelper/tools/README.md) for reference.
 * Change the bot return code and termination signal logging format to include the symbolic form of the signal along with the signal code. ([#22](https://github.com/abusesa/abusehelper/pull/22))

### Fixes

 * Support HTTPS URLs in mails processed by ```abusehelper.core.shadowservermail```.
 * Set socket timeouts for ```abusehelper.core.imapbot```'s IMAP connections, controlled with the ```mail_connection_timeout=[seconds]``` option and defaulting to 60 seconds.
 * Set socket timeouts for ```abusehelper.core.mailer```'s SMTP connections, controlled with the ```smtp_connection_timeout=[seconds]``` option and defaulting to 60 seconds.

### Deprecations

 * Remove ```abusehelper.core.dshield```, the DShield bot will be further maintained in the AbuseHelper Community repository ([#14](https://github.com/abusesa/abusehelper/pull/14))
 * Legacy rules from ```abusehelper.core.rules.compat``` (```AND```, ```OR```, ```NOT```, ```MATCH```, ```ANYTHING``` and ```NETBLOCK```) have been removed after a deprecation period. Please use corresponding ```abusehelper.core.rules``` functionality (```And```, ```Or```, ...).
 * Remove backwards compatibility from ```abusehelper.core.runtime``` and ```abusehelper.core.startup``` when launching and maintaining running bots ([#20](https://github.com/abusesa/abusehelper/pull/20))
 * Remove *warn* and *fatal* logging methods from ```abusehelper.core.log.EventLogger``` ([#19](https://github.com/abusesa/abusehelper/pull/19))
 * Remove temporary backwards compatibility code from ```abusehelper.core.serialize``` ([#21](https://github.com/abusesa/abusehelper/pull/21))
 * The migration period for the contrib package removal has ended. Please change all references of ```abusehelper.contrib``` package to ```abusehelper.bots```. Several bots also migrated to the AbuseHelper community repository in [https://bitbucket.org/ahcommunity/ahcommunity](https://bitbucket.org/ahcommunity/ahcommunity):
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
