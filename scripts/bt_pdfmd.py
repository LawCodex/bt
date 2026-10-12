#!/usr/bin/env python3
"""Convert a text-layer PDF of a Bhutanese Act (English version) into Markdown body text.

Adapted from the Pakistan converter: Bhutanese Acts print short cross-headings above numbered
sections ("Appointment" / "12. The Chairperson ..."), so sections become "#### 12." headings with
the full text below, and cross-headings are kept in bold.

Strategy (pdftotext -layout, page by page):
  * drop running footers ("Page N of M"), lone page numbers;
  * detect the footnote block at the bottom of each page (a footnote number alone at column 0,
    followed by the footnote text) and move footnotes to a quote block after the current
    section;
  * superscript amendment markers printed on their own line are re-attached to the next line
    (e.g. "2" + "[(2A) ..." -> "2[(2A) ...");
  * lines are joined into paragraphs (blank line = paragraph break);
  * PART / CHAPTER / SCHEDULE paragraphs become headings, sections ("12. Heading.__ text")
    become "#### 12. Heading" followed by the text;
  * the table of contents ("arrangement of sections") at the beginning is kept as a plain list;
  * tabular paragraphs (several columns separated by wide gaps) are kept in a fenced block.
"""
import re, subprocess

FOOTER = re.compile(r"^\s*(Page\s+\d+\s+of\s+\d+|\d{1,4}|-\s*\d+\s*-)\s*$", re.I)
FN_START = re.compile(r"^(\d{1,3})\s*$")
SUP_LINE = re.compile(r"^\s{2,}(\d{1,3}(?:\s+\d{1,3})*)\s*$")
PART = re.compile(r"^\[?\s*(?:\d{1,3}\s*\[)?\s*(PART|Part)[\s\-–]*[IVXLC\d]+[A-Z]?\b")
CHAP = re.compile(r"^\[?\s*(?:\d{1,3}\s*\[)?\s*(CHAPTER|Chapter)[\s\-–]*[IVXLC\d]+[A-Z]?\b")
SCHED = re.compile(r"^\[?\s*(?:\d{1,3}\s*\[)?\s*((THE\s+)?([A-Z]+\s+)?SCHEDULE|ANNEX(URE)?|APPENDIX|FORM)\b")
SECTION = re.compile(r"^((?:<sup>\d+</sup>|\d{1,3}(?=\s*\[))?\s*\[?\s*)(\d{1,4}[A-Z]{0,3}(?:-[A-Z])?)\.\s+(.*)$", re.S)
DELIMS = ["__", ".—", ".–", ".―", ".‒", ".-", ". —", ". –", ". ―", ":—", ":-", ":―", "—", "–", "―"]
ARTICLE = re.compile(r"^(?:Article|ARTICLE)\s+\d+[A-Z]?(?:\s+([A-Z][^.;:]{1,90}))?$")
TOCLINE = re.compile(r"^\[?\d{1,4}[A-Z]{0,3}\.\s+\S")


def pdf_pages(path):
    out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", path, "-"], capture_output=True)
    txt = out.stdout.decode("utf-8", "replace")
    return txt.split("\f")


