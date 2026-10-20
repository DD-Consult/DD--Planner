#!/usr/bin/env python3
"""
generate_proposal.py  (v4, advisory-led narrative proposal)
-----------------------------------------------------------
Fills proposal-template.html with a JSON brief and writes a finished,
self-contained static HTML file: the file you actually deploy.

Deliberately simple: plain string substitution, standard library only, no
network calls. An AI model (Claude, Gemini, anything) is used UPSTREAM to
help draft the prose fields of the JSON brief and to review it. It is not
the thing editing the HTML, doing the pricing arithmetic or drawing the
diagrams. Every dollar figure, bar width, chevron width, meter segment and
week total in the output is derived here from raw inputs (hours, rates,
percentages, week counts, level numbers), never typed in as a finished
number, so a miscalculation can never reach a client.

What the page contains (see proposal-template.html):
  cover -> 01 Understanding -> 02 The shift -> 03 Our approach
  (LEAD / DESIGN / BUILD + the 4-stage TOS) -> 04 Your advisory options
  (Path A / B / C ladder + extensions) -> 05 Recommended plan ->
  06 Measuring success -> 07 Transparent investment -> 08 Why DD ->
  09 Next steps + accept -> Appendix (technical detail, AWS funding admin).

Static brand copy (the Triangle, the TOS stage names, credentials, delivery
guardrails) lives in the template and in the constants below. Per-client
content lives in the JSON brief. Case studies are picked by id from
case-studies.json, DD's approved library.

Usage:
    python3 generate_proposal.py sample-proposal-data.json
    python3 generate_proposal.py sample-proposal-data.json --out output/custom-name.html
"""

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE_PATH = HERE / "proposal-template.html"
ASSETS_DIR = HERE / "assets"
CASE_LIBRARY_PATH = HERE / "case-studies.json"

# --------------------------------------------------------------------------
# Fixed brand structure. These never change per client.
# --------------------------------------------------------------------------

# Path A / B / C, always exactly three. Icon + label live here, not in every brief.
PATHS = {
    "a": {"label": "Path A", "icon": "i-flag"},
    "b": {"label": "Path B", "icon": "i-target"},
    "c": {"label": "Path C", "icon": "i-building"},
}

# The canonical 4-stage Transformation Operating System (TOS).
TOS_STAGES = {
    1: ("Align & Audit", "Ground-truth diagnostics of the systems and workflows your staff actually use."),
    2: ("Architect & Select", "Process re-engineering, vendor selection and the buy-vs-build gate."),
    3: ("Engineer & Operationalize", "Software builds, integrations and AI engineering, with zero operational downtime as the standard."),
    4: ("Adopt & Sustain", "ADKAR-led change, training sandboxes, hypercare and ongoing assurance."),
}

VECTORS = ("lead", "design", "build")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)


def esc(s):
    return escape(str(s), quote=True)


def fmt_money(n, currency):
    """Whole dollars when whole, otherwise two decimals."""
    if abs(n - round(n)) < 0.005:
        return f"{currency} {int(round(n)):,}"
    return f"{currency} {n:,.2f}"


def num_words(n):
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight",
             9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve"}
    return words.get(n, str(n))


def load_logo_data_uris():
    def uri(name):
        return "data:image/png;base64," + (ASSETS_DIR / name).read_text().strip()
    return uri("dd-icon.b64.txt"), uri("dd-lockup.b64.txt"), uri("dd-compass.b64.txt")


def known_icons(template_text):
    return set(re.findall(r'<symbol id="(i-[a-z0-9-]+)"', template_text))


class Ctx:
    """Holds things render functions need: currency and the valid icon set."""
    def __init__(self, currency, icons):
        self.currency = currency
        self.icons = icons

    def icon(self, name, cls="icon"):
        if name not in self.icons:
            raise SystemExit(f"Unknown icon '{name}'. Available: {', '.join(sorted(self.icons))}")
        return f'<svg class="{cls}"><use href="#{name}"></use></svg>'

    def money(self, n):
        return fmt_money(n, self.currency)


