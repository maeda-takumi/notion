import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import messagebox

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://www.notion.so/login"
HOME_URL = "https://www.notion.so/"
STATE_FILE = Path("notion_login_state.json")


class NotionLoginManager:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self._lock = threading.Lock()
        self._last_run_key: Optional[str] = None

    def load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {
                "credentials": {
                    "email": "",
                    "password": "",
                },
                "check_time": "09:00",
                "token": {
                    "cookies": [],
                    "saved_at": None,
                    "expires_at": None,
                },
            }

        with self.state_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, state: Dict[str, Any]) -> None:
        with self.state_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _new_driver(self) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def _find_continue_button(self, driver: webdriver.Chrome):
        return driver.find_element(
            By.XPATH,
            "//div[@role='button' and (contains(.,'続行') or contains(.,'Continue'))]",
        )

    def _find_login_button(self, driver: webdriver.Chrome):
        return driver.find_element(
            By.XPATH,
            "//div[@role='button' and (contains(.,'ログイン') or contains(.,'Log in'))]",
        )

    def save_login_token(self, email: str, password: str) -> Dict[str, Any]:
        driver = self._new_driver()
        try:
            wait = WebDriverWait(driver, 25)
            driver.get(LOGIN_URL)

            email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
            email_input.clear()
            email_input.send_keys(email)

            self._find_continue_button(driver).click()

            password_input = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            password_input.clear()
            password_input.send_keys(password)

            self._find_login_button(driver).click()

            wait.until(lambda d: "/login" not in d.current_url)

            cookies = driver.get_cookies()
            max_expiry = max(
                (cookie.get("expiry") for cookie in cookies if isinstance(cookie.get("expiry"), (int, float))),
                default=None,
            )

            return {
                "cookies": cookies,
                "saved_at": datetime.now().isoformat(),
                "expires_at": datetime.fromtimestamp(max_expiry).isoformat() if max_expiry else None,
            }
        finally:
            driver.quit()

    def is_token_valid(self, cookies: List[Dict[str, Any]]) -> bool:
        if not cookies:
            return False

        driver = self._new_driver()
        try:
            driver.get(LOGIN_URL)
            time.sleep(1)

            for cookie in cookies:
                cookie_copy = {k: v for k, v in cookie.items() if k not in {"sameSite"}}
                try:
                    driver.add_cookie(cookie_copy)
                except Exception:
                    continue

            driver.get(HOME_URL)
            time.sleep(3)

            if "/login" in driver.current_url:
                return False

            page_source = driver.page_source
            return "ログイン" not in page_source and "Log in" not in page_source
        finally:
            driver.quit()

    def recover_token_if_needed(self) -> str:
        with self._lock:
            state = self.load_state()
            email = state["credentials"].get("email", "")
            password = state["credentials"].get("password", "")
            token = state.get("token", {})

            if not email or not password:
                return "メールアドレス/パスワードが未設定です"

            now = datetime.now()
            expires_at_text = token.get("expires_at")

            expired = False
            if expires_at_text:
                try:
                    expired = now >= datetime.fromisoformat(expires_at_text)
                except ValueError:
                    expired = True

            cookies = token.get("cookies", [])
            usable = self.is_token_valid(cookies) if cookies and not expired else False

            if usable:
                return "トークンは有効です（再保存不要）"

            new_token = self.save_login_token(email=email, password=password)
            state["token"] = new_token
            self.save_state(state)
            return "トークンを再保存しました"

    def scheduler_loop(self, status_callback):
        while True:
            try:
                state = self.load_state()
                check_time = state.get("check_time", "09:00")
                now = datetime.now()
                run_key = now.strftime("%Y-%m-%d") + check_time
                target = now.strftime("%H:%M")

                if target == check_time and self._last_run_key != run_key:
                    result = self.recover_token_if_needed()
                    self._last_run_key = run_key
                    status_callback(f"[{datetime.now().strftime('%H:%M:%S')}] {result}")
            except Exception as e:
                status_callback(f"[{datetime.now().strftime('%H:%M:%S')}] スケジューラエラー: {e}")

            time.sleep(20)


