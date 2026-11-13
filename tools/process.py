"""candidates.jsonl -> games.json (play set) with marks, Lichess-style accuracy, and an
out-of-sample model estimate of the average rating trained on the disjoint remainder."""
import json, math, random, statistics, sys, collections
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

SRC, OUT = sys.argv[1], sys.argv[2]
PER_BAND = int(sys.argv[3]) if len(sys.argv) > 3 else 60
LO, HI, STEP = 600, 3000, 100
random.seed(20261101)


def win_pct(cp):
    if cp is None:
        return None
    if abs(cp) >= 9000:            # forced mate
        return 100.0 if cp > 0 else 0.0
    cp = max(-1000, min(1000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def analyse(g):
    ev = list(g['ev'])
    n = len(ev)
    # mate delivered on the last ply: eval after is a won (or drawn) position for the mover
    if ev[-1] is None:
        mover_white = (n - 1) % 2 == 0
        if g['term'] == 'mate':
            ev[-1] = 10000 if mover_white else -10000
        else:
            ev[-1] = 0
    wp = [win_pct(15)] + [win_pct(e) for e in ev]          # white-POV win% before ply 0 .. after ply n-1
    marks, accs, losses = [], [[], []], [[], []]
    cnt = {'w': [0, 0, 0], 'b': [0, 0, 0]}
    for k in range(n):
        side = k % 2                 # 0 white, 1 black
        before = wp[k] if side == 0 else 100 - wp[k]
        after = wp[k + 1] if side == 0 else 100 - wp[k + 1]
        drop = before - after
        if drop >= 15:
            m = 'b'
        elif drop >= 10:
            m = 'm'
        elif drop >= 5:
            m = 'i'
        else:
            m = '.'
        marks.append(m)
        if m != '.':
            cnt['wb'[side]]['imb'.index(m)] += 1
        a = 100.0 if after >= before else max(0.0, min(100.0, 103.1668100711649 * math.exp(-0.04354415386753951 * drop) - 3.166924740191411 + 1))
        accs[side].append(a)
        # centipawn loss (mover POV, capped)
        cb = max(-1000, min(1000, (15 if k == 0 else (ev[k - 1] if abs(ev[k - 1]) < 9000 else math.copysign(1000, ev[k - 1])))))
        ca = max(-1000, min(1000, ev[k] if abs(ev[k]) < 9000 else math.copysign(1000, ev[k])))
        loss = (cb - ca) if side == 0 else (ca - cb)
        losses[side].append(max(0, loss))
    # Lichess game accuracy: volatility-weighted mean blended with harmonic mean
    win_list = wp
    wsize = max(2, min(8, n // 10))
    windows = []
    for i in range(n):
        lo = max(0, i + 1 - wsize)
        seg = win_list[lo:i + 2] if i + 2 - lo >= 2 else win_list[:2]
        windows.append(seg)
    weights = [max(0.5, min(12.0, statistics.pstdev(s))) for s in windows]
    acc = []
    for side in (0, 1):
        idx = [k for k in range(n) if k % 2 == side]
        if not idx:
            acc.append(0.0)
            continue
        a = [accs[side][j] for j in range(len(idx))]
        w = [weights[k] for k in idx]
        wmean = sum(x * y for x, y in zip(a, w)) / sum(w)
        hmean = len(a) / sum(1 / max(x, 0.1) for x in a)
        acc.append(round((wmean + hmean) / 2, 1))
    return ''.join(marks), acc, cnt, losses


def features(g, marks, acc, cnt, losses):
    n = len(g['ev'])
    base, inc = g['base'], g['inc']
    clk = g['clk']
    spent = [[], []]
    prev = [base, base]
    for k, c in enumerate(clk):
        s = k % 2
        spent[s].append(max(0, prev[s] - c + (inc if k >= 2 else 0)))
        prev[s] = c
    tot = base + 40 * inc
    acpl = [statistics.mean(l) if l else 0 for l in losses]
    early = [statistics.mean(l[:10]) if l else 0 for l in losses]
    moves = n / 2
    f = [
        statistics.mean(acc), min(acc), max(acc), abs(acc[0] - acc[1]),
        statistics.mean(acpl), min(acpl), max(acpl), statistics.mean(early),
        (cnt['w'][0] + cnt['b'][0]) / moves, (cnt['w'][1] + cnt['b'][1]) / moves, (cnt['w'][2] + cnt['b'][2]) / moves,
        cnt['w'][2] + cnt['b'][2], n, math.log(base + 1), inc, math.log(tot),
        ['blitz', 'rapid', 'classical'].index(g['cls']),
        statistics.mean(spent[0] + spent[1]) / tot, min(clk[-2:]) / tot if len(clk) >= 2 else 1,
        max(spent[0] + spent[1]) / tot,
        ['mate', 'resign', 'time', 'draw', 'stalemate', 'insufficient', 'repetition'].index(g['term']) if g['term'] in ['mate', 'resign', 'time', 'draw', 'stalemate', 'insufficient', 'repetition'] else 3,
        'ABCDE'.index(g['eco'][0]) if g['eco'][:1] in 'ABCDE' and g['eco'] else -1,
        int(g['eco'][1:3]) if len(g['eco']) == 3 and g['eco'][1:].isdigit() else -1,
        sum(1 for m in marks[:20] if m != '.'),
    ]
    return f


def band(r):
    return (r - LO) // STEP


def main():
    rows = [json.loads(l) for l in open(SRC, encoding='utf-8')]
    print('candidates', len(rows))
    for g in rows:
        g['avg'] = (g['w'] + g['b']) / 2
        marks, acc, cnt, losses = analyse(g)
        g['mk'], g['acc'], g['cnt'] = marks, acc, cnt
        g['_f'] = features(g, marks, acc, cnt, losses)

    eligible = [g for g in rows if abs(g['w'] - g['b']) <= 150 and abs(g['wd']) <= 25 and abs(g['bd']) <= 25
                and LO <= g['avg'] < HI and 40 <= len(g['ev']) <= 160]
    bybands = collections.defaultdict(list)
    for g in eligible:
        bybands[band(int(g['avg']))].append(g)
    play = []
    for bnd in sorted(bybands):
        pool = bybands[bnd]
        random.shuffle(pool)
        bycls = collections.defaultdict(list)
        for g in pool:
            bycls[g['cls']].append(g)
        pick = []
        while len(pick) < PER_BAND and any(bycls.values()):
            for c in ('blitz', 'rapid', 'classical'):
                if bycls[c] and len(pick) < PER_BAND:
                    pick.append(bycls[c].pop())
        play.extend(pick)
        print(f"band {LO + bnd * STEP}-{LO + bnd * STEP + 99}: pool {len(pool):5d} picked {len(pick):3d} "
              f"{collections.Counter(g['cls'] for g in pick)}")
    play_ids = {g['id'] for g in play}

    # model: train on everything not in the play set, weighted toward a flat rating prior
    train = [g for g in rows if g['id'] not in play_ids and abs(g['w'] - g['b']) <= 300 and LO <= g['avg'] < HI]
    tb = collections.Counter(band(int(g['avg'])) for g in train)
    X = np.array([g['_f'] for g in train], dtype=float)
    y = np.array([g['avg'] for g in train])
    sw = np.array([1.0 / tb[band(int(g['avg']))] for g in train])
    sw = sw / sw.mean()
    model = HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_leaf_nodes=31,
                                          l2_regularization=1.0, random_state=0)
    model.fit(X, y, sample_weight=sw)
    Xp = np.array([g['_f'] for g in play], dtype=float)
    pred = model.predict(Xp)
    errs = []
    for g, p in zip(play, pred):
        g['model'] = int(round(max(LO, min(HI, p)) / 10) * 10)
        errs.append(abs(g['model'] - g['avg']))
    mae = statistics.mean(errs)
    base_mae = statistics.mean(abs(1800 - g['avg']) for g in play)
    print(f"train {len(train)}  play {len(play)}  model MAE {mae:.0f}  (always-1800 MAE {base_mae:.0f})")
    for lo in range(LO, HI, 400):
        e = [abs(g['model'] - g['avg']) for g in play if lo <= g['avg'] < lo + 400]
        if e:
            print(f"  {lo}-{lo + 399}: MAE {statistics.mean(e):.0f} n={len(e)}")

    random.shuffle(play)
    keep = ['id', 'w', 'b', 'tc', 'cls', 'eco', 'opening', 'result', 'term', 'date', 'san', 'uci', 'clk', 'ev', 'mk', 'acc', 'cnt', 'model']
    out = {
        'meta': {
            'source': 'Lichess open database, standard rated games, October 2026 (CC0)',
            'month': '2026-10', 'count': len(play), 'modelMAE': round(mae), 'baselineMAE': round(base_mae),
            'trainCount': len(train), 'scanned': None,
            'filters': 'blitz/rapid/classical; engine-analysed with clocks; both players within 150 points; '
                       'rating change under 26 (established ratings); 20-80 moves; normal finish or time-out; no bots',
            'bandStep': STEP, 'perBand': PER_BAND,
        },
        'games': [{k: g[k] for k in keep} for g in play],
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, separators=(',', ':'))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
