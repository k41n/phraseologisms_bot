#!/usr/bin/env python3
"""
Collect ЕГЭ phraseology tasks (Тип 25) from rus-ege.sdamgia.ru.

Pipeline:
  1. Download print pages of every Тип 25 sub-category (already gives us
     ~all problems with question+source+answer in a single HTML file).
  2. Parse each problem block; keep only those whose question asks for a
     phraseologism ("выпишите ... фразеологизм").
  3. Extract the source text, slice it down to the sentence range named in
     the question (e.g. "60-65"), and pair it with the answer.
  4. Write phraseo.json.

No third-party deps; cache pages on disk so re-runs are cheap.
"""
from __future__ import annotations

import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
OUT_DIR = ROOT / "out"
CACHE_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

EGE_BASE = "https://rus-ege.sdamgia.ru"
OGE_BASE = "https://rus-oge.sdamgia.ru"

# (host, category_id) → human label.
# - ЕГЭ Тип 25 (Лексическое значение / Фразеологизмы)
# - ОГЭ Тип 12 (Лексический анализ)  — same kind of "найдите фразеологизм" task
SOURCES: dict[tuple[str, int], dict] = {
    (EGE_BASE, 367): {"exam": "ЕГЭ", "label": "ЕГЭ Тип 25 — Задания ФИПИ"},
    (EGE_BASE, 395): {"exam": "ЕГЭ", "label": "ЕГЭ Тип 25 — Демоверсии и прошедшие экзамены"},
    (EGE_BASE, 231): {"exam": "ЕГЭ", "label": "ЕГЭ Тип 25 — Задания для подготовки"},
    (EGE_BASE, 314): {"exam": "ЕГЭ", "label": "ЕГЭ Тип 25 — Прошлые экзамены"},
    (EGE_BASE, 284): {"exam": "ЕГЭ", "label": "ЕГЭ Тип 25 — Тренировочные и диагностические"},
    (OGE_BASE, 139): {"exam": "ОГЭ", "label": "ОГЭ Тип 12 — Открытый банк ФИПИ ч.1"},
    (OGE_BASE, 138): {"exam": "ОГЭ", "label": "ОГЭ Тип 12 — Открытый банк ФИПИ ч.2"},
    # Old "Задания Д27 / Лексический анализ" — yields a small amount of
    # phraseology entries beyond the modern Тип 12 catalog.
    (OGE_BASE, 162): {"exam": "ОГЭ", "label": "ОГЭ Д27 — Альтернативные задания к открытому банку"},
    (OGE_BASE, 135): {"exam": "ОГЭ", "label": "ОГЭ Д27 — Задания для подготовки"},
}

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
]


# ---------------------------------------------------------------------- network


def fetch(url: str, cache_key: str, *, force: bool = False, sleep: float = 1.0) -> str:
    """Polite GET with disk cache. Detects captcha/empty pages and aborts loudly."""
    cache_path = CACHE_DIR / f"{cache_key}.html"
    if cache_path.exists() and not force:
        return cache_path.read_text(encoding="utf-8")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": random.choice(UA_POOL),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru,en;q=0.7",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            break
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 2 ** attempt + random.random()
            print(f"  retry {attempt+1} after {e!r} (sleep {wait:.1f}s)", file=sys.stderr)
            time.sleep(wait)
    else:
        raise RuntimeError(f"failed to fetch {url}")

    lower = body.lower()
    if "captcha" in lower or "проверк" in lower and "робот" in lower:
        raise RuntimeError(
            f"captcha hit at {url} — open in a browser to solve, then rerun "
            f"(cache file will be reused: {cache_path})"
        )
    if len(body) < 1000:
        raise RuntimeError(f"suspiciously small response from {url}: {len(body)} bytes")

    cache_path.write_text(body, encoding="utf-8")
    time.sleep(sleep + random.random() * 0.5)  # be polite
    return body


# ----------------------------------------------------------------------- parsing


SOFT_HYPHEN = "­"
NARROW_NBSP = " "
WORD_JOINER = "⁠"
NBSP = " "


def clean_text(s: str) -> str:
    """Strip soft hyphens, decode entities, normalise whitespace."""
    s = s.replace("&shy;", "").replace(SOFT_HYPHEN, "")
    s = html.unescape(s)
    s = s.replace(NARROW_NBSP, " ").replace(WORD_JOINER, "").replace(NBSP, " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def strip_tags(html_fragment: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", html_fragment))


