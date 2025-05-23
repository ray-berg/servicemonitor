import pytest
from flask import Flask, render_template_string
import monitor

app = Flask(__name__)

# Simple test to ensure template compiles without Jinja errors
@pytest.mark.parametrize('timestamp', ['test'])
def test_template_renders(timestamp):
    render_template_string(monitor.TEMPLATE, SERVICES=monitor.SERVICES, STATUS={}, timestamp=timestamp)
