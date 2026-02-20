import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import gspread
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://www.notion.so/login"


@dataclass
class InviteTarget:
    spreadsheet_key: str
    sheet_name: str
    notion_page_url: str
    email_column: int = 12
    status_column: int = 13
    invited_text: str = "招待済み"


class NotionInviteService:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file

    def _load_token_cookies(self) -> List[Dict[str, Any]]:
        if not self.state_file.exists():
            raise FileNotFoundError(f"ログイントークンが見つかりません: {self.state_file}")

        with self.state_file.open("r", encoding="utf-8") as f:
            state = json.load(f)

        # 新システム形式（notion_login_manager.py で保存）
        # state["token"]["cookies"] が Selenium の Cookie 配列
        cookies = state.get("token", {}).get("cookies", [])
        if not cookies:
            raise ValueError(
                "トークン形式が不正、または cookies が空です。notion_login_manager.py で再保存してください。"
            )
        return cookies

    def _new_driver(self) -> webdriver.Chrome:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    def _login_with_token(self, driver: webdriver.Chrome, cookies: List[Dict[str, Any]]) -> None:
        driver.get(LOGIN_URL)
        time.sleep(2)

        for cookie in cookies:
            # Selenium の add_cookie で受け付けない属性を除外
            cookie_copy = {k: v for k, v in cookie.items() if k not in {"sameSite"}}
            try:
                driver.add_cookie(cookie_copy)
            except Exception:
                continue

        driver.get(LOGIN_URL)
        time.sleep(3)

    def invite_guest(self, email: str, notion_page_url: str) -> None:
        cookies = self._load_token_cookies()
        driver = self._new_driver()

        try:
            self._login_with_token(driver, cookies)

            driver.get(notion_page_url)
            time.sleep(4)

            share_btn = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(@class,'notion-topbar-share-menu')]"))
            )
            driver.execute_script("arguments[0].click();", share_btn)
            time.sleep(2)

            email_input = driver.find_element(
                By.XPATH, "//input[@placeholder='カンマで区切ったメールアドレスまたはグループ']"
            )
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(2)

            role_btn = driver.find_element(
                By.XPATH,
                "//div[@role='button'][.//span[contains(text(),'フルアクセス権限')]]",
            )
            role_btn.click()
            time.sleep(1)

            view_btn = driver.find_element(
                By.XPATH,
                "//div[@role='menuitem']//div[contains(text(),'読み取り権限')]",
            )
            view_btn.click()
            time.sleep(1)

            invite_btn = driver.find_element(
                By.XPATH,
                "//div[@role='button' and contains(text(),'招待')]",
            )
            invite_btn.click()
            time.sleep(2)

            print(f"招待完了: {email}")
        finally:
            driver.quit()


def load_targets(config_path: Path) -> Dict[str, InviteTarget]:
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    targets: Dict[str, InviteTarget] = {}
    for name, cfg in raw.items():
        targets[name] = InviteTarget(
            spreadsheet_key=cfg["spreadsheet_key"],
            sheet_name=cfg.get("sheet_name", "シート1"),
            notion_page_url=cfg["notion_page_url"],
            email_column=cfg.get("email_column", 12),
            status_column=cfg.get("status_column", 13),
            invited_text=cfg.get("invited_text", "招待済み"),
        )
    return targets


def process_target(service: NotionInviteService, credentials_path: Path, target: InviteTarget) -> None:
    client = gspread.service_account(filename=str(credentials_path))
    sheet = client.open_by_key(target.spreadsheet_key).worksheet(target.sheet_name)

    data = sheet.get_all_values()
    email_idx = target.email_column - 1
    status_idx = target.status_column - 1

    for row_index in range(1, len(data)):
        row = data[row_index]
        email = row[email_idx].strip() if len(row) > email_idx else ""
        status = row[status_idx].strip() if len(row) > status_idx else ""

        if not email or status == target.invited_text:
            continue

        service.invite_guest(email=email, notion_page_url=target.notion_page_url)
        sheet.update_cell(row_index + 1, target.status_column, target.invited_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Notion 自動招待（共通処理 + ターゲット切替）")
    parser.add_argument("target", help="招待設定名（例: week1_week2）")
    parser.add_argument(
        "--config",
        default="notion_invite_targets.json",
        help="招待設定 JSON のパス（デフォルト: notion_invite_targets.json）",
    )
    parser.add_argument(
        "--state-file",
        default="notion_login_state.json",
        help="notion_login_manager.py が保存した状態ファイル",
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Google サービスアカウント鍵ファイル",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = load_targets(Path(args.config))

    if args.target not in targets:
        available = ", ".join(sorted(targets.keys()))
        raise ValueError(f"不明な target: {args.target}. 利用可能: {available}")

    service = NotionInviteService(state_file=Path(args.state_file))
    process_target(
        service=service,
        credentials_path=Path(args.credentials),
        target=targets[args.target],
    )


if __name__ == "__main__":
    main()
