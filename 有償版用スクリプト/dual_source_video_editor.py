#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Build one timeline from a slide recording and a camera recording.

The recording folder holds the PowerPoint capture as an `.mkv` and the green
screen camera as an `.mp4`. This entry point aligns them by audio, cuts both by
the same silence list so they cannot drift, places them on V1 and V2 with the
camera microphone as the only audio, and applies the measured placement.

Smooth Cut and the green screen key stay manual, because the DaVinci Resolve
scripting API can add neither transitions nor Edit page effects.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audio_sync
import dual_source
import resolve_session

TEMPLATE_NAME = "テンプレート.drp"
CUT_LIST_NAME = "_auto_editor_cuts.json"

# OneDriveのフォルダ名は過去に変わっているため、実在する方を使う
RECORDING_DIR_CANDIDATES = [
    r'C:\Users\masah\OneDrive - Masahiko Ebisuda (1)\Youtube動画作成場所\!OBS録画',
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!OBS録画',
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!OBS録画',
]

ENDING_VIDEO_CANDIDATES = [
    r'C:\Users\masah\OneDrive - Masahiko Ebisuda (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
]

OPENING_CLIP_MARKER = "01_EBI_CHAN_OP"

# 同じv3 JSONを出す --export の名前と、その版が強制する拡張子。新しい版から試す。
# 新版は --output の拡張子を無視して .v3 に書き換えるので、こちらから合わせる。
EXPORT_FORMATS = (("v3", ".v3"), ("json", ".json"))


def first_existing_path(candidates):
    """候補のうち実在する最初のパスを返す"""
    return next((path for path in candidates if os.path.exists(path)), None)


def find_opening_end_frame(timeline) -> int:
    """V1のオープニングクリップの終了フレームを返す（無ければ0）"""
    print("オープニングクリップを探します")
    try:
        items = timeline.GetItemsInTrack("video", 1)
        print(f"V1トラックのアイテム数: {len(items)}")
        for _, item in items.items():
            name = item.GetName()
            print(f"V1トラックのクリップ: {name}")
            if OPENING_CLIP_MARKER in name:
                end_frame = item.GetEnd()
                print(f"オープニングクリップの終了フレーム: {end_frame}")
                return end_frame
    except Exception as error:
        print(f"V1トラックのアイテム取得でエラー: {error}")

    print("オープニングクリップが見つかりません。タイムラインの先頭に配置します。")
    return 0


def clear_previous_cut_lists(output_path):
    """前回の書き出しを消す。古いファイルを読んで気付かない事故を防ぐ。"""
    output_path = Path(output_path)
    for stale in output_path.parent.glob(output_path.stem + ".*"):
        stale.unlink()


