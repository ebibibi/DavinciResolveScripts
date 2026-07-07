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
import importlib.util
import json
import re
import shlex
import shutil
import textwrap
from datetime import datetime
from pathlib import Path

SCRIPT_VERSION = "2026-07-07-subprocess-utf8-v1"

print("DaVinci Resolve自動動画編集スクリプト（有償版）開始")
print(f"Script version: {SCRIPT_VERSION}")

AI_ASSIST_ENABLED = os.environ.get("DAVINCI_AI_ASSIST", "1").lower() not in ("0", "false", "no")
AI_ASSIST_DIR_NAME = "_ai_assist"
HOOK_CARD_SECONDS = 4
CHAPTER_INTERVAL_SECONDS = 180
DEFAULT_OP_CLIP_NAME = "01_EBI_CHAN_OP"
DEFAULT_ENDING_CLIP_NAME = "03_EBI_CHAN_IN.mov"
DEFAULT_WHISPER_LANGUAGE = "Japanese"
DEFAULT_WHISPER_DEVICE = "auto"
DEFAULT_WHISPER_FP16 = "false"
DEFAULT_WHISPER_BACKEND = "local"
DEFAULT_REMOTE_WHISPER_DIR = "davinci-whisper-jobs"
KEY_CUE_PHRASES = [
    "重要",
    "ポイント",
    "結論",
    "つまり",
    "要するに",
    "ここで",
    "実際に",
    "注意",
    "理由",
    "違い",
    "おすすめ",
    "メリット",
    "デメリット",
    "まとめ",
]
COMMON_LATIN_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "you",
    "are",
    "is",
    "to",
    "of",
    "in",
    "on",
    "it",
    "as",
    "or",
    "from",
    "by",
    "video",
    "movie",
    "file",
    "mp4",
    "mov",
    "mkv",
}
TECH_SUFFIXES = [
    "管理",
    "設定",
    "連携",
    "検証",
    "実装",
    "自動化",
    "環境",
    "編集",
    "録画",
    "字幕",
    "マーカー",
    "タイムライン",
    "スクリプト",
    "プロジェクト",
    "テンプレート",
]
LOCAL_CONFIG_FILENAMES = ("config.local.json", "config.json")

def load_local_config():
    """git管理外のローカル設定を読み込む"""
    config_path = os.environ.get("DAVINCI_CONFIG")
    if config_path:
        config_candidates = [config_path]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_candidates = [
            os.path.join(script_dir, filename)
            for filename in LOCAL_CONFIG_FILENAMES
        ]

    config_path = next((path for path in config_candidates if os.path.exists(path)), None)
    if not config_path:
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
    """ローカル設定ファイルの値をリストとして取得"""
    value = LOCAL_CONFIG.get(key)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip().strip('"') for item in value.split(os.pathsep) if item.strip()]
    return []

def configured_paths(env_name, config_key):
    """環境変数またはローカル設定ファイルからパス候補を取得"""
    values = split_env_values(env_name)
    return values or config_list(config_key)

def configured_value(env_name, config_key, default_value):
    """環境変数またはローカル設定ファイルから単一値を取得"""
    return os.environ.get(env_name) or LOCAL_CONFIG.get(config_key) or default_value

def config_section(config_key):
    """ローカル設定ファイルのセクションをdictとして取得"""
    value = LOCAL_CONFIG.get(config_key)
    return value if isinstance(value, dict) else {}

def configured_section_value(env_name, section_key, value_key, default_value):
    """環境変数またはローカル設定セクションから単一値を取得"""
    section = config_section(section_key)
    return os.environ.get(env_name) or section.get(value_key) or default_value

def configured_section_list(env_name, section_key, value_key):
    """環境変数またはローカル設定セクションから引数リストを取得"""
    env_value = os.environ.get(env_name)
    if env_value:
        return shlex.split(env_value)
    value = config_section(section_key).get(value_key)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    return []

def configured_bool(value, default_value=False):
    """設定値をboolへ変換"""
    if isinstance(value, bool):
        return value
    if value is None:
        return default_value
    normalized = str(value).strip().lower()
    if not normalized:
        return default_value
    return normalized in ("1", "true", "yes", "on")

def first_existing_path(paths):
    """候補から最初に存在するパスを返す"""
    return next((path for path in paths if os.path.exists(path)), None)