# Match each problem block in a print-style page: from <div id="textNNN">
# through the corresponding <div id="solNNN">, plus the small <div class="answer">
# block that follows. We extract everything between text-open and the next
# text-open (or end of doc) and pull the pieces out.
PROBLEM_BLOCK = re.compile(
    r'<div\s+id="text(?P<id>\d+)"[^>]*class="probtext"[^>]*>(?P<rest>.*?)'
    r'(?=<div\s+id="text\d+"[^>]*class="probtext"|<table\b|</body>)',
    re.S,
)
TEXT_BODY = re.compile(r"^(?P<body>.*?)</div></div>", re.S)
QUESTION_BLOCK = re.compile(
    r'id="body\d+"\s+class="pbody">(?P<q>.*?)</div></div>', re.S
)
SOL_BLOCK = re.compile(
    r'id="sol\d+"[^>]*>(?P<sol>.*?)</div>\s*<div class="answer"', re.S
)
# Compact answer (no spaces) inside <div class="answer"> — used by sdamgia
# for input matching. Pipe-separated when multiple variants accepted.
ANSWER_VALUE = re.compile(
    r'<div class="answer"[^>]*>\s*<span[^>]*>\s*Ответ:\s*([^<]+)</span>', re.S
)
# Human answer extracted from the tail of the explanation block, e.g.
# "...<span>Ответ:</span> всё равно.<!--rule_body-->".
ANSWER_HUMAN = re.compile(
    r"Ответ:\s*</span>\s*([^<]+?)\s*(?:<|\.\s*<!--)", re.S
)
# In some older problems the "Ответ: ..." line is written without spaces, but
# the body of the explanation quotes the phrase in guillemets («...»).
GUILLEMET_PHRASE = re.compile(r'«([^»]{2,80})»|"([^"]{2,80})"')
SUMMARY_ROW = re.compile(
    r'<tr class="prob_answer">.*?/problem\?id=(\d+).*?'
    r'class="pbody">([^<]*)</td>',
    re.S,
)


def parse_summary_answers(page: str) -> dict[int, str]:
    """Pull the bottom answer table — gives us the canonical normalised answer."""
    out: dict[int, str] = {}
    for m in SUMMARY_ROW.finditer(page):
        pid = int(m.group(1))
        ans = clean_text(m.group(2))
        out[pid] = ans
    return out


def parse_problems(page: str) -> list[dict]:
    """Extract problems from a print page. Returns one dict per problem."""
    answers = parse_summary_answers(page)
    problems: list[dict] = []
    for m in PROBLEM_BLOCK.finditer(page):
        pid = int(m.group("id"))
        body = m.group("rest")

        # Source text: everything between the opening of #text<id> and the
        # first occurrence of </div></div> (which closes .pbody + .probtext).
        tb = TEXT_BODY.match(body)
        source_html = tb.group("body") if tb else ""

        qm = QUESTION_BLOCK.search(body)
        question_html = qm.group("q") if qm else ""

        sm = SOL_BLOCK.search(body)
        sol_html = sm.group("sol") if sm else ""

        compact_match = ANSWER_VALUE.search(body)
        answer_compact_local = (
            clean_text(compact_match.group(1)) if compact_match else ""
        )
        human_match = ANSWER_HUMAN.search(sol_html)
        answer_human = clean_text(human_match.group(1)) if human_match else ""

        # Strip a stray trailing period.
        answer_human = answer_human.rstrip(".,;:")

        # Fallback: if the "human" answer came back without spaces (old style),
        # try a phrase quoted with «...» or written after an em-dash whose
        # space-stripped form matches one of the compact variants.
        compact_for_match = answers.get(pid, "") or answer_compact_local
        if (
            (not answer_human or " " not in answer_human)
            and compact_for_match
        ):
            variants = {v.lower() for v in compact_for_match.split("|") if v}
            sol_clean = clean_text(strip_tags(sol_html))
            candidates = [
                a or b for a, b in GUILLEMET_PHRASE.findall(sol_clean)
            ]
            # "фразеологизм — отвёл глаза" / "фразеологизм: махнули рукой"
            candidates += re.findall(
                r"фразеологизм[ы]?\s*[—\-–:]\s*([А-Яа-яЁё][^.,;«»]{2,60})",
                sol_clean,
            )
            for q in candidates:
                clean = q.strip().rstrip(".,;:")
                if clean.replace(" ", "").lower() in variants:
                    answer_human = clean
                    break

        problems.append(
            {
                "id": pid,
                "question": clean_text(strip_tags(question_html)),
                "source_html": source_html,
                "explanation": clean_text(strip_tags(sol_html)),
                "answer_human": answer_human,
                "answer_compact": answers.get(pid, "") or answer_compact_local,
            }
        )
    return problems


