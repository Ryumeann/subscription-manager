"""
サブスクリプション管理ページ

サブスクリプションの一覧表示・新規追加・編集・削除を提供する。
"""
from datetime import date

import streamlit as st

from api_client import APIClient, APIError

# SubscriptionCategory の値（API送受信で使用する日本語文字列）
CATEGORIES = ["動画配信", "音楽", "ゲーム", "クラウド", "ツール", "メディア", "その他"]

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

# サービス名 → カテゴリのマッピング
SERVICE_CATEGORY_MAP: dict[str, str] = {
    # 動画配信
    "Netflix": "動画配信",
    "Amazon Prime Video": "動画配信",
    "Disney+": "動画配信",
    "Hulu": "動画配信",
    "U-NEXT": "動画配信",
    "FOD": "動画配信",
    "DAZN": "動画配信",
    "Apple TV+": "動画配信",
    "YouTube Premium": "動画配信",
    "ABEMAプレミアム": "動画配信",
    "NHKオンデマンド": "動画配信",
    "Paravi": "動画配信",
    # 音楽
    "Spotify": "音楽",
    "Apple Music": "音楽",
    "Amazon Music Unlimited": "音楽",
    "YouTube Music": "音楽",
    "LINE MUSIC": "音楽",
    "AWA": "音楽",
    "mora qualitas": "音楽",
    "RecMusic": "音楽",
    # ゲーム
    "Nintendo Switch Online": "ゲーム",
    "PlayStation Plus": "ゲーム",
    "Xbox Game Pass": "ゲーム",
    "Steam": "ゲーム",
    "Epic Games": "ゲーム",
    # メディア（読書・マンガ・ニュース）
    "Kindle Unlimited": "メディア",
    "コミックシーモア": "メディア",
    "ピッコマ": "メディア",
    "マンガBANG!": "メディア",
    "NewsPicks": "メディア",
    "日経電子版": "メディア",
    "Dマガジン": "メディア",
    "楽天マガジン": "メディア",
    # クラウド
    "iCloud+": "クラウド",
    "Google One": "クラウド",
    "Dropbox": "クラウド",
    "OneDrive": "クラウド",
    "Box": "クラウド",
    # ツール
    "Adobe Creative Cloud": "ツール",
    "Microsoft 365": "ツール",
    "Notion": "ツール",
    "Figma": "ツール",
    "Canva Pro": "ツール",
    "ChatGPT Plus": "ツール",
    "GitHub Copilot": "ツール",
    "Slack": "ツール",
    "Zoom": "ツール",
    # その他
    "セゾンプレミアム": "その他",
    "Amazon定期おトク便": "その他",
}


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
        # サービス名はフォーム外に置くことでカテゴリ自動連動を実現する
        selected_service = st.selectbox(
            "サービス名 *",
            SUBSCRIPTION_SERVICES,
            index=None,
            placeholder="サービスを選択または入力...",
            key="add_service_select",
        )
        if selected_service == _CUSTOM_OPTION:
            service_name = st.text_input(
                "サービス名を入力 *", max_chars=100, key="add_custom_name"
            )
            auto_category_idx = CATEGORIES.index("その他")
        else:
            service_name = selected_service or ""
            detected = SERVICE_CATEGORY_MAP.get(service_name, "その他")
            auto_category_idx = CATEGORIES.index(detected)

        with st.form("add_subscription_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                monthly_fee = st.number_input(
                    "月額料金（円）*", min_value=1, step=1, value=980
                )
                category = st.selectbox("カテゴリ *", CATEGORIES, index=auto_category_idx)
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
            # サービス名はフォーム外に置くことでカテゴリ自動連動を実現する
            current_name = selected["service_name"]
            if current_name in SUBSCRIPTION_SERVICES and current_name != _CUSTOM_OPTION:
                edit_service_default_idx = SUBSCRIPTION_SERVICES.index(current_name)
            else:
                edit_service_default_idx = SUBSCRIPTION_SERVICES.index(_CUSTOM_OPTION)

            edit_selected_service = st.selectbox(
                "サービス名",
                SUBSCRIPTION_SERVICES,
                index=edit_service_default_idx,
                key="edit_service_select",
            )
            if edit_selected_service == _CUSTOM_OPTION:
                edit_service_name = st.text_input(
                    "サービス名を入力",
                    value=current_name if edit_service_default_idx == SUBSCRIPTION_SERVICES.index(_CUSTOM_OPTION) else "",
                    max_chars=100,
                    key="edit_custom_name",
                )
                edit_auto_category_idx = CATEGORIES.index("その他")
            else:
                edit_service_name = edit_selected_service or current_name
                detected = SERVICE_CATEGORY_MAP.get(edit_service_name, selected["category"])
                edit_auto_category_idx = CATEGORIES.index(detected) if detected in CATEGORIES else 0

            with st.form("edit_subscription_form"):
                col1, col2 = st.columns(2)
                with col1:
                    monthly_fee = st.number_input(
                        "月額料金（円）",
                        min_value=1,
                        step=1,
                        value=int(float(selected["monthly_fee"])),
                    )
                    category = st.selectbox("カテゴリ", CATEGORIES, index=edit_auto_category_idx)
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
                    "service_name": edit_service_name,
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
                    st.success(f"「{edit_service_name}」を更新しました")
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
