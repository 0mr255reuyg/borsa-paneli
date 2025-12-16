import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# -----------------------------------------------------------------------------
# 1. SAYFA YAPILANDIRMASI VE STİL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BIST Swing Trader Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS ile arayüzü iyileştirme
st.markdown("""
<style>
    .metric-box {
        background-color: #262730;
        border: 1px solid #464b5f;
        padding: 15px;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-title {
        color: #fafafa;
        font-size: 0.9em;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.2em;
        font-weight: bold;
    }
    .big-font {
        font-size: 24px !important;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. VERİ VE HİSSE LİSTESİ
# -----------------------------------------------------------------------------

# Performans için BIST 100 ve Popüler Hisselerden oluşan geniş bir liste
BIST_TICKERS = [
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "VAKBN.IS", "HALKB.IS", "TUPRS.IS", 
    "EREGL.IS", "KCHOL.IS", "SAHOL.IS", "SISE.IS", "BIMAS.IS", "ASELS.IS", "FROTO.IS", "TOASO.IS", 
    "TTKOM.IS", "TCELL.IS", "PETKM.IS", "HEKTS.IS", "SASA.IS", "KOZAL.IS", "KOZAA.IS", "IPEKE.IS", 
    "KRDMD.IS", "EKGYO.IS", "ODAS.IS", "ARCLK.IS", "ENKAI.IS", "VESTL.IS", "ALARK.IS", "TAVHL.IS", 
    "MGROS.IS", "AEFES.IS", "AGHOL.IS", "AKSEN.IS", "ASTOR.IS", "EUPWR.IS", "KONTR.IS", "SMRTG.IS",
    "GESAN.IS", "YEOTK.IS", "ALFAS.IS", "CVKMD.IS", "KOPOL.IS", "EBEBK.IS", "TABGD.IS", "REEDR.IS",
    "HATSN.IS", "TARKM.IS", "DOAS.IS", "PGSUS.IS", "ENJSA.IS", "SOKM.IS", "ULKER.IS", "TKFEN.IS"
]

@st.cache_data(ttl=3600)  # 1 saatlik önbellek
def get_batch_data(tickers):
    """
    Tüm hisseler için toplu veri çeker (Performans optimizasyonu).
    """
    try:
        # Son 250 gün (yaklaşık 1 yıl) yeterli olacaktır
        data = yf.download(tickers, period="1y", group_by='ticker', threads=True, progress=False)
        return data
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return None

# -----------------------------------------------------------------------------
# 3. MANTIK VE HESAPLAMA MOTORU
# -----------------------------------------------------------------------------

def calculate_score(df):
    """
    Tek bir hisse senedi DataFrame'i için Swing Skorunu ve durumlarını hesaplar.
    """
    if df is None or len(df) < 50:
        return 0, {}, df

    # --- İndikatör Hesaplamaları ---
    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # MACD
    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_Signal'] = macd['MACDs_12_26_9']
    df['MACD_Hist'] = macd['MACDh_12_26_9']
    
    # MFI & Volume SMA
    df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # ADX
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df['ADX'] = adx['ADX_14']
    df['DMP'] = adx['DMP_14'] # DI+
    df['DMN'] = adx['DMN_14'] # DI-
    
    # SuperTrend
    st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=7, multiplier=3)
    # Sütun isimleri değişkendir, genellikle SUPERT_7_3.0 şeklindedir
    st_col = [c for c in st_data.columns if c.startswith('SUPERT')][0]
    df['SuperTrend'] = st_data[st_col]
    
    # Bollinger Bands
    bb = ta.bbands(df['Close'], length=20, std=2)
    df['BBU'] = bb['BBU_20_2.0']
    df['BBL'] = bb['BBL_20_2.0']
    df['BBM'] = bb['BBM_20_2.0'] # SMA
    df['BBP'] = bb['BBP_20_2.0'] # %B
    df['BBW'] = bb['BBB_20_2.0'] # Bandwidth for squeeze check
    
    # EMA
    df['EMA20'] = ta.ema(df['Close'], length=20)
    df['EMA50'] = ta.ema(df['Close'], length=50)

    # --- Puanlama Mantığı (Son satır verisi) ---
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    score = 0
    status = {}

    # 1. RSI [20 Puan]
    rsi_val = curr['RSI']
    if 55 <= rsi_val <= 60:
        score += 20
        status['RSI'] = "Mükemmel (55-60)"
    elif (50 <= rsi_val < 55) or (60 < rsi_val <= 65):
        score += 15
        status['RSI'] = "İyi (50-65)"
    elif (45 <= rsi_val < 50) or (65 < rsi_val <= 70):
        score += 10
        status['RSI'] = "Orta (45-70)"
    else:
        status['RSI'] = "Zayıf/Aşırı"

    # 2. MACD [20 Puan]
    # Yükseliş Kesişimi: MACD > Signal
    bullish_cross = curr['MACD'] > curr['MACD_Signal']
    above_zero = curr['MACD'] > 0
    hist_increasing = curr['MACD_Hist'] > prev['MACD_Hist']
    
    if bullish_cross and above_zero and hist_increasing:
        score += 20
        status['MACD'] = "Güçlü AL"
    elif bullish_cross and above_zero:
        score += 15
        status['MACD'] = "AL (>0)"
    elif bullish_cross and not above_zero:
        score += 12
        status['MACD'] = "AL (<0)"
    else:
        status['MACD'] = "Nötr/Sat"

    # 3. Hacim ve MFI [20 Puan]
    vol_cond1 = curr['Volume'] > (curr['Vol_SMA'] * 1.5)
    vol_cond2 = curr['Volume'] > (curr['Vol_SMA'] * 1.2)
    vol_cond3 = curr['Volume'] > curr['Vol_SMA']
    mfi_val = curr['MFI']
    mfi_rising = mfi_val > prev['MFI']

    if vol_cond1 and (50 <= mfi_val <= 80):
        score += 20
        status['MFI'] = "Balina Girişi"
    elif vol_cond2 and mfi_rising:
        score += 15
        status['MFI'] = "Hacimli Artış"
    elif vol_cond3:
        score += 10
        status['MFI'] = "Hacim > Ort"
    else:
        status['MFI'] = "Düşük Hacim"

    # 4. ADX [15 Puan]
    adx_val = curr['ADX']
    di_plus = curr['DMP']
    di_minus = curr['DMN']
    adx_rising = adx_val > prev['ADX']

    if adx_val > 25 and di_plus > di_minus:
        score += 15
        status['ADX'] = "Güçlü Trend"
    elif (20 <= adx_val <= 25) and adx_rising:
        score += 10
        status['ADX'] = "Trend Başlıyor"
    else:
        status['ADX'] = "Trendsiz"

    # 5. SuperTrend [15 Puan]
    if curr['Close'] > curr['SuperTrend']:
        score += 15
        status['Trend'] = "Yükseliş (Yeşil)"
    else:
        status['Trend'] = "Düşüş (Kırmızı)"

    # 6. Bollinger [10 Puan]
    bb_p = curr['BBP'] # %B
    # Sıkışma basit mantık: Bandwidth son 20 günün en düşüğüne yakınsa (burada basitleştirildi)
    squeeze = curr['BBW'] < df['BBW'].rolling(20).mean().iloc[-1] * 0.9 
    
    if bb_p > 0.8:
        score += 10
        status['BB'] = "Üst Banda Yakın"
    elif squeeze and curr['Close'] > curr['BBM']:
        score += 8
        status['BB'] = "Sıkışma Kırılımı"
    elif 0.5 <= bb_p <= 0.8:
        score += 5
        status['BB'] = "Orta Bandın Üstü"
    else:
        status['BB'] = "Zayıf Konum"

    return score, status, df

# -----------------------------------------------------------------------------
# 4. ANALİZ YÖNETİCİSİ
# -----------------------------------------------------------------------------

def analyze_market():
    """
    Tüm market verisini çeker, işler ve liderlik tablosunu oluşturur.
    """
    raw_data = get_batch_data(BIST_TICKERS)
    
    leaderboard = []
    analyzed_stocks = {} # Daha sonra grafik için sakla

    if raw_data is not None:
        # Progress bar
        progress_bar = st.sidebar.progress(0)
        total_stocks = len(BIST_TICKERS)
        
        for i, ticker in enumerate(BIST_TICKERS):
            try:
                # Multi-index'ten tek hisse verisini al
                df_ticker = raw_data[ticker].copy()
                df_ticker = df_ticker.dropna()
                
                if df_ticker.empty:
                    continue
                    
                score, status, df_calc = calculate_score(df_ticker)
                
                # Temiz Sembol Adı
                clean_symbol = ticker.replace(".IS", "")
                
                # Son Fiyat ve Değişim
                last_price = df_calc['Close'].iloc[-1]
                prev_price = df_calc['Close'].iloc[-2]
                pct_change = ((last_price - prev_price) / prev_price) * 100
                
                leaderboard.append({
                    "Sembol": clean_symbol,
                    "Puan": score,
                    "Fiyat": last_price,
                    "Değişim %": pct_change,
                    "Tam_Sembol": ticker,
                    "Status": status # Detaylar için
                })
                
                analyzed_stocks[clean_symbol] = df_calc
                
            except Exception as e:
                # Bazı hisselerde veri eksikliği olabilir, geçiyoruz
                continue
            
            # Progress bar güncelle
            progress_bar.progress((i + 1) / total_stocks)
        
        progress_bar.empty()

    # DataFrame'e çevir ve Puan'a göre sırala
    df_leaderboard = pd.DataFrame(leaderboard)
    if not df_leaderboard.empty:
        df_leaderboard = df_leaderboard.sort_values(by="Puan", ascending=False).reset_index(drop=True)
        
    return df_leaderboard, analyzed_stocks

# -----------------------------------------------------------------------------
# 5. KULLANICI ARAYÜZÜ (UI)
# -----------------------------------------------------------------------------

# --- KENAR ÇUBUĞU ---
st.sidebar.title("🚀 BIST Swing Pro")
st.sidebar.markdown("---")

df_lb, stock_data_dict = analyze_market()

if not df_lb.empty:
    st.sidebar.subheader("🏆 Liderlik Tablosu")
    
    # Basit bir tablo gösterimi
    st.sidebar.dataframe(
        df_lb[['Sembol', 'Puan']],
        hide_index=True,
        use_container_width=True,
        height=400
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Hisse Seçimi")
    
    # Seçim Kutusu
    selected_symbol = st.sidebar.selectbox(
        "Analiz edilecek hisseyi seçin:",
        options=df_lb['Sembol'].tolist()
    )
else:
    st.sidebar.warning("Veri çekilemedi. Lütfen bağlantınızı kontrol edin.")
    selected_symbol = None

# --- ANA EKRAN (ODAK MODU) ---

if selected_symbol and selected_symbol in stock_data_dict:
    # Seçilen hissenin verilerini al
    row_data = df_lb[df_lb['Sembol'] == selected_symbol].iloc[0]
    df_chart = stock_data_dict[selected_symbol]
    status_dict = row_data['Status']
    
    # 1. BAŞLIK BÖLÜMÜ
    col_header1, col_header2 = st.columns([3, 1])
    
    with col_header1:
        # Şirket adı eşleştirmesi (Demo için basit tutuldu, geliştirilebilir)
        st.title(f"{selected_symbol}")
        st.caption(f"BIST 100 / {selected_symbol} Analiz Raporu")
    
    with col_header2:
        price_color = "green" if row_data['Değişim %'] >= 0 else "red"
        st.markdown(f"""
        <div style="text-align: right;">
            <div class="big-font">{row_data['Fiyat']:.2f} TL</div>
            <div style="color: {price_color}; font-weight: bold; font-size: 18px;">
                {row_data['Değişim %']:.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 2. GRAFİK (PLOTLY)
    
    # Mum grafiği
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart['Open'],
        high=df_chart['High'],
        low=df_chart['Low'],
        close=df_chart['Close'],
        name='Fiyat'
    ))

    # EMA 20
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart['EMA20'],
        line=dict(color='orange', width=1), name='EMA 20'
    ))

    # EMA 50
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart['EMA50'],
        line=dict(color='blue', width=1), name='EMA 50'
    ))

    # Bollinger Bands
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart['BBU'],
        line=dict(color='gray', width=1, dash='dot'), name='BB Üst', opacity=0.5
    ))
    fig.add_trace(go.Scatter(
        x=df_chart.index, y=df_chart['BBL'],
        line=dict(color='gray', width=1, dash='dot'), name='BB Alt', opacity=0.5,
        fill='tonexty' # Üst ve alt arasını boyar
    ))

    # Düzen Ayarları
    fig.update_layout(
        height=600,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Gridleri koyulaştır
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#333')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')

    st.plotly_chart(fig, use_container_width=True)

    # 3. VERİ ŞERİDİ (GRAFİK ALTI)
    
    st.markdown("### 📊 Teknik Gösterge Özeti")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    
    # Renk kodu fonksiyonu
    def get_color(val, threshold=50):
        return "#4CAF50" if val >= threshold else "#FF5252" # Yeşil / Kırmızı

    score_color = get_color(row_data['Puan'], 70)
    
    with c1:
        st.markdown(f"""
        <div class="metric-box" style="border-color: {score_color};">
            <div class="metric-title">TOPLAM PUAN</div>
            <div class="metric-value" style="color: {score_color};">{int(row_data['Puan'])}/100</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">RSI (14)</div>
            <div class="metric-value">{int(df_chart['RSI'].iloc[-1])}</div>
            <div style="font-size: 0.8em; color: #aaa;">{status_dict.get('RSI', '-')}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">MACD</div>
            <div class="metric-value" style="font-size: 1em;">{status_dict.get('MACD', '-')}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">MFI / HACİM</div>
            <div class="metric-value" style="font-size: 1em;">{status_dict.get('MFI', '-')}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c5:
        trend_color = "#4CAF50" if "Yükseliş" in status_dict.get('Trend', '') else "#FF5252"
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">SÜPER TREND</div>
            <div class="metric-value" style="color: {trend_color}; font-size: 1em;">{status_dict.get('Trend', '-')}</div>
        </div>
        """, unsafe_allow_html=True)

else:
    st.info("Lütfen kenar çubuğundan analiz edilecek bir hisse seçin.")
