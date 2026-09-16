import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time

from gmgn import gmgn

st.set_page_config(
    page_title="GMGN 热榜分析器",
    page_icon="📊",
    layout="wide",
)

st.title("📊 GMGN 热榜多时间框架分析")
st.caption("GitHub + Streamlit Cloud 部署版 | 非官方接口，可能被 Cloudflare 拦截")

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("⚙️ 参数")
    chain = st.selectbox("链", ["sol", "bsc", "base", "eth"], index=0)
    volume_threshold = st.number_input("最小平均成交量", min_value=0, value=1000, step=500)
    market_cap_threshold = st.number_input("最小中位市值", min_value=0, value=10000, step=5000)
    min_consistency = st.slider("最少出现时间框架数", 1, 5, 3)
    st.divider()
    auto_refresh = st.checkbox("自动刷新（约 90 秒）", value=False)
    run_btn = st.button("🚀 立即分析", type="primary", use_container_width=True)

TIMEFRAMES = ["1m", "5m", "1h", "6h", "24h"]


def fetch_and_analyze(chain: str, volume_th: float, mcap_th: float, consistency_th: int):
    client = gmgn(chain=chain)
    rows = []
    errors = []

    progress = st.progress(0, text="正在抓取各时间框架...")
    for i, tf in enumerate(TIMEFRAMES):
        try:
            result = client.getTrendingTokens(timeframe=tf)
            # 兼容 rank / list / 直接 list
            if isinstance(result, dict):
                tokens = result.get("rank") or result.get("list") or result.get("data") or []
            elif isinstance(result, list):
                tokens = result
            else:
                tokens = []

            for t in tokens:
                if not isinstance(t, dict):
                    continue
                rows.append({
                    "address": t.get("address") or t.get("token_address") or t.get("id"),
                    "symbol": t.get("symbol") or t.get("name") or "?",
                    "chain": t.get("chain") or chain,
                    "price": _to_float(t.get("price") or t.get("price_usd")),
                    "volume": _to_float(t.get("volume") or t.get("volume_24h") or t.get("swaps")),
                    "market_cap": _to_float(t.get("market_cap") or t.get("mc") or t.get("fdv")),
                    "price_change": _to_float(
                        t.get("price_change_percent")
                        or t.get("price_change")
                        or t.get("price_change_percent1h")
                    ),
                    "timeframe": tf,
                })
        except Exception as e:
            errors.append(f"{tf}: {e}")
        progress.progress((i + 1) / len(TIMEFRAMES), text=f"已完成 {tf}")
    progress.empty()

    if not rows:
        msg = "没有获取到数据。"
        if errors:
            msg += "\n\n错误详情:\n" + "\n".join(errors)
        return None, msg, errors

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["address"])

    grouped = (
        df.groupby("address")
        .agg({
            "symbol": "first",
            "chain": "first",
            "price": "mean",
            "volume": "mean",
            "market_cap": "median",
            "timeframe": "nunique",
            "price_change": "mean",
        })
        .rename(columns={
            "timeframe": "consistency_count",
            "price": "avg_price",
            "volume": "avg_volume",
            "market_cap": "median_market_cap",
            "price_change": "avg_price_change",
        })
    )

    filtered = grouped[
        (grouped["consistency_count"] >= consistency_th)
        & (grouped["avg_volume"] >= volume_th)
        & (grouped["median_market_cap"] >= mcap_th)
    ].sort_values(
        by=["consistency_count", "avg_volume"], ascending=False
    ).reset_index()

    return filtered, None, errors


def _to_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


# ========== 主逻辑 ==========
should_run = run_btn or auto_refresh

if should_run:
    with st.spinner("分析中，请稍候..."):
        result, error, errors = fetch_and_analyze(
            chain, volume_threshold, market_cap_threshold, min_consistency
        )

    if error:
        st.error(error)
        st.info(
            "常见原因：\n"
            "1. GMGN Cloudflare 拦截了云端 IP\n"
            "2. 非官方接口结构变更\n"
            "3. 网络超时\n\n"
            "可尝试：换链、降低过滤条件、稍后重试，或改在本地/自己的服务器运行。"
        )
    elif result is None or result.empty:
        st.warning("过滤后没有符合条件的代币，请降低阈值再试。")
        if errors:
            with st.expander("部分时间框架报错"):
                for e in errors:
                    st.text(e)
    else:
        st.success(
            f"完成 | {len(result)} 个代币通过过滤 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if errors:
            with st.expander(f"⚠️ {len(errors)} 个时间框架有警告"):
                for e in errors:
                    st.text(e)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("通过数量", len(result))
        c2.metric("最高一致性", int(result["consistency_count"].max()))
        c3.metric("成交量中位数", f"{result['avg_volume'].median():,.0f}")
        c4.metric("市值中位数", f"{result['median_market_cap'].median():,.0f}")

        st.divider()
        st.subheader("📋 过滤结果")

        show = result.copy()
        show["avg_price"] = show["avg_price"].map(lambda x: f"{x:.8f}" if pd.notna(x) else "-")
        show["avg_volume"] = show["avg_volume"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")
        show["median_market_cap"] = show["median_market_cap"].map(
            lambda x: f"{x:,.0f}" if pd.notna(x) else "-"
        )
        show["avg_price_change"] = show["avg_price_change"].map(
            lambda x: f"{x:.2f}%" if pd.notna(x) else "-"
        )

        st.dataframe(
            show[
                [
                    "symbol",
                    "chain",
                    "address",
                    "consistency_count",
                    "avg_volume",
                    "median_market_cap",
                    "avg_price_change",
                    "avg_price",
                ]
            ],
            use_container_width=True,
            height=420,
        )

        csv = result.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ 下载 CSV",
            csv,
            f"gmgn_trending_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
        )

        st.subheader("📈 市值 vs 成交量")
        fig, ax = plt.subplots(figsize=(10, 6))
        sc = ax.scatter(
            result["median_market_cap"],
            result["avg_volume"],
            s=result["consistency_count"] * 80,
            c=result["avg_price_change"],
            cmap="coolwarm",
            alpha=0.85,
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Median Market Cap")
        ax.set_ylabel("Average Volume")
        ax.set_title("Trending Tokens (bubble = consistency)")
        plt.colorbar(sc, ax=ax, label="Avg Price Change (%)")
        for _, row in result.iterrows():
            ax.annotate(
                str(row["symbol"])[:8],
                (row["median_market_cap"], row["avg_volume"]),
                fontsize=7,
                alpha=0.7,
            )
        st.pyplot(fig)

        with st.expander("📋 地址列表"):
            for _, row in result.iterrows():
                st.code(f"{row['symbol']}: {row['address']}")

else:
    st.info("👈 左侧调整参数后，点击「立即分析」。")
    st.markdown(
        """
### 说明
- **一致性**：代币同时出现在多个时间框架热榜（1m/5m/1h/6h/24h）的次数
- 次数越高，热度越持续
- 本工具使用非官方接口，云端可能被拦截；本地运行通常更稳定
"""
    )

if auto_refresh and should_run:
    time.sleep(90)
    st.rerun()
