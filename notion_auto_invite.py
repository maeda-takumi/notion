import argparse
import json
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import gspread
import tkinter as tk
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tkinter import messagebox
from webdriver_manager.chrome import ChromeDriverManager
LOGIN_URL = "https://www.notion.so/login"
SOURCE_SPREADSHEET_KEY = "1OZMS0_7l4oum7JtIZR2WKoqb8-YNB4cBffrD9dcMGjc"
CHATWORK_API_TOKEN = "fee574510c5ce22d78b85282a0a8acaa"
CHATWORK_ROOM_ID = "420768122"


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path

@dataclass
class InviteTarget:
    spreadsheet_key: str
    sheet_name: str
    notion_page_url: str
    email_column: int
    status_column: int
    invited_text: str = "招待済み"

@dataclass
class PendingInvite:
    row_index: int
    email: str
    name: str
    scheduled_datetime: Optional[datetime]


def _post_chatwork_message(lines: List[str]) -> None:
    payload = urllib.parse.urlencode({"body": "\n".join(lines)}).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages",
        data=payload,
        headers={"X-ChatWorkToken": CHATWORK_API_TOKEN},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10):
        pass

def send_chatwork_notification(invite: PendingInvite) -> None:
    notified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        "Notion招待が完了しました。",
        f"通知したメアド: {invite.email}",
        f"通知した名前: {invite.name or '（未設定）'}",
        f"通知した日時: {notified_at}",
    ]

    if invite.scheduled_datetime is not None:
        lines.append(f"通知指定時刻: {invite.scheduled_datetime.strftime('%Y-%m-%d %H:%M')}")
    else:
        lines.append("通知指定時刻: なし")

    _post_chatwork_message(lines)

def send_chatwork_group_notification(target_name: str, invites: List[PendingInvite]) -> None:
    if not invites:
        return

    notified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        f"{target_name}: Notion招待が完了しました。",
        f"通知件数: {len(invites)}件",
        f"通知日時: {notified_at}",
        "",
        "対象一覧:",
    ]

    for index, invite in enumerate(invites, start=1):
        if invite.scheduled_datetime is not None:
            scheduled_text = invite.scheduled_datetime.strftime("%Y-%m-%d %H:%M")
        else:
            scheduled_text = "なし"

        lines.append(
            f"{index}. {invite.email} / {invite.name or '（未設定）'} / 通知指定時刻: {scheduled_text}"
        )

    _post_chatwork_message(lines)


def parse_scheduled_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()

    if not date_str or not time_str:
        return None

    patterns = [
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H時%M分",
    ]

    dt_text = f"{date_str} {time_str}"
    for pattern in patterns:
        try:
            return datetime.strptime(dt_text, pattern)
        except ValueError:
            continue

    return None



