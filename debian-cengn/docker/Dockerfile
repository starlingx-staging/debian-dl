FROM debian:bullseye

RUN echo "deb-src http://deb.debian.org/debian/ bullseye main" >> /etc/apt/sources.list

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install  --no-install-recommends -y \
        sudo \
        vim \
        wget \
        devscripts \
        debian-keyring \
        python3 \
        python3-pip \
        python3-git && \
        pip3 install \
        PyYaml==5.1

ARG MYUNAME=builder
ARG MYUID=1000
ENV container=docker

RUN groupadd -g 751 cgts && useradd -r -u $MYUID -g cgts -m $MYUNAME

# Genrate a git configuration file in order to save an extra step
# for end users, this file is required by "repo" tool.
RUN chown $MYUNAME /home/$MYUNAME

RUN echo "$MYUNAME ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /usr/local/

USER $MYUNAME
WORKDIR /outputs

CMD ["python3", "/usr/local/bin/mirror_sync_up.py"]
