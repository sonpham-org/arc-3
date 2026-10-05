// Small regression checks for review mode isolation, safe citations and team API behavior.
// Run: node --test tests/triage.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { reviewMode, safeSourceURL, nextItem, triageRequest } from '../docs/static/js/triage.js';

test('the default queue is distinct from legacy pair, split and invite review URLs', () => {
  assert.equal(reviewMode('', ''), 'triage');
  assert.equal(reviewMode('?view=triage&route=assistant', ''), 'triage');
  assert.equal(reviewMode('?view=pairs', ''), 'pairs');
  assert.equal(reviewMode('?split=game-level-1', ''), 'pairs');
  assert.equal(reviewMode('', '#k=abcdefghijklmnopqrstuvwx'), 'pairs');
  assert.equal(reviewMode('', '#k=bad'), 'triage');
});

test('notes links reject active content, credentials and relative URLs', () => {
  assert.equal(safeSourceURL('https://arc3.markbarney.net/games/ab12'), 'https://arc3.markbarney.net/games/ab12');
  for (const value of ['javascript:alert(1)', 'data:text/html,a', '//evil.example', 'file:///etc/passwd', 'https://a:b@example.com', undefined])
    assert.equal(safeSourceURL(value), null);
});

test('the queue preserves priority, omits skipped and resolved items and respects handoffs', () => {
  const items = [
    { id: 'handled', status: 'resolved', assessment: { route: 'human' } },
    { id: 'handoff', route: 'assistant', assessment: { route: 'human' } },
    { id: 'first', assessment: { route: 'human' } },
    { id: 'next', assessment: { route: 'human' } },
  ];
  assert.equal(nextItem(items, new Set(), 'human').id, 'first');
  assert.equal(nextItem(items, new Set(['first']), 'human').id, 'next');
  assert.equal(nextItem(items, new Set(), 'assistant').id, 'handoff');
  assert.equal(nextItem(items, new Set(['first', 'next']), 'human'), null);
});

test('triage uses only team credentials and JSON decisions', async () => {
  const body = { id: 'q1', verdict: 'reasonable', seconds: 8 };
  let called;
  const result = await triageRequest('decision', body, async (...args) => {
    called = args;
    return new Response('{"ok":true}', { headers: { 'content-type': 'application/json' } });
  });
  assert.deepEqual(result, { ok: true });
  assert.equal(called[0], '/api/v1/review/triage/decision');
  assert.equal(called[1].credentials, 'same-origin');
  assert.equal(called[1].redirect, 'manual');
  assert.equal(called[1].method, 'POST');
  assert.equal(called[1].body, JSON.stringify(body));
  assert.equal(called[1].headers['X-Review-Key'], undefined);
});

test('sign-in redirects and service errors cannot masquerade as an empty queue', async () => {
  for (const response of [
    { type: 'opaqueredirect', status: 0 },
    new Response('login', { status: 401 }),
    new Response('forbidden', { status: 403 }),
    new Response('conflict', { status: 409 }),
    new Response('error', { status: 500 }),
    new Response('<html>login</html>', { headers: { 'content-type': 'text/html' } }),
  ]) await assert.rejects(triageRequest('queue?route=human', undefined, async () => response));
});
