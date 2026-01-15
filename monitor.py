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

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
