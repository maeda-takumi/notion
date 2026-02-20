import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pickle
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------
# Google スプレッドシート設定
# ---------------------------------------------------
SPREADSHEET_KEY = "1OZMS0_7l4oum7JtIZR2WKoqb8-YNB4cBffrD9dcMGjc"
SHEET_NAME = "Week1送信用"

# Notion 招待対象ページ
NOTION_PAGE_URL = "https://www.notion.so/AI-Week1-ChatGPT-2a38252adfa7801b8554ff5febd9d378"


# ---------------------------------------------------
# 日付+時刻 文字列を datetime に変換（複数フォーマット対応）
# ---------------------------------------------------
def parse_scheduled_datetime(date_str: str, time_str: str):
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()

    if not date_str or not time_str:
        return None

    # よくある入力形式に対応（必要なら追加できます）
    patterns = [
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H時%M分",
        "%Y/%m/%d %H:%M:%S",
    ]

    dt_text = f"{date_str} {time_str}"

    for p in patterns:
        try:
            return datetime.strptime(dt_text, p)
        except ValueError:
            continue

    # 時間が "9:00" のようにゼロ埋め無しでも来る場合があるので補正（簡易）
    try:
        # 例: 2026/01/19 9:00 -> 2026/01/19 09:00
        parts = time_str.split(":")
        if len(parts) >= 2:
            hh = parts[0].zfill(2)
            mm = parts[1].zfill(2)
            ss = parts[2].zfill(2) if len(parts) >= 3 else None
            t = f"{hh}:{mm}" + (f":{ss}" if ss else "")
            dt_text2 = f"{date_str} {t}"
            for p in ["%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(dt_text2, p)
                except ValueError:
                    continue
    except Exception:
        pass

    return None


# ---------------------------------------------------
# Notion クッキーによるログイン
# ---------------------------------------------------
def login_with_cookie(driver):
    driver.get("https://www.notion.so/login")
    time.sleep(2)

    cookies = pickle.load(open("notion_cookies.pkl", "rb"))

    for c in cookies:
        try:
            driver.add_cookie(c)
        except:
            pass

    driver.get("https://www.notion.so/login")
    time.sleep(3)


# ---------------------------------------------------
# Notion 招待処理
# ---------------------------------------------------
def invite_guest(email):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    login_with_cookie(driver)

    driver.get(NOTION_PAGE_URL)
    time.sleep(4)

    # Share（共有）ボタン（安定版）
    share_btn = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(@class,'notion-topbar-share-menu')]"))
    )
    driver.execute_script("arguments[0].click();", share_btn)
    time.sleep(2)

    # メール入力
    email_input = driver.find_element(
        By.XPATH, "//input[@placeholder='カンマで区切ったメールアドレスまたはグループ']"
    )
    email_input.send_keys(email)
    time.sleep(2)

    # 権限ドロップダウン（フルアクセス権限）
    role_btn = driver.find_element(
        By.XPATH, "//div[@role='button'][.//span[contains(text(),'フルアクセス権限')]]"
    )
    role_btn.click()
    time.sleep(1)

    # 読み取り権限
    view_btn = driver.find_element(
        By.XPATH, "//div[@role='menuitem']//div[contains(text(),'読み取り権限')]"
    )
    view_btn.click()
    time.sleep(1)

    # 招待
    invite_btn = driver.find_element(
        By.XPATH, "//div[@role='button' and contains(text(),'招待')]"
    )
    invite_btn.click()
    time.sleep(2)

    driver.quit()
    print(f"招待完了：{email}")


# ---------------------------------------------------
# メイン処理
# ---------------------------------------------------
def main():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)

    data = sheet.get_all_values()
    now = datetime.now()

    for i in range(1, len(data)):
        row = data[i]

        # A列: 日付 / B列: 時間
        date_str = row[0] if len(row) >= 1 else ""
        time_str = row[1] if len(row) >= 2 else ""

        # C列: メールアドレス
        email = row[2] if len(row) >= 3 else ""

        # E列: ステータス
        status = row[4] if len(row) >= 5 else ""

        if email.strip() == "":
            continue

        if status == "招待済み":
            continue

        # A列とB列が両方入っている場合のみ「日時を過ぎたら実行」
        scheduled_dt = parse_scheduled_datetime(date_str, time_str)
        if scheduled_dt is not None and now < scheduled_dt:
            print(f"スキップ（未到来）: {email} / {scheduled_dt.strftime('%Y-%m-%d %H:%M')}")
            continue

        # --- Notion 招待 ---
        invite_guest(email)

        # --- E列に「招待済み」 ---
        sheet.update_cell(i + 1, 5, "招待済み")



if __name__ == "__main__":
    main()
