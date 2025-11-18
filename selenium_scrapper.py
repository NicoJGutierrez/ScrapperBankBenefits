from selenium import webdriver
from selenium.webdriver import Chrome
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
from itertools import zip_longest

service = Service(ChromeDriverManager().install())
options = webdriver.ChromeOptions()
# options.add_argument("--headless=new")
driver = Chrome(service=service, options=options)
driver.get(
    "https://sitiospublicos.bancochile.cl/personas/beneficios/beneficios-del-dia")
time.sleep(5)
elements = driver.find_elements(by=webdriver.common.by.By.CSS_SELECTOR,
                                value=".font-700.text-3.text-gray-dark.mb-2.overflow-ellipsis")
descriptions = driver.find_elements(by=webdriver.common.by.By.CSS_SELECTOR,
                                    value=".font-700.text-3.text-primary.mb-2.overflow-ellipsis")
descriptions2 = driver.find_elements(by=webdriver.common.by.By.CSS_SELECTOR,
                                     value=".overflow-ellipsis.mb-2.text-2.text-gray")

for el, desc, desc2 in zip_longest(elements, descriptions, descriptions2, fillvalue=None):
    el_text = el.text.strip() if el else ""
    desc_text = desc.text.strip() if desc else ""
    desc2_text = desc2.text.strip() if desc2 else ""
    print(f"{el_text} - {desc_text} {desc2_text}")

driver.quit()