def find_clip_path(video_paths, clip_name):
    """素材フォルダ候補から指定クリップ名のファイルを探す"""
    clip_name = str(clip_name or "").strip().strip('"')
    if not clip_name:
        return None

    direct_path = Path(clip_name)
    if direct_path.exists():
        return str(direct_path)

    for video_path in video_paths:
        base_path = Path(str(video_path).strip().strip('"'))
        if base_path.is_file() and base_path.name == clip_name:
            return str(base_path)
        if not base_path.is_dir():
            continue

        exact_path = base_path / clip_name
        if exact_path.exists():
            return str(exact_path)

        patterns = (
            [f"{clip_name}.*", f"*{clip_name}*"]
            if not direct_path.suffix
            else [f"*{clip_name}*"]
        )
        for pattern in patterns:
            for match in sorted(base_path.glob(pattern)):
                if match.is_file():
                    return str(match)

    return None

def get_priority_terms():
    """必要に応じて手動で優先する用語。自動抽出の補助としてだけ使う。"""
    value = (
        os.environ.get("DAVINCI_PRIORITY_TERMS")
        or LOCAL_CONFIG.get("priority_terms")
        or ""
    )
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = str(value)
    if value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []

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
        result = run_text_subprocess(command, check=True)
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

def unique_keep_order(items):
    """順序を保って重複を除く"""
    seen = set()
    unique = []
    for item in items:
        key = item.lower() if isinstance(item, str) else item
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique

def normalize_term(term):
    """マーカー名にしやすい形へ整える"""
    term = clean_text(term).strip("、。,.!?「」『』()[]{}")
    for prefix in ("ここで実際に", "ここから", "最後に", "今日は", "今回", "実際に"):
        if term.startswith(prefix):
            term = term[len(prefix):]
            break
    term = term.strip("をにのはがで、。,.!? ")
    return term

def extract_terms_from_text(text):
    """固定リストではなく、発話内から目立つ用語を拾う"""
    text = clean_text(text)
    terms = []

    for term in get_priority_terms():
        if term and term.lower() in text.lower():
            terms.append(term)

    for match in re.findall(r"[A-Za-z][A-Za-z0-9+#./_-]{1,}(?:\s+[A-Za-z][A-Za-z0-9+#./_-]{1,})+", text):
        normalized = normalize_term(match)
        if 3 <= len(normalized) <= 40:
            terms.append(normalized)

    for match in re.findall(r"[A-Za-z][A-Za-z0-9+#./_-]{1,}", text):
        normalized = normalize_term(match)
        if len(normalized) < 2:
            continue
        if normalized.lower() in COMMON_LATIN_WORDS:
            continue
        terms.append(normalized)

    for suffix in TECH_SUFFIXES:
        pattern = rf"[一-龥ぁ-んァ-ンA-Za-z0-9_+#./-]{{2,}}{re.escape(suffix)}"
        for match in re.findall(pattern, text):
            normalized = normalize_term(match)
            if 2 <= len(normalized) <= 24:
                terms.append(normalized)

    return unique_keep_order(terms)[:5]

def segment_has_key_cue(segment):
    """強調フレーズや用語があるセグメントをキーポイント候補にする"""
    text = clean_text(segment.get("text", ""))
    if any(phrase in text for phrase in KEY_CUE_PHRASES):
        return True
    return bool(extract_terms_from_text(text))

def key_point_label(segment):
    """マーカー名に使う短いラベルを作る"""
    terms = extract_terms_from_text(segment.get("text", ""))
    if terms:
        return terms[0]
    return shorten_text(segment.get("text", ""), 24)

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

def resolve_whisper_command():
    """whisper CLIまたはPythonモジュール実行のコマンドを返す"""
    whisper_exe = shutil.which("whisper")
    if whisper_exe:
        return [whisper_exe]
    if importlib.util.find_spec("whisper.__main__"):
        return [sys.executable, "-m", "whisper"]
    return []

def get_torch_status():
    """PyTorchとGPU利用可否の状態を返す"""
    status = {
        "torch": "",
        "torch_cuda_available": False,
        "torch_cuda_version": "",
        "torch_cuda_device": "",
        "torch_mps_available": False,
    }
    try:
        import torch
        status["torch"] = getattr(torch, "__version__", "available")
        status["torch_cuda_available"] = bool(torch.cuda.is_available())
        status["torch_cuda_version"] = getattr(torch.version, "cuda", "") or ""
        if status["torch_cuda_available"]:
            status["torch_cuda_device"] = torch.cuda.get_device_name(0)
        mps_backend = getattr(getattr(torch, "backends", None), "mps", None)
        if mps_backend is not None:
            status["torch_mps_available"] = bool(mps_backend.is_available())
    except Exception:
        pass
    return status

