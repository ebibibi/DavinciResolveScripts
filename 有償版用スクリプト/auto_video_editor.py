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

SCRIPT_VERSION = "2026-07-08-text-v2-markers-v1"
GIT_PULL_DONE_ENV = "DAVINCI_GIT_PULL_DONE"

def update_repository_before_start():
    """実行前にリポジトリを更新する。更新が入った場合は最新スクリプトで再起動する。"""
    if os.environ.get(GIT_PULL_DONE_ENV) == "1":
        return

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    if not (repo_root / ".git").exists():
        print(f"! Git repository was not found at {repo_root}. Cannot run git pull.")
        sys.exit(1)

    git_exe = shutil.which("git")
    if not git_exe:
        print("! git was not found. Install git or run from a cloned repository.")
        sys.exit(1)

    print("Updating DavinciResolveScripts with git pull --ff-only --autostash...")
    result = subprocess.run(
        [git_exe, "pull", "--ff-only", "--autostash"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    if result.returncode != 0:
        print("! git pull failed. Resolve the repository state before running the editor.")
        sys.exit(result.returncode)

    os.environ[GIT_PULL_DONE_ENV] = "1"
    if "Updating " in result.stdout or "Fast-forward" in result.stdout:
        print("Repository was updated. Restarting with the latest script...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

update_repository_before_start()

print("DaVinci Resolve自動動画編集スクリプト（有償版）開始")
print(f"Script version: {SCRIPT_VERSION}")

AI_ASSIST_ENABLED = os.environ.get("DAVINCI_AI_ASSIST", "1").lower() not in ("0", "false", "no")
AI_ASSIST_DIR_NAME = "_ai_assist"
HOOK_CARD_SECONDS = 4
CHAPTER_TITLE_SECONDS = 3
KEY_POINT_TITLE_SECONDS = 4
TEXT_TITLE_TRACK_INDEX = 2
TEXT_TITLE_FONT = "HGPSoeiKakugothicUB"
CHAPTER_INTERVAL_SECONDS = 180
DEFAULT_OP_CLIP_NAME = "01_EBI_CHAN_OP"
DEFAULT_ENDING_CLIP_NAME = "03_EBI_CHAN_IN.mov"
DEFAULT_SECTION_BREAK_CLIP_NAMES = ["02_EBI_CHAN_OP.mov", "03_EBI_CHAN_IN.mov"]
DEFAULT_WHISPER_LANGUAGE = "Japanese"
DEFAULT_WHISPER_DEVICE = "auto"
DEFAULT_WHISPER_FP16 = "false"
DEFAULT_WHISPER_WORD_TIMESTAMPS = True
DEFAULT_WHISPER_BACKEND = "local"
DEFAULT_REMOTE_WHISPER_DIR = "davinci-whisper-jobs"
DEFAULT_REMOTE_WHISPER_PROFILE = "speed"
DEFAULT_REMOTE_WHISPER_MODEL = "turbo"
DEFAULT_REMOTE_WHISPER_BEAM_SIZE = 1
DEFAULT_REMOTE_WHISPER_BEST_OF = 1
DEFAULT_REMOTE_WHISPER_VERBOSE = False
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

def has_config_value(value):
    """Falseや0は有効値として扱い、空文字/Noneだけ未設定にする"""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True

def configured_value(env_name, config_key, default_value):
    """環境変数またはローカル設定ファイルから単一値を取得"""
    env_value = os.environ.get(env_name)
    if has_config_value(env_value):
        return env_value
    config_value = LOCAL_CONFIG.get(config_key)
    if has_config_value(config_value):
        return config_value
    return default_value

def config_section(config_key):
    """ローカル設定ファイルのセクションをdictとして取得"""
    value = LOCAL_CONFIG.get(config_key)
    return value if isinstance(value, dict) else {}

def config_raw_value(config_key, default_value=None):
    """ローカル設定ファイルの値をそのまま取得"""
    return LOCAL_CONFIG.get(config_key, default_value)

def configured_section_value(env_name, section_key, value_key, default_value):
    """環境変数またはローカル設定セクションから単一値を取得"""
    env_value = os.environ.get(env_name)
    if has_config_value(env_value):
        return env_value
    section = config_section(section_key)
    section_value = section.get(value_key)
    if has_config_value(section_value):
        return section_value
    return default_value

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

def configured_top_level_bool(env_name, config_key, default_value=False):
    """環境変数またはローカル設定からboolを取得"""
    env_value = os.environ.get(env_name)
    if has_config_value(env_value):
        return configured_bool(env_value, default_value)
    return configured_bool(LOCAL_CONFIG.get(config_key), default_value)

def ai_edit_action_value(key, default_value=None):
    """ai_edit_actionsセクションの値を取得"""
    section = config_section("ai_edit_actions")
    value = section.get(key)
    return value if has_config_value(value) else default_value

def ai_edit_action_enabled(key, default_value=True):
    """ai_edit_actionsの機能フラグを取得"""
    return configured_bool(ai_edit_action_value(key, default_value), default_value)

def experimental_full_actions_enabled():
    """SEや区切り動画など、まだ荒い実験機能の安全弁"""
    return ai_edit_action_enabled("experimental_full_actions", False)

def ai_edit_action_int(key, default_value):
    """ai_edit_actionsの整数値を取得"""
    try:
        return int(ai_edit_action_value(key, default_value))
    except Exception:
        return int(default_value)

def ai_edit_action_float(key, default_value):
    """ai_edit_actionsの小数値を取得"""
    try:
        return float(ai_edit_action_value(key, default_value))
    except Exception:
        return float(default_value)

def configured_section_break_clip_names():
    """区切り動画ファイル名のリストを取得"""
    env_value = os.environ.get("DAVINCI_SECTION_BREAK_CLIP_NAMES")
    if env_value:
        return [item.strip().strip('"') for item in env_value.split(os.pathsep) if item.strip()]

    value = config_raw_value("section_break_clip_names")
    if isinstance(value, list):
        return [str(item).strip().strip('"') for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip().strip('"') for item in value.split(os.pathsep) if item.strip()]
    return list(DEFAULT_SECTION_BREAK_CLIP_NAMES)

def configured_sound_effects():
    """SE自動挿入用の設定リストを取得"""
    value = config_raw_value("sound_effects", [])
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    effects = []
    for item in value:
        if not isinstance(item, dict):
            continue
        clip_name = str(item.get("clip_name") or item.get("path") or "").strip()
        if not clip_name:
            continue
        effects.append({
            "name": str(item.get("name") or Path(clip_name).stem),
            "clip_name": clip_name,
            "trigger": str(item.get("trigger") or "key_point"),
            "track_index": int(item.get("track_index") or 3),
            "cooldown_seconds": float(item.get("cooldown_seconds") or 20),
        })
    return effects

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
    """短い表示ラベルにしやすい形へ整える"""
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
    """Text+表示に使う短いラベルを作る"""
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
        words = []
        for word in item.get("words", []) or []:
            try:
                word_start = float(word.get("start", start))
                word_end = float(word.get("end", end))
            except (TypeError, ValueError):
                continue
            word_text = clean_text(word.get("word", ""))
            if word_text:
                words.append({"start": word_start, "end": word_end, "word": word_text})
        segments.append({"start": start, "end": end, "text": text, "words": words})
    return segments

def resolve_whisper_command():
    """whisper CLIまたはPythonモジュール実行のコマンドを返す"""
    whisper_exe = shutil.which("whisper")
    if whisper_exe:
        return [whisper_exe]
    try:
        if importlib.util.find_spec("whisper.__main__"):
            return [sys.executable, "-m", "whisper"]
    except (ImportError, ModuleNotFoundError, ValueError):
        return []
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

def select_whisper_word_timestamps():
    """Whisperの単語タイムスタンプ利用有無を選ぶ"""
    return "True" if configured_top_level_bool(
        "DAVINCI_WHISPER_WORD_TIMESTAMPS",
        "whisper_word_timestamps",
        DEFAULT_WHISPER_WORD_TIMESTAMPS,
    ) else "False"

def remote_whisper_value(env_name, value_key, default_value):
    """remote_whisperセクションの値を取得"""
    return configured_section_value(env_name, "remote_whisper", value_key, default_value)

def remote_whisper_list(env_name, value_key):
    """remote_whisperセクションのリスト値を取得"""
    return configured_section_list(env_name, "remote_whisper", value_key)

def remote_whisper_profile():
    """リモートWhisperの実行プロファイルを取得"""
    return str(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_PROFILE",
        "profile",
        DEFAULT_REMOTE_WHISPER_PROFILE,
    )).strip().lower()

def is_remote_speed_profile(profile):
    """GPU性能優先のプロファイルかどうか"""
    return profile in ("speed", "spark", "performance", "fast")

def select_remote_whisper_fp16(remote_device, profile):
    """リモートWhisperのFP16設定。速度プロファイルではCUDAのFP16を優先する。"""
    if is_remote_speed_profile(profile) and str(remote_device).strip().lower().startswith("cuda"):
        return "True"

    value = remote_whisper_value("DAVINCI_REMOTE_WHISPER_FP16", "fp16", "auto")
    normalized = str(value).strip().lower()
    if normalized == "auto":
        return "True" if str(remote_device).strip().lower().startswith(("cuda", "mps")) else "False"
    return "True" if configured_bool(value) else "False"

def remote_whisper_option(env_name, value_key, default_value):
    """リモートWhisperのCLIオプション値を文字列として取得"""
    return str(remote_whisper_value(env_name, value_key, default_value)).strip()

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
        "--word_timestamps",
        select_whisper_word_timestamps(),
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
    profile = remote_whisper_profile()
    remote_device = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_DEVICE", "device", "cuda")).strip()
    remote_fp16 = select_remote_whisper_fp16(remote_device, profile)
    remote_model = remote_whisper_option(
        "DAVINCI_REMOTE_WHISPER_MODEL",
        "model",
        DEFAULT_REMOTE_WHISPER_MODEL,
    )
    remote_beam_size = remote_whisper_option(
        "DAVINCI_REMOTE_WHISPER_BEAM_SIZE",
        "beam_size",
        DEFAULT_REMOTE_WHISPER_BEAM_SIZE,
    )
    remote_best_of = remote_whisper_option(
        "DAVINCI_REMOTE_WHISPER_BEST_OF",
        "best_of",
        DEFAULT_REMOTE_WHISPER_BEST_OF,
    )
    remote_verbose = "True" if configured_bool(remote_whisper_value(
        "DAVINCI_REMOTE_WHISPER_VERBOSE",
        "verbose",
        DEFAULT_REMOTE_WHISPER_VERBOSE,
    )) else "False"
    remote_extra_args = remote_whisper_list("DAVINCI_REMOTE_WHISPER_EXTRA_ARGS", "extra_args")
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
        remote_args = [
            remote_input_name,
            "--model", remote_model,
            "--language", str(language),
            "--task", "transcribe",
            "--device", remote_device,
            "--fp16", remote_fp16,
            "--word_timestamps", select_whisper_word_timestamps(),
            "--beam_size", remote_beam_size,
            "--best_of", remote_best_of,
            "--verbose", remote_verbose,
            "--output_format", "json",
            "--output_dir", ".",
        ] + remote_extra_args
        remote_run_command = (
            f"cd {remote_shell_path(remote_job_dir)} && "
            f"{remote_command} "
            + " ".join(shlex.quote(str(part)) for part in remote_args)
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
    """発話内容からキーポイントText+候補を作る"""
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

def build_caption_cues(segments):
    """通常テロップ用の短い字幕候補を作る"""
    cues = []
    max_captions = ai_edit_action_int("max_captions", 12)
    min_gap_seconds = ai_edit_action_float("caption_min_gap_seconds", 8.0)
    last_time = -999999.0
    for segment in segments:
        if not segment_is_useful(segment):
            continue
        segment_start = float(segment["start"])
        if segment_start - last_time < min_gap_seconds:
            continue
        text = shorten_text(segment["text"], 42)
        if not text:
            continue
        duration = max(1.5, min(5.0, float(segment["end"]) - float(segment["start"])))
        cues.append({
            "time": segment_start,
            "duration": duration,
            "text": text,
        })
        last_time = segment_start
        if len(cues) >= max_captions:
            break
    return cues

def build_ai_edit_actions(ai_plan, segments):
    """AI補助結果からResolveに適用する編集アクションを作る"""
    actions = []

    if ai_plan.get("hook_text"):
        actions.append({
            "type": "hook_card",
            "time": 0.0,
            "duration": HOOK_CARD_SECONDS,
            "text": ai_plan["hook_text"],
        })

    if ai_edit_action_enabled("captions", False):
        for cue in build_caption_cues(segments):
            actions.append({
                "type": "text_title",
                "style": "caption",
                "time": cue["time"],
                "duration": cue["duration"],
                "text": cue["text"],
            })

    if ai_edit_action_enabled("key_point_titles", True):
        for cue in ai_plan.get("key_point_cues", []):
            actions.append({
                "type": "text_title",
                "style": "key_point",
                "time": float(cue["time"]),
                "duration": KEY_POINT_TITLE_SECONDS,
                "text": build_key_point_title_text(cue),
            })

    if experimental_full_actions_enabled() and ai_edit_action_enabled("section_cards", False):
        for chapter in ai_plan.get("chapters", [])[1:]:
            title = wrap_hook_text_for_title(chapter.get("title", ""), width=20, max_lines=2)
            actions.append({
                "type": "text_title",
                "style": "section_card",
                "time": float(chapter["time"]),
                "duration": 4.0,
                "text": f"SECTION\n{title}" if title else "SECTION",
            })

    if experimental_full_actions_enabled() and ai_edit_action_enabled("section_break_videos", False):
        for chapter in ai_plan.get("chapters", [])[1:]:
            for clip_name in configured_section_break_clip_names():
                actions.append({
                    "type": "media_clip",
                    "style": "section_break",
                    "time": float(chapter["time"]),
                    "duration": 0,
                    "clip_name": clip_name,
                    "media_type": 1,
                    "track_index": 2,
                })

    if experimental_full_actions_enabled() and ai_edit_action_enabled("sound_effects", False):
        effects = configured_sound_effects()
        key_point_effects = [effect for effect in effects if effect["trigger"] in ("key_point", "keypoint")]
        if key_point_effects:
            last_by_effect = {}
            for cue in ai_plan.get("key_point_cues", []):
                cue_time = float(cue["time"])
                for effect in key_point_effects:
                    last_time = last_by_effect.get(effect["name"], -999999)
                    if cue_time - last_time < effect["cooldown_seconds"]:
                        continue
                    actions.append({
                        "type": "sound_effect",
                        "style": "key_point",
                        "time": cue_time,
                        "duration": 0,
                        "clip_name": effect["clip_name"],
                        "media_type": 2,
                        "track_index": effect["track_index"],
                    })
                    last_by_effect[effect["name"]] = cue_time
                    break

    return sorted(actions, key=lambda action: float(action.get("time", 0)))

def describe_ai_dependencies():
    """AI補助に必要な外部ツールの状態を返す"""
    whisper_backend = select_whisper_backend()
    status = {
        "script_version": SCRIPT_VERSION,
        "whisper_backend": whisper_backend,
        "whisper": " ".join(resolve_whisper_command()),
        "whisper_device": select_whisper_device(),
        "whisper_fp16": select_whisper_fp16(select_whisper_device()),
        "whisper_word_timestamps": select_whisper_word_timestamps(),
        "ffmpeg": shutil.which("ffmpeg") or "",
    }
    if whisper_backend in ("ssh", "remote"):
        profile = remote_whisper_profile()
        remote_device = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_DEVICE", "device", "cuda"))
        remote_fp16 = select_remote_whisper_fp16(remote_device, profile)
        status["whisper"] = str(remote_whisper_value("DAVINCI_REMOTE_WHISPER_COMMAND", "command", "whisper"))
        status["whisper_device"] = remote_device
        status["whisper_fp16"] = remote_fp16
        status["remote_whisper_profile"] = profile
        status["remote_whisper_model"] = remote_whisper_option(
            "DAVINCI_REMOTE_WHISPER_MODEL",
            "model",
            DEFAULT_REMOTE_WHISPER_MODEL,
        )
        status["remote_whisper_beam_size"] = remote_whisper_option(
            "DAVINCI_REMOTE_WHISPER_BEAM_SIZE",
            "beam_size",
            DEFAULT_REMOTE_WHISPER_BEAM_SIZE,
        )
        status["remote_whisper_best_of"] = remote_whisper_option(
            "DAVINCI_REMOTE_WHISPER_BEST_OF",
            "best_of",
            DEFAULT_REMOTE_WHISPER_BEST_OF,
        )
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
        "hook_insert_mode": "",
        "timeline_insert_mode": "",
        "chapters": [],
        "key_point_cues": [],
        "qc_notes": [],
        "actions": [],
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
            f.write(f"remote_whisper_profile: {dependencies.get('remote_whisper_profile') or ''}\n")
            f.write(f"remote_whisper_model: {dependencies.get('remote_whisper_model') or ''}\n")
            f.write(f"remote_whisper_beam_size: {dependencies.get('remote_whisper_beam_size') or ''}\n")
            f.write(f"remote_whisper_best_of: {dependencies.get('remote_whisper_best_of') or ''}\n")
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
        f.write(f"whisper_word_timestamps: {dependencies.get('whisper_word_timestamps') or 'NOT SET'}\n")
        f.write(f"torch: {dependencies.get('torch') or 'NOT FOUND'}\n")
        f.write(f"torch_cuda_available: {dependencies.get('torch_cuda_available')}\n")
        f.write(f"torch_cuda_version: {dependencies.get('torch_cuda_version') or ''}\n")
        f.write(f"torch_cuda_device: {dependencies.get('torch_cuda_device') or ''}\n")
        f.write(f"ffmpeg: {dependencies.get('ffmpeg') or 'NOT FOUND'}\n")
        f.write(f"hook_asset_path: {ai_plan.get('hook_asset_path') or ''}\n")
        f.write(f"hook_insert_mode: {ai_plan.get('hook_insert_mode') or ''}\n")
        f.write(f"timeline_insert_mode: {ai_plan.get('timeline_insert_mode') or ''}\n")
        f.write(f"chapters: {len(ai_plan.get('chapters', []))}\n")
        f.write(f"key_point_cues: {len(ai_plan.get('key_point_cues', []))}\n")
        f.write(f"qc_notes: {len(ai_plan.get('qc_notes', []))}\n")
        f.write(f"actions: {len(ai_plan.get('actions', []))}\n")

    print(f"✓ AI編集プランを書き出しました: {plan_path}")
    print(f"✓ チャプター草案を書き出しました: {chapters_path}")
    print(f"✓ AI補助ステータスを書き出しました: {status_path}")

def prepare_editable_hook_card(ai_plan):
    """Resolve上で編集可能なフックカード挿入モードをプランに記録する"""
    hook_text = ai_plan.get("hook_text")
    if not hook_text:
        return None
    ai_plan["hook_asset_path"] = ""
    ai_plan["hook_insert_mode"] = "resolve_editable_text_plus"
    print("✓ フックカードはmp4ではなく、Resolve上で編集可能なText+/Fusionタイトルとして追加します。")
    return ai_plan["hook_insert_mode"]

def build_ai_assist_plan(source_video_path, working_dir):
    """文字起こしからDaVinci上に置く補助情報を作る。失敗時は空プランを返す。"""
    dependencies = describe_ai_dependencies()
    output_dir = Path(working_dir) / AI_ASSIST_DIR_NAME
    print("AI補助の依存ツール状態:")
    print(f"  whisper_backend: {dependencies.get('whisper_backend') or 'local'}")
    if dependencies.get("remote_whisper_host"):
        print(f"  remote_whisper_profile: {dependencies.get('remote_whisper_profile') or ''}")
        print(f"  remote_whisper_model: {dependencies.get('remote_whisper_model') or ''}")
        print(f"  remote_whisper_beam_size: {dependencies.get('remote_whisper_beam_size') or ''}")
        print(f"  remote_whisper_best_of: {dependencies.get('remote_whisper_best_of') or ''}")
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
            "timeline_insert_mode": "resolve_editable_text_plus",
        }
        prepare_editable_hook_card(ai_plan)
        ai_plan["actions"] = build_ai_edit_actions(ai_plan, segments)
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan
    except Exception as e:
        print(f"! AI補助処理でエラーが発生しました。従来処理を続行します: {e}")
        ai_plan = empty_ai_plan(f"AI assist error: {e}", dependencies)
        write_ai_assist_files(ai_plan, output_dir)
        return ai_plan

def wrap_hook_text_for_title(text, width=18, max_lines=4):
    """Text+で読みやすいように、空白あり/なしの文を軽く折り返す"""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    if re.search(r"\s", text):
        lines = textwrap.wrap(text, width=width)
    else:
        lines = [text[index:index + width] for index in range(0, len(text), width)]
    return "\n".join(lines[:max_lines])

def get_first_fusion_tool(comp, tool_type):
    """Fusion composition内の最初の指定toolを返す"""
    if comp is None or not hasattr(comp, "GetToolList"):
        return None
    try:
        tools = comp.GetToolList(False, tool_type)
    except Exception:
        return None
    if isinstance(tools, dict):
        return next(iter(tools.values()), None)
    if isinstance(tools, list):
        return tools[0] if tools else None
    return None

def set_fusion_input(tool, name, value):
    """Fusion tool inputを、API差分に耐える形で設定する"""
    if tool is None:
        return False
    try:
        result = tool.SetInput(name, value)
        if result is not False:
            return True
    except Exception:
        pass
    try:
        setattr(tool, name, value)
        return True
    except Exception:
        return False

def configure_text_title_item(timeline_item, text, *, size=0.075, color=None, clip_color="Teal"):
    """挿入したText+/Fusionタイトルの表示文言と基本スタイルを設定する"""
    if timeline_item is None:
        return False
    try:
        timeline_item.SetClipColor(clip_color)
    except Exception:
        pass

    comp = None
    try:
        if hasattr(timeline_item, "GetFusionCompCount") and timeline_item.GetFusionCompCount() >= 1:
            comp = timeline_item.GetFusionCompByIndex(1)
    except Exception:
        comp = None
    if comp is None:
        try:
            comp = timeline_item.AddFusionComp()
        except Exception:
            comp = None

    text_tool = get_first_fusion_tool(comp, "TextPlus")
    if text_tool is None:
        print("! Text+ツールを見つけられませんでした。タイトルはResolve上で手動編集してください。")
        return False

    configured = set_fusion_input(text_tool, "StyledText", text)
    red, green, blue = color or (0.92, 0.96, 1.0)

    style_inputs = {
        "Size": size,
        "Font": TEXT_TITLE_FONT,
        "Red1": red,
        "Green1": green,
        "Blue1": blue,
        "HorizontalJustification": 1,
        "VerticalJustification": 1,
    }
    for input_name, value in style_inputs.items():
        set_fusion_input(text_tool, input_name, value)

    if configured:
        print("✓ Text+の文言を設定しました。Resolve上で直接編集できます。")
    return configured

def configure_hook_title_item(timeline_item, hook_text):
    """挿入したフックカードタイトルの文言と基本スタイルを設定する"""
    body_text = wrap_hook_text_for_title(hook_text)
    title_text = f"AI DRAFT HOOK\n\n{body_text}" if body_text else "AI DRAFT HOOK"
    return configure_text_title_item(
        timeline_item,
        title_text,
        size=0.075,
        color=(0.92, 0.96, 1.0),
        clip_color="Teal",
    )

def ensure_video_track(timeline, track_index):
    """指定したビデオトラックが存在するように追加する"""
    try:
        while int(timeline.GetTrackCount("video")) < int(track_index):
            if not timeline.AddTrack("video"):
                return False
        return True
    except Exception as e:
        print(f"! V{track_index}トラック準備でエラー: {e}")
        return False

def get_track_lock_state(timeline, track_type, track_index):
    try:
        return bool(timeline.GetIsTrackLocked(track_type, track_index))
    except Exception:
        return None

def set_track_lock_if_possible(timeline, track_type, track_index, locked):
    try:
        return bool(timeline.SetTrackLock(track_type, track_index, locked))
    except Exception:
        return False

def insert_title_on_video_track(timeline, frame, title_variants, target_track_index):
    """Text+/TitleをV2などの上位トラックへ入れるため、下位トラックを一時ロックして挿入する"""
    ensure_video_track(timeline, target_track_index)

    original_locks = {}
    for track_index in range(1, int(target_track_index)):
        original_locks[track_index] = get_track_lock_state(timeline, "video", track_index)
        set_track_lock_if_possible(timeline, "video", track_index, True)

    try:
        target_tc = frame_to_timecode(timeline, frame)
        timeline.SetCurrentTimecode(target_tc)
    except Exception as e:
        print(f"! Text+挿入位置の設定でエラー: {e}")

    timeline_item = None
    try:
        for insert_method, title_name in title_variants:
            method = getattr(timeline, insert_method, None)
            if not method:
                continue
            try:
                timeline_item = method(title_name)
            except Exception as e:
                print(f"! {insert_method}({title_name}) 失敗: {e}")
                timeline_item = None
            if timeline_item:
                break
    finally:
        for track_index, was_locked in original_locks.items():
            if was_locked is not None:
                set_track_lock_if_possible(timeline, "video", track_index, was_locked)

    if timeline_item and hasattr(timeline_item, "GetTrackTypeAndIndex"):
        try:
            track_type, actual_track_index = timeline_item.GetTrackTypeAndIndex()
            if track_type == "video" and int(actual_track_index) != int(target_track_index):
                print(
                    f"! Text+はV{target_track_index}ではなくV{actual_track_index}に入りました。"
                    " Resolve側でV1ロックが効かなかった可能性があります。"
                )
        except Exception:
            pass

    return timeline_item

def insert_editable_hook_card(timeline, start_frame, ai_plan, fps):
    """mp4ではなく、Resolve上で編集可能なText+/Fusionタイトルを本編先頭へ挿入する"""
    hook_text = ai_plan.get("hook_text")
    if not hook_text:
        return 0
    if not (
        hasattr(timeline, "InsertFusionTitleIntoTimeline")
        or hasattr(timeline, "InsertTitleIntoTimeline")
    ):
        print("! このResolve APIではタイトル挿入が使えません。フックカード追加をスキップします。")
        return 0

    timeline_item = insert_title_on_video_track(
        timeline,
        start_frame,
        (
            ("InsertFusionTitleIntoTimeline", "Text+"),
            ("InsertTitleIntoTimeline", "Text+"),
            ("InsertTitleIntoTimeline", "Text"),
        ),
        TEXT_TITLE_TRACK_INDEX,
    )

    if not timeline_item:
        print("! 編集可能なフックカードタイトルを挿入できませんでした。")
        return 0

    configure_hook_title_item(timeline_item, hook_text)
    fallback_frames = int(HOOK_CARD_SECONDS * fps)
    try:
        hook_frames = int(timeline_item.GetDuration(False))
    except Exception:
        hook_frames = fallback_frames
    hook_frames = max(1, hook_frames or fallback_frames)
    print(f"✓ 編集可能なフックカードをV{TEXT_TITLE_TRACK_INDEX}に追加しました: {hook_frames} frames")
    return 0

def insert_text_title_at_frame(timeline, frame, text, *, fps, seconds, size=0.055, color=None, clip_color="Blue"):
    """指定フレームへText+/Fusionタイトルを挿入して、成立する見た目の文言を設定する"""
    if not text:
        return 0
    if not (
        hasattr(timeline, "InsertFusionTitleIntoTimeline")
        or hasattr(timeline, "InsertTitleIntoTimeline")
    ):
        print("! このResolve APIではタイトル挿入が使えません。Text+追加をスキップします。")
        return 0

    timeline_item = insert_title_on_video_track(
        timeline,
        frame,
        (
            ("InsertFusionTitleIntoTimeline", "Text+"),
            ("InsertTitleIntoTimeline", "Text+"),
            ("InsertTitleIntoTimeline", "Text"),
        ),
        TEXT_TITLE_TRACK_INDEX,
    )

    if not timeline_item:
        print("! Text+タイトルを挿入できませんでした。")
        return 0

    configure_text_title_item(
        timeline_item,
        text,
        size=size,
        color=color,
        clip_color=clip_color,
    )

    expected_frames = max(1, int(seconds * fps))
    return expected_frames

def map_source_time_to_edited_frame(source_seconds, source_duration, edited_duration_frames):
    """元動画時間をauto-editor後タイムラインの近似フレームへ変換"""
    if source_duration <= 0 or edited_duration_frames <= 0:
        return 0
    ratio = min(max(source_seconds / source_duration, 0), 1)
    return int(ratio * edited_duration_frames)

def map_ai_time_to_timeline_frame(source_time, source_duration, edited_duration_frames, content_start_frame):
    """AIプラン上の元動画秒数をmainタイムライン上のフレームへ変換する"""
    mapped = map_source_time_to_edited_frame(source_time, source_duration, edited_duration_frames)
    return int(content_start_frame + mapped)

def build_chapter_title_text(chapter):
    title = wrap_hook_text_for_title(chapter.get("title", ""), width=20, max_lines=2)
    return f"CHAPTER\n{title}" if title else "CHAPTER"

def build_key_point_title_text(cue):
    label = wrap_hook_text_for_title(cue.get("label", ""), width=18, max_lines=2)
    note = wrap_hook_text_for_title(cue.get("note", ""), width=22, max_lines=2)
    lines = ["KEY POINT"]
    if label:
        lines.append(label)
    if note:
        lines.append(note)
    return "\n".join(lines)

def text_action_style(action):
    """Text+ actionの見た目設定を返す"""
    style = action.get("style")
    if style == "caption":
        return {"size": 0.045, "color": (1.0, 1.0, 1.0), "clip_color": "Orange"}
    if style == "chapter":
        return {"size": 0.052, "color": (0.68, 0.86, 1.0), "clip_color": "Blue"}
    if style == "key_point":
        return {"size": 0.052, "color": (1.0, 0.88, 0.42), "clip_color": "Yellow"}
    if style == "section_card":
        return {"size": 0.07, "color": (0.70, 1.0, 0.92), "clip_color": "Teal"}
    return {"size": 0.052, "color": (0.92, 0.96, 1.0), "clip_color": "Teal"}

def insert_ai_assist_text_objects(timeline, start_frame, ai_plan, fps, edited_duration_frames, hook_frames=0):
    """mainタイムライン上のV2に編集可能なText+補助要素を追加"""
    if not ai_plan.get("enabled"):
        reason = ai_plan.get("skip_reason") or "AI assist did not run"
        print(f"! AI補助はスキップされました。理由: {reason}")
        return

    source_duration = float(ai_plan.get("source_duration") or 0)
    content_start_frame = start_frame + hook_frames
    added = 0

    def mapped_frame(source_time):
        return map_ai_time_to_timeline_frame(source_time, source_duration, edited_duration_frames, content_start_frame)

    text_actions = [
        action for action in ai_plan.get("actions", [])
        if action.get("type") == "text_title"
    ]
    if not text_actions:
        for cue in ai_plan.get("key_point_cues", []):
            text_actions.append({
                "type": "text_title",
                "style": "key_point",
                "time": float(cue["time"]),
                "duration": KEY_POINT_TITLE_SECONDS,
                "text": build_key_point_title_text(cue),
            })

    for action in text_actions:
        frame = mapped_frame(float(action.get("time", 0)))
        style = text_action_style(action)
        inserted = insert_text_title_at_frame(
            timeline,
            frame,
            action.get("text", ""),
            fps=fps,
            seconds=float(action.get("duration") or 3),
            size=style["size"],
            color=style["color"],
            clip_color=style["clip_color"],
        )
        if inserted:
            added += 1

    qc_count = len(ai_plan.get("qc_notes", []))
    if qc_count:
        print(f"✓ QC確認ポイントは最終映像に出さず、_ai_assist のステータスファイルに残しました: {qc_count}件")

    print(f"✓ AI補助Text+オブジェクトを追加しました: {added}件")

def insert_chapter_markers(timeline, start_frame, ai_plan, edited_duration_frames, hook_frames=0):
    """チャプターは映像を押しのけないタイムラインマーカーとして追加する"""
    if not ai_plan.get("enabled"):
        return
    if not hasattr(timeline, "AddMarker"):
        print("! このResolve APIではタイムラインマーカー追加が使えません。")
        return

    source_duration = float(ai_plan.get("source_duration") or 0)
    content_start_frame = start_frame + hook_frames
    added = 0
    for chapter in ai_plan.get("chapters", []):
        title = str(chapter.get("title") or "Chapter").strip() or "Chapter"
        frame = map_ai_time_to_timeline_frame(
            float(chapter.get("time", 0)),
            source_duration,
            edited_duration_frames,
            content_start_frame,
        )
        try:
            if timeline.AddMarker(frame, "Blue", title, "AI chapter marker", 1, f"ai_chapter_{frame}"):
                added += 1
        except Exception as e:
            print(f"! チャプターマーカー追加エラー ({title}): {e}")

    print(f"✓ チャプターマーカーを追加しました: {added}件")

def media_pool_item_frames(media_pool_item, fps, fallback_seconds=2):
    """MediaPoolItemのフレーム数を取得する"""
    try:
        frames = int(media_pool_item.GetClipProperty("Frames"))
        if frames > 0:
            return frames
    except Exception:
        pass
    return max(1, int(fallback_seconds * fps))

def import_action_media_item(media_pool, video_paths, clip_name, cache):
    """アクション用メディアをMedia Poolへ取り込む"""
    if not clip_name:
        return None
    if clip_name in cache:
        return cache[clip_name]

    clip_path = find_clip_path(video_paths, clip_name)
    if not clip_path:
        print(f"! アクション用素材が見つかりません: {clip_name}")
        cache[clip_name] = None
        return None

    try:
        clips = media_pool.ImportMedia([clip_path])
    except Exception as e:
        print(f"! アクション用素材のインポートに失敗: {clip_name}: {e}")
        cache[clip_name] = None
        return None
    if not clips:
        print(f"! アクション用素材のインポートに失敗: {clip_name}")
        cache[clip_name] = None
        return None
    cache[clip_name] = clips[0]
    return clips[0]

def insert_ai_assist_media_actions(media_pool, timeline, start_frame, ai_plan, fps, edited_duration_frames, hook_frames, video_paths):
    """区切り動画やSEなどのメディア系アクションを追加する"""
    if not ai_plan.get("enabled"):
        return

    media_actions = [
        action for action in ai_plan.get("actions", [])
        if action.get("type") in ("media_clip", "sound_effect")
    ]
    if not media_actions:
        return

    source_duration = float(ai_plan.get("source_duration") or 0)
    content_start_frame = start_frame + hook_frames
    cache = {}
    inserted = 0

    for action in media_actions:
        media_item = import_action_media_item(media_pool, video_paths, action.get("clip_name", ""), cache)
        if not media_item:
            continue
        frame = int(content_start_frame + map_source_time_to_edited_frame(
            float(action.get("time", 0)),
            source_duration,
            edited_duration_frames,
        ))
        frames = media_pool_item_frames(media_item, fps)
        clip_info = {
            "mediaPoolItem": media_item,
            "startFrame": 0,
            "endFrame": frames,
            "recordFrame": frame,
        }
        if action.get("media_type"):
            clip_info["mediaType"] = int(action["media_type"])
        if action.get("track_index"):
            clip_info["trackIndex"] = int(action["track_index"])
        try:
            result = media_pool.AppendToTimeline([clip_info])
        except Exception as e:
            print(f"! メディアアクション追加エラー ({action.get('clip_name')}): {e}")
            continue
        if result:
            inserted += 1

    print(f"✓ AI補助メディアアクションを追加しました: {inserted}件")

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
        hook_frames = insert_editable_hook_card(main_timeline, start_frame, ai_plan, fps)
        content_start_frame = start_frame + hook_frames

        print(f"挿入するクリップ数: {len(clips_to_append)}")
        
        if clips_to_append:
            # 再生ヘッドを配置（SetCurrentFrameはAPIに無いためタイムコードで指定）
            try:
                target_tc = frame_to_timecode(main_timeline, content_start_frame)
                main_timeline.SetCurrentTimecode(target_tc)
                print(f"再生ヘッド位置を {content_start_frame} フレーム ({target_tc}) に設定しました")
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
                insert_chapter_markers(
                    main_timeline,
                    start_frame,
                    ai_plan,
                    edited_duration_frames,
                    hook_frames=hook_frames,
                )
                insert_ai_assist_text_objects(
                    main_timeline,
                    start_frame,
                    ai_plan,
                    fps,
                    edited_duration_frames,
                    hook_frames=hook_frames,
                )
                insert_ai_assist_media_actions(
                    media_pool,
                    main_timeline,
                    start_frame,
                    ai_plan,
                    fps,
                    edited_duration_frames,
                    hook_frames,
                    video_paths,
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
