# environments

Dieses Projekt stellt eine Pentesting-Umgebung mit Docker bereit.

## Enthaltene Tools

- **recon-ng**: Framework für Reconnaissance (im `recon-ng` Container).
- **theHarvester**: Tool zum Sammeln von E-Mail-Adressen, Subdomains und mehr (im `recon-ng` Container).
- **BloodHound.py**: Python-basierter Ingestor für BloodHound (im `recon-ng` Container als `bloodhound-python`).
- **BloodHound (Community Edition)**: Grafische Oberfläche zur Analyse von Active Directory Beziehungen (erreichbar unter `http://localhost:8082`).
- **Neo4j**: Graph-Datenbank, die von BloodHound genutzt wird (erreichbar unter `http://localhost:7474`).

## Nutzung

### Starten der Umgebung

```bash
docker compose up -d
```

### Nutzung von recon-ng

```bash
docker compose run --rm recon-ng
```

### Nutzung von theHarvester

```bash
docker compose run --rm recon-ng theHarvester -d example.com -b google
```

### Nutzung von BloodHound.py

```bash
docker compose run --rm recon-ng bloodhound-python -u 'user' -p 'password' -d 'domain.local' -dc 'dc01.domain.local' -c All
```

### Zugriff auf BloodHound GUI

Öffne `http://localhost:8082` in deinem Browser. Standardmäßig ist BloodHound mit der Neo4j-Instanz im Hintergrund verbunden.
Die Neo4j-Konsole ist unter `http://localhost:7474` erreichbar (Benutzer: `neo4j`, Passwort: `password`).