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

def get_battery_info():
    system = platform.system().lower()
    if system == "windows":
        # Get RemainingCapacity, FullChargedCapacity and Status via WMI (root/wmi)
        ps = (
            "$status = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus; "
            "$full = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity; "
            "$base = Get-CimInstance Win32_Battery; "
            "$res = @{ "
            "  Remaining = $status.RemainingCapacity; "
            "  Full = $full.FullChargedCapacity; "
            "  Status = $base.BatteryStatus; "
            "  Percent = $base.EstimatedChargeRemaining "
            "}; "
            "$res | ConvertTo-Json"
        )
        try:
            out = run(["powershell", "-NoProfile", "-Command", ps]).strip()
            import json
            j = json.loads(out)
            # BatteryStatus 2 is Discharging, 1 is Other (often Charging), 3 is Fully Charged, etc.
            # Map to string
            st_map = {1: "Charging", 2: "Discharging", 3: "Fully Charged", 4: "Low", 5: "Critical", 6: "Charging", 7: "Charging and High", 8: "Charging and Low", 9: "Charging and Critical", 10: "Undefined", 11: "Partially Charged"}
            st = st_map.get(j["Status"], f"Unknown({j['Status']})")
            if j["Status"] in (6, 7, 8, 9): st = "charging"
            elif j["Status"] == 2: st = "discharging"
            elif j["Status"] == 3: st = "full"
            return j["Remaining"], j["Full"], st.lower(), j["Percent"]
        except Exception:
            # Fallback to existing percentage-based logic if WMI root/wmi fails
            pct, st_code = battery_percent_and_status()
            full = windows_full_charge_capacity_mwh()
            curr = int(full * pct / 100.0)
            st = "discharging" if st_code == 2 else "charging" # simple fallback
            return curr, full, st, pct

    elif system == "linux":
        base = "/sys/class/power_supply"
        bats = [d for d in os.listdir(base) if d.startswith("BAT")] if os.path.isdir(base) else []
        if bats:
            b = os.path.join(base, bats[0])
            def read_file(name):
                p = os.path.join(b, name)
                return open(p).read().strip() if os.path.exists(p) else None
            
            curr_uwh = read_file("energy_now")
            full_uwh = read_file("energy_full")
            if curr_uwh and full_uwh:
                curr = int(curr_uwh) // 1000
                full = int(full_uwh) // 1000
                st = read_file("status").lower()
                pct = int(read_file("capacity"))
                return curr, full, st, pct
            # Fallback to Ah
            curr_uah = read_file("charge_now")
            full_uah = read_file("charge_full")
            volt_uv = read_file("voltage_now")
            if curr_uah and full_uah and volt_uv:
                volt = int(volt_uv) / 1000000.0
                curr = int(int(curr_uah) * volt / 1000.0)
                full = int(int(full_uah) * volt / 1000.0)
                st = read_file("status").lower()
                pct = int(read_file("capacity"))
                return curr, full, st, pct

        # upower fallback
        out = run(["upower", "-e"])
        dev = next((l for l in out.splitlines() if "battery" in l.lower()), None)
        if dev:
            info = run(["upower", "-i", dev])
            curr_wh = re.search(r"energy:\s*([\d\.]+)\s*Wh", info, re.I)
            full_wh = re.search(r"energy-full:\s*([\d\.]+)\s*Wh", info, re.I)
            pct = re.search(r"percentage:\s*(\d+)%", info, re.I)
            st = re.search(r"state:\s*(\w+)", info, re.I)
            if curr_wh and full_wh and pct and st:
                return int(float(curr_wh.group(1)) * 1000), int(float(full_wh.group(1)) * 1000), st.group(1).lower(), int(pct.group(1))
        
        raise RuntimeError("Konnte Batteriedaten auf Linux nicht lesen.")

    elif system == "darwin":
        out = run(["ioreg", "-rn", "AppleSmartBattery"])
        curr_mah = int(re.search(r"\"CurrentCapacity\"\s*=\s*(\d+)", out).group(1))
        max_mah = int(re.search(r"\"MaxCapacity\"\s*=\s*(\d+)", out).group(1))
        volt_mv = int(re.search(r"\"Voltage\"\s*=\s*(\d+)", out).group(1))
        st_out = run(["pmset", "-g", "batt"])
        m = re.search(r"(\d+)%.*;\s*([a-zA-Z]+);", st_out)
        pct = int(m.group(1))
        st = m.group(2).lower()
        curr_mwh = int(curr_mah * volt_mv / 1000)
        full_mwh = int(max_mah * volt_mv / 1000)
        return curr_mwh, full_mwh, st, pct
    
    raise RuntimeError(f"OS {system} nicht unterstützt.")

def main(interval_sec=30):
    if interval_sec < 5 or interval_sec > 60:
        print(f"Warnung: Intervall {interval_sec}s liegt außerhalb von 5-60s. Setze auf Standard 30s.")
        interval_sec = 30

    curr_mwh, full_mwh, st, pct = get_battery_info()
    prev_mwh = curr_mwh
    prev_t = time.time()
    
    print(f"Batterie Kapazität: {full_mwh} mWh")
    print(f"Messintervall: {interval_sec}s (einstellbar 5-60s)")
    print(f"Zeit      | Ladung | Status      | Delta mWh | Leistung (W)")
    print("-" * 60)

    while True:
        try:
            time.sleep(interval_sec)
            curr_mwh, full_mwh, st, pct = get_battery_info()
            t = time.time()
            dt = t - prev_t
            dmwh = curr_mwh - prev_mwh
            
            # Leistung in Watt: (mWh / 1000) / (sec / 3600) = (mWh * 3.6) / sec
            p_watt = (dmwh * 3.6) / dt
            
            ts = datetime.now().strftime("%H:%M:%S")
            
            if dmwh > 0:
                detail = f"Aufladung: +{dmwh:4d} mWh"
            elif dmwh < 0:
                detail = f"Verbrauch: {dmwh:4d} mWh"
            else:
                detail = f"Keine Änderung    "
                
            print(f"{ts} | {pct:3d}%  | {st:11s} | {detail} | {p_watt:7.2f} W")
            
            prev_mwh, prev_t = curr_mwh, t
        except KeyboardInterrupt:
            print("\nBeendet durch Benutzer.")
            break
        except Exception as e:
            print(f"\nFehler: {e}")
            time.sleep(interval_sec)

if __name__ == "__main__":
    # Aufruf: python battery-check.py [Intervall in Sek]
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    main(interval_sec=interval)
