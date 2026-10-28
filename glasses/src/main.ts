import {
  waitForEvenAppBridge,
  TextContainerProperty,
  TextContainerUpgrade,
  CreateStartUpPageContainer,
  OsEventTypeList,
} from '@evenrealities/even_hub_sdk'
import { DATA_BASE, INVERT_SWIPE, PAGE_CHARS } from './config'

/* ------------------------------------------------------------------ types */
type Deck = { name: string; label: string; cards: string[][] } // each card = list of glasses pages
type Srs = Record<string, { box: number; due: number }>
type RCard = { id: string; term: string; q: string; a: string }

/* ------------------------------------------------------------ text helpers */
// The G2 font only has some glyphs; anything else is silently dropped, so we normalise to plain ASCII.
function safe(s: unknown): string {
  return String(s ?? '')
    .replace(/[‘’‚]/g, "'")
    .replace(/[“”„]/g, '"')
    .replace(/[–—−]/g, '-')
    .replace(/…/g, '...')
    .replace(/ /g, ' ')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\x20-\x7E\n]/g, '')
}

function splitLong(s: string, n: number): string[] {
  if (s.length <= n) return [s]
  const out: string[] = []
  let rest = s
  while (rest.length > n) {
    let cut = rest.lastIndexOf(' ', n)
    if (cut < n * 0.5) cut = n
    out.push(rest.slice(0, cut).trim())
    rest = rest.slice(cut).trim()
  }
  if (rest) out.push(rest)
  return out
}

function paginate(blocks: unknown[]): string[] {
  const pages: string[] = []
  let cur = ''
  for (const raw of blocks) {
    const b = safe(raw).trim()
    if (!b) {
      if (cur) cur += '\n'
      continue
    }
    for (const part of splitLong(b, PAGE_CHARS)) {
      if (cur && cur.length + part.length + 1 > PAGE_CHARS) {
        pages.push(cur.trim())
        cur = part
      } else cur = cur ? cur + '\n' + part : part
    }
  }
  if (cur.trim()) pages.push(cur.trim())
  return pages.length ? pages : ['(empty)']
}

/* ------------------------------------------------------------- data layer */
const FILES = ['meta', 'today', 'radar', 'learn', 'people', 'tools', 'debates', 'defense', 'weekly', 'map', 'learn_archive', 'briefing']
const fetchState: Record<string, string> = {}
const phoneTitle = document.querySelector<HTMLElement>('#screen-title')!
const phoneBody = document.querySelector<HTMLElement>('#screen-body')!
const phoneMenu = document.querySelector<HTMLElement>('#sections')!
const phoneStatus = document.querySelector<HTMLElement>('#status')!
const readerLink = document.querySelector<HTMLAnchorElement>('#reader-link')!
readerLink.href = DATA_BASE.replace(/\/data\/?$/, '/')
const bridge = await waitForEvenAppBridge()

async function kvGet(key: string): Promise<string | null> {
  try {
    const v = await bridge.getLocalStorage(key)
    return v ? String(v) : null
  } catch {
    try { return window.localStorage.getItem(key) } catch { return null }
  }
}
async function kvSet(key: string, value: string) {
  try { await bridge.setLocalStorage(key, value) } catch {
    try { window.localStorage.setItem(key, value) } catch { /* ignore */ }
  }
}

async function fetchJson(name: string): Promise<any | null> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 15000)
  try {
    const r = await fetch(`${DATA_BASE}/${name}.json?t=${Date.now()}`, { signal: ctl.signal })
    clearTimeout(timer)
    if (!r.ok) throw new Error(String(r.status))
    const j = await r.json()
    // Keep the offline copy small: the quiz archive only needs recent cards.
    const toStore = name === 'learn_archive' ? (j as any[]).slice(-250).map((l) => ({ id: l.id, term: l.term, quiz: l.quiz })) : j
    await kvSet('cache_' + name, JSON.stringify(toStore))
    fetchState[name] = 'online'
    return j
  } catch {
    const c = await kvGet('cache_' + name)
    fetchState[name] = c ? 'cached' : 'unavailable'
    try { return c ? JSON.parse(c) : null } catch { return null }
  } finally {
    clearTimeout(timer)
  }
}

