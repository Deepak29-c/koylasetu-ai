"""Word cloud and topic grouping for past Parliament Questions (guide section 11, Module E).

Pure functions, no database, so everything here is unit-tested on fixed text.

Why not BERTopic + KeyBERT + wordcloud (the guide's first suggestion): they pull in torch,
UMAP and HDBSCAN (well over 1 GB in the Docker image and CI) and BERTopic is not deterministic
run to run. Instead:

- Cleaning: lowercase, keep Latin and Devanagari words, drop numbers and punctuation, drop
  English + Hindi stopwords and a domain stopword list (guide 11: ministry, government,
  whether, details, ...).
- Topics: TF-IDF over words and two-word phrases, then NMF (non-negative matrix
  factorisation) from scikit-learn with a fixed initialisation, so the same questions always
  give the same topics. Each topic's label is its top keywords; each question goes to the
  topic it loads most on.
- Keywords per question (what KeyBERT would give): the question's highest TF-IDF terms.
- Word cloud: word counts returned as JSON; the browser draws them, so there is no image
  library (and no C extension) on the server.

Hindi and English questions on the same subject would otherwise never meet in one topic,
because they share no words. A small glossary maps common Hindi domain words to their English
form before topic building (not in the word cloud, which shows the words as asked).
"""

from __future__ import annotations

import math
import re
import warnings
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sklearn.decomposition import NMF
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

# Latin words (with inner hyphens: "e-auction") or Devanagari words. Devanagari digits
# (U+0966-096F) and the danda (U+0964-0965) are left out, so they split words like punctuation.
_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)*|[ऀ-ॣॱ-ॿ‌‍]+")

# Filler that PQ wording always contains; it says nothing about the subject (guide 11).
DOMAIN_STOPWORDS_EN = frozenset("""
    ministry ministries government governments gov govt union central whether details detail
    state-wise year-wise month-wise district-wise company-wise wise steps step taken take
    coal coals india indian minister ministers please pleased thereof therefor thereto
    therein reasons reason state states country countries said aforesaid regard regarding
    also number numbers present current currently year years last during till date any
    proposal proposed measures measure being made make time period total various besides
    so if the answer question questions lok sabha rajya starred unstarred shri smt dr
    kumari laid table house statement sir yes government's info information data view
    views including etc per cent percent pertaining namely likely whereby propose
    limited ltd received receive meet meeting quantum quantity action actions ensure
    ensured compared comparison previous available comprehensive fact caused does far
    ifso ofcoal coai coel coa-l thereon thereupon therefrom thereop
    """.split())
DOMAIN_STOPWORDS_HI = frozenset("""
    मंत्रालय सरकार सरकारों केंद्र केन्द्र केंद्रीय क्या ब्यौरा ब्योरा ब्यौरे ब्योरे
    राज्य-वार राज्यवार वर्ष-वार वर्षवार कदम उठाए उठाये गए गये कोयला कोयले भारत देश मंत्री कृपा
    बताने करेंगे तत्संबंधी संबंधी तत्सम्बन्धी कारण वर्तमान वर्ष वर्षों दौरान प्रस्ताव उपाय
    लोक सभा राज्यसभा लोकसभा अतारांकित तारांकित प्रश्न उत्तर श्री श्रीमती डॉ विवरण
    """.split())
HINDI_STOPWORDS = frozenset("""
    का की के को में से पर ने है हैं था थी थे हो होता होती होते होना होने और एवं तथा या
    यह यहाँ यहां वह वहाँ वहां ये वे इस उस इन उन इसे उसे इसका उसका इसकी उसकी इसके उसके
    जो जिस जिन जिसे कि भी ही तो न नहीं ना कोई कुछ सभी सब किसी किया किये किए गया गई गयी
    कर करना करने करता करते करती द्वारा लिए लिये साथ बाद पहले अब तक जब तब यदि अगर
    अपने अपना अपनी आदि रहा रही रहे रहता रूप बारे प्रति वाले वाली वाला संबंध सम्बन्ध
    एक दो इत्यादि जैसे कैसे कहाँ क्यों जा जाता जाती जाते जाने दिया दी दिए दिये ले लेकर
    """.split())
# scikit-learn's English list also drops a few words that are real PQ subjects ("mine fire").
_KEEP_EN = frozenset({"mine", "fire", "bill", "interest", "system"})
STOPWORDS = (frozenset(ENGLISH_STOP_WORDS) - _KEEP_EN) | DOMAIN_STOPWORDS_EN | DOMAIN_STOPWORDS_HI
STOPWORDS |= HINDI_STOPWORDS

