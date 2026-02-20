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