# --------------------------------------------------------------------------
# pricing math (single source of truth for every dollar on the page)
# --------------------------------------------------------------------------

def path_totals(pricing, key):
    """Return a dict of computed amounts for one path."""
    block = pricing[f"path_{key}"]
    if key == "a":
        fee = block["tier_fee"]
        offset = block.get("aws_offset", fee)  # T-05: the AIAF tier fee is offset in full, if approved
        return {"core": fee, "governance": None, "contingency": None, "gross": fee,
                "offset": offset, "net_if_approved": fee - offset}
    core = block["hours"] * block["hourly_rate"]
    gov = core * block["governance_pct"]
    cont = core * block["contingency_pct"]
    gross = core + gov + cont
    return {"core": core, "governance": gov, "contingency": cont, "gross": gross,
            "offset": None, "net_if_approved": gross}


# --------------------------------------------------------------------------
# renderers: each returns an HTML string
# --------------------------------------------------------------------------

def render_cover_chips(focus):
    return "".join(f'<span class="{"on" if v in focus else ""}">{v.upper()}</span>' for v in VECTORS)


def render_vec_flags(focus):
    out = {}
    for v in VECTORS:
        on = v in focus
        out[f"{{{{VEC_{v.upper()}_FOCUS}}}}"] = " focus" if on else ""
        out[f"{{{{VEC_{v.upper()}_TAG}}}}"] = '<span class="focus-tag">In this proposal</span>' if on else ""
    return out


def render_paragraphs(paras):
    return "\n".join(f'<p class="lead">{esc(p)}</p>' for p in paras)


def render_quote(q):
    if not q:
        return ""
    return (f'<figure class="quote"><p>“{esc(q["text"])}”</p>'
            f'<cite>{esc(q["attribution"])}</cite></figure>')


def render_challenges(ctx, items):
    return "\n".join(
        f'<div class="card"><div class="ico sig">{ctx.icon(i["icon"])}</div>'
        f'<h3>{esc(i["title"])}</h3><p>{esc(i["description"])}</p></div>'
        for i in items)


def render_maturity(rows):
    """Five-segment meter per dimension. Segments lit = level number (1-5)."""
    out = []
    for r in rows:
        level = max(1, min(5, int(r["level_number"])))
        segs = "".join(f'<span class="meter-seg{" on" if n < level else ""}"></span>' for n in range(5))
        out.append(
            '<li class="meter-item"><div class="meter-top">'
            f'<span class="meter-label">{esc(r["dimension"])}</span>'
            f'<span class="meter-level">Level {level} of 5</span></div>'
            f'<div class="meter-track" role="img" aria-label="{esc(r["dimension"])}: level {level} of 5">{segs}</div>'
            f'<p class="meter-note">{esc(r["note"])}</p></li>')
    return "\n".join(out)


def render_shift_list(ctx, points, icon):
    return "\n".join(f'<li>{ctx.icon(icon)}<span>{esc(p)}</span></li>' for p in points)


def render_tos_chevrons(scope):
    out = []
    for n in sorted(TOS_STAGES):
        name, desc = TOS_STAGES[n]
        on = n in scope
        flag = '<span class="chev-flag">In this proposal</span>' if on else ""
        out.append(f'<div class="chev{" on" if on else ""}" role="listitem"><div class="chev-n">{n}</div>'
                   f'<h4>{esc(name)}</h4><p>{esc(desc)}</p>{flag}</div>')
    return "\n".join(out)


