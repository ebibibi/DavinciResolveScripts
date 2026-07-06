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
  - `whisper` CLIが利用できる場合、録画音声を文字起こしして章マーカー・キーポイントマーカー・QCマーカーの草案を追加
  - `ffmpeg` と `Pillow` が利用できる場合、冒頭フックカード動画を自動生成して本編先頭に追加
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
- Pillow（例: `pip install Pillow`）
- ffmpeg（フックカード動画生成に使用）

AI編集補助を無効化したい場合は、環境変数 `DAVINCI_AI_ASSIST=0` を設定してください。
`run_auto_video_editor.ps1` から起動した場合、これらの任意ツールが不足しているときは確認メッセージが出ます。`Y` を入力すると、不足している `openai-whisper` / `Pillow` / `ffmpeg` のインストールを実行します。NVIDIA GPUがあるのにPyTorchがCUDAを使えない場合は、CUDA版PyTorchもインストールします。

### フォルダ構造
以下のフォルダ構造が必要です：
- OBS録画データが保存されているフォルダ
- エンディング動画が保存されているフォルダ

## 使用方法

### 有償版の場合

#### 方法1: バッチファイル実行（推奨）
1. `有償版用スクリプト\run_auto_video_editor.ps1` を右クリックしてPowerShellで実行
2. AI編集補助ツールが不足している場合は、`Y` でインストールするか、そのままEnterでスキップします
3. 自動的に環境チェックが実行され、スクリプトが起動します

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
- `_ai_assist/ai_edit_plan.json`、`_ai_assist/chapters_draft.txt`、`_ai_assist/ai_assist_status.txt` を出力
- `whisper_device` が `auto` の場合、PyTorchでCUDAが使えれば `cuda`、Apple SiliconのMPSが使えれば `mps`、それ以外は `cpu` を自動選択
- GTX 1650などでCUDA実行中にNaNが出るケースを避けるため、既定では `whisper_fp16=false` としてFP32で実行
- DaVinci Resolveのタイムラインに以下のドラフトマーカーを追加
  - Blue: 章マーカー
  - Yellow: キーポイントマーカー
  - Red: QC確認ポイント
  - Green: 冒頭フック
- `ffmpeg` と `Pillow` が利用できる場合、AIが選んだ冒頭フック文を4秒のカード動画として本編先頭に追加
- `whisper` が見つからない場合や文字起こしに失敗した場合は、タイムラインに `AI Assist skipped` マーカーを追加し、`ai_assist_status.txt` に理由を書き出します

マーカーやフックカードは編集のたたき台です。不要であればDaVinci Resolve上で削除・調整してください。

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
  "whisper_language": "Japanese",
  "whisper_device": "auto",
  "whisper_fp16": false,
  "priority_terms": []
}
```

`working_dirs`、`xml_dirs`、`video_path` は配列で複数指定できます。上から順に存在するフォルダや対象ファイルを探します。

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
- **AI編集補助**: whisper文字起こしが可能な環境では、章・キーポイント・QCマーカーと冒頭フックカードを自動生成

### パフォーマンス
- 大量クリップ（300+）の処理に対応
- メモリ効率的な処理方式
- エラー発生時の自動復旧機能

## ライセンス
このプロジェクトは個人利用・商用利用ともに自由にご利用いただけます。
