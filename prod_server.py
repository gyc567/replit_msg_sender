#!/usr/bin/env python3
"""Production entry point for webhook server"""

import os
import sys

# Ensure proper path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app from botsever
from botsever import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting production webhook server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