def read_cut_list(path):
    """カットリストを読む。日本語パスの文字コードで転ばないようにする。

    Windowsのauto-editorはJSONの中の入力パスをコードページ(CP932)で書き出すため、
    UTF-8として読めないことがある。必要なのは数値だけなので、パスが化けても構わない。
    """
    raw = Path(path).read_bytes()
    for encoding in ("utf-8", "cp932"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", "replace"))


def decode_output(raw):
    """auto-editorの出力を文字列にする。読めない字があっても捨てない。

    エラー本文は版の判定にも使うので、1バイト化けたくらいで失えない。
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for encoding in ("utf-8", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def locate_cut_list(output_path):
    """auto-editorが実際に書いたファイルを探す

    新しい版は --output の拡張子を書き換えるので、頼んだ名前に無いことがある。
    """
    output_path = Path(output_path)
    if output_path.exists():
        return output_path
    written = sorted(output_path.parent.glob(output_path.stem + ".*"))
    return written[0] if written else None


def run_auto_editor_cut_list(camera_path, output_path):
    """auto-editorを実行し、カットリスト（v3 JSON）を得る

    同じv3 JSONを出す指定の名前がバージョンで変わっている。新しい版は "v3"、
    古い版は "json" しか受け付けないので、順に試す。
    """
    output_path = Path(output_path)
    clear_previous_cut_lists(output_path)

    for export_format, suffix in EXPORT_FORMATS:
        requested = output_path.with_suffix(suffix)
        command = [
            "auto-editor",
            str(camera_path),
            "--margin", dual_source.SILENCE_MARGIN,
            "--edit", dual_source.SILENCE_EDIT,
            "--export", export_format,
            "--output", str(requested),
            "--no-open",
        ]
        print(f"実行コマンド: {' '.join(command)}")
        try:
            # 出力は生バイトで受ける。text=True はコンソールのコードページで
            # 解釈するため、日本語パスを含むauto-editorの出力で復号に失敗し、
            # 読み取りスレッドごと死んでエラー本文が取れなくなる。
            subprocess.run(command, capture_output=True, check=True)
        except subprocess.CalledProcessError as error:
            stderr = decode_output(error.stderr)
            if "Invalid export format" in stderr or "Export must be" in stderr:
                print(f"  この版のauto-editorは --export {export_format} を知りません")
                continue
            print(f"✗ auto-editor実行失敗: {error}")
            print(f"エラー出力: {stderr}")
            return None
        except FileNotFoundError:
            print("✗ auto-editorが見つかりません")
            return None

        written = locate_cut_list(requested)
        if written is None:
            print(f"✗ auto-editorはカットリストを書きませんでした: {requested}")
            return None
        if written != requested:
            print(f"  auto-editorは {written.name} に書き出しました")
        return read_cut_list(written)

    names = " / ".join(name for name, _ in EXPORT_FORMATS)
    print(f"✗ auto-editorが {names} のどれも受け付けませんでした")
    return None


ZERO_TIMECODE = "00:00:00:00"


def normalize_start_timecode(media_pool_item) -> bool:
    """素材の開始タイムコードを0にする。これをしないと配置位置が丸ごとずれる。

    AppendToTimeline の startFrame は素材の先頭からの位置ではなく、素材の
    タイムコードを基準に解釈される。カメラは撮影時刻のタイムコード
    （実測 17:54:31;54、ドロップフレーム）を持つため、頼んだ位置が約64.5秒
    ずれて別の場面が並び、映像も音声も無音カットの結果と一致しなくなる。
    画面録画は 00:00:00:00 なので無傷であり、2つの映像が噛み合わない原因は
    ここだけにあった。
    """
    try:
        current = media_pool_item.GetClipProperty("Start TC")
    except Exception:
        current = None
    if current in (ZERO_TIMECODE, "00:00:00;00"):
        return True

    try:
        changed = bool(media_pool_item.SetClipProperty("Start TC", ZERO_TIMECODE))
    except Exception as error:
        print(f"✗ 開始タイムコードを0にできません（{current}）: {error}")
        return False
    if not changed:
        print(f"✗ 開始タイムコードを0にできませんでした（{current}）")
        return False
    print(f"✓ 開始タイムコードを {current} から {ZERO_TIMECODE} に直しました")
    return True


def clip_frame_rate(media_pool_item, fallback):
    """素材のフレームレートを読む（読めなければfallback）"""
    try:
        frame_rate = float(media_pool_item.GetClipProperty("FPS"))
    except (TypeError, ValueError, AttributeError):
        return fallback
    return frame_rate if frame_rate > 0 else fallback


def append_clips_with_retry(media_pool, clip_infos, max_retries=3, delay=2):
    """クリップをタイムラインに追加（リトライ機能付き）"""
    for attempt in range(max_retries):
        print(f"クリップ追加試行 {attempt + 1}/{max_retries}...")
        try:
            appended = media_pool.AppendToTimeline(clip_infos)
            if appended:
                print(f"  ✓ クリップ追加成功（{len(appended)}クリップ）")
                return appended
            print(f"  AppendToTimelineが空を返しました（試行 {attempt + 1}）")
        except Exception as error:
            print(f"  クリップ追加エラー（試行 {attempt + 1}）: {error}")

        if attempt < max_retries - 1:
            time.sleep(delay)

    print(f"✗ {max_retries}回の試行すべてが失敗しました")
    return None


def ensure_video_tracks(timeline, required) -> bool:
    """必要な本数のビデオトラックを確保する"""
    while timeline.GetTrackCount("video") < required:
        if not timeline.AddTrack("video"):
            print("✗ ビデオトラックを追加できませんでした")
            return False
    return True


def apply_clip_properties(items, properties, label) -> int:
    """タイムラインアイテム群に同じ変形設定を適用する"""
    applied = 0
    for item in items:
        try:
            if item.SetProperty(dict(properties)):
                applied += 1
        except Exception as error:
            print(f"  {label}の変形設定でエラー: {error}")
            break
    print(f"✓ {label}の配置を{applied}/{len(items)}クリップに適用しました")
    return applied


def append_ending_video(media_pool, record_frame) -> bool:
    """エンディング動画をV1の末尾に追加する"""
    ending_video_path = first_existing_path(ENDING_VIDEO_CANDIDATES)
    if not ending_video_path:
        print("! エンディング動画が見つかりません（スキップ）")
        return False

    ending_clips = media_pool.ImportMedia([ending_video_path])
    if not ending_clips:
        print("✗ エンディング動画のインポートに失敗")
        return False

    ending_clip = ending_clips[0]
    normalize_start_timecode(ending_clip)
    try:
        ending_frames = int(ending_clip.GetClipProperty("Frames"))
        appended = media_pool.AppendToTimeline([{
            "mediaPoolItem": ending_clip,
            "startFrame": 0,
            "endFrame": ending_frames,
            "recordFrame": record_frame,
            "mediaType": dual_source.VIDEO_ONLY,
            "trackIndex": dual_source.SLIDES_TRACK,
        }])
    except Exception as error:
        print(f"✗ エンディング動画追加エラー: {error}")
        return False

    if not appended:
        print("✗ エンディング動画の追加に失敗")
        return False
    print("✓ エンディング動画を追加しました")
    return True


def build_dual_source_timeline(project, media_pool, timeline, pair, start_frame) -> bool:
    """mkv=V1 / mp4=V2 の2ソースタイムラインを組み立てる"""
    print(f"✓ 画面録画: {pair.slides.name}")
    print(f"✓ カメラ録画: {pair.camera.name}")

    frame_rate = resolve_session.timeline_frame_rate(timeline)
    print(f"✓ タイムラインのフレームレート: {frame_rate}")

    # 音声で2本の録画を合わせる。一致しなければここで止める。
    try:
        sync = audio_sync.estimate_offset(pair.slides, pair.camera)
    except audio_sync.AudioSyncError as error:
        print(f"✗ 音声同期に失敗: {error}")
        return False
    print(
        f"✓ 音声同期: 画面録画の先頭はカメラの {sync.offset_seconds:.3f} 秒地点"
        f"（確度 {sync.confidence:.2f}）"
    )

    document = run_auto_editor_cut_list(pair.camera, pair.folder / CUT_LIST_NAME)
    if document is None:
        return False

    try:
        segments = dual_source.parse_cut_list(document)
        cut_frame_rate = float(dual_source.cut_list_frame_rate(document))
    except dual_source.DualSourceError as error:
        print(f"✗ カットリストを読めません: {error}")
        return False

    print(f"✓ 無音カット後のセグメント数: {len(segments)}")

    imported = media_pool.ImportMedia([str(pair.slides), str(pair.camera)])
    if not imported or len(imported) < 2:
        print("✗ 素材のインポートに失敗しました")
        return False
    items_by_name = {item.GetName(): item for item in imported}
    slides_item = items_by_name.get(pair.slides.name)
    camera_item = items_by_name.get(pair.camera.name)
    if slides_item is None or camera_item is None:
        print("✗ インポートした素材を特定できませんでした")
        return False

    # 位置の計算はすべて素材の先頭からのフレーム数で行うので、先にタイムコードを
    # 揃える。ここを飛ばすとカメラだけ別の場面が並ぶ。
    if not all(normalize_start_timecode(item) for item in (slides_item, camera_item)):
        print("✗ 素材のタイムコードを揃えられないため中止します")
        return False

    try:
        slides_frame_count = int(slides_item.GetClipProperty("Frames"))
    except (TypeError, ValueError):
        slides_frame_count = None

    # タイムラインと素材のfpsは一致しない前提で、秒に直してから配置する
    rates = dual_source.FrameRates(
        timeline=frame_rate,
        slides=clip_frame_rate(slides_item, frame_rate),
        camera=clip_frame_rate(camera_item, cut_frame_rate),
        cut_list=cut_frame_rate,
    )
    print(
        f"✓ フレームレート: タイムライン {rates.timeline} / 画面録画 {rates.slides} / "
        f"カメラ {rates.camera} / カットリスト {rates.cut_list}"
    )

    try:
        plan = dual_source.build_placements(
            segments,
            rates=rates,
            slides_offset_seconds=sync.offset_seconds,
            timeline_start_frame=start_frame,
            slides_frame_count=slides_frame_count,
        )
    except dual_source.DualSourceError as error:
        print(f"✗ タイムラインを組み立てられません: {error}")
        return False
    print(f"✓ 配置計画: {plan.describe()}")
    placements = plan.placements

    if not ensure_video_tracks(timeline, dual_source.CAMERA_TRACK):
        return False

    project.SetCurrentTimeline(timeline)
    media_by_role = {
        "slides": slides_item,
        "camera": camera_item,
        "camera_audio": camera_item,
    }
    clip_infos = [p.to_clip_info(media_by_role[p.role]) for p in placements]
    appended = append_clips_with_retry(media_pool, clip_infos)
    if not appended:
        print("✗ クリップの配置に失敗しました")
        return False

    # 戻り値の並びは渡した順と同じなので、役割ごとに変形設定を分けられる
    slide_items = [
        item for placement, item in zip(placements, appended)
        if placement.role == "slides" and item
    ]
    camera_items = [
        item for placement, item in zip(placements, appended)
        if placement.role == "camera" and item
    ]
    apply_clip_properties(slide_items, dual_source.SLIDES_PROPERTIES, "画面録画")
    apply_clip_properties(camera_items, dual_source.CAMERA_PROPERTIES, "カメラ")

    append_ending_video(media_pool, plan.end_frame)
    return True


def resolve_recording_dir(explicit):
    """使用する録画フォルダを決める"""
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    return first_existing_path(RECORDING_DIR_CANDIDATES)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recording-dir",
        help="OBSの録画フォルダ（省略時は既定の候補から探す）",
    )
    parser.add_argument(
        "--folder",
        help="処理するサブフォルダを直接指定する（省略時は最新のペアを使う）",
    )
    arguments = parser.parse_args(argv)

    print("DaVinci Resolve 2ソース自動編集（画面録画 + カメラ）開始")

    if arguments.folder:
        pair = dual_source.find_recording_pair(Path(arguments.folder))
        if pair is None:
            print(f"✗ mkv 1本 + mp4 1本のフォルダではありません: {arguments.folder}")
            return 1
    else:
        recording_dir = resolve_recording_dir(arguments.recording_dir)
        if not recording_dir:
            print("✗ OBS録画フォルダが見つかりません")
            return 1
        print(f"✓ 録画フォルダ: {recording_dir}")

        pair = dual_source.find_latest_recording_pair(Path(recording_dir))
        if pair is None:
            print("✗ mkv 1本 + mp4 1本のサブフォルダが見つかりません")
            print("  単一ソースの録画は run_auto_video_editor.ps1 を使ってください")
            return 1
    print(f"✓ 対象フォルダ: {pair.folder}")

    try:
        resolve = resolve_session.connect()
        project_manager = resolve.GetProjectManager()
        if project_manager is None:
            print("✗ ProjectManager取得失敗")
            return 1

        template_path = Path(__file__).resolve().parent / TEMPLATE_NAME
        project_name = f"自動編集_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project = resolve_session.create_project_from_template(
            project_manager, template_path, project_name
        )
        media_pool = project.GetMediaPool()
        if not media_pool:
            print("✗ MediaPool取得失敗")
            return 1
        timeline = resolve_session.open_main_timeline(project)
    except resolve_session.ResolveSessionError as error:
        print(f"✗ {error}")
        return 1

    start_frame = find_opening_end_frame(timeline)
    if not build_dual_source_timeline(project, media_pool, timeline, pair, start_frame):
        print("✗ 2ソース編集に失敗しました")
        return 1

    resolve_session.finish(resolve, project, timeline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
