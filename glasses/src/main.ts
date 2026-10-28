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
const FILES = ['meta', 'today', 'radar', 'learn', 'people', 'tools', 'debates', 'defense', 'weekly', 'map', 'learn_archive']
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
  try {
    const ctl = new AbortController()
    const timer = setTimeout(() => ctl.abort(), 15000)
    const r = await fetch(`${DATA_BASE}/${name}.json?t=${Date.now()}`, { signal: ctl.signal })
    clearTimeout(timer)
    if (!r.ok) throw new Error(String(r.status))
    const j = await r.json()
    // Keep the offline copy small: the quiz archive only needs recent cards.
    const toStore = name === 'learn_archive' ? (j as any[]).slice(-250).map((l) => ({ id: l.id, term: l.term, quiz: l.quiz })) : j
    await kvSet('cache_' + name, JSON.stringify(toStore))
    return j
  } catch {
    const c = await kvGet('cache_' + name)
    try { return c ? JSON.parse(c) : null } catch { return null }
  }
}

/* -------------------------------------------------------------- deck builders */
const L = (label: string, v: unknown) => (v ? `${label}${v}` : '')

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
    }
    decks.push({ name: 'today', label: 'Today', cards })
  }

  const radar = d.radar
  if (radar?.items?.length || radar?.events?.length) {
    const cards: string[][] = []
    for (const e of radar.events || []) cards.push(paginate([`${e.kind.toUpperCase()} in ${e.days_left} days`, e.name, e.date, e.note]))
    for (const i of radar.items || []) {
      cards.push([
        ...paginate([`[${String(i.category).toUpperCase()}]${i.urgency >= 3 ? ' !!' : ''}`, i.title, '', i.one_liner]),
        ...paginate(['WHY IT MATTERS', i.why, '', `${i.source || ''} ${i.date || ''}`.trim(), '(headline only)']),
      ])
    }
    decks.push({ name: 'radar', label: 'Radar', cards })
  }

  const learn = d.learn
  if (learn?.lessons?.length) {
    decks.push({
      name: 'learn',
      label: 'Learn',
      cards: learn.lessons.map((l: any) => [
        ...paginate([l.term.toUpperCase(), '', l.definition]),
        ...paginate([l.plain]),
        ...paginate(['EXAMPLE', l.example, '', L('Links to: ', l.connects)]),
      ]),
    })
  }

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
      ]],
    })
  }

  if (d.weekly) {
    const w = d.weekly
    decks.push({
      name: 'weekly',
      label: 'Week',
      cards: [[
        ...paginate(['WEEK ' + w.week, ...(w.themes || []).map((t: string) => '- ' + t)]),
        ...paginate(['STUDIED', w.learned, '', 'NEXT', ...(w.next || []).map((n: string) => '- ' + n)]),
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
  rdeck = cards.filter((c) => !srs[c.id] || srs[c.id].due <= now).slice(0, 10)
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
  const lines = menu.map((m, i) => `${i === menuIdx ? '> ' : '  '}${m.label}`)
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
  xPosition: 0, yPosition: 40, width: 576, height: 248,
  borderWidth: 0, borderColor: 5, paddingLength: 4,
  containerID: 2, containerName: 'body', content: 'Loading your digest...', isEventCapture: 1,
})
const created = await bridge.createStartUpPageContainer(
  new CreateStartUpPageContainer({ containerTotalNum: 2, textObject: [hdr, body] }),
)
if (created !== 0) console.error('createStartUpPageContainer failed:', created)

bridge.onEvenHubEvent((event) => {
  const t = event.textEvent
  if (!t) return
  const type = t.eventType
  if (type === OsEventTypeList.DOUBLE_CLICK_EVENT) {
    if (mode === 'menu') void bridge.shutDownPageContainer(1) // root page: system exit dialog (required)
    else mode = 'menu'
  } else if (type === OsEventTypeList.SCROLL_BOTTOM_EVENT) {
    INVERT_SWIPE ? prev() : next()
  } else if (type === OsEventTypeList.SCROLL_TOP_EVENT) {
    INVERT_SWIPE ? next() : prev()
  } else if (type === OsEventTypeList.CLICK_EVENT || type === undefined) {
    click()
  } else return
  render()
})

const loaded: Record<string, any> = {}
await Promise.all(FILES.map(async (n) => { loaded[n] = await fetchJson(n) }))
try { srs = JSON.parse((await kvGet('srs')) || '{}') } catch { srs = {} }
meta = loaded.meta
decks = buildDecks(loaded)
buildRecall(loaded.learn_archive)

const order = ['today', 'radar', 'learn', 'recall', 'people', 'tools', 'debates', 'defense', 'map', 'weekly']
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
} else render()
