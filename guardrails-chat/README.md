# OCI Generative AI Guardrails 検証チャット

OCI Generative AIの`ApplyGuardrails` APIを使い、テキストと画像の判定結果をブラウザで確認するローカルデモです。LLMによる回答生成はしません。

## 必要なもの

- Node.js（追加のnpmパッケージは不要）
- OCIのAPI署名用秘密鍵と、対応する公開鍵を登録したOCIユーザー
- 対象コンパートメントでOCI Generative AIの推論APIを利用できる権限

## 設定と起動

環境変数には自分のOCI環境の値を設定します。秘密鍵やOCIDをソースコードへ書き込まないでください。

PowerShellの例:

```powershell
$env:OCI_REGION = '<YOUR_OCI_REGION>'
$env:OCI_TENANCY_OCID = '<YOUR_TENANCY_OCID>'
$env:OCI_USER_OCID = '<YOUR_USER_OCID>'
$env:OCI_COMPARTMENT_OCID = '<YOUR_COMPARTMENT_OCID>'
$env:OCI_PRIVATE_KEY_PATH = '<PATH_TO_PRIVATE_KEY_PEM>'
$env:OCI_FINGERPRINT = '<YOUR_API_KEY_FINGERPRINT>'

node .\guardrails-chat\server.js
```

ブラウザで`http://127.0.0.1:8787/`を開きます。`OCI_FINGERPRINT`を省略した場合は、秘密鍵から公開鍵のフィンガープリントを算出します。`PORT`で待受ポートを変更できます。サーバーは`127.0.0.1`で待ち受けます。

## 使い方

テキストを入力し、判定機能とGuardrailsバージョンを選んで送信します。バージョン候補は`ListGuardrailVersions` APIから取得します。PNG/JPEG/WebP画像を1枚、4MBまで添付できます。画像判定にはGuardrails `1.1.0`以降とContent Moderationが必要です。APIレスポンスの詳細は判定カードから展開できます。

UIに表示される履歴はブラウザでページを開いている間だけ保持します。サーバーは入力や画像を保存しませんが、判定のためOCIへ送信します。実データを試す際は送信してよい情報だけを入力してください。

## ファイル

| ファイル | 役割 |
| --- | --- |
| `index.html` | チャット形式の画面 |
| `styles.css` | 画面のスタイル |
| `app.js` | 入力、画像添付、判定結果の表示 |
| `server.js` | 静的ファイル配信とOCI API署名・中継 |

このリポジトリに`connection_info`や秘密鍵を含めないでください。認証情報は環境変数からのみ読み込みます。

## 参考

- [Guardrails for OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/guardrails.htm)
- [ApplyGuardrails API](https://docs.oracle.com/en-us/iaas/api/#/en/generativeaiinference/20231130/Guardrails/ApplyGuardrails)
