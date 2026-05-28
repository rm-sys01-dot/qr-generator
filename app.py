import streamlit as st
import pyqrcode
import zipfile
import io
import gspread
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# Googleスプレッドシート（データベース）連携設定
# ==========================================
def get_gspread_client():
    """StreamlitのSecretsからサービスアカウント情報を読み込んで接続"""
    try:
        credentials = dict(st.secrets["gcp_service_account"])
        # 改行コードのエラー対策
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(credentials)
        return gc
    except Exception as e:
        st.error(f"Googleサービスへの接続設定に失敗しています。Secretsを確認してください。: {e}")
        return None

def write_usage_log(qr_count):
    """利用実績をスプレッドシートに自動追記する関数"""
    gc = get_gspread_client()
    if gc:
        try:
            # スプレッドシート名と対象のシート名（タイムチャージ）
            sh = gc.open("qr_generator_log")
            worksheet = sh.worksheet("タイムチャージ")
            
            # 日本時間の現在日時を取得
            now_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
            
            # [日時, 生成されたQRコード数] を追記
            worksheet.append_row([now_str, qr_count])
        except Exception as e:
            # ユーザーの邪魔をしないよう、エラーは画面上部に小さく出すのみ
            st.sidebar.error(f"利用ログの記録に失敗しました: {e}")

# ==========================================
# 画面構成（タブ分け）
# ==========================================
st.title("QRコード一括生成ツール")

tab1, tab2 = st.tabs(["🔗 QRコード生成", "📊 利用実績の確認（管理者用）"])

# ------------------------------------------
# タブ1：一般ユーザー用（QRコード生成）
# ------------------------------------------
with tab1:
    st.write("対象のURLを入力すると、EPS形式のQRコードが入ったZIPファイルをダウンロードできます。")

    url_input = st.text_area(
        "URLを1行に1つずつ貼り付けてください:",
        height=200,
        placeholder="https://chocozap.jp/redirect/example1\nhttps://chocozap.jp/redirect/example2",
        key="main_url_input"
    )

    if st.button("QRコードを生成してZIP化する"):
        if not url_input.strip():
            st.warning("URLが入力されていません。")
        else:
            urls = [u.strip() for u in url_input.strip().split('\n') if u.strip()]
            uncorrect_urls = []
            generated_count = 0  
            
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for url in urls:
                    if 'https://chocozap.jp/redirect' not in url:
                        uncorrect_urls.append(url)
                        continue
                    
                    raw_file_name = url.replace('https://chocozap.jp/redirect', '')
                    file_name = raw_file_name.strip('/').replace('/', '_')
                    if not file_name:
                        file_name = "default"
                    
                    qr = pyqrcode.create(url, error='H')
                    eps_buffer = io.StringIO()
                    qr.eps(eps_buffer, scale=13)
                    
                    zip_file.writestr(f"{file_name}.eps", eps_buffer.getvalue())
                    generated_count += 1
            
            if generated_count > 0:
                st.success("QRコードの生成が完了しました！下のボタンからダウンロードしてください。")
                
                # スプレッドシートに実績を自動記録
                write_usage_log(generated_count)
                
                now = datetime.now(ZoneInfo("Asia/Tokyo"))
                now_str = now.strftime("%Y%m%d%H%M%S")
                zip_filename = f"qrcode_{now_str}.zip"
                
                st.download_button(
                    label="📦 ZIPファイルをダウンロード",
                    data=zip_buffer.getvalue(),
                    file_name=zip_filename,
                    mime="application/zip"
                )
            else:
                st.error("生成可能なURLがありませんでした。")
            
            if uncorrect_urls:
                st.warning(
                    "⚠️ 以下のURLは指定のフォーマットを含まないためスキップされました：\n\n" + 
                    "\n".join(uncorrect_urls)
                )

# ------------------------------------------
# タブ2：管理者用（利用実績の集計・確認）
# ------------------------------------------
with tab2:
    st.header("📊 利用実績の集計")
    st.write("指定した期間内に、ツールが何回使われ、何個のQRコードが作られたかを集計します。")
    
    # 期間選択（初期値は今日）
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("開始日", today)
    with col_end:
        end_date = st.date_input("終了日", today)
    
    if st.button("📊 まとめて集計を実行"):
        if start_date > end_date:
            st.error("開始日は終了日より前の日付を指定してください。")
        else:
            with st.spinner("スプレッドシートからデータを集計中..."):
                gc = get_gspread_client()
                if gc:
                    try:
                        sh = gc.open("qr_generator_log")
                        worksheet = sh.worksheet("タイムチャージ")
                        
                        # 蓄積された全ログを取得
                        all_records = worksheet.get_all_records()
                        
                        total_usage_runs = 0  # 総利用回数
                        total_qrcodes_made = 0 # 総QRコード生成数
                        
                        # 1行ずつ日付をチェックして期間内ならカウント
                        for record in all_records:
                            if not record.get('timestamp'):
                                continue
                            
                            log_date_str = record['timestamp'].split(' ')[0]
                            log_date = datetime.strptime(log_date_str, "%Y-%m-%d").date()
                            
                            # 選択された期間内か判定
                            if start_date <= log_date <= end_date:
                                total_usage_runs += 1
                                total_qrcodes_made += int(record.get('count', 0))
                        
                        # 結果を表示
                        st.markdown("---")
                        st.subheader(f"📅 集計結果 ({start_date} ～ {end_date})")
                        
                        m_col1, m_col2 = st.columns(2)
                        with m_col1:
                            st.metric(label="👥 総利用回数（システム実行回数）", value=f"{total_usage_runs} 回")
                        with m_col2:
                            st.metric(label="🖼️ 生成された総QRコード数", value=f"{total_qrcodes_made} 個")
                            
                    except Exception as e:
                        st.error(f"データの読み込み・集計に失敗しました: {e}")
