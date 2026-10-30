"""timeline.json -> out/youtube.json (chapters computed from the same output frames)."""
import json, os
os.chdir("/home/ebi/video-jobs/20261029-personal-data-leak")
TL = json.load(open("work/timeline.json"))
CH = [("hook_q", "漏れたら、まず何をする？（結論）"),
      ("check", "まず「何が漏れたか」を確かめる（メールのリンクは踏まない）"),
      ("pw", "漏れた情報ごとにやること：パスワード・カード"),
      ("addr", "住所・電話・メール／免許証の画像が漏れたら"),
      ("reuse", "一番効くのは「使い回しをやめる」"),
      ("pm", "パスワードマネージャーに覚えさせる"),
      ("passkey", "パスキーなら、そもそもパスワードが無い"),
      ("history", "この常識はいつから？（2013年〜2026年）"),
      ("inertia", "やらない理由がない／企業のIDも同じ"),
      ("priority", "大事なアカウントから順番に"),
      ("g07", "今日やる3つ"),
      ("trick", "裏技：全部本物の情報を入れなくていい"),
      ("sources", "出典と相談先"),
      ("summary", "まとめ")]
def start(bid):
    return min(p["o0"] for p in TL["pieces"] if p.get("block") == bid or p.get("id") == bid)
def ts(f):
    s = f // 30
    return f"{s // 60}:{s % 60:02d}"
rows = [(start(b), t) for b, t in CH]
rows[0] = (0, rows[0][1])
for (a, _), (b, t) in zip(rows, rows[1:]):
    assert (b - a) / 30 >= 10, t
chap = "\n".join(f"{ts(f)} {t}" for f, t in rows)
desc = f"""あちこちのサービスから個人情報が漏れたというニュースが続いています。「自分の情報も漏れたかも」と不安なときに、まず何をすればいいのかを、漏れた情報の種類ごとに整理しました。

結論：パスワードはすぐ変える（使い回している所も全部）。カードはカード会社に連絡して止める。住所・電話・メールが漏れたら届くものを疑う。免許証などの画像なら信用情報機関などに連絡。そして普段から、パスワードを使い回さない・パスワードマネージャーに覚えさせる・できればパスキーにしてパスワード自体をやめる。どれも10年以上前から言われている基本です。

▼ 今日やる3つ
1. メールや大事なアカウントにパスキーを登録する
2. パスワードマネージャーを入れて、使い回しているパスワードを全部違うものに変える
3. もう使わないサービスはアカウントを消す

▼ チャプター
{chap}

▼ 動画で使ったスライド（出典・相談先も掲載）
https://slides.ebistudy.net/decks/personal-data-leak-response

困ったときは IPA の「情報セキュリティ安心相談窓口」（電話・メール）にも相談できます。

#個人情報漏えい #パスワード #パスキー #パスワードマネージャー #セキュリティ"""
meta = {"title": "個人情報が漏れたら、まず何をする？パスワード・カード・免許証の対処とパスキーへの切り替え【今日やる3つ】",
        "description": desc,
        "tags": ["個人情報漏えい", "情報漏洩", "パスワード", "パスワード使い回し", "パスワードマネージャー", "パスキー",
                 "passkey", "多要素認証", "フィッシング", "クレジットカード", "信用情報機関", "IPA", "セキュリティ対策",
                 "Windows Hello", "胡田昌彦"]}
json.dump(meta, open("out/youtube.json", "w"), ensure_ascii=False, indent=1)
print(chap); print(len(meta["title"]))
