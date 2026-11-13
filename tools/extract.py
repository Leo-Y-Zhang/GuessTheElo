"""Stream a truncated Lichess monthly .pgn.zst and keep games that carry %eval and %clk
on every move. Writes candidates.jsonl (one compact game per line, no player names)."""
import io, json, math, re, sys
import zstandard as zstd
import chess

SRC, OUT = sys.argv[1], sys.argv[2]

HDR = re.compile(r'^\[(\w+) "(.*)"\]$')
TOK_COMMENT = re.compile(r'\{([^}]*)\}')
EVAL = re.compile(r'\[%eval ([^\]]+)\]')
CLK = re.compile(r'\[%clk (\d+):(\d+):(\d+)\]')
MOVE_NUM = re.compile(r'^\d+\.(\.\.)?$')
RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def parse_eval(s):
    s = s.strip()
    if s.startswith('#'):
        n = int(s[1:])
        return (10000 - abs(n)) * (1 if n > 0 else -1)
    return int(round(float(s) * 100))


def games(stream):
    hdr, body = {}, []
    in_body = False
    for raw in stream:
        line = raw.rstrip('\n')
        if line.startswith('['):
            if in_body:
                yield hdr, ' '.join(body)
                hdr, body, in_body = {}, [], False
            m = HDR.match(line)
            if m:
                hdr[m.group(1)] = m.group(2)
        elif line.strip():
            in_body = True
            body.append(line)
    if hdr and body:
        yield hdr, ' '.join(body)


def tokens(movetext):
    # returns list of (san, comment)
    out = []
    i, n = 0, len(movetext)
    while i < n:
        c = movetext[i]
        if c == '{':
            j = movetext.index('}', i)
            if out:
                out[-1][1] += movetext[i + 1:j]
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not movetext[j].isspace() and movetext[j] != '{':
                j += 1
            t = movetext[i:j]
            i = j
            if MOVE_NUM.match(t) or t in RESULTS or t.startswith('$'):
                continue
            t = t.rstrip('?!')
            out.append([t, ''])
    return out


def main():
    dctx = zstd.ZstdDecompressor()
    kept = seen = 0
    with open(SRC, 'rb') as fh, open(OUT, 'w', encoding='utf-8') as out:
        reader = dctx.stream_reader(fh, read_across_frames=True)
        text = io.TextIOWrapper(reader, encoding='utf-8', errors='replace')
        try:
            for hdr, mt in games(text):
                seen += 1
                if '%eval' not in mt or '%clk' not in mt:
                    continue
                if hdr.get('Event', '').lower().find('rated') < 0:
                    continue
                if 'BOT' in (hdr.get('WhiteTitle', ''), hdr.get('BlackTitle', '')):
                    continue
                tc = hdr.get('TimeControl', '-')
                if tc == '-' or '+' not in tc:
                    continue
                base, inc = (int(x) for x in tc.split('+'))
                est = base + 40 * inc
                if est < 180:      # drop bullet / ultrabullet
                    continue
                cls = 'blitz' if est < 480 else 'rapid' if est < 1500 else 'classical'
                term = hdr.get('Termination', '')
                if term not in ('Normal', 'Time forfeit'):
                    continue
                try:
                    w, b = int(hdr['WhiteElo']), int(hdr['BlackElo'])
                    wd, bd = int(hdr.get('WhiteRatingDiff', '0')), int(hdr.get('BlackRatingDiff', '0'))
                except (KeyError, ValueError):
                    continue
                toks = tokens(mt)
                if not (30 <= len(toks) <= 170):
                    continue
                board = chess.Board()
                san, uci, clk, ev = [], [], [], []
                ok = True
                for k, (s, com) in enumerate(toks):
                    try:
                        mv = board.parse_san(s)
                    except Exception:
                        ok = False
                        break
                    san.append(board.san(mv))
                    uci.append(mv.uci())
                    board.push(mv)
                    cm = CLK.search(com)
                    if not cm:
                        ok = False
                        break
                    clk.append(int(cm.group(1)) * 3600 + int(cm.group(2)) * 60 + int(cm.group(3)))
                    em = EVAL.search(com)
                    if em:
                        ev.append(parse_eval(em.group(1)))
                    elif k == len(toks) - 1 and board.is_game_over():
                        ev.append(None)   # mate / stalemate on board: no eval after
                    else:
                        ok = False
                        break
                if not ok:
                    continue
                outcome = board.outcome()
                res = hdr.get('Result')
                if term == 'Time forfeit':
                    how = 'time'
                elif outcome is not None:
                    how = {chess.Termination.CHECKMATE: 'mate', chess.Termination.STALEMATE: 'stalemate',
                           chess.Termination.INSUFFICIENT_MATERIAL: 'insufficient',
                           chess.Termination.FIVEFOLD_REPETITION: 'repetition',
                           chess.Termination.SEVENTYFIVE_MOVES: 'draw'}.get(outcome.termination, 'draw')
                elif res == '1/2-1/2':
                    how = 'draw'
                else:
                    how = 'resign'
                site = hdr.get('Site', '')
                gid = site.rsplit('/', 1)[-1]
                rec = dict(id=gid, w=w, b=b, wd=wd, bd=bd, tc=tc, base=base, inc=inc, cls=cls,
                           eco=hdr.get('ECO', ''), opening=hdr.get('Opening', ''), result=res,
                           term=how, date=hdr.get('UTCDate', ''), san=' '.join(san), uci=' '.join(uci),
                           clk=clk, ev=ev)
                out.write(json.dumps(rec, separators=(',', ':')) + '\n')
                kept += 1
                if kept % 2000 == 0:
                    print('kept', kept, 'seen', seen, flush=True)
        except (zstd.ZstdError, EOFError, ValueError) as e:
            print('stream ended:', type(e).__name__, str(e)[:80])
    print('DONE kept', kept, 'of', seen)


if __name__ == '__main__':
    main()
