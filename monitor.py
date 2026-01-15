#!/opt/srvmon/venv/bin/python3

from quart import Quart, render_template
import asyncio
import aiohttp
import ssl
from datetime import datetime

# Import configuration (copy config.example.py to config.py and add your credentials)
try:
    from config import PROXMOX_HOST, PROXMOX_TOKEN_ID, PROXMOX_TOKEN_SECRET, PROXMOX_VERIFY_SSL
except ImportError:
    # Default values if config.py doesn't exist
    PROXMOX_HOST = ""
    PROXMOX_TOKEN_ID = ""
    PROXMOX_TOKEN_SECRET = ""
    PROXMOX_VERIFY_SSL = False

try:
    from config import BMC_DEVICES
except ImportError:
    BMC_DEVICES = []

try:
    from config import SNMP_DEVICES
except ImportError:
    SNMP_DEVICES = []

app = Quart(__name__)



# =============================================================================
# SERVICES TO MONITOR
# =============================================================================

SERVICES = {
    "General Web": {
        "Google Search": "https://www.google.com",
        "YouTube": "https://www.youtube.com",
        "Facebook": "https://www.facebook.com",
        "Twitter": "https://twitter.com",
        "Instagram": "https://www.instagram.com",
        "Reddit": "https://www.reddit.com",
        "TikTok": "https://www.tiktok.com",
    },
    "Productivity / Email": {
        "Gmail": "https://mail.google.com",
        "Outlook / Office365": "https://outlook.office365.com",
        "Google Drive": "https://drive.google.com",
        "Dropbox": "https://www.dropbox.com",
        "OneDrive": "https://onedrive.live.com",
        "Slack": "https://slack.com",
    },
    "Enterprise SaaS": {
        "Salesforce": "https://login.salesforce.com",
        "Zoom": "https://zoom.us",
        "Microsoft Teams": "https://teams.microsoft.com",
        "Atlassian": "https://www.atlassian.com",
        "Zendesk": "https://www.zendesk.com",
        "Box": "https://www.box.com",
    },
    "Developer Tools": {
        "GitHub": "https://github.com",
        "GitLab": "https://gitlab.com",
        "Bitbucket": "https://bitbucket.org",
        "AWS": "https://aws.amazon.com",
        "Azure": "https://portal.azure.com",
        "Cloudflare": "https://www.cloudflare.com",
        "DigitalOcean": "https://www.digitalocean.com",
        "Heroku": "https://www.heroku.com",
    },
    "Other": {
        "Steam": "https://store.steampowered.com",
        "OpenAI": "https://api.openai.com/v1/models",
        "WhatsApp Web": "https://web.whatsapp.com",
        "LinkedIn": "https://www.linkedin.com",
    }
}

STATUS = {}

# =============================================================================
# SERVICE STATUS CHECKING
# =============================================================================

async def fetch_status(session, name, url):
    """Fetch the status of a single service."""
    try:
        start = asyncio.get_event_loop().time()
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            end = asyncio.get_event_loop().time()
            STATUS[name] = {
                "code": response.status,
                "status": "up" if response.status < 400 else "warning",
                "response_time": round((end - start) * 1000)
            }
    except Exception:
        STATUS[name] = {
            "code": None,
            "status": "down",
            "response_time": None
        }

async def check_services_async():
    """Check all services concurrently."""
    tasks = []
    async with aiohttp.ClientSession() as session:
        for category, services in SERVICES.items():
            for name, url in services.items():
                tasks.append(fetch_status(session, name, url))
        await asyncio.gather(*tasks)

# =============================================================================
# PROXMOX API INTEGRATION
# =============================================================================

def get_proxmox_headers():
    """Get authorization headers for Proxmox API."""
    return {
        "Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"
    }

def get_ssl_context():
    """Get SSL context for Proxmox API requests."""
    if PROXMOX_VERIFY_SSL:
        return None
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