/* -------------------------------------------------------------- deck builders */
const L = (label: string, v: unknown) => (v ? `${label}${v}` : '')
const STAGES: Record<string, string> = { proposal: 'Proposal', adopted: 'Adopted (check effective date)', in_force: 'In force (source report)', unknown: 'Unverified - check original', not_applicable: 'Not a legal update' }

function newsCard(item: any): string[] {
  return [
    ...paginate([`[${item.scope || 'World'} / ${item.category || 'news'}]`, item.title, item.one_liner]),
    ...paginate(['WHY IT MATTERS', item.why, '', 'SUGGESTED NEXT STEP', item.action || 'Open the source on your phone.']),
    ...paginate(['SOURCE', `${item.source || ''} ${item.date || ''}`, item.basis || 'headline only', '', STAGES[item.status || 'unknown'], item.status_evidence]),
  ]
}

function buildDecks(d: Record<string, any>): Deck[] {
  const decks: Deck[] = []

  const today = d.today
  if (today?.items?.length) {
    const cards: string[][] = []
    if (today.summary?.length) cards.push(paginate(['TODAY IN SHORT', '', ...today.summary.map((s: string) => '- ' + s)]))
    for (const p of today.items) {
      const glance = paginate([p.headline, '', ...(p.bullets || []).map((b: string) => '- ' + b), '', [p.source?.venue, p.source?.date].filter(Boolean).join(' | ')])
      const plain = [
        ...paginate(['IN PLAIN WORDS', L('Q: ', p.plain?.question), L('They did: ', p.plain?.method)]),
        ...paginate([L('Found: ', p.plain?.finding), L('So what: ', p.plain?.why)]),
      ]
      const fit = p.full?.fit ? paginate(['FIT WITH YOUR FIELD', p.full.fit, p.source?.open_access ? '(open access)' : '(maybe paywalled)']) : []
      cards.push([...glance, ...plain, ...fit])
      if (p.thesis?.why || p.thesis?.action) cards[cards.length - 1].push(...paginate(['YOUR PHD', p.thesis.why, '', 'NEXT STEP', p.thesis.action]))
      cards[cards.length - 1].push(...paginate(['SOURCE', `${p.source?.venue || ''} ${p.source?.date || ''}`, 'Based on title and abstract. Open original on phone.']))
    }
    decks.push({ name: 'today', label: 'Today', cards })
  }

  const radar = d.radar
  if (radar?.items?.length || radar?.events?.length) {
    const cards: string[][] = []
    for (const e of radar.events || []) cards.push(paginate([`${e.kind.toUpperCase()} in ${e.days_left} days`, e.name, e.date, e.note]))
    for (const i of radar.items || []) {
      cards.push(newsCard(i))
    }
    decks.push({ name: 'radar', label: 'Radar', cards })
  }
  if (!decks.some((deck) => deck.name === 'radar')) decks.push({ name: 'radar', label: 'Radar', cards: [['No news or deadlines available yet.\nSee Update status for errors.\nNo events are invented to fill this section.']] })
  for (const [name, label] of [['germany', 'Germany'], ['eu', 'EU']]) {
    const items = (radar?.items || []).filter((item: any) => item.scope === label)
    decks.push({ name, label, cards: items.length ? items.map(newsCard) : [[`No selected ${label} updates available.\nCheck Update status. Coverage is selective, not exhaustive.`]] })
  }
  const critical = (today?.items || []).filter((p: any) => p.critical?.question)
  decks.push({ name: 'challenges', label: 'Challenges', cards: critical.length ? critical.map((p: any) => [
    ...paginate(['EXAMINER CHALLENGE', p.critical.question]),
    ...paginate(['EVIDENCE FROM ABSTRACT', p.critical.evidence, '', 'LIMIT', p.critical.limit]),
    ...paginate(['CHECK THE FULL PAPER', p.critical.check, p.title, p.source?.date, 'Source link on phone. A question is not proof of contradiction.']),
  ]) : [['Challenges appear with newly generated paper summaries. They distinguish conflicting findings from questions and limitations.']] })

  const briefing = d.briefing
  const world = briefing?.world || []
  decks.push({ name: 'world', label: 'World week', cards: world.length ? world.map((item: any) => [
    ...paginate([`${item.region} | ${briefing.date}`, 'WHAT CHANGED', item.what]),
    ...paginate(['WHY IT MATTERS', item.why, '', 'NEXT STEP', item.action]),
    ...paginate(['SOURCE', item.source?.title, item.source?.date, item.source?.basis, '', briefing.coverage]),
  ]) : [['The world briefing appears after the next successful digest run. It uses collected sources and does not invent missing regional coverage.']] })
  const reading = briefing?.reading
  decks.push({ name: 'reading', label: 'Read this week', cards: reading ? [[
    ...paginate([`READ THIS WEEK | ${briefing.date}`, reading.title, '', reading.why]),
    ...paginate(['READ WITH THESE QUESTIONS', ...(reading.questions || [])]),
    ...paginate(['VERIFY IN FULL PAPER', reading.check, `${reading.source?.venue || ''} ${reading.source?.date || ''}`, 'Selection based on abstract; full text has not been reviewed. Link on phone.']),
  ]] : [['Your weekly reading pick appears when a paper is available.']] })

  const learn = d.learn
  if (learn?.lessons?.length) {
    decks.push({
      name: 'learn',
      label: 'Learn',
      cards: learn.lessons.map((l: any) => [
        ...paginate([l.term.toUpperCase(), '', l.definition]),
        ...paginate([l.plain]),
        ...paginate(['EXAMPLE', l.example, '', L('Links to: ', l.connects)]),
        ...paginate(['YOUR PHD', l.why_phd || l.connects, 'AI teaching explanation; source search on phone.']),
      ]),
    })
  }
  if (learn?.path) decks.push({ name: 'path', label: 'Learning path', cards: [[
    ...paginate([learn.path.stage, ...learn.path.stages, '', learn.path.note]),
    ...paginate(['COMING UP', ...learn.path.next_topics]),
  ]] })

  const p = d.people?.current
  if (p) {
    decks.push({
      name: 'people',
      label: 'People',
      cards: [[
        ...paginate([p.name, p.institution, '', p.headline, '', `${p.stats?.works ?? '?'} works, h-index ${p.stats?.h_index ?? '?'}`]),
        ...paginate(['KNOWN FOR', ...(p.known_for || []).map((k: string) => '- ' + k), '', p.why_follow]),
        ...(p.read_first?.length ? paginate(['READ FIRST', ...p.read_first.map((r: any) => `- ${r.title} (${r.year})`)]) : []),
      ]],
    })
  }

  if (d.tools?.items?.length) {
    decks.push({
      name: 'tools',
      label: 'Tools',
      cards: d.tools.items.slice(0, 10).map((t: any) => [
        ...paginate([`${t.name} ${t.version}`, t.date, '', t.summary]),
        ...paginate(['RELEVANCE', t.matters]),
      ]),
    })
  }

  const db = d.debates?.current
  if (db) {
    decks.push({
      name: 'debates',
      label: 'Debates',
      cards: [[
        ...paginate(['DEBATE', db.question]),
        ...paginate(['SIDE A: ' + db.side_a.claim, db.side_a.argument]),
        ...paginate(['SIDE B: ' + db.side_b.claim, db.side_b.argument]),
        ...paginate(['COMMON GROUND', db.middle, '', 'COMMITTEE MAY ASK', db.committee]),
      ]],
    })
  }

  const df = d.defense
  if (df?.enabled !== false && df?.today) {
    const q = df.today
    decks.push({
      name: 'defense',
      label: 'Defense',
      cards: [[
        ...paginate([`QUESTION (${q.type})`, '', q.q, '', 'Answer out loud, then swipe.']),
        ...paginate(['STRUCTURE', ...(q.outline || []).map((o: string) => '- ' + o)]),
        ...paginate(['PITFALL', q.pitfall]),
        ...paginate(['FOLLOW-UP QUESTION', q.follow_up || 'What evidence would change your answer?', '', 'BRING EVIDENCE', q.bring]),
        ...paginate(['SELF-CHECK', ...(q.self_check || []), '', df.basis || 'Practice based on configured study themes.']),
      ]],
    })
  }
  if (!d.weekly) decks.push({ name: 'weekly', label: 'Week', cards: [['No weekly review yet. The next successful digest creates an initial review, then refreshes it on Sundays.']] })

  const errors = d.meta?.errors || {}
  const cached = FILES.filter((file) => fetchState[file] === 'cached')
  decks.push({ name: 'status', label: 'Update status', cards: [
    paginate([`LAST DIGEST: ${d.meta?.generated_at || 'unknown'}`, d.meta?.sample ? 'SAMPLE DATA' : '',
      cached.length ? `Offline copies: ${cached.join(', ')}` : 'Online feed checked on opening.',
      ...Object.keys(errors).map((key) => `${key}: update failed; previous data may be shown.`),
      'Refresh from your phone, or close and reopen to check for new content.']),
    ...Object.entries(d.meta?.status || {}).map(([name, info]: [string, any]) => paginate([name.toUpperCase(), `State: ${info.state}`, `Content date: ${info.date || 'not supplied'}`, info.state === 'partial' ? 'Some news sources failed. Coverage is incomplete.' : '', info.error || ''])),
  ] })

  if (d.weekly) {
    const w = d.weekly
    decks.push({
      name: 'weekly',
      label: 'Week',
      cards: [[
        ...paginate(['WEEK ' + w.week, ...(w.themes || []).map((t: string) => '- ' + t)]),
        ...paginate(['INTRODUCED', w.learned, '', 'NEXT', ...(w.next || []).map((n: string) => '- ' + n)]),
      ]],
    })
  }

  if (d.map?.areas?.length) {
    const lines = d.map.areas.map((a: any) => `${a.name}: ${a.lessons}`)
    decks.push({ name: 'map', label: 'Map', cards: [paginate(['LESSONS PER AREA', ...lines])] })
  }
  return decks
}