def render_options_ladder(ctx, options, pricing, rec):
    out = []
    for o in options:
        key = o["path"]
        meta = PATHS[key]
        t = path_totals(pricing, key)
        block = pricing[f"path_{key}"]
        chips = "".join(f'<b class="{"on" if n in o["stages"] else ""}">{n}</b>' for n in sorted(TOS_STAGES))
        inc = "".join(f'<li>{ctx.icon("i-check")}<span>{esc(i)}</span></li>' for i in o["includes"])
        if key == "a":
            price = ctx.money(t["gross"])
            small = (f'Fixed fee, ex GST. Positioned to apply for AWS funding that, if approved, offsets it '
                     f'in full (net {ctx.money(t["net_if_approved"])}).')
        else:
            price = ctx.money(t["gross"])
            small = "Planning estimate, ex GST. Reconfirmed at the end of Stage 2."
        rec_tag = '<span class="rec-tag">Recommended start</span>' if key == rec else ""
        out.append(
            f'<article class="opt opt-{key}{" recommended" if key == rec else ""}">{rec_tag}'
            f'<div class="opt-band">{ctx.icon(meta["icon"])}<div><div class="opt-path">{meta["label"]}</div>'
            f'<h3>{esc(o["name"])}</h3></div></div>'
            '<div class="opt-body">'
            f'<p class="opt-tag">{esc(o["tagline"])}</p><p class="opt-who">{esc(o["who_for"])}</p>'
            f'<ul class="inc">{inc}</ul>'
            f'<div class="stage-chips">Stages covered {chips}</div>'
            '<div class="opt-foot">'
            f'<div class="opt-price">{esc(price)}<small>{esc(small)}</small></div>'
            f'<div class="opt-dur">{ctx.icon("i-clock")}<span>{esc(block["duration_label"])}</span></div>'
            f'<button class="opt-pick" type="button" data-path="{key}" aria-pressed="false">'
            f'{ctx.icon("i-check-circle")}Choose this option</button>'
            '</div></div></article>')
    return "\n".join(out)


def render_addons(ctx, items):
    out = []
    for a in items:
        if "price_label" in a:
            price = a["price_label"]
        elif "price_to" in a:
            price = f'{ctx.money(a["price_from"])} to {a["price_to"]:,.0f} {a["price_unit"]}, ex GST'
        else:
            price = f'From {ctx.money(a["price_from"])} {a["price_unit"]}, ex GST'
        if a.get("price_note"):
            price += f' · {a["price_note"]}'
        out.append(
            f'<div class="addon"><div class="ico bro">{ctx.icon(a["icon"])}</div>'
            f'<div><h4>{esc(a["title"])}</h4><p>{esc(a["description"])}</p>'
            f'<span class="addon-price">{esc(price)}</span></div></div>')
    return "\n".join(out)


def render_stage_cards(ctx, deliverables, scope):
    out = []
    for n in sorted(TOS_STAGES):
        name = TOS_STAGES[n][0]
        on = n in scope
        items = "".join(f'<li>{ctx.icon("i-check")}<span>{esc(d)}</span></li>' for d in deliverables[str(n)])
        flag = ('<span class="st-flag in">In this proposal</span>' if on else '<span class="st-flag">Later stage</span>')
        out.append(f'<div class="stage-card{"" if on else " later"}">{flag}<div class="st-n">{n}</div>'
                   f'<h3>{esc(name)}</h3><ul>{items}</ul></div>')
    return "\n".join(out)


def render_timeline(items):
    """Chevron widths are proportional to weeks (CSS flex-grow = weeks)."""
    out = []
    for it in items:
        on = it.get("on", True)
        out.append(f'<div class="chev{" on" if on else ""}" style="--w:{it["weeks"]}">'
                   f'<div class="tl-weeks">{esc(it["label"])}</div><h4>{esc(it["title"])}</h4>'
                   f'<p>{esc(it["detail"])}</p></div>')
    return "\n".join(out)


def timeline_total_weeks(items):
    return sum(i["weeks"] for i in items if i.get("on", True))


def render_outcomes(items):
    return "\n".join(
        f'<div class="outcome"><div class="o-val{" long" if len(o["value"]) > 6 else ""}"><span>{esc(o["value"])}</span></div>'
        f'<h4>{esc(o["label"])}</h4><p>{esc(o["detail"])}</p></div>' for o in items)


