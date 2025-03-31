import glob
import os
import sys

print("スクリプト開始")

# XMLファイルが格納されたフォルダを指定
xml_folder_paths = [
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!OBS録画',
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!OBS録画'
]

print(f"XMLフォルダのパス候補: {xml_folder_paths}")

# 存在するフォルダを選択
xml_folder_path = next((path for path in xml_folder_paths if os.path.exists(path)), None)

if xml_folder_path is None:
    print("いずれのXMLフォルダも存在しません。終了します。")
    sys.exit(1)

print(f"選択されたXMLフォルダ: {xml_folder_path}")

# エンディング動画へのパスを指定
ending_video_paths = [
    r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov',
    r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!動画素材\03_EBI_CHAN_IN.mov'
]
print(f"エンディング動画パス候補: {ending_video_paths}")

ending_video_path = next((path for path in ending_video_paths if os.path.exists(path)), None)

if ending_video_path is None:
    print("いずれのエンディング動画も存在しません。終了します。")
    sys.exit(1)

print(f"選択されたエンディング動画: {ending_video_path}")

# 現在開いているプロジェクトを取得
print("Resolveオブジェクトを取得します")
resolve = app.GetResolve()
print("ProjectManagerオブジェクトを取得します")
project_manager = resolve.GetProjectManager()
print("現在のプロジェクトを取得します")
project = project_manager.GetCurrentProject()
if project is None:
    print("プロジェクトが開かれていません。終了します。")
    sys.exit(1)

print("MediaPoolオブジェクトを取得します")
media_pool = project.GetMediaPool()

# フォルダ内の最新のXMLファイルを検索
print("XMLファイルを検索します")
fcpxml_files = glob.glob(os.path.join(xml_folder_path, '*.fcpxml'))
xml_files = glob.glob(os.path.join(xml_folder_path, '*.xml'))
all_xml_files = fcpxml_files + xml_files

print(f"見つかったXMLファイル: {len(all_xml_files)}個")
if not all_xml_files:
    print("指定したフォルダ内にXMLファイル(.fcpxml/.xml)がありません。")
    sys.exit(1)

# 最新のXMLファイルを選択
latest_xml = max(all_xml_files, key=os.path.getmtime)
print(f"最新のXMLファイルを選択しました: {latest_xml}")

# XMLをインポートしてタイムラインを作成
print("XMLからタイムラインをインポートします")
timeline = media_pool.ImportTimelineFromFile(latest_xml)
if timeline is None:
    print("タイムラインのインポートに失敗しました。XMLを確認してください。")
    sys.exit(1)

print(f"タイムラインをインポートしました: {timeline.GetName()}")

# エンディング動画をメディアプールに追加
print("エンディング動画をインポートします")
ending_clip_list = media_pool.ImportMedia([ending_video_path])
if not ending_clip_list:
    print("エンディング動画のインポートに失敗しました。パスを確認してください。")
    print(f"試行したパス: {ending_video_path}")
    sys.exit(1)

ending_clip = ending_clip_list[0]
print(f"エンディングクリップをインポートしました: {ending_clip.GetName()}")

# エンディング動画のフレーム数を取得
try:
    ending_clip_frames = int(ending_clip.GetClipProperty('Frames'))
    print(f"エンディングクリップのフレーム数: {ending_clip_frames}")
except Exception as e:
    print(f"エンディングクリップのフレーム数取得に失敗: {str(e)}")
    sys.exit(1)

# タイムラインの最後にエンディング動画を追加
print("タイムラインにエンディング動画を追加します")
append_result = media_pool.AppendToTimeline([{
    'mediaPoolItem': ending_clip,
    'startFrame': 0,
    'endFrame': ending_clip_frames
}])

if not append_result:
    print("エンディング動画の追加に失敗しました。")
    sys.exit(1)

print("最新XMLのタイムライン作成とエンディング追加が完了しました。")


# 新しく作成したタイムラインをアクティブにする
print("新しいタイムラインをアクティブにします")
try:
    set_result = project.SetCurrentTimeline(timeline)
    print(f"タイムラインのアクティブ化結果: {set_result}")
except Exception as e:
    print(f"タイムラインのアクティブ化でエラー: {str(e)}")
    sys.exit(1)

# メインタイムラインをアクティブにする
print("メインタイムラインをアクティブにします")
try:
    set_main_result = project.SetCurrentTimeline(main_timeline)
    print(f"メインタイムラインのアクティブ化結果: {set_main_result}")
    # 追加の確認
    current_tl = project.GetCurrentTimeline()
    print(f"現在のアクティブタイムライン: {current_tl.GetName() if current_tl else 'None'}")
except Exception as e:
    print(f"メインタイムラインのアクティブ化でエラー: {str(e)}")
    sys.exit(1)

# メインタイムラインのトラック情報を取得
try:
    main_track_count = main_timeline.GetTrackCount("video")
    print(f"メインタイムラインのビデオトラック数: {main_track_count}")
    
    if video_track > main_track_count:
        print(f"指定されたV{video_track}トラックがメインタイムラインに存在しません。最後のトラック(V{main_track_count})を使用します。")
        video_track = main_track_count
