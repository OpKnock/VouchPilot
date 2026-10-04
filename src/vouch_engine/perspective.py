"""Perspective resolution: infer whose books the sheet belongs to."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

_SUFFIX_RE = re.compile(
    r"\b(pvt|private|limited|ltd|llp|opc|inc|corp|corporation|co|company|enterprises|enterprise|traders|trading|sons)\b\.?",
    re.IGNORECASE,
)


def normalize_party(name: str | None) -> str:
    """Lowercase, strip Pvt/Ltd variants and punctuation for comparison."""
    if name is None:
        return ""
    s = name.strip().lower()
    s = _SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm_gstin(g: str | None) -> str:
    return "" if g is None else str(g).strip().upper().replace(" ", "")


def _fuzzy_group(names: list[str], threshold: int = 90) -> dict[str, str]:
    """Map each normalized name to a canonical group key (first-seen wins)."""
    from rapidfuzz import fuzz

    groups: dict[str, str] = {}
    leaders: list[str] = []
    for n in names:
        if not n:
            continue
        if n in groups:
            continue
        placed = False
        for lead in leaders:
            try:
                score = fuzz.ratio(n, lead)
            except Exception:
                score = 0
            if score >= threshold:
                groups[n] = lead
                placed = True
                break
        if not placed:
            leaders.append(n)
            groups[n] = n
    return groups


def _invoice_prefix(inv: str | None) -> str | None:
    if inv is None:
        return None
    s = str(inv).strip()
    if not s:
        return None
    parts = re.split(r"[\/\-\_\s]+", s)
    return parts[0].upper() if parts and parts[0] else None


def resolve(rows: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    """Infer the reporting entity and tag each row with a perspective.

    Sets ``row['perspective']`` (seller | buyer | neither | unknown) and
    ``row['self_entity']`` in place. Returns ``(self_entity, perspectives)``.
    ``self_entity`` is the display name of the reporting entity, or None.
    """
    if not rows:
        return None, []

    seller_norms: list[str] = []
    buyer_norms: list[str] = []
    all_norms: list[str] = []
    for r in rows:
        sn = normalize_party((r.get("seller") or {}).get("name"))
        bn = normalize_party((r.get("buyer") or {}).get("name"))
        seller_norms.append(sn)
        buyer_norms.append(bn)
        if sn:
            all_norms.append(sn)
        if bn:
            all_norms.append(bn)

    group_of = _fuzzy_group(sorted(set(all_norms)))

    def grp(n: str) -> str:
        return group_of.get(n, n) if n else ""

    seller_g = [grp(n) for n in seller_norms]
    buyer_g = [grp(n) for n in buyer_norms]

    total_counts: Counter[str] = Counter()
    seller_sides: dict[str, set[int]] = defaultdict(set)
    buyer_sides: dict[str, set[int]] = defaultdict(set)
    display: dict[str, Counter[str]] = defaultdict(Counter)
    for i, r in enumerate(rows):
        sg, bg = seller_g[i], buyer_g[i]
        if sg:
            total_counts[sg] += 1
            seller_sides[sg].add(i)
            raw = ((r.get("seller") or {}).get("name") or "").strip()
            if raw:
                display[sg][raw] += 1
        if bg:
            total_counts[bg] += 1
            buyer_sides[bg].add(i)
            raw = ((r.get("buyer") or {}).get("name") or "").strip()
            if raw:
                display[bg][raw] += 1

    # Candidates appearing on BOTH sides.
    both = [k for k in total_counts if k in seller_sides and k in buyer_sides]
    self_group: str | None = None
    if both:
        ranked = sorted(both, key=lambda k: total_counts[k], reverse=True)
        top = ranked[0]
        second = total_counts[ranked[1]] if len(ranked) > 1 else -1
        if total_counts[top] > second:
            self_group = top
        # Tie -> fall through to GSTIN / series tiebreaks.
    else:
        # No entity on both sides: self stays None unless series/GSTIN says otherwise.
        self_group = None

    # Tiebreak 1: GSTIN appearing on both sides.
    if self_group is None:
        seller_gstins: set[str] = set()
        buyer_gstins: set[str] = set()
        for r in rows:
            sg = _norm_gstin((r.get("seller") or {}).get("gstin"))
            bg = _norm_gstin((r.get("buyer") or {}).get("gstin"))
            if sg:
                seller_gstins.add(sg)
            if bg:
                buyer_gstins.add(bg)
        shared = seller_gstins & buyer_gstins
        shared.discard("")
        if shared:
            # Most frequent shared GSTIN's entity wins.
            cnt: Counter[str] = Counter()
            for r in rows:
                for side in ("seller", "buyer"):
                    g = _norm_gstin((r.get(side) or {}).get("gstin"))
                    if g in shared:
                        nm = grp(normalize_party((r.get(side) or {}).get("name")))
                        if nm:
                            cnt[nm] += 1
            if cnt:
                self_group = cnt.most_common(1)[0][0]

    # Tiebreak 2: own-series detection — invoice prefix with numeric sequence on one side.
    if self_group is None:
        prefixes = [_invoice_prefix((r.get("doc") or {}).get("invoice_number")) for r in rows]
        freq = Counter(p for p in prefixes if p)
        if freq:
            top_prefix, top_n = freq.most_common(1)[0]
            if top_n >= 3 and top_n >= len(rows) / 2:
                idxs = [i for i, p in enumerate(prefixes) if p == top_prefix]
                sell_c = Counter(seller_g[i] for i in idxs if seller_g[i])
                buy_c = Counter(buyer_g[i] for i in idxs if buyer_g[i])
                # Own series => one side consistent, other side varied.
                if sell_c and buy_c:
                    top_s, n_s = sell_c.most_common(1)[0]
                    top_b, n_b = buy_c.most_common(1)[0]
                    share_s = n_s / len(idxs)
                    share_b = n_b / len(idxs)
                    if share_s >= 0.8 and share_b < 0.8:
                        self_group = top_s
                    elif share_b >= 0.8 and share_s < 0.8:
                        self_group = top_b

    self_entity: str | None = None
    if self_group:
        cands = display.get(self_group)
        self_entity = cands.most_common(1)[0][0] if cands else self_group

    perspectives: list[str] = []
    for i, r in enumerate(rows):
        sg, bg = seller_g[i], buyer_g[i]
        if self_group is None:
            persp = "unknown"
        else:
            s_self = bool(sg) and sg == self_group
            b_self = bool(bg) and bg == self_group
            if s_self and not b_self:
                persp = "seller"
            elif b_self and not s_self:
                persp = "buyer"
            elif not s_self and not b_self:
                if sg or bg:
                    persp = "neither"
                else:
                    persp = "unknown"
            else:  # both sides are self (internal transfer)
                persp = "neither"
        r["perspective"] = persp
        r["self_entity"] = self_entity
        perspectives.append(persp)

    return self_entity, perspectives
