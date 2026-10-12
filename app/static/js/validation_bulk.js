/* Drafts are memory-only. Every save is checked independently by the server. */
(() => {
  const root = document.getElementById('bulk-review');
  if (!root) return;
  const rows = Array.from(root.querySelectorAll('[data-member-id]'));
  const form = document.getElementById('bulk-decisions');
  const save = document.getElementById('bulk-save');
  const message = document.getElementById('bulk-message');
  const drafts = new Map();
  let focused = rows[0] || null;
  let saving = false;
  let dialogOpen = false;
  const states = new Map(rows.map(row => [row, {receipt: '', loadedAt: 0, loading: false}]));
  const hasDrafts = () => drafts.size > 0;
  const announce = (row, text) => { row.querySelector('.bulk-row-message').textContent = text; };
  const updateCount = () => {
    document.getElementById('bulk-unsaved').textContent = Array.from(drafts.values())
      .filter(d => d.choice && d.choice !== 'skip').length;
  };
  function focus(row, move = false) {
    focused = row;
    rows.forEach(r => r.classList.toggle('bulk-focused', r === row));
    if (move) row.focus();
  }
  function choose(row, choice) {
    if (saving || !row.querySelector('.bulk-labels')) return;
    focus(row);
    const reason = row.querySelector('.bulk-reason').value;
    if (choice === 'skip') drafts.delete(row.dataset.memberId);
    else drafts.set(row.dataset.memberId, {choice, reason});
    row.querySelectorAll('[data-choice]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.choice === choice));
    });
    announce(row, choice === 'skip' ? 'Skipped; no human decision will be saved.' : 'Draft selection; not saved.');
    updateCount();
  }
  async function expand(row, refresh = false) {
    const state = states.get(row);
    if (state.loading || saving) return;
    const body = row.querySelector('.bulk-body');
    const button = row.querySelector('.bulk-expand');
    body.hidden = refresh ? false : !body.hidden;
    button.setAttribute('aria-expanded', String(!body.hidden));
    button.textContent = body.hidden ? 'Read article' : 'Collapse article';
    if (body.hidden || (!refresh && state.receipt && Date.now() - state.loadedAt < 1500000)) return;
    state.loading = true;
    announce(row, 'Loading verified article…');
    try {
      const response = await fetch(row.dataset.bodyUrl, {credentials: 'same-origin', cache: 'no-store'});
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || 'Article could not be loaded. Retry.');
      row.querySelector('.article-text').textContent = data.article_text || '';
      row.querySelector('.bulk-content-issue').textContent = data.content_issue || '';
      if (data.title) row.querySelector('.bulk-headline').textContent = `${row.getAttribute('aria-label').replace('Article ', '')}. ${data.title}`;
      if (data.expected_final !== row.dataset.expectedFinal && !refresh) {
        state.receipt = '';
        const refreshButton = row.querySelector('.bulk-refresh');
        if (refreshButton) refreshButton.hidden = false;
        announce(row, 'Another decision was saved. Refresh the saved version explicitly and reconsider your draft before revising.');
        return;
      }
      if (refresh) {
        row.dataset.expectedFinal = data.expected_final;
        row.querySelector('.bulk-saved-choice').textContent = data.human_choice;
        row.querySelector('.bulk-refresh').hidden = true;
      }
      state.receipt = data.body_receipt || '';
      state.loadedAt = Date.now();
      row.querySelector('.bulk-body-state').textContent = state.receipt ? 'Verified body opened in this session' : 'Verified body unavailable';
      announce(row, refresh ? 'Current saved decision shown above. Reconsider your retained draft and document the revision before saving.' : state.receipt ? 'Read the full context against the codebook before deciding.' : 'Use an unresolved decision if evidence is insufficient.');
    } catch (error) {
      announce(row, error.message || 'Could not load the article. Retry.');
    } finally { state.loading = false; }
  }
  rows.forEach(row => {
    row.addEventListener('focusin', () => focus(row));
    row.addEventListener('click', () => focus(row));
    row.querySelector('.bulk-expand').addEventListener('click', () => expand(row));
    const refreshButton = row.querySelector('.bulk-refresh');
    if (refreshButton) refreshButton.addEventListener('click', () => expand(row, true));
    row.querySelectorAll('[data-choice]').forEach(button => {
      button.addEventListener('click', () => choose(row, button.dataset.choice));
    });
    const reason = row.querySelector('.bulk-reason');
    if (reason) reason.addEventListener('input', () => {
      const draft = drafts.get(row.dataset.memberId) || {choice: ''};
      draft.reason = reason.value;
      if (draft.choice || draft.reason) drafts.set(row.dataset.memberId, draft);
      else drafts.delete(row.dataset.memberId);
      updateCount();
    });
  });
  if (focused) focus(focused);
  document.addEventListener('keydown', event => {
    if (!focused || saving || dialogOpen || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.repeat) return;
    if (event.target.closest('input, textarea, select, [contenteditable="true"], dialog, [role="dialog"]')) return;
    const key = event.key.toLowerCase();
    if (!['g', 'n', 'u', 'j', 'k', ' '].includes(key)) return;
    if (key === ' ' && event.target.closest('button, a')) return;
    event.preventDefault();
    if (key === 'j' || key === 'k') {
      const index = Math.max(0, Math.min(rows.length-1, rows.indexOf(focused) + (key === 'j' ? 1 : -1)));
      focus(rows[index], true);
    } else if (key === ' ') expand(focused);
    else choose(focused, {g: 'gbv', n: 'not_gbv', u: 'unable_to_determine'}[key]);
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving) return;
    const selected = rows.filter(row => {
      const draft = drafts.get(row.dataset.memberId);
      return draft && draft.choice && draft.choice !== 'skip';
    });
    if (!selected.length) { message.textContent = 'Choose a decision for at least one article.'; return; }
    const decisions = selected.map(row => ({member_id: row.dataset.memberId,
      ...drafts.get(row.dataset.memberId), expected_final: row.dataset.expectedFinal,
      body_receipt: states.get(row).receipt}));
    saving = true;
    save.disabled = true;
    root.querySelectorAll('.bulk-labels button, .bulk-reason').forEach(el => { el.disabled = true; });
    message.textContent = `Saving ${selected.length} decisions…`;
    try {
      const response = await fetch(root.dataset.saveUrl, {method: 'POST', credentials: 'same-origin', cache: 'no-store',
        body: new URLSearchParams({csrf_token: root.dataset.csrf, decisions: JSON.stringify(decisions)})});
      if (!(response.headers.get('content-type') || '').includes('application/json')) {
        throw new Error('Save was blocked. Keep drafts here, open review in another tab to check access, then retry.');
      }
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.error || 'Save failed. Drafts retained.');
      for (const result of data.results) {
        const row = rows.find(r => r.dataset.memberId === result.member_id);
        if (!row) continue;
        if (result.status === 'saved') {
          drafts.delete(result.member_id);
          row.dataset.expectedFinal = result.final_id;
          row.querySelector('.bulk-saved-choice').textContent = result.human_choice;
          row.querySelector('.bulk-reason').value = '';
          row.querySelectorAll('[data-choice]').forEach(button => button.setAttribute('aria-pressed', 'false'));
          states.get(row).receipt = ''; // Any further body access must match the new review pointer.
          row.querySelector('.bulk-body-state').textContent = 'Reopen to record verified body access for another decision';
          announce(row, 'Saved. Initial decision/history preserved. Title-only revisions are allowed; reopen the article if more context is needed.');
        } else {
          // A reason/storage error does not invalidate verified body access.
          if (result.status === 'conflict') {
            states.get(row).receipt = '';
            row.querySelector('.bulk-body-state').textContent = 'Saved version changed; refresh before revising';
            row.querySelector('.bulk-refresh').hidden = false;
          }
          announce(row, result.error || 'No decision saved. Draft retained.');
        }
      }
      if (data.progress) {
        document.getElementById('bulk-saved').textContent = data.progress.reviewed;
        document.getElementById('bulk-remaining').textContent = data.progress.pending;
        document.getElementById('bulk-progress').value = data.progress.reviewed;
      }
      const failures = data.results.filter(result => ['failed', 'conflict'].includes(result.status));
      const reasons = new Map();
      failures.forEach(result => {
        const reason = result.error || 'Check the row error and correct the draft.';
        reasons.set(reason, (reasons.get(reason) || 0) + 1);
      });
      const explanation = Array.from(reasons, ([reason, count]) => `${count} row${count === 1 ? '' : 's'}: ${reason}`).join(' ');
      message.textContent = `${data.saved} saved; ${data.failed} failed. ` +
        (data.failed ? `${explanation} Draft labels and reasons retained.` : 'Selections saved.');
      if (!data.progress) message.textContent += ' Progress counters could not be refreshed; reload after saving all drafts.';
    } catch (error) {
      message.textContent = error.message || 'Save outcome unavailable; drafts retained. Check saved versions in another tab before retrying.';
    } finally {
      saving = false;
      save.disabled = false;
      root.querySelectorAll('.bulk-labels button, .bulk-reason').forEach(el => { el.disabled = false; });
      updateCount();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (hasDrafts() || saving) { event.preventDefault(); event.returnValue = ''; }
  });
  function allowNavigation() {
    if (!hasDrafts() && !saving) return true;
    dialogOpen = true;
    try { return window.confirm('Unsaved drafts will be lost if you leave. Stay to save or correct them. Leave this page?'); }
    finally { dialogOpen = false; }
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && !allowNavigation()) event.preventDefault();
  });
  root.querySelector('form[method="get"]').addEventListener('submit', event => {
    if (!allowNavigation()) event.preventDefault();
  });
})();
