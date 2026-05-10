#!/usr/bin/env bash
# ================================================================
# load_prod_env.sh
#
# 本番環境のDB接続文字列を AWS SSM Parameter Store から取得し、
# 現在のシェルの DATABASE_URL 環境変数にセットする。
#
# 使い方:
#   source ./scripts/load_prod_env.sh <role>
#
#   <role>:
#     readonly  - SELECT のみ（デバッグ・閲覧用）
#     app       - CRUD のみ（DDL不可、アプリ実行用）
#     owner     - DDL 可能（マイグレーション用）
#     postgres  - スーパーユーザー（緊急時のみ）
#                 ALLOW_POSTGRES=1 を併せて指定する必要がある:
#                   ALLOW_POSTGRES=1 source ./scripts/load_prod_env.sh postgres
#
# 注意:
#   このスクリプトは "source" で読み込む必要がある。
#   直接実行すると親シェルに環境変数を設定できない。
#
#   使い終わったら必ず unload_prod_env.sh で環境変数をクリアすること。
# ================================================================

# --- 定数 ---
AWS_PROFILE_NAME="subscription-app"
AWS_REGION="ap-northeast-1"
SSM_PATH_PREFIX="/subscription-app/prod/database-url"

# --- source 経由で実行されているかを確認 ---
# BASH_SOURCE[0] と $0 が同じなら直接実行されている
# 直接実行だと親シェルに export できないので止める
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "エラー: このスクリプトは source で読み込んでください" >&2
    echo "" >&2
    echo "  正しい使い方:" >&2
    echo "    source ./scripts/load_prod_env.sh <role>" >&2
    echo "" >&2
    echo "  間違った使い方:" >&2
    echo "    ./scripts/load_prod_env.sh <role>     # ← 親シェルに反映されない" >&2
    exit 1
fi

# --- 引数チェック ---
# source 経由なので exit ではなく return を使う（親シェルを終了させない）
if [[ $# -ne 1 ]]; then
    echo "エラー: ロール名を1つ指定してください" >&2
    echo "" >&2
    echo "  使い方: source ./scripts/load_prod_env.sh <role>" >&2
    echo "  <role>: readonly | app | owner | postgres" >&2
    return 1
fi

_role="$1"

case "${_role}" in
    readonly|app|owner|postgres)
        ;;
    *)
        echo "エラー: 不正なロール名 '${_role}'" >&2
        echo "" >&2
        echo "  許可されているロール名:" >&2
        echo "    readonly  - SELECT のみ" >&2
        echo "    app       - CRUD のみ" >&2
        echo "    owner     - DDL 可能" >&2
        echo "    postgres  - スーパーユーザー（緊急時のみ・ALLOW_POSTGRES=1 必須）" >&2
        unset _role
        return 1
        ;;
esac

# --- postgres ロールの安全装置 ---
# postgres は強権限なので、誤って常用しないよう ALLOW_POSTGRES=1 を必須化する。
# 「明示的にこのロールを使う意思がある」ことを確認するためのフェイルセーフ。
if [[ "${_role}" == "postgres" ]] && [[ "${ALLOW_POSTGRES:-}" != "1" ]]; then
    echo "エラー: postgres ロールは緊急時のみ使用できます" >&2
    echo "" >&2
    echo "  postgres は Supabase スーパーユーザーで強権限のため、" >&2
    echo "  通常のオペレーション（CRUD・通常のDDL）には使用しないでください。" >&2
    echo "  使うべきケース: 既存テーブルの所有権変更など、subscription_owner では" >&2
    echo "                  実行できない管理操作のみ。" >&2
    echo "" >&2
    echo "  どうしても必要な場合は、明示的に ALLOW_POSTGRES=1 を指定してください:" >&2
    echo "    ALLOW_POSTGRES=1 source ./scripts/load_prod_env.sh postgres" >&2
    unset _role
    return 1
fi

# --- AWS CLI が利用可能か確認 ---
if ! command -v aws >/dev/null 2>&1; then
    echo "エラー: AWS CLI がインストールされていません" >&2
    echo "  インストール方法: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
    unset _role
    return 1
fi

# --- AWS プロファイルの存在チェック ---
if ! aws configure list-profiles 2>/dev/null | grep -qx "${AWS_PROFILE_NAME}"; then
    echo "エラー: AWS プロファイル '${AWS_PROFILE_NAME}' が見つかりません" >&2
    echo "" >&2
    echo "  以下のコマンドでプロファイルを設定してください:" >&2
    echo "    aws configure --profile ${AWS_PROFILE_NAME}" >&2
    echo "" >&2
    echo "  入力する値:" >&2
    echo "    AWS Access Key ID:     IAM ユーザー subscription-app-admin のアクセスキー" >&2
    echo "    AWS Secret Access Key: IAM ユーザーのシークレットキー" >&2
    echo "    Default region name:   ${AWS_REGION}" >&2
    echo "    Default output format: json" >&2
    unset _role
    return 1
