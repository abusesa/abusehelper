import splitterbot
from rules import *

ruleset = RuleSet()
ruleset.add("ips-from-finland@conference.example.com", 
            CONTAINS("ip", country="FI"))
ruleset.add("ips-not-from-finland-or-sweden@conference.example.com", 
            AND(CONTAINS("ip"), 
                NOT(OR(CONTAINS(country="SE"), 
                       CONTAINS(country="FI")))))

splitterbot.publish_ruleset(ruleset, "user@example.com", "password")
