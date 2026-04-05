"""
サブスクリプション管理ページ

サブスクリプションの一覧表示・新規追加・編集・削除を提供する。
"""
from datetime import date

import streamlit as st

from api_client import APIClient, APIError

# SubscriptionCategory の値（API送受信で使用する日本語文字列）
CATEGORIES = ["動画配信", "音楽", "ゲーム", "その他"]

# プルダウン用サービス一覧（カテゴリ別）
SUBSCRIPTION_SERVICES: list[str] = [
    # 動画配信
    "Netflix",
    "Amazon Prime Video",
    "Disney+",
    "Hulu",
    "U-NEXT",
    "FOD",
    "DAZN",
    "Apple TV+",
    "YouTube Premium",
    "ABEMAプレミアム",
    "NHKオンデマンド",
    "Paravi",
    # 音楽
    "Spotify",
    "Apple Music",
    "Amazon Music Unlimited",
    "YouTube Music",
    "LINE MUSIC",
    "AWA",
    "mora qualitas",
    "RecMusic",
    # ゲーム
    "Nintendo Switch Online",
    "PlayStation Plus",
    "Xbox Game Pass",
    "Steam",
    "Epic Games",
    # 読書・マンガ・ニュース
    "Kindle Unlimited",
    "コミックシーモア",
    "ピッコマ",
    "マンガBANG!",
    "NewsPicks",
    "日経電子版",
    "Dマガジン",
    # クラウドストレージ
    "iCloud+",
    "Google One",
    "Dropbox",
    "OneDrive",
    "Box",
    # ソフトウェア・ツール
    "Adobe Creative Cloud",
    "Microsoft 365",
    "Notion",
    "Figma",
    "Canva Pro",
    "ChatGPT Plus",
    "GitHub Copilot",
    "Slack",
    "Zoom",
    # その他
    "楽天マガジン",
    "セゾンプレミアム",
    "Amazon定期おトク便",
    # カスタム入力用
    "その他（直接入力）",
]

_CUSTOM_OPTION = "その他（直接入力）"


def _format_currency(amount) -> str:
    """金額を日本円フォーマット（¥xxx,xxx）で返す"""
    return f"¥{int(float(amount)):,}"


def _get_subscriptions(client: APIClient) -> list | None:
    """サブスクリプション一覧を取得する（401時はトークンリフレッシュを試みる）"""
    try:
        return client.get_subscriptions(st.session_state.access_token)
    except APIError as e:
        if e.status_code == 401:
            try:
                result = client.refresh_token(st.session_state.refresh_token)
                st.session_state.access_token = result["access_token"]
                st.session_state.refresh_token = result["refresh_token"]
                return client.get_subscriptions(st.session_state.access_token)
            except APIError:
                pass
        return None


def _render_add_form(client: APIClient) -> None:
    """新規サブスクリプション追加フォームを表示する"""
    with st.expander("➕ 新規サブスクリプションを追加", expanded=False):
        with st.form("add_subscription_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                selected_service = st.selectbox(
                    "サービス名 *",
                    SUBSCRIPTION_SERVICES,
                    index=None,
                    placeholder="サービスを選択または入力...",
                )
                # 「その他（直接入力）」選択時はテキスト入力を表示
                if selected_service == _CUSTOM_OPTION:
                    service_name = st.text_input("サービス名を入力 *", max_chars=100)
                else:
                    service_name = selected_service or ""
                monthly_fee = st.number_input(
                    "月額料金（円）*", min_value=1, step=1, value=980
                )
                category = st.selectbox("カテゴリ *", CATEGORIES)
            with col2:
                start_date = st.date_input("契約開始日 *", value=date.today())
                next_renewal_date = st.date_input("次回更新日（省略可）", value=None)
                memo = st.text_area("メモ", max_chars=500, height=80)

            submitted = st.form_submit_button("追加する", type="primary")

        if submitted:
            if not service_name:
                st.error("サービス名を入力してください")
                return

            data = {
                "service_name": service_name,
                "monthly_fee": float(monthly_fee),
                "category": category,
                "start_date": str(start_date),
                "next_renewal_date": str(next_renewal_date) if next_renewal_date else None,
                "memo": memo if memo else None,
            }
            try:
                client.create_subscription(st.session_state.access_token, data)
                st.success(f"「{service_name}」を追加しました")
                st.rerun()
            except APIError as e:
                st.error(f"追加に失敗しました: {e.message}")


