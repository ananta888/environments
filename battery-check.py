import os, re, sys, time, subprocess, platform, json
from datetime import datetime

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output.strip() if e.output else str(e)
        raise RuntimeError(f"Befehl '{' '.join(cmd)}' fehlgeschlagen: {output}") from None
    except FileNotFoundError:
        raise RuntimeError(f"Befehl '{cmd[0]}' nicht gefunden. Stellen Sie sicher, dass das Tool installiert ist.") from None

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
            # Fallback if WMI root/wmi fails
            ps_fallback = 'Get-CimInstance Win32_Battery | Select EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json'
            try:
                out = run(["powershell", "-NoProfile", "-Command", ps_fallback]).strip()
                j = json.loads(out)
                pct = int(j["EstimatedChargeRemaining"])
                st_code = int(j["BatteryStatus"])
                st = "discharging" if st_code == 2 else "charging"
                # For fallback mWh, we try powercfg once or just use a dummy full capacity
                full = 60000 # Default fallback
                curr = int(full * pct / 100.0)
                return curr, full, st, pct
            except:
                raise RuntimeError("Konnte Batteriedaten auf Windows nicht lesen.")

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

def main(interval_sec=5):
    if interval_sec < 5 or interval_sec > 60:
        print(f"Warnung: Intervall {interval_sec}s liegt außerhalb von 5-60s. Setze auf Standard 5s.")
        interval_sec = 5

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
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    main(interval_sec=interval)
