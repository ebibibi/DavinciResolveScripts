# DaVinci Resolve 自動動画編集スクリプト

## 概要
このプロジェクトは、DaVinci Resolveでの動画編集ワークフローを自動化するためのPythonスクリプトです。
無音部分の自動カット、エンディング動画の自動追加、タイムライン統合などを自動実行します。

**2つのバージョンを提供:**
- **有償版用**: テンプレートプロジェクトからの自動プロジェクト作成機能付き
- **無料版用**: 既存プロジェクトでの動作（従来版）

## 主な機能

### 共通機能
1. OBS録画した最新の`.mkv`ファイルを自動検出
2. `auto-editor`を使用して無音部分をカットし、XMLファイルを生成
3. 生成されたXMLファイルをDaVinci Resolveにインポート
4. タイムラインにエンディング動画を自動追加
5. メインタイムラインに新しく作成したタイムラインの内容を挿入

### 有償版限定機能
- Davinci Resolve自体の起動
- テンプレート.drpからの自動プロジェクト作成
- リトライ機能付きクリップ追加（安定性向上）
- クロスプラットフォーム対応（Windows/Mac/Linux）
- AI編集補助（試験機能）
  - `whisper` CLIが利用できる場合、録画音声を文字起こしして「いま何の話をしているか」を示すText+/Fusionタイトルを画面右上へ常時表示
  - 話題区間、章マーカー、挿入成否を動画別の診断ファイルへ記録
  - 依存ツールが無い場合や処理に失敗した場合も、従来の自動編集処理は継続

## ファイル構成

```
DavinciResolveScripts/
├── README.md
├── 有償版用スクリプト/
│   ├── auto_video_editor.py （メインスクリプト）
│   ├── run_auto_video_editor.ps1 （実行用PowerShellスクリプト）
│   ├── create_desktop_shortcut.ps1 （ショートカット作成）
│   ├── config.example.json （ローカル設定サンプル）
│   └── テンプレート.drp （プロジェクトテンプレート）
└── 無料版用スクリプト/
    ├── auto_video_editor.py （メインスクリプト）
    └── テンプレート.drp （プロジェクトテンプレート）
```

## 前提条件

### 必須環境
- DaVinci Resolve 17以上（有償版の場合はDaVinci Resolve Studio推奨）
- Python 3.6以上
- auto-editor（`pip install auto-editor`）

### 任意環境（有償版のAI編集補助）
- whisper CLI（例: `pip install openai-whisper`）
- ffmpeg（Whisperの音声処理で必要になる場合があります）

AI編集補助を無効化したい場合は、環境変数 `DAVINCI_AI_ASSIST=0` を設定してください。
`run_auto_video_editor.ps1` から起動した場合、これらの任意ツールが不足しているときは確認メッセージが出ます。`Y` を入力すると、不足している `openai-whisper` / `ffmpeg` のインストールを実行します。NVIDIA GPUがあるのにPyTorchがCUDAを使えない場合は、CUDA版PyTorchもインストールします。

### フォルダ構造
以下のフォルダ構造が必要です：
- OBS録画データが保存されているフォルダ
- エンディング動画が保存されているフォルダ

## 使用方法

### 有償版の場合

#### 方法1: バッチファイル実行（推奨）
1. `有償版用スクリプト\run_auto_video_editor.ps1` を右クリックしてPowerShellで実行
2. 起動時に `git pull --ff-only --autostash` でリポジトリを最新化します
3. AI編集補助ツールが不足している場合は、`Y` でインストールするか、そのままEnterでスキップします
4. 自動的に環境チェックが実行され、スクリプトが起動します

#### 方法2: デスクトップショートカット作成
1. `有償版用スクリプト\create_desktop_shortcut.ps1` を右クリックしてPowerShellで実行
2. デスクトップにショートカットが作成されます
3. 作成されたショートカットをダブルクリックして実行

#### 方法3: コマンドライン実行
1. DaVinci Resolve Studioを起動
2. コマンドラインまたはターミナルで以下を実行：
   ```bash
   cd 有償版用スクリプト
   python auto_video_editor.py
   ```
   Pythonスクリプト直実行時も、最初にリポジトリ直下で `git pull --ff-only --autostash` を実行します。更新が入った場合は最新スクリプトで自動再起動します。

### 無料版の場合
1. DaVinci Resolveを起動し、プロジェクトとタイムラインを開く
2. DaVinci ResolveのスクリプトコンソールでPy3を選択
3. `auto_video_editor.py`の内容をコピー＆ペーストして実行

