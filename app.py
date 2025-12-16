import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. SAYFA KONFİGÜRASYONU VE STİL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BIST Swing Trader Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS ile arayüzü güzelleştirme
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #363b4e;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #ffffff;
    }
    .metric-label {
        font-size: 14px;
        color: #a0a0a0;
    }
    .stProgress > div > div > div > div {
        background-color: #00c853;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. HİSSE LİSTESİ (BIST 100 ve Popüler Hisseler)
# -----------------------------------------------------------------------------
# Not: Gerçek bir üretim ortamında bu liste KAP'tan veya bir API'den dinamik çekilmelidir.
# Performans için şu an en likit hisseleri ekliyorum. Listenin tamamı yüzlerce hisse olabilir.
BIST_TICKERS = [
    "THYAO.IS", "ASELS.IS", "GARAN.IS", "SISE.IS", "EREGL.IS", "AKBNK.IS", "KCHOL.IS", "TUPRS.IS", 
    "YKBNK.IS", "ISCTR.IS", "SAHOL.IS", "BIMAS.IS", "PETKM.IS", "EKGYO.IS", "FROTO.IS", "PGSUS.IS", 
    "TTKOM.IS", "TCELL.IS", "ARCLK.IS", "ENKAI.IS", "TOASO.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS",
    "VESTL.IS", "SASA.IS", "HEKTS.IS", "ODAS.IS", "DOHOL.IS", "TSKB.IS", "ALARK.IS", "GUBRF.IS",
    "MGROS.IS", "SOKM.IS", "MAVI.IS", "TAVHL.IS", "TKFEN.IS", "AEFES.IS", "AGHOL.IS", "AKSEN.IS",
    "ALGYO.IS", "ALKIM.IS", "AYDEM.IS", "BAGFS.IS", "BERA.IS", "BIOEN.IS", "BRSAN.IS", "BRYAT.IS",
    "BUCIM.IS", "CCOLA.IS", "CEMTS.IS", "CIMSA.IS", "DOAS.IS", "EGEEN.IS", "ECILC.IS", "ENJSA.IS",
    "ENVER.IS", "ERBOS.IS", "FDOAF.IS", "GENIL.IS", "GESAN.IS", "GLYHO.IS", "GOZDE.IS", "GWIND.IS",
    "HALKB.IS", "ISDMR.IS", "ISFIN.IS", "ISGYO.IS", "ISMEN.IS", "IZMDC.IS", "KARSN.IS", "KARTN.IS",
    "KONTR.IS", "KORDS.IS", "KZBGY.IS", "LOGO.IS", "OTKAR.IS", "OYAKC.IS", "OZKGY.IS", "PARSN.IS",
    "PENTA.IS", "QUAGR.IS", "RTALB.IS", "SELEC.IS", "SKBNK.IS", "SMRTG.IS", "SNGYO.IS", "TATGD.IS",
    "TUKAS.IS", "TRGYO.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "YATAS.IS", "YYLGD.IS", "ZOREN.IS"
]

# -----------------------------------------------------------------------------
# 3. TEKNİK ANALİZ VE PUANLAMA MOTORU
# -----------------------------------------------------------------------------

def calculate_technicals(df):
    """Veri setine teknik indikatörleri ekler."""
    if len(df) < 50: return df # Yetersiz veri
    
    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # MACD
    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    # Sütun isimlerini standartlaştıralım (pandas_ta çıktıları değişken olabilir)
    df.rename(columns={col: col for col in df.columns if "MACD" in col or "MACDh" in col or "MACDs" in col}, inplace=True)
    # Genellikle: MACD_12_26_9, MACDh_12_26_9 (hist), MACDs_12_26_9 (signal)
    
    # MFI & Hacim Ortalaması
    df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
    
    # ADX
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df = pd.concat([df, adx], axis=1)
    
    # SuperTrend
    st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)
    df = pd.concat([df, st_data], axis=1)
    
    # Bollinger Bantları
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1)
    
    # EMA
    df['EMA_20'] = ta.ema(df['Close'], length=20)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    
    return df

