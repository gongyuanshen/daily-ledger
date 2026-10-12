"""Development-only UI verification server; actual Python API and temporary SQLite.

Not packaged in the APK. It refuses to use a pre-existing database directory.
Native Android file picker and lifecycle behavior require device acceptance.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app/src/main/python'))
from mobile_api import handle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, required=True)
    args = parser.parse_args()
    args.data.mkdir(parents=True, exist_ok=False)
    assets = ROOT / 'app/src/main/assets'

    class PreviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            files = {'/': ('index.html', 'text/html'), '/style.css': ('style.css', 'text/css'),
                     '/app.js': ('app.js', 'text/javascript')}
            if self.path not in files:
                self.send_error(404)
                return
            name, mime = files[self.path]
            content = (assets / name).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            if self.path != '/api':
                self.send_error(404)
                return
            body = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
            result = handle(str(args.data), body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(result)

    server = HTTPServer(('127.0.0.1', args.port), PreviewHandler)
    print(f'PREVIEW http://127.0.0.1:{args.port} DATA {args.data}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