def render_gates(ctx, gates):
    out = []
    for i, g in enumerate(gates, start=1):
        out.append(f'<div class="gate"><div class="gate-n">Gate {i} · {esc(TOS_STAGES[i][0])}</div>'
                   f'<h3>{esc(g["title"])}</h3><p>{ctx.icon("i-check-circle")}<span>{esc(g["evidence"])}</span></p></div>')
    return "\n".join(out)


def render_investment(ctx, options, pricing, rec):
    names = {o["path"]: o["name"] for o in options}
    totals = {k: path_totals(pricing, k) for k in PATHS}
    max_gross = max(t["gross"] for t in totals.values())

    # --- bars (to scale) ---
    bars = []
    for k in PATHS:
        t = totals[k]
        pct = max(4.0, t["gross"] / max_gross * 100)
        dur = pricing[f"path_{k}"]["duration_label"]
        note = ""
        if k == "a":
            note = (f'<div class="bar-note">If AWS approves funding, the net cost is {esc(ctx.money(t["net_if_approved"]))}. '
                    "Approval is AWS's decision.</div>")
        bars.append(
            f'<div class="bar-row"><div class="bar-label">{PATHS[k]["label"]}<small>{esc(names[k])} · {esc(dur)}</small></div>'
            f'<div class="bar-track"><div class="bar-fill bar-{k}" style="width:{pct:.1f}%">{esc(ctx.money(t["gross"]))}</div></div>{note}</div>')

    # --- table (mirrors T-05 section 6 rows) ---
    th = "".join(f'<th class="path{" rec" if k == rec else ""}">{PATHS[k]["label"]}</th>' for k in PATHS)

    b_blk, c_blk = pricing["path_b"], pricing["path_c"]
    gov_label = "Project Governance"
    if b_blk["governance_pct"] == c_blk["governance_pct"]:
        gov_label += f' ({b_blk["governance_pct"] * 100:.0f}%)'
    cont_label = "Risk Contingency"
    if b_blk["contingency_pct"] == c_blk["contingency_pct"]:
        cont_label += f' ({b_blk["contingency_pct"] * 100:.0f}%)'

    def row(label, brk, cells, cls=""):
        tds = "".join(f'<td class="path{" rec" if k == rec else ""}" data-label="{PATHS[k]["label"]}">{v}</td>' for k, v in zip(PATHS, cells))
        attr = f' class="{cls}"' if cls else ""
        return f'<tr{attr}><td class="cat">{esc(label)}<span class="brk">{esc(brk)}</span></td>{tds}</tr>'

    m = ctx.money
    a, b, c = totals["a"], totals["b"], totals["c"]
    rows = [
        row("Core Consulting & Dev", "BA discovery, architecture & build", [m(a["core"]), m(b["core"]), m(c["core"])]),
        row(gov_label, "QA, showcases, RAID log", ["Included in fixed fee", m(b["governance"]), m(c["governance"])]),
        row(cont_label, "Technical / API blockers", ["Included in fixed fee", m(b["contingency"]), m(c["contingency"])]),
        row("Gross Investment", "Total base cost", [m(a["gross"]), m(b["gross"]), m(c["gross"])], cls="emph"),
        row("AWS Partner Offset (if approved)", "Subject to AWS review and eligibility", [f'({m(a["offset"])})', "—", "—"]),
        row("Net Investment", "Payable by you, ex GST. Path A assumes AWS approval.",
            [f'{m(a["net_if_approved"])} (if approved)', m(b["net_if_approved"]), m(c["net_if_approved"])], cls="emph highlight"),
    ]
    return "\n".join(bars), th, "\n".join(rows)


def render_assumptions(items):
    return "\n".join(f"<li>{esc(s)}</li>" for s in items)


def render_case_studies(ids, library):
    out = []
    for cid in ids:
        if cid not in library:
            raise SystemExit(f"case_study_ids: '{cid}' is not in case-studies.json")
        c = library[cid]
        out.append(
            '<div class="case">'
            f'<span class="case-sector">{esc(c["sector"])}</span><h3>{esc(c["title"])}</h3>'
            f'<p class="case-chal">{esc(c["challenge"])}</p>'
            f'<p class="case-res"><b>Result</b>{esc(c["result"])}</p></div>')
    return "\n".join(out)


