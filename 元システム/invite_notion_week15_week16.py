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
SHEET_NAME = "week16"
NEXT_SHEET_NAME = "week17"

# Notion 招待対象ページ
NOTION_PAGE_URL = "https://www.notion.so/AI-Week-Etsy-Printify-2ab8252adfa780e2ba79c197097a7469"


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
# 次シートへ転記
# ---------------------------------------------------
def write_to_next_sheet(sheet_next, email):
    today = datetime.now()
    future_date = today + timedelta(days=6)

    sheet_next.append_row([
        email,
        future_date.strftime("%Y/%m/%d")
    ])

    print(f" → Week16 シートに登録：{email}, {future_date.strftime('%Y/%m/%d')}")


# ---------------------------------------------------
# メイン処理
# ---------------------------------------------------
def main():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
    sheet_next = client.open_by_key(SPREADSHEET_KEY).worksheet(NEXT_SHEET_NAME)

    data = sheet.get_all_values()

    today = datetime.now().date()

    for i in range(1, len(data)):
        email = data[i][0].strip() if len(data[i]) >= 1 else ""
        invite_date_str = data[i][1].strip() if len(data[i]) >= 2 else ""
        status = data[i][2].strip() if len(data[i]) >= 3 else ""

        # メールが空 or 招待済みならスキップ
        if email == "" or status == "招待済み":
            continue

        # B列：招待開始日が空ならスキップ
        if invite_date_str == "":
            print(f"{email}：開始日が空のためスキップ")
            continue

        # 日付チェック
        try:
            invite_date = datetime.strptime(invite_date_str, "%Y/%m/%d").date()
        except:
            print(f"{email}：日付形式エラーのためスキップ → {invite_date_str}")
            continue

        if today < invite_date:
            print(f"{email}：{invite_date} 以降のためまだ招待しません")
            continue

        # --- Notion 招待 ---
        invite_guest(email)

        # --- C列へ「招待済み」書き込み ---
        sheet.update_cell(i + 1, 3, "招待済み")

        # --- 次シート（week15Etsy送信用）へ追記 ---
        write_to_next_sheet(sheet_next, email)


if __name__ == "__main__":
    main()