class NotionInviteService:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._driver: Optional[webdriver.Chrome] = None
        self._is_logged_in = False

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
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        try:
            driver.maximize_window()
        except Exception:
            # 実行環境によっては最大化できないことがあるため、失敗時は継続する。
            pass
        return driver
    def _get_driver(self) -> webdriver.Chrome:
        if self._driver is None:
            self._driver = self._new_driver()
            self._is_logged_in = False
        return self._driver

    def _reset_driver(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
        self._driver = None
        self._is_logged_in = False

    def _click_with_retry(self, wait: WebDriverWait, by: By, selector: str) -> None:
        """UI 遷移中の一時的なクリック阻害を考慮してクリックする。"""
        last_error: Optional[Exception] = None
        for _ in range(3):
            target = wait.until(EC.presence_of_element_located((by, selector)))
            try:
                target.click()
                return
            except ElementClickInterceptedException as e:
                last_error = e
                # 通常クリックが阻害された場合は JS click で続行する。
                self._get_driver().execute_script("arguments[0].click();", target)
                return
            except Exception as e:
                last_error = e
                self._get_driver().execute_script("arguments[0].click();", target)
                return

        if last_error is not None:
            raise last_error

    def _click_if_present(self, by: By, selector: str, timeout: float = 2.0) -> bool:
        """短時間だけ待機して要素があればクリックする。"""
        wait = WebDriverWait(self._get_driver(), timeout)
        try:
            target = wait.until(EC.presence_of_element_located((by, selector)))
        except TimeoutException:
            return False

        try:
            target.click()
        except Exception:
            self._get_driver().execute_script("arguments[0].click();", target)
        return True

    def _set_read_only_permission(self, wait: WebDriverWait) -> None:
        """招待前の権限ドロップダウンで「読み取り権限」を選択・検証する。"""
        driver = self._get_driver()
        role_btn_xpath = (
            "(//div[@role='button' and @aria-haspopup='dialog'"
            " and (.//*[contains(normalize-space(.),'権限')]"
            " or contains(normalize-space(.),'権限'))])[1]"
        )
        read_only_menu_item_xpath = (
            "//div[@role='menuitem'][.//*[contains(normalize-space(.),'読み取り権限')]"
            " or contains(normalize-space(.),'読み取り権限')]"
        )

        role_btn = wait.until(EC.element_to_be_clickable((By.XPATH, role_btn_xpath)))
        driver.execute_script("arguments[0].click();", role_btn)

        view_menu_item = wait.until(
            EC.element_to_be_clickable((By.XPATH, read_only_menu_item_xpath))
        )
        driver.execute_script("arguments[0].click();", view_menu_item)

        def _is_read_only_selected(_: webdriver.Chrome) -> bool:
            try:
                selected_role = driver.find_element(By.XPATH, role_btn_xpath)
                return "読み取り権限" in selected_role.text
            except Exception:
                return False

        if not WebDriverWait(driver, 5).until(_is_read_only_selected):
            raise RuntimeError("権限を『読み取り権限』に変更できなかったため招待を中止します。")
        
    def close_driver(self) -> None:
        self._reset_driver()

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

    def _invite_guest_once(self, email: str, notion_page_url: str) -> None:
        cookies = self._load_token_cookies()
        driver = self._get_driver()
        wait = WebDriverWait(driver, 8)

        if not self._is_logged_in:
            self._login_with_token(driver, cookies)
            self._is_logged_in = True

        driver.get(notion_page_url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        share_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(@class,'notion-topbar-share-menu')]"))
        )
        driver.execute_script("arguments[0].click();", share_btn)
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@role='dialog' or @role='menu' or @data-overlay='true']")
            )
        )

        email_input = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//input[contains(@placeholder,'メール') or contains(@placeholder,'email') or contains(@aria-label,'メール') or contains(@aria-label,'email')]",
                )
            )
        )
        email_input.clear()
        email_input.send_keys(email)

        invite_btn_xpath = (
            "(//div[@role='button' and (contains(.,'招待') or contains(.,'Invite'))]"
            " | //button[contains(.,'招待') or contains(.,'Invite')])[1]"
        )

        
        self._set_read_only_permission(wait)

        self._click_with_retry(wait, By.XPATH, invite_btn_xpath)

    def invite_guest(self, email: str, notion_page_url: str) -> None:
        try:
            self._invite_guest_once(email=email, notion_page_url=notion_page_url)
        except Exception:
            self._reset_driver()
            self._invite_guest_once(email=email, notion_page_url=notion_page_url)


def load_targets(config_path: Path) -> Dict[str, InviteTarget]:
    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    targets: Dict[str, InviteTarget] = {}
    for name, cfg in raw.items():
        email_column = cfg.get("email_column")
        status_column = cfg.get("status_column")

        if email_column is None or status_column is None:
            raise ValueError(
                f"{name}: email_column/status_column は必須です。元システムの列定義を設定してください。"
            )

        if int(email_column) < 1 or int(status_column) < 1:
            raise ValueError(f"{name}: email_column/status_column は 1 以上で指定してください。")

        if int(email_column) == int(status_column):
            raise ValueError(f"{name}: email_column と status_column は同じ列にできません。")
        targets[name] = InviteTarget(
            spreadsheet_key=cfg["spreadsheet_key"],
            sheet_name=cfg.get("sheet_name", "シート1"),
            notion_page_url=cfg["notion_page_url"],
            email_column=int(email_column),
            status_column=int(status_column),
            invited_text=cfg.get("invited_text", "招待済み"),
        )
    return targets


def collect_pending_invites(
    credentials_path: Path,
    target_name: str,
    target: InviteTarget,
    log_callback: Optional[Callable[[str], None]] = None,
) -> tuple[Any, List[PendingInvite]]:
    client = gspread.service_account(filename=str(credentials_path))
    sheet = client.open_by_key(target.spreadsheet_key).worksheet(target.sheet_name)

    data = sheet.get_all_values()
    email_idx = target.email_column - 1
    status_idx = target.status_column - 1
    is_week1 = target_name.strip().casefold() == "week1"
    pending_invites: List[PendingInvite] = []

    for row_index in range(1, len(data)):
        row = data[row_index]
        email = row[email_idx].strip() if len(row) > email_idx else ""
        status = row[status_idx].strip() if len(row) > status_idx else ""

        if not email or status == target.invited_text:
            continue

        if is_week1:
            date_str = row[0] if len(row) > 0 else ""
            time_str = row[1] if len(row) > 1 else ""
            scheduled_dt = parse_scheduled_datetime(date_str, time_str)
            if scheduled_dt is not None and datetime.now() < scheduled_dt:
                if log_callback:
                    log_callback(
                        f"{target_name}: スキップ（未到来） row={row_index + 1}, email={email}, scheduled={scheduled_dt.strftime('%Y-%m-%d %H:%M')}"
                    )
                continue
        else:
            scheduled_dt = None

        name = row[3].strip() if len(row) > 3 else ""

        if log_callback:
            log_callback(f"{target_name}: 招待候補 row={row_index + 1}, email={email}")

        pending_invites.append(
            PendingInvite(
                row_index=row_index + 1,
                email=email,
                name=name,
                scheduled_datetime=scheduled_dt,
            )
        )

    return sheet, pending_invites