def render_team(team):
    out = []
    for p in team:
        who = esc(p["name"]) if p.get("name") else esc(p["role"])
        role = esc(p["role"]) if p.get("name") else "To be named at kickoff"
        out.append(f'<div class="person"><div class="avatar">{esc(p["initials"])}</div>'
                   f'<div><h4>{who}</h4><div class="role">{role}</div><p>{esc(p["focus"])}</p></div></div>')
    return "\n".join(out)


def render_next_steps(steps):
    return "\n".join(
        f'<div class="step-card"><div class="chev-n">{i}</div><h3>{esc(s["title"])}</h3><p>{esc(s["description"])}</p></div>'
        for i, s in enumerate(steps, start=1))


def render_accept_radios(ctx, options, pricing, rec):
    out = []
    for o in options:
        k = o["path"]
        total = ctx.money(path_totals(pricing, k)["gross"])
        star = " (recommended)" if k == rec else ""
        out.append(f'<label><input type="radio" name="path" value="{k}"><span><b>{PATHS[k]["label"]}</b>, '
                   f'{esc(o["name"])} · {esc(total)}{star}</span></label>')
    return "\n".join(out)


def render_friction_flow(ctx, rows):
    parts = []
    for i, r in enumerate(rows):
        parts.append(f'<div class="flow-step">{ctx.icon("i-alert")}<span>{esc(r["step"])}</span></div>')
        if i < len(rows) - 1:
            parts.append(ctx.icon("i-arrow-right", "icon flow-arrow"))
    return "".join(parts)


def render_friction_rows(rows):
    return "\n".join(
        f'<tr><td>{esc(r["step"])}</td><td>{esc(r["system"])}</td><td>{esc(r["friction"])}</td><td>{esc(r["impact"])}</td></tr>'
        for r in rows)


def render_target_state(ctx, rows):
    return "\n".join(
        f'<li><span class="req">{esc(r["requirement"])}</span>{ctx.icon("i-arrow-right")}<span>{esc(r["solution"])}</span></li>'
        for r in rows)


def render_aws_stack(ctx, rows):
    out = []
    for i, r in enumerate(rows):
        out.append(f'<div class="stack-card"><span class="stack-layer">{esc(r["layer"])}</span>'
                   f'<span class="stack-service">{esc(r["service"])}</span><p class="stack-fn">{esc(r["function"])}</p></div>')
        if i < len(rows) - 1:
            out.append(f'<div class="stack-arrow">{ctx.icon("i-arrow-down")}</div>')
    return "\n".join(out)


def render_aws_funding_appendix(ctx, fd, a_totals):
    if not fd:
        return ""
    kv = [
        ("AWS account ID", fd["account_id"]), ("Partner of record", fd["partner_of_record"]),
        ("Location", fd["location"]), ("Customer segment", fd["customer_segment"]),
        ("Workload name", fd["workload_name"]), ("Business driver", fd["driver"]),
        ("Planned start", fd["start_date"]), ("Planned end", fd["end_date"]),
        ("Currency", "AUD (AWS converts to USD at request time)"),
        ("Total cost of activity", ctx.money(a_totals["gross"])),
        ("Partner contribution", ctx.money(a_totals["gross"] - a_totals["offset"])),
        ("Requested funding", ctx.money(a_totals["offset"])),
    ]
    rows = "".join(f'<div class="row"><div class="k">{esc(k)}</div><div>{esc(v)}</div></div>' for k, v in kv)
    return ('<h3 class="ap-h">AWS funding administration (Path A)</h3>'
            '<p class="muted" style="font-size:13.5px;">The details DD Consulting submits to AWS when applying for assessment funding. '
            'Shown for transparency; approval is AWS\'s decision.</p>'
            f'<div class="kv-list">{rows}</div>')


# --------------------------------------------------------------------------
# validation (warnings only; hard errors raise)
# --------------------------------------------------------------------------