async def fetch_proxmox_nodes(session):
    """Fetch Proxmox cluster nodes status."""
    try:
        url = f"{PROXMOX_HOST}/api2/json/nodes"
        async with session.get(url, headers=get_proxmox_headers(),
                               ssl=get_ssl_context(),
                               timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            return []
    except Exception as e:
        print(f"Error fetching Proxmox nodes: {e}")
        return []

async def fetch_proxmox_resources(session):
    """Fetch all Proxmox cluster resources (VMs and containers)."""
    try:
        url = f"{PROXMOX_HOST}/api2/json/cluster/resources"
        async with session.get(url, headers=get_proxmox_headers(),
                               ssl=get_ssl_context(),
                               timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                resources = data.get("data", [])
                # Filter to only VMs and containers
                return [r for r in resources if r.get("type") in ("qemu", "lxc")]
            return []
    except Exception as e:
        print(f"Error fetching Proxmox resources: {e}")
        return []

async def get_proxmox_data():
    """Fetch all Proxmox data concurrently."""
    connector = aiohttp.TCPConnector(ssl=get_ssl_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        nodes, vms = await asyncio.gather(
            fetch_proxmox_nodes(session),
            fetch_proxmox_resources(session)
        )
        return nodes, vms

def format_bytes(bytes_val):
    """Format bytes to human-readable string."""
    if bytes_val is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"

def process_node_data(node):
    """Process raw node data into display format."""
    mem_used = node.get("mem", 0)
    mem_total = node.get("maxmem", 1)
    disk_used = node.get("disk", 0)
    disk_total = node.get("maxdisk", 1)
    cpu = node.get("cpu", 0)

    return {
        "name": node.get("node", "Unknown"),
        "status": "up" if node.get("status") == "online" else "down",
        "uptime": node.get("uptime", 0),
        "cpu_percent": round(cpu * 100, 1),
        "mem_percent": round((mem_used / mem_total) * 100, 1) if mem_total else 0,
        "mem_used": format_bytes(mem_used),
        "mem_total": format_bytes(mem_total),
        "disk_percent": round((disk_used / disk_total) * 100, 1) if disk_total else 0,
        "disk_used": format_bytes(disk_used),
        "disk_total": format_bytes(disk_total),
    }

def process_vm_data(vm):
    """Process raw VM/container data into display format."""
    mem_used = vm.get("mem", 0)
    mem_total = vm.get("maxmem", 1)
    cpu = vm.get("cpu", 0)

    return {
        "vmid": vm.get("vmid", 0),
        "name": vm.get("name", f"VM {vm.get('vmid', 'Unknown')}"),
        "type": vm.get("type", "qemu"),
        "status": "up" if vm.get("status") == "running" else "down",
        "node": vm.get("node", "Unknown"),
        "cpu_percent": round(cpu * 100, 1),
        "mem_percent": round((mem_used / mem_total) * 100, 1) if mem_total else 0,
        "mem_used": format_bytes(mem_used),
        "mem_total": format_bytes(mem_total),
        "uptime": vm.get("uptime", 0),
    }

# =============================================================================
# BMC/REDFISH INTEGRATION
# =============================================================================

async def fetch_redfish_endpoint(session, base_url, endpoint, auth):
    """Fetch data from a Redfish API endpoint."""
    url = f"{base_url}{endpoint}"
    try:
        async with session.get(url, auth=auth, ssl=False,
                               timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status == 200:
                return await response.json()
            return None
    except Exception:
        return None

async def fetch_bmc_status(device):
    """Fetch BMC status via Redfish API."""
    base_url = f"https://{device['host']}/redfish/v1"
    auth = aiohttp.BasicAuth(device["username"], device["password"])

    result = {
        "name": device["name"],
        "host": device["host"],
        "power": "unknown",
        "health": "Unknown",
        "model": "",
        "serial": "",
        "sensor_categories": {
            "temperature": [],
            "fan": [],
            "voltage": [],
            "power": [],
        },
        "storage": {
            "controllers": [],
            "drives": [],
            "volumes": [],
        },
        "sel_entries": [],
        "error": None,
    }

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Fetch all data concurrently
            system_data, thermal_data, power_data, storage_data, sel_data = await asyncio.gather(
                fetch_redfish_endpoint(session, base_url, "/Systems/1", auth),
                fetch_redfish_endpoint(session, base_url, "/Chassis/1/Thermal", auth),
                fetch_redfish_endpoint(session, base_url, "/Chassis/1/Power", auth),
                fetch_redfish_endpoint(session, base_url, "/Systems/1/Storage", auth),
                fetch_redfish_endpoint(session, base_url, "/Managers/1/LogServices/SEL/Entries", auth),
            )

            # Process system info
            if system_data:
                result["power"] = system_data.get("PowerState", "Unknown")
                result["health"] = system_data.get("Status", {}).get("Health", "Unknown")
                result["model"] = system_data.get("Model", "")
                result["serial"] = system_data.get("SerialNumber", "")
            else:
                result["error"] = "Unable to connect to Redfish API"
                return result

            # Process thermal data (temperatures and fans)
            if thermal_data:
                # Temperatures
                for temp in thermal_data.get("Temperatures", []):
                    if temp.get("ReadingCelsius") is not None:
                        health = temp.get("Status", {}).get("Health", "OK")
                        result["sensor_categories"]["temperature"].append({
                            "name": temp.get("Name", "Unknown"),
                            "value": temp.get("ReadingCelsius"),
                            "units": "°C",
                            "state": "ok" if health == "OK" else "warning" if health == "Warning" else "critical",
                        })
                # Fans
                for fan in thermal_data.get("Fans", []):
                    reading = fan.get("Reading") or fan.get("ReadingRPM")
                    if reading is not None:
                        health = fan.get("Status", {}).get("Health", "OK")
                        units = fan.get("ReadingUnits", "RPM")
                        result["sensor_categories"]["fan"].append({
                            "name": fan.get("Name", "Unknown"),
                            "value": reading,
                            "units": units if units else "RPM",
                            "state": "ok" if health == "OK" else "warning" if health == "Warning" else "critical",
                        })

            # Process power data
            if power_data:
                # Power consumption
                for pc in power_data.get("PowerControl", []):
                    watts = pc.get("PowerConsumedWatts")
                    if watts is not None:
                        result["sensor_categories"]["power"].append({
                            "name": pc.get("Name", "Power Consumption"),
                            "value": watts,
                            "units": "W",
                            "state": "ok",
                        })
                # Voltages
                for volt in power_data.get("Voltages", []):
                    reading = volt.get("ReadingVolts")
                    if reading is not None:
                        health = volt.get("Status", {}).get("Health", "OK")
                        result["sensor_categories"]["voltage"].append({
                            "name": volt.get("Name", "Unknown"),
                            "value": reading,
                            "units": "V",
                            "state": "ok" if health == "OK" else "warning" if health == "Warning" else "critical",
                        })

            # Process storage data
            if storage_data:
                members = storage_data.get("Members", [])
                for member in members:
                    member_url = member.get("@odata.id", "")
                    if member_url:
                        controller_data = await fetch_redfish_endpoint(session, f"https://{device['host']}", member_url, auth)
                        if controller_data:
                            # Controller info
                            controller_health = controller_data.get("Status", {}).get("Health", "Unknown")
                            result["storage"]["controllers"].append({
                                "name": controller_data.get("Name", "Storage Controller"),
                                "health": controller_health,
                                "state": "ok" if controller_health == "OK" else "warning" if controller_health == "Warning" else "critical",
                            })

                            # Get drives
                            drives_link = controller_data.get("Drives", [])
                            for drive_ref in drives_link:
                                drive_url = drive_ref.get("@odata.id", "")
                                if drive_url:
                                    drive_data = await fetch_redfish_endpoint(session, f"https://{device['host']}", drive_url, auth)
                                    if drive_data:
                                        drive_health = drive_data.get("Status", {}).get("Health", "Unknown")
                                        capacity_bytes = drive_data.get("CapacityBytes", 0)
                                        capacity_gb = round(capacity_bytes / (1024**3), 1) if capacity_bytes else 0
                                        result["storage"]["drives"].append({
                                            "name": drive_data.get("Name", "Unknown Drive"),
                                            "capacity": f"{capacity_gb} GB",
                                            "health": drive_health,
                                            "state": "ok" if drive_health == "OK" else "warning" if drive_health == "Warning" else "critical",
                                            "type": drive_data.get("MediaType", "Unknown"),
                                            "protocol": drive_data.get("Protocol", ""),
                                            "predicted_failure": drive_data.get("PredictedMediaLifeLeftPercent", None),
                                        })

                            # Get volumes
                            volumes_link = controller_data.get("Volumes", {}).get("@odata.id", "")
                            if volumes_link:
                                volumes_data = await fetch_redfish_endpoint(session, f"https://{device['host']}", volumes_link, auth)
                                if volumes_data:
                                    for vol_ref in volumes_data.get("Members", []):
                                        vol_url = vol_ref.get("@odata.id", "")
                                        if vol_url:
                                            vol_data = await fetch_redfish_endpoint(session, f"https://{device['host']}", vol_url, auth)
                                            if vol_data:
                                                vol_health = vol_data.get("Status", {}).get("Health", "Unknown")
                                                vol_capacity = vol_data.get("CapacityBytes", 0)
                                                vol_capacity_gb = round(vol_capacity / (1024**3), 1) if vol_capacity else 0
                                                raid_types = vol_data.get("RAIDType", "Unknown")
                                                result["storage"]["volumes"].append({
                                                    "name": vol_data.get("Name", "Unknown Volume"),
                                                    "capacity": f"{vol_capacity_gb} GB",
                                                    "raid": raid_types,
                                                    "health": vol_health,
                                                    "state": "ok" if vol_health == "OK" else "warning" if vol_health == "Warning" else "critical",
                                                })

            # Process SEL entries
            if sel_data:
                entries = sel_data.get("Members", [])[-10:]  # Last 10 entries
                for entry in entries:
                    severity = entry.get("Severity", "OK")
                    result["sel_entries"].append({
                        "id": entry.get("Id", ""),
                        "timestamp": entry.get("Created", ""),
                        "message": entry.get("Message", str(entry)),
                        "severity": "critical" if severity == "Critical" else "warning" if severity == "Warning" else "info",
                    })

    except Exception as e:
        result["error"] = str(e)

    return result

async def get_all_bmc_data():
    """Fetch all BMC data concurrently."""
    if not BMC_DEVICES:
        return []

    tasks = [fetch_bmc_status(device) for device in BMC_DEVICES]
    results = await asyncio.gather(*tasks)
    return results

# =============================================================================
# SNMP INTEGRATION
# =============================================================================

try:
    from pysnmp.hlapi.asyncio import (
        getCmd, bulkCmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity
    )
    SNMP_AVAILABLE = True
except ImportError:
    SNMP_AVAILABLE = False

# Standard OIDs
SNMP_OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
}

# Table OIDs for bulk walks
SNMP_TABLES = {
    "hrProcessorLoad": "1.3.6.1.2.1.25.3.3.1.2",  # CPU load per processor
    "hrStorageDescr": "1.3.6.1.2.1.25.2.3.1.3",   # Storage description
    "hrStorageSize": "1.3.6.1.2.1.25.2.3.1.5",    # Storage size
    "hrStorageUsed": "1.3.6.1.2.1.25.2.3.1.6",    # Storage used
    "hrStorageAllocationUnits": "1.3.6.1.2.1.25.2.3.1.4",  # Allocation units
    "hrStorageType": "1.3.6.1.2.1.25.2.3.1.2",    # Storage type
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",             # Interface description
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",        # Interface status
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",             # Interface speed
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",         # Bytes in
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",        # Bytes out
}

def format_uptime(timeticks):
    """Convert SNMP timeticks (1/100 seconds) to human-readable format."""
    if timeticks is None:
        return "Unknown"
    seconds = int(timeticks) // 100
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    else:
        return f"{minutes}m {secs}s"

def format_speed(speed_bps):
    """Format interface speed to human-readable format."""
    if speed_bps is None or speed_bps == 0:
        return "Unknown"
    if speed_bps >= 1000000000:
        return f"{speed_bps // 1000000000} Gbps"
    elif speed_bps >= 1000000:
        return f"{speed_bps // 1000000} Mbps"
    elif speed_bps >= 1000:
        return f"{speed_bps // 1000} Kbps"
    return f"{speed_bps} bps"

def format_octets(octets):
    """Format octet count to human-readable format."""
    if octets is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if octets < 1024:
            return f"{octets:.1f} {unit}"
        octets /= 1024
    return f"{octets:.1f} PB"

async def snmp_get(host, port, community, oids):
    """Perform SNMP GET for multiple OIDs."""
    results = {}
    try:
        engine = SnmpEngine()
        transport = UdpTransportTarget((host, port), timeout=5, retries=1)
        for name, oid in oids.items():
            errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                engine,
                CommunityData(community),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            if errorIndication or errorStatus:
                results[name] = None
            else:
                for varBind in varBinds:
                    results[name] = varBind[1].prettyPrint() if hasattr(varBind[1], 'prettyPrint') else str(varBind[1])
    except Exception as e:
        return None, str(e)
    return results, None

async def snmp_bulk_walk(host, port, community, oid_base, max_rows=100):
    """Perform SNMP bulk walk on a table OID."""
    results = {}
    try:
        engine = SnmpEngine()
        transport = UdpTransportTarget((host, port), timeout=5, retries=1)
        count = 0
        async for errorIndication, errorStatus, errorIndex, varBinds in bulkCmd(
            engine,
            CommunityData(community),
            transport,
            ContextData(),
            0, 25,  # nonRepeaters, maxRepetitions
            ObjectType(ObjectIdentity(oid_base)),
        ):
            if errorIndication or errorStatus:
                break
            for varBind in varBinds:
                oid_str = str(varBind[0])
                if not oid_str.startswith(oid_base):
                    return results
                # Extract the index from the OID
                index = oid_str[len(oid_base) + 1:] if len(oid_str) > len(oid_base) else "0"
                value = varBind[1]
                if hasattr(value, 'prettyPrint'):
                    results[index] = value.prettyPrint()
                else:
                    results[index] = str(value)
            count += 1
            if count >= max_rows:
                break
    except Exception:
        pass
    return results

async def fetch_snmp_data(device):
    """Fetch comprehensive SNMP data from a device."""
    result = {
        "name": device["name"],
        "host": device["host"],
        "status": "down",
        "error": None,
        "system": {
            "description": "",
            "name": "",
            "uptime": "",
            "contact": "",
            "location": "",
        },
        "cpu": {
            "count": 0,
            "average": 0,
            "cores": [],
        },
        "memory": {
            "total": 0,
            "used": 0,
            "percent": 0,
        },
        "disks": [],
        "interfaces": [],
    }

    if not SNMP_AVAILABLE:
        result["error"] = "pysnmp-lextudio not installed"
        return result

    host = device["host"]
    port = device.get("port", 161)
    community = device.get("community", "public")

    # Fetch system info
    sys_data, error = await snmp_get(host, port, community, SNMP_OIDS)
    if error or sys_data is None:
        result["error"] = error or "SNMP connection failed"
        return result

    result["status"] = "up"
    result["system"]["description"] = sys_data.get("sysDescr", "")
    result["system"]["name"] = sys_data.get("sysName", "")
    result["system"]["contact"] = sys_data.get("sysContact", "")
    result["system"]["location"] = sys_data.get("sysLocation", "")

    # Parse uptime
    uptime_raw = sys_data.get("sysUpTime", "0")
    try:
        uptime_ticks = int(uptime_raw)
        result["system"]["uptime"] = format_uptime(uptime_ticks)
    except (ValueError, TypeError):
        result["system"]["uptime"] = str(uptime_raw)

    # Fetch CPU load
    cpu_loads = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrProcessorLoad"])
    if cpu_loads:
        cores = []
        for idx, load in cpu_loads.items():
            try:
                cores.append(int(load))
            except (ValueError, TypeError):
                pass
        if cores:
            result["cpu"]["cores"] = cores
            result["cpu"]["count"] = len(cores)
            result["cpu"]["average"] = round(sum(cores) / len(cores), 1)

    # Fetch storage data
    storage_descr = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrStorageDescr"])
    storage_size = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrStorageSize"])
    storage_used = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrStorageUsed"])
    storage_units = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrStorageAllocationUnits"])
    storage_type = await snmp_bulk_walk(host, port, community, SNMP_TABLES["hrStorageType"])

    # Process storage entries
    for idx in storage_descr:
        descr = storage_descr.get(idx, "")
        type_oid = storage_type.get(idx, "")

        # Filter to physical memory and fixed disks
        # hrStorageRam = 1.3.6.1.2.1.25.2.1.2
        # hrStorageFixedDisk = 1.3.6.1.2.1.25.2.1.4
        is_ram = "1.3.6.1.2.1.25.2.1.2" in type_oid
        is_disk = "1.3.6.1.2.1.25.2.1.4" in type_oid

        try:
            size_blocks = int(storage_size.get(idx, 0))
            used_blocks = int(storage_used.get(idx, 0))
            alloc_units = int(storage_units.get(idx, 1))

            size_bytes = size_blocks * alloc_units
            used_bytes = used_blocks * alloc_units
            size_mb = size_bytes / (1024 * 1024)
            used_mb = used_bytes / (1024 * 1024)
            percent = round((used_bytes / size_bytes) * 100, 1) if size_bytes > 0 else 0

            if is_ram:
                result["memory"]["total"] = round(size_mb)
                result["memory"]["used"] = round(used_mb)
                result["memory"]["percent"] = percent
            elif is_disk and size_mb > 100:  # Filter out tiny pseudo-filesystems
                result["disks"].append({
                    "mount": descr,
                    "total": round(size_mb / 1024, 1),  # GB
                    "used": round(used_mb / 1024, 1),   # GB
                    "percent": percent,
                })
        except (ValueError, TypeError):
            pass

    # Fetch interface data
    if_descr = await snmp_bulk_walk(host, port, community, SNMP_TABLES["ifDescr"])
    if_status = await snmp_bulk_walk(host, port, community, SNMP_TABLES["ifOperStatus"])
    if_speed = await snmp_bulk_walk(host, port, community, SNMP_TABLES["ifSpeed"])
    if_in = await snmp_bulk_walk(host, port, community, SNMP_TABLES["ifInOctets"])
    if_out = await snmp_bulk_walk(host, port, community, SNMP_TABLES["ifOutOctets"])

    for idx in if_descr:
        name = if_descr.get(idx, f"Interface {idx}")
        # Skip loopback and virtual interfaces
        if name.lower() in ("lo", "loopback"):
            continue

        status_val = if_status.get(idx, "2")
        try:
            status = "up" if int(status_val) == 1 else "down"
        except (ValueError, TypeError):
            status = "unknown"

        try:
            speed = int(if_speed.get(idx, 0))
        except (ValueError, TypeError):
            speed = 0

        try:
            in_octets = int(if_in.get(idx, 0))
        except (ValueError, TypeError):
            in_octets = 0

        try:
            out_octets = int(if_out.get(idx, 0))
        except (ValueError, TypeError):
            out_octets = 0

        # Only include interfaces with traffic or that are up
        if status == "up" or in_octets > 0 or out_octets > 0:
            result["interfaces"].append({
                "name": name,
                "status": status,
                "speed": format_speed(speed),
                "in_octets": in_octets,
                "out_octets": out_octets,
                "in_formatted": format_octets(in_octets),
                "out_formatted": format_octets(out_octets),
            })

    return result

async def get_all_snmp_data():
    """Fetch all SNMP device data concurrently."""
    if not SNMP_DEVICES:
        return []

    tasks = [fetch_snmp_data(device) for device in SNMP_DEVICES]
    results = await asyncio.gather(*tasks)
    return results

# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
async def dashboard():
    """Main dashboard showing internet service status."""
    await check_services_async()
    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")
    return await render_template('dashboard.html',
                                  SERVICES=SERVICES,
                                  STATUS=STATUS,
                                  timestamp=now,
                                  active_page='services')

@app.route('/proxmox')
async def proxmox():
    """Proxmox cluster status page."""
    nodes_raw, vms_raw = await get_proxmox_data()

    # Process node data
    nodes = [process_node_data(n) for n in nodes_raw]
    nodes.sort(key=lambda x: x["name"])

    # Process VM/container data
    vms = [process_vm_data(v) for v in vms_raw]
    vms.sort(key=lambda x: (x["node"], x["name"]))

    # Separate VMs and containers
    qemu_vms = [v for v in vms if v["type"] == "qemu"]
    lxc_cts = [v for v in vms if v["type"] == "lxc"]

    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")

    return await render_template('proxmox.html',
                                  nodes=nodes,
                                  vms=qemu_vms,
                                  containers=lxc_cts,
                                  timestamp=now,
                                  active_page='proxmox',
                                  error=None if nodes else "Unable to connect to Proxmox API")

@app.route('/bmc')
async def bmc():
    """BMC/Redfish status page."""
    devices = await get_all_bmc_data()
    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")

    return await render_template('bmc.html',
                                  devices=devices,
                                  timestamp=now,
                                  active_page='bmc',
                                  error=None if devices else "No BMC devices configured")

@app.route('/snmp')
async def snmp():
    """SNMP monitoring page."""
    devices = await get_all_snmp_data()
    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")

    return await render_template('snmp.html',
                                  devices=devices,
                                  timestamp=now,
                                  active_page='snmp',
                                  error=None if devices else "No SNMP devices configured")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
