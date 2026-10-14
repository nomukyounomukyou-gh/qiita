# 店舗システム障害の初動支援Agent：公開用サンプル

OCI Enterprise AI Responses API、file_search、関数ツール、Guardrailsを組み合わせたPythonアプリです。監視アラートから、根拠と未確認事項を含む初動対応票の下書きを作成します。店舗・アラート・連絡先はすべて架空です。

## 必要な環境

- Python 3.12（WebサーバはPython標準ライブラリ、依存パッケージは`requirements.txt`）
- OCI Generative AIのプロジェクトとUnstructured dataのベクトルストア
- 利用リージョンでResponses API、file_search、Function Callingに対応したモデル
- 同リージョンで利用可能なACTIVEのGuardrailsバージョン
- 初回の資料登録とCLI実行に使うOCI Compute。Instance Principalで認証します
- ブラウザ公開する場合はOCIR、Hosted Application、Hosted Deployment

OCIの利用料金が発生します。モデル・機能の利用可否とIAM設定は利用するテナンシ・リージョンで確認してください。

## 1. OCIリソースとIAMを用意する

OCIコンソールでGenerative AIのプロジェクトとベクトルストアを作成します。ベクトルストアはUnstructured dataを選択してください。

ビルド用ComputeのInstance Principalと、Hosted ApplicationのResource Principalが、利用するコンパートメント・プロジェクトに対して、Responses、Files、Vector Stores、Guardrailsを呼び出せるようにIAMポリシーを設定します。Hosted DeploymentからOCIRの画像を取得する権限も必要です。ユーザーのブラウザ認証とアプリからOCI APIを呼ぶ認証は別に設定します。

