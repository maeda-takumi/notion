import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pickle

# ---------------------------------------------------
# Google スプレッドシート設定
# ---------------------------------------------------
SPREADSHEET_KEY = "1IBGD-u-qxl7UF7WlXCmM9a_nT6ZE8UtmyndaLW1yJ4w"
SHEET_NAME = "シート1"

# Notion 招待対象ページ（短縮URLでもOKにする）
NOTION_PAGE_URL = "https://www.notion.so/AI-Week2-ChatGPT-2a48252adfa7804dac3bd02f9418a375"

# ---------------------------------------------------
# Notion クッキーによるログイン
# ---------------------------------------------------
def login_with_cookie(driver):
    # 必ず .so/login を最初に開く（ここはリダイレクトされない）
    driver.get("https://www.notion.so/login")
    time.sleep(2)

    cookies = pickle.load(open("notion_cookies.pkl", "rb"))

    for c in cookies:
        try:
            driver.add_cookie(c)
        except:
            pass

    # Cookieを入れた状態でもう一度開き直す（確実にログイン状態になる）
    driver.get("https://www.notion.so/login")
    time.sleep(3)

# ---------------------------------------------------
# Notion 招待処理（日本語UI対応版）
# ---------------------------------------------------
def invite_guest(email):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    # ① loginページを開いて Cookie でログイン
    login_with_cookie(driver)

    # ② ログイン状態で招待ページへ移動（ここで短縮URLでも動く）
    driver.get(NOTION_PAGE_URL)
    time.sleep(4)

    # ③ Share ボタン
    share_btn = WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.XPATH, "//*[contains(@class,'notion-topbar-share-menu')]"))
    )
    driver.execute_script("arguments[0].click();", share_btn)
    time.sleep(2)

    # ④ メールアドレスを入力（Enter は押さない）
    email_input = driver.find_element(
        By.XPATH, "//input[@placeholder='カンマで区切ったメールアドレスまたはグループ']"
    )
    email_input.send_keys(email)
    time.sleep(2)

    # -------------------------------------------------------
    # ⑤ 権限ドロップダウン（フルアクセス権限）クリック
    # -------------------------------------------------------
    role_btn = driver.find_element(
        By.XPATH,
        "//div[@role='button'][.//span[contains(text(),'フルアクセス権限')]]"
    )
    role_btn.click()
    time.sleep(1)

    # -------------------------------------------------------
    # ⑥ 「読み取り権限」を選択（あなたのHTML専用）
    # -------------------------------------------------------
    view_btn = driver.find_element(
        By.XPATH,
        "//div[@role='menuitem']//div[contains(text(),'読み取り権限')]"
    )
    view_btn.click()
    time.sleep(1)

 # -------------------------------------------------------
    # ⑦ 「招待」ボタンをクリック
    # -------------------------------------------------------
    invite_btn = driver.find_element(
        By.XPATH,
        "//div[@role='button' and contains(text(),'招待')]"
    )
    invite_btn.click()
    time.sleep(2)

    driver.quit()
    print(f"招待完了：{email}")

# ---------------------------------------------------
# Google シートからメール取得 → 招待 → ステータス更新
# ---------------------------------------------------
def main():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)

    data = sheet.get_all_values()

    for i in range(1, len(data)):
        # L列（index 11）からメールアドレスを取得
        email = data[i][11] if len(data[i]) >= 12 else ""

        # M列（index 12）に「招待済み」があるか確認
        status = data[i][12] if len(data[i]) >= 13 else ""

        if status == "招待済み" or email.strip() == "":
            continue

        invite_guest(email)

        # M列に「招待済み」を書き込む
        sheet.update_cell(i + 1, 13, "招待済み")

if __name__ == "__main__":
    main()
