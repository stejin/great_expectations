import pytest

from great_expectations.core.expectation_diagnostics.supporting_types import Maturity
from tests.expectations.fixtures.expect_column_values_to_equal_three import (
    ExpectColumnValuesToEqualThree,
    ExpectColumnValuesToEqualThree__SecondIteration,
    ExpectColumnValuesToEqualThree__ThirdIteration,
)

# module level markers
pytestmark = pytest.mark.unit


@pytest.mark.skip("This is broken because Expectation._get_execution_engine_diagnostics is broken")
def test_print_diagnostic_checklist__first_iteration():
    output_message = ExpectColumnValuesToEqualThree().print_diagnostic_checklist()

    assert (
        output_message
        == """\
Completeness checklist for ExpectColumnValuesToEqualThree:
   library_metadata object exists
   Has a docstring, including a one-line short description that begins with "Expect" and ends with a period
   Has at least one positive and negative example case, and all test cases pass
   Has core logic and passes tests on at least one Execution Engine
"""  # noqa: E501 # FIXME CoP
    )


def test_print_diagnostic_checklist__second_iteration():
    output_message = ExpectColumnValuesToEqualThree__SecondIteration(
        column="values"
    ).print_diagnostic_checklist()
    print(output_message)

    assert (
        output_message
        == f"""\
Completeness checklist for ExpectColumnValuesToEqualThree__SecondIteration ({Maturity.EXPERIMENTAL}):
 ✔ Has a valid library_metadata object
 ✔ Has a docstring, including a one-line short description that begins with "Expect" and ends with a period
    ✔ "Expect values in this column to equal the number three."
 ✔ Has at least one positive and negative example case, and all test cases pass
 ✔ Has core logic and passes tests on at least one Execution Engine
    ✔ All 3 tests for pandas are passing
   Has basic input validation and type checking
      No validate_configuration method defined on subclass
 ✔ Has both statement Renderers: prescriptive and diagnostic
 ✔ Has core logic that passes tests for all applicable Execution Engines and SQL dialects
    ✔ All 3 tests for pandas are passing
   Has a full suite of tests, as determined by a code owner
   Has passed a manual review by a code owner for code standards and style guides
"""  # noqa: E501 # FIXME CoP
    )


def test_print_diagnostic_checklist__third_iteration():
    output_message = ExpectColumnValuesToEqualThree__ThirdIteration(
        column="values"
    ).print_diagnostic_checklist()
    print(output_message)

    assert (
        output_message
        == f"""\
Completeness checklist for ExpectColumnValuesToEqualThree__ThirdIteration ({Maturity.EXPERIMENTAL}):
 ✔ Has a valid library_metadata object
   Has a docstring, including a one-line short description that begins with "Expect" and ends with a period
 ✔ Has at least one positive and negative example case, and all test cases pass
 ✔ Has core logic and passes tests on at least one Execution Engine
    ✔ All 3 tests for pandas are passing
   Has basic input validation and type checking
      No validate_configuration method defined on subclass
 ✔ Has both statement Renderers: prescriptive and diagnostic
 ✔ Has core logic that passes tests for all applicable Execution Engines and SQL dialects
    ✔ All 3 tests for pandas are passing
   Has a full suite of tests, as determined by a code owner
   Has passed a manual review by a code owner for code standards and style guides
"""  # noqa: E501 # FIXME CoP
    )
