# DaVinci Resolve 自動編集実験メモ

## 目的

DaVinci Resolve Studio の外部スクリプト API と Whisper 文字起こし結果を組み合わせて、手動編集前のタイムラインに「そのまま残しても成立する」編集候補を自動生成する。

## APIで確認できたこと

- Resolve は Python / Lua スクリプトで外部制御できる。外部Pythonから使う場合は、Resolve付属の `DaVinciResolveScript` / `fusionscript.dll` などを参照する。
- `resolve = DaVinciResolveScript.scriptapp("Resolve")` で接続し、`resolve.Fusion()` からFusion側の機能にも触れる。
- Media Pool / Timeline APIで、メディア取り込み、タイムライン作成、クリップ追加、XML/FCPXML/AAF/OTIO/DRTインポートができる。
- Timeline APIには `InsertTitleIntoTimeline()` / `InsertFusionTitleIntoTimeline()` / `InsertFusionCompositionIntoTimeline()` があり、Text+やFusionタイトルをタイムラインに追加できる。
- TimelineItemにはFusion comp取得・追加・インポートのAPIがあり、TextPlusノードの `StyledText` などを設定できる。
- `InsertTitleIntoTimeline()` / `InsertFusionTitleIntoTimeline()` はトラック番号を直接指定できないため、V2に入れたい場合はV2を作成し、挿入中だけV1をロックして逃がす方式で検証する。
- チャプターは映像を押しのけるText+ではなく、`Timeline.AddMarker()` でタイムラインマーカーとして追加するほうが編集しやすい。
- `AppendToTimeline([{mediaPoolItem, startFrame, endFrame, mediaType, trackIndex, recordFrame}])` により、素材クリップやSEを指定位置に追加できる余地がある。
- Resolve側にも `CreateSubtitlesFromAudio()` があるが、現状のパイプラインではWhisper結果を使ったText+/字幕生成のほうが制御しやすい。

## すぐ試せる自動編集

### 1. 自動テロップ

Whisperの `segments` から短いフレーズを作り、該当時刻にText+/Fusionタイトルとして挿入する。

実験案:

- セグメント単位の下部テロップ
- キーワードだけを強調するKeyPointテロップ
- 重要語だけを左上・右上に短く出す補助ラベル

改善余地:

- `word_timestamps` を使うと、字幕の表示開始/終了を発話リズムに合わせやすい。
- 日本語は空白がないため、文字数・句読点・無音ギャップで分割する。

### 2. SE自動挿入

Whisperテキストから重要箇所を判定し、SE素材を音声トラックへ追加する。

トリガー候補:

- 「重要」「ポイント」「結論」「注意」「実は」「ここで」などのキュー語
- 章境界
- 長い沈黙明け
- 話題転換
- AIが高スコアを付けたKeyPoint

実装案:

- `config.local.json` に `se_library` を追加する。
- `se_library` には `type`, `path`, `gain`, `cooldown_seconds` を持たせる。
- Media PoolへSEを取り込み、`AppendToTimeline` の `mediaType=2` / `trackIndex` / `recordFrame` を使って追加を試す。
- まずは1種類の短いSEだけで実験し、過剰挿入を防ぐためにクールダウンを入れる。

### 3. セクション切れ目のアイキャッチ

章境界に、mp4焼き込みではなく編集可能なテンプレートを挿入する。

候補:

- Fusion Titleテンプレート
- `.setting` のFusion comp
- `.drt` の小さなテンプレートタイムライン
- Text+ / Background / Shape を組み合わせたセクションカード

方針:

- まずは区切り動画の挿入タイミングだけをplanに出し、実機でズレを確認する。
- 見た目が固まったらテンプレート化して、章名だけ差し替える。
- 動画ファイルではなくResolve上で編集できるオブジェクトとして残す。

## 次に作るとよい仕組み

### Edit Action Plan

Whisper解析結果を直接タイムライン操作に変換せず、いったん `_ai_assist/ai_edit_plan.json` に編集アクションとして保存する。

