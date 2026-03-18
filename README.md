# Notion ログイントークン管理

元システムの `save_cookie.py` の手動ログインを置き換えるため、
以下を自動化する Python スクリプトです。

- UIでログイン情報（メールアドレス / パスワード / チェック時刻）入力
- JSON (`notion_login_state.json`) に設定とトークン保存
- Selenium による Notion ログイン自動実行
  - メールアドレス入力
  - 続行ボタン押下
  - パスワード入力
  - ログインボタン押下
- 指定時刻にトークン有効性を確認し、無効なら再ログインしてトークン再保存

## セットアップ

```bash
pip install selenium webdriver-manager
```

## 起動

```bash
python notion_login_manager.py
```

## 補足

- 保存先JSONにはログイン情報が含まれるため、取り扱いには注意してください。
- Notionの画面仕様が変更された場合、ボタン要素の特定条件を更新する必要があります。


## Notion 自動招待（統合版）

`元システム/invite_notion_*.py` で分散していた処理を、
`notion_auto_invite.py` に統一しました。

- 招待処理ロジックは共通化
- 参照先（スプレッドシート / NotionページURL）は `notion_invite_targets.json` で切替
- ログイントークンは **旧 `notion_cookies.pkl` ではなく**
  `notion_login_manager.py` が保存する `notion_login_state.json` を利用

### 実行例

```bash
python notion_auto_invite.py week1_week2
```

任意パス指定:

```bash
python notion_auto_invite.py week1_week2 \
  --config notion_invite_targets.json \
  --state-file notion_login_state.json \
  --credentials credentials.json
```

### 設定ファイル形式

`notion_invite_targets.json`

```json
{
  "week1_week2": {
    "spreadsheet_key": "...",
    "sheet_name": "シート1",
    "notion_page_url": "https://www.notion.so/...",
    "email_column": 12,
    "status_column": 13,
    "invited_text": "招待済み"
  }
}
```

`email_column` / `status_column` / `invited_text` は省略可能です。
`email_column` / `status_column` / `invited_text` は省略可能です。
### 進捗シート（`shichoku.json`）連携

`shichoku.json` が存在する場合、Notion 招待完了後に進捗シートも更新します。

- `week3_week4_column` などの `*_column` は **「済」を書き込む列番号**
- LINE名の照合は進捗シートの **B列** を使用（列番号は固定）
- LINE名は全角/半角ゆれを吸収するため NFKC 正規化＋大文字小文字無視で比較
## PyInstaller での配布

以下の spec を用意しています。

- `notion_auto_invite.spec`（アイコン: `img/auto.png`）
- `notion_login_manager.spec`（アイコン: `img/login.png`）

ビルド例:

```bash
pyinstaller notion_auto_invite.spec
pyinstaller notion_login_manager.spec
```