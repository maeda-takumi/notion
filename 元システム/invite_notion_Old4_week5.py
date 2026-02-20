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

# ---------------------------------------------------
# Google スプレッドシート設定（変更）
# ---------------------------------------------------
SPREADSHEET_KEY = "1vfHpZbwC-KlEB5q4zbzpuyFhbf5P9dd96ZoCCa4lSq8"
SHEET_GID = 1376074701  # URLの gid
SHEET_NAME = "シート1"   # シート名が違う場合はここを変更してください

# Notion 招待対象ページ（短縮URLでもOK）
NOTION_PAGE_URL = "https://www.notion.so/AI-Week5-Notion-2a98252adfa78023a320ffe0ff1ad5ca"

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
# Notion 招待処理（日本語UI対応版）
# ---------------------------------------------------
def invite_guest(email: str):
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    try:
        # ① loginページを開いて Cookie でログイン
        login_with_cookie(driver)

        # ② ログイン状態で招待ページへ移動
        driver.get(NOTION_PAGE_URL)
        time.sleep(4)

        # ③ Share ボタン
        share_btn = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(@class,'notion-topbar-share-menu')]"))
        )
        driver.execute_script("arguments[0].click();", share_btn)
        time.sleep(2)

        # ④ メールアドレスを入力
        email_input = driver.find_element(
            By.XPATH, "//input[@placeholder='カンマで区切ったメールアドレスまたはグループ']"
        )
        email_input.send_keys(email)
        time.sleep(2)

        # ⑤ 権限ドロップダウン（フルアクセス権限）クリック
        role_btn = driver.find_element(
            By.XPATH,
            "//div[@role='button'][.//span[contains(text(),'フルアクセス権限')]]"
        )
        role_btn.click()
        time.sleep(1)

        # ⑥ 「読み取り権限」を選択
        view_btn = driver.find_element(
            By.XPATH,
            "//div[@role='menuitem']//div[contains(text(),'読み取り権限')]"
        )
        view_btn.click()
        time.sleep(1)

        # ⑦ 「招待」ボタンをクリック
        invite_btn = driver.find_element(
            By.XPATH,
            "//div[@role='button' and contains(text(),'招待')]"
        )
        invite_btn.click()
        time.sleep(2)

        print(f"招待完了：{email}")

    finally:
        driver.quit()

# ---------------------------------------------------
# Google シートからメール取得 → 招待 → ステータス更新
# ---------------------------------------------------
def main():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    # どのシートか曖昧になりがちなので、基本は「名前」で取ります
    # シート名が不明なら、下の「gidで探す」方式に切り替え可能です
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)

    data = sheet.get_all_values()

    EMAIL_COL = 12   # L列（1始まり）
    STATUS_COL = 13  # M列（1始まり）※ステータスはM列に書く（L列はメールなので潰さない）

    for i in range(1, len(data)):  # 1行目はヘッダー想定
        row = data[i]

        email = row[EMAIL_COL - 1] if len(row) >= EMAIL_COL else ""
        status = row[STATUS_COL - 1] if len(row) >= STATUS_COL else ""

        if email.strip() == "":
            continue
        if status.strip() == "招待済み":
            continue

        invite_guest(email.strip())

        # M列に「招待済み」を書き込む
        sheet.update_cell(i + 1, STATUS_COL, "招待済み")

if __name__ == "__main__":
    main()
