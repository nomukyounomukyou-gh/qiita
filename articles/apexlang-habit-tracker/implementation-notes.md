# 実装と検証の記録

実行日: 2026-11-19（日本標準時）

## 確認できた結果

- ADBおよび作業サーバを停止状態から起動
- APEXの実バージョン: 26.1.6
- SQLcl: 26.3.0.0 / Build 26.3.0.260.1620
- 最終CSS更新時のSQLcl: 26.3.1.0 / Build 26.3.1.301.1413（作業途中のサーバ再起動後に更新を確認、こちらから更新操作は行っていない）
- Java最終実測: 21.0.13.1 LTS / build 21.0.13.1+4-LTS-22
- `scripts/01_schema.sql`でHT_HABIT、HT_CHECKIN、HT_APIの作成に成功、コンパイルエラーなし
- 新規アプリ110で`apex validate`成功、最終実行は警告なし
- 続けて`apex import`成功
- アプリ名Habit Pulse、別名HABIT-PULSEをデータディクショナリで確認
- KPI文字サイズと詳細入力欄のCSS改善を反映後、実機validate/import成功、習慣4件・記録28件・デモユーザー1件の保持を確認
- 通常のAPEX Accounts認証を維持

## 実行時の解析スキーマ不一致を修正

ログイン後にHTTP400となったため、`APEX_DEBUG_MESSAGES`のエラーを調査した。
根本原因はORA-00942で、アプリが利用する解析スキーマとテーブルを作成したスキーマが一致していなかった。
SQLclのインポート成功だけでは、実行時のSQLまで正しいとは判断できない。
アプリの解析スキーマを`APEX_APPLICATIONS.OWNER`で確認し、そのスキーマにDDLを適用して解消した。
読者はDDLを実行する接続先スキーマと、APEXの解析スキーマ（本記事の例ではHABIT_APP）を一致させる。

## 再現する実行順序

1. Oracle APEX 26.1以降とSQLcl 26.1.2以降を準備する
2. ワークスペースと解析スキーマを用意する
3. SQLclで対象スキーマへ接続する
4. `@scripts/01_schema.sql`を実行する（新規オブジェクト用。既存同名オブジェクトへ再実行しない）
5. `applications/habit-pulse/deployments/default.json`のHABIT_WORKSPACEを自分のワークスペース名へ変更する
6. `apex validate -input applications/habit-pulse -workspace HABIT_WORKSPACE`を実行する
7. Validation successfulを確認する
8. 未使用のアプリケーションIDを決め、`apex import -input applications/habit-pulse -workspace HABIT_WORKSPACE -schema HABIT_APP -id 110`を実行する
9. Import successfulを確認する
10. APEX App Builderから新規アプリを実行し、ワークスペースのアカウントでログインする

この例のHABIT_WORKSPACE、HABIT_APPは読者が置換する値。
同じIDのアプリがある場合は別の未使用IDを指定する。

## バージョン差分の実測

同梱スキルのscaffoldと実機コンパイラの間に表記差分があった。
実際に実機のエラーメッセージを確認し、次を修正した。

| 対象 | 修正前 | 実機で成功した表記 |
|---|---|---|
| ページ識別 | page宣言と別にpage属性 | page宣言のみ |
| ログイン用PL/SQLプロセス | plsqlCode | executeCode |
| 隠し項目のセッション保護 | checksumRequired-sessionLevel | checksumRequiredSessionLevel |
| ボタン | labelのみ | buttonNameとlabel |
| ボタン配置 | belowItems | bottom |
| 処理後の分岐 | pageOrUrlRedirect | pageOrUrl |
| IR列 | column、security.escapeSpecialCharacters | type: plainText、source.dataTypeのみ |

SQLcl付属コンパイラから属性を読み取るローカル監査ツールにも、実機で成功するMetricCard・chartの形式を誤検出する差分が残った。
ローカル監査の成功とは記載せず、実機の`apex validate`を成功判定とした。

## 初版の機能と制限

- 今日: KPI、現役習慣カード、詳細画面で実施・取消
- 振り返り: 過去7日間の達成率折れ線、習慣カード
- 習慣管理: 現役・アーカイブ済みを一緒に表示
- 履歴: 日付・習慣名・メモの読取専用インタラクティブレポート。APEX標準フィルターで絞り込む
- 詳細: 習慣登録・編集、今日のメモ、実施、取消、アーカイブ
- 白と深緑を基調とするCSS

連続日数とカレンダーヒートマップは初版未実装。
管理の現役/アーカイブ専用切替は初版未実装で、同一カード一覧に状態ラベルを表示する。
色の選択値は保存するが、初版カードは統一された深緑スタイルを使用する。
習慣別の累積実施数グラフは初版未実装。
これらは今後の改善として記事で扱う。

## UI確認の状況

通常のAPEX Accounts認証を使う撮影用End Userでログインし、登録、実施、取消、再読み込み後の保持、アーカイブ、履歴、必須入力を確認した。
7日間のグラフ値をSQLで照合し、390px幅で横にはみ出さないことも確認した。
記事には実機UIのスクリーンショット13枚を掲載している。
API層は実際の解析スキーマで8項目を再検証し、すべてPASSとなった。

## 後片付け

撮影用の4習慣・28記録、デモユーザー、関連セッション10件を削除し、対象データとユーザーが0件であることを確認した。
データの削除には公開スクリプト05_cleanup_demo.sqlのPREVIEW/DELETEを使用した。
一時資格情報と検証ファイル、誤ったスキーマに作成した空の中間HTオブジェクトを削除した。
作業サーバーとADBは停止状態を確認した。
アプリ110、解析スキーマのオブジェクト、公開用成果物は保持した。
