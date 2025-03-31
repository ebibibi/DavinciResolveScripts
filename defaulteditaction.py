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

print("メインタイムラインを取得します")
main_timeline = project.GetCurrentTimeline()
if not main_timeline:
    print("メインタイムラインが見つかりません。終了します。")
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

# オープニングクリップ(01_EBI_CHAN_OP.mov)の位置を探す
print("オープニングクリップを探します")
op_clip_found = False
start_frame = 0
# すでに上で検証済みのvideo_track変数を使用

# V1トラックの各クリップをチェック
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
            # クリップ名をチェック
            if "01_EBI_CHAN_OP" in clip_name:
                # オープニングクリップの終了フレームを取得
                start_frame = item.GetEnd()
                op_clip_found = True
                print(f"オープニングクリップが見つかりました。終了フレーム: {start_frame}")
                break
            clip_index += 1
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
    print(f"Debug: video_track_count={video_track_count}")
    for track_idx in range(1, video_track_count + 1):
        print(f"Debug: processing video track_idx={track_idx}")
        items_in_track = timeline.GetItemsInTrack("video", track_idx)
        print(f"Debug: got items_in_track={items_in_track}, type={type(items_in_track)}")
        if items_in_track:
            for item_id, clip_obj in items_in_track.items():
                print(f"Debug: video item_id={item_id}, clip_obj={clip_obj}, type={type(clip_obj)}")
                if clip_obj:
                    clip_start, clip_end = None, None
                    try:
                        clip_start = clip_obj.GetLeftOffset()
                        print(f"Debug: clip_start={clip_start}, type={type(clip_start)}")
                        clip_duration = clip_obj.GetDuration()
                        print(f"Debug: clip_duration={clip_duration}, type={type(clip_duration)}")
                        clip_end = clip_duration + clip_start
                        print(f"Debug: clip_end={clip_end}, type={type(clip_end)}")
                        print(f"Debug: clip_start={clip_start}, clip_end={clip_end}, clip_name={clip_obj.GetName()}")
                    except Exception as e:
                        print(f"Debug: exception calling GetMediaIn/Out on {clip_obj}: {e}")
                        continue
                    media_item = clip_obj.GetMediaPoolItem()
                    if media_item is not None and clip_start is not None and clip_end is not None:
                        clips_to_append.append({
                            'mediaPoolItem': media_item,
                            'startFrame': clip_start,
                            'endFrame': clip_end
                        })
    
    # オーディオトラックからクリップを取得
    audio_track_count = timeline.GetTrackCount("audio")
    print(f"Debug: audio_track_count={audio_track_count}")
    for track_idx in range(1, audio_track_count + 1):
        print(f"Debug: processing audio track_idx={track_idx}")
        items_in_track = timeline.GetItemsInTrack("audio", track_idx)
        print(f"Debug: got items_in_track={items_in_track}, type={type(items_in_track)}")
        if items_in_track:
            for item_id, clip_obj in items_in_track.items():
                print(f"Debug: audio item_id={item_id}, clip_obj={clip_obj}, type={type(clip_obj)}")
                if clip_obj:
                    clip_start, clip_end = None, None
                    try:
                        clip_start = clip_obj.GetLeftOffset()
                        print(f"Debug: clip_start={clip_start}, type={type(clip_start)}")
                        clip_duration = clip_obj.GetDuration()
                        print(f"Debug: clip_duration={clip_duration}, type={type(clip_duration)}")
                        clip_end = clip_duration + clip_start
                        print(f"Debug: clip_end={clip_end}, type={type(clip_end)}")
                        print(f"Debug: clip_start={clip_start}, clip_end={clip_end}, clip_name={clip_obj.GetName()}")
                    except Exception as e:
                        print(f"Debug: exception calling GetStart/End on {clip_obj}: {e}")
                        continue
                    media_item = clip_obj.GetMediaPoolItem()
                    if media_item is not None and clip_start is not None and clip_end is not None:
                        clips_to_append.append({
                            'mediaPoolItem': media_item,
                            'startFrame': clip_start,
                            'endFrame': clip_end
                        })
    
    print(f"挿入するクリップ数: {len(clips_to_append)}")
    
    # 追加のデバッグプリント
    print(f"Debug: timeline is {timeline}")
    print(f"Debug: media_pool is {media_pool}")
    print(f"Debug: main_timeline is {main_timeline}")
    print(f"Debug: clips_to_append is {clips_to_append}")
    
    # クリップが取得できた場合のみ挿入
    if clips_to_append:
        # 再生ヘッドを配置
        try:
            main_timeline.SetCurrentFrame(start_frame)
        except Exception as e:
            print(f"再生ヘッド配置でエラー: {str(e)}")
        
        # Debug Insert Step: Variables in the try block
        print("Debug Insert Step: Variables in the try block:")
        print(f"  timeline: {timeline}, type={type(timeline)}")
        print(f"  media_pool: {media_pool}, type={type(media_pool)}")
        print(f"  main_timeline: {main_timeline}, type={type(main_timeline)}")
        print(f"  start_frame: {start_frame}, type={type(start_frame)}")
        print(f"  clips_to_append: {clips_to_append}, type={type(clips_to_append)}")
        
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