def select_whisper_device():
    """Whisperで使うデバイスを選ぶ"""
    requested = str(configured_value(
        "DAVINCI_WHISPER_DEVICE",
        "whisper_device",
        DEFAULT_WHISPER_DEVICE,
    )).strip().lower()
    if requested and requested != "auto":
        return requested

    torch_status = get_torch_status()
    if torch_status["torch_cuda_available"]:
        return "cuda"
    if torch_status["torch_mps_available"]:
        return "mps"
    return "cpu"

def select_whisper_backend():
    """Whisperの実行場所を選ぶ"""
    backend = configured_value("DAVINCI_WHISPER_BACKEND", "whisper_backend", DEFAULT_WHISPER_BACKEND)
    return str(backend).strip().lower()

def select_whisper_fp16(whisper_device):
    """WhisperのFP16利用有無を選ぶ。既定は安定性優先でFalse。"""
    value = configured_value("DAVINCI_WHISPER_FP16", "whisper_fp16", DEFAULT_WHISPER_FP16)
    if isinstance(value, bool):
        return "True" if value else "False"

    normalized = str(value).strip().lower()
    if normalized == "auto":
        return "True" if whisper_device == "cuda" else "False"
    if normalized in ("1", "true", "yes", "on"):
        return "True"
    return "False"

def remote_whisper_value(env_name, value_key, default_value):
    """remote_whisperセクションの値を取得"""
    return configured_section_value(env_name, "remote_whisper", value_key, default_value)

def remote_whisper_list(env_name, value_key):
    """remote_whisperセクションのリスト値を取得"""
    return configured_section_list(env_name, "remote_whisper", value_key)

def sanitize_remote_name(value):
    """リモート作業名に使える安全な名前へ変換"""
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return sanitized or "whisper_job"

def remote_join(base_path, *parts):
    """リモートのPOSIXパスを結合する"""
    path = str(base_path).rstrip("/")
    for part in parts:
        path = path + "/" + str(part).strip("/")
    return path

def remote_shell_path(path):
    """ssh先シェル用にリモートパスをクォートする"""
    path = str(path)
    if path.startswith("~/"):
        return "$HOME/" + shlex.quote(path[2:])
    return shlex.quote(path)

def format_command_for_log(command):
    """実行コマンドをログ用に安全に整形する"""
    return " ".join(shlex.quote(str(part)) for part in command)

def run_text_subprocess(command, check=True):
    """Windowsの既定cp932に依存せず、UTF-8出力を安全に捕捉する"""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )

def build_remote_client_command(kind):
    """ssh/scpの実行コマンドと共通オプションを組み立てる"""
    if kind == "scp":
        command = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_SCP", "scp", "scp")).strip()
        args = remote_whisper_list("DAVINCI_REMOTE_WHISPER_SCP_ARGS", "scp_args")
    else:
        command = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_SSH", "ssh", "ssh")).strip()
        args = remote_whisper_list("DAVINCI_REMOTE_WHISPER_SSH_ARGS", "ssh_args")

    identity_file = str(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_IDENTITY_FILE",
        "identity_file",
        "",
    )).strip()
    if identity_file:
        args = ["-i", identity_file] + args
    return [command] + args

def build_remote_target(host):
    """remote_whisper.userがあれば user@host の接続先にする"""
    user = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_USER", "user", "")).strip()
    if user and "@" not in host:
        return f"{user}@{host}"
    return host

def find_whisper_transcript_path(output_dir, source_video_path, min_mtime=None):
    """Whisperが出力したJSONを、名前揺れを許容して探す"""
    exact_path = output_dir / f"{source_video_path.stem}.json"
    if exact_path.exists() and (min_mtime is None or exact_path.stat().st_mtime >= min_mtime):
        return exact_path

    ignored_names = {"ai_edit_plan.json"}
    json_files = [
        path
        for path in output_dir.glob("*.json")
        if path.name not in ignored_names
        and (min_mtime is None or path.stat().st_mtime >= min_mtime)
    ]
    if not json_files:
        return None

    source_stem = source_video_path.stem.lower()
    matching_files = [path for path in json_files if source_stem in path.stem.lower()]
    candidates = matching_files or json_files
    return max(candidates, key=lambda path: path.stat().st_mtime)

