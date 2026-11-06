"""Browser regression check using isolated local pages and synthetic news.

python scripts/check_ui.py --channel chrome --output test-results/ui
Omit --channel to use Playwright's installed Chromium. No scraping is started.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def luminance(rgb):
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in (c / 255 for c in rgb)]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(foreground, background):
    values = [luminance([int(c) for c in re.findall(r"\d+", value)[:3]]) for value in (foreground, background)]
    return (max(values) + 0.05) / (min(values) + 0.05)


def inspect(browser, base_url, output, name, width, height, *, results=False, preference="light"):
    context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=preference,
                                  reduced_motion="reduce")
    # Block any external HTTP resource; news links are never followed.
    context.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname == "127.0.0.1" else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base_url + ("?scenario=results" if results else ""))
    page.get_by_role("heading", name="Fantastik Bulungan", exact=True).wait_for()
    if results:
        page.get_by_role("radio", name="Tabel", exact=True).wait_for()
    else:
        page.get_by_role("button", name="Kumpulkan berita", exact=True).wait_for()
    page.evaluate("document.fonts.ready")
    record = {"scenario": name, "viewport": {"width": width, "height": height}, "preference": preference}
    record["main"] = page.get_by_test_id("stMain").evaluate("e=>({width:e.clientWidth,scrollWidth:e.scrollWidth})")
    assert record["main"]["scrollWidth"] <= record["main"]["width"], f"Horizontal page overflow: {name}"
    if results:
        table = page.locator('[data-testid="stDataFrame"]:visible')
        table.wait_for()
        assert table.count() == 1
        record["table"] = table.bounding_box()
        assert record["table"]["y"] < height, f"Table starts below the first viewport: {name}"
        assert page.get_by_role("textbox", name="Cari dalam hasil", exact=True).is_visible()
    else:
        field = page.get_by_role("spinbutton", name="day, Tanggal awal", exact=True)
        colors = field.evaluate("""e=>{const color=getComputedStyle(e).color;let a=e;
          while(a){const background=getComputedStyle(a).backgroundColor;
            if(background!=='rgba(0, 0, 0, 0)'&&background!=='transparent')return {color,background};
            a=a.parentElement;}throw Error('Missing field background');}""")
        record["date_contrast"] = contrast(colors["color"], colors["background"])
        assert record["date_contrast"] >= 4.5, f"Unreadable date: {name}: {colors}"
        field.focus()
        page.keyboard.press("Tab")
        focus = page.evaluate("""()=>{const e=document.activeElement,s=getComputedStyle(e);
            return {role:e.getAttribute('role'),outline:s.outlineStyle,width:s.outlineWidth};}""")
        assert focus["role"] == "spinbutton" and focus["outline"] != "none", f"Missing date keyboard focus: {focus}"
        record["keyboard_focus"] = focus
        page.keyboard.press("Escape")
        button_colors = page.get_by_role("button", name="Kumpulkan berita", exact=True).evaluate(
            "e=>({color:getComputedStyle(e.querySelector('p')||e).color,background:getComputedStyle(e).backgroundColor})")
        record["primary_button_contrast"] = contrast(button_colors["color"], button_colors["background"])
        assert record["primary_button_contrast"] >= 4.5, f"Unreadable primary action: {button_colors}"
    page.screenshot(path=str(output / f"{name}.png"))
    (output / f"{name}.aria.txt").write_text(page.locator("body").aria_snapshot(), encoding="utf-8")
    if name in {"desktop-results", "mobile-results", "narrow-results"}:
        # Click the visible text label: the native radio input is visually covered.
        label = page.get_by_role("radiogroup", name="Tampilan hasil", exact=True).get_by_text("Detail", exact=True)
        assert label.count() == 1
        label.click()
        page.get_by_text("Pilih berita", exact=True).wait_for()
        page.locator(".article-title").wait_for()
        page.locator(".article-body").wait_for()
        next_button = page.get_by_role("button", name="Berikutnya", exact=True)
        assert next_button.is_enabled()
        next_button.click()
        page.get_by_text("Berita 2 dari 40", exact=True).wait_for()
        page.get_by_role("heading", name="Berita contoh 2: Kegiatan ekonomi dan usaha masyarakat", exact=True).wait_for()
        article_main = page.get_by_test_id("stMain").evaluate("e=>({width:e.clientWidth,scrollWidth:e.scrollWidth})")
        assert article_main["scrollWidth"] <= article_main["width"], f"Article overflow: {name}"
        title = page.locator(".article-title").bounding_box()
        page.get_by_test_id("stMain").evaluate("(e,y)=>e.scrollTop+=y-80", title["y"])
        page.screenshot(path=str(output / f"{name.replace('results', 'detail')}.png"))
        record["article_navigation"] = "passed"
    assert not errors, errors
    context.close()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", type=Path, default=ROOT / "test-results/ui")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fantastik-ui-") as temporary:
        temporary = Path(temporary)
        wrapper = temporary / "preview.py"
        wrapper.write_text(
            f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nsys.path.insert(0, {str(ROOT / 'tests')!r})\n"
            "import streamlit as st\nfrom ui_fixture import preview_result\nimport main\n"
            "if st.query_params.get('scenario') == 'results' and 'active_result' not in st.session_state:\n"
            "    st.session_state.active_result = preview_result()\nmain.main()\n", encoding="utf-8")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        with (temporary / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [args.python, "-m", "streamlit", "run", str(wrapper), "--server.address", "127.0.0.1",
                 "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
            try:
                for _ in range(100):
                    try:
                        with urlopen(base_url + "/_stcore/health", timeout=1):
                            break
                    except OSError:
                        if process.poll() is not None:
                            raise RuntimeError((temporary / "server.log").read_text(encoding="utf-8"))
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Preview did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel=args.channel, headless=True)
                    browser_version = browser.version
                    try:
                        records = []
                        for name, width, height, results, preference in [
                            ("desktop-empty", 1440, 900, False, "light"),
                            ("desktop-results", 1440, 900, True, "light"),
                            ("mobile-results", 390, 844, True, "light"),
                            ("narrow-results", 320, 844, True, "light"),
                            ("mobile-empty", 390, 844, False, "light"),
                            ("dark-preference", 390, 844, False, "dark"),
                        ]:
                            records.append(inspect(browser, base_url, output, name, width, height,
                                                   results=results, preference=preference))
                    finally:
                        browser.close()
                (output / "verification.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
                manifest = {"python": sys.version.split()[0], "browser": browser_version,
                            "channel": args.channel or "chromium", "playwright": importlib.metadata.version("playwright"),
                            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                              for name in ["main.py", "styles/style.css", ".streamlit/config.toml",
                                                           "helper/presentation.py", "scripts/check_ui.py", "tests/ui_fixture.py"]}}
                (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(records))
            finally:
                if os.name == "nt":
                    # Windows venv python.exe can be a launcher whose child owns
                    # the server/socket/log. Stop only this spawned process tree.
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
