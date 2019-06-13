FROM ubuntu:bionic

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        borgbackup \
        cron \
        dumb-init \
        curl \
        ca-certificates \
        jq \
        mariadb-client \
        openssh-client && \
        rm -rf /var/cache/apt /var/lib/apt/lists

# download docker cli binary
ENV DOCKERVERSION=18.06.3-ce
RUN curl -fsSLO https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKERVERSION}.tgz \
  && tar xzvf docker-${DOCKERVERSION}.tgz --strip 1 \
                 -C /usr/local/bin docker/docker \
  && rm docker-${DOCKERVERSION}.tgz

# copy scripts
COPY backup.sh init.sh /backupscripts/

RUN ln -s /backupscripts/backup.sh /usr/local/bin/backup && \
    ln -s /backupscripts/init.sh /usr/local/bin/init-backup && \
    touch /var/log/cron.log && \
    chmod a+x /backupscripts/*.sh && \
    echo "59 2 * * * backup > /dev/stdout 2>&1" | crontab -

ENV BORG_BASE_DIR=/borgconfig

VOLUME /borgconfig

# mount /root/.ssh/id_rsa with ssh key for borg server
# ENV BORG_REMOTE_URL # borg URL of the server including remote path
# ENV BORG_PASSPHRASE # for passphrase encryption  

ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["cron", "-f"]