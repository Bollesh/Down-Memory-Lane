import pytest

from prompts import STYLE, build_prompt, extract_age


@pytest.mark.parametrize("description,expected", [
    ("Your 2-year-old self in your house's backyard",
     "a photo of TOK as a 2-year-old toddler, in the house's backyard"),
    ("Your 5-year-old self on a beach", "a photo of TOK as a 5-year-old child, on a beach"),
    ("Your 10-year-old self in a classroom", "a photo of TOK as a 10-year-old child, in a classroom"),
    ("me at 7 riding a bicycle", "a photo of TOK as a 7-year-old child, riding a bicycle"),
    ("photo of myself aged 15 at a school dance", "a photo of TOK as a 15-year-old teenager, at a school dance"),
    ("my 3 yr old self eating cake", "a photo of TOK as a 3-year-old toddler, eating cake"),
])
def test_assignment_examples_and_casual_phrasing(description, expected):
    assert build_prompt(description, "TOK") == f"{expected}, {STYLE}"


def test_prompt_always_contains_trigger_word():
    assert "ZXQ" in build_prompt("a snowy mountain", "ZXQ")


def test_no_age_keeps_description():
    assert build_prompt("a snowy mountain", "TOK") == f"a photo of TOK, a snowy mountain, {STYLE}"


def test_extract_age_without_age():
    assert extract_age("on a beach") == (None, "on a beach")
