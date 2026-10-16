#!/usr/bin/env python3
"""Record every line Pip can say with the Dragon Spit Narrator engine.

Run it on the Mac mini, in the PipVoice repo (next to index.html), while the engine is running:

    python3 make_pip_voice.py                          # Kokoro "Heart" (default)
    python3 make_pip_voice.py --voice qwen3:ono_anna   # a more playful, expressive voice
    python3 make_pip_voice.py --sample                 # record 5 lines to audition a voice

It writes audio/<hash>.mp3 for each line plus audio/manifest.js, which the page loads.
Lines that already have a clip are skipped, so after editing a line in index.html just run it again.
Use --fresh after changing the voice to re-record everything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fnv1a(text: str) -> str:
    """Same hash pip.html uses to find a line's clip."""
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def load_lines(page: Path) -> list[str]:
    html = page.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="pip-lines">(.*?)</script>', html, re.S)
    if not m:
        sys.exit(f"Couldn't find Pip's lines in {page}")
    data = json.loads(m.group(1))
    lines: list[str] = []
    for t in data["topics"]:
        lines += t["say"]
        lines += [s.replace("{topic}", t["label"].lower()) for s in data["idle"]]
    for group in ("combos", "social"):
        for item in data[group]:
            lines += item["say"]
    for key in ("generic", "hello", "poke", "sleepy"):
        lines += data[key]
    return list(dict.fromkeys(lines))  # drop duplicates, keep order


def read_token() -> str:
    if os.environ.get("NARRATOR_TOKEN"):
        return os.environ["NARRATOR_TOKEN"]
    data_dir = Path(os.environ.get("NARRATOR_DATA_DIR", "~/.dragonspit-narrator")).expanduser()
    token_file = data_dir / "api-token"
    if token_file.exists():
        return token_file.read_text().strip()
    sys.exit("No engine token found. Start the engine once, or set NARRATOR_TOKEN.")


class Engine:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _req(self, method: str, path: str, body: dict | None = None) -> bytes:
        headers = dict(self.headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read()

    def json(self, method: str, path: str, body: dict | None = None) -> dict:
        return json.loads(self._req(method, path, body))

    def record(self, text: str, args: argparse.Namespace) -> bytes:
        clip = self.json("POST", "/v1/clips", {
            "text": text, "voice_id": args.voice, "emotion": args.emotion,
            "intensity": args.intensity, "speed": args.speed, "format": "mp3",
            "tags": ["pip"], "wait": True,
        })
        while clip["status"] in ("queued", "running"):
            time.sleep(1)
            clip = self.json("GET", f"/v1/clips/{clip['id']}")
        if clip["status"] != "done":
            raise RuntimeError(clip.get("error") or clip["status"])
        return self._req("GET", f"/v1/clips/{clip['id']}/audio")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--voice", default="kokoro:af_heart", help="voice id from GET /v1/voices (default kokoro:af_heart)")
    p.add_argument("--emotion", default="happy", help="happy, excited, warm, ... (Kokoro ignores this)")
    p.add_argument("--intensity", type=float, default=0.7)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--engine", default="http://127.0.0.1:8765")
    p.add_argument("--page", default=str(HERE / "index.html") if (HERE / "index.html").exists() else str(HERE / "pip.html"))
    p.add_argument("--sample", action="store_true", help="record only 5 lines, into audio-sample/")
    p.add_argument("--fresh", action="store_true", help="delete existing clips first")
    args = p.parse_args()

    page = Path(args.page)
    lines = load_lines(page)
    out = page.parent / ("audio-sample" if args.sample else "audio")
    if args.sample:
        lines = lines[:: max(1, len(lines) // 5)][:5]
    if args.fresh and out.exists():
        shutil.rmtree(out)
    out.mkdir(exist_ok=True)

    engine = Engine(args.engine, read_token())
    try:
        engine.json("GET", "/v1/voices")
    except urllib.error.URLError as exc:
        sys.exit(f"Can't reach the engine at {args.engine} ({exc}). Start it with: cd engine && uv run narrator-engine serve")

    clips: dict[str, int] = {}
    failed = 0
    for i, text in enumerate(lines, 1):
        key = fnv1a(text)
        path = out / f"{key}.mp3"
        if path.exists():
            clips[key] = 1
            continue
        print(f"[{i}/{len(lines)}] {text}")
        try:
            path.write_bytes(engine.record(text, args))
            clips[key] = 1
        except Exception as exc:  # keep going; the page falls back to the device voice for this line
            failed += 1
            print(f"    failed: {exc}")

    manifest = {"voice": args.voice, "clips": clips}
    (out / "manifest.js").write_text("window.PIP_AUDIO = " + json.dumps(manifest) + ";\n")
    print(f"\n{len(clips)} of {len(lines)} lines recorded in {out}" + (f", {failed} failed" if failed else ""))
    if args.sample:
        print("Listen to the files in audio-sample/, then run without --sample to record them all.")
    else:
        print("Commit and push the audio folder to update the live site.")


if __name__ == "__main__":
    main()
