# Field Mastery

A free, automatic study-and-news assistant for your PhD field, readable on your Even G2 glasses and on your phone.

Every day it finds new papers, explains them in simple language, tracks regulations / funding / conferences, teaches you two small concepts, quizzes you, introduces a researcher of the week, follows software releases, argues one open debate per week, and asks you one likely defense question.

**Cost: 0.** GitHub (hosting and daily schedule), Google Gemini free tier (AI), OpenAlex free key (papers).

## What you get

| Section | What it shows |
|---|---|
| Today | New papers: headline, 3 bullets, "in plain words", full explainer with limits and jargon |
| Radar | Regulation, policy, funding, conference news (headline-level) + your deadline countdowns |
| Learn | 2 micro-lessons a day (definition, plain explanation, example, connections) |
| Recall | Spaced-repetition quiz from everything you have learned |
| People | Researcher of the week, chosen from real citation data |
| Tools | New releases of software you follow |
| Debates | One open debate a week, argued only from highly cited papers |
| Defense | One likely committee question a day, with an answer outline |
| Map | Lessons per knowledge area + your quiz mastery (phone only) |
| Week | Sunday review of the week |

## Setup (about 30 minutes, once)

### 1. Free accounts and keys
1. **GitHub**: create an account at github.com.
2. **Gemini key**: go to aistudio.google.com, sign in, "Get API key" > create. Copy it.
3. **OpenAlex key**: create an account at openalex.org, copy your key from openalex.org/settings/api.

### 2. Put the project on GitHub
1. Create a new **public** repository (public is required for free hosting).
2. Upload all files of this folder (drag and drop works, keep the folder structure; make sure the hidden `.github` folder is included).
3. In the repo: **Settings > Secrets and variables > Actions > New repository secret**. Add two secrets:
   - `GEMINI_API_KEY` = your Gemini key
   - `OPENALEX_API_KEY` = your OpenAlex key
4. **Settings > Pages**: Source = "Deploy from a branch", Branch = `main`, Folder = `/docs`. Save.
5. **Settings > Actions > General > Workflow permissions**: choose "Read and write permissions".

### 3. Make it yours
Edit `config.yaml` (on GitHub, click the file, then the pencil icon):
- `research_question` and `keywords`: your field.
- `papers.watch_journals`, `papers.key_references` (DOIs of papers central to your thesis).
- `radar.events`: conferences and deadlines you know.
- `tools.github_repos`: software you use.
- `defense`: keep it generic (see Privacy), or `enabled: false`.

### 4. First run
**Actions** tab > "Daily digest" > **Run workflow**. It takes 5 to 15 minutes (the free AI limits how fast it can go). When it finishes, open `https://YOUR-USERNAME.github.io/YOUR-REPO/` on your phone. Add it to your home screen if you like.
From then on it runs by itself every day at 04:30 UTC.

### 5. Glasses app
You need a computer with Node.js 20+ once (nodejs.org), plus the Even Realities developer account (hub.evenrealities.com, same login as your phone app, then restart the phone app so developer mode appears).

```bash
node setup.mjs YOUR-USERNAME YOUR-REPO     # fills in your address (run in the project root)
cd glasses
npm install
npm run dev                                 # in a second terminal: evenhub-simulator http://localhost:5173
```
To try it on the real glasses: install the Even Hub tooling per the Even docs, then `evenhub qr --url "http://<your-computer-LAN-IP>:5173"` and scan the QR with the Even Realities app (Scan QR).
To keep it permanently on your glasses without your computer: `npm run build`, then `evenhub pack app.json dist` and upload the resulting file as a **private build** in the developer portal (no store review needed).

**Controls on the glasses:** swipe down = next page, swipe up = previous page, tap = next card (skips the detail pages), double-tap = back to menu, double-tap on the menu = exit. In Recall: tap shows the answer, swipe down = "got it", swipe up = "again". If swiping feels reversed, set `INVERT_SWIPE = true` in `glasses/src/config.ts`.

## Honest limits
- **The glasses app has not been run on real glasses yet.** Its logic was tested against a stand-in for the Even SDK, and the SDK could not be installed in the build environment. Expect to adjust small things (page length `PAGE_CHARS`, swipe direction) on first use.
- **Papers are explained from the title and abstract only**, not the full text. Each card says so. Check the original for anything central to your thesis.
- **AI can misread a paper.** Radar items are based on headlines only. Learn lessons are generated from general knowledge: use them to orient, then verify with the "find sources" link. People and Debates are grounded in OpenAlex data and cite only the papers they were given.
- **Free limits change.** Google and OpenAlex may change free quotas or model names. If a model is retired, change `llm.model` in `config.yaml`. If a section fails, the apps keep showing the last good data and the phone page says which section failed.
- **GitHub pauses scheduled runs** in public repos after about 60 days without activity by you. If the digest stops, open the Actions tab and re-enable the workflow.
- **Recall progress and saved papers are stored on the device** (phone browser and glasses separately).

## Privacy
- The repository and the website are **public**. Do not put anything confidential in `config.yaml`.
- On Google's free tier, prompts may be used to improve their models. The pipeline only sends public paper abstracts, headlines, release notes and the text in `config.yaml` (research question, and the `defense` section if you fill it in). Defense questions also appear on your public page.
- Want it private? Cloudflare Pages (free) can host a private repository, but needs a different setup.

## Testing without keys
`python -m pipeline.build_digest --mock` fills `docs/data` with clearly labelled sample data. The shipped `docs/data` is such sample data; your first real run deletes it.
