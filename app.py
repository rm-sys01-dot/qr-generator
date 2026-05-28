import streamlit as st
import pyqrcode
import zipfile
import io
from datetime import datetime
from zoneinfo import ZoneInfo

# ページのタイトルと説明
st.title("QRコード一括生成ツール")
st.write("対象のURLを入力すると、EPS形式のQRコードが入ったZIPファイルをダウンロードできます。")

# ユーザーからの入力を受け付けるテキストエリア
url_input = st.text_area(
    "URLを1行に1つずつ貼り付けてください:",
    height=200,
    placeholder="https://chocozap.jp/redirect/example1\nhttps://chocozap.jp/redirect/example2"
)

# 生成ボタン
if st.button("QRコードを生成してZIP化する"):
    if not url_input.strip():
        st.warning("URLが入力されていません。")
    else:
        # 入力されたテキストを改行で分割し、空行を除去
        urls = [u.strip() for u in url_input.strip().split('\n') if u.strip()]
        
        uncorrect_urls = []
        
        # メモリ上でZIPファイルを作成するためのバッファを用意（サーバーにファイルを保存しないため）
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for url in urls:
                # 対象外のURLを弾く
                if 'https://chocozap.jp/redirect' not in url:
                    uncorrect_urls.append(url)
                    continue
                
                # ファイル名の生成（URLから特定の文字列を削除）
                raw_file_name = url.replace('https://chocozap.jp/redirect', '')
                # ファイル名として不正な文字（スラッシュなど）をアンダースコアに変換して安全にする
                file_name = raw_file_name.strip('/').replace('/', '_')
                if not file_name:
                    file_name = "default" # 万が一ファイル名が空になった場合
                
                # QRコードの作成 (エラーレベル'H')
                qr = pyqrcode.create(url, error='H')
                
                # EPSデータをメモリ上のテキストバッファに書き出す
                eps_buffer = io.StringIO()
                qr.eps(eps_buffer, scale=13)
                
                # ZIPファイルの中にEPSファイルとして追加
                zip_file.writestr(f"{file_name}.eps", eps_buffer.getvalue())
        
        # 処理完了後の画面表示
        st.success("QRコードの生成が完了しました！下のボタンからダウンロードしてください。")
        
        # 想定外のURLがあった場合のアラート表示
        if uncorrect_urls:
            st.warning(
                "⚠️ 以下のURLは指定のフォーマット（https://chocozap.jp/redirect）を含まないためスキップされました：\n\n" + 
                "\n".join(uncorrect_urls)
            )

        # ZIPファイル名の設定 (現在日時)
        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        now_str = now.strftime("%Y%m%d%H%M%S")
        zip_filename = f"qrcode_{now_str}.zip"
        
        # ダウンロードボタンの表示
        st.download_button(
            label="📦 ZIPファイルをダウンロード",
            data=zip_buffer.getvalue(),
            file_name=zip_filename,
            mime="application/zip"
        )