## 動作の仕組み

### 1. auto-editorの実行
- 指定ディレクトリ内の最新の`.mkv`ファイルを自動検出
- 無音部分をカットしてResolve用XMLファイルを生成

### 2. プロジェクト準備（有償版のみ）
- テンプレート.drpから新規プロジェクトを自動作成
- ユニークなプロジェクト名を自動生成

### 3. XMLファイルの処理
- 最新のXMLファイル（`.fcpxml`または`.xml`）を自動検出
- DaVinci Resolveにインポートして新しいタイムラインを作成

### 4. エンディング動画の追加
- 指定したエンディング動画をメディアプールにインポート
- タイムラインの最後に自動追加

### 5. タイムラインの統合
- オープニングクリップ（`01_EBI_CHAN_OP`）の位置を自動検出
- オープニング後に新しいコンテンツを挿入
- 編集ポジションをタイムライン先頭に移動

### 6. AI編集補助（有償版・試験機能）
- `auto-editor` 実行後、最新録画を `whisper` で文字起こし
- `_ai_assist/{動画名_サイズ_mtime}/ai_edit_plan.json`、`chapters_draft.txt`、`ai_assist_status.txt` を出力
- `whisper_device` が `auto` の場合、PyTorchでCUDAが使えれば `cuda`、Apple SiliconのMPSが使えれば `mps`、それ以外は `cpu` を自動選択
- GTX 1650などでCUDA実行中にNaNが出るケースを避けるため、既定では `whisper_fp16=false` としてFP32で実行
- `whisper_backend` を `ssh` にすると、SSH接続できるリモートGPUマシンへ音声だけ転送してWhisperを実行し、JSONだけ回収
- DaVinci Resolveのタイムラインに章マーカーと「いまの話題」Text+/Fusionタイトルを追加
  - Blue marker: 章
  - Yellow: キーポイントタイトル
  - Text+/Fusionタイトルは一時タイムラインで複合クリップ化し、`trackIndex: 2` を指定してV2へ非リップル配置
  - 追加後に実トラックがV2であることを検証し、V1等へ誤配置された場合は即削除して失敗として記録
  - フォントは `HGPSoeiKakugothicUB` を設定後にTextPlusから読み戻し、完全一致しなければ失敗として記録
  - 話題表示は画面右上へ小さく置き、次の話題へ切り替わるまで表示を継続
  - Resolve Scripting APIにはタイトル尺を直接変更するメソッドがないため、既定では4秒ごとの連続したText+として配置
  - QC確認ポイントは最終映像に出さず、動画別 `_ai_assist` フォルダの `ai_assist_status.txt` と `ai_edit_plan.json` に残します
- `hook_card=true` の場合は、AIが選んだ冒頭フック文も本編先頭のV2へ追加できます（既定OFF）
- `whisper` が見つからない場合や文字起こしに失敗した場合は、タイムライン上の追加は行わず、`ai_assist_status.txt` に理由を書き出します

Text+/Fusionタイトルは、そのまま最終映像に載っても成立するたたき台です。チャプターは映像を押しのけないタイムラインマーカーとして追加します。必要に応じてDaVinci Resolve上で削除・調整してください。

## カスタマイズ

有償版では、スクリプトを直接編集せずに `config.local.json` または環境変数でローカル環境を指定できます。
互換用に `config.json` も読み込みますが、新規作成時は `config.local.json` を推奨します。

### 方法1: config.local.json（推奨）

`有償版用スクリプト/config.example.json` を `config.local.json` にコピーし、自分の環境に合わせて編集してください。
`config.local.json` と `config.json` は `.gitignore` 済みなので、GitHubには公開されません。

