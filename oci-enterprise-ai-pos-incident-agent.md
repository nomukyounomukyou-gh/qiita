# OCI Enterprise AIで「店舗システム障害の初動支援Agent」を作ってみた：RAG・台帳照会・Guardrailsを組み合わせる

## はじめに

店舗システムの障害アラートを受けたとき、担当者は監視情報だけでなく、システム台帳や運用手順書も確認します。ここで欲しいのは「もっともらしい復旧策」ではなく、**何が分かっていて、何が未確認かを分けた初動対応票**です。

ハッカソンの題材として、架空の小売企業「東都マート」を設定し、OCI Generative AIのEnterprise AI機能を使ってWebアプリを作りました。Pythonでアラートと台帳を完全一致照会し、Responses APIの `file_search` で運用手順書を検索します。入力と回答にはOCI Generative AI Guardrailsを適用します。

この記事の店舗、アラート、連絡先はすべて架空です。OCIのOCID、ベクトルストアID、レジストリ名、接続先などはプレースホルダーに置き換えています。

## サンプルコードと再現手順

記事で紹介する実装と架空資料をGitHubに公開しています。

- [サンプル一式：pos-incident-agent](https://github.com/nomukyounomukyou-gh/qiita/tree/main/pos-incident-agent)
- [セットアップ手順（README）](https://github.com/nomukyounomukyou-gh/qiita/blob/main/pos-incident-agent/README.md)
- [サンプル一式のZIP](https://github.com/nomukyounomukyou-gh/qiita/blob/main/downloads/pos-incident-agent.zip)

```bash
git clone https://github.com/nomukyounomukyou-gh/qiita.git
cd qiita/pos-incident-agent
```

ZIPをダウンロードして展開しても同じファイルを取得できます。公開物に実環境の接続設定や鍵は含みません。`settings.example.json`を`settings.json`へコピーし、自分で作成したOCIプロジェクト・ベクトルストア・モデル・Guardrailsバージョンを設定してください。

| 公開ファイル | 役割 |
| --- | --- |
| `pos_incident_agent.py` | Responses API、関数ツール、入力・回答のGuardrails |
| `guardrails.py` | ApplyGuardrails呼び出しと保留・通知の判定 |
| `web_app.py`, `chat.html` | チャット画面、セッション履歴、ヘルスチェック |
| `oci_vector_store_upload.py` | 検索資料の登録、索引完了確認、検索確認 |
| `settings.example.json` | 個別環境値を持たない設定テンプレート |
| `alerts.json`, `system_inventory.csv` | 関数ツールが照会する架空データ |
| `pos_incident_runbook.md`, `*_for_rag.md` | ベクトルストアに入れる架空資料 |
| `demo_questions.md` | 通常の障害対応とGuardrailsのデモ質問 |
| `Dockerfile`, `requirements.txt` | コンテナと依存関係 |
| `.gitignore`, `.dockerignore` | ローカル設定・不要ファイルの除外 |
| `test_guarded_agent.py`, `test_vector_store_upload.py` | 入力・回答保留と資料登録などの回帰テスト |
| `README.md` | OCIの準備からWeb配備までの再現手順 |

資料登録とCLI実行は、IAM権限を設定したOCI Compute上でInstance Principalを使う構成です。アプリはHosted ApplicationのResource Principalで動きます。自分のOCIリソースと認証・権限の準備が必要で、Deploymentの作成はREADMEに沿ってOCIコンソールで行います。

## 作ったもの

ブラウザでアラートIDを含む質問を送ると、Agentが次をまとめます。

- 対象システムと監視上の影響範囲
- 手順書に基づく暫定優先度とその根拠
- まだ確認できていない業務影響
- 一次連絡先とエスカレーション先の下書き

たとえば共通DBの接続失敗を32店舗で18分間観測したケースでは、手順書の条件に照らして「P1候補」とします。ただし、**32店舗で販売が停止したとは断定しません**。これは監視で異常を観測した店舗数であり、会計や決済が実際に止まった店舗数は別途確認が必要です。

構成は次のとおりです。

```text
ブラウザ
  │ 質問
  ▼
OCI Hosted Application（Python / 8080）
  ├─ 入力Guardrails：コンテンツモデレーション・プロンプトインジェクション
  ├─ OCI Responses API
  │    ├─ function: lookup_alert  → alerts.jsonをID完全一致で照会
  │    ├─ function: lookup_system → system_inventory.csvをID完全一致で照会
  │    └─ file_search             → ベクトルストアの運用手順書を検索
  └─ 回答Guardrails：コンテンツモデレーション
  │
  ▼
初動対応票・参照ツール・Guardrails判定を画面に表示
```

OCI Responses APIはOpenAI互換のリクエスト形式を使えますが、認証・エンドポイント・リソース管理はOCI側です。OCIの公式ドキュメントでも `file_search` と `function` がサポート対象として案内されています。[OCI Responses API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm)

## デモ資料をどう作ったか

最初にCodexで、次の3種類の架空データを作りました。

| ファイル | 内容 | Agentでの扱い |
| --- | --- | --- |
| `alerts.json` | アラートID、システムID、観測店舗数、継続時間など | `lookup_alert` で完全一致照会 |
| `system_inventory.csv` | システムID、担当部署、連絡先、手順書IDなど | `lookup_system` で完全一致照会 |
| `pos_incident_runbook.md` | P1～P3の判定条件、初動確認項目、連絡ルール | ベクトルストアから `file_search` |

アラートは次のような形です。実データではなく、2026年10月8日11:15時点を想定したスナップショットです。

```json
{
  "alert_id": "ALT-20261008-001",
  "system_id": "POS-CORE-DB",
  "duration_minutes": 18,
  "affected_store_count_observed": 32,
  "monitoring_severity": "critical",
  "evidence": "40店舗中32店舗でPOS共通DBへの接続失敗を観測。販売停止店舗数は未確認。"
}
```

手順書の判定条件も曖昧な文章にせず、検証しやすい形にしました。

| 暫定優先度 | 手順書の条件例 |
| --- | --- |
| P1候補 | POS共通基盤で10店舗以上の異常を観測し、15分以上継続 |
| P2候補 | P1に当たらない共通基盤の長時間障害、2～9店舗の異常など |
| P3候補 | 台帳登録済みの単一店舗POS端末で、継続10分未満 |
| 未判定 | 台帳に対象がない、または判定に必要な値が不足 |

監視レベルの `critical` と業務上のP1は別の概念です。優先度は `duration_minutes`、`affected_store_count_observed`、台帳上の対象区分から判定させます。

### 検索資料はMarkdownに変換した

ベクトルストアには手順書に加えて、台帳とアラートを検索用Markdownへ変換したものも登録しました。検証時、CSVをそのままベクトルストアへ登録すると `unsupported_file` が返ったためです。一方、**IDや数値の正確な照会には元のJSON/CSVを関数ツールで使います**。RAGだけに数値判定を任せない構成です。

ファイル登録はFiles APIへのアップロードと、ベクトルストアへの関連付けの2段階です。作成したベクトルストアは「Unstructured data」を選びました。[ベクトルストアの作成](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-vector-store.htm) / [ファイルの追加と検索](https://docs.oracle.com/en-us/iaas/Content/generative-ai/use-vector-store.htm)

作成済みベクトルストアに資料を登録するスクリプトは、次のように実行しました。変数には各自の値を入れてください。

```bash
REGION="<region>"
PROJECT_OCID="<project-ocid>"
COMPARTMENT_OCID="<compartment-ocid>"
VECTOR_STORE_ID="<vector-store-id>"

python3 oci_vector_store_upload.py upload \
  --region "$REGION" \
  --project-id "$PROJECT_OCID" \
  --compartment-id "$COMPARTMENT_OCID" \
  --store-id "$VECTOR_STORE_ID"
```

このスクリプトはOCI ComputeのInstance Principalで実行しました。登録後は索引状態が `completed` になったことと、検索APIで手順書のP1条件が返ることを確認しています。デモ質問集は期待回答を含むため、検索対象には入れていません。

## Agentの実装

設定ファイルはIDだけを保持し、秘密鍵やAuth Tokenをコンテナには入れません。以下は公開用に値を置き換えた例です。

```json
{
  "region": "<region>",
  "project_id": "<project-ocid>",
  "compartment_id": "<compartment-ocid>",
  "vector_store_id": "<vector-store-id>",
  "model": "<supported-model-id>",
  "guardrail_version": "<active-guardrail-version>"
}
```

Hosted Application内ではResource Principal、ビルド用のOCI Compute上ではInstance Principalを使用します。Responses APIへはOCI署名付きのHTTPリクエストを送っています。

```python
session = requests.Session()
if os.environ.get("OCI_RESOURCE_PRINCIPAL_VERSION"):
    session.auth = oci.auth.signers.get_resource_principals_signer()
else:
    session.auth = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

session.headers.update({
    "OpenAI-Project": settings["project_id"],
    "opc-compartment-id": settings["compartment_id"],
    "Content-Type": "application/json",
})
base = f"https://inference.generativeai.{settings['region']}.oci.oraclecloud.com/openai/v1"
```

ツールは `file_search` と2つの関数を渡します。`lookup_alert` と `lookup_system` はIDの完全一致だけを許し、台帳にないIDを似たレコードで補完しません。

```python
available_tools = [
    {"type": "file_search", "vector_store_ids": [settings["vector_store_id"]]},
    {
        "type": "function",
        "name": "lookup_alert",
        "description": "アラートIDを完全一致で検索する",
        "parameters": {
            "type": "object",
            "properties": {"alert_id": {"type": "string"}},
            "required": ["alert_id"],
            "additionalProperties": False,
        },
    },
    # lookup_system も同様に定義
]
```

モデルから `function_call` が返ったら、Python側でJSON/CSVを照会し、`call_id` を付けた `function_call_output` を次のResponses API呼び出しに渡します。この繰り返しで検索結果と台帳情報を合わせた回答を得ます。[OpenAI公式ドキュメントのFunction Callingの流れ](https://developers.openai.com/api/docs/guides/function-calling)

```python
for item in response["output"]:
    if item["type"] == "function_call":
        result = execute_call(item["name"], item["arguments"], alerts, systems)
        outputs.append({
            "type": "function_call_output",
            "call_id": item["call_id"],
            "output": json.dumps(result, ensure_ascii=False),
        })

next_request = {
    "model": settings["model"],
    "instructions": INSTRUCTIONS,
    "input": outputs,
    "tools": available_tools,
    "previous_response_id": response["id"],
    "store": True,
}
```

システム指示には「監視で観測した店舗数を販売停止店舗数と同一視しない」「手順書にない閾値を作らない」「復旧操作は提案・実行しない」と明記しました。出力はあくまで担当者が確認する下書きです。

## 入力と回答をGuardrailsで判定する

このアプリは `ApplyGuardrails` を入力前と回答後に呼びます。入力でコンテンツモデレーションまたはプロンプトインジェクションが検出された場合は、Responses APIを呼ばずに保留します。回答でコンテンツモデレーションが検出された場合は、画面に回答を表示しません。

```python
input_check = evaluate(question, settings, "input")
if input_check["blocked"]:
    return {"answer": "", "trace": [], "checks": [input_check]}

answer, trace = run_agent(question, settings, directory)
output_check = evaluate(answer, settings, "output")
if output_check["blocked"]:
    answer = ""
return {"answer": answer, "trace": trace, "checks": [input_check, output_check]}
```

PII検出はこのデモでは画面に通知して処理を続けます。架空の連絡先メールアドレスを含む通常回答まで止めないための設定です。**PII検出の対応言語は英語のみ**なので、日本語の個人情報保護をこれだけに任せる設計にはしていません。また、Guardrails APIが失敗した場合はAgent処理を続けずエラーにします。利用可能なGuardrailsバージョンを確認してから、設定値を固定しました。[OCI Generative AI Guardrails](https://docs.oracle.com/en-us/iaas/Content/generative-ai/guardrails.htm)

ここでチェックしているのは利用者の入力文と最終回答です。**ベクトルストアから取得した個々の文書断片を別途検査する実装ではありません**。検索資料自体の管理も必要です。

## コンテナ化してブラウザから使う

Web画面はPythonのHTTPサーバで実装し、`GET /` でチャット画面、`POST /` で質問を受けます。`GET /health` と `GET /ready` も用意しました。画面にはサンプル質問、会話、参照ツール、入力・回答それぞれのGuardrails判定を表示します。

Hosted Deployment向けコンテナは `linux/amd64` でビルドし、`0.0.0.0:8080` で待ち受けます。OCI公式ドキュメントにあるヘルスチェック要件に合わせました。[コンテナイメージの準備](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm)

```dockerfile
FROM docker.io/library/python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY pos_incident_agent.py guardrails.py web_app.py chat.html demo_questions.md \
     settings.json alerts.json system_inventory.csv ./
USER 10001:10001
EXPOSE 8080
CMD ["python", "web_app.py"]
```

OCI Container Registry（OCIR）へは、レジストリのホスト名・ネームスペース・リポジトリ名を各自の値に置き換えてPushします。認証にはOCIR用Auth Tokenを使い、スクリプトやイメージに埋め込まないようにしました。

```bash
REGISTRY="<your-region-ocir-host>"
NAMESPACE="<your-tenancy-namespace>"
REPOSITORY="<your-repository>"
TAG="v1"
IMAGE="$REGISTRY/$NAMESPACE/$REPOSITORY:$TAG"

podman build --platform linux/amd64 --format docker -t "$IMAGE" .
podman login "$REGISTRY"   # ユーザー名とOCIR Auth Tokenを対話入力
podman push "$IMAGE"
podman logout "$REGISTRY"
```

OCI Generative AIのApplicationとHosted Deploymentを作り、OCIRのリポジトリとタグを選んで有効化します。既存Deploymentを更新する場合は新しい画像タグをアーティファクトとして追加し、有効化します。アプリの認証方式とIAM権限は利用環境に合わせて設定してください。[Deploymentの作成](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-deployment.htm) / [アーティファクトの追加](https://docs.oracle.com/en-us/iaas/Content/generative-ai/add-artifact.htm)

## 動作確認

検証時には次の問いを用意しました。いずれも架空アラートです。

| 問い | 期待する動作 |
| --- | --- |
| `ALT-20261008-001` の初動対応票 | 共通DB、32店舗で異常観測、18分継続からP1候補。販売停止は未確認と明記 |
| `ALT-20261008-002` の優先度 | 台帳登録済みの単一端末、6分継続からP3候補 |
| `ALT-20261008-003` の優先度 | 対象システムが台帳にないため未判定。似たIDから担当者を推測しない |
| 指示の上書きを求める入力 | プロンプトインジェクションとして入力を保留 |

1件目の回答では `lookup_alert`、`lookup_system`、`file_search` が参照ツールとして表示され、P1候補の根拠と未確認事項が出ました。プロンプトインジェクション用の質問も検証時点のGuardrailsバージョンで保留されました。検出結果はバージョンや文面で変わるため、デモ前に同じ入力で再確認します。

通常質問で表示する内容の要約例です。文面はモデルの実行ごとに変わります。

```text
対象システム: POS-CORE-DB（POS共通DB）
監視上の影響: 40店舗中32店舗で接続失敗を観測。販売停止店舗数は未確認。
暫定優先度: P1候補
根拠: RB-POS-01 第2章（共通基盤、10店舗以上、15分以上）
次の確認: 店舗での決済・会計停止の有無、直近監視画面での継続状況
参照ツール: lookup_alert / lookup_system / file_search
```

## 運用に広げる前に

今回はアラートと台帳を**ファイルの固定スナップショット**としてコンテナに入れています。実運用では監視基盤や構成管理システムと連携し、鮮度と変更履歴を担保する必要があります。

また、画面の会話表示はブラウザの `sessionStorage`、Agentに渡す直近の会話文脈はコンテナ内メモリです。デモには十分ですが、アプリ再起動や複数レプリカでは会話文脈を共有できません。継続利用には永続化先を設計します。

初動対応票は人が確認する下書きにとどめ、連絡、起票、DBや端末の再起動は自動実行しません。この境界を明確にしたことで、ハッカソンの短時間でも、現場に見せて業務適用を議論できるデモになりました。

