#!/usr/bin/env bash
set -euo pipefail

MARKER="/data/.reconng_bootstrapped"
BOOT_RC="/data/.reconng_bootstrap.rc"

# recon-ng speichert Konfig i.d.R. unter $HOME; bei dir ist HOME=/data
export HOME="${HOME:-/data}"

bootstrap() {
  # Resource-File bauen (wird von recon-ng abgearbeitet)
  : > "${BOOT_RC}"

  # Marketplace: am einfachsten alles installieren, damit Shodan sicher dabei ist
  # (kann beim ersten Mal etwas dauern)
  cat >> "${BOOT_RC}" <<'RC'
marketplace install all
RC

  # Keys setzen, falls vorhanden
  if [[ -n "${SHODAN_API:-}" ]]; then
    printf 'keys add shodan_api %s\n' "${SHODAN_API}" >> "${BOOT_RC}"
  fi

  if [[ -n "${CENSYSIO_ID:-}" ]]; then
    printf 'keys add censysio_id %s\n' "${CENSYSIO_ID}" >> "${BOOT_RC}"
  fi

  if [[ -n "${CENSYSIO_SECRET:-}" ]]; then
    printf 'keys add censysio_secret %s\n' "${CENSYSIO_SECRET}" >> "${BOOT_RC}"
  fi

  if [[ -n "${VIRUSTOTAL_API:-}" ]]; then
    printf 'keys add virustotal_api %s\n' "${VIRUSTOTAL_API}" >> "${BOOT_RC}"
  fi

  # sauber beenden
  echo "exit" >> "${BOOT_RC}"

  # Bootstrap ausführen
  recon-ng -r "${BOOT_RC}"

  # Marker setzen
  touch "${MARKER}"
}

if [[ ! -f "${MARKER}" ]]; then
  echo "[recon-ng] First start bootstrap: installing marketplace modules + setting keys ..."
  bootstrap
  echo "[recon-ng] Bootstrap done."
fi

# Danach normal starten (interaktiv, falls tty/stdin_open gesetzt)
exec "$@"
