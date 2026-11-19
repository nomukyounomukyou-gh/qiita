# Habit Pulse / APEXlang習慣トラッカー

Oracle APEXとAutonomous Databaseで、毎日の習慣の実施と達成状況を管理するサンプルです。

## 現在の状態

- テーブルとPL/SQL API：実装・実機確認済み
- API検証：2026年11月19日、アプリ110のセッションで8項目PASS、テスト行ロールバック済み
- APEXlang画面：アプリ110への検証・取り込み成功
- UI検証：習慣登録、必須入力、実施・取消、再読み込み後の保持、アーカイブ・履歴を確認
- 集計検証：今日3件中2件で67%、7日間の折れ線をSQLと照合して一致
- 表示検証：履歴28件、390px幅のカード表示を確認
- スクリーンショット：ログインを含む13枚を取得
- Qiita記事：実機検証結果を反映済み

上記の範囲で実装・検証を完了しました。
別利用者の更新拒否はAPIで確認し、別利用者のブラウザー参照操作の検証は今回の範囲には含めていません。

## 検証環境

- Oracle APEX 26.1.6
- SQLcl 26.3.1.0 / Build 26.3.1.301.1413（最終確認）
- Java 21.0.13.1 LTS
- Autonomous Database

## ファイル

| ファイル | 内容 |
|---|---|
| article.md | 実機結果と再現手順を含むQiita記事 |
| requirements.md | 実装要件 |
| scripts/01_schema.sql | 2表、制約、索引、HT_API定義 |
| scripts/02_demo_data.sql | 任意投入の架空データ |
| scripts/03_verify.sql | APEXセッションを利用したAPI検証 |
| scripts/04_check_metrics.sql | 7日間の達成率を照合する読み取り専用SQL |
| scripts/05_cleanup_demo.sql | PREVIEWとDELETEを明示指定する専用デモ利用者のデータ削除用SQL |
| applications/habit-pulse/ | APEXlangソース一式 |
| images/ | 実機のログイン・操作・集計・入力検証画面13枚 |
| implementation-notes.md | 実装コマンド・互換性調整・制限の記録 |

## データベース部分の実行

アプリ専用の解析スキーマの保存接続を、SQLclに`habit-dev`という名前で用意します。
DDLを実行するDBユーザーと、APEXアプリのParsing Schemaを一致させてください。
Walletと接続情報は、このフォルダーの外で管理します。

```text
sql -name habit-dev
```

SQLclで、このREADMEのあるディレクトリから実行します。
`01_schema.sql`は同名オブジェクトのない専用スキーマで、一度だけ実行してください。

```text
@scripts/01_schema.sql
```

次に`applications/habit-pulse/deployments/default.json`の`HABIT_WORKSPACE`を自分のワークスペース名、`app.databaseSession.parsingSchema`の`HABIT_APP`をDDLを実行したDBユーザー名へ変更します。
SQLclで次を実行します。
コマンド内の`HABIT_WORKSPACE`と`HABIT_APP`も自分の値へ変更し、110が使用済みの場合は未使用のIDを指定します。

```text
apex validate -input applications/habit-pulse -workspace HABIT_WORKSPACE
apex import -input applications/habit-pulse -workspace HABIT_WORKSPACE -schema HABIT_APP -id 110
```

検証時は`Validation successful`、取り込み時は`Import successful`を確認します。
APEXアプリの作成後、実際のアプリIDを引数にAPI検証を実行します。
引数の`<アプリID>`は数値へ置き換えてください。

```text
@scripts/03_verify.sql <アプリID>
```

正常終了の目印は`ALL API CHECKS PASSED; test rows rolled back`です。
テストは最後にロールバックします。
未コミットの作業がない検証用接続から実行してください。

APEX管理画面で専用End Userを作成した後、任意で架空データを投入できます。
以下の`HABIT_DEMO`はAPEXログイン名です。

```text
@scripts/02_demo_data.sql HABIT_DEMO
@scripts/04_check_metrics.sql HABIT_DEMO
```

デモデータは3習慣の過去14日分です。
スクリプトはCOMMITして保存し、同名のデモ習慣がある場合は二重投入せず停止します。
アプリはApp BuilderからHabit Pulseを選び、「Run Application」で開きます。

## 初版の制限

連続達成日数、カレンダーヒートマップ、習慣別の累積実施数グラフは未実装です。
習慣管理は現役とアーカイブ済みを同じ一覧で状態ラベル表示し、カード配色は深緑で統一しています。
撮影と集計確認には架空のサンプル記録を使用しています。

## 検証後の片付け

撮影用4習慣・28実施記録、デモユーザー、テストセッション10件、一時資格情報・サーバー一時ファイルを削除しました。
作業サーバー・ADBの両方がSTOPPEDであることを確認済みです。
アプリ110、解析スキーマのテーブル/API、ソース、記事、画像は保持しています。

データ削除用SQLを使う場合は、解析スキーマで`@scripts/05_cleanup_demo.sql HABIT_DEMO PREVIEW`を実行し、候補の習慣一覧を確認してから、第2引数を`DELETE`へ変更して実行します。
このスクリプトによる削除を実機で確認済みです。
指定した所有者のすべての習慣・実施記録を削除するため、専用デモ利用者だけを指定してください。
APEXユーザーはAPEX管理画面から別途削除します。

## 詳細

設計と事前準備は[記事](article.md)、設計時の要件は[requirements.md](requirements.md)、初版の実装範囲は[implementation-notes.md](implementation-notes.md)を参照してください。
