"""
ログインページ

ユーザー名とパスワードでログインするフォームを提供する。
"""
import streamlit as st

from api_client import APIClient, APIError


def render() -> None:
    """ログインページを表示する"""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("📊 サブスクリプション管理")
        st.markdown("### ログイン")

        with st.form("login_form"):
            username = st.text_input("ユーザー名", placeholder="ユーザー名を入力")
            password = st.text_input(
                "パスワード", type="password", placeholder="パスワードを入力"
            )
            submitted = st.form_submit_button(
                "ログイン", use_container_width=True, type="primary"
            )

        if submitted:
            if not username or not password:
                st.error("ユーザー名とパスワードを入力してください")
                return

            client = APIClient()
            try:
                result = client.login(username, password)
                st.session_state.logged_in = True
                st.session_state.access_token = result["access_token"]
                st.session_state.refresh_token = result["refresh_token"]
                st.session_state.username = username
                st.rerun()
            except APIError as e:
                st.error(f"ログインに失敗しました: {e.message}")
            except Exception:
                st.error(
                    "サーバーに接続できません。バックエンドが起動しているか確認してください。"
                )
