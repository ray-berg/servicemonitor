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
# BMC/IPMI INTEGRATION
# =============================================================================

def fetch_bmc_status_sync(device):
    """Fetch BMC status synchronously (called in thread pool)."""
    from pyghmi.ipmi import command

    result = {
        "name": device["name"],
        "host": device["host"],
        "power": None,
        "sensors": [],
        "sel_entries": [],
        "error": None,
    }

    try:
        ipmi_conn = command.Command(
            bmc=device["host"],
            userid=device["username"],
            password=device["password"],
        )

        # Get power status
        try:
            power_state = ipmi_conn.get_power()
            result["power"] = power_state.get("powerstate", "unknown")
        except Exception as e:
            result["power"] = "unknown"

        # Get sensor data
        try:
            sensors = ipmi_conn.get_sensor_data()
            sensor_list = []
            for sensor in sensors:
                sensor_info = {
                    "name": sensor.name if hasattr(sensor, 'name') else str(sensor),
                    "value": None,
                    "units": "",
                    "state": "ok",
                    "type": "unknown",
                }
                if hasattr(sensor, 'value') and sensor.value is not None:
                    sensor_info["value"] = sensor.value
                if hasattr(sensor, 'units'):
                    sensor_info["units"] = sensor.units or ""
                if hasattr(sensor, 'health'):
                    health = sensor.health
                    if health == 0:
                        sensor_info["state"] = "ok"
                    elif health == 1:
                        sensor_info["state"] = "warning"
                    else:
                        sensor_info["state"] = "critical"
                if hasattr(sensor, 'type'):
                    sensor_info["type"] = sensor.type or "unknown"
                # Only include sensors with actual values
                if sensor_info["value"] is not None:
                    sensor_list.append(sensor_info)
            result["sensors"] = sensor_list
        except Exception as e:
            result["sensors"] = []

        # Get SEL (System Event Log) entries
        try:
            sel = ipmi_conn.get_event_log()
            sel_entries = []
            for entry in list(sel)[-10:]:  # Last 10 entries
                sel_entry = {
                    "id": getattr(entry, 'id', None),
                    "timestamp": str(getattr(entry, 'timestamp', '')),
                    "message": getattr(entry, 'message', str(entry)),
                    "severity": getattr(entry, 'severity', 'info'),
                }
                sel_entries.append(sel_entry)
            result["sel_entries"] = sel_entries
        except Exception as e:
            result["sel_entries"] = []

        ipmi_conn.ipmi_session.logout()

    except Exception as e:
        result["error"] = str(e)

    return result

async def fetch_bmc_status(device):
    """Fetch BMC status asynchronously."""
    return await asyncio.to_thread(fetch_bmc_status_sync, device)

async def get_all_bmc_data():
    """Fetch all BMC data concurrently."""
    if not BMC_DEVICES:
        return []

    tasks = [fetch_bmc_status(device) for device in BMC_DEVICES]
    results = await asyncio.gather(*tasks)
    return results

def categorize_sensors(sensors):
    """Categorize sensors by type."""
    categories = {
        "temperature": [],
        "fan": [],
        "voltage": [],
        "power": [],
        "other": [],
    }

    for sensor in sensors:
        name_lower = sensor["name"].lower()
        sensor_type = sensor.get("type", "").lower()

        if "temp" in name_lower or sensor_type == "temperature":
            categories["temperature"].append(sensor)
        elif "fan" in name_lower or sensor_type == "fan":
            categories["fan"].append(sensor)
        elif "volt" in name_lower or sensor_type == "voltage":
            categories["voltage"].append(sensor)
        elif "watt" in name_lower or "power" in name_lower or sensor_type == "power":
            categories["power"].append(sensor)
        else:
            categories["other"].append(sensor)

    return categories

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
    """BMC/IPMI status page."""
    devices = await get_all_bmc_data()

    # Process each device to categorize sensors
    for device in devices:
        if device.get("sensors"):
            device["sensor_categories"] = categorize_sensors(device["sensors"])
        else:
            device["sensor_categories"] = {
                "temperature": [],
                "fan": [],
                "voltage": [],
                "power": [],
                "other": [],
            }

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