# Hindi domain word -> English form, used only for topic building (see module docstring).
HINDI_GLOSSARY = {
    "कोकिंग": "coking",
    "बिजली": "power",
    "विद्युत": "power",
    "ताप": "thermal",
    "संयंत्र": "plant",
    "संयंत्रों": "plant",
    "खान": "mine",
    "खानों": "mine",
    "खदान": "mine",
    "खदानों": "mine",
    "उत्पादन": "production",
    "आयात": "import",
    "निर्यात": "export",
    "सुरक्षा": "safety",
    "दुर्घटना": "accident",
    "दुर्घटनाओं": "accident",
    "नीलामी": "auction",
    "आपूर्ति": "supply",
    "कमी": "shortage",
    "मांग": "demand",
    "लक्ष्य": "target",
    "प्रदूषण": "pollution",
    "पर्यावरण": "environment",
    "पुनर्वास": "rehabilitation",
    "विस्थापित": "displaced",
    "भंडार": "stock",
    "रेल": "rail",
    "रेलवे": "railway",
    "मजदूर": "worker",
    "श्रमिक": "worker",
    "कर्मचारी": "employee",
    "कर्मचारियों": "employee",
    "आवंटन": "allocation",
    "लिंकेज": "linkage",
    "वाशरी": "washery",
    "निजीकरण": "privatisation",
    "विनिवेश": "disinvestment",
}

_KEEP_S = ("ss", "us", "is", "ous")
_NO_SINGULAR = frozenset({"series", "species", "news", "gas", "ltd", "lakhs"})


def singular(word: str) -> str:
    """Rough English plural -> singular, so "plants" and "plant" count as one word."""
    if len(word) <= 4 or not word.isascii() or word in _NO_SINGULAR:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith(_KEEP_S):
        return word[:-1]
    return word


def tokenize(text: str, *, glossary: bool = False) -> list[str]:
    """Cleaned content words of `text`, in order (guide 11 "Clean")."""
    words = []
    for raw in _TOKEN.findall(text.lower()):
        word = singular(raw.strip("-"))
        if glossary:
            word = HINDI_GLOSSARY.get(word, word)
        if word in STOPWORDS or singular(word) in STOPWORDS:
            continue
        if word.isascii() and len(word) < 3:
            continue
        if not word.isascii() and len(word) < 2:
            continue
        words.append(word)
    return words


def _terms(text: str) -> list[str]:
    """Words plus two-word phrases ("power plant", "coking washery") for TF-IDF."""
    words = tokenize(text, glossary=True)
    return words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False) if a != b]


def word_cloud(texts: Iterable[str], top_n: int = 80) -> list[dict]:
    """[{"text": word, "weight": count}, ...], most frequent first. Weight = number of texts
    the word appears in, so one long question that repeats a word does not dominate."""
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(set(tokenize(text)))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"text": w, "weight": n} for w, n in ranked[:top_n]]


# --- Periods -----------------------------------------------------------------------------

SESSIONS = ("budget", "monsoon", "winter")


def session_of(day: date) -> str:
    """Parliament session a date falls in: Budget (Jan-May), Monsoon (Jun-Oct), Winter
    (Nov-Dec). The first session after a general election (June) counts as Monsoon."""
    if day.month <= 5:
        return "budget"
    if day.month <= 10:
        return "monsoon"
    return "winter"


def period_counts(dates: Iterable[date | None]) -> dict:
    """{"year": {"2021": 4, ...}, "session": {"2021-budget": 3, ...}, "undated": n}."""
    years: Counter[str] = Counter()
    sessions: Counter[str] = Counter()
    undated = 0
    for day in dates:
        if day is None:
            undated += 1
            continue
        years[str(day.year)] += 1
        sessions[f"{day.year}-{session_of(day)}"] += 1
    return {
        "year": dict(sorted(years.items())),
        "session": dict(sorted(sessions.items())),
        "undated": undated,
    }


# --- Word cloud filters ------------------------------------------------------------------

# How a subsidiary is named inside question text. PQs carry no org unit, so the subsidiary
# filter on questions is a text match; on documents it is the uploading org unit.
SUBSIDIARY_NAMES = {
    "ECL": r"\becl\b|(?<!south )eastern coalfields",
    "BCCL": r"\bbccl\b|bharat coking",
    "CCL": r"\bccl\b|central coalfields",
    "NCL": r"\bncl\b|northern coalfields",
    "WCL": r"\bwcl\b|western coalfields",
    "SECL": r"\bsecl\b|south eastern coalfields",
    "MCL": r"\bmcl\b|mahanadi coalfields",
    "NEC": r"\bnec\b|north eastern coalfields",
    "CMPDI": r"\bcmpdi\b|central mine planning",
    "SCCL": r"\bsccl\b|singareni",
}