```json
{
  "working_dirs": [
    "C:\\Users\\YOUR_NAME\\Videos\\OBS"
  ],
  "xml_dirs": [
    "C:\\Users\\YOUR_NAME\\Videos\\OBS"
  ],
  "video_path": [
    "C:\\Users\\YOUR_NAME\\Videos\\Assets"
  ],
  "ending_clip_name": "ending.mov",
  "op_clip_name": "01_EBI_CHAN_OP",
  "section_break_clip_names": [
    "02_EBI_CHAN_OP.mov",
    "03_EBI_CHAN_IN.mov"
  ],
  "whisper_backend": "local",
  "whisper_language": "Japanese",
  "whisper_device": "auto",
  "whisper_fp16": false,
  "whisper_word_timestamps": true,
  "ai_edit_actions": {
    "experimental_full_actions": false,
    "captions": false,
    "chapter_markers": true,
    "chapter_titles": false,
    "hook_card": false,
    "current_topic_overlay": true,
    "key_point_titles": false,
    "combine_legacy_titles": false,
    "topic_target_seconds": 45,
    "topic_min_seconds": 15,
    "topic_max_seconds": 75,
    "topic_overlay_refresh_seconds": 4,
    "max_topics": 30,
    "section_cards": false,
    "section_break_videos": false,
    "sound_effects": false,
    "max_captions": 12,
    "caption_min_gap_seconds": 8
  },
  "sound_effects": [
    {
      "name": "key_point",
      "clip_name": "key_point.wav",
      "trigger": "key_point",
      "track_index": 3,
      "cooldown_seconds": 20
    }
  ],
  "remote_whisper": {
    "host": "",
    "identity_file": "",
    "ssh_args": [],
    "scp_args": [],
    "remote_dir": "davinci-whisper-jobs",
    "command": "whisper",
    "device": "cuda",
    "fp16": false,
    "upload": "audio",
    "keep_remote_files": false
  },
  "priority_terms": []
}
```

`working_dirs`、`xml_dirs`、`video_path` は配列で複数指定できます。上から順に存在するフォルダや対象ファイルを探します。
`section_break_clip_names` は章境界などに挿入する区切り動画のファイル名です。素材フォルダ `video_path` から探索され、`ai_edit_actions.section_break_videos` が `true` の場合に使われます。
`ai_edit_actions` は実験的な自動編集機能のON/OFFです。既定では `current_topic_overlay` だけを有効にし、Whisper文字起こしを約45秒単位の話題へまとめてV2へ常時表示します。`topic_target_seconds` / `topic_min_seconds` / `topic_max_seconds` で話題区間、`topic_overlay_refresh_seconds` でText+を連続配置する間隔を調整できます。旧方式の `hook_card` と `key_point_titles` は既定OFFです。既存のローカル設定で `key_point_titles=true` が残っていても、現在トピック表示中は抑止されます。両方を重ねたい場合だけ `combine_legacy_titles=true` にします。`captions` は通常テロップです。`chapter_markers` はチャプターのタイムラインマーカー追加を制御します。`section_cards`、`section_break_videos`、`sound_effects` は `experimental_full_actions=true` を明示した場合だけ動く高度な実験機能です。
`sound_effects` はKeyPointなどに自動挿入するSE素材です。`clip_name` は `video_path` 配下から探索されます。

### 方法2: 環境変数

環境変数は `config.local.json` / `config.json` より優先されます。複数パスはWindowsではセミコロン区切りで指定します。

### 1. 作業ディレクトリ（OBS録画データの保存場所）
```powershell
$env:DAVINCI_WORKING_DIRS = "C:\Users\YOUR_NAME\Videos\OBS"
```

### 2. XMLフォルダの候補パス
```powershell
$env:DAVINCI_XML_DIRS = "C:\Users\YOUR_NAME\Videos\OBS"
```

### 3. 動画素材フォルダ
```powershell
$env:DAVINCI_VIDEO_PATH = "C:\Users\YOUR_NAME\Videos\Assets"
```

Windowsで複数フォルダを指定する場合はセミコロン区切りにします。

```powershell
$env:DAVINCI_VIDEO_PATH = "C:\Users\YOUR_NAME\Videos\Assets;D:\Shared\VideoAssets"
```

### 4. その他の設定
```powershell
$env:DAVINCI_ENDING_CLIP_NAME = "ending.mov"
$env:DAVINCI_OP_CLIP_NAME = "01_EBI_CHAN_OP"
$env:DAVINCI_WHISPER_BACKEND = "local"
$env:DAVINCI_WHISPER_LANGUAGE = "Japanese"
$env:DAVINCI_WHISPER_DEVICE = "auto"
$env:DAVINCI_WHISPER_FP16 = "false"
$env:DAVINCI_PRIORITY_TERMS = "Claude Code,MCP,Hooks"
$env:DAVINCI_AI_ASSIST = "1"
```

`priority_terms` / `DAVINCI_PRIORITY_TERMS` は必須ではありません。基本的には文字起こしから英数字の技術用語、強調フレーズ、章境界を自動抽出します。特定の用語を優先的に拾いたい場合だけ指定してください。

