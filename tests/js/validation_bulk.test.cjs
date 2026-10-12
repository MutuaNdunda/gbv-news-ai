/* A small DOM adapter exercises actual page handlers without browser dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

class Element {
  constructor(tag = 'div', attrs = {}) {
    this.tag = tag; this.attrs = attrs; this.children = []; this.parent = null;
    this.handlers = new Map(); this.dataset = {}; this.value = ''; this.textContent = '';
    this.hidden = false; this.disabled = false;
    this.classes = new Set((attrs.class || '').split(' '));
    this.classList = {toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name)};
  }
  add(child) { this.children.push(child); child.parent = this; return child; }
  matches(selector) {
    return selector.split(',').some(s => {
      s = s.trim();
      if (s.startsWith('.')) return this.classes.has(s.slice(1));
      if (s.startsWith('#')) return this.attrs.id === s.slice(1);
      const attribute = s.match(/^(\w+)?\[([^=\]]+)(?:="([^"]*)")?\]$/);
      if (attribute) {
        const key = attribute[2];
        const value = key.startsWith('data-') ? this.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] : this.attrs[key];
        return (!attribute[1] || attribute[1] === this.tag) && value !== undefined && (attribute[3] === undefined || value === attribute[3]);
      }
      return this.tag === s;
    });
  }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return this.matches(selector) ? this : this.parent?.closest(selector) || null; }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key]; }
  addEventListener(type, handler) { const handlers = this.handlers.get(type) || []; handlers.push(handler); this.handlers.set(type, handlers); }
  async fire(type, extra = {}) {
    const event = {target: this, prevented: false, preventDefault() {this.prevented = true;}, ...extra};
    for (const handler of this.handlers.get(type) || []) await handler(event);
    return event;
  }
  focus() { for (const handler of this.handlers.get('focusin') || []) handler({target: this}); }
}

function setup() {
  const document = new Element('document');
  document.getElementById = id => document.querySelector('#'+id);
  const root = document.add(new Element('div', {id: 'bulk-review'}));
  root.dataset = {saveUrl: '/bulk/save', csrf: 'synthetic-csrf'};
  const message = root.add(new Element('span', {id: 'bulk-message'}));
  const unsaved = root.add(new Element('strong', {id: 'bulk-unsaved'}));
  const saved = root.add(new Element('strong', {id: 'bulk-saved'})); saved.textContent = '0';
  const remaining = root.add(new Element('strong', {id: 'bulk-remaining'})); remaining.textContent = '2';
  root.add(new Element('progress', {id: 'bulk-progress'}));
  const filter = root.add(new Element('form', {method: 'get'}));
  const form = root.add(new Element('form', {id: 'bulk-decisions'}));
  const save = form.add(new Element('button', {id: 'bulk-save'}));
  const rows = ['one', 'two'].map((id, index) => {
    const row = form.add(new Element('article', {'aria-label': `Article ${index+1}`, class: 'bulk-row'}));
    row.dataset = {memberId: id, expectedFinal: '', bodyUrl: '/body/'+id};
    row.add(new Element('h2', {class: 'bulk-headline'}));
    row.add(new Element('button', {class: 'bulk-expand'}));
    row.add(new Element('strong', {class: 'bulk-saved-choice'}));
    row.add(new Element('span', {class: 'bulk-body-state'}));
    const labels = row.add(new Element('div', {class: 'bulk-labels'}));
    for (const choice of ['gbv','not_gbv','unable_to_determine','borderline','needs_adjudication','skip']) {
      const button = labels.add(new Element('button')); button.dataset.choice = choice;
    }
    row.add(new Element('textarea', {class: 'bulk-reason'}));
    row.add(new Element('p', {class: 'bulk-row-message'}));
    row.add(new Element('button', {class: 'bulk-refresh'})).hidden = true;
    const body = row.add(new Element('div', {class: 'bulk-body'})); body.hidden = true;
    body.add(new Element('p', {class: 'bulk-content-issue'}));
    body.add(new Element('div', {class: 'article-text'}));
    return row;
  });
  const link = document.add(new Element('a', {href: '/next'}));
  const window = new Element('window'); window.confirm = () => false;
  const replies = []; const calls = [];
  const fetch = async (url, options) => {
    calls.push({url, options});
    if (!replies.length) throw new Error('Synthetic network failure');
    const reply = replies.shift();
    return {ok: reply.ok !== false, headers: {get: () => reply.type || 'application/json'}, json: async () => reply.data};
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../app/static/js/validation_bulk.js'), 'utf8'),
    {document, window, fetch, URLSearchParams, Date});
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const key = (value, target=rows[0], extra={}) => document.fire('keydown', {key: value, target, ...extra});
  return {document, window, root, form, filter, rows, save, message, unsaved, saved, remaining, link, replies, calls, tick, key};
}

test('inline and keyboard decisions change drafts only; typing and modifiers disable shortcuts', async () => {
  const ui = setup();
  await ui.key('g');
  assert.equal(ui.unsaved.textContent, 1);
  assert.equal(ui.saved.textContent, '0');
  assert.equal(ui.rows[0].querySelector('[data-choice="gbv"]').getAttribute('aria-pressed'), 'true');
  await ui.key('j'); await ui.key('n', ui.rows[1]);
  assert(ui.rows[1].classes.has('bulk-focused'));
  assert.equal(ui.unsaved.textContent, 2);
  await ui.key('u', ui.rows[1].querySelector('textarea'));
  assert.equal(ui.rows[1].querySelector('[data-choice="not_gbv"]').getAttribute('aria-pressed'), 'true');
  await ui.key('g', ui.rows[1], {ctrlKey: true});
  await ui.key('k'); await ui.key('u');
  assert.equal(ui.rows[0].querySelector('[data-choice="unable_to_determine"]').getAttribute('aria-pressed'), 'true');
  assert.equal(ui.calls.length, 0);
});

test('space fetches full text lazily, uses textContent, and collapse reuses verified access', async () => {
  const ui = setup();
  ui.replies.push({data: {title: 'Synthetic pinned title', article_text: '<script>private()</script>', body_receipt: 'receipt', expected_final: ''}});
  await ui.key(' '); await ui.tick();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.rows[0].querySelector('.article-text').textContent, '<script>private()</script>');
  assert.equal(ui.rows[0].querySelector('.bulk-body').hidden, false);
  await ui.key(' '); await ui.key(' '); await ui.tick();
  assert.equal(ui.calls.length, 1);
});

test('partial save keeps unsuccessful drafts, updates saved progress, and submits selected rows only', async () => {
  const ui = setup(); await ui.key('g'); await ui.key('j'); await ui.key('u');
  ui.replies.push({data: {saved: 1, failed: 1, progress: {reviewed: 1, pending: 1}, results: [
    {member_id: 'one', status: 'failed', error: 'Open verified body'},
    {member_id: 'two', status: 'saved', final_id: 'final-two', human_choice: 'unable_to_determine'}]}});
  await ui.form.fire('submit');
  assert.equal(ui.unsaved.textContent, 1);
  assert.equal(ui.saved.textContent, 1);
  assert.equal(ui.remaining.textContent, 1);
  assert.equal(ui.rows[0].querySelector('[data-choice="gbv"]').getAttribute('aria-pressed'), 'true');
  assert.equal(ui.rows[1].dataset.expectedFinal, 'final-two');
  assert.match(ui.message.textContent, /1 row: Open verified body/);
  assert.equal(JSON.parse(ui.calls[0].options.body.get('decisions')).length, 2);
  assert.equal(ui.save.disabled, false);
  await ui.rows[0].querySelector('[data-choice="skip"]').fire('click');
  assert.equal(ui.unsaved.textContent, 0);
  const event = await ui.window.fire('beforeunload'); assert.equal(event.prevented, false);
});

test('title-only resolved decisions save without fetching article bodies', async () => {
  const ui = setup(); await ui.key('g'); await ui.key('j'); await ui.key('n');
  for (const row of ui.rows) {
    const reason = row.querySelector('.bulk-reason');
    reason.value = 'Synthetic title provides sufficient evidence'; await reason.fire('input');
  }
  ui.replies.push({data: {saved: 2, failed: 0, progress: {reviewed: 2, pending: 0}, results: [
    {member_id: 'one', status: 'saved', final_id: 'final-one', human_choice: 'gbv'},
    {member_id: 'two', status: 'saved', final_id: 'final-two', human_choice: 'not_gbv'}]}});
  await ui.form.fire('submit');
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0].url, '/bulk/save');
  const decisions = JSON.parse(ui.calls[0].options.body.get('decisions'));
  assert.deepEqual(decisions.map(row => row.body_receipt), ['', '']);
  assert.equal(ui.unsaved.textContent, 0);
  assert.equal(ui.saved.textContent, 2);
  assert.match(ui.message.textContent, /2 saved; 0 failed/);
});

test('network/access failures retain drafts and navigation guards prevent accidental loss', async () => {
  const ui = setup(); await ui.key('u');
  ui.replies.push({ok: false, data: {error: 'Session expired'}});
  await ui.form.fire('submit');
  assert.equal(ui.unsaved.textContent, 1);
  assert.equal(ui.message.textContent, 'Session expired');
  assert.equal((await ui.window.fire('beforeunload')).prevented, true);
  assert.equal((await ui.document.fire('click', {target: ui.link})).prevented, true);
  assert.equal((await ui.filter.fire('submit')).prevented, true);
});

test('concurrent conflict requires explicit refresh, preserves draft, and revises current pointer', async () => {
  const ui = setup(); await ui.key('u');
  ui.replies.push({data: {saved: 0, failed: 1, results: [{member_id: 'one', status: 'conflict', error: 'Decision changed'}]}});
  await ui.form.fire('submit');
  assert.equal(ui.rows[0].querySelector('.bulk-refresh').hidden, false);
  assert.equal(ui.rows[0].dataset.expectedFinal, '');
  ui.replies.push({data: {article_text: 'Synthetic body', body_receipt: 'current-receipt', expected_final: 'new-final', human_choice: 'needs_adjudication'}});
  await ui.rows[0].querySelector('.bulk-refresh').fire('click'); await ui.tick();
  assert.equal(ui.rows[0].dataset.expectedFinal, 'new-final');
  assert.equal(ui.unsaved.textContent, 1);
  ui.replies.push({data: {saved: 1, failed: 0, progress: {reviewed: 1, pending: 1}, results: [
    {member_id: 'one', status: 'saved', final_id: 'revision', human_choice: 'unable_to_determine'}]}});
  await ui.form.fire('submit');
  const submitted = JSON.parse(ui.calls[2].options.body.get('decisions'))[0];
  assert.equal(submitted.expected_final, 'new-final');
  assert.equal(submitted.body_receipt, 'current-receipt');
  assert.equal(ui.unsaved.textContent, 0);
});

test('a failed save retains valid body access so correcting a reason does not require reopening', async () => {
  const ui = setup();
  ui.replies.push({data: {article_text: 'Synthetic body', body_receipt: 'verified-receipt', expected_final: ''}});
  await ui.key(' '); await ui.tick(); await ui.key('g');
  ui.replies.push({data: {saved: 0, failed: 1, results: [
    {member_id: 'one', status: 'failed', error: 'Record an independent decision reason.'}]}});
  await ui.form.fire('submit');
  assert.match(ui.message.textContent, /Record an independent decision reason/);
  const reason = ui.rows[0].querySelector('.bulk-reason');
  reason.value = 'Synthetic context rationale'; await reason.fire('input');
  ui.replies.push({data: {saved: 1, failed: 0, progress: {reviewed: 1, pending: 1}, results: [
    {member_id: 'one', status: 'saved', final_id: 'saved-one', human_choice: 'gbv'}]}});
  await ui.form.fire('submit');
  const retry = JSON.parse(ui.calls[2].options.body.get('decisions'))[0];
  assert.equal(retry.body_receipt, 'verified-receipt');
  assert.equal(retry.reason, 'Synthetic context rationale');
  assert.equal(ui.unsaved.textContent, 0);
});
