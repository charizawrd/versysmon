"""
Versysmon - System Hardware Logic

Provides low-level access to CPU, RAM, Disk, and Battery metrics.
Wraps psutil and Windows Management Instrumentation (WMI) to fetch 
real-time hardware diagnostics and power states without blocking the UI.
"""
import psutil
import ctypes
import os
import time
import cpuinfo

def get_sys_stats():
    """Gets the basic dashboard stats."""
    mem = psutil.virtual_memory()
    return {
        "cpu_perc": psutil.cpu_percent(),
        "ram_gb": mem.used / (1024**3),
        "ram_total_gb": mem.total / (1024**3),                   
        "ram_perc": mem.percent
    }

def get_detailed_ram():
    """Gets data for the 3-color memory composition bar."""
    mem = psutil.virtual_memory()
                                                                           
    cached = mem.available - mem.free
    return {
        "used": mem.used,
        "cached": max(0, cached),
        "free": mem.free,
        "total": mem.total
    }

def get_top_ram_hogs():
    """Returns the top 12 memory-heavy processes."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
                                                               
            mem_mb = p.info['memory_info'].rss / (1024 * 1024)
            procs.append((p.info['name'], p.info['pid'], mem_mb))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
                                     
    procs.sort(key=lambda x: x[2], reverse=True)
    return procs[:12]

def kill_process(pid):
    """The Kill Switch."""
    try:
        psutil.Process(pid).terminate()
        return True
    except:
        return False

def clean_memory():
    """
    THE MEMREDUCT CLONE: Uses Windows API to force apps to empty their 
    working sets and dump memory to the pagefile.
    """
    psapi = ctypes.WinDLL('psapi')
    kernel32 = ctypes.WinDLL('kernel32')
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_QUERY_INFORMATION = 0x0400

    freed_apps = 0
    for p in psutil.process_iter(['pid']):
        try:
                                                                   
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, p.info['pid'])
            if handle:
                                        
                psapi.EmptyWorkingSet(handle)
                kernel32.CloseHandle(handle)
                freed_apps += 1
        except:
            continue
    return freed_apps

def get_cpu_hardware_info():
    """Fetches static hardware info about the CPU."""
    info = cpuinfo.get_cpu_info()
    freq = psutil.cpu_freq()
    
    return {
        "name": info.get("brand_raw", "Unknown CPU"),
        "arch": info.get("arch_string_raw", info.get("arch", "Unknown")),
        "cores": psutil.cpu_count(logical=False),
        "threads": psutil.cpu_count(logical=True),
        "base_clock": (freq.max / 1000) if freq and freq.max else 0.0      
    }

def get_cpu_core_usage():
    """Returns a list of usage percentages for every logical thread."""
    return psutil.cpu_percent(interval=None, percpu=True)


class DiskTracker:
    """Tracks disk read/write speeds between calls."""
    def __init__(self):
        self.old_io = psutil.disk_io_counters()
        self.old_time = time.time()

    def get_speeds(self):
        """Returns (read_MB/s, write_MB/s)."""
        new_io = psutil.disk_io_counters()
        new_time = time.time()
        dt = new_time - self.old_time
        if dt <= 0:
            return 0.0, 0.0

        read = (new_io.read_bytes - self.old_io.read_bytes) / dt / (1024 * 1024)
        write = (new_io.write_bytes - self.old_io.write_bytes) / dt / (1024 * 1024)

        self.old_io = new_io
        self.old_time = new_time
        return max(0, read), max(0, write)


def get_disk_partitions():
    """Returns partition usage info for all mounted drives."""
    partitions = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            })
        except (PermissionError, OSError):
            pass
    return partitions


def get_battery_info():
    """Returns battery status or None if no battery is present."""
    bat = psutil.sensors_battery()
    if bat is None:
        return None
    secs = bat.secsleft
                                                                                                
    if secs < 0 or secs > 360000:  
        secs = -1
    return {
        "percent": bat.percent,
        "plugged": bat.power_plugged,
        "secs_left": secs
    }


def get_system_info():
    """Returns uptime string, boot time, and total process count."""
    from datetime import datetime
    boot = psutil.boot_time()
    uptime_secs = time.time() - boot
    days = int(uptime_secs // 86400)
    hours = int((uptime_secs % 86400) // 3600)
    mins = int((uptime_secs % 3600) // 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")

    return {
        "uptime_str": " ".join(parts),
        "boot_time": datetime.fromtimestamp(boot).strftime("%b %d, %I:%M %p"),
        "process_count": len(psutil.pids())
    }


def get_detailed_battery_info():
    """Fetches detailed battery specifications via WMI (Windows only)."""
    if os.name != 'nt':
        return None
        
    try:
        import subprocess
        import json
        cmd = 'powershell -Command "Get-CimInstance Win32_Battery | Select-Object Name, BatteryStatus, Chemistry, EstimatedChargeRemaining, EstimatedRunTime, DesignVoltage | ConvertTo-Json"'
        out = subprocess.check_output(cmd, shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
        if not out:
            return None
            
        data = json.loads(out)
        if isinstance(data, list):
            data = data[0]                                 
            
        chemistry_map = {
            1: "Other", 2: "Unknown", 3: "Lead Acid", 4: "Nickel Cadmium",
            5: "Nickel Metal Hydride", 6: "Lithium-ion", 7: "Zinc Air", 8: "Lithium Polymer"
        }
        
        status_map = {
            1: "Discharging", 2: "AC Power", 3: "Fully Charged", 4: "Low",
            5: "Critical", 6: "Charging", 7: "Charging / High", 8: "Charging / Low",
            9: "Charging / Critical", 10: "Undefined", 11: "Partially Charged"
        }
        
        voltage = data.get("DesignVoltage")
        voltage_str = f"{voltage / 1000.0:.2f} V" if voltage else "Unknown"
        
        chem_code = data.get("Chemistry")
        chem_str = chemistry_map.get(chem_code, f"Unknown ({chem_code})")
        
        stat_code = data.get("BatteryStatus")
        stat_str = status_map.get(stat_code, f"Unknown ({stat_code})")
        
        return {
            "Battery Name": data.get("Name", "Unknown"),
            "Chemistry": chem_str,
            "Power Status": stat_str,
            "Design Voltage": voltage_str,
            "Charge Remaining": f"{data.get('EstimatedChargeRemaining', 'Unknown')}%"
        }
    except Exception:
        return None