configure:
	pod2man --section=1 man/roomreader.pod man/roomreader.1
	pod2man --section=8 man/abusehelperctl.pod man/abusehelperctl.8
all:
	# nothing to be done here
install:
	# nothing to be done here
	
clean:
	rm -f man/*.1 man/*.8
	
.PHONY: configure all install clean
