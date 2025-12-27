FROM kalilinux/kali-rolling:latest

# Installation von Kali-Basis und Tools
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      recon-ng \
      theharvester \
      bloodhound \
      neo4j \
      ca-certificates \
      git \
      python3-pip \
      bloodhound.py \
 && python3 -m pip install --no-cache-dir --break-system-packages \
      shodan beautifulsoup4 cryptography censys PyPDF3 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Bootstrap-Skript für recon-ng kopieren
COPY recon_ng_bootstrap.sh /usr/local/bin/reconng-entrypoint.sh
RUN chmod +x /usr/local/bin/reconng-entrypoint.sh

# Arbeitsverzeichnis setzen
WORKDIR /data

# Ports für Neo4j und BloodHound (falls man sie im Container startet)
EXPOSE 7474 7687 8080

ENTRYPOINT ["/usr/local/bin/reconng-entrypoint.sh"]
CMD ["recon-ng"]
