// Replays every game in games.json with the page's own move engine and checks the final
// position against a reference produced independently with python-chess.
// Run from the repository root:  node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const src = readFileSync('src/app.html', 'utf8');
const start = src.indexOf('// ENGINE START');
const end = src.indexOf('// ENGINE END');
assert.ok(start >= 0 && end > start, 'engine markers not found in src/app.html');
const ENGINE = new Function(src.slice(start, end) + '; return ENGINE;')();
const data = JSON.parse(readFileSync('games.json', 'utf8'));
const reference = JSON.parse(readFileSync('tests/final_fens.json', 'utf8'));

test('every game replays to its reference final position', () => {
  const wrong = [];
  for (const g of data.games) {
    const { boards } = ENGINE.replay(g.uci.split(' '));
    const fen = ENGINE.toFen(boards[boards.length - 1]).split(' ')[0];
    if (fen !== reference[g.id]) wrong.push(g.id);
  }
  assert.equal(data.games.length, Object.keys(reference).length);
  assert.deepEqual(wrong, []);
});

test('scoring: bullseye inside 25 points, zero beyond 525', () => {
  assert.equal(ENGINE.score(0), 1000);
  assert.equal(ENGINE.score(25), 1000);
  assert.equal(ENGINE.score(125), 800);
  assert.equal(ENGINE.score(525), 0);
  assert.equal(ENGINE.score(2000), 0);
});

test('every game carries the fields the page reads', () => {
  for (const g of data.games) {
    const plies = g.uci.split(' ').length;
    assert.equal(g.san.split(' ').length, plies, g.id);
    assert.equal(g.clk.length, plies, g.id);
    assert.equal(g.ev.length, plies, g.id);
    assert.equal(g.mk.length, plies, g.id);
    assert.ok(Number.isFinite(g.model) && Number.isFinite(g.w) && Number.isFinite(g.b), g.id);
  }
});
