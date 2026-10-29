#!/usr/bin/env python3
"""Tiny local stand-in for Cloudflare Pages, to test dist/site/_headers.

    python3 tests/serve_cf.py dist/site 8092

Emulates what matters here: `_headers` rules (exact paths and trailing `*` splats;
all matching rules apply; same-named headers are joined with ", "), directory
index + redirect to trailing slash, `_headers` itself not served, ETag/304.
It is a simulation for testing, not a full Pages emulator.
"""
import hashlib, http.server, mimetypes, pathlib, sys

root = pathlib.Path(sys.argv[1]).resolve()
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8092


def parse_rules(text):
    rules, cur = [], None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            cur = (line.strip(), []); rules.append(cur)
        else:
            k, v = line.strip().split(":", 1)
            cur[1].append((k.strip(), v.strip()))
    return rules


RULES = parse_rules((root / "_headers").read_text(encoding="utf-8"))


def match(pattern, path):
    return path.startswith(pattern[:-1]) if pattern.endswith("*") else pattern == path


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        path = self.path.split("?")[0].split("#")[0]
        if path == "/_headers":
            return self.send_error(404)
        fs = (root / path.lstrip("/")).resolve()
        if root not in fs.parents and fs != root:
            return self.send_error(404)
        if fs.is_dir():
            if not path.endswith("/"):
                self.send_response(308); self.send_header("Location", path + "/"); self.end_headers(); return
            fs = fs / "index.html"
        if not fs.is_file():
            return self.send_error(404)
        data = fs.read_bytes()
        etag = '"' + hashlib.sha256(data).hexdigest()[:32] + '"'
        hdrs = {}
        for pattern, pairs in RULES:
            if match(pattern, path):
                for k, v in pairs:
                    hdrs[k] = hdrs[k] + ", " + v if k in hdrs else v
        ctype = hdrs.pop("Content-Type", None) or {
            ".webmanifest": "application/manifest+json", ".js": "text/javascript",
        }.get(fs.suffix) or mimetypes.guess_type(fs.name)[0] or "application/octet-stream"
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("ETag", etag)
        for k, v in hdrs.items():
            self.send_header(k, v)
        if self.headers.get("If-None-Match") == etag:
            self.end_headers(); return
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head:
            self.wfile.write(data)


if __name__ == "__main__":
    print(f"serving {root} on http://localhost:{port}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
