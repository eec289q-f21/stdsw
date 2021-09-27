ARG UBUNTU_VERSION

FROM ubuntu:${UBUNTU_VERSION}

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /setup

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apt-utils \
        nano \
        vim \
        curl \
        sudo \
        debhelper \
        python3-setuptools \
        build-essential \
        python3-all \
        python3-pip \
        wget \
        libz-dev \
        libz3-dev \
        ninja-build \
        git \
        unzip \
        cmake \
        gdb \
        valgrind \
        gcovr \
      	debian-keyring  \
      	debian-archive-keyring   \
      	apt-transport-https \
      	gnupg \
      	ca-certificates \
      	libc-dev \        
        linux-tools-common \
        linux-tools-aws \
        fakeroot
    
RUN curl -1sLf \
  'https://dl.cloudsmith.io/public/eec289/eec289-f1/setup.deb.sh' \
  | bash
  
RUN apt-get install opencilk=1.0

RUN rm -rf /var/lib/apt/lists
   
COPY requirements.txt requirements.txt

RUN pip3 install wheel

RUN pip3 install -r requirements.txt

RUN groupadd -g 1000 ubuntu \
    && useradd -m -u 1000 -g ubuntu eec289

WORKDIR /home/eec289

ENV DEBIAN_FRONTEND=

USER eec289
