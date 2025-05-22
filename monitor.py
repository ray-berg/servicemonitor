#!/home/brehberg/summarizer/bin/python3

import asyncio
import aiohttp
from datetime import datetime
from flask import Flask, render_template_string

app = Flask(__name__)

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
    },
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
                "response_time": round((end - start) * 1000),  # ms
            }
    except:
        STATUS[name] = {"code": None, "status": "down", "response_time": None}


async def check_services_async():
    tasks = []
    async with aiohttp.ClientSession() as session:
        for category, services in SERVICES.items():
            for name, url in services.items():
                tasks.append(fetch_status(session, name, url))
        await asyncio.gather(*tasks)


def check_services():
    asyncio.run(check_services_async())


@app.route("/")
def dashboard():
    check_services()
    now = datetime.now().strftime("Status as of %B %d, %Y at %I:%M %p")
    return render_template_string(
        TEMPLATE, SERVICES=SERVICES, STATUS=STATUS, timestamp=now
    )


TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Service Monitor</title>
    <meta http-equiv="refresh" content="30">
    <style>
        :root {
            --bg-color: #fafafa;
            --text-color: #333;
            --up-color: #00cc00;
            --warning-color: #ffbf00;
            --down-color: #cc0000;
        }
        body {
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 20px;
            margin: auto;
            max-width: 1000px;
        }
        body.dark {
            --bg-color: #222;
            --text-color: #eee;
            --up-color: #009900;
            --warning-color: #c08000;
            --down-color: #990000;
        }
        h1 {
            font-size: 2em;
            margin-bottom: 0;
        }
        .toggle {
            float: right;
            padding: 4px 8px;
            margin-left: 10px;
            border: 1px solid currentColor;
            border-radius: 4px;
            background: none;
            cursor: pointer;
        }
        p {
            font-size: 1em;
            margin-top: 0;
            color: #555;
        }
        h2 {
            margin-top: 40px;
            font-size: 1.4em;
            color: var(--text-color);
        }
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 8px;
            table-layout: fixed;
        }
        td {
            border-radius: 6px;
            position: relative;
            aspect-ratio: 1;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        td .content {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            text-align: center;
            font-weight: bold;
            font-size: 0.95em;
        }
        td::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 6px;
            background: linear-gradient(135deg, rgba(255,255,255,0.7), rgba(255,255,255,0) 70%);
            pointer-events: none;
        }
        .up {
            background-color: var(--up-color);
        }
        .warning {
            background-color: var(--warning-color);
        }
        .down {
            background-color: var(--down-color);
        }
    </style>
</head>
<body>
    <button id="toggle-dark" class="toggle">🌙 Dark</button>
    <h1>🌐 Internet Service Status Monitor</h1>
    <p><em>{{ timestamp }}</em></p>

    {% for category, services in SERVICES.items() %}
        <h2>{{ category }}</h2>
        <table>
            <tr>
            {% for name, url in services.items() %}
            <td class="{{ STATUS.get(name, {}).get('status', '') }}">
                <div class="content">
                    {{ name }}<br>
                    {% if STATUS[name]['code'] %}
                        <small>{{ STATUS[name]['code'] }} – {{ STATUS[name]['response_time'] }} ms</small>
                    {% else %}
                        <small>No Response</small>
                    {% endif %}
                </div>
            </td>
                {% if loop.index % 4 == 0 %}
            </tr><tr>
                {% endif %}
            {% endfor %}
            </tr>
        </table>
    {% endfor %}
    <script>
        function adjustTextColors() {
            document.querySelectorAll('td.up, td.warning, td.down').forEach(td => {
                const bg = window.getComputedStyle(td).backgroundColor;
                const rgb = bg.match(/\d+/g).map(Number);
                const brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000;
                td.style.color = brightness > 150 ? '#000' : '#fff';
            });
        }
        adjustTextColors();

        document.getElementById('toggle-dark').addEventListener('click', () => {
            document.body.classList.toggle('dark');
            const btn = document.getElementById('toggle-dark');
            btn.textContent = document.body.classList.contains('dark') ? '☀️ Light' : '🌙 Dark';
            adjustTextColors();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