`whisper_device` / `DAVINCI_WHISPER_DEVICE` は通常 `auto` のままで構いません。GPUを強制したい場合は `cuda`、CPUに固定したい場合は `cpu` を指定できます。
`whisper_fp16` / `DAVINCI_WHISPER_FP16` は既定で `false` です。GPU使用時にNaNで失敗する場合は `false` のままにしてください。RTX系などで速度優先にしたい場合だけ `true` または `auto` を試してください。
CUDA版PyTorchのインストール元は `DAVINCI_TORCH_CUDA_INDEX_URL` で変更できます。既定値は `https://download.pytorch.org/whl/cu126` です。

### 5. リモートGPUでWhisperを実行する

SSH接続できるGPUマシンがある場合、`whisper_backend` を `ssh` にするとリモートで文字起こしできます。既定ではローカルで音声だけ抽出して転送するため、動画ファイル全体を送るより軽くなります。

```json
{
  "whisper_backend": "ssh",
  "remote_whisper": {
    "host": "spark",
    "user": "ebi",
    "identity_file": "C:\\Users\\YOUR_NAME\\.ssh\\id_ed25519",
    "ssh_args": ["-o", "IdentitiesOnly=yes"],
    "scp_args": ["-o", "IdentitiesOnly=yes"],
    "remote_dir": "davinci-whisper-jobs",
    "command": "$HOME/whisper-env/bin/whisper",
    "profile": "speed",
    "model": "turbo",
    "device": "cuda",
    "fp16": true,
    "beam_size": 1,
    "best_of": 1,
    "verbose": false,
    "extra_args": [],
    "upload": "audio",
    "keep_remote_files": false
  }
}
```

Windows側で `ssh ebi@spark` と `scp` が使えること、リモート側で指定した `command` が使えることが前提です。`profile: "speed"` では、リモートGPU向けに `--model turbo --device cuda --fp16 True --beam_size 1 --best_of 1 --verbose False` を明示します。精度優先に寄せる場合は `model` を `large-v3` にする、または `profile: "custom"` にして `beam_size` などを調整します。`user` を指定すると `user@host` 形式で接続します。`identity_file` を指定すると、`ssh` と `scp` の両方に `-i <鍵パス>` を付けて実行します。追加オプションが必要な場合は `ssh_args` / `scp_args` / `extra_args` に配列で指定できます。リモート側のホスト名・ユーザー名・鍵パスなどは `.ssh/config` や `config.local.json` / `config.json` にだけ置き、公開リポジトリには入れないでください。

## 注意事項

### 有償版
- DaVinci Resolve Studioが推奨（Python APIの完全サポート）
- テンプレート.drpファイルが同一フォルダに必要
- 自動的にプロジェクトが作成されるため、手動でのプロジェクト準備は不要

### 無料版
- 実行前にDaVinci Resolveでプロジェクトとタイムラインを開く必要あり
- スクリプトコンソールからの実行が必要

### 共通
- 指定したパスがすべて存在することを確認
- オープニングクリップは名前に「01_EBI_CHAN_OP」を含む必要あり
- デバッグ情報が詳細に出力されます

## トラブルシューティング

### よくあるエラーと対処法

#### 「指定ディレクトリに mkv ファイルが見つかりません」
- 作業ディレクトリに`.mkv`ファイルがあることを確認
- ファイルパスが正しいことを確認

#### 「テンプレートインポート失敗」（有償版）
- テンプレート.drpファイルがスクリプトと同じフォルダにあることを確認
- DaVinci Resolve Studioを使用していることを確認

#### 「タイムラインのインポートに失敗しました」
- XMLファイルの形式が正しいか確認
- auto-editorが正常に実行されているか確認

#### 「クリップの挿入に失敗しました」
- リトライ機能が自動実行されます（有償版）
- DaVinci Resolveの状態を確認し、必要に応じて再実行

## 技術仕様

### 有償版の追加機能
- **リトライ機能**: `'NoneType' object is not callable`エラーに対する自動リトライ
- **クロスプラットフォーム対応**: Windows、Mac、Linux自動対応
- **オブジェクト再取得**: 安定性向上のための自動オブジェクト更新
- **詳細ログ**: トラブルシューティング用の詳細情報出力
- **AI編集補助**: whisper文字起こしが可能な環境では、章マーカーと現在トピックを自動生成。Text+/FusionタイトルはV2へ明示配置し、フォントを検証

### パフォーマンス
- 大量クリップ（300+）の処理に対応
- メモリ効率的な処理方式
- エラー発生時の自動復旧機能

## ライセンス
このプロジェクトは個人利用・商用利用ともに自由にご利用いただけます。