def process_all_targets(
    service: NotionInviteService,
    credentials_path: Path,
    targets: Dict[str, InviteTarget],
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    total_invited = 0

    for target_name, target in targets.items():
        if log_callback:
            log_callback(f"{target_name}: 処理開始")
        sheet, pending_invites = collect_pending_invites(
            credentials_path=credentials_path,
            target_name=target_name,
            target=target,
            log_callback=log_callback,
        )

        if not pending_invites:
            if log_callback:
                log_callback(f"{target_name}: 招待対象なし")
            continue

        unique_emails = list(dict.fromkeys(pending.email for pending in pending_invites))
        if log_callback:
            log_callback(f"{target_name}: Notion招待開始 notion={target.notion_page_url}, 対象数={len(unique_emails)}")

        for email in unique_emails:
            service.invite_guest(email=email, notion_page_url=target.notion_page_url)

        if log_callback:
            log_callback(f"{target_name}: Notion招待完了")

        for pending in pending_invites:
            sheet.update_cell(pending.row_index, target.status_column, target.invited_text)
            if log_callback:
                log_callback(f"{target_name}: ステータス更新 row={pending.row_index}, email={pending.email}")
        send_chatwork_group_notification(target_name, pending_invites)
        if log_callback:
            log_callback(f"{target_name}: Chatwork通知完了 (通知件数={len(pending_invites)})")

        total_invited += len(pending_invites)
        if log_callback:
            log_callback(f"{target_name}: 処理完了 (招待数={len(pending_invites)})")

    return total_invited

def process_single_target(
    service: NotionInviteService,
    credentials_path: Path,
    target_name: str,
    target: InviteTarget,
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    return process_all_targets(
        service=service,
        credentials_path=credentials_path,
        targets={target_name: target},
        log_callback=log_callback,
    )


def run_polling(
    service: NotionInviteService,
    credentials_path: Path,
    targets: Dict[str, InviteTarget],
    poll_interval_seconds: int,
    log_callback: Callable[[str], None],
    stop_event: threading.Event,
) -> None:
    cycle = 0
    try:
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
                log_callback(f"ポーリング {cycle} 回目でエラー: {type(e).__name__}: {e}")
                for line in traceback.format_exc().strip().splitlines():
                    log_callback(f"  {line}")

            if stop_event.wait(poll_interval_seconds):
                break
    finally:
        service.close_driver()
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
        self._icon_image: Optional[tk.PhotoImage] = None
        self._set_window_icon()

        self.config_var = tk.StringVar(value="notion_invite_targets.json")
        self.credentials_var = tk.StringVar(value="credentials.json")
        self.state_file_var = tk.StringVar(value=str(service.state_file))
        self.interval_var = tk.StringVar(value="300")
        self.status_var = tk.StringVar(value="待機中")

        self.log_widget: Optional[tk.Text] = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)


    def _set_window_icon(self) -> None:
        icon_path = resource_path("img/auto.png")
        if not icon_path.exists():
            return
        try:
            self._icon_image = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass
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

    def _on_close(self) -> None:
        self.stop_event.set()
        self.service.close_driver()
        self.root.destroy()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Notion 自動招待（引数なし/--ui でポーリングUI起動、target 指定で単発実行）"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="招待設定名（例: week1_week2）。未指定時は UI を起動",
    )
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
        help="ポーリングUIを起動する（target 未指定時はデフォルトで UI 起動）",
    )
    return parser.parse_args()




def run_ui(state_file: Path) -> None:
    root = tk.Tk()
    service = NotionInviteService(state_file=state_file)
    InvitePollingUI(root, service)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        service.close_driver()
        if root.winfo_exists():
            root.destroy()



def main() -> None:
    args = parse_args()
    if args.ui or args.target is None:
        run_ui(state_file=Path(args.state_file))
        return

    config_path = Path(args.config)
    credentials_path = Path(args.credentials)
    state_file = Path(args.state_file)

    targets = load_targets(config_path)
    target = targets.get(args.target)
    if target is None:
        raise ValueError(f"指定した target が見つかりません: {args.target}")

    service = NotionInviteService(state_file=state_file)
    try:
        invited_count = process_single_target(
            service=service,
            credentials_path=credentials_path,
            target_name=args.target,
            target=target,
            log_callback=print,
        )
        print(f"単発実行完了: target={args.target}, 招待数={invited_count}")
    finally:
        service.close_driver()


if __name__ == "__main__":
    main()
