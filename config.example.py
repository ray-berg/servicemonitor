# Service Monitor Configuration
# Copy this file to config.py and fill in your credentials

# Proxmox API Configuration
PROXMOX_HOST = "https://192.168.1.100:8006"  # Your Proxmox server URL
PROXMOX_TOKEN_ID = "user@pam!tokenname"       # API token ID
PROXMOX_TOKEN_SECRET = "your-token-secret"    # API token secret
PROXMOX_VERIFY_SSL = False                    # Set True if using valid SSL cert

# BMC/IPMI Configuration
# Add your BMC devices here with per-device credentials
BMC_DEVICES = [
    {
        "name": "Server 1",
        "host": "192.168.1.10",
        "username": "admin",
        "password": "password",
    },
    {
        "name": "Server 2",
        "host": "192.168.1.11",
        "username": "admin",
        "password": "password",
    },
]
