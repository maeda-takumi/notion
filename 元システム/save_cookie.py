from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pickle
import time

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://www.notion.so/login")

print("Notion にログインしてください。ログイン完了後 Enter キーを押してください。")
input()

pickle.dump(driver.get_cookies(), open("notion_cookies.pkl", "wb"))
print("Cookies 保存完了：notion_cookies.pkl")
driver.quit()