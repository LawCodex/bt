# LawCodex — Bhutan (`bt`)

Laws of the Kingdom of Bhutan as plain Markdown, one file per text: the Constitution (2008) and
Acts of Parliament in their **English** version, recovered from Internet Archive copies of the
official websites of the **National Assembly of Bhutan** (nab.gov.bt) and the **Office of the
Attorney General** (oag.gov.bt).

Part of [LawCodex](https://github.com/LawCodex): the laws of every country as Markdown in git.

Retrieved: 2026-10-12. **166 files.** This is a **partial** corpus — read *Gaps* below.

## Contents

| Category | Directory | Files |
|---|---|---:|
| The Constitution of the Kingdom of Bhutan (2008), English text | `constitution/constitution-of-bhutan-2008.md` | 1 |
| Acts (incl. amendment Acts, the Civil and Criminal Procedure Code, Chathrims), English text | `acts/<year>/` | 165 |
| **Total** | | **166** |

122 Acts come from the National Assembly's site (`/assets/uploads/docs/acts/…`), 43 from the Office of
the Attorney General's site (`/wp-content/uploads/…`), for Acts not found on the former.

## Why archived copies?

At retrieval time neither official site was usable: `nab.gov.bt` answered with an unrelated web
application under a TLS certificate for `*.systems.gov.bt`, and `oag.gov.bt` timed out. Both sites'
PDF files are well covered by the Internet Archive; the latest archived copy of each file was used
(`https://web.archive.org/web/<timestamp>id_/<url>`, listed with the Wayback CDX API). Each file
records both the original official URL (`source`) and the archived copy (`archived`).

## Gaps

- **No Dzongkha texts.** Acts are enacted in Dzongkha and English. The Dzongkha PDFs (or Dzongkha
  pages of bilingual PDFs) either use legacy non-Unicode fonts (text comes out as Latin-1 garbage such
  as `hq¾-¿km-º|âG`) or lose stacked letters in extraction (e.g. the Dzongkha Constitution); they are
  not included. English pages of bilingual PDFs were kept.
- **Currency.** The archived copies were captured between 2011 and 2024 (most in 2017). Amendments enacted later, and Acts not
  posted on either site, are missing; files have `status: unknown`. Amendment Acts are separate files
  (texts are not consolidated).
- 97 archived PDFs gave no English text (Dzongkha-only, scanned, or not an Act) and 96 were
  duplicates of another copy of the same Act (the National Assembly copy was preferred).
- Rules and regulations, conventions, and Acts published only on other sites (e.g. the National
  Council) are not covered.

## Structure

```
constitution/constitution-of-bhutan-2008.md
acts/<year>/<slug>.md              year = the year in the Act's title; undated/ when none
```

Front matter: `title` (as printed on the first English page, or derived from the file name when no
title line could be found), `type`, `jurisdiction`, `language` (`en`), `date` (Constitution only),
`status` (`unknown`), `publisher`, `source`, `archived`, `retrieved`.

Body: text extracted with `pdftotext -layout`. `Article N` (Constitution) → `##`, `Chapter`/`Part` →
`###`/`##`, numbered sections → `#### N.` followed by the section text; the short cross-headings that
Bhutanese Acts print above sections are kept in **bold**. The table of contents (dot leaders) is kept
as a plain list. Page numbers and running heads are removed.

## Licence

Laws of Bhutan are official public texts. This compilation adds no copyrightable content.

## Regenerate

```
pip install -r scripts/requirements.txt
python scripts/bt_fetch.py      # lists and downloads archived PDFs to ../_raw/bt (1 request/second)
python scripts/bt_convert.py .  # writes the Markdown files
```