/* --------------------------------------------------------------- recall (SRS) */
const GAP_DAYS = [0, 1, 2, 4, 8, 16, 32]
let srs: Srs = {}
let rdeck: RCard[] = []

function buildRecall(archive: any[] | null) {
  const cards: RCard[] = (archive || []).flatMap((l) => (l.quiz || []).map((q: any, i: number) => ({ id: `${l.id}:${i}`, term: l.term, q: q.q, a: q.a })))
  const now = Date.now()
  rdeck = cards.filter((c) => !srs[c.id] || srs[c.id].due <= now)
    .sort((a, b) => (srs[a.id]?.box ?? 2) - (srs[b.id]?.box ?? 2) || (srs[a.id]?.due ?? 0) - (srs[b.id]?.due ?? 0)).slice(0, 10)
}

/* ------------------------------------------------------------------ UI state */
type Mode = 'menu' | 'deck' | 'recall'
let mode: Mode = 'menu'
let decks: Deck[] = []
let menu: { key: string; label: string }[] = []
let menuIdx = 0
let deck: Deck | null = null
let ci = 0
let pi = 0
let ri = 0
let revealed = false
let meta: any = null

function menuText(): { head: string; body: string } {
  const head = safe(`FIELD MASTERY ${meta?.generated_at ?? ''}${meta?.sample ? ' SAMPLE' : ''}`)
  if (menu[0]?.key === 'none') return { head, body: 'No data yet.\nCheck your research website and daily update.\n\ndouble-tap: exit' }
  // Keep the selected row visible without firmware text scrolling.
  const start = Math.max(0, Math.min(menuIdx - 2, menu.length - 5))
  const lines = menu.slice(start, start + 5).map((m, i) => `${i + start === menuIdx ? '> ' : '  '}${m.label}`)
  return { head, body: lines.join('\n') + '\n\nswipe: move   tap: open' }
}

