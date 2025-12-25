FROM kalilinux/kali-rolling:latest

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      recon-ng ca-certificates git python3-pip \
 && python3 -m pip install --no-cache-dir --break-system-packages \
      shodan beautifulsoup4 cryptography censys PyPDF3 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY recon_ng_bootstrap.sh /usr/local/bin/reconng-entrypoint.sh
RUN chmod +x /usr/local/bin/reconng-entrypoint.sh

WORKDIR /data
ENTRYPOINT ["/usr/local/bin/reconng-entrypoint.sh"]
CMD ["recon-ng"]