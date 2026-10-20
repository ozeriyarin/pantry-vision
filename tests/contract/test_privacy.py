"""Principle IV, FR-012, FR-013: no photo contents, captions, owner text or secrets in logs or records."""

import logging

from pantry.domain.models import RunRecord
from tests.conftest import SECRET
from tests.integration.conftest import box


def test_run_record_has_no_image_fields():
    names = set(RunRecord.__dataclass_fields__)
    assert not names & {"image", "photo", "bytes", "data", "crop", "caption", "text"}


def test_logs_hold_no_caption_text_bytes_or_secrets(h, caplog):
    caplog.set_level(logging.DEBUG)
    h.verifier.answers = [RuntimeError("down")]
    h.photo([box("eggs"), box("hummus", score=0.25, i=1)], caption="מקפיא מילה-פרטית")
    h.text("ביצים 3\nקולרבי-פרטי 1")
    h.morning()
    logged = caplog.text
    assert "מילה-פרטית" not in logged and "קולרבי-פרטי" not in logged
    assert SECRET not in logged and "\\xff\\xd8" not in logged


def test_failure_logs_carry_type_not_message(make_client, caplog):
    from tests.conftest import message, post

    def boom(update):
        raise RuntimeError("owner text: קולרבי-פרטי")

    caplog.set_level(logging.DEBUG)
    post(make_client(boom), message(99))
    assert "RuntimeError" in caplog.text and "קולרבי-פרטי" not in caplog.text
