import argparse
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import gspread
import tkinter as tk
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tkinter import messagebox
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


def process_target(
    service: NotionInviteService,
    credentials_path: Path,
    target_name: str,
    target: InviteTarget,
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    client = gspread.service_account(filename=str(credentials_path))
    sheet = client.open_by_key(target.spreadsheet_key).worksheet(target.sheet_name)

    data = sheet.get_all_values()
    email_idx = target.email_column - 1
    status_idx = target.status_column - 1
    invited_count = 0

    for row_index in range(1, len(data)):
        row = data[row_index]
        email = row[email_idx].strip() if len(row) > email_idx else ""
        status = row[status_idx].strip() if len(row) > status_idx else ""

        if not email or status == target.invited_text:
            continue

        if log_callback:
            log_callback(f"{target_name}: 招待処理開始 row={row_index + 1}, email={email}")

        service.invite_guest(email=email, notion_page_url=target.notion_page_url)
        sheet.update_cell(row_index + 1, target.status_column, target.invited_text)


        invited_count += 1

        if log_callback:
            log_callback(f"{target_name}: 招待完了 row={row_index + 1}, email={email}")

    return invited_count


def process_all_targets(
    service: NotionInviteService,
    credentials_path: Path,
    targets: Dict[str, InviteTarget],
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    total_invited = 0
    for target_name, target in targets.items():
        if log_callback:
            log_callback(f"{target_name}: シート処理を開始")
        invited = process_target(
            service=service,
            credentials_path=credentials_path,
            target_name=target_name,
            target=target,
            log_callback=log_callback,
        )
        total_invited += invited
        if log_callback:
            log_callback(f"{target_name}: シート処理完了 (招待数={invited})")
    return total_invited


def run_polling(
    service: NotionInviteService,
    credentials_path: Path,
    targets: Dict[str, InviteTarget],
    poll_interval_seconds: int,
    log_callback: Callable[[str], None],
    stop_event: threading.Event,
) -> None:
    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_callback(f"=== ポーリング {cycle} 回目を開始 ({started_at}) ===")

        try:
            total_invited = process_all_targets(
                service=service,
                credentials_path=credentials_path,
                targets=targets,
                log_callback=log_callback,
            )
            log_callback(f"=== ポーリング {cycle} 回目が完了 (合計招待数={total_invited}) ===")
        except Exception as e:
            log_callback(f"ポーリング {cycle} 回目でエラー: {e}")

        if stop_event.wait(poll_interval_seconds):
            break

    log_callback("ポーリングを停止しました")


class InvitePollingUI:
    def __init__(self, root: tk.Tk, service: NotionInviteService) -> None:
        self.root = root
        self.service = service
        self.stop_event = threading.Event()
        self.polling_thread: Optional[threading.Thread] = None

        self.colors = {
            "bg": "#F6F4FA",
            "card": "#FFFFFF",
            "accent": "#4A2A75",
            "accent_hover": "#3F2364",
            "muted": "#7A6E8F",
            "input_border": "#DDD4EB",
        }

        root.title("Notion 自動招待ポーリング")
        root.geometry("980x640")
        root.configure(bg=self.colors["bg"])

        self.config_var = tk.StringVar(value="notion_invite_targets.json")
        self.credentials_var = tk.StringVar(value="credentials.json")
        self.state_file_var = tk.StringVar(value=str(service.state_file))
        self.interval_var = tk.StringVar(value="300")
        self.status_var = tk.StringVar(value="待機中")

        self.log_widget: Optional[tk.Text] = None

        self._build_ui()

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

    def _make_input(
        self,
        parent: tk.Widget,
        text_var: tk.StringVar,
        width: int = 360,
    ) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=self.colors["card"])
        canvas = tk.Canvas(
            wrapper,
            bg=self.colors["card"],
            highlightthickness=0,
            bd=0,
            width=width,
            height=44,
        )
        canvas.pack(fill="x")
        self._rounded_rect(
            canvas,
            2,
            2,
            width - 2,
            42,
            radius=20,
            fill="#FFFFFF",
            outline=self.colors["input_border"],
            width=1,
        )
        entry = tk.Entry(
            canvas,
            textvariable=text_var,
            bd=0,
            relief="flat",
            bg="#FFFFFF",
            fg="#2B2338",
            insertbackground="#2B2338",
            font=("Segoe UI", 11),
        )
        canvas.create_window(width // 2, 22, width=width - 44, height=26, window=entry)
        return wrapper

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        width: int = 175,
        filled: bool = True,
    ) -> tk.Canvas:
        height = 46
        canvas = tk.Canvas(parent, width=width, height=height, bd=0, highlightthickness=0, bg=self.colors["card"])
        fill = self.colors["accent"] if filled else "#F2ECFA"
        text_color = "#FFFFFF" if filled else self.colors["accent"]
        border_color = self.colors["accent"]
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
        canvas.create_text(
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

        canvas.bind("<Button-1>", lambda _e: command())
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)
        return canvas

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=self.colors["bg"], padx=22, pady=22)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=self.colors["card"], padx=20, pady=20)
        card.pack(fill="both", expand=True)

        left_frame = tk.Frame(card, bg=self.colors["card"])
        left_frame.pack(side="left", fill="y", padx=(0, 16))

        right_frame = tk.Frame(card, bg=self.colors["card"])
        right_frame.pack(side="right", fill="both", expand=True)

        title = tk.Label(
            left_frame,
            text="Notion 自動招待ポーリング",
            bg=self.colors["card"],
            fg="#2E2342",
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w", pady=(0, 14))

        tk.Label(left_frame, text="設定ファイル", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")
        self._make_input(left_frame, self.config_var).pack(fill="x", pady=(6, 10))

        tk.Label(left_frame, text="認証情報ファイル", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")
        self._make_input(left_frame, self.credentials_var).pack(fill="x", pady=(6, 10))

        tk.Label(left_frame, text="状態ファイル", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")
        self._make_input(left_frame, self.state_file_var).pack(fill="x", pady=(6, 10))

        tk.Label(left_frame, text="ポーリング間隔(秒)", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")
        self._make_input(left_frame, self.interval_var).pack(fill="x", pady=(6, 14))

        button_row = tk.Frame(left_frame, bg=self.colors["card"])
        button_row.pack(fill="x")
        self._make_button(button_row, "ポーリング開始", self.start_polling, width=175, filled=True).pack(side="left")
        self._make_button(button_row, "ポーリング停止", self.stop_polling, width=175, filled=False).pack(side="right")

        tk.Label(
            left_frame,
            textvariable=self.status_var,
            bg=self.colors["card"],
            fg=self.colors["accent"],
            wraplength=360,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(14, 0))

        tk.Label(
            right_frame,
            text="処理ログ",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        self.log_widget = tk.Text(
            right_frame,
            height=30,
            bd=1,
            relief="solid",
            bg="#FAF8FD",
            fg="#2B2338",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        if self.log_widget is None:
            return

        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", line)
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _log_threadsafe(self, message: str) -> None:
        self.root.after(0, lambda: self._append_log(message))

    def _set_status_threadsafe(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(message))

    def _validate_inputs(self) -> Optional[Dict[str, Any]]:
        try:
            interval_seconds = int(self.interval_var.get().strip())
            if interval_seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("入力エラー", "ポーリング間隔は 1 以上の整数(秒)で入力してください")
            return None

        config_path = Path(self.config_var.get().strip())
        credentials_path = Path(self.credentials_var.get().strip())
        state_file = Path(self.state_file_var.get().strip())

        if not config_path.exists():
            messagebox.showerror("入力エラー", f"設定ファイルが見つかりません: {config_path}")
            return None
        if not credentials_path.exists():
            messagebox.showerror("入力エラー", f"認証情報ファイルが見つかりません: {credentials_path}")
            return None

        return {
            "interval_seconds": interval_seconds,
            "config_path": config_path,
            "credentials_path": credentials_path,
            "state_file": state_file,
        }

    def start_polling(self) -> None:
        if self.polling_thread and self.polling_thread.is_alive():
            messagebox.showinfo("通知", "すでにポーリングを実行中です")
            return

        values = self._validate_inputs()
        if values is None:
            return

        self.stop_event.clear()
        self.service = NotionInviteService(state_file=values["state_file"])

        try:
            targets = load_targets(values["config_path"])
        except Exception as e:
            messagebox.showerror("設定読み込みエラー", str(e))
            return

        if not targets:
            messagebox.showerror("設定読み込みエラー", "ターゲットが1件もありません")
            return

        self.status_var.set("ポーリング実行中")
        self._append_log("ポーリングを開始します")

        def worker() -> None:
            run_polling(
                service=self.service,
                credentials_path=values["credentials_path"],
                targets=targets,
                poll_interval_seconds=values["interval_seconds"],
                log_callback=self._log_threadsafe,
                stop_event=self.stop_event,
            )
            self._set_status_threadsafe("停止中")

        self.polling_thread = threading.Thread(target=worker, daemon=True)
        self.polling_thread.start()

    def stop_polling(self) -> None:
        self.stop_event.set()
        self.status_var.set("停止リクエスト送信済み")
        self._append_log("停止リクエストを送信しました")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Notion 自動招待（単発 + ポーリングUI）")
    parser.add_argument("target", nargs="?", help="招待設定名（例: week1_week2）")
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
    parser.add_argument(
        "--ui",
        action="store_true",
        help="ポーリングUIを起動する",
    )
    return parser.parse_args()



def run_single_target(args: argparse.Namespace) -> None:
    if args.target is None:
        raise ValueError("単発実行では target の指定が必要です。UI を使う場合は --ui を付けてください。")

    targets = load_targets(Path(args.config))

    if args.target not in targets:
        available = ", ".join(sorted(targets.keys()))
        raise ValueError(f"不明な target: {args.target}. 利用可能: {available}")

    service = NotionInviteService(state_file=Path(args.state_file))
    invited = process_target(
        service=service,
        credentials_path=Path(args.credentials),
        target_name=args.target,
        target=targets[args.target],
    )
    print(f"処理完了: target={args.target}, invited={invited}")


def run_ui(state_file: Path) -> None:
    root = tk.Tk()
    service = NotionInviteService(state_file=state_file)
    InvitePollingUI(root, service)
    root.mainloop()


def main() -> None:
    args = parse_args()
    if args.ui:
        run_ui(state_file=Path(args.state_file))
        return
    run_single_target(args)


if __name__ == "__main__":
    main()
