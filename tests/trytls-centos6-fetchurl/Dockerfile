FROM centos:6

RUN yum -y update && \
    yum -y install \
        epel-release \
        centos-release-scl \
        git

# TryTLS + deps
RUN yum -y install \
        python27 \
    && \
    scl enable python27 -- pip install git+git://github.com/ouspg/trytls.git

# Abusehelper + deps
RUN yum -y install \
        python \
        python-pip \
    && \
    pip install git+git://github.com/abusesa/idiokit.git && \
    pip install git+git://github.com/abusesa/abusehelper.git

RUN useradd -m -c "Testing User" tester
USER tester
ENV HOME /home/tester

WORKDIR ${HOME}
COPY trytls_fetch_url.py .
CMD scl enable python27 -- trytls /usr/bin/python trytls_fetch_url.py