def score_stock(df, ticker):
    """
    Belirtilen algoritmaya göre son mum için 0-100 arası puan üretir.
    Geriye puan ve açıklama detaylarını döner.
    """
    if df is None or len(df) < 50:
        return 0, {}

    # Son veriyi al
    last = df.iloc[-1]
    prev = df.iloc[-2] # Bir önceki mum (trend değişimleri için)

    score = 0
    details = {}

    # Pandas_ta sütun isimlerini yakalama (dinamik)
    try:
        macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
        hist_col = [c for c in df.columns if c.startswith('MACDh_')][0]
        # signal_col = [c for c in df.columns if c.startswith('MACDs_')][0]
        adx_col = [c for c in df.columns if c.startswith('ADX_')][0]
        dmp_col = [c for c in df.columns if c.startswith('DMP_')][0]
        dmn_col = [c for c in df.columns if c.startswith('DMN_')][0]
        st_col = [c for c in df.columns if c.startswith('SUPERT_')][0] # Trend değeri
        # st_dir_col = [c for c in df.columns if c.startswith('SUPERTd_')][0] # 1: Bull, -1: Bear
        bb_p_col = [c for c in df.columns if c.startswith('BBP_')][0] # %B
        bb_w_col = [c for c in df.columns if c.startswith('BBB_')][0] # Bandwidth
        bb_mid_col = [c for c in df.columns if c.startswith('BBM_')][0] # SMA (Middle Band)
    except IndexError:
        return 0, {"Hata": "İndikatör hesaplanamadı"}

    # --- 1. RSI [20 Puan] ---
    rsi = last['RSI']
    rsi_score = 0
    if 55 <= rsi <= 60:
        rsi_score = 20
    elif (50 <= rsi < 55) or (60 < rsi <= 65):
        rsi_score = 15
    elif (45 <= rsi < 50) or (65 < rsi <= 70):
        rsi_score = 10
    score += rsi_score
    details['RSI'] = f"{rsi:.2f} ({rsi_score}p)"

    # --- 2. MACD [20 Puan] ---
    macd_val = last[macd_col]
    hist_val = last[hist_col]
    prev_hist = prev[hist_col]
    
    macd_score = 0
    is_bullish_cross = (prev_hist < 0 and hist_val > 0) or (hist_val > 0 and hist_val > prev_hist)
    
    if is_bullish_cross and macd_val > 0 and hist_val > prev_hist:
        macd_score = 20
    elif hist_val > 0 and macd_val > 0:
        macd_score = 15
    elif hist_val > 0 and macd_val < 0:
        macd_score = 12
    # Else 0 (Düşüşte)
    score += macd_score
    details['MACD'] = f"{macd_score}p"

    # --- 3. Hacim ve MFI [20 Puan] ---
    vol = last['Volume']
    vol_avg = last['Vol_SMA']
    mfi = last['MFI']
    prev_mfi = prev['MFI']
    
    vol_score = 0
    if vol > (vol_avg * 1.5) and (50 <= mfi <= 80):
        vol_score = 20
    elif vol > (vol_avg * 1.2) and mfi > prev_mfi:
        vol_score = 15
    elif vol > vol_avg:
        vol_score = 10
    score += vol_score
    details['Hacim/MFI'] = f"{vol_score}p (MFI: {mfi:.1f})"

    # --- 4. ADX [15 Puan] ---
    adx = last[adx_col]
    di_plus = last[dmp_col]
    di_minus = last[dmn_col]
    prev_adx = prev[adx_col]
    
    adx_score = 0
    if adx > 25 and di_plus > di_minus:
        adx_score = 15
    elif (20 <= adx <= 25) and adx > prev_adx:
        adx_score = 10
    score += adx_score
    details['ADX'] = f"{adx:.1f} ({adx_score}p)"

    # --- 5. SuperTrend [15 Puan] ---
    st_val = last[st_col]
    close = last['Close']
    
    st_score = 0
    if close > st_val: # Fiyat SuperTrend'in üzerindeyse (Genelde SuperTrend değeri stop loss seviyesidir)
        st_score = 15
    score += st_score
    details['SuperTrend'] = "BULL" if st_score > 0 else "BEAR"

    # --- 6. Bollinger Bantları [10 Puan] ---
    pct_b = last[bb_p_col]
    bandwidth = last[bb_w_col]
    prev_bw = prev[bb_w_col]
    sma = last[bb_mid_col]
    
    bb_score = 0
    if pct_b > 0.8:
        bb_score = 10
    elif (bandwidth < prev_bw) and (close > sma): # Sıkışma (Bandwidth düşüyor) ve Trend pozitif
        bb_score = 8
    elif 0.5 <= pct_b <= 0.8:
        bb_score = 5
    score += bb_score
    details['Bollinger'] = f"%B: {pct_b:.2f} ({bb_score}p)"
    
    details['Fiyat'] = close
    details['Değişim'] = ((close - prev['Close']) / prev['Close']) * 100

    return score, details

