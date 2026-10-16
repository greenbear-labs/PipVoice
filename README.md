# Pip

A talking buddy for toddlers. Pip listens through the browser's speech recognition, picks out words like cars, robots and candy, and answers with short recorded lines. When she hears talking but no word she knows, she answers with a friendly "tell me more" line.

- `index.html` is the whole site. Pip's lines are in the `pip-lines` block near the bottom.
- `audio/` holds one MP3 per line plus `manifest.js`. Lines without a clip use the device's own voice.
- `make_pip_voice.py` records the clips with the Dragon Spit Narrator engine on the Mac mini.

## Updating Pip's voice

On the Mac mini, with the engine running:

```bash
python3 make_pip_voice.py --sample   # record 5 lines into audio-sample/ to audition a voice
python3 make_pip_voice.py            # record every line that has no clip yet
git add audio && git commit -m "Record Pip's voice clips" && git push
```

Add `--voice qwen3:ono_anna --emotion excited` to try a different voice, and `--fresh` to re-record every line after switching.

Vercel serves this folder as a static site with no build step. Speech recognition works in Chrome, Edge and Safari; Firefox doesn't support it.
