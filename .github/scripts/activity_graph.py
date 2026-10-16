"""Render a contributions area chart (last 52 weeks) as an SVG for the profile README.

Runs in GitHub Actions with GITHUB_TOKEN. Uses only the standard library.
Usage: python activity_graph.py <username> <output.svg> [sample.json]
"""
import json
import os
import sys
import urllib.request
from datetime import date

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""

W, H = 900, 260
PAD_L, PAD_R, PAD_T, PAD_B = 48, 24, 70, 36


def fetch(login):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": "bearer " + os.environ["GITHUB_TOKEN"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def nice_max(v):
    for step in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if v <= step * 4:
            return step * 4, step
    return v, v // 4


def render(cal):
    weeks = cal["weeks"][-52:]
    pts = [(w["contributionDays"][0]["date"], sum(d["contributionCount"] for d in w["contributionDays"])) for w in weeks]
    total = cal["totalContributions"]
    top, step = nice_max(max(c for _, c in pts) or 1)

    cw, ch = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    n = len(pts)
    xy = [(PAD_L + i * cw / (n - 1), PAD_T + ch - c / top * ch) for i, (_, c) in enumerate(pts)]

    # smooth path (Catmull-Rom -> cubic Bezier)
    d = f"M{xy[0][0]:.1f},{xy[0][1]:.1f}"
    for i in range(n - 1):
        p0, p1, p2 = xy[max(i - 1, 0)], xy[i], xy[i + 1]
        p3 = xy[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        c1 = (c1[0], min(c1[1], PAD_T + ch)); c2 = (c2[0], min(c2[1], PAD_T + ch))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    base = PAD_T + ch
    area = d + f" L{xy[-1][0]:.1f},{base} L{xy[0][0]:.1f},{base} Z"

    grid = ""
    for k in range(5):
        y = PAD_T + ch - k * step / top * ch
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" stroke="#21262D"/>'
        grid += f'<text x="{PAD_L - 10}" y="{y + 4:.1f}" text-anchor="end" class="ax">{k * step}</text>'

    months, seen = "", None
    for i, (ds, _) in enumerate(pts):
        m = date.fromisoformat(ds).strftime("%b")
        if m != seen and 0 < i < n - 2:
            months += f'<text x="{xy[i][0]:.1f}" y="{H - 12}" text-anchor="middle" class="ax">{m}</text>'
        seen = m

    ex, ey = xy[-1]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{total} contributions in the last year">
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}
.ax{{fill:#8B949E;font-size:11px}}
</style>
<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#8B5CF6" stop-opacity=".55"/><stop offset="1" stop-color="#8B5CF6" stop-opacity="0"/>
</linearGradient></defs>
<rect width="{W}" height="{H}" rx="12" fill="#0D1117"/>
<text x="{PAD_L}" y="34" fill="#A78BFA" font-size="26" font-weight="700">{total:,}</text>
<text x="{PAD_L}" y="54" fill="#C9D1D9" font-size="13">Contributions in the last year</text>
<text x="{W - PAD_R}" y="34" fill="#8B949E" font-size="12" text-anchor="end">weekly · updated daily</text>
{grid}{months}
<path d="{area}" fill="url(#fill)"/>
<path d="{d}" fill="none" stroke="#8B5CF6" stroke-width="2.5" stroke-linejoin="round"/>
<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="#C4B5FD" stroke="#0D1117" stroke-width="2"/>
</svg>
"""


if __name__ == "__main__":
    login, out = sys.argv[1], sys.argv[2]
    cal = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else fetch(login)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(cal))
    print(f"wrote {out}: {cal['totalContributions']} contributions")
