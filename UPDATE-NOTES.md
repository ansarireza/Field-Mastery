# Field Mastery 0.2.0

This update keeps the existing website address, API secrets, schedule and quiz
storage keys. It changes the content generator, phone reader and glasses app.

## New features

- Germany and EU news sections, with official environmental agency feeds plus
  regional searches alongside worldwide sources. Cards explain what changed,
  research relevance and a suggested next step. Legal stages require a matching
  quote from an official feed excerpt; otherwise status is unverified.
- A weekly worldwide briefing and one paper to read closely, including reading
  questions and original source links. Coverage follows the collected sources;
  it is not a complete worldwide news service.
- New paper summaries connect to the configured research question and methods.
  Challenges distinguish an examiner question from evidence of a contradiction.
- Defence practice includes a tougher follow-up, evidence to bring and a spoken
  answer checklist. It uses the public study themes in config.yaml, not a review
  of a complete thesis or unpublished results.
- A learning path moves from foundations to comparison and critical appraisal.
  Each day mixes a curriculum lesson with vocabulary from current papers.
  Recall prioritises due questions at the lowest review levels. Phone and glasses
  quiz progress remain separate and are not uploaded to GitHub.
- Dates, offline-copy notices, per-section update status, and a Refresh content
  button. Missing news or weekly content has an explanation instead of silently
  disappearing from the glasses menu.
- A first partial weekly review is generated on initial setup, then on Sundays.
- The daily workflow explicitly requests a website rebuild after saving data.

## Applying this update

Only changed source files need updating on GitHub. Do not replace docs/data or
state with local sample files; the daily workflow owns the live research data.
No new API secrets or account setup are needed.

1. Publish the prepared Git commit to the existing main branch.
2. On GitHub open Actions -> Daily digest -> Run workflow -> main -> Run workflow.
3. Wait for Daily digest and the subsequent Pages publication to finish.
4. Install/update Field Mastery 0.2.0 from the existing Even beta installation.
5. Open the app and choose Refresh content. Newly generated paper summaries
   contain the new thesis and challenge fields; older cached papers may not.

The glasses package is built and tested with mocked G2/R1 event envelopes. Real
device verification of the new screens is still needed. No real Gemini run has
been made locally because API secrets remain in the user's GitHub account.

## Validation

- Python regression tests cover legal-status evidence, source integrity,
  regional interleaving, feed outages, initial weekly reviews, reading selection,
  JSON response recovery and an isolated full mock digest.
- Glasses regression tests cover temple/ring taps, swipes, empty input capture,
  new sections, offline status, refresh and quiz persistence.
- All phone sections were exercised in a browser with no console errors; the
  Germany card was visually checked at a 390 px phone width.

## Source subscriptions

- https://www.bfn.de/pressemitteilungen
- https://www.umweltbundesamt.de/presse
- https://environment.ec.europa.eu/news_en

These are monitoring inputs. A short feed excerpt is not a full legal document,
and an abstract-based research explanation is not a full-paper review.
