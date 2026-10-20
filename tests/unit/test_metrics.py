"""Metrics on hand-computed fixtures (T045)."""

import pytest

from eval.metrics import Pred, Truth, average_precision, evaluate, iou

A = (0.0, 0.0, 10.0, 10.0)
B = (20.0, 0.0, 30.0, 10.0)
C = (40.0, 0.0, 50.0, 10.0)


def test_iou():
    assert iou(A, A) == 1.0
    assert iou(A, B) == 0.0
    assert iou(A, (5.0, 0.0, 15.0, 10.0)) == pytest.approx(50 / 150)


def test_perfect_detections():
    r = evaluate([([Truth("eggs", A), Truth("eggs", B)], [Pred("eggs", A, 0.9), Pred("eggs", B, 0.8)])])
    assert r.map50 == 1.0 and r.count_accuracy == 1.0
    assert (r.items[0].precision, r.items[0].recall) == (1.0, 1.0)


def test_false_positive_ranked_first_halves_precision_at_first_hit():
    # Ranking: FP (0.9), TP (0.8). Recall jumps to 1 at precision 0.5, so AP = 0.5.
    hits = [(0.9, False), (0.8, True)]
    assert average_precision(hits, 1) == 0.5


def test_missed_item_and_wrong_label():
    truths = [Truth("eggs", A), Truth("milk", B)]
    preds = [Pred("eggs", A, 0.9), Pred("jam", B, 0.7)]
    r = evaluate([(truths, preds)])
    scores = {i.key: i for i in r.items}
    assert scores["eggs"].recall == 1.0 and scores["milk"].recall == 0.0
    assert r.map50 == 0.5
    assert r.count_accuracy == 0.5  # eggs count right, milk count wrong


def test_count_accuracy_counts_per_photo_item_occurrence():
    photo1 = ([Truth("eggs", A), Truth("eggs", B)], [Pred("eggs", A, 0.9)])  # 1 of 2 eggs: wrong
    photo2 = ([Truth("eggs", C)], [Pred("eggs", C, 0.9)])  # right
    assert evaluate([photo1, photo2]).count_accuracy == 0.5


def test_duplicate_box_is_a_false_positive():
    r = evaluate([([Truth("eggs", A)], [Pred("eggs", A, 0.9), Pred("eggs", A, 0.8)])])
    assert r.items[0].precision == 0.5 and r.items[0].recall == 1.0