def write_whisper_process_logs(output_dir, result):
    """Whisper実行時の標準出力・標準エラーを診断用に保存する"""
    stdout_text = getattr(result, "stdout", "") or ""
    stderr_text = getattr(result, "stderr", "") or ""
    if stdout_text:
        (output_dir / "whisper_stdout.log").write_text(
            stdout_text,
            encoding="utf-8",
            errors="replace",
        )
    if stderr_text:
        (output_dir / "whisper_stderr.log").write_text(
            stderr_text,
            encoding="utf-8",
            errors="replace",
        )

def build_whisper_command(whisper_command, source_video_path, output_dir, whisper_device, whisper_fp16):
    """Whisper CLIの実行コマンドを組み立てる"""
    return whisper_command + [
        str(source_video_path),
        "--language",
        configured_value("DAVINCI_WHISPER_LANGUAGE", "whisper_language", DEFAULT_WHISPER_LANGUAGE),
        "--task",
        "transcribe",
        "--device",
        whisper_device,
        "--fp16",
        whisper_fp16,
        "--output_format",
        "json",
        "--output_dir",
        str(output_dir),
    ]

def run_whisper_command(command, output_dir):
    """Whisperを実行し、標準出力・標準エラーを保存する"""
    try:
        result = run_text_subprocess(command, check=True)
        write_whisper_process_logs(output_dir, result)
        return True
    except subprocess.CalledProcessError as e:
        write_whisper_process_logs(output_dir, e)
        print(f"! whisper文字起こしに失敗しました: {e}")
        if e.stderr:
            print(e.stderr)
        return False

