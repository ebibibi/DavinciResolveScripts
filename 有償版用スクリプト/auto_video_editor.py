#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DaVinci Resolve自動動画編集スクリプト（有償版）
- テンプレートプロジェクトから新規プロジェクトを作成
- auto-editorで無音部分を自動カット
- エンディング動画を自動追加
- mainタイムラインに統合

録画フォルダの中に「mkv 1本 + mp4 1本」のサブフォルダがある場合は、
2ソースモード（mkv=PowerPoint画面=V1 / mp4=グリーンバック=V2）で動作する。
それ以外の入力に対する挙動は従来どおり変わらない。
"""

import os
import sys
import time
import json
import subprocess
import platform
import glob
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio_sync
import dual_source

print("DaVinci Resolve自動動画編集スクリプト（有償版）開始")

# OneDriveのフォルダ名は過去に変わっているため、実在する方を使う
WORKING_DIR_CANDIDATES = [
    r'C:\Users\masah\OneDrive - Masahiko Ebisuda (1)\Youtube動画作成場所\!OBS録画',
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!OBS録画',
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!OBS録画',
]

ENDING_VIDEO_CANDIDATES = [
    r'C:\Users\masah\OneDrive - Masahiko Ebisuda (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
]


def first_existing_path(candidates):
    """候補のうち実在する最初のパスを返す"""
    return next((path for path in candidates if os.path.exists(path)), None)

def add_resolve_api_to_sys_path():
    """DaVinci Resolve APIのパスをsys.pathに追加"""
    candidates = []

    env_api = os.environ.get("RESOLVE_SCRIPT_API")
    if env_api:
        candidates.append(os.path.join(env_api, "Modules"))

    if platform.system() == "Windows":
        candidates += [
            r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Developer\Scripting\Modules",
        ]
    elif platform.system() == "Darwin":
        candidates += [
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
        ]
    else:  # Linux
        candidates += [
            "/opt/resolve/Developer/Scripting/Modules",
            "/home/resolve/Developer/Scripting/Modules",
        ]

    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
            print(f"✓ APIパス追加: {p}")

def launch_resolve_if_needed():
    """必要に応じてDaVinci Resolveを起動"""
    exe_candidates = []
    if platform.system() == "Windows":
        exe_candidates = [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
            r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve\Resolve.exe"
        ]
    elif platform.system() == "Darwin":
        exe_candidates = ["/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"]
    else:
        exe_candidates = ["/opt/resolve/bin/resolve", "/usr/bin/resolve"]

    for exe in exe_candidates:
        if os.path.isfile(exe):
            try:
                print(f"DaVinci Resolveを起動中: {exe}")
                subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception as e:
                print(f"起動失敗: {e}")
    return False

def get_resolve_with_retry(bmd, retries=60, interval=1):
    """リトライ機能付きでDaVinci Resolveに接続"""
    print("DaVinci Resolveへの接続を試行中...")
    for attempt in range(retries):
        resolve = bmd.scriptapp("Resolve")
        if resolve:
            print(f"✓ 接続成功（試行 {attempt + 1}/{retries}）")
            return resolve
        if attempt < retries - 1:
            print(f"接続試行 {attempt + 1}/{retries}... 待機中")
            time.sleep(interval)
    return None

def make_unique_name(pm, base_name: str) -> str:
    """プロジェクト名の重複を回避"""
    try:
        existing = set(pm.GetProjectListInCurrentFolder() or [])
    except Exception:
        existing = set()

    if base_name not in existing:
        return base_name

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_{ts}"

def run_auto_editor(working_dir):
    """auto-editorを実行"""
    print("auto-editorを実行中...")
    os.chdir(working_dir)

    # 最新の .mkv / .mp4 ファイルを取得
    video_files = glob.glob("*.mkv") + glob.glob("*.mp4")
    if not video_files:
        print("✗ mkv/mp4ファイルが見つかりません")
        return False

    latest_file = max(video_files, key=os.path.getmtime)
    print(f"✓ 処理対象ファイル: {latest_file}")

    command = [
        "auto-editor",
        str(Path(working_dir) / latest_file),
        "--margin", "0.2sec",
        "--edit", "audio:threshold=3%",
        "--export", "resolve"
    ]

    command_str = ' '.join(command)
    print(f"実行コマンド: {command_str}")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print("✓ auto-editor実行成功")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ auto-editor実行失敗: {e}")
        print(f"エラー出力: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ auto-editorが見つかりません")
        return False

def create_project_from_template(pm, template_path, project_name):
    """テンプレートから新しいプロジェクトを作成"""
    print(f"テンプレートからプロジェクトを作成: {project_name}")

    # プロジェクト名の重複を回避
    safe_name = make_unique_name(pm, project_name)
    print(f"使用するプロジェクト名: {safe_name}")

    # ImportProjectの第2引数を使用（ChatGPTスクリプト参考）
    try:
        print(f"テンプレートインポート試行: {template_path}")
        ok = pm.ImportProject(template_path, safe_name)
        if ok:
            print("✓ テンプレートインポート成功（第2引数使用）")
            return safe_name
    except TypeError:
        print("第2引数がサポートされていません。フォールバック処理を実行...")

        # フォールバック: 第2引数なしでインポート
        ok = pm.ImportProject(template_path)
        if ok:
            # インポートされたプロジェクトを探して改名
            base_name = os.path.splitext(os.path.basename(template_path))[0]
            project = pm.LoadProject(base_name)
            if project:
                project.SetName(safe_name)
                print(f"✓ プロジェクト名を変更: {safe_name}")
                return safe_name

    print("✗ テンプレートインポート失敗")
    return None

def frame_to_timecode(timeline, frame):
    """フレーム番号をタイムコード文字列(HH:MM:SS:FF)に変換する。

    Resolve APIのTimelineにはSetCurrentFrame()が無く、再生ヘッドの移動は
    SetCurrentTimecode()のみ。タイムラインのフレームレートを使って変換する。
    """
    # タイムラインのフレームレートを取得（例: "30.0", "29.97"）
    try:
        fps_raw = timeline.GetSetting("timelineFrameRate")
        fps = int(round(float(fps_raw)))
    except Exception:
        fps = 30  # 取得失敗時のフォールバック
    if fps <= 0:
        fps = 30

    frame = int(frame)
    f = frame % fps
    total_seconds = frame // fps
    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

def append_clips_with_retry(media_pool, clips_to_append, max_retries=3, delay=2):
    """
    クリップをタイムラインに追加（リトライ機能付き）
    """
    for attempt in range(max_retries):
        try:
            print(f"クリップ追加試行 {attempt + 1}/{max_retries}...")

            # オブジェクトの有効性を確認
            if media_pool is None:
                print(f"  MediaPoolがNoneです（試行 {attempt + 1}）")
                time.sleep(delay)
                continue

            # AppendToTimelineを実行
            result = media_pool.AppendToTimeline(clips_to_append)

            if result is not None:
                print(f"  ✓ クリップ追加成功（試行 {attempt + 1}）")
                return result
            else:
                print(f"  AppendToTimelineがNoneを返しました（試行 {attempt + 1}）")

        except TypeError as e:
            if "'NoneType' object is not callable" in str(e):
                print(f"  NoneTypeエラー発生（試行 {attempt + 1}）: {e}")
                if attempt < max_retries - 1:
                    print(f"  {delay}秒待機してリトライします...")
                    time.sleep(delay)
                    continue
            else:
                print(f"  予期しないTypeError（試行 {attempt + 1}）: {e}")
                break
        except Exception as e:
            print(f"  予期しないエラー（試行 {attempt + 1}）: {e}")
            break

        if attempt < max_retries - 1:
            print(f"  {delay}秒待機してリトライします...")
            time.sleep(delay)

    print(f"✗ {max_retries}回の試行すべてが失敗しました")
    return False

def timeline_frame_rate(timeline):
    """タイムラインのフレームレートを取得（取得失敗時は30）"""
    try:
        fps = float(timeline.GetSetting("timelineFrameRate"))
    except Exception:
        return 30.0
    return fps if fps > 0 else 30.0


def find_opening_end_frame(main_timeline):
    """V1のオープニングクリップの終了フレームを返す（無ければ0）"""
    print("オープニングクリップを探します")
    try:
        items_in_track = main_timeline.GetItemsInTrack("video", 1)
        print(f"V1トラックのアイテム数: {len(items_in_track)}")
        for _, item in items_in_track.items():
            clip_name = item.GetName()
            print(f"V1トラックのクリップ: {clip_name}")
            if "01_EBI_CHAN_OP" in clip_name:
                start_frame = item.GetEnd()
                print(f"オープニングクリップが見つかりました。終了フレーム: {start_frame}")
                return start_frame
    except Exception as e:
        print(f"V1トラックのアイテム取得でエラー: {e}")

    print("オープニングクリップが見つかりません。タイムラインの先頭に配置します。")
    return 0


def run_auto_editor_cut_list(camera_path, output_path):
    """auto-editorを実行し、カットリスト（v3 JSON）を得る"""
    command = [
        "auto-editor",
        str(camera_path),
        "--margin", "0.2sec",
        "--edit", "audio:threshold=3%",
        "--export", "json",
        "--output", str(output_path),
        "--no-open",
    ]
    print(f"実行コマンド: {' '.join(command)}")
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"✗ auto-editor実行失敗: {e}")
        print(f"エラー出力: {e.stderr}")
        return None
    except FileNotFoundError:
        print("✗ auto-editorが見つかりません")
        return None

    return json.loads(Path(output_path).read_text(encoding="utf-8"))


def ensure_video_tracks(timeline, required):
    """必要な本数のビデオトラックを確保する"""
    while timeline.GetTrackCount("video") < required:
        if not timeline.AddTrack("video"):
            print("✗ ビデオトラックを追加できませんでした")
            return False
    return True


def apply_clip_properties(items, properties, label):
    """タイムラインアイテム群に同じ変形設定を適用する"""
    applied = 0
    for item in items:
        try:
            if item.SetProperty(dict(properties)):
                applied += 1
        except Exception as e:
            print(f"  {label}の変形設定でエラー: {e}")
            break
    print(f"✓ {label}の配置を{applied}/{len(items)}クリップに適用しました")
    return applied


def run_dual_source_edit(project, media_pool, main_timeline, pair, start_frame):
    """mkv=V1 / mp4=V2 の2ソースタイムラインを組み立てる"""
    print(f"✓ 画面録画: {pair.slides.name}")
    print(f"✓ カメラ録画: {pair.camera.name}")

    fps = timeline_frame_rate(main_timeline)
    print(f"✓ タイムラインのフレームレート: {fps}")

    # 音声で2本の録画を合わせる。一致しなければここで止める。
    try:
        sync = audio_sync.estimate_offset(pair.slides, pair.camera)
    except audio_sync.AudioSyncError as e:
        print(f"✗ 音声同期に失敗: {e}")
        return False
    offset_frames = dual_source.seconds_to_frames(sync.offset_seconds, fps)
    print(
        f"✓ 音声同期: 画面録画の先頭はカメラの {sync.offset_seconds:.3f} 秒"
        f"（{offset_frames}フレーム）地点（確度 {sync.confidence:.1f}）"
    )

    cut_list_path = pair.folder / "_auto_editor_cuts.json"
    document = run_auto_editor_cut_list(pair.camera, cut_list_path)
    if document is None:
        return False

    try:
        segments = dual_source.parse_cut_list(document)
        cut_fps = float(dual_source.cut_list_frame_rate(document))
    except dual_source.DualSourceError as e:
        print(f"✗ カットリストを読めません: {e}")
        return False

    if round(cut_fps, 3) != round(fps, 3):
        print(f"✗ カットリスト({cut_fps}fps)とタイムライン({fps}fps)のフレームレートが違います")
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

    try:
        slides_frame_count = int(slides_item.GetClipProperty("Frames"))
    except Exception:
        slides_frame_count = None

    try:
        placements = dual_source.build_placements(
            segments,
            slides_offset_frames=offset_frames,
            timeline_start_frame=start_frame,
            slides_frame_count=slides_frame_count,
        )
    except dual_source.DualSourceError as e:
        print(f"✗ タイムラインを組み立てられません: {e}")
        return False
    print(f"✓ 配置計画: {dual_source.describe_plan(placements, len(segments))}")

    if not ensure_video_tracks(main_timeline, dual_source.CAMERA_TRACK):
        return False

    project.SetCurrentTimeline(main_timeline)
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

    append_ending_video(media_pool, dual_source.placement_end_frame(placements))
    return True


def append_ending_video(media_pool, record_frame):
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
    try:
        ending_frames = int(ending_clip.GetClipProperty("Frames"))
        appended = media_pool.AppendToTimeline([{
            "mediaPoolItem": ending_clip,
            "startFrame": 0,
            "endFrame": ending_frames,
            "recordFrame": record_frame,
            "mediaType": 1,
            "trackIndex": dual_source.SLIDES_TRACK,
        }])
    except Exception as e:
        print(f"✗ エンディング動画追加エラー: {e}")
        return False

    if not appended:
        print("✗ エンディング動画の追加に失敗")
        return False
    print("✓ エンディング動画を追加しました")
    return True


def finish_editing(resolve, project, main_timeline):
    """再生ヘッドを先頭に戻してEditページを開く"""
    try:
        main_timeline.SetCurrentTimecode("00:00:00:00")
        print("✓ 編集ポジションをタイムライン先頭に移動しました")
    except Exception as e:
        print(f"編集ポジション移動エラー: {str(e)}")

    try:
        resolve.OpenPage("edit")
        print("✓ Editページに切り替えました")
    except Exception:
        pass

    print(f"\n✓ 全処理完了！プロジェクト '{project.GetName()}' が準備できました。")


def main():
    # APIパスの設定
    add_resolve_api_to_sys_path()

    try:
        import DaVinciResolveScript as bmd
        print("✓ DaVinciResolveScript インポート成功")
    except Exception as e:
        print(f"✗ DaVinciResolveScript インポート失敗: {e}")
        sys.exit(1)

    # DaVinci Resolveに接続
    resolve = bmd.scriptapp("Resolve")
    if resolve is None:
        print("DaVinci Resolveが起動していません。起動を試行...")
        launch_resolve_if_needed()
        time.sleep(10)  # 起動待機
        resolve = get_resolve_with_retry(bmd, retries=60, interval=1)

    if resolve is None:
        print("✗ DaVinci Resolveに接続できませんでした")
        sys.exit(1)

    pm = resolve.GetProjectManager()
    if pm is None:
        print("✗ ProjectManager取得失敗")
        sys.exit(1)

    print("✓ DaVinci Resolve接続完了")

    # テンプレートファイルパス
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "テンプレート.drp")
    if not os.path.exists(template_path):
        print(f"✗ テンプレートファイルが見つかりません: {template_path}")
        sys.exit(1)

    print(f"✓ テンプレートファイル確認: {template_path}")

    # プロジェクト名生成
    project_name = f"自動編集_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # テンプレートからプロジェクト作成
    created_project_name = create_project_from_template(pm, template_path, project_name)
    if not created_project_name:
        print("✗ テンプレートプロジェクト作成失敗")
        sys.exit(1)

    # プロジェクトを開く
    project = pm.LoadProject(created_project_name)
    if not project:
        print("✗ プロジェクトを開けませんでした")
        sys.exit(1)

    print(f"✓ プロジェクトを開きました: {project.GetName()}")

    # MediaPoolとタイムライン確認
    media_pool = project.GetMediaPool()
    if not media_pool:
        print("✗ MediaPool取得失敗")
        sys.exit(1)

    # mainタイムラインを探す
    main_timeline = None
    current_timeline = project.GetCurrentTimeline()

    if current_timeline and current_timeline.GetName().lower() == "main":
        main_timeline = current_timeline
        print(f"✓ mainタイムラインが見つかりました: {main_timeline.GetName()}")
    else:
        # 全タイムラインから"main"を探す
        print("mainタイムラインを検索中...")
        # Note: DaVinci ResolveのAPIにはGetTimelineList()がないため、
        # 現在のタイムラインがmainでない場合は、それを使用
        if current_timeline:
            main_timeline = current_timeline
            print(f"✓ 現在のタイムラインを使用: {main_timeline.GetName()}")
        else:
            print("✗ タイムラインが見つかりません")
            sys.exit(1)

    working_dir = first_existing_path(WORKING_DIR_CANDIDATES)
    if not working_dir:
        print("✗ OBS録画フォルダが見つかりません")
        sys.exit(1)
    print(f"✓ 録画フォルダ: {working_dir}")

    # サブフォルダに「mkv 1本 + mp4 1本」があれば2ソースモード。
    # 無ければ従来どおり、フォルダ直下の最新動画1本を処理する。
    pair = dual_source.find_latest_recording_pair(Path(working_dir))
    if pair:
        print(f"✓ 2ソース録画を検出しました: {pair.folder.name}")
        start_frame = find_opening_end_frame(main_timeline)
        if not run_dual_source_edit(project, media_pool, main_timeline, pair, start_frame):
            print("✗ 2ソース編集に失敗しました")
            sys.exit(1)
        finish_editing(resolve, project, main_timeline)
        return

    print("2ソースのサブフォルダは無いため、従来の単一ソース処理を行います")
    if not run_auto_editor(working_dir):
        print("✗ auto-editor実行失敗")
        sys.exit(1)

    # auto-editorは元動画と同じフォルダにXMLを書き出す
    xml_folder_path = working_dir
    print(f"✓ XMLフォルダ: {xml_folder_path}")

    # 最新のXMLファイルを検索
    fcpxml_files = glob.glob(os.path.join(xml_folder_path, '*.fcpxml'))
    xml_files = glob.glob(os.path.join(xml_folder_path, '*.xml'))
    all_xml_files = fcpxml_files + xml_files

    if not all_xml_files:
        print("✗ XMLファイルが見つかりません")
        sys.exit(1)

    latest_xml = max(all_xml_files, key=os.path.getmtime)
    print(f"✓ 最新XMLファイル: {latest_xml}")

    # XMLからタイムラインをインポート
    print("XMLからタイムラインをインポート中...")
    xml_timeline = media_pool.ImportTimelineFromFile(latest_xml)
    if not xml_timeline:
        print("✗ XMLタイムラインインポート失敗")
        sys.exit(1)

    print(f"✓ XMLタイムラインインポート成功: {xml_timeline.GetName()}")

    # エンディング動画をXMLタイムラインに追加
    ending_video_paths = [
        r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
        r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov'
    ]

    ending_video_path = next((path for path in ending_video_paths if os.path.exists(path)), None)
    if ending_video_path:
        print(f"✓ エンディング動画: {ending_video_path}")

        # エンディング動画をインポート
        ending_clips = media_pool.ImportMedia([ending_video_path])
        if ending_clips:
            ending_clip = ending_clips[0]
            print(f"✓ エンディングクリップインポート: {ending_clip.GetName()}")

            # XMLタイムラインをアクティブにしてエンディング動画を追加
            project.SetCurrentTimeline(xml_timeline)
            try:
                ending_frames = int(ending_clip.GetClipProperty('Frames'))
                append_result = media_pool.AppendToTimeline([{
                    'mediaPoolItem': ending_clip,
                    'startFrame': 0,
                    'endFrame': ending_frames
                }])

                if append_result:
                    print("✓ エンディング動画をXMLタイムラインに追加しました")
                else:
                    print("✗ エンディング動画の追加に失敗")
            except Exception as e:
                print(f"✗ エンディング動画追加エラー: {e}")
    else:
        print("! エンディング動画が見つかりません（スキップ）")

    # mainタイムラインをアクティブにする
    print("mainタイムラインをアクティブにします")
    project.SetCurrentTimeline(main_timeline)
    current_tl = project.GetCurrentTimeline()
    print(f"現在のアクティブタイムライン: {current_tl.GetName() if current_tl else 'None'}")

    # オープニングクリップの位置を探す
    start_frame = find_opening_end_frame(main_timeline)

    # XMLタイムラインの内容をmainタイムラインに挿入
    print("XMLタイムラインの内容をmainタイムラインに挿入します")
    try:
        clips_to_append = []

        # XMLタイムラインからクリップを取得
        video_track_count = xml_timeline.GetTrackCount("video")
        print(f"XMLタイムラインのビデオトラック数: {video_track_count}")

        for track_idx in range(1, video_track_count + 1):
            items_in_track = xml_timeline.GetItemsInTrack("video", track_idx)
            if items_in_track:
                for item_id, clip_obj in items_in_track.items():
                    if clip_obj:
                        try:
                            clip_start = clip_obj.GetLeftOffset()
                            clip_duration = clip_obj.GetDuration()
                            clip_end = clip_duration + clip_start
                            media_item = clip_obj.GetMediaPoolItem()

                            if media_item is not None:
                                clips_to_append.append({
                                    'mediaPoolItem': media_item,
                                    'startFrame': clip_start,
                                    'endFrame': clip_end
                                })
                                print(f"クリップ追加予定: {clip_obj.GetName()}")
                        except Exception as e:
                            print(f"クリップ情報取得エラー: {e}")
                            continue

        print(f"挿入するクリップ数: {len(clips_to_append)}")

        if clips_to_append:
            # 再生ヘッドを配置（SetCurrentFrameはAPIに無いためタイムコードで指定）
            try:
                target_tc = frame_to_timecode(main_timeline, start_frame)
                main_timeline.SetCurrentTimecode(target_tc)
                print(f"再生ヘッド位置を {start_frame} フレーム ({target_tc}) に設定しました")
            except Exception as e:
                print(f"再生ヘッド配置でエラー: {str(e)}")

            # クリップをmainタイムラインに追加（リトライ機能付き）
            print("クリップをmainタイムラインに追加中...")

            # オブジェクトの再取得（念のため）
            try:
                media_pool = project.GetMediaPool()
                main_timeline = project.GetCurrentTimeline()
                print(f"オブジェクト再取得: MediaPool={type(media_pool)}, Timeline={type(main_timeline)}")
            except Exception as e:
                print(f"オブジェクト再取得エラー: {e}")

            # リトライ機能付きでクリップ追加
            insert_result = append_clips_with_retry(media_pool, clips_to_append, max_retries=3, delay=2)

            if insert_result:
                print(f"✓ mainタイムラインの位置 {start_frame} にクリップを挿入しました")
            else:
                print("✗ クリップの挿入に失敗しました")

                # 失敗時のデバッグ情報
                print("=== デバッグ情報 ===")
                print(f"media_pool型: {type(media_pool)}")
                print(f"main_timeline型: {type(main_timeline)}")
                print(f"clips_to_append数: {len(clips_to_append)}")
                if clips_to_append:
                    print(f"最初のクリップ構造: {clips_to_append[0]}")
                print("===================")
        else:
            print("! 挿入するクリップが見つかりませんでした")

    except Exception as e:
        print(f"✗ タイムライン挿入エラー: {str(e)}")

    finish_editing(resolve, project, main_timeline)

if __name__ == "__main__":
    main()