function view(): { head: string; body: string } {
  if (mode === 'menu') return menuText()
  if (mode === 'recall') {
    if (!rdeck.length) return { head: 'RECALL', body: 'Nothing due right now.\n\ndouble-tap: menu' }
    if (ri >= rdeck.length) return { head: 'RECALL DONE', body: `Reviewed ${rdeck.length} cards.\n\ndouble-tap: menu` }
    const c = rdeck[ri]
    return revealed
      ? { head: safe(`RECALL ${ri + 1}/${rdeck.length} ANSWER`), body: paginate([c.a, '', 'swipe down: got it', 'swipe up: again'])[0] }
      : { head: safe(`RECALL ${ri + 1}/${rdeck.length} ${c.term}`.slice(0, 50)), body: paginate([c.q, '', 'tap: show answer'])[0] }
  }
  const cards = deck!.cards
  const pages = cards[ci]
  return {
    head: safe(`${deck!.label.toUpperCase()} ${ci + 1}/${cards.length}  p${pi + 1}/${pages.length}`),
    body: pages[pi],
  }
}

let busy: Promise<unknown> = Promise.resolve()
function render() {
  const v = view()
  phoneTitle.textContent = v.head
  phoneBody.textContent = v.body
  phoneMenu.replaceChildren(...menu.map((item, index) => {
    const button = document.createElement('button')
    button.textContent = item.label
    button.addEventListener('click', () => {
      menuIdx = index
      openMenuItem()
      render()
    })
    return button
  }))
  busy = busy.then(async () => {
    await bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: 1, containerName: 'hdr', content: v.head }))
    await bridge.textContainerUpgrade(new TextContainerUpgrade({ containerID: 2, containerName: 'body', content: v.body }))
  }).catch(() => { /* a dropped frame is not fatal */ })
}

