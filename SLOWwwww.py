import subprocess
import sys
import re
import time
import signal

# --- PRESET CONFIGURATION ---
# Format: "Key": {
#    "name": "Display Name", 
#    "rate": "speed", 
#    "delay": "base_latency", 
#    "jitter": "instability (+/- ms)", 
#    "loss": "packet drop %"
# }
PRESETS = {
    # --- CELLULAR (Mobile Data) ---
    "1": {"name": "GPRS (1 Bar)",     "rate": "50kbit",   "delay": "700ms", "jitter": "200ms", "loss": "5"},   # Very unstable
    "2": {"name": "2G (EDGE)",        "rate": "250kbit",  "delay": "400ms", "jitter": "50ms",  "loss": "1"},   # Stable but slow
    "3": {"name": "3G (HSPA)",        "rate": "3mbit",    "delay": "150ms", "jitter": "20ms",  "loss": "0.1"}, # Decent
    "4": {"name": "4G (LTE)",         "rate": "20mbit",   "delay": "50ms",  "jitter": "10ms",  "loss": "0"},   # Good
    "5": {"name": "5G (Low Latency)", "rate": "100mbit",  "delay": "10ms",  "jitter": "1ms",   "loss": "0"},   # Perfect

    # --- SATELLITE (Space) ---
    "l": {"name": "Legacy Sat (GEO)", "rate": "15mbit",   "delay": "600ms", "jitter": "60ms",  "loss": "0.5"}, # Weather interference
    "s": {"name": "Starlink (LEO)",   "rate": "150mbit",  "delay": "40ms",  "jitter": "15ms",  "loss": "0.5"}, # Handovers cause jitter

    # --- WIRED / WI-FI ---
    "d": {"name": "Dial-up (Retro)",  "rate": "56kbit",   "delay": "200ms", "jitter": "30ms",  "loss": "0"},   # Phone line noise
    "w": {"name": "Public Wi-Fi",     "rate": "2mbit",    "delay": "100ms", "jitter": "80ms",  "loss": "2"},   # Congested router
    "f": {"name": "Fiber (International)", "rate": "100mbit", "delay": "150ms", "jitter": "2ms", "loss": "0"},

    # --- THEORETICAL ---
    "6": {"name": "6G (Theoretical)", "rate": "1000gbit", "delay": "100us", "jitter": "0ms",   "loss": "0"},
    
    # --- CONTROLS ---
    "c": {"name": "Custom Settings",  "rate": None,       "delay": None,    "jitter": None,    "loss": None},
    "0": {"name": "Reset (Actual Speed)", "rate": "0",    "delay": "0",     "jitter": "0",     "loss": "0"}
}

def run_command(command):
    """Runs a shell command."""
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def get_active_interface():
    """Auto-detects the interface."""
    try:
        route = subprocess.check_output("ip route show default", shell=True, text=True)
        match = re.search(r"dev\s+(\S+)", route)
        if match: return match.group(1)
    except Exception: pass
    return None

def reset_network(interface):
    """Restores internet speed."""
    print(f"\n[*] Restoring actual speed on {interface}...")
    subprocess.run(f"tc qdisc del dev {interface} root", shell=True, stderr=subprocess.DEVNULL)

def apply_rules(interface, rate, delay, jitter, loss):
    """Applies traffic control rules."""
    # 1. Clear old rules
    subprocess.run(f"tc qdisc del dev {interface} root", shell=True, stderr=subprocess.DEVNULL)
    
    # 2. Build command
    cmd_parts = [f"tc qdisc add dev {interface} root netem"]
    
    if rate and rate != "0": 
        cmd_parts.append(f"rate {rate}")
    
    if delay and delay != "0":
        jitter_str = f" {jitter}" if jitter and jitter != "0" else ""
        cmd_parts.append(f"delay {delay}{jitter_str}")
        
    if loss and float(loss) > 0: 
        cmd_parts.append(f"loss {loss}%")

    full_command = " ".join(cmd_parts)
    print(f"[*] Applying: {full_command}")
    
    if run_command(full_command):
        print(f"[+] Active: {rate or 'Unlimited'} | {delay} delay (+/- {jitter}) | Loss: {loss}%")
    else:
        print("[-] Error: Are you running as root?")
        sys.exit(1)

def print_menu():
    print("\n" + "="*50)
    print(f"{'LINUX NETWORK SHAPER TOOL':^50}")
    print("="*50)
    print(f"{'PRESET':<5} {'NAME':<20} {'SPEED':<10} {'DELAY':<10}")
    print("-" * 50)
    
    groups = [
        ("CELLULAR", ["1", "2", "3", "4", "5"]),
        ("SATELLITE", ["l", "s"]),
        ("WIRED / WI-FI", ["d", "w", "f"]),
        ("THEORETICAL", ["6"])
    ]

    for title, keys in groups:
        print(f"\n--- {title} ---")
        for k in keys:
            p = PRESETS[k]
            # Show a summary of the stats
            print(f" [{k}]  {p['name']:<20} {p['rate']:<10} {p['delay']}")

    print("\n" + "-" * 50)
    print(" [c]  Custom Settings")
    print(" [0]  RESET")

def signal_handler(sig, frame):
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    if subprocess.call("id -u", shell=True, stdout=subprocess.DEVNULL) != 0:
        print("[-] Run with sudo.")
        sys.exit(1)

    interface = get_active_interface()
    if not interface:
        interface = input("[-] Interface not found. Enter manually (e.g. eth0): ")
    else:
        print(f"[*] Interface: {interface}")

    try:
        while True:
            print_menu()
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == "0":
                reset_network(interface)
                break
            if choice not in PRESETS: continue
            
            sel = PRESETS[choice]
            r, d, j, l = sel["rate"], sel["delay"], sel["jitter"], sel["loss"]
            
            if choice == "c":
                r = input("Speed (e.g. 5mbit): ")
                d = input("Latency (e.g. 50ms): ")
                j = input("Jitter (e.g. 10ms): ")
                l = input("Loss % (e.g. 1): ")
            else:
                # Ask if user wants to override the defaults for this preset
                # Just press enter to keep the realistic defaults
                print(f"\nDefault Chaos: Jitter={j}, Loss={l}%")
                override = input("Press ENTER to accept defaults, or type 'edit' to modify: ")
                if override == 'edit':
                    j = input(f"Jitter [{j}]: ") or j
                    l = input(f"Loss % [{l}]: ") or l

            apply_rules(interface, r, d, j, l)
            print("\n[!] Network shaped. Press CTRL+C to stop.")
            while True: time.sleep(1)

    except KeyboardInterrupt:
        reset_network(interface)

if __name__ == "__main__":
    main()