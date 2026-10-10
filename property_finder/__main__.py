"""python -m property_finder serve [port] [--host 0.0.0.0] | probe | admin | users | approve EMAIL | revoke EMAIL"""
import getpass
import sys

from . import auth, scrape, store, web

args = [a for a in sys.argv[1:]]
host = "127.0.0.1"
if "--host" in args:
    i = args.index("--host")
    host = args[i + 1]
    del args[i:i + 2]
cmd = args[0] if args else "serve"


def need(email):
    con = store.connect()
    u = auth.find(con, email)
    if not u:
        sys.exit(f"No account for {email}. Run `users` to see who has asked for access.")
    return con, u


if cmd == "probe":
    rows = scrape.probe()
    for r in rows:
        print(f"{r['name']:<40} robots: {r['robots'] or '-':<34} HTTP {str(r['status']) or '-':<4} listings: {r['listings']:<3} {r['verdict']}")
    ok = sum(r["verdict"].startswith("CRAWLABLE") for r in rows)
    print(f"\n{ok} of {sum(not r['name'].startswith('Search:') for r in rows)} auto sites crawlable; {len(rows)} sources total.")
elif cmd == "admin":
    email = input("Admin email: ").strip()
    name = input("Admin name: ").strip()
    pw = getpass.getpass("Password (10+ characters): ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    con = store.connect()
    try:
        auth.create_user(con, email, name, pw, role="admin", status="approved", by="setup")
    except auth.AuthError as e:
        sys.exit(str(e))
    print(f"Admin {email} created. Start the app with: python -m property_finder serve")
elif cmd == "users":
    con = store.connect()
    for u in auth.list_users(con):
        print(f"{u['status']:<9} {u['role']:<7} {u['email']:<34} {u['name']:<24} {u['phone']}  {u['note']}")
elif cmd in ("approve", "revoke"):
    con, u = need(args[1] if len(args) > 1 else "")
    auth.set_status(con, u["id"], "approved" if cmd == "approve" else "revoked", "cli")
    print(f"{u['email']}: {'approved' if cmd == 'approve' else 'revoked, sessions ended'}.")
else:
    port = int(args[1]) if len(args) > 1 else 8770
    con = store.connect()
    if not con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        sys.exit("No admin yet. Run `python -m property_finder admin` first, then start the app.")
    con.close()
    srv = web.serve(port, open_browser=host == "127.0.0.1", host=host)
    print(f"Property Finder on http://{host}:{srv.server_port}  (Ctrl+C to stop)")
    if host != "127.0.0.1":
        print("Serving other computers: put this behind HTTPS (for example a Caddy or nginx reverse proxy) and set PF_SECURE_COOKIES=1,\n"
              "otherwise passwords travel unencrypted.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
