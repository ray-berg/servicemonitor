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
    <meta http-equiv=\"refresh\" content=\"30\">
    <style>
        :root {
            --up: #3cd556;
            --up-light: #69f080;
            --warning: #ffbf00;
            --warning-light: #ffd966;
            --down: #d32f2f;
            --down-light: #ff6b6b;
            --bg: #fafafa;
            --text: #333;
        }
        body.dark {
            --up: #49e167;
            --up-light: #5aec7a;
            --warning: #ffc74d;
            --warning-light: #ffd280;
            --down: #ff5252;
            --down-light: #ff8a8a;
            --bg: #1e1e1e;
            --text: #eee;
        }
        body {
            font-family: \"Segoe UI\", Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            padding: 20px;
            max-width: 600px;
            margin: 0 auto;
            transition: background-color 0.3s, color 0.3s;
        }
        .toggle {
            float: right;
            margin-top: -10px;
        }
        h1 { font-size: 2em; margin-bottom: 0; }
        p { margin-top: 0; color: #555; }
        h2 { margin-top: 40px; font-size: 1.4em; color: inherit; }

        table { width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 8px; }
        td {
            position: relative;
            border-radius: 8px;
            padding: 0;
            height: 140px;
            width: 100px;
            font-weight: bold;
            box-shadow: inset 0 4px 8px rgba(0,0,0,0.25), inset 0 -4px 8px rgba(255,255,255,0.2);
            overflow: hidden;
        }
        td .label {
            position: absolute;
            bottom: 4px;
            left: 0;
            right: 0;
            font-size: 0.85em;
            padding: 0 4px;
        }
        td.up { background: linear-gradient(var(--up-light), var(--up)); }
        td.warning { background: linear-gradient(var(--warning-light), var(--warning)); }
        td.down { background: linear-gradient(var(--down-light), var(--down)); }
        td::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 40%;
            background: rgba(255, 255, 255, 0.35);
            transform: translateY(-20%) rotate(-20deg);
            filter: blur(8px);
        }
    </style>
</head>
<body>
    <button id=\"dark-toggle\" class=\"toggle\">🌓</button>
    <h1>🌐 Internet Service Status Monitor</h1>
    <p><em>{{ timestamp }}</em></p>

    {% for category, services in SERVICES.items() %}
        <h2>{{ category }}</h2>
        <table>
            <tr>
            {% for name, url in services.items() %}
                <td class="{{ STATUS.get(name, {}).get('status', '') }}">
                    <div class=\"label\">{{ name }}</div>
                    {% if STATUS[name]['code'] %}
                        <small>{{ STATUS[name]['code'] }} – {{ STATUS[name]['response_time'] }} ms</small>
                    {% else %}
                        <small>No Response</small>
                    {% endif %}
                </td>
                {% if loop.index % 3 == 0 %}
            </tr><tr>
                {% endif %}
            {% endfor %}
            </tr>
        </table>
    {% endfor %}
    <script>
        const toggle = document.getElementById('dark-toggle');
        function applyMode() {
            if (localStorage.getItem('dark') === 'true') {
                document.body.classList.add('dark');
            } else {
                document.body.classList.remove('dark');
            }
            adjustContrast();
        }
        toggle.addEventListener('click', () => {
            const dark = !(localStorage.getItem('dark') === 'true');
            localStorage.setItem('dark', dark);
            applyMode();
        });
        function adjustContrast() {
            document.querySelectorAll('td.up, td.warning, td.down').forEach(td => {
                const bg = window.getComputedStyle(td).backgroundColor;
                const rgb = bg.match(/\d+/g).map(Number);
                const brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000;
                td.style.color = brightness > 140 ? '#000' : '#fff';
            });
        }
        applyMode();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
