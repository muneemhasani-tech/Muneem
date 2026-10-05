"""python -m property_finder [serve|probe]"""
import sys

from . import scrape, web

cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd == "probe":
    for r in scrape.probe():
        print(f"{r['source']:<16} HTTP {r['status']:<4} listings recognised: {r['listings']}")
else:
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8770
    srv = web.serve(port)
    print(f"Property Finder on http://127.0.0.1:{srv.server_port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
