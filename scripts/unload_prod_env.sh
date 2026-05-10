#!/usr/bin/env bash
# ================================================================
# unload_prod_env.sh
#
# load_prod_env.sh で設定した本番環境関連の環境変数を全て解除する。
# 隔離運用（秘密情報を扱った後の片付け）のために使用する。
#
# 使い方:
#   source ./scripts/unload_prod_env.sh
#
# 注意:
#   このスクリプトも "source" で読み込む必要がある。
#   直接実行すると親シェルの環境変数が変更されない。
# ================================================================

# --- source 経由で実行されているかを確認 ---
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "エラー: このスクリプトは source で読み込んでください" >&2
    echo "" >&2
    echo "  正しい使い方:" >&2
    echo "    source ./scripts/unload_prod_env.sh" >&2
    exit 1
fi

# --- 解除対象の環境変数一覧 ---
# DATABASE_URL: load_prod_env.sh で設定する本番DB接続文字列
# その他は本番運用で扱う可能性のある関連変数（念のため一括クリア）
_vars_to_unset=(
    DATABASE_URL
    SECRET_KEY
    ALGORITHM
    ACCESS_TOKEN_EXPIRE_HOURS
    REFRESH_TOKEN_EXPIRE_DAYS
    APP_ENV
    DEBUG
    CORS_ALLOWED_ORIGINS
)

# --- クリア前にどの変数が設定されていたかを記録 ---
_cleared_vars=()
for _var in "${_vars_to_unset[@]}"; do
    if [[ -n "${!_var:-}" ]]; then
        _cleared_vars+=("${_var}")
    fi
    unset "${_var}"
done

# --- 完了メッセージ ---
echo ""
echo "✓ 本番環境関連の環境変数をクリアしました"
echo ""
if [[ ${#_cleared_vars[@]} -gt 0 ]]; then
    echo "  クリアした変数:"
    for _var in "${_cleared_vars[@]}"; do
        echo "    - ${_var}"
    done
else
    echo "  （クリア対象の環境変数は設定されていませんでした）"
fi
echo ""

# --- 一時変数のクリーンアップ ---
unset _vars_to_unset _cleared_vars _var
