import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import pickle
from datetime import datetime, timedelta

# ---------------------------------------------------
# Google スプレッドシート設定
# ---------------------------------------------------
SPREADSHEET_KEY = "1TZ1pYTjgRwuLcGWMj-2FfWouK46w7lJiu-fhIwWOuig"
SHEET_NAME = "シート1"
NEXT_SHEET_NAME = "week14"

# Notion 招待対象ページ（短縮URLでもOK）
NOTION_PAGE_URL = "https://www.notion.so/AI-Week-2c38252adfa780f592bbd6868bace9fa"


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

    share_btn = driver.find_element(By.XPATH, "//div[contains(text(),'共有')]")
    share_btn.click()
    time.sleep(2)

    email_input = driver.find_element(
        By.XPATH, "//input[@placeholder='カンマで区切ったメールアドレスまたはグループ']"
    )
    email_input.send_keys(email)
    time.sleep(2)

    role_btn = driver.find_element(
        By.XPATH,
        "//div[@role='button'][.//span[contains(text(),'フルアクセス権限')]]"
    )
    role_btn.click()
    time.sleep(1)

    view_btn = driver.find_element(
        By.XPATH,
        "//div[@role='menuitem']//div[contains(text(),'読み取り権限')]"
    )
    view_btn.click()
    time.sleep(1)

    invite_btn = driver.find_element(
        By.XPATH,
        "//div[@role='button' and contains(text(),'招待')]"
    )
    invite_btn.click()
    time.sleep(2)

    driver.quit()
    print(f"招待完了：{email}")


# ---------------------------------------------------
# Google シート操作：招待後に Week14 シートに書き込む
# ---------------------------------------------------
def write_to_next_sheet(sheet_next, email):
    today = datetime.now()
    future_date = today + timedelta(days=6)

    sheet_next.append_row([
        email,
        future_date.strftime("%Y/%m/%d")
    ])

    print(f" → Week14 シートに登録：{email}, {future_date.strftime('%Y/%m/%d')}")


# ---------------------------------------------------
# Google シートからメール取得 → 招待 → ステータス更新 → 次シートへ転記
# ---------------------------------------------------
def main():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
    sheet_next = client.open_by_key(SPREADSHEET_KEY).worksheet(NEXT_SHEET_NAME)

    data = sheet.get_all_values()

    for i in range(1, len(data)):
        # L列：メールアドレス
        email = data[i][11] if len(data[i]) >= 12 else ""

        # M列：面談ステータス
        interview_status = data[i][12] if len(data[i]) >= 13 else ""

        # N列：招待ステータス
        invite_status = data[i][13] if len(data[i]) >= 14 else ""

        # ---- 実行条件 ----
        if (
            email.strip() == "" or
            interview_status != "面談済み" or
            invite_status == "招待済み"
        ):
            continue

        # --- Notion 招待 ---
        invite_guest(email)

        # --- 招待済みを N列に記録 ---
        sheet.update_cell(i + 1, 14, "招待済み")

        # --- 次シート（week14）へ登録（列構成は変更なし） ---
        write_to_next_sheet(sheet_next, email)

if __name__ == "__main__":
    main()
