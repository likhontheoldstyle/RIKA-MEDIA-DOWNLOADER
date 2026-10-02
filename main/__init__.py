import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main.app import create_app
from main.startup import startup

startup()

app = create_app()
