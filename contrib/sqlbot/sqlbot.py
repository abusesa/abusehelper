from abusehelper.core import postgres
from abusehelper.core import events, bot, taskfarm
from idiokit import threado

class SQLReport(bot.ServiceBot):
    sqlqueries = None
    dbsrv = bot.Param()
    dbname = bot.Param()
    dbusr = bot.Param()
    dbpwd = bot.Param()
    
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.sqlqueries = SQLQueries(self.dbsrv, self.dbname, self.dbusr, self.dbpwd)
        self.log.info("SQLBOT initialized")

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Calling handle_room")
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.collect(name))
        finally:
            self.log.info("Left room %r", name)

    @threado.stream_fast
    def collect(inner, self, name):
        while True:
            yield inner
            for event in inner:
                self.sqlqueries.insertEvent(event)

    @threado.stream
    def session(inner, self, state, src_room):
        yield inner.sub(self.rooms.inc(src_room))

class SQLQueries():
    connection = None

    def __init__(self, dbsrv, dbname, dbusr, dbpwd):
        self.connection = postgres.PostgresConnector(dbsrv, dbname, dbusr, dbpwd)

    def existsASN(self, asn):
        result = self.connection.executeAndReturnResult("SELECT asn FROM asn WHERE asn = ?", asn)
        
        if(result is None or len(result) < 1):
            return False
        else:
            return True

    def insertASN(self, asn, asname):
        if(not self.existsASN(asn)):
            query = "INSERT INTO asn (asn, asname) VALUES ( %s, %s )"
            self.connection.executeAndCommit(query, asn, asname)
        return

    def insertEvent(self, event):
            time = event.value("time", None)
            ip = event.value("ip", None)
            type = event.value("type", None)
            source = event.value("source", None)
            asn = event.value("asn", None)
            customer = event.value("customer", None)
            abuse_email = event.value("abuse_email", None)

            if(not self.existsASN(asn)):
                self.insertASN(asn, str(event.value("as_name", None)))

            
            #check values
            if(type is None):
                type = ""
            if(source is None):
                source = ""
            if(asn is None):
                asn = ""
            if(customer is None):
                customer = ""
            if(abuse_email is None):
                abuse_email = ""
            
            #proceed with query
            query =  "INSERT INTO raw_events(time, ip, type, source, asn, customer, abuse_email) 
                                     VALUES (%s,   %s, %s  , %s    , %s , %s      , %s) "
            self.connection.executeAndCommit(query, time, ip, type, source, asn, customer, abuse_email)
    
if __name__ == "__main__":
    SQLReport.from_command_line().execute()



