import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime


BASE_URL = "https://www.yeshiva.org.il/calendar/shabatot?place="

PLACES = [
    ("טבריה", "Tiberias"),
    ("ירושלים", "Jerusalem"),
    ("חיפה", "Haifa"),
    ("הרצליה", "Herzliya"),
]

SHABBAT_PLACES = [
    "Tiberias",
    "Jerusalem",
    "Haifa",
]


OUT_DIR = Path(".")


def get_user_agent(browser):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto("https://example.com")
    ua = page.evaluate("() => navigator.userAgent")
    ctx.close()
    return ua.replace("HeadlessChrome/", "Chrome/")


def create_context(browser, user_agent: str):
    ctx = browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="Asia/Jerusalem",
    )
    ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    return ctx


def fetch_place_data(page, place_he):
    url = BASE_URL + place_he
    page.goto(url)
    page.wait_for_function("() => window.defaultLayoutData !== undefined", timeout=15000)

    return page.evaluate("""
        () => {
            const layout = window.defaultLayoutData.day;
            const shabat = layout.shabat;
            const dailyTimes = layout.times;

            const getTime = (name) =>
                dailyTimes.find(t => t.name === name)?.value;

            const getShabatTime = (name) =>
                shabat.times.find(t => t.name === name)?.value;

            return {
                parsha: shabat.shabat_prefix + " " + shabat.shabat_name,
                shabatIn: getShabatTime("כניסת שבת"),
                shabatOut: getShabatTime("צאת שבת"),
                netz: getTime("הנץ החמה"),
                chatzot: getTime("חצות היום"),
                shkiah: getTime("שקיעה"),
                tzet: getTime("צאת הכוכבים"),
                chatzotLayla: getTime("חצות הלילה"),
                shaharitEnd: getTime('סוף זמן תפילה לגר"א'),
                alotHaShahar: getTime('עלות השחר 72 דקות'),
            };
        }
    """)


def write_place_times(place_en, data):
    slug = place_en.lower()
    today = datetime.now().strftime("%d/%m/%Y")

    # todo format:
    #  shaharit: netz - shaharitEnd
    #  shaharit Bediavad: shaharitEnd - chatzot
    #  minha - chatzot + 30 - shkiah
    #  arvit - tzet - chatzotLayla
    #  arvit bediavad: chatzotLayla - alotHaShahar

    content = (
        f"{today}\n"
        f"הנץ החמה - {data['netz']}\n"
        f"חצות היום - {data['chatzot']}\n"
        f"שקיעה - {data['shkiah']}\n"
        f"צאת הכוכבים - {data['tzet']}\n"
        f"חצות הלילה - {data['chatzotLayla']}\n"
    )
    (OUT_DIR / f"{slug}_times.txt").write_text(content, encoding="utf-8")


def write_shabbat_times(parsha, lines):
    content = (
        f"{parsha}\n" +
        "\n".join(f"{line}" for line in lines) +
        "\n"
    )
    (OUT_DIR / "shabbat_times.txt").write_text(content, encoding="utf-8")


def write_last_update():
    now = int(time.time())
    (OUT_DIR / "last_update_time.txt").write_text(str(now), encoding="utf-8")


def run():
    shabbat_lines = []
    parsha_name = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        user_agent = get_user_agent(browser)
        context = create_context(browser, user_agent)

        for place_he, place_en in PLACES:
            try:
                page = context.new_page()
                data = fetch_place_data(page, place_he)
                page.close()

                print(data)

                if not parsha_name:
                    parsha_name = data["parsha"].replace("שבת", "פרשת", 1)

                write_place_times(place_en, data)

                if place_en in SHABBAT_PLACES:
                    shabbat_lines.append(
                        f"{data['shabatIn']} - {data['shabatOut']}  {place_he}"
                    )

            except PlaywrightTimeoutError:
                print(f"Timeout fetching data for {place_he}")
            except Exception as e:
                print(f"Error fetching {place_he}: {e}")

        context.close()
        browser.close()

    if parsha_name and shabbat_lines:
        write_shabbat_times(parsha_name, shabbat_lines)

    write_last_update()


if __name__ == "__main__":
    run()
