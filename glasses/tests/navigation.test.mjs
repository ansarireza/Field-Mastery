import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

// Exercise the actual app entry point with the event envelopes sent by G2/R1.
class Element {
  textContent = ''
  children = []
  listeners = {}
  disabled = true
  dataset = {}
  addEventListener(name, callback) { this.listeners[name] = callback }
  replaceChildren(...children) { this.children = children }
  click() { return this.listeners.click?.() }
}

async function start({ overrides = {}, offline = [], storage = {} } = {}) {
  const nodes = Object.fromEntries(['screen-title', 'screen-body', 'sections', 'status', 'reader-link', 'refresh'].map(id => [id, new Element()]))
  const controls = ['previous', 'next', 'tap', 'menu'].map(action => {
    const element = new Element()
    element.dataset.action = action
    return element
  })
  const data = {
    meta: { generated_at: '2026-10-28' },
    today: { items: [{ headline: 'Paper one' }, { headline: 'Paper two' }] },
    radar: { items: [{ category: 'news', title: 'News' }] },
    learn: { lessons: [{ term: 'Lesson', definition: 'Definition', plain: 'Explanation' }] },
    tools: { items: [{ name: 'Tool', version: '1', summary: 'Update' }] },
    weekly: { week: '44' },
    map: { areas: [{ name: 'Topic', lessons: 1 }] },
    learn_archive: [{ id: 'lesson', term: 'Lesson', quiz: [{ q: 'Question?', a: 'Answer' }] }],
    ...overrides,
  }
  let handler, page
  const upgrades = []
  let exits = 0
  const bridge = {
    getLocalStorage: async key => storage[key] || null,
    setLocalStorage: async (key, value) => { storage[key] = value },
    createStartUpPageContainer: async value => { page = value; return 0 },
    textContainerUpgrade: async value => { upgrades.push(value) },
    onEvenHubEvent: callback => { handler = callback },
    shutDownPageContainer: async () => { exits++ },
  }
  const context = vm.createContext({
    console, setTimeout, clearTimeout, AbortController,
    document: {
      querySelector: selector => nodes[selector.slice(1)],
      querySelectorAll: () => controls,
      createElement: () => new Element(),
    },
    window: { localStorage: { getItem: () => null, setItem: () => {} } },
    fetch: async url => {
      const name = new URL(url).pathname.split('/').pop().replace('.json', '')
      if (offline.includes(name)) throw new Error('offline')
      return { ok: !!data[name], status: 404, json: async () => data[name] }
    },
  })
  const sdkNames = ['waitForEvenAppBridge', 'TextContainerProperty', 'TextContainerUpgrade', 'CreateStartUpPageContainer', 'OsEventTypeList']
  const sdk = new vm.SyntheticModule(sdkNames, function () {
    this.setExport('waitForEvenAppBridge', async () => bridge)
    for (const name of sdkNames.slice(1, 4)) this.setExport(name, class { constructor(value) { Object.assign(this, value) } })
    this.setExport('OsEventTypeList', { CLICK_EVENT: 0, SCROLL_TOP_EVENT: 1, SCROLL_BOTTOM_EVENT: 2, DOUBLE_CLICK_EVENT: 3 })
  }, { context })
  const config = new vm.SyntheticModule(['DATA_BASE', 'INVERT_SWIPE', 'PAGE_CHARS'], function () {
    this.setExport('DATA_BASE', 'https://ansarireza.github.io/Field-Mastery/data')
    this.setExport('INVERT_SWIPE', false)
    this.setExport('PAGE_CHARS', 300)
  }, { context })
  const source = await readFile(new URL('../src/main.ts', import.meta.url), 'utf8')
  const js = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  const app = new vm.SourceTextModule(js, { context })
  await app.link(specifier => specifier === './config' ? config : sdk)
  await app.evaluate()
  const flush = () => new Promise(resolve => setImmediate(resolve))
  await flush()
  return {
    nodes, controls, page, upgrades,
    storage,
    emit: async event => { handler(event); await flush() },
    flush,
    exits: () => exits,
  }
}

test('G2 and ring taps open sections; lifecycle and audio events do not act as taps', async () => {
  const app = await start()
  assert.match(app.nodes['screen-body'].textContent, /> Today/)
  await app.emit({ sysEvent: { eventType: 4 } })
  await app.emit({ audioEvent: { audioPcm: [] } })
  assert.match(app.nodes['screen-body'].textContent, /> Today/)
  await app.emit({ sysEvent: { eventSource: 1 } })
  assert.match(app.nodes['screen-title'].textContent, /TODAY 1\/2/)
  await app.emit({ sysEvent: { eventSource: 2, eventType: 0 } })
  assert.match(app.nodes['screen-title'].textContent, /TODAY 2\/2/)
  await app.emit({ sysEvent: { eventType: 3 } })
  assert.match(app.nodes['screen-body'].textContent, /> Today/)
  await app.emit({ sysEvent: { eventType: 3 } })
  assert.equal(app.exits(), 1)
})