def prepare_remote_whisper_input(source_video_path, output_dir):
    """リモートWhisperへ送る入力ファイルを準備する"""
    upload_mode = str(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_UPLOAD",
        "upload",
        "audio",
    )).strip().lower()
    if upload_mode != "audio":
        return source_video_path

    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        print("! ffmpegが見つからないため、動画ファイルをそのままリモートへ転送します。")
        return source_video_path

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / f"{source_video_path.stem}.whisper_audio.m4a"
    if audio_path.exists() and audio_path.stat().st_mtime >= source_video_path.stat().st_mtime:
        print(f"✓ 既存のリモートWhisper用音声を再利用: {audio_path}")
        return audio_path

    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source_video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        str(audio_path),
    ]
    print("リモートWhisper用の音声を抽出中...")
    print("実行コマンド:", " ".join(command))
    try:
        run_text_subprocess(command, check=True)
        print(f"✓ 音声抽出完了: {audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"! 音声抽出に失敗しました。動画ファイルをそのまま転送します: {e}")
        if e.stderr:
            print(e.stderr)
        return source_video_path

def run_remote_command(ssh_command, host, remote_command, stdout_path=None, stderr_path=None, check=True):
    """SSHでリモートコマンドを実行する"""
    base_command = [ssh_command] if isinstance(ssh_command, str) else list(ssh_command)
    command = base_command + [host, remote_command]
    print("SSH実行:", format_command_for_log(command))
    result = run_text_subprocess(command, check=False)
    if stdout_path and result.stdout:
        stdout_path.write_text(result.stdout, encoding="utf-8", errors="replace")
    if stderr_path and result.stderr:
        stderr_path.write_text(result.stderr, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result

def run_remote_whisper_transcription(source_video_path, output_dir):
    """SSH先のGPUマシンでWhisperを実行し、JSONを回収する"""
    host = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_HOST", "host", "")).strip()
    if not host:
        print("! remote_whisper.host が未設定です。リモートWhisperをスキップします。")
        return None

    remote_target = build_remote_target(host)
    ssh_command = build_remote_client_command("ssh")
    scp_command = build_remote_client_command("scp")
    remote_command = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_COMMAND", "command", "whisper")).strip()
    remote_base_dir = str(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_DIR",
        "remote_dir",
        DEFAULT_REMOTE_WHISPER_DIR,
    )).strip()
    remote_device = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_DEVICE", "device", "cuda")).strip()
    remote_fp16_value = remote_whisper_value("DAVINCI_REMOTE_WHISPER_FP16", "fp16", False)
    remote_fp16 = select_whisper_fp16(remote_device) if str(remote_fp16_value).lower() == "auto" else (
        "True" if configured_bool(remote_fp16_value) else "False"
    )
    keep_remote_files = configured_bool(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_KEEP_FILES",
        "keep_remote_files",
        False,
    ))

    output_dir.mkdir(parents=True, exist_ok=True)
    source_mtime = source_video_path.stat().st_mtime
    transcript_path = find_whisper_transcript_path(output_dir, source_video_path, min_mtime=source_mtime)
    if transcript_path:
        print(f"✓ 既存の文字起こしJSONを再利用: {transcript_path}")
        return transcript_path

    upload_file = prepare_remote_whisper_input(source_video_path, output_dir)
    job_name = sanitize_remote_name(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source_video_path.stem}")
    remote_job_dir = remote_join(remote_base_dir, job_name)
    remote_input_name = sanitize_remote_name(upload_file.stem) + upload_file.suffix.lower()
    remote_input_path = remote_join(remote_job_dir, remote_input_name)

    stdout_path = output_dir / "whisper_stdout.log"
    stderr_path = output_dir / "whisper_stderr.log"

    print(f"リモートWhisperを使用します: {remote_target}")
    print(f"リモート作業ディレクトリ: {remote_job_dir}")
    try:
        run_remote_command(
            ssh_command,
            remote_target,
            f"mkdir -p {remote_shell_path(remote_job_dir)}",
            check=True,
        )

        print("リモートへWhisper入力ファイルを転送中...")
        upload_command = scp_command + [str(upload_file), f"{remote_target}:{remote_input_path}"]
        print("SCP実行:", format_command_for_log(upload_command))
        run_text_subprocess(upload_command, check=True)

        language = configured_value(
            "DAVINCI_WHISPER_LANGUAGE",
            "whisper_language",
            DEFAULT_WHISPER_LANGUAGE,
        )
        remote_run_command = (
            f"cd {remote_shell_path(remote_job_dir)} && "
            f"{remote_command} {shlex.quote(remote_input_name)} "
            f"--language {shlex.quote(str(language))} "
            f"--task transcribe "
            f"--device {shlex.quote(remote_device)} "
            f"--fp16 {shlex.quote(remote_fp16)} "
            f"--output_format json "
            f"--output_dir ."
        )
        print("リモートWhisper文字起こしを実行中...")
        print("実行コマンド:", remote_run_command)
        run_remote_command(
            ssh_command,
            remote_target,
            remote_run_command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            check=True,
        )

        list_result = run_remote_command(
            ssh_command,
            remote_target,
            f"cd {remote_shell_path(remote_job_dir)} && ls -1 *.json 2>/dev/null || true",
            check=False,
        )
        remote_json_names = [
            line.strip()
            for line in list_result.stdout.splitlines()
            if line.strip() and line.strip() != "ai_edit_plan.json"
        ]
        if not remote_json_names:
            print("! リモートWhisper実行後にJSONが見つかりませんでした。")
            return None

        for json_name in remote_json_names:
            download_command = scp_command + [
                f"{remote_target}:{remote_join(remote_job_dir, json_name)}",
                str(output_dir),
            ]
            print("SCP実行:", format_command_for_log(download_command))
            run_text_subprocess(download_command, check=True)

        transcript_path = find_whisper_transcript_path(output_dir, source_video_path)
        if transcript_path:
            print(f"✓ リモート文字起こしJSON取得: {transcript_path}")
            return transcript_path

        print("! JSONを取得しましたが、文字起こしJSONとして検出できませんでした。")
        return None
    except subprocess.CalledProcessError as e:
        print(f"! リモートWhisper処理に失敗しました: {e}")
        if e.stderr:
            stderr_path.write_text(e.stderr, encoding="utf-8", errors="replace")
            print(e.stderr)
        return None
    finally:
        if not keep_remote_files:
            try:
                run_remote_command(
                    ssh_command,
                    remote_target,
                    f"rm -rf {remote_shell_path(remote_job_dir)}",
                    check=False,
                )
            except Exception:
                pass

