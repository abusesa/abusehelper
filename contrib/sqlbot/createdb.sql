CREATE TABLE customer();

CREATE TABLE sources();

CREATE TABLE asn(
    asn             integer PRIMARY KEY,
    asname          char(256)
);

CREATE TABLE raw_events(
    id              serial,
    time            timestamp with time zone,
    ip              char(11),
    type            char(256),
    source          char(256),
    asn             integer REFERENCES asn (asn),
    customer        char(256),
    abuse_email     char(1024)
);


