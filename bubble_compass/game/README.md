# Bubble Compass (Kaplay)

Playable desk scaffold for allocating sleeve weights along a real history tape from the Bubble Compass brain API.

## Run

```bash
cd bubble_compass/game
npm install
npm run dev
```

Open the URL Vite prints (default port `5174`). Build for production:

```bash
npm run build
```

## History tape

`TapePlayer` loads per-asset history from:

- `GET {VITE_API_URL}/api/v1/history/{asset}` (default `VITE_API_URL=http://localhost:8000`)
- If every fetch fails, `src/data/history_fixture.json` is used for offline play.

If neither source yields data, the title screen shows **TAPE NOT BUILT**. Build parquet history under the brain cache (`data/cache/history/...`) and run the API from `bubble_compass/brain`.

## Controls

- **Title:** arrow keys pick episode, `1`–`5` jump tape to pinned dates, `enter` starts a desk session.
- **Desk:** `up`/`down` select sleeve, `w`/`s` adjust weight, `space` commit turn (advances `as_of`), `escape` back to title.
- **Crash / debrief:** `space` or `enter` to continue.

## Notes

- One session is a short turn loop on the history tape; episodes only set the starting `as_of` (no random event generator).
- HUD fields map brain layers: Heat (`residual_z`), Stretch (`bsadf`), crash window (`lppls`), sentiment, regime.
