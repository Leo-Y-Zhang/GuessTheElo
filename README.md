# Guess the Elo

Watch a real rated chess game from Lichess, move by move, with the players' real clocks and
thinking times. Then guess the average rating of the two players. A model makes its own guess on
every game, so you can see whether you read a game better than it does.

**Play it: <https://leo-y-zhang.github.io/GuessTheElo/>**

## What it does

- **Real games, real clocks.** 1,302 rated blitz, rapid and classical games from October 2026,
  replayed with each player's clock and the time spent on every move. Names are never shown.
- **Even spread.** About 60 games for every 100-point band of average rating from 600 to 2,900,
  so the middle is no safer a guess than the edges.
- **Three assist levels.** Blind (board and moves only), Standard (adds clocks, time control and
  think times) and Assisted (adds an evaluation bar and inaccuracy, mistake and blunder marks).
- **A daily five.** The same five games for everyone each day, up to 5,000 points, plus endless
  practice with a streak for guesses within 150 points.
- **An opponent with a known error.** A gradient-boosted model trained on 52,159 other games from
  the same month reads only engine and clock figures. On this set it misses by 269 rating points on
  average, against 546 for always guessing 1,800. The reveal shows who was closer.
- **Stats that teach.** A calibration plot (do you rate players too high or too low?), your error
  by rating band, and your record against the model. They stay in your browser.

Scoring: `points = 1000 - 2 * max(0, error - 25)`, never below zero.

## How it is built

| Path | What it is |
|---|---|
| `index.html` | The whole game: one page, inline CSS and plain JavaScript, no framework, no tracking. Generated from `src/app.html`. |
| `src/app.html` | The source of the page, including its own move engine (`ENGINE START` to `ENGINE END`). |
| `games.json` | The game set: moves, clocks, engine evaluations, move marks, accuracy and the model's guess. |
| `tools/build.py` | Builds `index.html`: inlines the piece SVGs and wraps the page in a full HTML document. |
| `tools/extract.py`, `tools/process.py` | The data pipeline (python-chess, NumPy, scikit-learn): stream a Lichess monthly database file, keep engine-analysed games that record both clocks, compute marks and accuracy with the Lichess win-chance thresholds, train the model on games outside the play set, and pick the set band by band. |
| `tests/engine.test.mjs` | Replays all 1,302 games with the page's engine and checks every final position against one computed independently with python-chess. |
| `tools/review.py` | Screenshots every screen at phone and desktop widths in light and dark themes, and reports console errors and sideways scrolling. |

## Run it locally

```sh
python -m http.server          # then open http://localhost:8000
node --test tests/engine.test.mjs
python tools/build.py          # after editing src/app.html
```

The page fetches `games.json`, so it needs a local server rather than opening the file directly.

## Data and credits

- Games: the [Lichess open database](https://database.lichess.org/), released under CC0.
- Pieces: the cburnett set by Colin M.L. Burnett, under its BSD licence.

See `NOTICE` for details.

## Licence

Proprietary, source-available: you may read and run it, but not reuse it. See `LICENSE`. The
piece set and the game data keep their own licences, listed in `NOTICE`.
