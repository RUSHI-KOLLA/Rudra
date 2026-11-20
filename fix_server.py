#!/usr/bin/env python3
content = open('/home/rushi/vg/api/server.py').read()

old = '''    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003

    """Start the threaded VG web server."""
    print(f"  Mode: Public SaaS (per-request API keys)")'''

new = '''    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        """Keep request logging concise. Never log API keys."""
        print(f"[vg-web] {self.address_string()} - {format % args}")

    def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
        """Start the threaded VG web server."""
        print(f"  Mode: Public SaaS (per-request API keys)")
'''

if old in content:
    content = content.replace(old, new, 1)
    open('/home/rushi/vg/api/server.py', 'w').write(content)
    print("FIXED")
else:
    print("OLD NOT FOUND")
    lines = content.split('\n')
    for i in range(273, 285):
        if i < len(lines):
            print(f'{i+1}: {repr(lines[i])}')
