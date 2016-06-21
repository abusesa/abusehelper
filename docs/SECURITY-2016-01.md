# AbuseHelper Security Announcement 2016-01

Released 2016-05-18

We found out that abusehelper.core.imapbot, abusehelper.core.mailer
and abusehelper.core.utils.fetch_url did not validate X.509
certificates of TLS connections. This made it possible for malicious
third party to MITM the connection and gain access to contents of the
IMAP, SMTP and HTTPS connections TLS session including credentials.

Originally the code directly used Python 2.x standard library's
imaplib, smtplib and httplib/urllib2 modules respectively, every one
of them apparently skipping all server certificate checks.

This issue is fixed by enabling basic ssl.wrap_socket certificate
checks. Also hostname matching is performed. The fixes bump the
idiokit version requirement to 2.6.0, as the new idiokit.ssl.ca_certs
function is used.
