#!/usr/bin/env python3
"""Check that the presenter's whole head is visible on a thumbnail.

Rejects a thumbnail when
  - no face is detected (hidden, cut off, too small or not frontal),
  - the face is an extreme close-up,
  - the head (face box grown for hair, ears and chin) runs off the canvas,
  - with --source: anything was laid over the head (headline glyphs, panels, gradients, the logo).
    The unmodified video frame the photo was cut from is aligned onto the thumbnail (face landmarks,
    then ECC on the face) and the head region is compared pixel by pixel.

2026-10-04: a thumbnail with a headline glyph in the hair/ear and a gradient over half of the face
passed a face-detection-only check, and colour heuristics confused the wooden door behind the
presenter with the accent colour. Only the comparison with the source frame separates them
reliably (21% of the head changed vs 0%), so save the frame you used and pass it with --source.

Writes <thumbnail>.faces.png (detected face and head boxes) for a visual check.

Usage: check_thumbnail.py out/thumbnail.png [--source work/thumbnail_source.png]
Exit 0 = ok, 1 = rejected, 2 = cannot read.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")
YUNET_PATH = Path.home() / ".cache/opencv/face_detection_yunet_2023mar.onnx"
MIN_SCORE = 0.8
MIN_FACE_FRACTION = 0.15  # face height relative to thumbnail height
MAX_FACE_FRACTION = 0.60  # bigger than this is an extreme close-up
HEAD_GROW = 0.30          # grow the face box by this much on every side for hair, ears and chin
DIFF_LEVEL = 40           # grey-level difference that counts as "something drawn over the photo"
MAX_COVERED = 0.03        # share of the head that may differ from the source frame


def yunet_model() -> Path:
    """OpenCV's YuNet face detector (the Haar cascades are gone in OpenCV 5). Downloaded once."""
    if not YUNET_PATH.is_file():
        YUNET_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
    return YUNET_PATH


def largest_face(bgr: np.ndarray) -> np.ndarray | None:
    """YuNet row for the largest face: x, y, w, h, 5 landmarks (x, y), score."""
    height, width = bgr.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(yunet_model()), "", (width, height), MIN_SCORE)
    _, found = detector.detect(bgr)
    if found is None:
        return None
    rows = [r for r in found if r[3] >= height * MIN_FACE_FRACTION]
    return max(rows, key=lambda r: r[2] * r[3]) if rows else None


def head_box(face: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = face
    gx, gy = int(w * HEAD_GROW), int(h * HEAD_GROW)
    return x - gx, y - gy, x + w + gx, y + h + gy


def covered_share(thumb: np.ndarray, thumb_face: np.ndarray, source: np.ndarray,
                  head: tuple[int, int, int, int]) -> float:
    """Share of the head that differs from the source frame aligned onto the thumbnail."""
    src_face = largest_face(source)
    if src_face is None:
        raise OSError("no face in the source frame")
    height, width = thumb.shape[:2]
    coarse, _ = cv2.estimateAffinePartial2D(src_face[4:14].reshape(5, 2), thumb_face[4:14].reshape(5, 2))
    thumb_gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY).astype(np.float32)
    warped = cv2.warpAffine(cv2.cvtColor(source, cv2.COLOR_BGR2GRAY).astype(np.float32), coarse, (width, height))
    x, y, w, h = (int(v) for v in thumb_face[:4])
    mask = np.zeros((height, width), np.uint8)
    mask[max(y, 0):y + h, max(x, 0):x + w] = 255
    fine = np.eye(2, 3, dtype=np.float32)
    try:  # landmarks are only good to a few per cent; refine on the face itself
        _, fine = cv2.findTransformECC(thumb_gray, warped, fine, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), mask, 5)
    except cv2.error:
        pass
    aligned = cv2.warpAffine(warped, fine, (width, height), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    x0, y0, x1, y1 = head
    region = (slice(max(y0, 0), min(y1, height)), slice(max(x0, 0), min(x1, width)))
    a = cv2.GaussianBlur(thumb_gray[region], (5, 5), 0)
    b = cv2.GaussianBlur(aligned[region], (5, 5), 0)
    return float((np.abs(a - b) > DIFF_LEVEL).mean())


def check(path: Path, source_path: Path | None) -> list[str]:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise OSError(f"cannot read {path}")
    height, width = bgr.shape[:2]
    debug = bgr.copy()
    row = largest_face(bgr)
    if row is None:
        cv2.imwrite(str(path.with_suffix(".faces.png")), debug)
        return ["no face detected - the face is hidden, cut off, too small or not frontal"]
    face = tuple(int(v) for v in row[:4])
    x, y, w, h = face
    head = head_box(face)
    x0, y0, x1, y1 = head
    cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 3)
    cv2.rectangle(debug, (x0, y0), (x1, y1), (0, 200, 255), 2)
    cv2.imwrite(str(path.with_suffix(".faces.png")), debug)
    problems = []
    if h > height * MAX_FACE_FRACTION:
        problems.append(f"extreme close-up ({h / height:.0%} of the height, max {MAX_FACE_FRACTION:.0%})")
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        problems.append(f"head runs off the canvas (head box {x0},{y0}-{x1},{y1} on {width}x{height})")
    if source_path is not None:
        source = cv2.imread(str(source_path))
        if source is None:
            raise OSError(f"cannot read {source_path}")
        share = covered_share(bgr, row, source, head)
        if share > MAX_COVERED:
            problems.append(f"{share:.0%} of the head differs from the source frame - "
                            "text, a panel, a gradient or the logo is over the head")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("thumbnail")
    parser.add_argument("--source", help="the unmodified video frame the face photo was cut from")
    args = parser.parse_args()
    path = Path(args.thumbnail)
    try:
        problems = check(path, Path(args.source) if args.source else None)
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 2
    if problems:
        print("THUMBNAIL REJECTED:\n- " + "\n- ".join(problems))
        print(f"see {path.with_suffix('.faces.png')}")
        return 1
    if not args.source:
        print("note: without --source nothing over the head can be detected; look at the .faces.png")
    print(f"thumbnail ok: whole head visible (see {path.with_suffix('.faces.png')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
