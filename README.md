# The Likeness

A machine is shown yesterday's photograph and nothing else. It fills in six
slots describing what it can see. Those six lines are the entire prompt for
today's photograph. Then it is shown that one.

No memory, no earlier picture, no earlier words, no idea what it is looking at.
One frame a day, forever, until the chain stops moving.

Live at <https://likeness.charlietrenorden.com> (pending DNS).

## The loop

| Stage | File | What happens |
|---|---|---|
| Describe | `describe.py` | Gemini vision looks at frame N and fills six slots |
| Avoid | `avoid.py` | Words the run has leaned on lately are banned from that description |
| Draw | `draw.py` | The six slots become the prompt; Cloudflare Workers AI draws frame N+1 |
| Assess | `collapse.py` | Have the words AND the pictures both stopped moving? |
| Render | `render.py` | Rebuild the viewer |

`step.py` is the daily entry point and owns all the IO. Everything else is pure
functions over plain dicts.

These loops are known to converge rather than wander, and the design is built
around that fact rather than in spite of it. **Read [docs/collapse.md](docs/collapse.md)
before changing anything in `describe.py`, `avoid.py` or the `collapse` block of
`config/settings.yaml`** - each of those numbers is load-bearing and the reasons
are not guessable from the code.

## Running it

```bash
pip install -r requirements.txt
python step.py            # advance the chain one frame
python step.py --render   # rebuild the site from existing data, no API calls
python -m pytest tests/ -q
```

Needs `GEMINI_API_KEY`, `CF_ACCOUNT_ID` and `CF_API_TOKEN`, from a gitignored
`.env` locally or from repository secrets in CI. Both services are on free tiers.

## Data

- `data/runs/NNN.json` - one file per run, holding every frame's description,
  prompt, image path, perceptual hash and collapse reading. A sealed run never
  changes again, so it never appears in another diff.
- `assets/img/rNNN-fNNNN.jpg` - the frames, all one width. Not decorative: the
  collapse detector compares them against each other, so a size change mid-chain
  would register as movement the loop did not produce.
- `manifest.json` - the whole chain as data, rebuilt each run. The page does not
  read it (the payload is inlined so the viewer works on first paint); it is
  there for anyone who wants the chain without scraping it.

## The site

One page. Arrows and the left/right keys step through the chain a frame at a
time, Home and End jump to the ends, the slider scrubs, and the URL hash
(`#r2f14`) makes any frame linkable. Deliberately not a page per frame: the whole
point is comparing frame N with frame N+1, and a document load between them puts
a white flash exactly where the comparison happens.