class LoginUI:
    def __init__(self, root: tk.Tk, manager: NotionLoginManager) -> None:
        self.root = root
        self.manager = manager

        root.title("Notion ログイントークン管理")
        root.geometry("460x300")

        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.check_time_var = tk.StringVar(value="09:00")
        self.status_var = tk.StringVar(value="初期化中...")

        self._build_ui()
        self._load_state_to_form()
        self._start_scheduler()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="メールアドレス").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.email_var, width=45).grid(row=1, column=0, columnspan=2, sticky="ew")

        tk.Label(frame, text="パスワード").grid(row=2, column=0, sticky="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.password_var, show="*", width=45).grid(
            row=3, column=0, columnspan=2, sticky="ew"
        )

        tk.Label(frame, text="毎日チェック時刻 (HH:MM)").grid(row=4, column=0, sticky="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.check_time_var, width=12).grid(row=5, column=0, sticky="w")

        tk.Button(frame, text="設定を保存", command=self.save_settings).grid(row=6, column=0, sticky="w", pady=(10, 0))
        tk.Button(frame, text="今すぐトークン保存", command=self.save_token_now).grid(
            row=6, column=1, sticky="e", pady=(10, 0)
        )
        tk.Button(frame, text="今すぐトークン確認/復旧", command=self.recover_now).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        tk.Label(frame, textvariable=self.status_var, fg="blue", wraplength=420, justify="left").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

    def _load_state_to_form(self) -> None:
        state = self.manager.load_state()
        self.email_var.set(state["credentials"].get("email", ""))
        self.password_var.set(state["credentials"].get("password", ""))
        self.check_time_var.set(state.get("check_time", "09:00"))
        self.status_var.set("設定を読み込みました")

    def _collect_state(self) -> Dict[str, Any]:
        state = self.manager.load_state()
        state["credentials"] = {
            "email": self.email_var.get().strip(),
            "password": self.password_var.get(),
        }
        state["check_time"] = self.check_time_var.get().strip()
        state.setdefault("token", {"cookies": [], "saved_at": None, "expires_at": None})
        return state

    def save_settings(self) -> None:
        check_time = self.check_time_var.get().strip()
        if len(check_time) != 5 or check_time[2] != ":":
            messagebox.showerror("入力エラー", "時刻は HH:MM 形式で入力してください")
            return

        self.manager.save_state(self._collect_state())
        self.status_var.set("設定を保存しました")

    def save_token_now(self) -> None:
        try:
            state = self._collect_state()
            email = state["credentials"]["email"]
            password = state["credentials"]["password"]
            if not email or not password:
                messagebox.showerror("入力エラー", "メールアドレスとパスワードを入力してください")
                return

            token = self.manager.save_login_token(email=email, password=password)
            state["token"] = token
            self.manager.save_state(state)
            self.status_var.set("トークン保存に成功しました")
        except TimeoutException:
            self.status_var.set("ログイン画面の要素取得でタイムアウトしました")
        except Exception as e:
            self.status_var.set(f"トークン保存に失敗しました: {e}")

    def recover_now(self) -> None:
        try:
            self.manager.save_state(self._collect_state())
            result = self.manager.recover_token_if_needed()
            self.status_var.set(result)
        except Exception as e:
            self.status_var.set(f"復旧処理に失敗しました: {e}")

    def _start_scheduler(self) -> None:
        def status_callback(msg: str) -> None:
            self.root.after(0, lambda: self.status_var.set(msg))

        thread = threading.Thread(target=self.manager.scheduler_loop, args=(status_callback,), daemon=True)
        thread.start()


def main() -> None:
    manager = NotionLoginManager(STATE_FILE)
    root = tk.Tk()
    LoginUI(root, manager)
    root.mainloop()


if __name__ == "__main__":
    main()
