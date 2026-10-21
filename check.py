import json
import os
import sys

import requests
from playwright.sync_api import sync_playwright

URL = "https://cologne.pasport.org.ua/solutions/e-queue"
TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]
MANUAL = os.environ.get("MANUAL") == "true"
STATE = "state.json"


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text},
        timeout=30,
    )


def find_form(page):
    for fr in page.frames:
        if fr.locator("select").count() >= 2:
            return fr
    return None


def diagnose(page):
    print("--- DIAGNOSTIC ---")
    print("title:", page.title())
    print("url:", page.url)
    print("frames:", [f.url for f in page.frames])
    for fr in page.frames:
        print(
            "frame",
            fr.url[:60],
            "select:", fr.locator("select").count(),
            "input:", fr.locator("input").count(),
            "button:", fr.locator("button").count(),
        )
    try:
        print("text:", page.inner_text("body")[:700].replace("\n", " | "))
    except Exception as e:
        print("no text:", e)
    print("--- END ---")


def get_days():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="uk-UA")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(6000)
            form = find_form(page)
            if form is None:
                diagnose(page)
                raise RuntimeError("Не нашёл выпадающие списки на странице")

            selects = form.locator("select")
            selects.nth(0).select_option(index=1)
            page.wait_for_timeout(4000)

            options = selects.nth(1).locator("option")
            days = []
            for i in range(options.count()):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                if not text or text.lower().startswith("обрати"):
                    continue
                if opt.get_attribute("disabled") is not None:
                    continue
                days.append(text)
            return days
        finally:
            with open("page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            page.screenshot(path="screenshot.png", full_page=True)
            browser.close()


def main():
    try:
        days = get_days()
    except Exception as e:
        if MANUAL:
            tg(f"Ошибка при проверке: {e}")
        print("ERROR:", e)
        sys.exit(1)

    try:
        with open(STATE, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = []

    if MANUAL:
        tg(f"Бот работает. Сейчас доступных дней: {len(days)}")

    if days and days != old:
        tg("Появились места в Кельне!\n" + "\n".join(days) + "\n\n" + URL)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(days, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
