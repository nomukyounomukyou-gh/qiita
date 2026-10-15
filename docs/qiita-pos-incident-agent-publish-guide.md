# 店舗Agent記事と構成図をQiitaへ載せる手順

Markdown本文と画像は別のファイルです。Markdownに画像そのものは埋め込まず、画像URLを`![説明](画像URL)`で指定します。

## そのまま貼り付ける方法

今回の記事Markdownには、公開済みGitHub画像のURLを設定しています。記事本文をQiitaエディタへ貼り付けると、別途画像をアップロードせずに構成図を参照できます。プレビューで表示を確認してから投稿してください。外部画像なので、GitHub側の画像を削除・移動すると記事にも影響します。

- [記事Markdown](https://github.com/nomukyounomukyou-gh/qiita/blob/main/oci-enterprise-ai-pos-incident-agent.md)
- [構成図PNG](https://raw.githubusercontent.com/nomukyounomukyou-gh/qiita/main/images/oci-enterprise-ai-pos-incident-agent-architecture.png)
- [編集用PowerPoint](https://github.com/nomukyounomukyou-gh/qiita/blob/main/diagram-source/oci-enterprise-ai-pos-incident-agent-architecture.pptx)

## Qiitaに画像を保存する方法

1. 記事Markdownの本文をQiitaの記事エディタへ貼り付ける。先頭の`# 記事タイトル`をタイトル欄へ移した場合は、本文中の同じ見出しを削除しておく。
2. 構成図PNGをダウンロードする。
3. 記事内の「システム構成」の画像行を選び、PNGをQiitaエディタへドラッグ＆ドロップする。またはエディタの画像添付操作でPNGを選択する。
4. Qiitaが挿入した画像Markdownを使い、元のGitHub画像の`![...](...)`行を置き換える。画像が2枚にならないように確認する。
5. 「構成図を拡大表示」のリンクもQiitaが発行した画像URLに置き換えると、画像の参照先をQiitaに揃えられる。編集用PowerPointのGitHubリンクはそのまま利用できる。
6. プレビューで図の文字・矢印と、記事内のコードブロックを確認して投稿する。

画像だけを先にアップロードしたい場合は、Qiitaの「設定」→「ファイルのアップロード」からPNGを選び、発行された画像URLをコピーして本文の画像行へ設定します。

```markdown
![店舗システム障害の初動支援Agentの構成図](ここをQiitaが発行した画像URLに置き換える)
```

PNGは閲覧・投稿用、PPTXは編集用です。図を修正するときはPowerPointの文字や線を編集し、PNGとして書き出して記事の画像を更新してください。

参照：[Qiita公式「画像のアップロード・削除方法」](https://help.qiita.com/ja/articles/qiita-image-upload)
