#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DaVinci Resolve自動動画編集スクリプト（有償版）
- テンプレートプロジェクトから新規プロジェクトを作成
- auto-editorで無音部分を自動カット
- エンディング動画を自動追加
- mainタイムラインに統合
"""

import os
import sys
import time
import subprocess
import platform
import glob
import json
import re
import shutil
import textwrap
from datetime import datetime
from pathlib import Path

print("DaVinci Resolve自動動画編集スクリプト（有償版）開始")

AI_ASSIST_ENABLED = os.environ.get("DAVINCI_AI_ASSIST", "1").lower() not in ("0", "false", "no")
AI_ASSIST_DIR_NAME = "_ai_assist"
HOOK_CARD_SECONDS = 4
CHAPTER_INTERVAL_SECONDS = 180
DEFAULT_OP_CLIP_NAME = "01_EBI_CHAN_OP"
DEFAULT_WHISPER_LANGUAGE = "Japanese"
DEFAULT_KEYWORD_PATTERNS = [
    "Claude Code",
    "CLAUDE.md",
    "コンテキスト",
    "Hooks",
    "Hook",
    "MCP",
    "API",
    "スキル",
    "サブエージェント",
    "検証",
    "自動化",
    "WSL",
    "GitHub",
    "CI/CD",
]

def load_local_config():
    """git管理外のローカル設定を読み込む"""
    config_path = os.environ.get("DAVINCI_CONFIG")
    if not config_path:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✓ ローカル設定を読み込みました: {config_path}")
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"! ローカル設定の読み込みに失敗しました: {e}")
        return {}

LOCAL_CONFIG = load_local_config()

def split_env_values(name):
    """環境変数をOS標準の区切り文字で分割"""
    value = os.environ.get(name, "")
    return [item.strip().strip('"') for item in value.split(os.pathsep) if item.strip()]

def config_list(key):
    """config.local.jsonの値をリストとして取得"""
    value = LOCAL_CONFIG.get(key)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip().strip('"') for item in value.split(os.pathsep) if item.strip()]
    return []

def configured_paths(env_name, config_key):
    """環境変数またはconfig.local.jsonからパス候補を取得"""
    values = split_env_values(env_name)
    return values or config_list(config_key)

def configured_value(env_name, config_key, default_value):
    """環境変数またはconfig.local.jsonから単一値を取得"""
    return os.environ.get(env_name) or LOCAL_CONFIG.get(config_key) or default_value

def first_existing_path(paths):
    """候補から最初に存在するパスを返す"""
    return next((path for path in paths if os.path.exists(path)), None)

def get_ai_keywords():
    """AI補助で拾う重要語。環境変数でカンマ区切り上書き可。"""
    value = configured_value("DAVINCI_AI_KEYWORDS", "ai_keywords", "")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = str(value)
    if value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return DEFAULT_KEYWORD_PATTERNS

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
    latest_path = Path(working_dir) / latest_file
    print(f"✓ 処理対象ファイル: {latest_file}")
    
    command = [
        "auto-editor",
        str(latest_path),
        "--margin", "0.5sec",
        "--edit", "audio:threshold=1%",
        "--export", "resolve"
    ]
    
    print("実行コマンド:", " ".join(command))
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print("✓ auto-editor実行成功")
        print(result.stdout)
        return latest_path
    except subprocess.CalledProcessError as e:
        print(f"✗ auto-editor実行失敗: {e}")
        print(f"エラー出力: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ auto-editorが見つかりません")
        return None

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
    fps = get_timeline_fps(timeline)

    frame = int(frame)
    f = frame % fps
    total_seconds = frame // fps
    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

def get_timeline_fps(timeline):
    """タイムラインのフレームレートを整数で取得"""
    try:
        fps_raw = timeline.GetSetting("timelineFrameRate")
        fps = int(round(float(fps_raw)))
    except Exception:
        fps = 30
    return fps if fps > 0 else 30

def clean_text(text):
    """文字起こしテキストを短い表示用に整える"""
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"^(えー|えっと|あの|その|まあ|はい)[、,\s]*", "", text)
    return text

def shorten_text(text, limit=34):
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"

def segment_is_useful(segment):
    text = clean_text(segment.get("text", ""))
    return len(text) >= 12 and not re.fullmatch(r"[、。,.!\s]+", text)

def load_transcript_segments(transcript_path):
    """Whisper JSONからセグメントを読み込む"""
    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = []
    for item in data.get("segments", []):
        text = clean_text(item.get("text", ""))
        if not text:
            continue
        try:
            start = float(item.get("start", 0))
            end = float(item.get("end", start))
        except (TypeError, ValueError):
            continue
        if end <= start:
            end = start + 1
        segments.append({"start": start, "end": end, "text": text})
    return segments

def run_whisper_transcription(source_video_path, output_dir):
    """whisper CLIがあれば文字起こしを実行し、JSONパスを返す"""
    whisper_exe = shutil.which("whisper")
    if not whisper_exe:
        print("! whisper CLIが見つかりません。AI補助をスキップします。")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{source_video_path.stem}.json"
    if transcript_path.exists() and transcript_path.stat().st_mtime >= source_video_path.stat().st_mtime:
        print(f"✓ 既存の文字起こしJSONを再利用: {transcript_path}")
        return transcript_path

    command = [
        whisper_exe,
        str(source_video_path),
        "--language",
        configured_value("DAVINCI_WHISPER_LANGUAGE", "whisper_language", DEFAULT_WHISPER_LANGUAGE),
        "--task",
        "transcribe",
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]
    print("whisper文字起こしを実行中...")
    print("実行コマンド:", " ".join(command))
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"! whisper文字起こしに失敗しました: {e}")
        if e.stderr:
            print(e.stderr)
        return None

    if transcript_path.exists():
        print(f"✓ 文字起こしJSON作成: {transcript_path}")
        return transcript_path

    print("! whisper実行後にJSONが見つかりませんでした。")
    return None

def choose_hook_text(segments):
    """冒頭に置く短い結論カードの文言を決める"""
    useful_segments = [s for s in segments if segment_is_useful(s)]
    if not useful_segments:
        return ""

    keyword_segments = [
        s for s in useful_segments[:20]
        if any(keyword.lower() in s["text"].lower() for keyword in get_ai_keywords())
    ]
    chosen = keyword_segments[0] if keyword_segments else useful_segments[0]
    return "今回のポイント: " + shorten_text(chosen["text"], 42)

def build_chapters(segments):
    """文字起こしからYouTube/Resolve用の章ドラフトを作る"""
    useful_segments = [s for s in segments if segment_is_useful(s)]
    if not useful_segments:
        return []

    chapters = [{"time": 0.0, "title": "導入"}]
    next_boundary = CHAPTER_INTERVAL_SECONDS
    for segment in useful_segments:
        if segment["start"] < next_boundary:
            continue
        title = shorten_text(segment["text"], 28)
        chapters.append({"time": segment["start"], "title": title})
        next_boundary += CHAPTER_INTERVAL_SECONDS
        if len(chapters) >= 12:
            break
    return chapters

def build_keyword_cues(segments):
    """重要語が出た箇所をマーカー候補にする"""
    cues = []
    seen = set()
    for segment in segments:
        text_lower = segment["text"].lower()
        for keyword in get_ai_keywords():
            if keyword.lower() not in text_lower:
                continue
            bucket = (keyword, int(segment["start"] // 30))
            if bucket in seen:
                continue
            seen.add(bucket)
            cues.append({
                "time": segment["start"],
                "keyword": keyword,
                "note": shorten_text(segment["text"], 60),
            })
            break
        if len(cues) >= 24:
            break
    return cues

def build_qc_notes(segments):
    """編集時に見るべき箇所を簡易検出する"""
    notes = []
    previous_end = None
    for segment in segments:
        if previous_end is not None:
            gap = segment["start"] - previous_end
            if gap >= 8:
                notes.append({
                    "time": previous_end,
                    "type": "long_gap",
                    "message": f"{gap:.1f}秒の発話ギャップがあります",
                })
        duration = segment["end"] - segment["start"]
        if duration <= 0.4 and len(segment["text"]) >= 6:
            notes.append({
                "time": segment["start"],
                "type": "short_segment",
                "message": "短すぎる発話断片です",
            })
        previous_end = segment["end"]
        if len(notes) >= 20:
            break
    return notes

def write_ai_assist_files(ai_plan, output_dir):
    """後段や手動確認用のファイルを書き出す"""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "ai_edit_plan.json"
    chapters_path = output_dir / "chapters_draft.txt"

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(ai_plan, f, ensure_ascii=False, indent=2)

    with open(chapters_path, "w", encoding="utf-8") as f:
        for chapter in ai_plan.get("chapters", []):
            seconds = int(chapter["time"])
            f.write(f"{seconds // 60:02d}:{seconds % 60:02d} {chapter['title']}\n")

    print(f"✓ AI編集プランを書き出しました: {plan_path}")
    print(f"✓ チャプター草案を書き出しました: {chapters_path}")

def create_hook_card_asset(ai_plan, output_dir):
    """Pillowとffmpegがあれば、冒頭フックカード動画を作る"""
    hook_text = ai_plan.get("hook_text")
    if not hook_text:
        return None
    if not shutil.which("ffmpeg"):
        print("! ffmpegが見つかりません。フックカード動画の生成をスキップします。")
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("! Pillowが見つかりません。フックカード動画の生成をスキップします。")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "hook_card.png"
    video_path = output_dir / "hook_card.mp4"

    image = Image.new("RGB", (1920, 1080), (18, 24, 31))
    draw = ImageDraw.Draw(image)
    font_candidates = [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    title_font = None
    body_font = None
    for font_path in font_candidates:
        if os.path.exists(font_path):
            title_font = ImageFont.truetype(font_path, 54)
            body_font = ImageFont.truetype(font_path, 76)
            break
    if title_font is None:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.rectangle((0, 0, 1920, 1080), fill=(18, 24, 31))
    draw.rectangle((120, 116, 1800, 964), outline=(70, 130, 180), width=5)
    draw.text((160, 168), "AI DRAFT HOOK", fill=(102, 204, 255), font=title_font)

    wrapped = textwrap.wrap(hook_text, width=22)
    y = 390
    for line in wrapped[:4]:
        draw.text((160, y), line, fill=(245, 248, 250), font=body_font)
        y += 110
    draw.text((160, 875), "必要ならDaVinci上で削除・編集してください", fill=(180, 190, 200), font=title_font)
    image.save(png_path)

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(png_path),
        "-t",
        str(HOOK_CARD_SECONDS),
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        str(video_path),
    ]
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"! フックカード動画の生成に失敗しました: {e}")
        if e.stderr:
            print(e.stderr)
        return None

    print(f"✓ フックカード動画を作成しました: {video_path}")
    return str(video_path)

def build_ai_assist_plan(source_video_path, working_dir):
    """文字起こしからDaVinci上に置く補助情報を作る。失敗時は空プランを返す。"""
    empty_plan = {
        "enabled": False,
        "hook_text": "",
        "hook_asset_path": "",
        "chapters": [],
        "keyword_cues": [],
        "qc_notes": [],
        "source_duration": 0,
    }
    if not AI_ASSIST_ENABLED:
        print("! DAVINCI_AI_ASSIST=0 のためAI補助をスキップします。")
        return empty_plan

    output_dir = Path(working_dir) / AI_ASSIST_DIR_NAME
    try:
        transcript_path = run_whisper_transcription(Path(source_video_path), output_dir)
        if not transcript_path:
            return empty_plan

        segments = load_transcript_segments(transcript_path)
        if not segments:
            print("! 文字起こしセグメントが空です。AI補助をスキップします。")
            return empty_plan

        ai_plan = {
            "enabled": True,
            "source_video": str(source_video_path),
            "transcript_path": str(transcript_path),
            "hook_text": choose_hook_text(segments),
            "chapters": build_chapters(segments),
            "keyword_cues": build_keyword_cues(segments),
            "qc_notes": build_qc_notes(segments),
            "source_duration": segments[-1]["end"],
        }
        hook_asset_path = create_hook_card_asset(ai_plan, output_dir)
        ai_plan["hook_asset_path"] = hook_asset_path or ""
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan
    except Exception as e:
        print(f"! AI補助処理でエラーが発生しました。従来処理を続行します: {e}")
        return empty_plan

def prepare_hook_clip(media_pool, ai_plan, fps):
    """フックカード動画をメディアプールに読み込み、挿入用clipInfoを返す"""
    hook_asset_path = ai_plan.get("hook_asset_path")
    if not hook_asset_path or not os.path.exists(hook_asset_path):
        return None

    try:
        hook_clips = media_pool.ImportMedia([hook_asset_path])
        if not hook_clips:
            print("! フックカード動画のインポートに失敗しました。")
            return None
        hook_clip = hook_clips[0]
        try:
            hook_frames = int(hook_clip.GetClipProperty("Frames"))
        except Exception:
            hook_frames = HOOK_CARD_SECONDS * fps
        hook_frames = max(hook_frames, HOOK_CARD_SECONDS * fps)
        print(f"✓ フックカードを挿入候補に追加: {hook_clip.GetName()} ({hook_frames} frames)")
        return {
            "mediaPoolItem": hook_clip,
            "startFrame": 0,
            "endFrame": hook_frames,
        }, hook_frames
    except Exception as e:
        print(f"! フックカード準備でエラー: {e}")
        return None

def map_source_time_to_edited_frame(source_seconds, source_duration, edited_duration_frames):
    """元動画時間をauto-editor後タイムラインの近似フレームへ変換"""
    if source_duration <= 0 or edited_duration_frames <= 0:
        return 0
    ratio = min(max(source_seconds / source_duration, 0), 1)
    return int(ratio * edited_duration_frames)

def add_ai_assist_markers(timeline, start_frame, ai_plan, fps, edited_duration_frames, hook_frames=0):
    """mainタイムライン上にAI補助マーカーを追加"""
    if not ai_plan.get("enabled"):
        return
    if not hasattr(timeline, "AddMarker"):
        print("! このResolve APIではAddMarkerが使えません。マーカー追加をスキップします。")
        return

    source_duration = float(ai_plan.get("source_duration") or 0)
    content_start_frame = start_frame + hook_frames
    added = 0

    def add_marker(source_time, color, name, note):
        nonlocal added
        mapped = map_source_time_to_edited_frame(source_time, source_duration, edited_duration_frames)
        frame = int(content_start_frame + mapped)
        try:
            ok = timeline.AddMarker(frame, color, name, note, 1, "")
        except Exception as e:
            print(f"! マーカー追加エラー ({name}): {e}")
            return
        if ok:
            added += 1

    if ai_plan.get("hook_text"):
        try:
            timeline.AddMarker(int(start_frame), "Green", "AI Hook", ai_plan["hook_text"], max(1, hook_frames), "")
            added += 1
        except Exception as e:
            print(f"! フックマーカー追加エラー: {e}")

    for chapter in ai_plan.get("chapters", []):
        add_marker(float(chapter["time"]), "Blue", "Chapter: " + chapter["title"], "AI chapter draft")

    for cue in ai_plan.get("keyword_cues", []):
        add_marker(float(cue["time"]), "Yellow", "Keyword: " + cue["keyword"], cue.get("note", ""))

    for note in ai_plan.get("qc_notes", []):
        add_marker(float(note["time"]), "Red", "QC: " + note["type"], note.get("message", ""))

    print(f"✓ AI補助マーカーを追加しました: {added}件")

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
    
    # auto-editorの実行
    working_dir = first_existing_path(configured_paths("DAVINCI_WORKING_DIRS", "working_dirs"))
    if not working_dir:
        print("✗ OBS録画フォルダが見つかりません")
        print("  環境変数 DAVINCI_WORKING_DIRS に録画フォルダを指定してください")
        sys.exit(1)
    print(f"✓ OBS録画フォルダ: {working_dir}")
    source_video_path = run_auto_editor(working_dir)
    if not source_video_path:
        print("✗ auto-editor実行失敗")
        sys.exit(1)

    # AI補助情報の作成（失敗しても従来処理を続行）
    ai_plan = build_ai_assist_plan(source_video_path, working_dir)
    
    # XMLファイルの検索とインポート
    xml_folder_paths = configured_paths("DAVINCI_XML_DIRS", "xml_dirs")
    xml_folder_path = next((path for path in xml_folder_paths if os.path.exists(path)), None)
    if not xml_folder_path:
        print("✗ XMLフォルダが見つかりません")
        sys.exit(1)
    
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
    ending_video_paths = configured_paths("DAVINCI_ENDING_VIDEO_PATHS", "ending_video_paths")
    ending_video_path = first_existing_path(ending_video_paths)
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
    print("オープニングクリップを探します")
    op_clip_found = False
    start_frame = 0
    
    try:
        video_track = 1  # V1トラックを指定
        items_in_track = main_timeline.GetItemsInTrack("video", video_track)
        items_count = len(items_in_track)
        print(f"V{video_track}トラックのアイテム数: {items_count}")
        
        if items_count == 0:
            print(f"V{video_track}トラックにアイテムがありません。")
            op_clip_found = False
        else:
            clip_index = 1
            for item_id, item in items_in_track.items():
                clip_name = item.GetName()
                print(f"V{video_track}トラックのクリップ {clip_index}: {clip_name}")
                # オープニングクリップをチェック
                op_clip_name = configured_value("DAVINCI_OP_CLIP_NAME", "op_clip_name", DEFAULT_OP_CLIP_NAME)
                if op_clip_name in clip_name:
                    start_frame = item.GetEnd()
                    op_clip_found = True
                    print(f"オープニングクリップが見つかりました。終了フレーム: {start_frame}")
                    break
                clip_index += 1
    except Exception as e:
        print(f"V{video_track}トラックのアイテム数取得でエラー: {str(e)}")
        op_clip_found = False
    
    if not op_clip_found:
        print(f"V{video_track}トラックにオープニングクリップが見つかりません。タイムラインの先頭に配置します。")
        start_frame = 0
    
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
        
        edited_duration_frames = sum(
            max(0, int(clip.get('endFrame', 0)) - int(clip.get('startFrame', 0)))
            for clip in clips_to_append
        )

        fps = get_timeline_fps(main_timeline)
        hook_frames = 0
        hook_clip_result = prepare_hook_clip(media_pool, ai_plan, fps)
        if hook_clip_result:
            hook_clip_info, hook_frames = hook_clip_result
            clips_to_append.insert(0, hook_clip_info)
            print("✓ フックカードを本編先頭に追加します")

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
                add_ai_assist_markers(
                    main_timeline,
                    start_frame,
                    ai_plan,
                    fps,
                    edited_duration_frames,
                    hook_frames=hook_frames,
                )
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
    
    # 編集ポジションをタイムライン先頭に移動
    try:
        main_timeline.SetCurrentTimecode("00:00:00:00")
        print("✓ 編集ポジションをタイムライン先頭に移動しました")
    except Exception as e:
        print(f"編集ポジション移動エラー: {str(e)}")
    
    # Editページに切り替え
    try:
        resolve.OpenPage("edit")
        print("✓ Editページに切り替えました")
    except Exception:
        pass
    
    print(f"\n✓ 全処理完了！プロジェクト '{project.GetName()}' が準備できました。")

if __name__ == "__main__":
    main()