def split_page(page):
    lines = page.split("\n")
    # strip trailing blank/footer lines
    while lines and (not lines[-1].strip() or FOOTER.match(lines[-1])):
        lines.pop()
    # remove footer anywhere in last few lines
    lines = [l for i, l in enumerate(lines) if not (re.match(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", l, re.I))]
    # footnote block: first line (in bottom 60% of page) that is a bare number at col 0
    fn_at = None
    n = len(lines)
    for i in range(n):
        if FN_START.match(lines[i]) and i + 1 < n and lines[i + 1].strip() and i > n * 0.25:
            # the following text must not look like a section heading
            fn_at = i
            break
    body, notes = lines, []
    if fn_at is not None:
        body = lines[:fn_at]
        cur = None
        for l in lines[fn_at:]:
            m = FN_START.match(l)
            if m:
                cur = [m.group(1), ""]
                notes.append(cur)
            elif l.strip():
                if cur is None:
                    cur = ["", ""]
                    notes.append(cur)
                cur[1] = (cur[1] + " " + l.strip()).strip()
        notes = [f"{a} {b}".strip() for a, b in notes if b or a]
    # re-attach superscript marker lines
    fixed = []
    pending = None
    for l in body:
        m = SUP_LINE.match(l)
        if m and len(m.group(1)) <= 7:
            pending = (pending + " " if pending else "") + m.group(1).replace(" ", "")
            continue
        if pending and l.strip():
            ind = len(l) - len(l.lstrip())
            l = " " * ind + (pending if l.lstrip().startswith("[") else "<sup>" + pending + "</sup>") + l.lstrip()
            pending = None
        fixed.append(l)
    return fixed, notes


SECSTART = re.compile(r"^(<sup>\d+</sup>|\d{1,3}(?=\s*\[))?\s*\[?\d{1,4}[A-Z]{0,3}\.\s+\S")


def is_heading_line(l):
    st = l.strip()
    ind = len(l) - len(l.lstrip())
    if len(st) > 120:
        return False
    if (PART.match(st) or CHAP.match(st)) and (ind >= 8 or len(st) < 60):
        return True
    if ind >= 10 and re.search(r"[A-Z]{3}", st) and st.upper() == st and not re.match(r"^\(?[a-z0-9]+\)", st):
        return True
    return False


def is_tabular(lines):
    rows = [l.strip() for l in lines if l.strip()]
    if len(rows) < 2:
        return False
    multi = sum(1 for r in rows if len(re.findall(r"\S {3,}(?=\S)", r)) >= 2)
    return multi >= max(2, len(rows) * 0.6)


def running_headers(pages):
    """lines repeated at the top of many pages (running heads) -> set of normalized texts"""
    from collections import Counter
    c = Counter()
    for p in pages:
        top = [l for l in p.split("\n") if l.strip()][:2]
        for l in top:
            c[re.sub(r"\d+", "#", " ".join(l.split()))] += 1
    n = len(pages)
    return {k for k, v in c.items() if v >= 3 and (v >= 0.2 * n or re.search(r"_{5,}\s*$", k))}


def paragraphs(pages):
    """yield ('p', lines) or ('fn', text) items"""
    heads = running_headers(pages)
    pages = ["\n".join(l for l in p.split("\n") if re.sub(r"\d+", "#", " ".join(l.split())) not in heads
                       and not re.fullmatch(r"\s*\.\.\s*", l)) for p in pages]
    items = []
    cur = []
    for pi, page in enumerate(pages):
        body, notes = split_page(page)
        # page break: decide whether first para continues the last one
        first = next((l for l in body if l.strip()), None)
        if cur and first is not None:
            last = cur[-1].rstrip()
            ind = len(first) - len(first.lstrip())
            if last.endswith((".", ":", ";", "]")) and (ind >= 4 or first.strip()[:1].isupper() or first.strip().startswith("(")):
                items.append(("p", cur))
                cur = []
        for l in body:
            if not l.strip():
                if cur:
                    items.append(("p", cur))
                    cur = []
                continue
            st = l.strip()
            ind = len(l) - len(l.lstrip())
            if is_heading_line(l):
                if cur:
                    items.append(("p", cur))
                items.append(("p", [l]))
                cur = []
                continue
            if cur:
                prev = cur[-1]
                pind = len(prev) - len(prev.lstrip())
                pend = prev.rstrip()[-1:]
                crosshead = SECSTART.match(st) and len(cur) == 1 and len(prev.strip()) < 100 and \
                    not prev.rstrip().endswith((".", ";", ":", ",", "-", "—"))
                if crosshead or (pend in ".;:]_—–" and (ind - pind >= 3 or SECSTART.match(st))):
                    items.append(("p", cur))
                    cur = []
            cur.append(l)
        for nt in notes:
            items.append(("fn", nt))
    if cur:
        items.append(("p", cur))
    # footnotes were emitted at page end, possibly in the middle of a paragraph that continues;
    # move each footnote after the next paragraph boundary is handled by the renderer.
    return items


def join(lines):
    s = " ".join(re.sub(r"\s+", " ", l.strip()) for l in lines)
    s = re.sub(r"(\w)- (\w)", lambda m: m.group(0) if m.group(2).isupper() else m.group(1) + "-" + m.group(2), s)
    return s.strip()


def esc(s):
    # avoid accidental markdown: leading '#', '>', list markers like '1.' are fine as text
    if s.startswith(("#", ">", "+ ", "- ", "* ", "=")):
        return "\\" + s
    return s


def split_heading(rest):
    cands = []
    for d in DELIMS:
        i = rest.find(d)
        if 0 < i <= 250:
            if d in ("—", "–") and i > 160:
                continue
            cands.append((i, i + len(d)))
    m = re.match(r"^(.{3,200}?[a-z\)\]])\.\s+(?=[A-Z(\[\"“‘0-9])", rest, re.S)
    if m:
        cands.append((len(m.group(1)), m.end()))
    if not cands:
        return None, rest
    i, j = min(cands)
    title = rest[:i].strip()
    if not title or len(title) < 2:
        return None, rest
    return title.rstrip(".").strip(), rest[j:].strip()


def to_markdown(pdf_path, level_base=2, page_filter=None):
    pages = pdf_pages(pdf_path)
    if page_filter:
        pages = [p for p in pages if page_filter(p)]
    items = paragraphs(pages)
    paras = [(k, join(v) if k == "p" else v, v if k == "p" else None) for k, v in items]
    # the table of contents is recognised by its dot leaders ("Article 1 ........ 1")
    toc_end = -1
    for idx, (k, t, raw) in enumerate(paras[:400]):
        if k == "p" and re.search(r"\.{5,}|…{2,}", t):
            toc_end = idx
    H = lambda n: "#" * min(6, level_base + n)
    out = []
    pending_fn = []
    in_toc_list = False
    in_sched = False
    skip_next = set()

    def flush_fn():
        if pending_fn:
            out.append("")
            for f in pending_fn:
                out.append("> " + f)
            out.append("")
            pending_fn.clear()

    for idx, (k, t, raw) in enumerate(paras):
        if k == "fn":
            pending_fn.append(t)
            continue
        if not t:
            continue
        if idx <= toc_end:
            out.append(esc(t) + "  ")
            in_toc_list = True
            continue
        if in_toc_list:
            out.append("")
            in_toc_list = False
        if is_tabular(raw):
            out.append("")
            out.append("```")
            base = min(len(l) - len(l.lstrip()) for l in raw if l.strip())
            out.extend(l[base:].rstrip() for l in raw)
            out.append("```")
            out.append("")
            continue
        short = len(t) < 160
        am = ARTICLE.match(t) if len(t) < 110 else None
        if am:
            flush_fn()
            if am.group(1):
                t = t[:am.start(1)].strip() + " — " + am.group(1).strip()
                title = ""
            else:
                nxt = next((pp for kk, pp, rr in paras[idx + 1:idx + 2] if kk == "p" and pp), "")
                title = nxt if nxt and len(nxt) < 90 and not SECTION.match(nxt) and not re.search(r"[.;:]$", nxt) else ""
            out += ["", H(0) + " " + t + (" — " + title if title else ""), ""]
            if title:
                skip_next.add(idx + 1)
            in_sched = False
            continue
        if idx in skip_next:
            continue
        if short and PART.match(t):
            flush_fn()
            out += ["", H(0) + " " + t, ""]
            continue
        if short and CHAP.match(t):
            flush_fn()
            out += ["", H(1) + " " + t, ""]
            continue
        if short and SCHED.match(t) and t.upper()[:40] == t[:40]:
            flush_fn()
            out += ["", H(0) + " " + t, ""]
            in_sched = True
            continue
        m = SECTION.match(t)
        if m and idx > toc_end and not in_sched and len(m.group(3)) > 5:
            flush_fn()
            out += ["", H(2) + " " + m.group(2) + ".", ""]
            out += [esc(t), ""]
            continue
        nxt = next((pp for kk, pp, rr in paras[idx + 1:idx + 3] if kk == "p" and pp), "")
        if idx > toc_end and len(t) < 100 and not re.search(r"[.;:,]$", t) and t[:1].isupper() and SECTION.match(nxt):
            out += ["", "**" + esc(t) + "**", ""]
            continue
        out += [esc(t), ""]
    flush_fn()
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


if __name__ == "__main__":
    import sys
    print(to_markdown(sys.argv[1]))
