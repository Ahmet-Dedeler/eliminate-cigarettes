import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from classify import Category, Confidence, classify  # noqa: E402


def test_corroborating_topic_with_comma_is_recognised():
    v = classify("Mystery Vapes LLC", "Food, Beverages & Tobacco")
    assert v.category == Category.VAPE
    assert v.confidence == Confidence.LIKELY


def test_corroboration_inside_multivalued_topics():
    v = classify("Mystery Vapes LLC", "Shopping,Food, Beverages & Tobacco")
    assert v.confidence == Confidence.LIKELY


def test_no_corroboration_stays_quarantined():
    v = classify("Mystery Vapes LLC", "Shopping")
    assert v.confidence == Confidence.QUARANTINE


if __name__ == "__main__":
    test_corroborating_topic_with_comma_is_recognised()
    test_corroboration_inside_multivalued_topics()
    test_no_corroboration_stays_quarantined()
    print("ok")
