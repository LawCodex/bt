#!/usr/bin/env python3
"""Fetch Bhutanese Acts from Internet Archive copies of the official websites of the
National Assembly of Bhutan (nab.gov.bt) and the Office of the Attorney General (oag.gov.bt).

Both sites were unreachable at retrieval time (nab.gov.bt serves an unrelated application under a
certificate for *.systems.gov.bt; oag.gov.bt timed out), so archived copies of their official PDF
files are used (web.archive.org/web/<timestamp>id_/<url>).

Output: RAW/index.json, PDFs in RAW/pdf/.
"""
import json, os, re, sys, time, urllib.parse
import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW = os.environ.get("RAW", os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "bt"))
S = requests.Session()
S.headers["User-Agent"] = UA
CDX = "http://web.archive.org/cdx/search/cdx?url={}/*&filter=statuscode:200&filter=mimetype:application/pdf&collapse=urlkey&fl=original,timestamp,length"
KEEP = re.compile(r"(act|constitution|code|chathrim|thrimzhung|thrimshung|kadyig)", re.I)
SKIP = re.compile(r"(rules|regulation|resolution|session|report|bill|amendment[-_ ]bill|convention|treaty|"
                  r"agreement|guideline|manual|policy|handbook|hand-book|procedure|form|notice|speech|"
                  r"minutes|budget|calendar|brochure)", re.I)


def get(url, path=None):
    if path and os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, "rb").read()
    for attempt in range(5):
        try:
            r = S.get(url, timeout=300)
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path + ".part", "wb") as f:
                    f.write(r.content)
                os.replace(path + ".part", path)
            time.sleep(1.0)
            return r.content
        except Exception as e:
            print("retry", attempt, url, e, file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    return None


def main():
    os.makedirs(RAW, exist_ok=True)
    cands = {}
    for host in ("nab.gov.bt", "oag.gov.bt"):
        txt = get(CDX.format(host), f"{RAW}/cdx-{host}.txt").decode()
        for line in txt.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            url, ts = parts[0], parts[1]
            name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
            if not name.lower().endswith(".pdf"):
                continue
            if not KEEP.search(name) or SKIP.search(name):
                continue
            if host == "nab.gov.bt" and "/docs/acts/" not in url and "constitution" not in name.lower():
                continue
            key = re.sub(r"[^a-z0-9]+", "-", name.lower()[:-4]).strip("-")
            k = (host, key)
            if k not in cands or ts > cands[k]["ts"]:
                cands[k] = {"host": host, "key": key, "name": name, "url": url, "ts": ts}
    print(len(cands), "candidates", file=sys.stderr)
    out = []
    for i, c in enumerate(sorted(cands.values(), key=lambda c: (c["host"], c["key"]))):
        path = f"{RAW}/pdf/{c['host'].split('.')[0]}-{c['key'][:110]}.pdf"
        b = get(f"http://web.archive.org/web/{c['ts']}id_/{c['url']}", path)
        if b and b.startswith(b"%PDF"):
            c["path"] = path
            c["status"] = "ok"
        else:
            c["status"] = "missing"
            if os.path.exists(path):
                os.remove(path)
        c["archived"] = f"https://web.archive.org/web/{c['ts']}/{c['url']}"
        out.append(c)
        if i % 25 == 0:
            print(i, len(cands), file=sys.stderr)
            json.dump(out, open(f"{RAW}/index.json", "w"), indent=1, ensure_ascii=False)
    json.dump(out, open(f"{RAW}/index.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