/* ---------------------------------------------------------------- navigation */
function openMenuItem() {
  const m = menu[menuIdx]
  if (m.key === 'recall') {
    mode = 'recall'
    ri = 0
    revealed = false
  } else {
    deck = decks.find((d) => d.name === m.key) || null
    if (!deck) return
    mode = 'deck'
    ci = 0
    pi = 0
  }
}

function rate(ok: boolean) {
  const c = rdeck[ri]
  const box = ok ? Math.min(6, (srs[c.id]?.box ?? 0) + 1) : 1
  srs[c.id] = { box, due: Date.now() + GAP_DAYS[box] * 86_400_000 }
  void kvSet('srs', JSON.stringify(srs))
  ri += 1
  revealed = false
}

function next() {
  if (mode === 'menu') menuIdx = (menuIdx + 1) % menu.length
  else if (mode === 'deck') {
    const pages = deck!.cards[ci]
    if (pi < pages.length - 1) pi += 1
    else if (ci < deck!.cards.length - 1) { ci += 1; pi = 0 }
  } else if (mode === 'recall' && revealed && ri < rdeck.length) rate(true)
}
function prev() {
  if (mode === 'menu') menuIdx = (menuIdx - 1 + menu.length) % menu.length
  else if (mode === 'deck') {
    if (pi > 0) pi -= 1
    else if (ci > 0) { ci -= 1; pi = deck!.cards[ci].length - 1 }
  } else if (mode === 'recall' && revealed && ri < rdeck.length) rate(false)
}
function click() {
  if (mode === 'menu') openMenuItem()
  else if (mode === 'deck') { if (ci < deck!.cards.length - 1) { ci += 1; pi = 0 } else { ci = 0; pi = 0 } }
  else if (mode === 'recall' && ri < rdeck.length) revealed = true
}

