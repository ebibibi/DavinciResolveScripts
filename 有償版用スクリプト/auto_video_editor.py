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
from datetime import datetime
from pathlib import Path

print("DaVinci Resolve自動動画編集スクリプト（有償版）開始")

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
    
    # 最新の .mkv ファイルを取得
    mkv_files = glob.glob("*.mkv")
    if not mkv_files:
        print("✗ mkvファイルが見つかりません")
        return False
    
    latest_file = max(mkv_files, key=os.path.getmtime)
    print(f"✓ 処理対象ファイル: {latest_file}")
    
    command = [
        "auto-editor",
        f'"{str(Path(working_dir) / latest_file)}"',
        "--margin", "0.2sec",
        "--edit", "audio:threshold=1%",
        "--export", "resolve"
    ]
    
    command_str = ' '.join(command)
    print(f"実行コマンド: {command_str}")
    
    try:
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True, check=True)
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
    working_dir = r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!OBS録画'
    if not run_auto_editor(working_dir):
        print("✗ auto-editor実行失敗")
        sys.exit(1)
    
    # XMLファイルの検索とインポート
    xml_folder_paths = [
        r'C:\OneDrive\OneDrive - hccjp\Youtube動画作成場所\!OBS録画',
        r'C:\Users\masah\OneDrive - hccjp (1)\Youtube動画作成場所\!OBS録画'
    ]
    
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
                if "01_EBI_CHAN_OP" in clip_name:
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
        
        print(f"挿入するクリップ数: {len(clips_to_append)}")
        
        if clips_to_append:
            # 再生ヘッドを配置（無料版の方法に合わせる）
            try:
                main_timeline.SetCurrentFrame(start_frame)
                print(f"再生ヘッド位置を {start_frame} に設定しました")
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