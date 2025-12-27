import os, re, sys, time, subprocess, platform
from datetime import datetime

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output.strip() if e.output else str(e)
        raise RuntimeError(f"Befehl '{' '.join(cmd)}' fehlgeschlagen: {output}") from None
    except FileNotFoundError:
        raise RuntimeError(f"Befehl '{cmd[0]}' nicht gefunden. Stellen Sie sicher, dass das Tool installiert ist.") from None

def windows_full_charge_capacity_mwh():
    # generate report
    out = os.path.join(os.path.expanduser("~"), "battery-report.html")
    run(["powercfg", "/batteryreport", "/output", out])
    html = open(out, "r", encoding="utf-8", errors="ignore").read()
    # try to find "Full Charge Capacity"
    m = re.search(r"Full Charge Capacity.*?</td>\s*<td[^>]*>\s*([\d,\.]+)\s*mWh", html, re.I | re.S)
    if not m:
        # fallback for different report formats
        m = re.search(r"Full Charge Capacity</span>\s*</td>\s*<td>\s*([\d,\.]+)\s*mWh", html, re.I)
    if not m:
        raise RuntimeError("Konnte 'Full Charge Capacity' im battery-report nicht finden.")
    return int(re.sub(r"[^\d]", "", m.group(1)))

def linux_full_charge_capacity_mwh():
    # prefer sysfs if present
    base = "/sys/class/power_supply"
    if os.path.isdir(base):
        bats = [d for d in os.listdir(base) if d.startswith("BAT")]
        if bats:
            b = os.path.join(base, bats[0])
            # energy_full in uWh
            for fn in ("energy_full", "energy_full_design"):
                p = os.path.join(b, fn)
                if os.path.exists(p):
                    uwh = int(open(p).read().strip())
                    return uwh // 1000
            # charge_full in uAh -> need voltage to convert, skip
    # fallback: upower
    out = run(["upower", "-e"])
    dev = next((l for l in out.splitlines() if "battery" in l.lower()), None)
    if not dev:
        raise RuntimeError("Kein Battery-Device via upower gefunden.")
    info = run(["upower", "-i", dev])
    m = re.search(r"energy-full:\s*([\d\.]+)\s*Wh", info, re.I)
    if not m:
        raise RuntimeError("Konnte energy-full nicht aus upower lesen.")
    return int(float(m.group(1)) * 1000)

def macos_full_charge_capacity_mwh():
    # via ioreg (MaxCapacity in mAh + Voltage mV -> mWh)
    out = run(["ioreg", "-rn", "AppleSmartBattery"])
    m1 = re.search(r"\"MaxCapacity\"\s*=\s*(\d+)", out)
    m2 = re.search(r"\"Voltage\"\s*=\s*(\d+)", out)
    if not (m1 and m2):
        raise RuntimeError("Konnte MaxCapacity/Voltage via ioreg nicht lesen.")
    mah = int(m1.group(1))
    mv = int(m2.group(1))
    # mWh = mAh * mV / 1000
    return int(mah * mv / 1000)

def battery_percent_and_status():
    system = platform.system().lower()
    if system == "windows":
        # WMI via powershell (no extra libs)
        ps = 'Get-CimInstance Win32_Battery | Select EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json'
        out = run(["powershell", "-NoProfile", "-Command", ps]).strip()
        # very small json parse without json lib? use json.
        import json
        j = json.loads(out)
        return int(j["EstimatedChargeRemaining"]), int(j["BatteryStatus"])
    elif system == "linux":
        # sysfs
        base = "/sys/class/power_supply"
        bats = [d for d in os.listdir(base) if d.startswith("BAT")] if os.path.isdir(base) else []
        if bats:
            b = os.path.join(base, bats[0])
            cap = int(open(os.path.join(b, "capacity")).read().strip())
            status = open(os.path.join(b, "status")).read().strip().lower()  # charging/discharging/full
            return cap, status
        # upower fallback
        out = run(["upower", "-e"])
        dev = next((l for l in out.splitlines() if "battery" in l.lower()), None)
        info = run(["upower", "-i", dev])
        cap = int(re.search(r"percentage:\s*(\d+)%", info, re.I).group(1))
        st = re.search(r"state:\s*(\w+)", info, re.I).group(1).lower()
        return cap, st
    elif system == "darwin":
        out = run(["pmset", "-g", "batt"])
        # e.g. "... 73%; charging; ..."
        m = re.search(r"(\d+)%.*;\s*([a-zA-Z]+);", out)
        if not m:
            raise RuntimeError("Konnte pmset Ausgabe nicht parsen.")
        return int(m.group(1)), m.group(2).lower()
    else:
        raise RuntimeError(f"Unbekanntes OS: {platform.system()}")

def get_capacity_mwh():
    system = platform.system().lower()
    if system == "windows":
        return windows_full_charge_capacity_mwh()
    if system == "linux":
        return linux_full_charge_capacity_mwh()
    if system == "darwin":
        return macos_full_charge_capacity_mwh()
    raise RuntimeError("Dieses OS wird nicht unterstützt.")

def main(interval_sec=30, capacity_mwh=None):
    if capacity_mwh is None:
        capacity_mwh = get_capacity_mwh()

    prev_pct, _ = battery_percent_and_status()
    prev_t = time.time()
    print(f"Capacity: {capacity_mwh} mWh | interval={interval_sec}s | Ctrl+C beendet")

    while True:
        time.sleep(interval_sec)
        try:
            pct, st = battery_percent_and_status()
            t = time.time()

            dp = pct - prev_pct
            dh = (t - prev_t) / 3600.0

            ts = datetime.now().strftime("%H:%M:%S")
            if dp != 0 and dh > 0:
                delta_mwh = capacity_mwh * (dp / 100.0)
                w = (delta_mwh / dh) / 1000.0
                print(f"{ts}  {pct:3d}%  Δ{dp:+4d}%  ~ {w:7.2f} W  status={st}")
            else:
                print(f"{ts}  {pct:3d}%  (keine Änderung)  status={st}")

            prev_pct, prev_t = pct, t
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"{ts}  Fehler beim Abrufen des Batteriestatus: {e}")

if __name__ == "__main__":
    # optional: python battery_live.py 30 60000
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(interval_sec=interval, capacity_mwh=cap)
