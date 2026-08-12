# TODO

| ID | Priority | Duration | Input | Prereqs | Description |
|---|---|---|---|---|---|
| P1 | 1.1 | 10 min | Auto | quota reset | **Verify the text-artefact fix end to end.** `strip_text_artefacts()` is unit-tested against the real failing string, but has never been proven on a live chain: the verification probe died at frame 5 on a Gemini 429. Re-run `probe.yml` with 18 frames and grep every description in `probe.json` for text/lettering/watermark words - there should be none. A scheduled task (`photocopy-probe-rerun`) is set for 14/08/2026 08:00 AEST to do exactly this. |
| P2 | 1.2 | 20 min | Charlie | - | **Give Photocopy its own Google Cloud project for the Gemini key.** The free tier emptied at roughly 25 image calls on 12/08/2026, and the key may be shared with The Aftertimes. One afternoon of probing cost the chain a day's frame. A separate project means a separate daily quota, so research runs cannot starve the daily job. |
| P3 | 2.1 | 15 min | Auto | P1 | **Decide whether the drawer needs a text fix too, or only the describer.** The describer side is closed. The image model still renders lettering occasionally on its own (frame 17 of the first probe, unprompted). That is harmless now it cannot reach a description, but if it becomes frequent the options are a stronger negative, a different model, or cropping a band the way The Aftertimes does. Only act if P1 shows it recurring. |
| P4 | 2.2 | 5 min | Auto | - | **Frames 1 and 2 share a date (2026-08-12).** Historical artefact of two manual dispatches on day one, before `chain.filed_on()` existed. Harmless and only visible in the data. Leave it unless the duplicate date ever confuses the viewer. |
| P5 | 3.1 | 10 min | Auto | - | **Bricolage Grotesque was never evaluated.** It failed to download from Google Fonts during the specimen build, so it is the one shortlisted face Charlie never saw. Only worth revisiting if Silkscreen is ever reconsidered. |

## Notes

**Quota.** One Gemini vision call per frame. Daily ceiling, not a rate limit - measured at
about 4.5 requests a minute when it emptied. The free day rolls over at midnight Pacific
(07:00 UTC), NOT midnight in Sydney, so an afternoon probe can starve that evening's real
frame. Never run the probe before the day's frame has filed.

**Do not add an automatic reset.** Considered and cut deliberately - see
[docs/collapse.md](collapse.md). If the chain locks onto one image, that is the result.
