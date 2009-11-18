# Bots that provide services gather in service_room. 
# This room is used for communicating configuration to different bots.
service_room = "services"

# Right now, DShield bot will deliver results to separate dshield room
dshield_room = "dshield"

# Mailer will use this server for sending mails.
mail_host = "mail.example.com"
# You can use e.g. the traditional 25 or the submission port 587.
mail_port = 25
# From whom it looks like the mails came from.
mail_sender = "sender@example.com"
# If you use authenticated submission port, put here your username 
# (without the domain) and the password.
mail_username = ""
mail_password = ""

# GraphingWiki configuration (optional, testing)
wiki_username = ''
wiki_password = ''
wiki_url = 'http://localhost/wiki/'
wiki_category = 'CategoryAbuseContact'

# username is the full XMPP account name (JID) you plan to use for
# your bots.
username = "xmppuser@xmppserver.org"
password = "xmpppasword"
