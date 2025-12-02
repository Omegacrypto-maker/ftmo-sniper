import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(layout="wide", page_title="FTMO Sniper Cloud", page_icon="☁️")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .metric-container {
        background-color: #1e2130;
        border: 1px solid #2b2f42;
        padding: 15px;
        border-radius: 8px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心逻辑类 (Kraken 版 - 美国IP可用)
# ==========================================
class SniperBrain:
    def __init__(self):
        # 🔥 修改点：换成 Kraken 交易所
        # Kraken 允许美国 IP 访问，Streamlit Cloud 可以连接
        self.exchange = ccxt.kraken({
            'enableRateLimit': True
        })
    
    def fetch_candles(self, symbol, timeframe, limit=100):
        try:
            # Kraken 的数据获取逻辑
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'vol'])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            return df
            
        except Exception as e:
            st.error(f"❌ 数据抓取出错 [{timeframe}]: {e}")
            return None

    def calculate_indicators(self, df, ema_period, atr_period=14):
        if df is None or df.empty:
            return None
            
        try:
            df[f'EMA_{ema_period}'] = df['close'].ewm(span=ema_period, adjust=False).mean()
            
            # ATR 计算
            df['tr0'] = abs(df['high'] - df['low'])
            df['tr1'] = abs(df['high'] - df['close'].shift())
            df['tr2'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
            df['ATR'] = df['tr'].rolling(window=atr_period).mean()
            return df
        except Exception as e:
            st.error(f"❌ 指标计算出错: {e}")
            return None

# ==========================================
# 3. 侧边栏
# ==========================================
with st.sidebar:
    st.title("🦅 FTMO 狙击手")
    st.caption("☁️ 云端兼容版 (Kraken)")
    st.success("✅ 数据源: Kraken (US Compatible)")
    st.divider()
    
    # Kraken 的交易对名称通常是 ETH/USD 而不是 USDT
    symbol = st.selectbox("交易标的", ["ETH/USD", "BTC/USD", "SOL/USD"])
    refresh_btn = st.button("🔄 刷新行情", type="primary")

# ==========================================
# 4. 主程序
# ==========================================

if True:
    brain = SniperBrain()
    
    status_text = st.empty()
    status_text.info(f"📡 正在连接 Kraken 获取 {symbol} 数据...")
    
    # --- 1. 获取日线 ---
    df_daily = brain.fetch_candles(symbol, '1d', limit=100)
    
    if df_daily is None:
        status_text.error("💀 错误：无法获取数据。可能 Kraken 接口繁忙，请稍后刷新。")
        st.stop()
        
    df_daily = brain.calculate_indicators(df_daily, 50)
    
    # --- 2. 获取4H线 ---
    df_4h = brain.fetch_candles(symbol, '4h', limit=100)
    
    if df_4h is None:
        status_text.error("💀 错误：日线成功，但 4H 线获取失败。")
        st.stop()
        
    df_4h = brain.calculate_indicators(df_4h, 20)
    
    status_text.empty() 

    # --- 数据提取 ---
    daily_trend = df_daily.iloc[-1]['EMA_50']
    daily_close = df_daily.iloc[-1]['close']
    current_price = df_4h.iloc[-1]['close']
    h4_ema = df_4h.iloc[-1]['EMA_20']
    current_atr = df_4h.iloc[-1]['ATR']

    # --- 逻辑判断 ---
    is_bullish = daily_close > daily_trend
    dist_pct = abs(current_price - h4_ema) / current_price * 100
    is_pullback = dist_pct <= 2.5
    
    # --- 界面渲染 ---
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("当前价格", f"${current_price:.2f}")
    with col2: st.metric("日线大势", "Bull" if is_bullish else "Bear", delta="🟢 多头" if is_bullish else "🔴 空头")
    with col3: st.metric("4H 回调", f"距均线 {dist_pct:.2f}%", delta="🎯 射程内" if is_pullback else "⏳ 等待")
    with col4: st.metric("ATR (波动)", f"{current_atr:.2f}")

    # 画图
    st.subheader(f"📈 {symbol} 4H 狙击视图")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df_4h['time'], open=df_4h['open'], high=df_4h['high'], low=df_4h['low'], close=df_4h['close'], name='Price'))
    fig.add_trace(go.Scatter(x=df_4h['time'], y=df_4h['EMA_20'], line=dict(color='yellow', width=2), name='EMA20'))
    
    if is_pullback:
         fig.add_annotation(x=df_4h.iloc[-1]['time'], y=current_price, text="🎯 狙击机会", showarrow=True, arrowhead=1)
         
    fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    
    # 策略建议
    st.info(f"💡 数据源已切换至 Kraken (以兼容云端网络)。策略状态: 日线趋势 {'向上' if is_bullish else '向下'} | 4H 距离 EMA20 {dist_pct:.2f}%")
