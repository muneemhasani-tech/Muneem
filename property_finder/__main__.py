"""python -m property_finder [serve|probe]"""
import sys

from . import scrape, web

cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd == "probe":
    rows = scrape.probe()
    for r in rows:
        print(f"{r['name']:<40} robots: {r['robots'] or '-':<34} HTTP {str(r['status']) or '-':<4} listings: {r['listings']:<3} {r['verdict']}")
    ok = sum(r["verdict"].startswith("CRAWLABLE") for r in rows)
    print(f"\n{ok} of {sum(r['verdict'] != 'LINK-OUT (never crawled; you open it yourself)' for r in rows)} auto sites crawlable; {len(rows)} sources total.")
else:
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8770
    srv = web.serve(port)
    print(f"Property Finder on http://127.0.0.1:{srv.server_port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
