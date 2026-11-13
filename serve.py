#!/usr/bin/env python3
"""Serve this folder on http://localhost:8000 with caching disabled,
so edits to index.html and a fresh session.js show up on a normal reload."""
import functools
import http.server
import pathlib

HERE = pathlib.Path(__file__).parent


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


handler = functools.partial(NoCacheHandler, directory=str(HERE))
with http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler) as httpd:
    print("Serving on http://localhost:8000 (no caching). Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
