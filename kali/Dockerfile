FROM kalilinux/kali-rolling:latest

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      recon-ng ca-certificates git python3-pip \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY recon_ng_bootstrap.sh /usr/local/bin/reconng-entrypoint.sh
RUN chmod +x /usr/local/bin/reconng-entrypoint.sh

WORKDIR /data
ENTRYPOINT ["/usr/local/bin/reconng-entrypoint.sh"]
CMD ["recon-ng"]