def mentions_subsidiary(text: str, code: str) -> bool:
    pattern = SUBSIDIARY_NAMES.get(code.upper(), rf"\b{re.escape(code.lower())}\b")
    return re.search(pattern, text.lower()) is not None


def keep_question(day: date | None, text: str, session: str | None, subsidiary: str | None) -> bool:
    """Word-cloud filters that are not plain SQL columns: session and subsidiary."""
    if session and (day is None or session_of(day) != session):
        return False
    return not subsidiary or mentions_subsidiary(text, subsidiary)


def fy_start_year(fy: str | None) -> int | None:
    """'FY 2023-24' -> 2023 (documents are filtered by the year their FY starts)."""
    m = re.search(r"(\d{4})", fy or "")
    return int(m.group(1)) if m else None


# --- Topics ------------------------------------------------------------------------------


@dataclass
class TopicDoc:
    id: str
    text: str
    day: date | None = None


@dataclass
class TopicMember:
    id: str
    weight: float
    keywords: list[str]


@dataclass
class TopicDraft:
    topic_no: int
    label: str
    keywords: list[str]
    size: int
    period_counts: dict
    members: list[TopicMember] = field(default_factory=list)


def default_topic_count(n_docs: int) -> int:
    """About sqrt(n/2) topics: 6 for 70 questions, 16 for 500, never more than 20."""
    return max(2, min(20, round(math.sqrt(n_docs / 2))))


def _pick_keywords(terms: Sequence[str], scores: np.ndarray, k: int) -> list[str]:
    """Top-k terms by score. A phrase takes the place of its single words chosen earlier, and
    a word already inside a chosen phrase is skipped, so the list reads "power plant, ..."
    rather than "power, power plant, plant"."""
    chosen: list[str] = []
    for idx in np.argsort(-scores, kind="stable"):
        if scores[idx] <= 0 or len(chosen) == k:
            break
        term = terms[idx]
        parts = term.split(" ")
        covered = {w for c in chosen for w in c.split(" ")}
        if len(parts) == 1:
            if term not in covered:
                chosen.append(term)
            continue
        if any(term == c for c in chosen):
            continue
        at = next((i for i, c in enumerate(chosen) if c in parts), len(chosen))
        chosen = [c for c in chosen if c not in parts]
        chosen.insert(min(at, len(chosen)), term)
    return chosen[:k]


def build_topics(
    docs: Sequence[TopicDoc], n_topics: int | None = None, n_keywords: int = 8
) -> list[TopicDraft]:
    """Group questions into topics. Deterministic: same input, same output.

    Returns topics largest first, numbered 0..n-1. A question with no usable words (e.g.
    only stopwords) is left out of every topic.
    """
    docs = [d for d in docs if _terms(d.text)]
    if len(docs) < 2:
        return []
    vectorizer = TfidfVectorizer(
        analyzer=_terms,
        min_df=2 if len(docs) >= 10 else 1,
        max_df=0.6 if len(docs) >= 10 else 1.0,
        sublinear_tf=True,
    )
    try:
        matrix = vectorizer.fit_transform([d.text for d in docs])
    except ValueError:  # no term left after min_df / max_df
        return []
    terms = vectorizer.get_feature_names_out()
    k = min(n_topics or default_topic_count(len(docs)), len(docs), len(terms))
    if k < 1:
        return []
    model = NMF(n_components=k, init="nndsvd", max_iter=1000, random_state=0)
    with warnings.catch_warnings():
        # Not fully converging only means slightly softer weights; the grouping is stable.
        warnings.simplefilter("ignore", ConvergenceWarning)
        doc_topic = model.fit_transform(matrix)  # docs x topics
    topic_term = model.components_  # topics x terms

    groups: dict[int, list[int]] = {}
    for i, row in enumerate(doc_topic):
        if row.max() > 0:
            groups.setdefault(int(np.argmax(row)), []).append(i)

    dense = matrix.toarray()
    drafts = []
    for t, members in groups.items():
        keywords = _pick_keywords(terms, topic_term[t], n_keywords)
        members.sort(key=lambda i: (-doc_topic[i, t], docs[i].id))
        drafts.append(
            TopicDraft(
                topic_no=-1,
                label=" · ".join(keywords[:3]),
                keywords=keywords,
                size=len(members),
                period_counts=period_counts(docs[i].day for i in members),
                members=[
                    TopicMember(
                        id=docs[i].id,
                        weight=round(float(doc_topic[i, t]), 4),
                        keywords=_pick_keywords(terms, dense[i], 5),
                    )
                    for i in members
                ],
            )
        )
    drafts.sort(key=lambda d: (-d.size, d.label))
    for no, draft in enumerate(drafts):
        draft.topic_no = no
    return drafts
