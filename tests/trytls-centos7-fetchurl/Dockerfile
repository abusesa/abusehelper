FROM centos:7

RUN yum -y update && \
    yum -y install epel-release && \
    yum -y install \
        git \
        openssl \
        python \
        python-pip

# TryTLS + deps
RUN pip install git+git://github.com/ouspg/trytls.git

# Abusehelper + deps
RUN pip install git+git://github.com/abusesa/idiokit.git && \
    pip install git+git://github.com/abusesa/abusehelper.git

RUN useradd -m -c "Testing User" tester
USER tester
ENV HOME /home/tester

WORKDIR ${HOME}
COPY trytls_fetch_url.py .
CMD trytls /usr/bin/python trytls_fetch_url.py
