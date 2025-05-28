#!/opt/srvmon/venv/bin/python3

from quart import Quart, render_template_string
import asyncio
import aiohttp
from datetime import datetime

app = Quart(__name__)

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

async def fetch_status(session, name, url):
    try:
        start = asyncio.get_event_loop().time()
        async with session.head(url, timeout=5) as response:
            end = asyncio.get_event_loop().time()
            STATUS[name] = {
                "code": response.status,
                "status": "up" if response.status < 400 else "warning",
                "response_time": round((end - start) * 1000)  # ms
            }
    except Exception:
        STATUS[name] = {
            "code": None,
            "status": "down",
            "response_time": None
        }

async def check_services_async():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for category, services in SERVICES.items():
            for name, url in services.items():
                tasks.append(fetch_status(session, name, url))
        await asyncio.gather(*tasks)

@app.route('/')
async def dashboard():
    await check_services_async()
    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")
    return await render_template_string(TEMPLATE, SERVICES=SERVICES, STATUS=STATUS, timestamp=now)

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Service Monitor</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
            color: #333;
        }
        h1 {
            font-size: 2em;
            margin-bottom: 0;
        }
        p {
            font-size: 1em;
            margin-top: 0;
            color: #555;
        }
        h2 {
            margin-top: 40px;
            font-size: 1.4em;
            color: #222;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }
        td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
            font-weight: bold;
            font-size: 0.95em;
            color: #000;
        }
        .up {
            background-color: #c8e6c9;
        }
        .warning {
            background-color: #fff9c4;
        }
        .down {
            background-color: #ffcdd2;
        }
    </style>
</head>
<body>
    <h1>🌐 Internet Service Status Monitor</h1>
    <p><em>{{ timestamp }}</em></p>

    {% for category, services in SERVICES.items() %}
        <h2>{{ category }}</h2>
        <table>
            <tr>
            {% for name, url in services.items() %}
            <td class="{{ STATUS.get(name, {}).get('status', '') }}">
                {{ name }}<br>
                {% if STATUS[name]['code'] %}
                    <small>{{ STATUS[name]['code'] }} – {{ STATUS[name]['response_time'] }} ms</small>
                {% else %}
                    <small>No Response</small>
                {% endif %}
            </td>
                {% if loop.index % 4 == 0 %}
            </tr><tr>
                {% endif %}
            {% endfor %}
            </tr>
        </table>
    {% endfor %}
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
