"""Edit the design discussions directly.

    python tools/disc.py get 3            # -> prints the body of discussion #3 (the file is the discussion)
    python tools/disc.py put 3 body.md    # -> replaces the body of #3 with body.md (cross-links rewritten to discussion URLs)

Runs as naga-9 via gh's stored token. Discussions are the source of truth; there are no local copies.
"""
import json, os, pathlib, re, subprocess, sys

OWNER, REPO = "plinta-framework", "plinta"
BASE = f"https://github.com/{OWNER}/{REPO}/discussions/"
NUMBERS = {"1-EVENTS.md": 1, "2-PERMISSIONS.md": 2, "3-SOURCES.md": 3, "4-WRITES.md": 4, "5.1-SCREENS-models.md": 5,
           "5.2-SCREENS-rendering.md": 6, "5.3-SCREENS-filters.md": 7, "5.4-SCREENS-writes.md": 8, "5.5-SCREENS-shell.md": 9,
           "5.6-SCREENS-authoring.md": 10, "6-COMPONENTS.md": 11, "7-AUDIT.md": 12, "8-CONTRIBS.md": 13, "9-AI.md": 14,
           "10-API.md": 15, "11-MCP.md": 16}


def gh(query, variables):
    token = subprocess.run(["gh", "auth", "token", "-u", "naga-9"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=json.dumps({"query": query, "variables": variables}),
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "GH_TOKEN": token})
    if r.returncode:
        sys.exit(r.stderr)
    return json.loads(r.stdout)["data"]


def get(n):
    d = gh("query($n:Int!){ repository(owner:\"%s\", name:\"%s\"){ discussion(number:$n){ id title body } } }" % (OWNER, REPO), {"n": n})
    return d["repository"]["discussion"]


def put(n, body):
    for f, k in NUMBERS.items():
        body = body.replace(f"]({f})", f"]({BASE}{k})")
    body = body.replace("](README.md)", f"](https://github.com/{OWNER}/{REPO}#readme)")
    did = get(n)["id"]
    gh("mutation($id:ID!,$b:String!){ updateDiscussion(input:{discussionId:$id, body:$b}){ discussion{ number } } }", {"id": did, "b": body})
    print(f"updated #{n}")


if __name__ == "__main__":
    cmd, n = sys.argv[1], int(sys.argv[2])
    if cmd == "get":
        sys.stdout.reconfigure(encoding="utf-8"); print(get(n)["body"])
    elif cmd == "put":
        put(n, pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
