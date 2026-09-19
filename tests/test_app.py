from pathlib import Path

from streamlit.testing.v1 import AppTest

from .conftest import sample_path

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_prompts_for_upload():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert [i.value for i in at.info] == ["Upload a drawing PDF to begin."]
    assert not at.exception


def test_app_extracts_uploaded_pdf_without_llm(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DQA_CACHE_DIR", str(tmp_path))
    p = sample_path("16807")
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.file_uploader[0].upload(p.name, p.read_bytes(), "application/pdf")
    at.run()
    assert not at.exception
    assert [t.value for t in at.title] == ["TST-SFD-46-01-01-07-000-16807"]
    assert at.metric[0].value.endswith("0 ❌")


def test_app_survives_unreachable_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")      # nothing listens here
    monkeypatch.setenv("DQA_CACHE_DIR", str(tmp_path))
    p = sample_path("16807")
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.file_uploader[0].upload(p.name, p.read_bytes(), "application/pdf")
    at.run()
    assert not at.exception
    assert [t.value for t in at.title] == ["TST-SFD-46-01-01-07-000-16807"]   # extraction never needs OpenAI
    assert at.metric[0].value.endswith("0 ❌")
    run = next(b for b in at.button if b.label.startswith("Run OpenAI step"))
    run.click().run()                                                      # inventory OpenAI step fails...
    assert not at.exception                                                # ...without crashing the page
    shown = " ".join(str(df.value.to_dict()) for df in at.dataframe)
    assert "inventory.llm" in shown                                        # reported as a warning
