import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="黄金AI决策雷达", page_icon="🏆", layout="wide")

# --- 核心逻辑：数据获取 (缓存1小时，实现每小时更新) ---
@st.cache_data(ttl=3600)
def get_financial_data():
    # 定义监控的资产
    tickers = {
        '黄金 (Gold)': 'GC=F',
        '美元指数 (DXY)': 'DX-Y.NYB',
        '10年美债收益率': '^TNX',
        '恐慌指数 (VIX)': '^VIX', # 政治风险代理指标
        '标普500': '^GSPC'
    }
    
    data_store = {}
    # 获取最近1个月的数据，用于计算趋势
    for name, symbol in tickers.items():
        try:
            # 下载数据
            df = yf.download(symbol, period="1mo", interval="1h", progress=False)
            if not df.empty:
                data_store[name] = df
        except Exception as e:
            st.error(f"获取 {name} 失败: {e}")
    return data_store

# --- 核心逻辑：新闻抓取 (政治/宏观) ---
@st.cache_data(ttl=3600)
def get_news():
    # 使用 CNBC 和 Investing.com 的 RSS 源 (免费且实时)
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
        "https://feeds.content.dowjones.io/public/rss/mw_topstories" # Market Watch
    ]
    news_items = []
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]: # 每个源取前5条
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', '刚刚')
            })
    return news_items

# --- 核心逻辑：AI 打分系统 ---
def calculate_signal(data):
    score = 0
    reasons = []
    
    # 1. 黄金技术面 (RSI & 均线)
    gold_df = data.get('黄金 (Gold)')
    if gold_df is not None:
        current_price = gold_df['Close'].iloc[-1]
        # 计算 50小时均线
        ma50 = gold_df['Close'].rolling(50).mean().iloc[-1]
        # 简单计算 RSI (14)
        delta = gold_df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        if current_price > ma50:
            score += 2
            reasons.append("📈 技术面：金价位于50小时均线上方 (看涨)")
        else:
            score -= 2
            reasons.append("📉 技术面：金价位于50小时均线下方 (看跌)")
            
        if rsi < 30:
            score += 1
            reasons.append("⚡ RSI指标：进入超卖区间 (反弹概率大)")
        elif rsi > 70:
            score -= 1
            reasons.append("⚠️ RSI指标：进入超买区间 (回调风险大)")

    # 2. 宏观面 (美元 & 美债)
    dxy_df = data.get('美元指数 (DXY)')
    if dxy_df is not None:
        # 比较当前和24小时前
        dxy_now = dxy_df['Close'].iloc[-1]
        dxy_prev = dxy_df['Close'].iloc[-24] if len(dxy_df) > 24 else dxy_df['Close'].iloc[0]
        
        if dxy_now < dxy_prev:
            score += 2
            reasons.append("💵 宏观面：美元指数日内走弱 (利好黄金)")
        else:
            score -= 2
            reasons.append("💵 宏观面：美元指数日内走强 (利空黄金)")

    # 3. 情绪面 (VIX 恐慌指数 - 代理地缘政治)
    vix_df = data.get('恐慌指数 (VIX)')
    if vix_df is not None:
        vix_now = vix_df['Close'].iloc[-1]
        if vix_now > 20: # 恐慌高企
            score += 2
            reasons.append("💣 情绪面：市场恐慌指数(VIX)较高 (避险资金流入)")
        elif vix_now < 13:
            score -= 1
            reasons.append("🕊️ 情绪面：市场极度贪婪/平静 (避险需求低)")

    return score, reasons

# --- 界面渲染 ---
def main():
    st.title("🥇 黄金投资 AI 决策室")
    st.markdown(f"*数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} (每小时自动刷新)*")
    
    # 侧边栏
    with st.sidebar:
        st.header("关于系统")
        st.info("本系统每小时抓取美联储利率预期(美债)、全球地缘政治恐慌度(VIX)及美元走势，综合计算买卖信号。")
        if st.button("🔄 手动强制刷新数据"):
            st.cache_data.clear()
            st.rerun()

    # 加载数据
    with st.spinner('正在连接全球交易所与新闻源...'):
        data = get_financial_data()
        news = get_news()
        score, reasons = calculate_signal(data)

    # 1. 核心决策仪表盘
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        cur_gold = data['黄金 (Gold)']['Close'].iloc[-1]
        st.metric("实时金价 (USD/oz)", f"${cur_gold:.2f}", 
                  f"{cur_gold - data['黄金 (Gold)']['Close'].iloc[-2]:.2f}")
    
    with col2:
        # 信号展示
        st.subheader("🤖 AI 建议")
        if score >= 3:
            st.success(f"⭐⭐⭐ 强烈建议买入 (得分: {score})")
        elif score > 0:
            st.info(f"⭐ 偏多震荡 / 逢低做多 (得分: {score})")
        elif score <= -3:
            st.error(f"🔻🔻🔻 建议卖出 / 做空 (得分: {score})")
        else:
            st.warning(f"✋ 观望 / 等待方向 (得分: {score})")

    with col3:
        cur_dxy = data['美元指数 (DXY)']['Close'].iloc[-1]
        st.metric("美元指数 DXY", f"{cur_dxy:.2f}", 
                  f"{cur_dxy - data['美元指数 (DXY)']['Close'].iloc[-2]:.2f}", delta_color="inverse")

    # 2. 详细逻辑展示
    st.write("### 🧠 决策依据")
    for r in reasons:
        st.write(r)

    st.divider()

    # 3. 图表与新闻
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("### 📊 黄金 vs 美元走势 (最近1周)")
        # 归一化处理以便在同一张图显示
        df_chart = pd.DataFrame()
        g_data = data['黄金 (Gold)']['Close'][-120:] # 最近120小时
        d_data = data['美元指数 (DXY)']['Close'][-120:]
        
        # 简单归一化: (价格 - 均值) / 均值
        df_chart['Gold'] = (g_data - g_data.mean()) / g_data.mean()
        df_chart['USD'] = (d_data - d_data.mean()) / d_data.mean()
        st.line_chart(df_chart)
        st.caption("注：数据已归一化，目的是看‘剪刀差’。通常美元跌(橙线)，黄金涨(蓝线)。")

    with c2:
        st.write("### 🌍 全球宏观/政治快讯")
        for n in news:
            st.markdown(f"**[{n['title']}]({n['link']})**")
            st.caption(f"发布时间: {n['published']}")

if __name__ == "__main__":
    main()