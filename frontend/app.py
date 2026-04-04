"""
Streamlitアプリケーションのエントリポイント

セッション管理とページルーティングを担当する。
起動コマンド: streamlit run frontend/app.py
"""
import streamlit as st

# ページ設定（最初のStreamlitコマンドである必要がある）
st.set_page_config(
    page_title="サブスクリプション管理",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pages import dashboard, login, subscriptions  # noqa: E402


def _apply_styles() -> None:
    """Material Design風カスタムCSSを適用する"""
    st.markdown(
        """
        <style>
        /* メトリクスカード */
        [data-testid="stMetric"] {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            border-left: 4px solid #1976D2;
        }
        /* 更新予定アラート */
        .renewal-alert {
            background-color: #fff8e1;
            border-left: 4px solid #FFA000;
            padding: 10px 14px;
            border-radius: 4px;
            margin: 4px 0;
        }
        /* ダークモード対応 */
        @media (prefers-color-scheme: dark) {
            [data-testid="stMetric"] {
                background-color: #1e1e1e;
            }
            .renewal-alert {
                background-color: #3d2e00;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_session_state() -> None:
    """セッション状態を初期化する（未設定のキーのみ）"""
    defaults = {
        "logged_in": False,
        "access_token": None,
        "refresh_token": None,
        "username": None,
        "current_page": "ダッシュボード",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_sidebar() -> None:
    """サイドバーのナビゲーションとログアウトボタンを表示する"""
    with st.sidebar:
        st.title("📊 サブスク管理")
        st.markdown(f"👤 **{st.session_state.username}**")
        st.divider()

        page = st.radio(
            "ページ",
            ["ダッシュボード", "サブスクリプション管理"],
            key="nav_radio",
        )
        st.session_state.current_page = page

        st.divider()
        if st.button("ログアウト", use_container_width=True):
            from api_client import APIClient, APIError

            client = APIClient()
            try:
                client.logout(st.session_state.access_token)
            except (APIError, Exception):
                pass
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def main() -> None:
    """メインアプリケーションのエントリポイント"""
    _apply_styles()
    _init_session_state()

    if not st.session_state.logged_in:
        login.render()
    else:
        _render_sidebar()
        if st.session_state.current_page == "ダッシュボード":
            dashboard.render()
        else:
            subscriptions.render()


main()