/* --------------------------------------------------------------------- start */
// Show a loading screen immediately; the real content arrives after the downloads.
const hdr = new TextContainerProperty({
  xPosition: 0, yPosition: 0, width: 576, height: 40,
  borderWidth: 0, borderColor: 5, paddingLength: 4,
  containerID: 1, containerName: 'hdr', content: 'FIELD MASTERY', isEventCapture: 0,
})
const body = new TextContainerProperty({
  xPosition: 0, yPosition: 40, width: 576, height: 247,
  borderWidth: 0, borderColor: 5, paddingLength: 4,
  containerID: 2, containerName: 'body', content: 'Loading your digest...', isEventCapture: 0,
})
// Capture swipes in an empty container. A text-filled capture container first
// consumes gestures to scroll its own content before emitting boundary events.
const input = new TextContainerProperty({
  xPosition: 0, yPosition: 287, width: 1, height: 1,
  borderWidth: 0, paddingLength: 0,
  containerID: 3, containerName: 'input', content: ' ', isEventCapture: 1,
})
const created = await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({ containerTotalNum: 3, textObject: [hdr, body, input] }),
)
if (created !== 0) console.error('createStartUpPageContainer failed:', created)

function eventTypeOf(envelope?: { eventType?: OsEventTypeList }): OsEventTypeList | null {
  // Protobuf omits CLICK_EVENT (zero), but a missing envelope is not a tap.
  return envelope ? envelope.eventType ?? OsEventTypeList.CLICK_EVENT : null
}

bridge.onEvenHubEvent((event) => {
  const sysType = eventTypeOf(event.sysEvent)
  const textType = eventTypeOf(event.textEvent)
  if (sysType === OsEventTypeList.DOUBLE_CLICK_EVENT || textType === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    if (mode === 'menu') void bridge.shutDownPageContainer(1) // root page: system exit dialog (required)
    else mode = 'menu'
  } else if (!menu.length) return
  else if (textType === OsEventTypeList.SCROLL_BOTTOM_EVENT) {
    INVERT_SWIPE ? prev() : next()
  } else if (textType === OsEventTypeList.SCROLL_TOP_EVENT) {
    INVERT_SWIPE ? next() : prev()
  } else if (sysType === OsEventTypeList.CLICK_EVENT || textType === OsEventTypeList.CLICK_EVENT) {
    click()
  } else return
  render()
})

const loaded: Record<string, any> = {}
async function refreshData() {
phoneStatus.textContent = 'Checking for new content…'
await Promise.all(FILES.map(async (n) => { loaded[n] = await fetchJson(n) }))
try { srs = JSON.parse((await kvGet('srs')) || '{}') } catch { srs = {} }
meta = loaded.meta
decks = buildDecks(loaded)
buildRecall(loaded.learn_archive)

const order = ['today', 'germany', 'eu', 'radar', 'learn', 'recall', 'challenges', 'defense', 'world', 'reading', 'path', 'people', 'tools', 'debates', 'map', 'weekly', 'status']
const labels: Record<string, string> = {}
for (const d of decks) labels[d.name] = `${d.label} (${d.cards.length})`
if (rdeck.length) labels.recall = `Recall (${rdeck.length} due)`
menu = order.filter((k) => labels[k]).map((k) => ({ key: k, label: labels[k] }))
if (!menu.length) {
  await bridge.textContainerUpgrade(new TextContainerUpgrade({
    containerID: 2, containerName: 'body',
    content: 'No data yet.\nCheck DATA_BASE in config.ts and that the daily workflow has run.\n\ndouble-tap: exit',
  }))
  menu = [{ key: 'none', label: 'No data' }]
}
mode = 'menu'
menuIdx = 0
const cached = FILES.some((file) => fetchState[file] === 'cached')
phoneStatus.textContent = created !== 0 ? 'Glasses connection needs attention' : cached ? 'Using some saved content — see Update status' : 'Connected to your glasses'
render()
}
await refreshData()
document.querySelector<HTMLButtonElement>('#refresh')!.addEventListener('click', async () => {
  const button = document.querySelector<HTMLButtonElement>('#refresh')!
  button.disabled = true
  try { await refreshData() } finally { button.disabled = false }
})
for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>('[data-action]'))) {
  button.disabled = false
  button.addEventListener('click', () => {
    switch (button.dataset.action) {
      case 'previous': prev(); break
      case 'next': next(); break
      case 'tap': click(); break
      case 'menu': mode = 'menu'; break
    }
    render()
  })
}
render()
