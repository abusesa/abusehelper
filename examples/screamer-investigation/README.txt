This example contains: 
 * a repr bot, which represents human input as events
 * cymruwhois screaming expert bot
 * passivedns screaming expert bot

You may define an investigation channel in startup.py. The bots will join there.
Then you can go to the channel with your chat client and start asking questions, 
see below: 


<human> /repr ip=131.131.131.131, domain=www.tieto.com
<repr> ip=131.131.131.131, domain=www.tieto.com
<cymruwhois> IP 131.131.131.131 has values cc=US, registry=arin, as name=COMPUTER-SCIENCES-CORP-NTIS - Computer Sciences Corp - NTIS, bgp_prefix=131.131.128.0/19, allocated=1988-09-22, asn=10859
<passivedns>
 key3=2009-07-21 10:33:30, key2=www.tietoenator.com, key1=www.tieto.com, augment sha-1=9a1c6926f7b0bff2bf85622f753f4782fe7aec09, key4=2010-09-16 10:53:58
 key3=2010-11-12 14:33:30, key2=217.152.19.25, key1=www.tietoenator.com, augment sha-1=9a1c6926f7b0bff2bf85622f753f4782fe7aec09, key4=2011-04-29 11:49:08
 key3=2009-08-10 15:15:37, key2=217.152.19.4, key1=www.tietoenator.com, augment sha-1=9a1c6926f7b0bff2bf85622f753f4782fe7aec09, key4=2010-09-16 16:06:04
 1:35:11 key3=2010-10-26 19:27:41, key2=217.152.19.25, key1=www.tieto.com, augment sha-1=9a1c6926f7b0bff2bf85622f753f4782fe7aec09, key4=2011-05-02 16:29:55
