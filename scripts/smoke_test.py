"""Offline application smoke test suitable for the built container."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

app = AppTest.from_file(str(ROOT / "main.py"), default_timeout=30).run()
if app.exception:
    raise RuntimeError([error.message for error in app.exception])
app.session_state["active_result"] = {
    "metadata": {"run_id": "smoke", "state": "complete"},
    "reports": [{"source": "Prokal", "status": "success", "count": 1, "issues": []}],
    "data": [{"Tanggal": "2026-11-06", "Judul": "=1+1", "Tagar": "Uji", "Sumber": "Prokal",
              "Isi": "Teks sintetis", "Tautan": "https://www.prokal.co/ekonomi/123/uji"}],
}
app.run()
app.radio[0].set_value("Unduh").run()
next(button for button in app.button if button.label == "Siapkan unduhan").click().run()
if app.exception or len(app.get("download_button")) != 2:
    raise RuntimeError("Aplikasi tidak berhasil menyiapkan unduhan pada smoke test.")
print("Offline UI and export smoke test passed.")