# -----------------------------------------------------------------------------
# 4. VERİ ÇEKME VE İŞLEME (Optimize Edilmiş)
# -----------------------------------------------------------------------------

@st.cache_data(ttl=3600) # 1 saat cache
def get_historical_data(ticker, period="6mo"):
    """
    Tek bir hisse için geçmiş veriyi çeker.
    Hata durumunda None döner.
    """
    try:
        df = yf.download(ticker, period=period, progress=False, threads=False)
        # MultiIndex sütun yapısını düzelt (yfinance yeni versiyon uyumluluğu)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if df.empty:
            return None
        return df
    except Exception as e:
        return None

def analyze_market(tickers_list):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers_list)
    
    for i, ticker in enumerate(tickers_list):
        # UI Güncelleme
        perc = (i + 1) / total
        progress_bar.progress(int(perc * 100))
        status_text.text(f"Analiz ediliyor: {ticker} ({i+1}/{total})")
        
        # Veri Çek
        df = get_historical_data(ticker)
        
        if df is not None:
            try:
                # İndikatörleri Hesapla
                df = calculate_technicals(df)
                # Puanla
                score, details = score_stock(df, ticker)
                
                if score > 0: # Sadece hesaplanabilenleri ekle
                    results.append({
                        "Hisse": ticker.replace(".IS", ""),
                        "Toplam Puan": score,
                        "Fiyat": f"{details.get('Fiyat', 0):.2f} TL",
                        "Değişim %": details.get('Değişim', 0),
                        "RSI Detay": details.get('RSI'),
                        "Trend": details.get('SuperTrend'),
                        "Hacim": details.get('Hacim/MFI')
                    })
            except Exception as e:
                continue # Hesaplama hatası olursa atla

    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results)

# -----------------------------------------------------------------------------
# 5. ARAYÜZ (UI) YAPILANDIRMASI
# -----------------------------------------------------------------------------

# --- Sidebar ---
st.sidebar.title("🛠 Kontrol Paneli")
st.sidebar.markdown("Algoritmayı çalıştırmak için aşağıdaki butonu kullanın.")

run_analysis = st.sidebar.button("🚀 Piyasayı Tara ve Analiz Et", use_container_width=True)

st.sidebar.info(f"Listede {len(BIST_TICKERS)} adet hisse tanımlı.")
st.sidebar.markdown("---")

# Session State Yönetimi (Analiz sonuçlarını kaybetmemek için)
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# Analizi Çalıştır
if run_analysis:
    with st.spinner('Veriler çekiliyor ve indikatörler hesaplanıyor... Lütfen bekleyin.'):
        df_results = analyze_market(BIST_TICKERS)
        if not df_results.empty:
            # Puan sırasına göre diz
            df_results = df_results.sort_values(by="Toplam Puan", ascending=False).reset_index(drop=True)
            st.session_state.analysis_results = df_results
        else:
            st.error("Veri alınamadı veya piyasa kapalı olabilir.")

# --- Ana Ekran ---
st.title("📊 BIST Swing Trader Pro")
st.markdown("Bu panel, **Borsa İstanbul** hisselerini özel bir teknik analiz algoritması ile tarar ve 0-100 arasında puanlar.")

