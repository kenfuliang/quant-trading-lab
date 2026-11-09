#!/usr/bin/env python3
"""Single entry page for the local progress pages. Offline; reads only file timestamps.

Writes .local/progress/index.html: one tab bar over the pages that exist in the folder, each shown
in a frame, with the time each page was last built. Serve only that folder. The pages themselves
come from scripts/progress.py, profile_strategy.py, daily_holdings.py and t11_target_view.py; this
script does not build them and cannot trade.

  --dir PATH    folder holding the pages (default .local/progress)
"""
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = [("progress.html", "Progress"), ("holdings.html", "Holdings"), ("profile-replay.html", "Profile (replay)"),
         ("profile.html", "Profile (cloud)"), ("target.html", "Target log")]

_PAGE = r"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Quant lab dashboard</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14181f;--mute:#5b6573;--line:#dfe3e8;--acc:#2f6fdb}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf2;--mute:#9aa5b4;--line:#2a313c;--acc:#6aa0ff}}
*{box-sizing:border-box}html,body{height:100%;margin:0}body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,sans-serif}
nav{display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:8px 12px;background:var(--card);border-bottom:1px solid var(--line)}
nav b{margin-right:8px}nav button{font:inherit;color:var(--ink);background:none;border:1px solid transparent;border-radius:6px;padding:4px 10px;cursor:pointer}
nav button[aria-selected=true]{border-color:var(--acc);color:var(--acc);font-weight:600}nav .st{margin-left:auto;color:var(--mute);font-size:12px}
iframe{flex:1;width:100%;border:0;background:var(--bg)}
</style></head><body><nav role=tablist><b>Quant lab</b>__TABS__<span class=st id=st></span></nav><iframe id=f title=page></iframe>
<script>
const PAGES=__DATA__,BUILT="__BUILT__",$=id=>document.getElementById(id);
function show(name){const p=PAGES.find(x=>x.name===name)||PAGES[0];if(!p)return;$("f").src=p.file+"?v="+p.mtime;
 document.querySelectorAll("nav button").forEach(b=>b.setAttribute("aria-selected",b.dataset.n===p.name));
 $("st").textContent=p.label+" built "+p.built+" (dashboard "+BUILT+")";history.replaceState(null,"","#"+p.name)}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>show(b.dataset.n));
show(location.hash.slice(1));
</script></body></html>"""


def collect(folder):
    out = []
    for file, label in PAGES:
        path = Path(folder) / file
        if path.exists():
            when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            out.append({"name": file[:-5], "file": file, "label": label, "mtime": int(when.timestamp()),
                        "built": when.astimezone().strftime("%Y-%m-%d %H:%M")})
    return out


def render(pages, built):
    tabs = "".join(f'<button role=tab data-n="{html.escape(p["name"])}">{html.escape(p["label"])}</button>' for p in pages)
    data = json.dumps(pages, separators=(",", ":")).replace("</", "<\\/")
    return _PAGE.replace("__TABS__", tabs).replace("__DATA__", data).replace("__BUILT__", html.escape(built))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=ROOT / ".local/progress")
    args = parser.parse_args(argv)
    pages = collect(args.dir)
    args.dir.mkdir(parents=True, exist_ok=True)
    (args.dir / "index.html").write_text(render(pages, datetime.now().strftime("%Y-%m-%d %H:%M")))
    print(f"index.html: {len(pages)} page(s): {', '.join(p['label'] for p in pages) or 'none'}. Wrote {args.dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
