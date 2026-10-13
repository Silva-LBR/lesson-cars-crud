import re

from playwright.sync_api import expect


def test_user_creates_car_in_browser(page, live_server):
    page.goto(f"{live_server}/cars/new")
    page.get_by_label("Make", exact=True).fill("Toyota")
    page.get_by_label("Model", exact=True).fill("Yaris")
    page.get_by_label("Year", exact=True).fill("2020")
    page.get_by_label("Color", exact=False).fill("Blue")
    page.get_by_role("button", name="Create car").click()

    expect(page).to_have_url(re.compile(r"/cars/\d+$"))
    expect(page.get_by_role("heading", name="Toyota Yaris")).to_be_visible()


def test_user_edits_car_and_change_survives_reload(page, live_server):
    # DIAGNOSTIC: remove these listeners once the CI failure is understood.
    # They record the HTTP calls the page makes and any JavaScript errors.
    events = []

    def on_request(request):
        # DIAGNOSTIC: the body of the PUT is what distinguishes "saved the old
        # values" from "the backend did not persist the new values".
        if request.method == "PUT":
            events.append(f"REQ  PUT {request.url} body={request.post_data}")

    def on_response(response):
        line = f"RESP {response.status} {response.request.method} {response.url}"
        # DIAGNOSTIC: bodies of the write requests, plus the car GET that
        # loadForm() uses to populate the edit form.
        if response.request.method in ("PUT", "POST") or response.url.endswith(
            "/api/cars/1"
        ):
            try:
                line += f"  body={response.text()[:200]}"
            except Exception as exc:  # noqa: BLE001
                line += f"  <body unreadable: {exc}>"
        events.append(line)

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("pageerror", lambda e: events.append(f"JSERR {e}"))

    page.goto(f"{live_server}/cars/new")
    page.get_by_label("Make", exact=True).fill("Honda")
    page.get_by_label("Model", exact=True).fill("Civic")
    page.get_by_label("Year", exact=True).fill("2022")
    page.get_by_role("button", name="Create car").click()
    expect(page.get_by_role("heading", name="Honda Civic")).to_be_visible()

    page.get_by_role("link", name="Edit car").click()
    page.get_by_label("Model", exact=True).fill("Accord")
    page.get_by_label("Year", exact=True).fill("2023")

    # DIAGNOSTIC: what the form fields actually hold right before saving.
    print(
        "=== FORM STATE BEFORE SAVE ===",
        page.evaluate(
            "() => ({model: document.querySelector('#model').value,"
            " year: document.querySelector('#year').value})"
        ),
    )

    page.get_by_role("button", name="Save changes").click()

    # DIAGNOSTIC: remove this try/except once the CI failure is understood.
    # It prints what the page actually looked like at the moment of failure
    # and saves a screenshot that the workflow uploads as an artifact.
    try:
        expect(page.get_by_role("heading", name="Honda Accord")).to_be_visible()
    except AssertionError:
        print("=== E2E DIAGNOSTIC ===")
        print("URL  :", page.url)
        print("TITLE:", page.title())
        try:
            print("H1   :", page.locator("h1").first.inner_text())
        except Exception as exc:  # noqa: BLE001
            print("H1   : <unreadable>", exc)
        try:
            error_text = page.locator("#error").first.inner_text()
            print("ERROR:", repr(error_text))
        except Exception as exc:  # noqa: BLE001
            print("ERROR: <unreadable>", exc)
        try:
            page.screenshot(path="e2e-failure.png", full_page=True)
            print("SHOT : e2e-failure.png")
        except Exception as exc:  # noqa: BLE001
            print("SHOT : <failed>", exc)
        print("BODY :", page.locator("body").inner_text()[:400].replace("\n", " | "))
        print("--- HTTP / JS EVENTS ---")
        for line in events:
            print(line)
        print("=== END DIAGNOSTIC ===")
        raise

    page.reload()
    expect(page.locator("#car-model")).to_have_text("Accord")
    expect(page.locator("#car-year")).to_have_text("2023")