except Exception as e:
    print(f"メインタイムラインのトラック情報取得でエラー: {str(e)}")
    # エラーが発生してもデフォルトのトラック番号を使用する
    print(f"デフォルトのトラック番号({video_track})を使用します。")

# オープニングクリップ(01_EBI_CHAN_OP.mov)の位置を探す
print("オープニングクリップを探します")
op_clip_found = False
start_frame = 0
# すでに上で検証済みのvideo_track変数を使用

# V4トラックの各クリップをチェック
try:
    items_count = main_timeline.GetItemsInTrack("video", video_track)
    print(f"V{video_track}トラックのアイテム数: {items_count}")
    
    if items_count == 0:
        print(f"V{video_track}トラックにアイテムがありません。")
        op_clip_found = False
    else:
        for i in range(items_count):
            try:
                item = main_timeline.GetItemInTrack("video", video_track, i+1)
                clip_name = item.GetName()
                print(f"V{video_track}トラックのクリップ {i+1}: {clip_name}")
                # クリップ名をチェック
                if "01_EBI_CHAN_OP" in clip_name:
                    # オープニングクリップの終了フレームを取得
                    start_frame = item.GetEnd()
                    op_clip_found = True
                    print(f"オープニングクリップが見つかりました。終了フレーム: {start_frame}")
                    break
            except Exception as e:
                print(f"クリップ {i+1} の処理中にエラー: {str(e)}")
except Exception as e:
    print(f"V{video_track}トラックのアイテム数取得でエラー: {str(e)}")
    op_clip_found = False

if not op_clip_found:
    print(f"V{video_track}トラックにオープニングクリップが見つかりません。タイムラインの先頭に貼り付けます。")
    # タイムラインのスタートフレームを取得
    try:
        start_timecode = main_timeline.GetStartTimecode()
        print(f"タイムラインの開始タイムコード: {start_timecode}")
        # タイムコードをフレーム番号に変換（必要に応じて）
        # ここでは簡易的に0を設定
        start_frame = 0
    except Exception as e:
        print(f"タイムラインの開始フレーム取得でエラー: {str(e)}")
        start_frame = 0

print("新しいタイムラインをメインタイムラインに挿入します")
try:
    # timeline自体をmediaPoolItemとして使用することはできない
    # 代わりに、timeline内の全クリップを取得して追加する
    clips_to_append = []
    
    # ビデオトラックからクリップを取得
    video_track_count = timeline.GetTrackCount("video")
    for track_idx in range(1, video_track_count + 1):
        items_in_track = timeline.GetItemsInTrack("video", track_idx)
        if items_in_track:
            for item_id, clip_obj in items_in_track.items():
                if clip_obj:
                    clip_start = clip_obj.GetStart()
                    clip_end = clip_obj.GetEnd()
                    media_item = clip_obj.GetMediaPoolItem()
                    if media_item:
                        clips_to_append.append({
                            'mediaPoolItem': media_item,
                            'startFrame': clip_start,
                            'endFrame': clip_end
                        })
    
    # オーディオトラックからクリップを取得
    audio_track_count = timeline.GetTrackCount("audio")
    for track_idx in range(1, audio_track_count + 1):
        items_in_track = timeline.GetItemsInTrack("audio", track_idx)
        if items_in_track:
            for item_id, clip_obj in items_in_track.items():
                if clip_obj:
                    clip_start = clip_obj.GetStart()
                    clip_end = clip_obj.GetEnd()
                    media_item = clip_obj.GetMediaPoolItem()
                    if media_item:
                        clips_to_append.append({
                            'mediaPoolItem': media_item,
                            'startFrame': clip_start,
                            'endFrame': clip_end
                        })
    
    print(f"挿入するクリップ数: {len(clips_to_append)}")
    
    # クリップが取得できた場合のみ挿入
    if clips_to_append:
        # 再生ヘッドを配置
        try:
            main_timeline.SetCurrentTimecode(start_frame)
        except:
            try:
                main_timeline.SetCurrentFrameNumber(start_frame)
            except Exception as e:
                print(f"再生ヘッド配置でエラー: {str(e)}")
        
        # クリップをメインタイムラインに追加
        insert_result = media_pool.AppendToTimeline(clips_to_append)
        if not insert_result:
            print("クリップの挿入に失敗しました。")
            sys.exit(1)
        print(f"メインタイムラインの位置 {start_frame} にクリップを挿入しました。")
    else:
        print("挿入するクリップが見つかりませんでした。")
        sys.exit(1)
except Exception as e:
    print(f"タイムラインの挿入でエラー: {str(e)}")
    sys.exit(1)

print("全ての処理が完了しました。")

# 編集ポジションをタイムライン先頭に移動
try:
    main_timeline.SetCurrentTimecode("00:00:00:00")
    print("編集ポジションをタイムライン先頭に移動しました。")
except Exception as e:
    print(f"編集ポジションの移動でエラー: {str(e)}")
