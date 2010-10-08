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

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.distribute(name))
        finally:
            self.log.info("Left room %r", name)

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner
            for event in inner:
                self.sqlqueries.insertEvent(event)

class SQLQueries():
    connection = None

    def __init__(self, dbsrv, dbname, dbusr, dbpwd):
        self.connection = postgres.PostgresConnector(dbsrv, dbname, dbusr, dbpwd)

    def existsASN(self, asn):
        result = self.connection.executeAndReturnResult("SELECT asn FROM asn WHERE asn = " + asn)
        if(len(result) >= 1):
            return True
        else:
            return False

    def insertASN(self, asn, asname):
        if(not self.existsASN(asn)):
            query = "INSERT INTO asn (asn, asname) VALUES (" + asn + ", '" + asname + "')"
            self.connection.executeAndCommit(query)
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

            query =  "INSERT INTO raw_events(time, ip, type, source, asn, customer, abuse_email) VALUES ("
            query += "'" +    time     + "', "
            query += "'" +     ip      + "', "
            query += "'" +    source   + "', "
            query += "'" +     asn     + "', "
            query += "'" +   customer  + "', "
            query += "'" + abuse_email + "'"
            
            self.connection.executeAndReturnResult(query)
    
if __name__ == "__main__":
    SQLReport.from_command_line().execute()



