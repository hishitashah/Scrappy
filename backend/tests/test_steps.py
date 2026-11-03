"""Cleaning a method's numbering (spec 10.3, 10.12).

The page renders an `<ol>`, so a step that carries its own "1." is numbered twice. Both
sources produce it — TheMealDB inconsistently, a model reliably — so the cleaning is
shared and tested here rather than twice over.
"""

from app.steps import clean_steps


def test_a_numbered_step_loses_its_number() -> None:
    assert clean_steps(["1. Boil the rice.", "2. Fry the eggs."]) == [
        "Boil the rice.",
        "Fry the eggs.",
    ]


def test_the_other_shapes_of_numbering() -> None:
    """Models and TheMealDB between them use all of these."""
    assert clean_steps(["1) Boil it.", "2: Fry it.", "3 - Serve it.", "4.  Eat it."]) == [
        "Boil it.",
        "Fry it.",
        "Serve it.",
        "Eat it.",
    ]


def test_a_step_opening_with_a_quantity_keeps_its_number() -> None:
    """The reason the pattern needs punctuation: "2 eggs, beaten" is not step two.

    Stripping it would turn an instruction into a different instruction, which is worse
    than leaving a stray number on the page.
    """
    assert clean_steps(["2 eggs, beaten, go in next."]) == ["2 eggs, beaten, go in next."]


def test_a_bare_number_is_not_a_step() -> None:
    """A number on its own is a heading for the line below, and renders as an empty step."""
    assert clean_steps(["1", "Boil the rice.", "2.", "Fry the eggs."]) == [
        "Boil the rice.",
        "Fry the eggs.",
    ]


def test_blanks_and_whitespace_are_dropped() -> None:
    assert clean_steps(["", "   ", "\n", "Boil the rice."]) == ["Boil the rice."]


def test_an_unnumbered_method_is_left_alone() -> None:
    """The ordinary case once the prompt is obeyed: nothing to do."""
    assert clean_steps(["Boil the rice.", "Fry the eggs."]) == ["Boil the rice.", "Fry the eggs."]
