# DD proposal system, v4 (advisory-led narrative)

A locked HTML template, a JSON brief and a small generator script produce one
shareable proposal page per client. The page now reads like the proposals you
actually send (Qrida, Activus, 5Fold) and leads with DD's advisory options.
The AWS and architecture detail sits in a collapsible appendix.

## What changed from v3

v3 mirrored the internal T-05 form: nine tabs, mostly current-state and
architecture. v4 follows the story arc the three sent decks share:

| Chapter | What the client sees |
|---|---|
| Cover | Title, prepared for/by, validity, LEAD / DESIGN / BUILD chips lit for what applies |
| 01 Understanding | Their situation in plain English, an optional quote from the discovery call, four challenge cards, an indicative readiness snapshot |
| 02 The shift | Today vs With DD |
| 03 Our approach | The Transformation Triangle (LEAD, DESIGN, BUILD) and the 4-stage operating system, with the in-scope stages lit |
| 04 Your options | Path A / B / C ladder with a recommended start, price and duration on each, "Choose this option" buttons, and four ways to extend (fractional CIO/CTO/PMO, ADKAR change, ISO 42001 governance, buy-vs-build sprint) |
| 05 Plan | Stage-by-stage deliverables for the recommended option and a chevron timeline drawn to scale |
| 06 Success | Targets to baseline, plus one sign-off gate per stage |
| 07 Investment | To-scale cost bars, the T-05 line-by-line table, the 48-hour approval, data-readiness and scope-discipline terms, assumptions |
| 08 Why DD | The thesis, credentials in brand order, three case studies from the approved library, the named team |
| 09 Next steps | Four numbered steps and the accept panel (the client picks a preferred option) |
| Appendix | Friction map, target-state requirements, indicative AWS footprint, AWS funding admin details (Path A only) |

## Files

- `proposal-template.html` is the locked master. Edit it for structure and brand. Static brand copy lives here (the Triangle, TOS descriptions, credentials, delivery guardrails).
- `sample-proposal-data.json` is the brief for one client: the only file a person (or Claude) fills in per deal. It holds prose, hours, rates, percentages and week counts, never finished totals.
- `case-studies.json` is DD's approved case-study library from the Master Capability doc. A brief picks entries by id (`case_study_ids`). Edit it once and every future proposal benefits.
- `generate_proposal.py` combines them with the standard library only. It computes every dollar figure, bar width, chevron width and meter segment, validates icons and case-study ids, and refuses to write a page with an unfilled token.
- `to_artifact_fragment.py` converts a generated page into the format the Claude Artifact tool publishes. It is used only for the live prototype link.
- `assets/` holds the DD compass and lockup as base64 PNGs, spliced in at generation time.

Run it:

```
python3 generate_proposal.py sample-proposal-data.json --out sample-proposal-generated.html
```

## Filling in a new brief

1. Copy `sample-proposal-data.json`. Change `client_name`, `proposal_slug`, dates and contact details.
2. Set `recommended_path` (a, b or c), `vectors_in_focus` (lead, design, build) and `stages_in_scope` (1 to 4). These drive the cover chips, the highlighted triangle cards and the lit chevrons.
3. Draft the prose: `understanding`, `vision`, the three `options`, `plan.stage_deliverables`, `plan.timeline`, `success`.
4. Enter pricing as hours, rate, percentages and `tier_fee`. Never type a finished total.
5. Pick `case_study_ids` from `case-studies.json`.
6. Run the generator. It prints warnings if the timeline weeks disagree with the path's `duration_label`, or if the stages in scope disagree with the recommended option.

Optional blocks: delete `client_quote` if you have no real words from a discovery call (the sample quote is illustrative). Delete `aws_funding_details` for a non-AWS-funded engagement and the appendix section disappears.

## Brand and wording rules built in

- AWS funding is always phrased as "positioned to apply for" and "if approved". The page never says guaranteed or funded.
- No bare multipliers appear in generated copy. The only multiplier in the library is the USG TradeFlow result, attributed to that engagement.
- Credentials appear in brand order: PMP, Prosci/ADKAR, ISO 42001, AWS, HubSpot.
- Public references use ddconsult.com.au. The ddconsult.tech address appears only as the contact email.
- One-time professional fees are shown separately from ongoing AWS, API and licence costs.
- Not-for-profit clients: apply the standing 40% NFP rate adjustment in your hours and rate inputs and say so in `investment_note`.

## Accept vs sign

"Accept proposal" is the soft, informal go-ahead. It records a name and the preferred path and logs an `accepted` event. The binding contract is the separate services agreement, as before.

## What the live page tracks

`opened`, `section_view` (a chapter counts only after about 1.2 seconds on screen, so scrolling past does not inflate it), `option_interest` (which option they clicked), `appendix_opened`, `accept_clicked` and `accepted` (with the chosen path). The events post to `tracking_webhook_url`. The sample URL is a placeholder, so nothing is recorded until you point it at a real endpoint.

## Still to build (the Emergent piece)

- Hosting with a unique unlisted link per proposal, for example `proposals.ddconsult.com.au/{proposal_slug}/`.
- The tracking endpoint: receive the small JSON payload and write it to the matching HubSpot deal.
- A trigger that produces the JSON brief (a form, an automation off a finalised Doc, or Claude assembling it from a HubSpot deal) and calls the generator.
- Optional: a "Download PDF" export for clients who want a file.

## Notes on content

- The sample client (Meridian Health Group) is fictional. v3's invented fintech case study is gone; every case study now comes from the approved library.
- The readiness snapshot still uses the three T-05 dimensions on the 1 to 5 scale. Stage 1 delivers the full seven-pillar scorecard.
- Signal Blue uses `#4A90E2` as the fix for the guide's invalid `#4A9E2`. Please correct it in the brand guide itself.
- Sent proposals use two looks (Activus: beige and bronze; Qrida and 5Fold: navy infographic). v4 follows the brand guide palette with dark infographic panels. If you want it closer to one of the two, that is a CSS-only change.
