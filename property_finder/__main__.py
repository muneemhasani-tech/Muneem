"""python -m property_finder serve [port] [--host 0.0.0.0] | probe | admin | users | approve EMAIL | revoke EMAIL
   | reset-password EMAIL | build-html OUT.html
   | scout [--seen seen.tsv] [--out DIR] [--master master.csv] [--extra N]   (the daily run: targeted Google searches only)
   | sites --registry sites-old.json leads-*.csv [--add domain] --out sites.json   (weekly: find and test other listing sites)
   | mail --routes associates.json leads-*.csv --out DIR   (one email per associate, their areas only)
   | weekly leads-*.csv stats-*.json --out DIR   (the associates' weekly one-pager email)"""
import getpass
import json
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
elif cmd == "scout":
    from . import scout
    opt = lambda n, d=None: args[args.index(n) + 1] if n in args else d
    info = scout.run(master=opt("--master"), out=opt("--out", "out"), seen=opt("--seen"), fresh="--fresh" in args,
                     extra=int(opt("--extra")) if opt("--extra") else None, sites=opt("--sites"))
    print(f"{info['new']} new, {info['duplicates']} repeats skipped, {info['searches']} searches\n"
          f"leads: {info['leads']}\ndigest: {info['digest']}\nseen: {info['seen']}")
elif cmd == "weekly":
    from . import weekly
    out = args[args.index("--out") + 1] if "--out" in args else "weekly"
    info = weekly.make([a for a in args[1:] if a.endswith(".csv")], [a for a in args[1:] if a.endswith(".json")], out)
    print(f"{info['rows']} listings, one-pager image: {'yes' if info['png'] else 'no (table email instead)'} -> {out}/email.html")
elif cmd == "mail":
    from . import mailer
    opt = lambda n, d=None: args[args.index(n) + 1] if n in args else d
    m = mailer.make(opt("--routes"), [a for a in args[1:] if a.endswith(".csv")], opt("--out", "mail_out"), opt("--label"))
    print(json.dumps([{k: x[k] for k in ("name", "count", "subject")} for x in m], ensure_ascii=False))
elif cmd == "sites":
    from . import sites
    opt = lambda n, d=None: args[args.index(n) + 1] if n in args else d
    adds = [args[i + 1] for i, a in enumerate(args) if a == "--add" and i + 1 < len(args)]
    info = sites.write(opt("--registry"), [a for a in args[1:] if a.endswith(".csv")], adds, opt("--out", "sites.json"))
    print(json.dumps(info, ensure_ascii=False))
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
elif cmd == "reset-password":
    con, u = need(args[1] if len(args) > 1 else "")
    pw = getpass.getpass(f"New password for {u['email']} (10+ characters): ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        auth.set_password(con, u["email"], pw)
    except auth.AuthError as e:
        sys.exit(str(e))
    print(f"Password changed for {u['email']}. Their old sessions and any lockout are cleared.")
elif cmd == "build-html":
    from pathlib import Path

    from . import vault
    out = Path(args[1] if len(args) > 1 else "index.html")
    email = input("Admin email: ").strip()
    name = input("Admin name: ").strip()
    pw = getpass.getpass("Admin password (12+ characters): ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        info = vault.build(store.connect(), out, email, name, pw)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Wrote {out} with {info['listings']} listings ({info['bytes'] // 1024} KB). Upload it to your hosting as index.html.\n"
          "Forgot the admin password? Run this command again: it makes a new file with a new admin password. Members must be re-added.")
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