def _render_edit_form(client: APIClient, subscriptions: list) -> None:
    """サブスクリプション編集・削除フォームを表示する"""
    with st.expander("✏️ 編集・削除", expanded=False):
        if not subscriptions:
            st.info("編集できるサブスクリプションがありません")
            return

        names = [s["service_name"] for s in subscriptions]
        selected_name = st.selectbox("対象サービスを選択", names, key="edit_select")
        selected = next(s for s in subscriptions if s["service_name"] == selected_name)

        tab_edit, tab_delete = st.tabs(["編集", "削除"])

        with tab_edit:
            with st.form("edit_subscription_form"):
                col1, col2 = st.columns(2)
                category_value = selected["category"]
                category_idx = CATEGORIES.index(category_value) if category_value in CATEGORIES else 0
                with col1:
                    # 既存のサービス名がリストにあればそれを初期選択、なければ「その他」
                    current_name = selected["service_name"]
                    if current_name in SUBSCRIPTION_SERVICES and current_name != _CUSTOM_OPTION:
                        service_default_idx = SUBSCRIPTION_SERVICES.index(current_name)
                    else:
                        service_default_idx = SUBSCRIPTION_SERVICES.index(_CUSTOM_OPTION)
                    selected_service = st.selectbox(
                        "サービス名",
                        SUBSCRIPTION_SERVICES,
                        index=service_default_idx,
                    )
                    if selected_service == _CUSTOM_OPTION:
                        service_name = st.text_input(
                            "サービス名を入力", value=current_name if service_default_idx == SUBSCRIPTION_SERVICES.index(_CUSTOM_OPTION) else "", max_chars=100
                        )
                    else:
                        service_name = selected_service or current_name
                    monthly_fee = st.number_input(
                        "月額料金（円）",
                        min_value=1,
                        step=1,
                        value=int(float(selected["monthly_fee"])),
                    )
                    category = st.selectbox("カテゴリ", CATEGORIES, index=category_idx)
                with col2:
                    start_date = st.date_input(
                        "契約開始日", value=date.fromisoformat(selected["start_date"])
                    )
                    next_renewal_date = st.date_input(
                        "次回更新日",
                        value=date.fromisoformat(selected["next_renewal_date"]),
                    )
                    memo = st.text_area(
                        "メモ", value=selected.get("memo") or "", max_chars=500, height=80
                    )

                submitted = st.form_submit_button("更新する", type="primary")

            if submitted:
                data = {
                    "service_name": service_name,
                    "monthly_fee": float(monthly_fee),
                    "category": category,
                    "start_date": str(start_date),
                    "next_renewal_date": str(next_renewal_date),
                    "memo": memo if memo else None,
                }
                try:
                    client.update_subscription(
                        st.session_state.access_token, selected["id"], data
                    )
                    st.success(f"「{service_name}」を更新しました")
                    st.rerun()
                except APIError as e:
                    st.error(f"更新に失敗しました: {e.message}")

        with tab_delete:
            st.warning(f"「{selected_name}」を削除しますか？この操作は取り消せません。")
            if st.button("削除する", type="secondary", key="delete_btn"):
                try:
                    client.delete_subscription(
                        st.session_state.access_token, selected["id"]
                    )
                    st.success(f"「{selected_name}」を削除しました")
                    st.rerun()
                except APIError as e:
                    st.error(f"削除に失敗しました: {e.message}")


def render() -> None:
    """サブスクリプション管理ページを表示する"""
    st.title("📋 サブスクリプション管理")

    client = APIClient()
    subscriptions = _get_subscriptions(client)

    if subscriptions is None:
        st.error("データの取得に失敗しました。再度ログインしてください。")
        st.session_state.logged_in = False
        st.rerun()
        return

    # 一覧テーブル
    if subscriptions:
        st.subheader(f"契約中サービス（{len(subscriptions)} 件）")
        display_data = [
            {
                "サービス名": s["service_name"],
                "月額料金": _format_currency(s["monthly_fee"]),
                "カテゴリ": s["category"],
                "次回更新日": s["next_renewal_date"],
                "メモ": s.get("memo") or "",
            }
            for s in subscriptions
        ]
        st.dataframe(display_data, use_container_width=True, hide_index=True)
    else:
        st.info("サブスクリプションが登録されていません。以下から追加してください。")

    st.divider()
    _render_add_form(client)
    _render_edit_form(client, subscriptions)
