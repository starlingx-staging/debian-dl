FROM debian:bullseye

RUN echo "deb-src http://deb.debian.org/debian/ bullseye main" >> /etc/apt/sources.list

# Download required dependencies by mirror/build processes.
RUN     apt-get update && apt-get install  --no-install-recommends -y \
        sudo \
        vim \
        wget \
        coreutils \
        devscripts \
        debian-keyring \
        python3 \
        python3-pip \
        python3-git \
        python3-debian

RUN     sudo pip3 install \
        PyYaml==5.1

RUN     apt-get install  --no-install-recommends -y \
        curl

RUN     curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/bin/repo && \
        chmod 755 /usr/bin/repo

RUN     apt-get install  --no-install-recommends -y \
        python-is-python3

RUN     apt-get install  --no-install-recommends -y \
        openssh-client


ARG MYUNAME=builder
ARG MYUID=1000
ENV container=docker

RUN groupadd -g 751 cgts && useradd -r -u $MYUID -g cgts -m $MYUNAME

# Genrate a git configuration file in order to save an extra step
# for end users, this file is required by "repo" tool.
RUN chown $MYUNAME /home/$MYUNAME
RUN sudo su -l -c "git config --global user.email $MYUNAME@opendev.org" $MYUNAME
RUN sudo su -l -c "git config --global user.name $MYUNAME" $MYUNAME
RUN sudo su -l -c "git config --global color.ui false" $MYUNAME

RUN echo "$MYUNAME ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers

USER $MYUNAME
WORKDIR /outputs

CMD ["/bin/bash", "/opt/bin/mirror_sync_up"]