例:

```json
{
  "chapters": [
    {
      "time": 0.0,
      "title": "導入"
    }
  ],
  "actions": [
    {
      "type": "text_title",
      "time": 12.4,
      "duration": 3.0,
      "style": "key_point",
      "text": "KEY POINT\n設定ファイルを分ける"
    },
    {
      "type": "sound_effect",
      "time": 12.4,
      "asset": "pop",
      "track": 3
    },
    {
      "type": "section_card",
      "time": 180.0,
      "duration": 4.0,
      "title": "環境構築"
    }
  ]
}
```

利点:

- AI判断とResolve操作を分離できる。
- 実験機能を `text_title`, `sound_effect`, `section_card` などで個別にON/OFFできる。
- 生成結果を人間がレビューしやすい。
- 同じplanから再実行できる。
- チャプターは `actions` ではなく `chapters` からマーカー化する。

実装メモ:

- 2026-07-07時点で、`ai_edit_plan.json` に `actions` 配列を出力する最小実装を追加済み。
- 2026-07-08時点で、Text+がV1に入り映像を押しのける問題が出たため、Text+はV2挿入を目標にし、章はマーカーへ戻した。
- `text_title` は通常テロップ、KeyPoint、SECTIONカードに利用する。章タイトルには使わない。
- `media_clip` は `section_break_clip_names` で指定した区切り動画に利用する。
- `sound_effect` は `sound_effects` で指定したSE素材に利用する。
- `whisper_word_timestamps` は既定 `true` とし、Whisper JSONの `segments[].words` を読み込めるようにした。現時点では通常字幕の分割改善に使う余地を残している。

### 実験フラグ

`config.local.json` に以下のような設定を追加する。

```json
{
  "ai_edit_actions": {
    "experimental_full_actions": false,
    "captions": false,
    "chapter_titles": false,
    "key_point_titles": true,
    "sound_effects": false,
    "section_cards": false,
    "section_break_videos": false,
    "max_captions": 12,
    "caption_min_gap_seconds": 8
  }
}
```

最初はKeyPoint Text+だけONにし、SE、アイキャッチ、通常テロップは実機検証しながら段階的に有効化する。SE、アイキャッチ、区切り動画は `experimental_full_actions=true` を明示したときだけ動かす。

## 優先順位

1. **Text+自動テロップの安定化**
   - まずKeyPoint Text+をV2に安定挿入する。通常字幕・キーワード補助・章カードは後段で拡張する。
2. **SE挿入の最小実験**
   - 1種類のSEをKeyPointにだけ挿入し、音声トラック追加・位置合わせ・過剰挿入を検証する。
3. **章カード/アイキャッチのテンプレート化**
   - Text+だけの章カードから始め、Fusion template / DRT化する。
4. **word_timestamps対応**
   - Whisper出力を単語タイミング付きにし、字幕のズレを減らす。
5. **画面効果**
   - 長尺の単調区間にゆるいZoom/Pan、重要箇所に注目枠などを追加する。

## 注意点

- Resolve APIは強力だが、UIでできる全操作がAPIに公開されているとは限らない。
- Text+の挿入位置・トラック指定・尺変更は、実機で挙動確認が必要。
- SEやアイキャッチは入れすぎると動画品質を下げるため、最初は上限数とクールダウンを必ず入れる。
- QC系の情報は最終映像に出さず、ファイルやログに残すほうが安全。

## 参照

- Blackmagic Design Fusion 8 Scripting Guide: https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf
- DaVinci Resolve 20 New Features Guide: https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_20_New_Features_Guide.pdf
- DaVinci Resolve 21 New Features Guide: https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_21_New_Features_Guide.pdf
- Resolve Scripting API README mirror: https://gist.github.com/X-Raym/2f2bf453fc481b9cca624d7ca0e19de8
- Formatted Resolve Scripting API mirror: https://extremraym.com/cloud/resolve-scripting-doc/
