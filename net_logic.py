"""
Versysmon - Network Packet Tracking

Maintains the background thread that intercepts and tracks per-process 
network bandwidth usage. Logs traffic data continuously to the local 
SQLite database for historical analysis.
"""
import psutil
import time
import socket
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
from db_logic import log_app_usage

class NetTracker:
    """Handles the live speed for the UI (Total System Speed)"""
    def __init__(self):
        self.old_io = psutil.net_io_counters()
        self.old_time = time.time()

    def get_speeds(self):
        new_io = psutil.net_io_counters()
        new_time = time.time()
        dt = new_time - self.old_time
        
        up = (new_io.bytes_sent - self.old_io.bytes_sent) / dt / 1024 / 1024 
        down = (new_io.bytes_recv - self.old_io.bytes_recv) / dt / 1024 / 1024 
        
        self.old_io = new_io
        self.old_time = new_time
        return up, down


class AppTrackerThread(QThread):
    """Background engine that logs per-app usage using a Weighted Heuristic"""
    def __init__(self):
        super().__init__()
        self.running = True
        self.old_sys_io = psutil.net_io_counters()
        self.old_proc_io = {}                                             

    def run(self):
        while self.running:
            time.sleep(5) 
            
                                                               
            new_sys_io = psutil.net_io_counters()
            net_bytes = (new_sys_io.bytes_recv - self.old_sys_io.bytes_recv) +\
                        (new_sys_io.bytes_sent - self.old_sys_io.bytes_sent)
            self.old_sys_io = new_sys_io
            
            if net_bytes <= 0:
                continue

            active_procs = []
            new_proc_io = {}

                                                                        
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'ESTABLISHED' and conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            name = proc.name()
                            
                            if name in ["svchost.exe", "System Idle Process", "System"]:
                                continue

                                                                                       
                            io = proc.io_counters()
                            total_io = io.read_bytes + io.write_bytes
                            
                            active_procs.append((name, conn.pid, total_io))
                            new_proc_io[conn.pid] = total_io
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
            except psutil.AccessDenied:
                pass 

                                                                        
            app_weights = {}
            total_weight = 0

            for name, pid, current_io in active_procs:
                                                              
                last_io = self.old_proc_io.get(pid, current_io)
                delta_io = current_io - last_io
                
                                                                                               
                weight = max(delta_io, 1) 
                
                if name not in app_weights:
                    app_weights[name] = 0
                
                app_weights[name] += weight
                total_weight += weight

                                                   
            self.old_proc_io = new_proc_io

                                                                             
            if total_weight > 0:
                for app_name, weight in app_weights.items():
                                                                             
                    app_net_bytes = int(net_bytes * (weight / total_weight))
                    
                    if app_net_bytes > 0:
                        log_app_usage(app_name, app_net_bytes)

    def stop(self):
        self.running = False
        self.wait()

def get_wifi_details():
    """Secretly runs a Windows command to get Wi-Fi SSID and Band info."""
    wifi_info = {}
    try:
                                                                                
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], 
            capture_output=True, text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        current_name = None
        for line in result.stdout.split('\n'):
            line = line.strip()
                                   
            if line.startswith("Name"):
                current_name = line.split(":", 1)[1].strip()
                wifi_info[current_name] = {}
            elif current_name:
                                  
                if line.startswith("SSID") and not line.startswith("BSSID"):
                    wifi_info[current_name]["ssid"] = line.split(":", 1)[1].strip()
                elif line.startswith("Band"):
                    wifi_info[current_name]["band"] = line.split(":", 1)[1].strip()
                elif line.startswith("Radio type"):
                    wifi_info[current_name]["radio"] = line.split(":", 1)[1].strip()
    except Exception:
        pass
    return wifi_info

def get_adapter_info():
    """Scans for active network adapters and attaches Wi-Fi details if found."""
    adapters = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    
                                 
    wifi_details = get_wifi_details()
    
    for name, addresses in addrs.items():
        stat = stats.get(name)
        if not stat or not stat.isup or "Loopback" in name:
            continue
            
        info = {"name": name, "ipv4": "N/A", "mac": "N/A", "wifi": None}
        
        for addr in addresses:
            if addr.family == socket.AF_INET:
                info["ipv4"] = addr.address
            elif addr.family == psutil.AF_LINK: 
                info["mac"] = addr.address
        
        if info["ipv4"] != "N/A" and not info["ipv4"].startswith("169.254"):
                                                                       
            if name in wifi_details and "ssid" in wifi_details[name]:
                info["wifi"] = wifi_details[name]
                
            adapters.append(info)
            
    return adapters