"""
ダッシュボードページ

月間支出サマリー、カテゴリ別円グラフ、支出推移グラフ、更新予定を表示する。
"""
import streamlit as st
import plotly.graph_objects as go

from api_client import APIClient, APIError

# カテゴリ別カラーパレット
CATEGORY_COLORS = {
    "動画配信": "#1976D2",
    "音楽": "#9C27B0",
    "ゲーム": "#F44336",
    "その他": "#4CAF50",
}


def _format_currency(amount) -> str:
    """金額を日本円フォーマット（¥xxx,xxx）で返す"""
    return f"¥{int(float(amount)):,}"


def _try_refresh(client: APIClient) -> bool:
    """トークンのリフレッシュを試みる。成功すればTrueを返す"""
    try:
        result = client.refresh_token(st.session_state.refresh_token)
        st.session_state.access_token = result["access_token"]
        st.session_state.refresh_token = result["refresh_token"]
        return True
    except APIError:
        return False


def _get_dashboard_data(client: APIClient) -> dict | None:
    """ダッシュボードデータを取得する（401時はトークンリフレッシュを試みる）"""
    try:
        return client.get_dashboard(st.session_state.access_token)
    except APIError as e:
        if e.status_code == 401 and _try_refresh(client):
            try:
                return client.get_dashboard(st.session_state.access_token)
            except APIError:
                pass
        return None


def render() -> None:
    """ダッシュボードページを表示する"""
    st.title("📊 ダッシュボード")

    client = APIClient()
    data = _get_dashboard_data(client)

    if data is None:
        st.error("データの取得に失敗しました。再度ログインしてください。")
        st.session_state.logged_in = False
        st.rerun()
        return

    # サマリーメトリクス（3列）
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="月間総支出", value=_format_currency(data["total_monthly_expense"]))
    with col2:
        st.metric(label="契約中サービス数", value=f"{data['subscription_count']} 件")
    with col3:
        renewal_count = len(data["upcoming_renewals"])
        st.metric(label="7日以内の更新予定", value=f"{renewal_count} 件")

    st.divider()

    # グラフ（2列）
    col_pie, col_line = st.columns(2)

    with col_pie:
        st.subheader("カテゴリ別内訳")
        category_data = data["category_breakdown"]
        if category_data:
            labels = list(category_data.keys())
            values = [float(v) for v in category_data.values()]
            colors = [CATEGORY_COLORS.get(label, "#999999") for label in labels]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker_colors=colors,
                textinfo="label+percent",
                hovertemplate="%{label}: ¥%{value:,.0f}<extra></extra>",
            )])
            fig.update_layout(
                showlegend=True,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("サブスクリプションがありません")

    with col_line:
        st.subheader("月別支出推移（12ヶ月）")
        trends = data["monthly_trends"]
        if trends:
            months = [f"{t['year']}/{t['month']:02d}" for t in trends]
            amounts = [float(t["total_amount"]) for t in trends]

            fig = go.Figure(data=[go.Scatter(
                x=months,
                y=amounts,
                mode="lines+markers",
                line=dict(color="#1976D2", width=2),
                marker=dict(size=8, color="#1976D2"),
                hovertemplate="%{x}: ¥%{y:,.0f}<extra></extra>",
            )])
            fig.update_layout(
                xaxis_title="月",
                yaxis_title="支出（円）",
                margin=dict(t=20, b=40, l=40, r=20),
                height=300,
                yaxis=dict(tickformat=",.0f"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("推移データがありません")

    # 更新予定一覧
    st.divider()
    st.subheader("🔔 7日以内の更新予定")
    renewals = data["upcoming_renewals"]
    if renewals:
        for r in renewals:
            st.markdown(
                f'<div class="renewal-alert">'
                f'📅 <b>{r["service_name"]}</b> — {r["next_renewal_date"]} '
                f'（{_format_currency(r["monthly_fee"])} / 月）'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("7日以内の更新予定はありません")
