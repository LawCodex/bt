#!/usr/bin/env python3
"""Convert the archived Bhutanese Act PDFs (see bt_fetch.py) into Markdown (English text).

Many PDFs contain both the Dzongkha and the English version; only pages whose text is English are
kept. Dzongkha text layers are not used (see README).

Usage: bt_convert.py [REPO_DIR]
"""
import datetime, json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from bt_pdfmd import to_markdown, pdf_pages

RAW = os.environ.get("RAW", os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "bt"))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")
RETRIEVED = os.environ.get("RETRIEVED", datetime.date.today().isoformat())
SOURCES = {"nab.gov.bt": "National Assembly of Bhutan", "oag.gov.bt": "Office of the Attorney General"}


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def slug(s, n=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rsplit("-", 1)[0] if len(s) > n else s


def is_english(page):
    letters = [c for c in page if c.isalpha()]
    if len(letters) < 80:
        return False
    tib = sum(1 for c in letters if "ༀ" <= c <= "࿿")
    lat1 = sum(1 for c in page if " " <= c <= "ÿ")
    asc = sum(1 for c in letters if c.isascii())
    words = re.findall(r"\b(the|of|and|shall|to|in|be|or|by|any)\b", page, re.I)
    return tib < 0.02 * len(letters) and lat1 < 0.02 * len(letters) and asc > 0.9 * len(letters) and len(words) > 10


BAD = re.compile(r"\b(amended|amend|provides|provided|shall|whereas|recogni[sz]ing|hereinafter|section|chapter|"
                 r"on the|in the act|day of|month|session|passed|enacted|mandates?|pursuant)\b|\.{3,}|^\d|:", re.I)


def clean_name(name):
    n = re.sub(r"\.pdf$", "", name, flags=re.I)
    n = re.sub(r"[_\-]+", " ", n)
    n = re.sub(r"(?i)\b(eng(lish)?|dzo(ngkha)?|version|both|final|draft)\b", " ", n)
    n = re.sub(r"(?i)(\d{4})\s*(eng|english|dzo)\w*", r"\1", n)
    n = re.sub(r"(?i)\b\d+(st|nd|rd|th)\b", " ", n)
    n = re.sub(r"\b\d{1,2} \d{1,2} (\d{4})\b", r"\1", n)
    n = re.sub(r"(?i)(of)(bhutan)", r"\1 \2", n)
    n = re.sub(r"(?i)(act)(of)", r"\1 \2", n)
    n = " ".join(n.split())
    return " ".join(w if w.isupper() and len(w) <= 4 else w.capitalize() for w in n.split()).replace(" Of ", " of ").replace(" And ", " and ").replace(" The ", " the ")


def find_title(en_pages, name):
    lines = [" ".join(l.split()) for l in en_pages[0].split("\n") if l.strip()][:25]
    for i, l in enumerate(lines):
        if len(l) > 110 or BAD.search(l) or not re.search(r"\b(ACT|Act|CODE|Code|CONSTITUTION|Constitution|THRIMZHUNG|Thrimzhung)\b", l):
            continue
        t = l
        if i + 1 < len(lines) and re.match(r"^(OF|of|Of)\b.{0,40}$|^(BHUTAN|Bhutan),?\s*\d{4}\.?$|^\(?\d{4}\)?\.?$", lines[i + 1]) \
                and not BAD.search(lines[i + 1]):
            t += " " + lines[i + 1]
        t = re.sub(r"\s+\d{1,2}$", "", t).rstrip(".")
        if t.isupper():
            t = " ".join(w.capitalize() if len(w) > 3 or w in ("ACT",) else w.lower() for w in t.split())
            t = t[0].upper() + t[1:]
        if not re.search(r"\d{4}", t):
            y = re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", name)
            if y:
                t += f", {y[0]}"
        return t
    return clean_name(name)


def main():
    idx = json.load(open(f"{RAW}/index.json"))
    # prefer the National Assembly copy, then the most recent snapshot
    idx.sort(key=lambda c: (c["host"] != "nab.gov.bt", c.get("ts", "")), reverse=False)
    idx.sort(key=lambda c: (c["host"] != "nab.gov.bt", -int(c.get("ts", "0"))))
    stats = {"written": 0, "no_english": [], "duplicate": [], "missing": []}
    seen = {}
    for c in idx:
        if c.get("status") != "ok":
            stats["missing"].append(c["url"])
            continue
        pages = pdf_pages(c["path"])
        en = [p for p in pages if is_english(p)]
        if sum(len(p) for p in en) < 1500:
            stats["no_english"].append(c["url"])
            continue
        if re.search(r"(?i)code[s]?-?of-?(practice|ethics)|work-?from-?home|abridged", c["name"]):
            stats["no_english"].append(c["url"] + " (not an Act)")
            continue
        title = find_title(en, c["name"])
        if re.search(r"^[a-z(]|\bhereby\b|\bbe called\b|^(IT IS|This Act|In the|The Act to|An Act to|Rate of|Schedule)\b|[|…;]|"
                     r"\bContent\b|\bis$|\bat its\b|\bof,|\bfor,|\bthe,", title):
            title = clean_name(c["name"])
        ym = re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", title) or re.findall(r"(?<!\d)(19\d\d|20\d\d)(?!\d)", c["name"])
        year = ym[0] if ym else "undated"
        is_const = re.search(r"constitution", c["key"]) and not re.search(r"amend", c["key"])
        core = re.sub(r"\b(the|of|for|bhutan|kingdom|acts?|both|ship|amendendment)\b", "", title.lower().replace("citizenship", "citizen"))
        core = re.sub(r"\d{4}|[^a-z]", "", core).replace("envirnment", "environment").replace("electicity", "electricity").replace("immagration", "immigration").replace("employement", "employment")
        tkey = "constitution" if is_const else core + year
        if tkey in seen:
            stats["duplicate"].append(c["url"] + " = " + seen[tkey])
            continue
        seen[tkey] = c["url"]
        if is_const:
            rel = "constitution/constitution-of-bhutan-2008.md"
            title = "The Constitution of the Kingdom of Bhutan"
            typ = "constitution"
        else:
            rel = f"acts/{year}/{slug(title)}.md"
            typ = "act"
        body = to_markdown(c["path"], page_filter=is_english)
        fm = ["---", f"title: {q(title)}", f"type: {typ}", "jurisdiction: bt", "language: en"]
        if typ == "constitution":
            fm.append("date: 2008-07-18")
        fm += ["status: unknown", f"publisher: {q(SOURCES[c['host']])}", f"source: {q(c['url'])}",
               f"archived: {q(c['archived'])}", f"retrieved: {RETRIEVED}", "---"]
        md = "\n".join(fm) + "\n\n# " + title + "\n\n" + body
        path = os.path.join(REPO, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        stats["written"] += 1
    json.dump(stats, open(f"{RAW}/convert-stats.json", "w"), indent=1)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in stats.items()}))


if __name__ == "__main__":
    main()