def run_local_whisper_transcription(source_video_path, output_dir):
    """whisper CLIがあれば文字起こしを実行し、JSONパスを返す"""
    whisper_command = resolve_whisper_command()
    if not whisper_command:
        print("! whisperが見つかりません。AI補助をスキップします。")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    source_mtime = source_video_path.stat().st_mtime
    transcript_path = find_whisper_transcript_path(output_dir, source_video_path, min_mtime=source_mtime)
    if transcript_path:
        print(f"✓ 既存の文字起こしJSONを再利用: {transcript_path}")
        return transcript_path

    whisper_device = select_whisper_device()
    whisper_fp16 = select_whisper_fp16(whisper_device)
    command = build_whisper_command(
        whisper_command,
        source_video_path,
        output_dir,
        whisper_device,
        whisper_fp16,
    )
    print("whisper文字起こしを実行中...")
    print(f"Whisper device: {whisper_device}")
    print(f"Whisper fp16: {whisper_fp16}")
    print("実行コマンド:", " ".join(command))

    if not run_whisper_command(command, output_dir):
        return None

    transcript_path = find_whisper_transcript_path(output_dir, source_video_path)
    if transcript_path:
        print(f"✓ 文字起こしJSON作成: {transcript_path}")
        return transcript_path

    if whisper_fp16 == "True":
        print("! JSONが見つかりません。FP16を無効化して再実行します。")
        retry_command = build_whisper_command(
            whisper_command,
            source_video_path,
            output_dir,
            whisper_device,
            "False",
        )
        print("再実行コマンド:", " ".join(retry_command))
        if not run_whisper_command(retry_command, output_dir):
            return None
        transcript_path = find_whisper_transcript_path(output_dir, source_video_path)
        if transcript_path:
            print(f"✓ 文字起こしJSON作成: {transcript_path}")
            return transcript_path

    print("! whisper実行後にJSONが見つかりませんでした。")
    print(f"  診断ログ: {output_dir / 'whisper_stdout.log'} / {output_dir / 'whisper_stderr.log'}")
    return None

def run_whisper_transcription(source_video_path, output_dir):
    """設定されたバックエンドでWhisper文字起こしを実行する"""
    backend = select_whisper_backend()
    if backend in ("ssh", "remote"):
        return run_remote_whisper_transcription(source_video_path, output_dir)
    return run_local_whisper_transcription(source_video_path, output_dir)

def choose_hook_text(segments):
    """冒頭に置く短い結論カードの文言を決める"""
    useful_segments = [s for s in segments if segment_is_useful(s)]
    if not useful_segments:
        return ""

    cue_segments = [s for s in useful_segments[:24] if segment_has_key_cue(s)]
    chosen = cue_segments[0] if cue_segments else useful_segments[0]
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

