"""Pipeline band selection and the budgeted fallback (FR-003, FR-004, research R2)."""

from pantry.config import load_settings
from pantry.detection.fallback import Fallback, VerifyFailed
from pantry.detection.pipeline import Pipeline
from pantry.domain.models import Budget, Detection, FallbackResult
from tests.fakes import FakeClock, FakeDetector, FakeVerifier, InMemoryStore
from tests.images import jpeg

KEYS = ["eggs", "milk", "hummus"]


def det(key, score, i=0):
    return Detection(key, (10.0 + 50 * i, 10.0, 50.0 + 50 * i, 60.0), score)


def make(detections, answers=(), budget=None):
    settings = load_settings({})
    store, clock = InMemoryStore(), FakeClock()
    if budget is not None:
        store.budgets[clock.now().strftime("%Y-%m")] = budget
    verifier = FakeVerifier(list(answers))
    image = jpeg(1)
    detector = FakeDetector({image: detections})
    fallback = Fallback(verifier, store, clock, settings.fallback, settings.crop)
    return Pipeline(detector, fallback, settings), image, verifier, store


def test_only_band_scores_go_to_fallback():
    """Constitution II: the fallback sees only crops below the threshold, never the whole photo."""
    pipeline, image, verifier, _ = make(
        [det("eggs", 0.9), det("milk", 0.2, 1), det("hummus", 0.05, 2)],
        answers=[FallbackResult("milk", 1, 0.0001)],
    )
    result = pipeline.run(image, KEYS)
    assert verifier.calls == 1
    assert set(result.items) == {"eggs", "milk"}
    assert not result.items["milk"].uncertain and result.items["milk"].source == "fallback"


def test_spend_at_or_above_cap_skips_the_call():
    pipeline, image, verifier, _ = make([det("milk", 0.2)], budget=Budget("x", 1.0, 3, 1.0))
    result = pipeline.run(image, KEYS)
    assert verifier.calls == 0 and result.skipped == 1
    assert result.items["milk"].uncertain


def test_cost_added_to_budget_and_result():
    pipeline, image, _, store = make([det("milk", 0.2)], answers=[FallbackResult("milk", 1, 0.0002)])
    result = pipeline.run(image, KEYS)
    month = FakeClock().now().strftime("%Y-%m")
    assert store.budgets[month].spent_usd == 0.0002 and store.budgets[month].calls == 1
    assert result.cost_usd == 0.0002 and result.fallback_calls == 1


def test_refusal_and_errors_leave_item_uncertain_and_still_bill_refusal():
    pipeline, image, _, store = make(
        [det("milk", 0.2), det("hummus", 0.2, 1)],
        answers=[VerifyFailed("refusal", 0.0001), RuntimeError("api down")],
    )
    result = pipeline.run(image, KEYS)
    assert result.items["milk"].uncertain and result.items["hummus"].uncertain
    assert result.skipped == 2 and result.cost_usd == 0.0001


def test_verifier_none_drops_the_box():
    pipeline, image, _, _ = make([det("milk", 0.2)], answers=[FallbackResult("none", 0, 0.0001)])
    assert pipeline.run(image, KEYS).status == "empty"


def test_verifier_can_relabel_and_count():
    pipeline, image, _, _ = make([det("milk", 0.2)], answers=[FallbackResult("eggs", 3, 0.0001)])
    items = pipeline.run(image, KEYS).items
    assert items["eggs"].count == 3 and "milk" not in items


def test_cost_formula_from_usage():
    from pantry.adapters.anthropic_verifier import cost_usd

    assert round(cost_usd(600, 30, 0.10, 0.50), 9) == 0.000075


def test_calls_per_photo_are_capped_and_highest_scores_go_first():
    """Security review: one photo with many uncertain boxes must not make unbounded paid calls."""
    dets = [det("milk", 0.20 + i * 0.007, i % 5) for i in range(20)]
    answers = [FallbackResult("milk", 1, 0.0001)] * 8
    pipeline, image, verifier, _ = make(dets, answers=answers)
    result = pipeline.run(image, KEYS)
    assert verifier.calls == 8 and result.fallback_calls == 8 and result.skipped == 12
    verified_scores = sorted(d.score for d in result.detections if d.fallback)
    assert verified_scores[0] >= 0.28


def test_calls_limited_by_remaining_budget():
    dets = [det("milk", 0.2, i) for i in range(5)]
    budget = Budget("x", 0.9996, 3, 1.0)  # room for 2 calls at 0.0002
    pipeline, image, verifier, _ = make(dets, answers=[FallbackResult("milk", 1, 0.0001)] * 2, budget=budget)
    result = pipeline.run(image, KEYS)
    assert verifier.calls == 2 and result.skipped == 3