# Recognise phraseology questions. Forms seen in the wild:
#  ЕГЭ:  "Из предложений 60-65 выпишите один фразеологизм."
#  ОГЭ:  "В предложениях 12-16 найдите фразеологизм. Выпишите этот фразеологизм."
# So we just look for an action verb plus the word "фразеологизм" anywhere.
PHRASEO_Q = re.compile(
    r"\b(выпишите|выпиш[ие]те|найдите|укажите|выберите|определите)\b[^.]{0,200}фразеологизм"
    r"|фразеологизм[^.]{0,200}\b(выпишите|выпиш[ие]те|найдите|укажите)\b",
    re.I,
)
# Dashes/minus signs that show up between sentence numbers on sdamgia:
# hyphen, en/em dash, figure dash, horizontal bar, minus sign.
_DASHES = "-‐‑‒–—―−"
# "предложен..." can be in many cases: предложений / предложениях / предложения /
# предложении / предложение. Match the stem and any short ending.
_PRED = r"предложен\w{1,4}"
RANGE_Q = re.compile(rf"{_PRED}\s+(\d+)\s*[{_DASHES}]\s*(\d+)")
SINGLE_Q = re.compile(rf"{_PRED}\s+(\d+)\b")
# "из предложений 10, 11 ..." or "в предложениях 22, 23, 24 ..."
LIST_Q = re.compile(rf"{_PRED}\s+(\d+(?:\s*,\s*\d+)+)")


def question_kind(question: str) -> dict | None:
    if not PHRASEO_Q.search(question):
        return None
    rm = RANGE_Q.search(question)
    if rm:
        return {
            "kind": "range",
            "from": int(rm.group(1)),
            "to": int(rm.group(2)),
            "explicit": None,
        }
    lm = LIST_Q.search(question)
    if lm:
        nums = [int(n) for n in re.findall(r"\d+", lm.group(1))]
        return {"kind": "list", "from": min(nums), "to": max(nums), "explicit": nums}
    sm = SINGLE_Q.search(question)
    if sm:
        n = int(sm.group(1))
        return {"kind": "single", "from": n, "to": n, "explicit": [n]}
    return {"kind": "unknown", "from": None, "to": None, "explicit": None}


SENTENCE_NUM = re.compile(r"\((\d+)\)")


def split_sentences(source_html: str) -> dict[int, str]:
    """Return {sentence_number: text} from a problem's source-text HTML."""
    text = clean_text(strip_tags(source_html))
    # text now looks like "Прочитайте текст и выполните задание. (1)... (2)... ".
    # Walk through (N) markers and slice between them.
    out: dict[int, str] = {}
    matches = list(SENTENCE_NUM.finditer(text))
    for i, m in enumerate(matches):
        n = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[n] = text[start:end].strip()
    return out


def slice_context(
    source_html: str, lo: int, hi: int, *, explicit: list[int] | None = None
) -> tuple[str, list[int]]:
    sents = split_sentences(source_html)
    if explicit:
        keys = [n for n in explicit if n in sents]
    else:
        keys = [n for n in sents if lo <= n <= hi]
    keys.sort()
    chunks = [f"({n}) {sents[n]}" for n in keys]
    return " ".join(chunks), keys


# ---------------------------------------------------------------------- driver


def collect():
    all_problems: list[dict] = []
    # Dedupe across exams by (exam, problem_id) since ЕГЭ and ОГЭ have
    # independent ID spaces.
    seen: set[tuple[str, int]] = set()
    for (host, cid), meta in SOURCES.items():
        url = f"{host}/test?filter=all&category_id={cid}&print=true"
        slug = host.split("//")[-1].split(".")[0]
        cache_key = f"{slug}_cat_{cid}_print"
        print(f"[fetch] {meta['label']}")
        page = fetch(url, cache_key)
        for prob in parse_problems(page):
            key = (meta["exam"], prob["id"])
            if key in seen:
                continue
            seen.add(key)
            prob["source_host"] = host
            prob["source_category_id"] = cid
            prob["source_category"] = meta["label"]
            prob["exam"] = meta["exam"]
            all_problems.append(prob)
    print(f"[parsed] {len(all_problems)} unique problems across all sources")

    phraseo: list[dict] = []
    skipped_no_match = 0
    skipped_no_range = 0
    skipped_no_context = 0
    for prob in all_problems:
        q = prob["question"]
        kind = question_kind(q)
        if not kind:
            skipped_no_match += 1
            continue
        if kind["kind"] == "unknown":
            skipped_no_range += 1
            continue
        ctx, keys = slice_context(
            prob["source_html"], kind["from"], kind["to"], explicit=kind.get("explicit")
        )
        if not ctx:
            skipped_no_context += 1
            continue
        phraseo.append(
            {
                "id": prob["id"],
                "exam": prob["exam"],
                "url": f"{prob['source_host']}/problem?id={prob['id']}",
                "category": prob["source_category"],
                "question": q,
                "sentence_range": [kind["from"], kind["to"]],
                "sentences_found": keys,
                "context": ctx,
                "answer": prob["answer_human"] or prob["answer_compact"],
                "answer_compact": prob["answer_compact"],
                "explanation": prob["explanation"],
            }
        )

    print(
        f"[filter] phraseo={len(phraseo)} "
        f"skipped: not-phraseo={skipped_no_match} "
        f"no-range={skipped_no_range} no-context={skipped_no_context}"
    )

    out_path = OUT_DIR / "phraseo.json"
    out_path.write_text(
        json.dumps(phraseo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[write] {out_path} ({len(phraseo)} entries)")


if __name__ == "__main__":
    collect()