def build_key_point_cues(segments):
    """発話内容からキーポイントマーカー候補を作る"""
    cues = []
    seen = set()
    for segment in segments:
        if not segment_has_key_cue(segment):
            continue
        label = key_point_label(segment)
        bucket = (label.lower(), int(segment["start"] // 30))
        if bucket in seen:
            continue
        seen.add(bucket)
        cues.append({
            "time": segment["start"],
            "label": label,
            "terms": extract_terms_from_text(segment["text"]),
            "note": shorten_text(segment["text"], 60),
        })
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

def describe_ai_dependencies():
    """AI補助に必要な外部ツールの状態を返す"""
    try:
        import PIL
        pillow_status = getattr(PIL, "__version__", "available")
    except ImportError:
        pillow_status = ""

    whisper_backend = select_whisper_backend()
    status = {
        "script_version": SCRIPT_VERSION,
        "whisper_backend": whisper_backend,
        "whisper": " ".join(resolve_whisper_command()),
        "whisper_device": select_whisper_device(),
        "whisper_fp16": select_whisper_fp16(select_whisper_device()),
        "ffmpeg": shutil.which("ffmpeg") or "",
        "pillow": pillow_status,
    }
    if whisper_backend in ("ssh", "remote"):
        remote_device = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_DEVICE", "device", "cuda"))
        remote_fp16_value = remote_whisper_value("DAVINCI_REMOTE_WHISPER_FP16", "fp16", False)
        remote_fp16 = select_whisper_fp16(remote_device) if str(remote_fp16_value).lower() == "auto" else (
            "True" if configured_bool(remote_fp16_value) else "False"
        )
        status["whisper"] = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_COMMAND", "command", "whisper"))
        status["whisper_device"] = remote_device
        status["whisper_fp16"] = remote_fp16
        remote_host = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_HOST", "host", ""))
        remote_user = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_USER", "user", ""))
        status["remote_whisper_host"] = remote_host
        status["remote_whisper_user"] = remote_user
        status["remote_whisper_target"] = build_remote_target(remote_host) if remote_host else ""
        status["remote_whisper_dir"] = str(remote_whisper_value(
            "DAVINCI_REMOTE_WHISPER_DIR",
            "remote_dir",
            DEFAULT_REMOTE_WHISPER_DIR,
        ))
        status["remote_whisper_upload"] = str(remote_whisper_value(
            "DAVINCI_REMOTE_WHISPER_UPLOAD",
            "upload",
            "audio",
        ))
        status["remote_whisper_identity_configured"] = bool(str(remote_whisper_value(
            "DAVINCI_REMOTE_WHISPER_IDENTITY_FILE",
            "identity_file",
            "",
        )).strip())
    else:
        status.update(get_torch_status())
    return status

def empty_ai_plan(reason, dependencies=None):
    """AI補助が動かなかった理由つきの空プランを返す"""
    return {
        "enabled": False,
        "script_version": SCRIPT_VERSION,
        "skip_reason": reason,
        "dependencies": dependencies or {},
        "hook_text": "",
        "hook_asset_path": "",
        "chapters": [],
        "key_point_cues": [],
        "qc_notes": [],
        "source_duration": 0,
    }

def write_ai_assist_files(ai_plan, output_dir):
    """後段や手動確認用のファイルを書き出す"""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "ai_edit_plan.json"
    chapters_path = output_dir / "chapters_draft.txt"
    status_path = output_dir / "ai_assist_status.txt"

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(ai_plan, f, ensure_ascii=False, indent=2)

    with open(chapters_path, "w", encoding="utf-8") as f:
        for chapter in ai_plan.get("chapters", []):
            seconds = int(chapter["time"])
            f.write(f"{seconds // 60:02d}:{seconds % 60:02d} {chapter['title']}\n")

    dependencies = ai_plan.get("dependencies", {})
    with open(status_path, "w", encoding="utf-8") as f:
        f.write("AI Assist Status\n")
        f.write("================\n")
        f.write(f"script_version: {ai_plan.get('script_version') or SCRIPT_VERSION}\n")
        f.write(f"enabled: {bool(ai_plan.get('enabled'))}\n")
        if ai_plan.get("skip_reason"):
            f.write(f"skip_reason: {ai_plan['skip_reason']}\n")
        f.write(f"whisper_backend: {dependencies.get('whisper_backend') or 'local'}\n")
        if dependencies.get("remote_whisper_host"):
            f.write(f"remote_whisper_host: {dependencies.get('remote_whisper_host')}\n")
            f.write(f"remote_whisper_user: {dependencies.get('remote_whisper_user') or ''}\n")
            f.write(f"remote_whisper_target: {dependencies.get('remote_whisper_target') or ''}\n")
            f.write(f"remote_whisper_dir: {dependencies.get('remote_whisper_dir') or ''}\n")
            f.write(f"remote_whisper_upload: {dependencies.get('remote_whisper_upload') or ''}\n")
            f.write(
                "remote_whisper_identity_configured: "
                f"{dependencies.get('remote_whisper_identity_configured')}\n"
            )
        f.write(f"whisper: {dependencies.get('whisper') or 'NOT FOUND'}\n")
        f.write(f"whisper_device: {dependencies.get('whisper_device') or 'NOT SET'}\n")
        f.write(f"whisper_fp16: {dependencies.get('whisper_fp16') or 'NOT SET'}\n")
        f.write(f"torch: {dependencies.get('torch') or 'NOT FOUND'}\n")
        f.write(f"torch_cuda_available: {dependencies.get('torch_cuda_available')}\n")
        f.write(f"torch_cuda_version: {dependencies.get('torch_cuda_version') or ''}\n")
        f.write(f"torch_cuda_device: {dependencies.get('torch_cuda_device') or ''}\n")
        f.write(f"ffmpeg: {dependencies.get('ffmpeg') or 'NOT FOUND'}\n")
        f.write(f"pillow: {dependencies.get('pillow') or 'NOT FOUND'}\n")
        f.write(f"hook_asset_path: {ai_plan.get('hook_asset_path') or ''}\n")
        f.write(f"chapters: {len(ai_plan.get('chapters', []))}\n")
        f.write(f"key_point_cues: {len(ai_plan.get('key_point_cues', []))}\n")
        f.write(f"qc_notes: {len(ai_plan.get('qc_notes', []))}\n")

    print(f"✓ AI編集プランを書き出しました: {plan_path}")
    print(f"✓ チャプター草案を書き出しました: {chapters_path}")
    print(f"✓ AI補助ステータスを書き出しました: {status_path}")

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
        run_text_subprocess(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"! フックカード動画の生成に失敗しました: {e}")
        if e.stderr:
            print(e.stderr)
        return None

    print(f"✓ フックカード動画を作成しました: {video_path}")
    return str(video_path)

def build_ai_assist_plan(source_video_path, working_dir):
    """文字起こしからDaVinci上に置く補助情報を作る。失敗時は空プランを返す。"""
    dependencies = describe_ai_dependencies()
    output_dir = Path(working_dir) / AI_ASSIST_DIR_NAME
    print("AI補助の依存ツール状態:")
    print(f"  whisper_backend: {dependencies.get('whisper_backend') or 'local'}")
    if dependencies.get("remote_whisper_host"):
        print(f"  remote_whisper_host: {dependencies.get('remote_whisper_host')}")
        print(f"  remote_whisper_user: {dependencies.get('remote_whisper_user') or ''}")
        print(f"  remote_whisper_target: {dependencies.get('remote_whisper_target') or ''}")
        print(f"  remote_whisper_upload: {dependencies.get('remote_whisper_upload')}")
        print(
            "  remote_whisper_identity_configured: "
            f"{dependencies.get('remote_whisper_identity_configured')}"
        )
    print(f"  whisper: {dependencies.get('whisper') or 'NOT FOUND'}")
    print(f"  whisper_device: {dependencies.get('whisper_device') or 'NOT SET'}")
    print(f"  whisper_fp16: {dependencies.get('whisper_fp16') or 'NOT SET'}")
    print(f"  torch: {dependencies.get('torch') or 'NOT FOUND'}")
    print(f"  torch CUDA: {dependencies.get('torch_cuda_available')}")
    if dependencies.get("torch_cuda_device"):
        print(f"  torch CUDA device: {dependencies.get('torch_cuda_device')}")
    print(f"  ffmpeg: {dependencies.get('ffmpeg') or 'NOT FOUND'}")
    print(f"  Pillow: {dependencies.get('pillow') or 'NOT FOUND'}")

    if not AI_ASSIST_ENABLED:
        print("! DAVINCI_AI_ASSIST=0 のためAI補助をスキップします。")
        ai_plan = empty_ai_plan("DAVINCI_AI_ASSIST=0", dependencies)
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan

    try:
        transcript_path = run_whisper_transcription(Path(source_video_path), output_dir)
        if not transcript_path:
            ai_plan = empty_ai_plan(
                "whisper CLI is missing or transcription failed",
                dependencies,
            )
            write_ai_assist_files(ai_plan, output_dir)
            return ai_plan

        segments = load_transcript_segments(transcript_path)
        if not segments:
            print("! 文字起こしセグメントが空です。AI補助をスキップします。")
            ai_plan = empty_ai_plan("transcript has no usable segments", dependencies)
            write_ai_assist_files(ai_plan, output_dir)
            return ai_plan

        ai_plan = {
            "enabled": True,
            "script_version": SCRIPT_VERSION,
            "source_video": str(source_video_path),
            "transcript_path": str(transcript_path),
            "skip_reason": "",
            "dependencies": dependencies,
            "hook_text": choose_hook_text(segments),
            "chapters": build_chapters(segments),
            "key_point_cues": build_key_point_cues(segments),
            "qc_notes": build_qc_notes(segments),
            "source_duration": segments[-1]["end"],
        }
        hook_asset_path = create_hook_card_asset(ai_plan, output_dir)
        ai_plan["hook_asset_path"] = hook_asset_path or ""
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan
    except Exception as e:
        print(f"! AI補助処理でエラーが発生しました。従来処理を続行します: {e}")
        ai_plan = empty_ai_plan(f"AI assist error: {e}", dependencies)
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan

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
    if not hasattr(timeline, "AddMarker"):
        print("! このResolve APIではAddMarkerが使えません。マーカー追加をスキップします。")
        return
    if not ai_plan.get("enabled"):
        reason = ai_plan.get("skip_reason") or "AI assist did not run"
        try:
            timeline.AddMarker(int(start_frame), "Red", "AI Assist skipped", reason, 1, "")
            print(f"! AI補助はスキップされました。理由: {reason}")
        except Exception as e:
            print(f"! AI補助スキップマーカー追加エラー: {e}")
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

    for cue in ai_plan.get("key_point_cues", []):
        add_marker(float(cue["time"]), "Yellow", "Key point: " + cue["label"], cue.get("note", ""))

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
        print("  config.local.json / config.json の working_dirs、または環境変数 DAVINCI_WORKING_DIRS を確認してください")
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
        print("  config.local.json / config.json の xml_dirs、または環境変数 DAVINCI_XML_DIRS を確認してください")
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
    video_paths = configured_paths("DAVINCI_VIDEO_PATH", "video_path")
    ending_clip_name = configured_value("DAVINCI_ENDING_CLIP_NAME", "ending_clip_name", DEFAULT_ENDING_CLIP_NAME)
    ending_video_path = find_clip_path(video_paths, ending_clip_name)
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
        print(f"! エンディング動画が見つかりません（スキップ）: {ending_clip_name}")
        print("  config.local.json / config.json の video_path / ending_clip_name を確認してください")
    
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
