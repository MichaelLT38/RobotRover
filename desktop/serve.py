#!/usr/bin/env python3
"""
Starts the RobotRover desktop controller.

Web Bluetooth only works on pages served from a secure origin, and
http://localhost counts as one, so this serves the controller from this
folder on localhost and opens it in your browser.

    python serve.py              # serve and open the browser
    python serve.py --no-browser # serve only

Use Chrome or Edge: Firefox and Safari don't support Web Bluetooth.
The server only listens on this computer (127.0.0.1); nothing is exposed
to your network.
"""

import argparse
import functools
import http.server
import os
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="RobotRover desktop controller")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    args = parser.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=HERE)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/"
        print(f"RobotRover controller running at {url}")
        print("Open it in Chrome or Edge. Press Ctrl+C to stop.")
        if not args.no_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
