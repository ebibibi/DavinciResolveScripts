#!/usr/bin/env python3
"""Generate the whole thumbnail with GPT Image, using the presenter's video frame as the face reference.

2026-10-05 review of MS週報 #1: a video frame with headline text laid next to it looked weak.
"Use my face, but generate everything else with AI – a normal YouTube thumbnail is better."
The face photo is passed as a reference image; background, motif, lighting and the Japanese text
are generated as one picture. Then the image is scaled to 1280x720 and the real channel logo is
pasted into the top-right corner the prompt keeps empty (skipped when the head is there anyway).

Never ask the model to change the expression or pose (surprised face, pointing): it then redraws
the face and it stops looking like him. That variant was rejected in the same review.

Usage:
  ai_thumbnail.py work/thumbnail_frame.png --headline "EWS廃止" --sub "Exchange Online" \
      --badge "MS週報" --motif "a cracked Exchange mail server falling apart" [--out out/thumbnail.png]
Exit 0 = written and the whole head is visible, 1 = check failed, 2 = generation failed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_thumbnail  # noqa: E402  (copied next to this script in every job directory)

GPT_IMAGE = Path(os.environ.get(
    "GPT_IMAGE_SCRIPT", Path.home() / ".claude/skills/image-gen/scripts/gpt_image.py"))
LOGO = Path(os.environ.get(
    "THUMBNAIL_LOGO", Path.home() / "presentations/Images/ebi/ebi-icon-circle.png"))
GEN_SIZE = (1536, 864)
OUT_SIZE = (1280, 720)
LOGO_SIZE = 100
LOGO_MARGIN = 16


def face_crop_box(face: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    """Head and shoulders around a face box (x, y, w, h), clamped to the frame."""
    x, y, w, h = face
    return (max(x - int(w * 1.2), 0), max(y - h, 0),
            min(x + w + int(w * 1.2), width), min(y + h * 3, height))


def build_prompt(headline: str, sub: str = "", badge: str = "", motif: str = "") -> str:
    texts = []
    if badge:
        texts.append(f'A very prominent badge at the top-left reading "{badge}", styled like a TV news '
                     "program logo: bold, orange-yellow plate with dark text and a glowing frame. "
                     "It is the second most noticeable element after the headline.")
    texts.append(f'A huge main headline "{headline}" in extra-bold white and orange-yellow letters '
                 "with a thick dark outline.")
    if sub:
        texts.append(f'A smaller line next to the headline: "{sub}".')
    numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    return f"""Create a complete, professional Japanese YouTube tech thumbnail, 16:9 landscape.
Use the man in the reference photo as the presenter, on the right third, looking at the camera.
Keep his face, expression, head shape, hairline, skin and identity EXACTLY as in the photo
(realistic photo, do not stylize, do not beautify, do not change the expression or the pose).
Show his whole head with clear space around the hair; no text or object overlaps his head or face.
Everything else is newly generated: a dramatic dark navy tech background with depth, cinematic rim
lighting, high contrast, one strong accent color (vivid orange-yellow) plus white.
Main motif behind the headline: {motif or "the product of the story, shown changing or breaking"}.
Minimal and uncluttered.
Required text, rendered perfectly and legibly, exactly as written:
{numbered}
No other text, no fake words, no watermark. Keep the bottom-right corner free (video length overlay).
Keep the top-right corner (about 170x170 px) empty background for a logo: the presenter's head stays
clearly below and left of it.
"""


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def logo_keepout(face: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Face box (x, y, w, h) grown for the hair: a little to the sides, more upwards.

    check_thumbnail.head_box grows 30% on every side, which also covers the empty background the
    prompt keeps for the logo and would always push the logo out.
    """
    x, y, w, h = face
    return x - int(w * 0.10), y - int(h * 0.25), x + w + int(w * 0.10), y + h


def pick_logo_corner(head: tuple[int, int, int, int] | None,
                     size: tuple[int, int] = OUT_SIZE) -> tuple[int, int] | None:
    """Top-left corner of the logo in the top-right corner, or None when the head is there.

    Only the top-right corner is reserved in the prompt; the other corners hold the series badge,
    the headline and YouTube's duration overlay, so pasting the logo there covers text.
    """
    width, _ = size
    pos = (width - LOGO_SIZE - LOGO_MARGIN, LOGO_MARGIN)
    box = (pos[0], pos[1], pos[0] + LOGO_SIZE, pos[1] + LOGO_SIZE)
    return None if head is not None and _overlaps(box, head) else pos


def crop_face(frame: Path, dest: Path) -> None:
    bgr = cv2.imread(str(frame))
    if bgr is None:
        raise OSError(f"cannot read {frame}")
    row = check_thumbnail.largest_face(bgr)
    if row is None:
        raise OSError(f"no face in {frame} - pick a frame where he looks at the camera")
    x0, y0, x1, y1 = face_crop_box(tuple(int(v) for v in row[:4]), bgr.shape[1], bgr.shape[0])
    cv2.imwrite(str(dest), bgr[y0:y1, x0:x1])


def generate(prompt: str, face: Path, raw: Path, quality: str) -> None:
    prompt_file = raw.with_suffix(".prompt.txt")
    prompt_file.write_text(prompt, encoding="utf-8")
    subprocess.run(["python3", str(GPT_IMAGE), "--prompt-file", str(prompt_file), "-i", str(face),
                    "-s", f"{GEN_SIZE[0]}x{GEN_SIZE[1]}", "-q", quality, "-o", str(raw)],
                   check=True, timeout=600)


def finish(raw: Path, out: Path) -> None:
    image = Image.open(raw).convert("RGB").resize(OUT_SIZE, Image.LANCZOS)
    row = check_thumbnail.largest_face(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR))
    head = logo_keepout(tuple(int(v) for v in row[:4])) if row is not None else None
    pos = pick_logo_corner(head)
    if pos and LOGO.is_file():
        logo = Image.open(LOGO).convert("RGBA").resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
        image.paste(logo, pos, logo)
    else:
        print("note: logo skipped - the head reaches the top-right corner (or the logo file is missing); "
              "regenerate if the logo matters")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("frame", help="a video frame where he looks at the camera")
    parser.add_argument("--headline", required=True, help="3-7 characters, e.g. EWS廃止")
    parser.add_argument("--sub", default="", help="product name line, e.g. Exchange Online")
    parser.add_argument("--badge", default="", help="series label shown as a big badge, e.g. MS週報")
    parser.add_argument("--motif", default="", help="main visual behind the headline, in English")
    parser.add_argument("--out", default="out/thumbnail.png")
    parser.add_argument("--work", default="work")
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    args = parser.parse_args()
    work, out = Path(args.work), Path(args.out)
    work.mkdir(parents=True, exist_ok=True)
    face, raw = work / "thumbnail_face.png", work / "thumbnail_ai_raw.png"
    try:
        crop_face(Path(args.frame), face)
        generate(build_prompt(args.headline, args.sub, args.badge, args.motif), face, raw, args.quality)
        finish(raw, out)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}")
        return 2
    problems = check_thumbnail.check(out, None)
    if problems:
        print("THUMBNAIL REJECTED:\n- " + "\n- ".join(problems))
        return 1
    print(f"wrote {out} - now look at it: same face as the photo, nothing over the head, text spelt right")
    return 0


if __name__ == "__main__":
    sys.exit(main())