test('one scroll event moves one row; selected rows remain visible; capture text is empty', async () => {
  const app = await start()
  const capture = app.page.textObject.filter(item => item.isEventCapture === 1)
  assert.equal(capture.length, 1)
  assert.equal(capture[0].content.trim(), '')
  assert.equal(capture[0].containerName, 'input')
  await app.emit({ textEvent: { eventType: 2 } })
  assert.match(app.nodes['screen-body'].textContent, /> Germany/)
  await app.emit({ textEvent: { eventType: 1 } })
  assert.match(app.nodes['screen-body'].textContent, /> Today/)
  for (let i = 0; i < 7; i++) {
    await app.emit({ textEvent: { eventType: 2 } })
    assert.equal(app.nodes['screen-body'].textContent.split('\n').filter(line => line.startsWith('> ')).length, 1)
    assert.ok(app.nodes['screen-body'].textContent.split('\n').length <= 8)
  }
})

test('phone shows content, section buttons and working navigation; recall reveals and rates', async () => {
  const app = await start()
  assert.equal(app.nodes.status.textContent, 'Connected to your glasses')
  assert.equal(app.nodes['reader-link'].href, 'https://ansarireza.github.io/Field-Mastery/')
  assert.ok(app.controls.every(button => !button.disabled))
  const learn = app.nodes.sections.children.find(button => button.textContent.startsWith('Learn'))
  learn.click()
  await app.flush()
  assert.match(app.nodes['screen-title'].textContent, /LEARN/)
  assert.match(app.nodes['screen-body'].textContent, /Definition/)
  app.controls.find(button => button.dataset.action === 'next').click()
  await app.flush()
  assert.match(app.nodes['screen-body'].textContent, /Explanation/)
  app.nodes.sections.children.find(button => button.textContent.startsWith('Recall')).click()
  await app.flush()
  assert.match(app.nodes['screen-body'].textContent, /Question/)
  await app.emit({ sysEvent: { eventSource: 2 } })
  assert.match(app.nodes['screen-body'].textContent, /Answer/)
  await app.emit({ textEvent: { eventType: 2 } })
  assert.equal(app.nodes['screen-title'].textContent, 'RECALL DONE')
})

test('new sections show source-backed context and empty sections explain their state', async () => {
  const app = await start({ overrides: {
    today: { items: [{ headline: 'A paper', title: 'Original title', source: { date: '2026-10-27' },
      thesis: { why: 'Relevance to Kabul', action: 'Check validation' },
      critical: { question: 'Does supply measure use?', evidence: 'Only supply was modelled', limit: 'Actual use is unknown', check: 'Read methods' } }] },
    radar: { items: [{ scope: 'Germany', category: 'policy', title: 'German update', one_liner: 'A proposal', why: 'Urban planning', action: 'Read source', status: 'proposal', source: 'Agency', date: '2026-10-27', basis: 'official feed excerpt' }] },
    briefing: { date: '2026-10-28', world: [{ region: 'Africa', what: 'A collected update', why: 'Relevant comparison', action: 'Read the report', source: { title: 'Source title', date: '2026-10-27' } }], reading: { title: 'Read this paper', why: 'Useful method', questions: ['How validated?'], source: {} } },
  } })
  const open = async label => { app.nodes.sections.children.find(b => b.textContent.startsWith(label)).click(); await app.flush() }
  await open('Germany')
  assert.match(app.nodes['screen-body'].textContent, /German update/)
  await open('EU ')
  assert.match(app.nodes['screen-body'].textContent, /No selected EU updates/)
  await open('Challenges')
  assert.match(app.nodes['screen-body'].textContent, /Does supply measure use/)
  await open('World week')
  assert.match(app.nodes['screen-body'].textContent, /Africa/)
  await open('Read this week')
  assert.match(app.nodes['screen-body'].textContent, /Read this paper/)
})

test('offline cache and failed sections are visible; refresh retains quiz progress', async () => {
  const storage = { cache_meta: JSON.stringify({ generated_at: '2026-10-27', errors: { radar: 'Failed source' }, status: { radar: { state: 'error', date: '2026-10-26' } } }) }
  const app = await start({ offline: ['meta'], storage })
  assert.match(app.nodes.status.textContent, /saved content/)
  app.nodes.sections.children.find(b => b.textContent.startsWith('Update status')).click()
  await app.flush()
  assert.match(app.nodes['screen-body'].textContent, /Offline copies: meta/)
  app.nodes.sections.children.find(b => b.textContent.startsWith('Recall')).click()
  await app.flush()
  await app.emit({ sysEvent: {} })
  await app.emit({ textEvent: { eventType: 2 } })
  const progress = storage.srs
  assert.ok(progress)
  await app.nodes.refresh.click()
  await app.flush()
  assert.equal(storage.srs, progress)
  assert.equal(app.nodes.refresh.disabled, false)
})
