#!/usr/bin/env python3
"""Keep the real embroidered Microsoft MVP logo on a thumbnail made from his video frame.

The blue MVP shirt (and the navy MVP hoodie) carry an embroidered "MVP / Microsoft Most Valuable
Professional" logo. The image model redraws the shirt and drops or warps it; he asked three times
(2026-11-10, 11-15, 11-21) not to lose it. Instructions in the brief were not enough: a regenerated
thumbnail went out without the logo. So this module enforces it in code.

  find_logo    SIFT features of the reference logo (reference/mvp_logo/shirt_logo.png, cut from a real
               frame) matched in the area below the face, RANSAC similarity transform, then normalised
               cross-correlation of the aligned patch as a second opinion. Gives position and size, so
               nobody types coordinates.
  paste_logo   cuts the logo with a margin of shirt from the source frame, scales it uniformly by the
               face-size ratio, places it at the same offset from the face, colour-matches only the shirt
               fabric around the lettering and feathers only that margin. The logo pixels themselves are
               the real ones: never redrawn, blurred or warped.
  check        the source frame(s) or the recording show the logo -> the thumbnail must show it too.

Usage (in a job directory):
  mvp_logo.py check out/thumbnail.png        sources: work/thumbnail_frame.png, work/thumbnail_ai_frame.png,
                                             work/thumbnail_source.png and frames of input/source.mkv
  mvp_logo.py check THUMB --source FRAME [--video VIDEO]
  mvp_logo.py paste THUMB --source FRAME [--out OUT]
  mvp_logo.py find IMAGE                     prints the detection scores
Exit 0 = ok, 1 = the logo is missing / could not be pasted, 2 = cannot read or nothing to compare with.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_thumbnail  # noqa: E402  (copied next to this script in every job directory)

TEMPLATE = Path(__file__).resolve().parent / "reference/mvp_logo/shirt_logo.png"
TEMPLATE_UPSCALE = 2.0      # more SIFT keypoints on the small embroidery
LOGO_TO_FACE = 0.565        # logo width / face width in the reference frame (shirt logo, seated)
MIN_INLIERS = 12            # logo frames 17-315, frames without the logo 0-6 (2026-11-21 corpus)
MIN_NCC = 0.30              # aligned patch vs reference: logo 0.26-1.00, but no-logo hits need inliers too
SCALE_RANGE = (0.3, 2.0)    # matched size relative to the expected size; outside = degenerate fit
PATCH_MARGIN = 0.15         # shirt around the logo, used for the soft edge (share of the logo size)
VIDEO_SAMPLES = 8


class MvpLogoError(Exception):
    """The logo is required but cannot be pasted or found."""


@dataclass(frozen=True)
class Match:
    inliers: int
    ncc: float
    scale: float
    box: tuple[int, int, int, int]   # x0, y0, x1, y1 in image pixels (clipped)
    quad: tuple[tuple[float, float], ...] = ()   # the logo's own corners in image pixels

    @property
    def found(self) -> bool:
        return (self.inliers >= MIN_INLIERS and self.ncc >= MIN_NCC
                and SCALE_RANGE[0] <= self.scale <= SCALE_RANGE[1])

    def describe(self) -> str:
        where = f", box {self.box}" if self.found else ""
        return (f"{'found' if self.found else 'not found'} (inliers {self.inliers}, need {MIN_INLIERS}; "
                f"ncc {self.ncc:.2f}, need {MIN_NCC}; scale {self.scale:.2f}{where})")


NO_MATCH = Match(0, 0.0, 0.0, (0, 0, 0, 0))
_sift = cv2.SIFT_create()
_clahe = cv2.createCLAHE(2.0, (8, 8))
_reference: tuple | None = None


def _reference_features():
    global _reference
    if _reference is None:
        gray = cv2.imread(str(TEMPLATE), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise OSError(f"cannot read the reference logo {TEMPLATE}")
        gray = cv2.resize(gray, None, fx=TEMPLATE_UPSCALE, fy=TEMPLATE_UPSCALE, interpolation=cv2.INTER_CUBIC)
        keypoints, descriptors = _sift.detectAndCompute(_clahe.apply(gray), None)
        _reference = gray, keypoints, descriptors
    return _reference


def search_area(shape: tuple[int, ...], face: np.ndarray | None) -> tuple[int, int, int, int]:
    """Chest area below the face (x0, y0, x1, y1); the whole image without a face.

    Keeps the MVP award plaque and trophy on the shelf behind him out of the search.
    """
    height, width = shape[:2]
    if face is None:
        return 0, 0, width, height
    x, y, w, h = (float(v) for v in face[:4])
    return (max(int(x - 1.5 * w), 0), min(max(int(y + 0.8 * h), 0), height - 1),
            min(int(x + 2.5 * w), width), height)


def find_logo(bgr: np.ndarray) -> Match:
    template, ref_kp, ref_desc = _reference_features()
    face = check_thumbnail.largest_face(bgr)
    x0, y0, x1, y1 = search_area(bgr.shape, face)
    expected = LOGO_TO_FACE * float(face[2]) if face is not None else template.shape[1] / TEMPLATE_UPSCALE
    zoom = float(np.clip(template.shape[1] / expected, 1.0, 4.0))
    gray = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    if gray.size == 0:
        return NO_MATCH
    area = cv2.resize(gray, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)
    keypoints, descriptors = _sift.detectAndCompute(_clahe.apply(area), None)
    if descriptors is None or len(keypoints) < 4:
        return NO_MATCH
    pairs = cv2.BFMatcher().knnMatch(ref_desc, descriptors, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < 4:
        return Match(len(good), 0.0, 0.0, (0, 0, 0, 0))
    src = np.float32([ref_kp[m.queryIdx].pt for m in good])
    dst = np.float32([keypoints[m.trainIdx].pt for m in good])
    transform, inlier_mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=6)
    if transform is None:
        return Match(0, 0.0, 0.0, (0, 0, 0, 0))
    scale = float(np.hypot(transform[0, 0], transform[1, 0]))
    th, tw = template.shape
    aligned = cv2.warpAffine(area, transform, (tw, th), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)
    ncc = float(cv2.matchTemplate(aligned, template, cv2.TM_CCOEFF_NORMED)[0, 0])
    corners = cv2.transform(np.float32([[[0, 0], [tw, 0], [tw, th], [0, th]]]), transform)[0] / zoom
    height, width = bgr.shape[:2]
    box = (max(int(corners[:, 0].min()) + x0, 0), max(int(corners[:, 1].min()) + y0, 0),
           min(int(np.ceil(corners[:, 0].max())) + x0, width), min(int(np.ceil(corners[:, 1].max())) + y0, height))
    quad = tuple((float(cx) + x0, float(cy) + y0) for cx, cy in corners)
    return Match(int(inlier_mask.sum()), ncc, scale, box, quad)


def _fabric_weight(patch: np.ndarray) -> np.ndarray:
    """1 on the dark shirt fabric, 0 on the white lettering and the diamond, soft in between."""
    lum = cv2.cvtColor(patch.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    threshold, _ = cv2.threshold(lum.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return np.clip((threshold + 20 - lum) / 40, 0, 1)[..., None]


def _match_fabric(patch: np.ndarray, region: np.ndarray, fabric: np.ndarray) -> np.ndarray:
    """Shift the source shirt fabric to the generated shirt's colour (Lab mean and spread)."""
    weight = fabric[..., 0] > 0.9
    if weight.sum() < 20:
        return patch
    lab = cv2.cvtColor(patch.astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    target = cv2.cvtColor(region.astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
    src_mean, src_std = lab[weight].mean(0), lab[weight].std(0) + 1e-3
    gain = np.clip((target.std(0) + 1e-3) / src_std, 0.5, 2.0)
    shifted = (lab - src_mean) * gain + target.mean(0)
    recoloured = cv2.cvtColor(shifted.clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    return patch * (1 - fabric) + recoloured * fabric


def paste_logo(source: np.ndarray, thumb: np.ndarray, logo: Match | None = None) -> np.ndarray:
    """New thumbnail with the source frame's real logo on his shirt. Raises MvpLogoError."""
    logo = logo or find_logo(source)
    if not logo.found:
        raise MvpLogoError(f"no MVP logo in the source frame: {logo.describe()}")
    sh, sw = source.shape[:2]
    if any(not (-2 <= qx <= sw + 2 and -2 <= qy <= sh + 2) for qx, qy in logo.quad):
        raise MvpLogoError("the logo is cut off at the edge of the source frame - "
                           "pick a frame where the whole logo is visible")
    src_face, dst_face = check_thumbnail.largest_face(source), check_thumbnail.largest_face(thumb)
    if src_face is None or dst_face is None:
        raise MvpLogoError("no face in the " + ("source frame" if src_face is None else "thumbnail")
                           + " - the logo is placed relative to the face")
    lx0, ly0, lx1, ly1 = logo.box
    mx, my = int((lx1 - lx0) * PATCH_MARGIN), int((ly1 - ly0) * PATCH_MARGIN)
    px0, py0, px1, py1 = max(lx0 - mx, 0), max(ly0 - my, 0), min(lx1 + mx, sw), min(ly1 + my, sh)
    ratio = float(dst_face[2]) / float(src_face[2])
    src_center = src_face[:2] + src_face[2:4] / 2
    dst_center = dst_face[:2] + dst_face[2:4] / 2
    x = int(round(dst_center[0] + (px0 - src_center[0]) * ratio))
    y = int(round(dst_center[1] + (py0 - src_center[1]) * ratio))
    w, h = max(int(round((px1 - px0) * ratio)), 1), max(int(round((py1 - py0) * ratio)), 1)
    th, tw = thumb.shape[:2]
    if x < 0 or y < 0 or x + w > tw or y + h > th:
        raise MvpLogoError(f"the logo would land outside the thumbnail ({x},{y} {w}x{h} on {tw}x{th}) - "
                           "regenerate with his chest in view")
    interp = cv2.INTER_AREA if ratio < 1 else cv2.INTER_CUBIC
    patch = cv2.resize(source[py0:py1, px0:px1], (w, h), interpolation=interp).astype(np.float32)
    region = thumb[y:y + h, x:x + w].astype(np.float32)
    fabric = _fabric_weight(patch)
    matched = _match_fabric(patch, region, fabric)
    # Opaque on the logo itself (its own frame, rotated with the shirt), feathered across the margin.
    inner = np.zeros((h, w), np.uint8)
    quad = np.int32([[(qx - px0) * ratio, (qy - py0) * ratio] for qx, qy in logo.quad])
    cv2.fillConvexPoly(inner, quad, 1)
    margin = max(int(min(mx, my) * ratio), 2)
    alpha = cv2.GaussianBlur(cv2.dilate(inner, np.ones((3, 3), np.uint8), iterations=max(margin // 3, 1))
                             .astype(np.float32), (0, 0), margin / 3)
    alpha = np.maximum(alpha, inner.astype(np.float32))[..., None]
    out = thumb.copy()
    out[y:y + h, x:x + w] = (matched * alpha + region * (1 - alpha)).clip(0, 255).astype(np.uint8)
    after = find_logo(out)
    if not after.found:
        raise MvpLogoError(f"pasted the logo but cannot find it afterwards: {after.describe()}")
    return out


def ensure_logo(source: np.ndarray, thumb: np.ndarray) -> tuple[np.ndarray, Match]:
    """Paste the real logo when the source frame shows it; otherwise return the thumbnail unchanged."""
    logo = find_logo(source)
    return (paste_logo(source, thumb, logo) if logo.found else thumb), logo


def video_frames(video: Path, samples: int = VIDEO_SAMPLES) -> list[np.ndarray]:
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
                           capture_output=True, text=True, check=True, timeout=120)
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    frames = []
    for i in range(samples):
        grab = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{duration * (i + 0.5) / samples:.2f}",
                               "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                              capture_output=True, check=True, timeout=300)
        image = cv2.imdecode(np.frombuffer(grab.stdout, np.uint8), cv2.IMREAD_COLOR)
        if image is not None:
            frames.append(image)
    return frames


def default_sources(thumbnail: Path) -> tuple[list[Path], Path | None]:
    """Frames and recording of the job the thumbnail belongs to (<job>/out/thumbnail.png)."""
    job = thumbnail.resolve().parent.parent
    frames = [job / "work" / n for n in ("thumbnail_frame.png", "thumbnail_ai_frame.png", "thumbnail_source.png")]
    video = job / "input" / "source.mkv"
    return [f for f in frames if f.is_file()], (video if video.exists() else None)


def check(thumbnail: Path, sources: list[tuple[str, np.ndarray]]) -> list[str]:
    """Problems: empty when the thumbnail keeps the logo or no source shows one."""
    thumb = cv2.imread(str(thumbnail))
    if thumb is None:
        raise OSError(f"cannot read {thumbnail}")
    with_logo = []
    for name, image in sources:
        match = find_logo(image)
        print(f"source {name}: MVP logo {match.describe()}")
        if match.found:
            with_logo.append(name)
    if not with_logo:
        return []
    result = find_logo(thumb)
    print(f"thumbnail {thumbnail}: MVP logo {result.describe()}")
    if result.found:
        return []
    return [f"{len(with_logo)} of {len(sources)} source images (e.g. {with_logo[0]}) show the real MVP logo "
            f"but the thumbnail does not - paste it: python3 mvp_logo.py paste {thumbnail} --source <frame>"]


def _load_sources(args: argparse.Namespace) -> list[tuple[str, np.ndarray]]:
    frames = [Path(s) for s in args.source or []]
    video = Path(args.video) if args.video else None
    if not frames and video is None:
        frames, video = default_sources(Path(args.thumbnail))
    sources = []
    for frame in frames:
        image = cv2.imread(str(frame))
        if image is None:
            raise OSError(f"cannot read {frame}")
        sources.append((str(frame), image))
    if video is not None:
        try:
            sources += [(f"{video} sample {i + 1}", f) for i, f in enumerate(video_frames(video))]
        except (subprocess.SubprocessError, ValueError, KeyError) as exc:
            raise OSError(f"cannot sample frames from {video}: {exc}") from exc
    if not sources:
        raise OSError("nothing to compare with - pass --source <the frame the thumbnail was made from>")
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="reject a thumbnail that lost the logo the source shows")
    c.add_argument("thumbnail")
    c.add_argument("--source", action="append", help="frame the thumbnail was made from (repeatable)")
    c.add_argument("--video", help="the recording; frames are sampled from it")
    p = sub.add_parser("paste", help="paste the source frame's real logo onto a thumbnail")
    p.add_argument("thumbnail")
    p.add_argument("--source", required=True)
    p.add_argument("--out", help="default: overwrite the thumbnail")
    f = sub.add_parser("find", help="print the detection scores for an image")
    f.add_argument("image")
    args = parser.parse_args()
    try:
        if args.command == "find":
            image = cv2.imread(args.image)
            if image is None:
                raise OSError(f"cannot read {args.image}")
            match = find_logo(image)
            print(f"MVP logo {match.describe()}")
            return 0 if match.found else 1
        if args.command == "paste":
            source, thumb = cv2.imread(args.source), cv2.imread(args.thumbnail)
            if source is None or thumb is None:
                raise OSError(f"cannot read {args.source if source is None else args.thumbnail}")
            out = Path(args.out or args.thumbnail)
            cv2.imwrite(str(out), paste_logo(source, thumb))
            print(f"wrote {out} - compare the logo with the frame at full size")
            return 0
        problems = check(Path(args.thumbnail), _load_sources(args))
    except MvpLogoError as exc:
        print(f"MVP LOGO: {exc}")
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 2
    if problems:
        print("THUMBNAIL REJECTED:\n- " + "\n- ".join(problems))
        return 1
    print("mvp logo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