if st.session_state.analysis_results is not None:
    df_res = st.session_state.analysis_results
    
    # En iyiler (Top 5)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if len(df_res) > 0:
            top1 = df_res.iloc[0]
            st.metric(label=f"🥇 Lider: {top1['Hisse']}", value=f"{top1['Toplam Puan']} Puan", delta=f"%{top1['Değişim %']:.2f}")
    with col2:
        if len(df_res) > 1:
            top2 = df_res.iloc[1]
            st.metric(label=f"🥈 İkinci: {top2['Hisse']}", value=f"{top2['Toplam Puan']} Puan", delta=f"%{top2['Değişim %']:.2f}")
    with col3:
        if len(df_res) > 2:
            top3 = df_res.iloc[2]
            st.metric(label=f"🥉 Üçüncü: {top3['Hisse']}", value=f"{top3['Toplam Puan']} Puan", delta=f"%{top3['Değişim %']:.2f}")

    # Liderlik Tablosu (Sidebar'a özet, Ana ekrana detay)
    st.subheader("🏆 Liderlik Tablosu (Top 50)")
    
    # Tabloyu biçimlendirme
    st.dataframe(
        df_res.head(50).style.background_gradient(subset=['Toplam Puan'], cmap="Greens"),
        use_container_width=True,
        height=400
    )
    
    # --- Detaylı Hisse İnceleme ---
    st.markdown("---")
    st.subheader("🔍 Detaylı Hisse Analizi")
    
    selected_ticker = st.selectbox("İncelemek istediğiniz hisseyi seçin:", df_res['Hisse'].tolist())
    
    if selected_ticker:
        full_ticker = selected_ticker + ".IS"
        stock_df = get_historical_data(full_ticker, period="1y")
        
        if stock_df is not None:
            stock_df = calculate_technicals(stock_df)
            score, details = score_stock(stock_df, full_ticker)
            
            # --- Grafik ve Metrikler ---
            
            # Üst Bilgi
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-card'><div class='metric-label'>Toplam Puan</div><div class='metric-value'>{score}/100</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-card'><div class='metric-label'>RSI</div><div class='metric-value'>{stock_df['RSI'].iloc[-1]:.1f}</div></div>", unsafe_allow_html=True)
            
            # MACD Sinyali (Basitçe)
            macd_col = [c for c in stock_df.columns if c.startswith('MACD_')][0]
            hist_col = [c for c in stock_df.columns if c.startswith('MACDh_')][0]
            macd_val = stock_df[macd_col].iloc[-1]
            hist_val = stock_df[hist_col].iloc[-1]
            macd_str = "AL" if hist_val > 0 and macd_val > 0 else "SAT/NÖTR"
            
            c3.markdown(f"<div class='metric-card'><div class='metric-label'>MACD Durumu</div><div class='metric-value' style='font-size:18px'>{macd_str}</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-card'><div class='metric-label'>Fiyat</div><div class='metric-value'>{stock_df['Close'].iloc[-1]:.2f} ₺</div></div>", unsafe_allow_html=True)
            
            st.markdown("###")
            
            # Plotly Grafiği
            fig = go.Figure()
            
            # Mum Grafiği
            fig.add_trace(go.Candlestick(x=stock_df.index,
                            open=stock_df['Open'],
                            high=stock_df['High'],
                            low=stock_df['Low'],
                            close=stock_df['Close'],
                            name='Fiyat'))
            
            # EMA 20 & 50
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['EMA_20'], line=dict(color='orange', width=1), name='EMA 20'))
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['EMA_50'], line=dict(color='blue', width=1), name='EMA 50'))
            
            # Bollinger Bands
            bb_upper = [c for c in stock_df.columns if c.startswith('BBU_')][0]
            bb_lower = [c for c in stock_df.columns if c.startswith('BBL_')][0]
            
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df[bb_upper], line=dict(color='gray', width=0), showlegend=False, name='BB Upper'))
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df[bb_lower], line=dict(color='gray', width=0), fill='tonexty', fillcolor='rgba(128,128,128,0.1)', name='Bollinger'))

            fig.update_layout(
                title=f"{selected_ticker} Teknik Analiz Grafiği",
                yaxis_title='Fiyat (TL)',
                xaxis_rangeslider_visible=False,
                height=600,
                template="plotly_dark",
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Puan Detayları (Expandable)
            with st.expander("📝 Puanlama Detaylarını Gör"):
                st.json(details)

else:
    st.info("👈 Lütfen sol menüden 'Piyasayı Tara' butonuna basarak analizi başlatın.")
    st.warning("Not: 100+ hissenin verisini çekmek ve işlemek yaklaşık 30-60 saniye sürebilir.")