- [OCI Generative AIのIAMポリシー](https://docs.oracle.com/en-us/iaas/Content/generative-ai/iam-policies.htm)
- [ベクトルストアの作成](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-vector-store.htm)
- [Hosted Applicationの作成と認証設定](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm)
- [Guardrailsとバージョン](https://docs.oracle.com/en-us/iaas/Content/generative-ai/guardrails.htm)

この公開サンプルはInstance Principal / Resource Principalを利用します。手元のPCにOCI設定やAPI鍵を置いて実行する方式は実装していません。

## 2. 自分の設定を作成する

以下はOCI Compute上のLinuxで実行する例です。このディレクトリに移動してから実行してください。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp settings.example.json settings.json
```

`settings.json`の全プレースホルダーを、自分のリソースの値に置き換えてください。GuardrailsバージョンはACTIVEのものを選びます。`settings.json`はGit管理から除外しています。

## 3. 資料をベクトルストアへ登録する

```bash
python oci_vector_store_upload.py upload
python oci_vector_store_upload.py list
python oci_vector_store_upload.py search
```

登録対象は次の3ファイルだけです。アップロード後、索引が`completed`になるまで確認します。

- `pos_incident_runbook.md`
- `system_inventory_for_rag.md`
- `alerts_for_rag.md`

`demo_questions.md`は期待回答を含むため検索対象に入れません。元の`alerts.json`と`system_inventory.csv`は関数ツールが完全一致で照会します。

登録スクリプトはファイル内容のSHA-256をアップロード名に含め、同じ内容の再実行時には既存ファイルを再利用します。資料を変更して再登録した場合、旧版は自動削除しません。検索対象を最新に統一するには、OCI側で旧版を対象ベクトルストアから外してください。

## 4. CLIとWeb画面で実行する

```bash
python pos_incident_agent.py \
  --question 'ALT-20261008-001 の初動対応票を作ってください。' --show-trace
python web_app.py --host 127.0.0.1 --port 8080
```

Web画面はCompute内の`http://127.0.0.1:8080/`で確認します。別端末からは自分の環境のSSHポートフォワードを使ってください。`GET /health`と`GET /ready`はJSONで正常状態を返します。

入力のモデレーション・プロンプトインジェクション検出時はAgent実行を保留し、回答のモデレーション検出時は表示を保留します。PIIは通知して続行するデモ設定です。Guardrails API失敗時には処理を続けません。

## 5. コンテナ化してOCIRへPushする

`settings.json`を作成してからビルドします。画像には自分のリソースIDが含まれるため、公開するソースやZIPに`settings.json`を追加しないでください。秘密鍵や認証トークンは画像に入れません。

```bash
REGISTRY="<your-region-ocir-host>"
NAMESPACE="<your-tenancy-namespace>"
REPOSITORY="<your-repository>"
TAG="v1"
IMAGE="$REGISTRY/$NAMESPACE/$REPOSITORY:$TAG"

podman build --platform linux/amd64 --format docker -t "$IMAGE" .
podman login "$REGISTRY"
podman push "$IMAGE"
podman logout "$REGISTRY"
```

OCIRログインのユーザー名は自分のネームスペース・OCIユーザーに対応する形式を使用し、パスワード欄には自分のOCI Auth Tokenを入力します。このサンプルにはPush用アカウント情報を含めていません。

## 6. Hosted Deploymentを設定する

1. OCIコンソールのGenerative AIでApplicationを作成し、ブラウザ利用向けの認証方式を設定する。
2. ApplicationのDeploymentを作成し、OCIRリポジトリとタグを選択する。
3. Deploymentを有効化し、状態がActiveになるまで待つ。
4. ApplicationのInvokeエンドポイントを認証済みブラウザで開く。
5. サンプル質問1と、Guardrails用質問6を実行する。

コンテナは`0.0.0.0:8080`で起動し、`/health`と`/ready`を提供します。Deploymentの設定はOCIコンソールで行う想定で、Terraformによる自動作成は含みません。

- [コンテナ要件](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm)
- [Deploymentの作成](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-deployment.htm)
- [アーティファクトの追加](https://docs.oracle.com/en-us/iaas/Content/generative-ai/add-artifact.htm)
- [Applicationの呼び出し](https://docs.oracle.com/en-us/iaas/Content/generative-ai/use-applications.htm)

## 検証

```bash
python -m unittest discover -p 'test_*.py' -v
```

単体テストはネットワークをモックし、入力保留・サービスエラー時のAgent未実行、回答保留、台帳未登録時の扱い、サンプル質問と会話履歴を確認します。資料登録では登録対象3点と同じ内容のファイル再利用を確認します。実際のモデル・Guardrails・RAG検索は、自分のOCI環境で`demo_questions.md`を使って確認してください。

## 構成と制約

| ファイル | 用途 |
| --- | --- |
| `pos_incident_agent.py` | Responses APIと関数ツール、Guardrails前後判定 |
| `guardrails.py` | ApplyGuardrailsと保留・通知の判断 |
| `web_app.py`, `chat.html` | チャット画面とセッション履歴 |
| `oci_vector_store_upload.py` | 検索資料3点の登録、索引確認、検索 |
| `settings.example.json` | 個別環境値を含まない設定テンプレート |
| `alerts.json`, `system_inventory.csv` | 完全一致照会の架空データ |
| `pos_incident_runbook.md`, `*_for_rag.md` | 検索用の架空資料 |
| `demo_questions.md` | 通常・Guardrailsデモ質問 |
| `Dockerfile`, `requirements.txt` | ビルドと依存関係 |
| `.gitignore`, `.dockerignore` | ローカル設定・不要ファイルの除外 |
| `SHA256SUMS` | 同梱ファイルのSHA-256チェックサム |
| `test_guarded_agent.py`, `test_vector_store_upload.py` | 保留・表示・資料登録の回帰テスト |

データは固定スナップショットです。復旧操作、連絡、起票は実行しません。ブラウザ表示の履歴はsessionStorage、Agentの会話文脈はコンテナ内メモリに最大6往復・12時間保持します。複数レプリカでは文脈を共有しません。Guardrailsが検査するのは入力と最終回答で、取得した文書断片の個別検査は含みません。PII検出の対応言語と検出結果は公式仕様・利用バージョンで確認してください。

## 公開物に含めていないもの

個人の接続情報フォルダ、API鍵、SSH鍵、Wallet、known_hosts、実環境の設定JSON、リソースIDを含む配備結果、個別アカウントに依存するPush・サーバ操作スクリプトは同梱していません。架空データの連絡先は`example.com`です。