def validate(data):
    rec = data["recommended_path"]
    if rec not in PATHS:
        raise SystemExit("recommended_path must be one of a / b / c")
    opt = next((o for o in data["options"] if o["path"] == rec), None)
    if not opt:
        raise SystemExit(f"options has no entry for the recommended path '{rec}'")
    if sorted(opt["stages"]) != sorted(data["stages_in_scope"]):
        warn(f"stages_in_scope {data['stages_in_scope']} differs from the recommended option's stages {opt['stages']}")
    weeks = timeline_total_weeks(data["plan"]["timeline"])
    m = re.search(r"(\d+)", data["pricing_model"][f"path_{rec}"]["duration_label"])
    if m and int(m.group(1)) != weeks:
        warn(f"timeline totals {weeks} weeks but path_{rec}.duration_label says '{data['pricing_model'][f'path_{rec}']['duration_label']}'")
    for k in ("1", "2", "3", "4"):
        if k not in data["plan"]["stage_deliverables"]:
            raise SystemExit(f"plan.stage_deliverables is missing stage '{k}'")
    if len(data["success"]["gates"]) != 4:
        raise SystemExit("success.gates must have exactly 4 entries (one per TOS stage)")
    if {o["path"] for o in data["options"]} != set(PATHS):
        raise SystemExit("options must contain exactly path a, b and c")


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build(data):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    ctx = Ctx(data["currency"], known_icons(template))
    library = json.loads(CASE_LIBRARY_PATH.read_text(encoding="utf-8"))
    library.pop("_readme", None)
    validate(data)

    pricing = data["pricing_model"]
    rec = data["recommended_path"]
    focus = data["vectors_in_focus"]
    scope = data["stages_in_scope"]
    icon_uri, lockup_uri, compass_uri = load_logo_data_uris()
    rec_name = next(o["name"] for o in data["options"] if o["path"] == rec)

    understanding = data["understanding"]
    vision = data["vision"]
    plan = data["plan"]
    success = data["success"]
    appendix = data["appendix"]

    bars_html, th_html, rows_html = render_investment(ctx, data["options"], pricing, rec)
    weeks = timeline_total_weeks(plan["timeline"])

    next_intro = f'{data["next_steps_intro"]} Pricing and timelines are valid until {data["valid_until"]}.'

    rep = {
        "{{DD_ICON_DATA_URI}}": icon_uri,
        "{{DD_LOCKUP_DATA_URI}}": lockup_uri,
        "{{DD_COMPASS_DATA_URI}}": compass_uri,

        "{{CLIENT_NAME}}": esc(data["client_name"]),
        "{{PROPOSAL_DATE}}": esc(data["proposal_date"]),
        "{{VALID_UNTIL}}": esc(data["valid_until"]),
        "{{PROPOSAL_SLUG}}": esc(data["proposal_slug"]),
        "{{PREPARED_BY_NAME}}": esc(data["prepared_by_name"]),
        "{{PREPARED_BY_TITLE}}": esc(data["prepared_by_title"]),
        "{{CONTACT_EMAIL}}": esc(data["contact_email"]),
        "{{CONTACT_PHONE}}": esc(data["contact_phone"]),

        "{{PROPOSAL_TITLE}}": esc(data["proposal_title"]),
        "{{PROPOSAL_SUBTITLE}}": esc(data["proposal_subtitle"]),
        "{{COVER_EYEBROW}}": esc(f'Proposal · Recommended start: {PATHS[rec]["label"]}, {rec_name}'),
        "{{COVER_VECTOR_CHIPS_HTML}}": render_cover_chips(focus),
        "{{RECOMMENDED_PATH_KEY}}": rec,

        "{{UNDERSTANDING_PARAGRAPHS_HTML}}": render_paragraphs(understanding["paragraphs"]),
        "{{CLIENT_QUOTE_HTML}}": render_quote(understanding.get("client_quote")),
        "{{CHALLENGE_CARDS_HTML}}": render_challenges(ctx, understanding["challenges"]),
        "{{MATURITY_ROWS_HTML}}": render_maturity(data["readiness_snapshot"]),

        "{{VISION_HEADLINE}}": esc(vision["headline"]),
        "{{SHIFT_FROM_TITLE}}": esc(vision["from_title"]),
        "{{SHIFT_TO_TITLE}}": esc(vision["to_title"]),
        "{{SHIFT_FROM_HTML}}": render_shift_list(ctx, vision["from_points"], "i-x"),
        "{{SHIFT_TO_HTML}}": render_shift_list(ctx, vision["to_points"], "i-check"),

        "{{TOS_CHEVRONS_HTML}}": render_tos_chevrons(scope),

        "{{OPTIONS_INTRO}}": esc(data["options_intro"]),
        "{{OPTIONS_LADDER_HTML}}": render_options_ladder(ctx, data["options"], pricing, rec),
        "{{OPTIONS_NOTE}}": esc(data["options_note"]),
        "{{ADDONS_HTML}}": render_addons(ctx, data["add_ons"]),

        "{{PLAN_HEADLINE}}": esc(plan["headline"]),
        "{{PLAN_INTRO}}": esc(plan["intro"]),
        "{{STAGE_CARDS_HTML}}": render_stage_cards(ctx, plan["stage_deliverables"], scope),
        "{{TIMELINE_TITLE}}": esc(plan["timeline_title"].format(weeks=weeks)),
        "{{TIMELINE_HTML}}": render_timeline(plan["timeline"]),

        "{{OUTCOMES_CAPTION}}": esc(success["outcomes_caption"]),
        "{{OUTCOMES_HTML}}": render_outcomes(success["outcomes"]),
        "{{GATES_HTML}}": render_gates(ctx, success["gates"]),

        "{{INVESTMENT_BARS_HTML}}": bars_html,
        "{{INVEST_TH_HTML}}": th_html,
        "{{INVESTMENT_ROWS_HTML}}": rows_html,
        "{{INVESTMENT_NOTE}}": esc(data["investment_note"]),
        "{{ASSUMPTIONS_HTML}}": render_assumptions(data["assumptions"]),

        "{{CASE_STUDIES_HTML}}": render_case_studies(data["case_study_ids"], library),
        "{{TEAM_HTML}}": render_team(data["team"]),

        "{{NEXT_STEPS_INTRO}}": esc(next_intro),
        "{{NEXT_STEPS_HTML}}": render_next_steps(data["next_steps"]),
        "{{ACCEPT_RADIOS_HTML}}": render_accept_radios(ctx, data["options"], pricing, rec),

        "{{FRICTION_FLOW_HTML}}": render_friction_flow(ctx, appendix["friction_matrix"]),
        "{{FRICTION_ROWS_HTML}}": render_friction_rows(appendix["friction_matrix"]),
        "{{TARGET_STATE_HTML}}": render_target_state(ctx, appendix["target_state"]),
        "{{AWS_FOOTPRINT_STACK_HTML}}": render_aws_stack(ctx, appendix["aws_footprint"]),
        "{{AWS_FUNDING_APPENDIX_HTML}}": render_aws_funding_appendix(ctx, data.get("aws_funding_details"), path_totals(pricing, "a")),

        "{{TRACKING_WEBHOOK_URL}}": data["tracking_webhook_url"],
    }
    rep.update(render_vec_flags(focus))

    # Longest tokens first is unnecessary (all tokens are unique), but loop once.
    for token, value in rep.items():
        template = template.replace(token, value)

    leftover = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", template)))
    if leftover:
        raise SystemExit(f"Unfilled template tokens: {', '.join(leftover)}")
    return template


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_file", help="Path to a proposal JSON brief")
    ap.add_argument("--out", help="Output path (defaults to output/<slug>.html)")
    args = ap.parse_args()

    data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
    html = build(data)

    out_path = Path(args.out) if args.out else Path("output") / f'{data["proposal_slug"]}.html'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}  ({len(html):,} bytes)")
    for w in WARNINGS:
        print(f"WARNING: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
