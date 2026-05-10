"""
ログイン・新規登録ページ

ログインタブと新規登録タブを切り替えて表示する。
新規登録成功時は自動でログイン状態になる。
"""
import streamlit as st

from api_client import APIClient, APIError


def _login_user(username: str, access_token: str, refresh_token: str) -> None:
    """ログイン状態をセッションに記録してダッシュボードへ遷移する"""
    st.session_state.logged_in = True
    st.session_state.access_token = access_token
    st.session_state.refresh_token = refresh_token
    st.session_state.username = username
    st.rerun()


def _render_login_form(client: APIClient) -> None:
    """ログインフォーム"""
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

        try:
            result = client.login(username, password)
            _login_user(username, result["access_token"], result["refresh_token"])
        except APIError as e:
            st.error(f"ログインに失敗しました: {e.message}")
        except Exception:
            st.error(
                "サーバーに接続できません。バックエンドが起動しているか確認してください。"
            )


def _render_register_form(client: APIClient) -> None:
    """新規登録フォーム"""
    st.caption(
        "アカウント作成後は自動でログインしてダッシュボードに移動します。"
    )
    with st.form("register_form"):
        username = st.text_input(
            "ユーザー名 *",
            placeholder="3〜50文字（英数字・_・-）",
            max_chars=50,
        )
        password = st.text_input(
            "パスワード *",
            type="password",
            placeholder="8文字以上、大小英字と数字を含む",
        )
        password_confirm = st.text_input(
            "パスワード（確認用）*", type="password"
        )
        st.caption(
            "パスワード要件: 8文字以上、大文字英字・小文字英字・数字を各1文字以上含む"
        )
        submitted = st.form_submit_button(
            "登録する", use_container_width=True, type="primary"
        )

    if submitted:
        # クライアント側の最低限のチェック（サーバー側でも検証されるが UX のため事前確認）
        if not username or not password:
            st.error("すべての必須項目を入力してください")
            return
        if password != password_confirm:
            st.error("パスワードと確認用パスワードが一致しません")
            return

        try:
            result = client.register(username, password)
            st.success(f"「{username}」を登録しました。ログインします...")
            _login_user(username, result["access_token"], result["refresh_token"])
        except APIError as e:
            # サーバー側のバリデーション・重複エラーをそのまま表示
            st.error(f"登録に失敗しました: {e.message}")
        except Exception:
            st.error(
                "サーバーに接続できません。バックエンドが起動しているか確認してください。"
            )


def render() -> None:
    """ログイン・新規登録ページを表示する"""
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("📊 サブスクリプション管理")

        client = APIClient()
        tab_login, tab_register = st.tabs(["ログイン", "新規登録"])

        with tab_login:
            _render_login_form(client)

        with tab_register:
            _render_register_form(client)
