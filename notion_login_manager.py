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
LOG_FILE = Path("notion_login_log.json")


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

        self.colors = {
            "bg": "#F6F4FA",
            "card": "#FFFFFF",
            "accent": "#4A2A75",
            "accent_hover": "#3F2364",
            "muted": "#7A6E8F",
            "input_border": "#DDD4EB",
        }

        root.title("Notion ログイントークン管理")
        root.geometry("520x620")
        root.configure(bg=self.colors["bg"])

        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.check_time_var = tk.StringVar(value="09:00")
        self.status_var = tk.StringVar(value="初期化中...")
        self.token_path_var = tk.StringVar(value="")

        self.log_path = LOG_FILE
        self.log_widget: Optional[tk.Text] = None

        self._build_ui()
        self._load_state_to_form()
        self._append_log("実行開始")
        self._start_scheduler()


    @staticmethod
    def _rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
        points = [
            x1 + radius,
            y1,
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _append_log(self, message: str) -> None:
        entry = {"timestamp": datetime.now().isoformat(), "message": message}
        logs: List[Dict[str, str]] = []

        if self.log_path.exists():
            try:
                with self.log_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        logs = loaded
            except (json.JSONDecodeError, OSError):
                logs = []

        logs.append(entry)
        with self.log_path.open("w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        if self.log_widget is not None:
            self.log_widget.configure(state="normal")
            self.log_widget.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            self.log_widget.see("end")
            self.log_widget.configure(state="disabled")
    def _make_input(self, parent: tk.Widget, text_var: tk.StringVar, show: Optional[str] = None) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=self.colors["card"])
        canvas = tk.Canvas(
            wrapper,
            bg=self.colors["card"],
            highlightthickness=0,
            bd=0,
            width=440,
            height=44,
        )
        canvas.pack(fill="x")
        self._rounded_rect(
            canvas,
            2,
            2,
            438,
            42,
            radius=20,
            fill="#FFFFFF",
            outline=self.colors["input_border"],
            width=1,
        )
        entry = tk.Entry(
            canvas,
            textvariable=text_var,
            show=show,
            bd=0,
            relief="flat",
            bg="#FFFFFF",
            fg="#2B2338",
            insertbackground="#2B2338",
            font=("Segoe UI", 11),
        )
        canvas.create_window(220, 22, width=396, height=26, window=entry)
        return wrapper

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        width: int = 210,
        filled: bool = True,
    ) -> tk.Canvas:
        height = 46
        canvas = tk.Canvas(parent, width=width, height=height, bd=0, highlightthickness=0, bg=self.colors["card"])
        fill = self.colors["accent"] if filled else "#F2ECFA"
        text_color = "#FFFFFF" if filled else self.colors["accent"]
        border_color = self.colors["accent"] if not filled else self.colors["accent"]
        button_shape = self._rounded_rect(
            canvas,
            2,
            2,
            width - 2,
            height - 2,
            radius=20,
            fill=fill,
            outline=border_color,
            width=1,
        )
        label = canvas.create_text(
            width // 2,
            height // 2,
            text=text,
            fill=text_color,
            font=("Segoe UI", 10, "bold"),
        )

        def _on_enter(_event):
            if filled:
                canvas.itemconfigure(button_shape, fill=self.colors["accent_hover"])

        def _on_leave(_event):
            if filled:
                canvas.itemconfigure(button_shape, fill=self.colors["accent"])

        for target in (canvas,):
            target.bind("<Button-1>", lambda _e: command())
            target.bind("<Enter>", _on_enter)
            target.bind("<Leave>", _on_leave)
        canvas.tag_bind(label, "<Button-1>", lambda _e: command())
        return canvas

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=self.colors["bg"], padx=22, pady=22)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=self.colors["card"], padx=20, pady=20)
        card.pack(fill="both", expand=True)

        title = tk.Label(
            card,
            text="Notion ログイントークン管理",
            bg=self.colors["card"],
            fg="#2E2342",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w", pady=(0, 14))

        tk.Label(card, text="メールアドレス", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(
            anchor="w"
        )
        self._make_input(card, self.email_var).pack(fill="x", pady=(6, 10))

        tk.Label(card, text="パスワード", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")
        self._make_input(card, self.password_var, show="*").pack(fill="x", pady=(6, 10))

        tk.Label(
            card,
            text="毎日チェック時刻 (HH:MM)",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        self._make_input(card, self.check_time_var).pack(fill="x", pady=(6, 14))

        button_row = tk.Frame(card, bg=self.colors["card"])
        button_row.pack(fill="x")
        self._make_button(button_row, "設定を保存", self.save_settings, filled=False).pack(side="left")
        self._make_button(button_row, "今すぐトークン保存", self.save_token_now).pack(side="right")

        self._make_button(card, "今すぐトークン確認/復旧", self.recover_now, width=440).pack(fill="x", pady=(10, 0))

        status_label = tk.Label(
            card,
            textvariable=self.status_var,
            bg=self.colors["card"],
            fg=self.colors["accent"],
            wraplength=440,
            justify="left",
            font=("Segoe UI", 10),
        )
        status_label.pack(anchor="w", pady=(14, 0))

        token_path_label = tk.Label(
            card,
            textvariable=self.token_path_var,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            wraplength=440,
            justify="left",
            font=("Segoe UI", 9),
        )
        token_path_label.pack(anchor="w", pady=(6, 0))

        tk.Label(
            card,
            text="ログ",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(14, 6))

        self.log_widget = tk.Text(
            card,
            height=8,
            bd=1,
            relief="solid",
            bg="#FAF8FD",
            fg="#2B2338",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")

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

        if not messagebox.askyesno("確認", "設定を保存してよろしいですか？"):
            return
        self.manager.save_state(self._collect_state())
        self.status_var.set("設定を保存しました")
        self._append_log("設定保存")

    def save_token_now(self) -> None:
        if not messagebox.askyesno("確認", "トークンを保存してよろしいですか？"):
            return

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
            token_path_text = f"保存トークン: {self.manager.state_path.resolve()}"
            self.token_path_var.set(token_path_text)
            self.status_var.set("トークン保存に成功しました")
            self._append_log("保存完了")
            self._append_log(token_path_text)
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