fi

# --- AWS 認証情報の動作確認（sts get-caller-identity）---
echo "AWS 認証情報を確認中... (profile=${AWS_PROFILE_NAME})"
if ! aws sts get-caller-identity \
        --profile "${AWS_PROFILE_NAME}" \
        --region "${AWS_REGION}" \
        >/dev/null 2>&1; then
    echo "エラー: AWS 認証に失敗しました" >&2
    echo "  以下を確認してください:" >&2
    echo "    1. アクセスキーが有効か（無効化・ローテーション後に古いキーを使っていないか）" >&2
    echo "    2. ~/.aws/credentials の [${AWS_PROFILE_NAME}] セクションが正しいか" >&2
    echo "    3. ネットワーク接続" >&2
    unset _role
    return 1
fi

# --- SSM から接続文字列を取得 ---
_ssm_param_name="${SSM_PATH_PREFIX}-${_role}"
echo "SSM Parameter Store から接続文字列を取得中... (${_ssm_param_name})"

# --with-decryption: SecureString を復号して取得
# --query: 値だけを取り出す
# --output text: JSON ではなく生の文字列で出力
_db_url=$(aws ssm get-parameter \
    --name "${_ssm_param_name}" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --profile "${AWS_PROFILE_NAME}" \
    --region "${AWS_REGION}" \
    2>/dev/null)
_aws_exit_code=$?

if [[ ${_aws_exit_code} -ne 0 ]] || [[ -z "${_db_url}" ]]; then
    echo "エラー: SSM パラメータの取得に失敗しました" >&2
    echo "  パラメータ名: ${_ssm_param_name}" >&2
    echo "" >&2
    echo "  確認方法:" >&2
    echo "    1. パラメータが存在するか:" >&2
    echo "       aws ssm describe-parameters \\" >&2
    echo "         --parameter-filters Key=Name,Values=${_ssm_param_name} \\" >&2
    echo "         --profile ${AWS_PROFILE_NAME} --region ${AWS_REGION}" >&2
    echo "" >&2
    echo "    2. IAM ポリシーで ssm:GetParameter / kms:Decrypt が許可されているか" >&2
    unset _role _ssm_param_name _db_url _aws_exit_code
    return 1
fi

# --- 取得値の妥当性チェック ---
# postgresql:// で始まることを確認（誤ったパラメータを引いていないかの保険）
if [[ "${_db_url}" != postgresql://* ]]; then
    echo "エラー: 取得した値が postgresql:// で始まっていません" >&2
    echo "  パラメータ名: ${_ssm_param_name}" >&2
    echo "  SSM の値が正しい接続文字列になっているか確認してください" >&2
    unset _role _ssm_param_name _db_url _aws_exit_code
    return 1
fi

# --- DATABASE_URL にセット ---
export DATABASE_URL="${_db_url}"

# --- 完了メッセージ ---
# postgres ロールは緊急時のみの使用なので、警告色で目立たせる
_host_only=$(echo "${_db_url}" | sed -E 's|^postgresql://[^@]+@([^/]+)/.*$|\1|')

echo ""
if [[ "${_role}" == "postgres" ]]; then
    echo "⚠️  WARNING: postgres スーパーユーザーで接続します"
    echo "⚠️  DATABASE_URL を設定しました（ロール: ${_role}）← 緊急時のみ"
    echo ""
    echo "  パラメータ名: ${_ssm_param_name}"
    echo "  接続先ホスト: ${_host_only}"
    echo ""
    echo "  ⚠️  postgres は強権限です。最小限の管理操作だけ実行し、"
    echo "  ⚠️  作業が終わったら すぐに 以下で環境変数をクリアしてください:"
    echo "    source ./scripts/unload_prod_env.sh"
else
    echo "✓ DATABASE_URL を設定しました（ロール: ${_role}）"
    echo ""
    echo "  パラメータ名: ${_ssm_param_name}"
    echo "  接続先ホスト: ${_host_only}"
    echo ""
    echo "  ⚠ 使い終わったら必ず以下で環境変数をクリアしてください:"
    echo "    source ./scripts/unload_prod_env.sh"
fi
echo ""

# --- 一時変数のクリーンアップ ---
# DATABASE_URL は残すが、ローカル変数は親シェルに残さない
unset _role _ssm_param_name _db_url _aws_exit_code _host_only
