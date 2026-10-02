"""Make the arc3-rl-live web.app page the same page as arc3.sonpham.net/rl.html (Son 2-Oct: bright, like the site).

Copies rl.html (as index.html), its CSS and JS and the site theme from the site checkout into public/, with the nav
pointing at arc3.sonpham.net. rl.js reads data.json when it runs on a web.app host. Run before every deploy, so the
two pages never drift.

  C:/Python312/python.exe sync_site_page.py [--site D:/codex-work/arc3-site-rl/docs]
"""
import argparse
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--site", default=r"D:\codex-work\arc3-site-rl\docs")
args = ap.parse_args()
site, public = Path(args.site), HERE / "public"
for rel in ("static/css/theme.css", "static/css/rl.css", "static/js/rl.js", "static/js/theme-toggle.js"):
    (public / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(site / rel, public / rel)
page = (site / "rl.html").read_text(encoding="utf-8")
# site links (./x.html, ./) go to the site; the page's own static files stay relative
page = re.sub(r'href="\./(?!static/)([^"]*)"', r'href="https://arc3.sonpham.net/\1"', page)
page = page.replace('<meta name="robots" content="noindex, nofollow">',
                    '<meta name="robots" content="noindex, nofollow">\n<!-- copy of arc3.sonpham.net/rl.html, synced by sync_site_page.py -->')
(public / "index.html").write_text(page, encoding="utf-8", newline="\n")
print("synced", len(page))
