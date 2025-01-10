import sys
from typing import List, Union

import pytest

from great_expectations.core.run_identifier import RunIdentifier
from great_expectations.data_context.types.resource_identifiers import (
    ExpectationSuiteIdentifier,
    ValidationResultIdentifier,
)
from great_expectations.render.util import (
    _convert_unexpected_indices_to_df,
    build_count_and_index_table,
    build_count_table,
    num_to_str,
    resource_key_passes_run_name_filter,
    truncate_list_of_indices,
)

# module level markers
pytestmark = pytest.mark.unit


def test_num_to_str():
    f = 0.99999999999999
    # We can round
    assert num_to_str(f, precision=4) == "≈1"
    # Specifying extra precision should not cause a problem
    assert num_to_str(f, precision=20) == "0.99999999999999"

    f = 1234567890.123456  # Our float can only hold 17 significant digits
    assert num_to_str(f, precision=4) == "≈1.235e+9"
    assert num_to_str(f, precision=20) == "1234567890.123456"
    assert num_to_str(f, use_locale=True, precision=40) == "1,234,567,890.123456"

    f = 1.123456789012345  # 17 sig digits mostly after decimal
    assert num_to_str(f, precision=5) == "≈1.1235"
    assert num_to_str(f, precision=20) == "1.123456789012345"

    f = 0.1  # A classic difficulty for floating point arithmetic
    assert num_to_str(f) == "0.1"
    assert num_to_str(f, precision=20) == "0.1"
    assert num_to_str(f, no_scientific=True) == "0.1"

    f = 1.23456789012345e-10  # significant digits can come late
    assert num_to_str(f, precision=20) == "1.23456789012345e-10"
    assert num_to_str(f, precision=5) == "≈1.2346e-10"
    assert num_to_str(f, precision=20, no_scientific=True) == "0.000000000123456789012345"
    assert num_to_str(f, precision=5, no_scientific=True) == "≈0.00000000012346"

    f = 100.0  # floats should have trailing digits and numbers stripped
    assert num_to_str(f, precision=10, no_scientific=True) == "100"
    assert num_to_str(f, precision=10) == "100"
    assert num_to_str(f, precision=10, use_locale=True) == "100"

    f = 100  # integers should never be stripped!
    assert num_to_str(f, precision=10, no_scientific=True) == "100"
    assert num_to_str(f, precision=10) == "100"
    assert num_to_str(f, precision=10, use_locale=True) == "100"

    f = 1000  # If we have a number longer than our precision, we should still be able to correctly format  # noqa: E501 # FIXME CoP
    assert num_to_str(f, precision=4) == "1000"
    assert num_to_str(f) == "1000"


def test_resource_key_passes_run_name_filter():
    resource_key = ValidationResultIdentifier(
        expectation_suite_identifier=ExpectationSuiteIdentifier("test_suite"),
        run_id=RunIdentifier(run_name="foofooprofilingfoo"),
        batch_identifier="f14c3d2f6e8028c2db0c25edabdb0d61",
    )

    assert (
        resource_key_passes_run_name_filter(resource_key, run_name_filter={"equals": "profiling"})
        is False
    )
    assert (
        resource_key_passes_run_name_filter(
            resource_key, run_name_filter={"equals": "foofooprofilingfoo"}
        )
        is True
    )

    assert (
        resource_key_passes_run_name_filter(
            resource_key, run_name_filter={"not_equals": "profiling"}
        )
        is True
    )
    assert (
        resource_key_passes_run_name_filter(
            resource_key, run_name_filter={"not_equals": "foofooprofilingfoo"}
        )
        is False
    )

    assert (
        resource_key_passes_run_name_filter(resource_key, run_name_filter={"includes": "profiling"})
        is True
    )
    assert (
        resource_key_passes_run_name_filter(resource_key, run_name_filter={"includes": "foobar"})
        is False
    )

    assert (
        resource_key_passes_run_name_filter(
            resource_key, run_name_filter={"not_includes": "foobar"}
        )
        is True
    )
    assert (
        resource_key_passes_run_name_filter(
            resource_key, run_name_filter={"not_includes": "profiling"}
        )
        is False
    )

    assert (
        resource_key_passes_run_name_filter(
            resource_key,
            run_name_filter={"matches_regex": "(foo){2}profiling(" "foo)+"},
        )
        is True
    )
    assert (
        resource_key_passes_run_name_filter(
            resource_key,
            run_name_filter={"matches_regex": "(foo){3}profiling(" "foo)+"},
        )
        is False
    )


def test_convert_unexpected_indices_to_df():
    unexpected_index_list = [
        {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
        {"animals": "lion", "pk_1": 4, "pk_2": "four"},
        {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
    ]
    unexpected_index_column_names = ["pk_1", "pk_2"]

    partial_unexpected_counts = [
        {"count": 1, "value": "giraffe"},
        {"count": 1, "value": "lion"},
        {"count": 1, "value": "zebra"},
    ]

    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_index_column_names=unexpected_index_column_names,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["pk_1", "pk_2", "Count"]
    assert res.iloc[0].tolist() == ["3", "three", 1]
    assert res.iloc[1].tolist() == ["4", "four", 1]
    assert res.iloc[2].tolist() == ["5", "five", 1]


def test_convert_unexpected_indices_to_df_multiple():
    result = [
        {"animals": "giraffe", "pk_1": 3},
        {"animals": "lion", "pk_1": 4},
        {"animals": "zebra", "pk_1": 5},
        {"animals": "zebra", "pk_1": 6},
        {"animals": "zebra", "pk_1": 7},
        {"animals": "zebra", "pk_1": 8},
    ]
    unexpected_index_column_names = ["pk_1"]
    partial_unexpected_counts = [
        {"count": 1, "value": "giraffe"},
        {"count": 1, "value": "lion"},
        {"count": 4, "value": "zebra"},
    ]

    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=result,
        unexpected_index_column_names=unexpected_index_column_names,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["pk_1", "Count"]
    assert res.iloc[0, 0] == "3"
    assert res.iloc[1, 0] == "4"
    assert res.iloc[2, 0] == "5, 6, 7, 8"
    assert res.iloc[0, 1] == 1
    assert res.iloc[1, 1] == 1
    assert res.iloc[2, 1] == 4


def test_convert_unexpected_indices_to_df_multiple_with_truncation():
    result = [
        {"animals": "zebra", "pk_1": 0},
        {"animals": "zebra", "pk_1": 1},
        {"animals": "zebra", "pk_1": 2},
        {"animals": "zebra", "pk_1": 3},
        {"animals": "zebra", "pk_1": 4},
        {"animals": "zebra", "pk_1": 5},
        {"animals": "zebra", "pk_1": 6},
        {"animals": "zebra", "pk_1": 7},
        {"animals": "zebra", "pk_1": 8},
        {"animals": "zebra", "pk_1": 9},
        {"animals": "zebra", "pk_1": 10},
        {"animals": "zebra", "pk_1": 11},
        {"animals": "zebra", "pk_1": 12},
    ]
    unexpected_index_column_names = ["pk_1"]
    partial_unexpected_counts = [{"count": 13, "value": "zebra"}]
    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=result,
        unexpected_index_column_names=unexpected_index_column_names,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["pk_1", "Count"]
    assert res.iloc[0].tolist() == ["0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ...", 13]


def test_convert_unexpected_indices_to_df_column_pair_expectation():
    partial_unexpected_counts = [{"value": ("eraser", "desk"), "count": 3}]
    unexpected_index_list = [
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "three"},
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "four"},
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "five"},
    ]
    unexpected_index_column_names = ["pk_2"]
    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_index_column_names=unexpected_index_column_names,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["pk_2", "Count"]
    assert res.index.to_list() == ["('eraser', 'desk')"] or res.index.to_list() == [
        "('desk', 'eraser')"
    ]
    assert res.iloc[0].tolist() == ["three, four, five", 3]


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="Failing on Python 3.7 and 3.8; blocking 0.15.48 release",
)
def test_convert_unexpected_indices_to_df_column_pair_expectation_no_id_pk():
    partial_unexpected_counts = [{"value": ("eraser", "desk"), "count": 3}]
    unexpected_index_list = [3, 4, 5]
    unexpected_list = [("eraser", "desk"), ("eraser", "desk"), ("eraser", "desk")]
    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_index_column_names=None,
        unexpected_list=unexpected_list,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["Index", "Count"]
    assert res.index.to_list() == ["('eraser', 'desk')"] or res.index.to_list() == [
        "('desk', 'eraser')"
    ]
    assert res.iloc[0].tolist() == ["3, 4, 5", 3]


def test_convert_unexpected_indices_to_df_multiple_column_expectation():
    partial_unexpected_counts = [
        {"value": (20, 20, 20), "count": 1},
        {"value": (30, 30, 30), "count": 1},
        {"value": (40, 40, 40), "count": 1},
        {"value": (50, 50, 50), "count": 1},
        {"value": (60, 60, 60), "count": 1},
    ]
    unexpected_index_list = [
        {"a": 20, "pk_1": 1, "b": 20, "c": 20},
        {"a": 30, "pk_1": 2, "b": 30, "c": 30},
        {"a": 40, "pk_1": 3, "b": 40, "c": 40},
        {"a": 50, "pk_1": 4, "b": 50, "c": 50},
        {"a": 60, "pk_1": 5, "b": 60, "c": 60},
    ]
    unexpected_index_column_names = ["pk_1"]
    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_index_column_names=unexpected_index_column_names,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["pk_1", "Count"]
    assert res.index.to_list() == [
        "('20', '20', '20')",
        "('30', '30', '30')",
        "('40', '40', '40')",
        "('50', '50', '50')",
        "('60', '60', '60')",
    ]
    assert res.iloc[0].tolist() == ["1", 1]
    assert res.iloc[1].tolist() == ["2", 1]
    assert res.iloc[2].tolist() == ["3", 1]
    assert res.iloc[3].tolist() == ["4", 1]
    assert res.iloc[4].tolist() == ["5", 1]


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="Failing on Python 3.7 and 3.8; blocking 0.15.48 release",
)
def test_convert_unexpected_indices_to_df_multiple_column_expectation_no_id_pk():
    partial_unexpected_counts = [
        {"value": (20, 20, 20), "count": 1},
        {"value": (30, 30, 30), "count": 1},
        {"value": (40, 40, 40), "count": 1},
        {"value": (50, 50, 50), "count": 1},
        {"value": (60, 60, 60), "count": 1},
    ]
    unexpected_list = [
        (20, 20, 20),
        (30, 30, 30),
        (40, 40, 40),
        (50, 50, 50),
        (60, 60, 60),
    ]
    unexpected_index_list = [1, 2, 3, 4, 5]
    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_index_column_names=None,
        unexpected_list=unexpected_list,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["Index", "Count"]
    assert res.index.to_list() == [
        "(20, 20, 20)",
        "(30, 30, 30)",
        "(40, 40, 40)",
        "(50, 50, 50)",
        "(60, 60, 60)",
    ]
    assert res.iloc[0].tolist() == ["1", 1]
    assert res.iloc[1].tolist() == ["2", 1]
    assert res.iloc[2].tolist() == ["3", 1]
    assert res.iloc[3].tolist() == ["4", 1]
    assert res.iloc[4].tolist() == ["5", 1]


def test_convert_unexpected_indices_to_df_actual_values():
    """
    Test if no index_column_names are specified, and we use Pandas' default unexpected indices
    """
    unexpected_index_list = [3, 4, 5]
    unexpected_list = ["giraffe", "lion", "zebra"]
    partial_unexpected_counts = [
        {"count": 1, "value": "giraffe"},
        {"count": 1, "value": "lion"},
        {"count": 4, "value": "zebra"},
    ]

    res = _convert_unexpected_indices_to_df(
        unexpected_index_list=unexpected_index_list,
        unexpected_list=unexpected_list,
        partial_unexpected_counts=partial_unexpected_counts,
    )
    assert list(res) == ["Index", "Count"]
    assert res.iloc[0].tolist() == ["3", 1]
    assert res.iloc[1].tolist() == ["4", 1]
    assert res.iloc[2].tolist() == ["5", 1]


def test_truncate_list_of_indices():
    int_indices: List[Union[int, str]] = [4, 5, 6, 7]
    result: str = truncate_list_of_indices(indices=int_indices)
    assert result == "4, 5, 6, 7"

    result: str = truncate_list_of_indices(indices=int_indices, max_index=2)
    assert result == "4, 5, ..."

    str_indices: List[Union[int, str]] = ["four", "five", "six", "seven"]
    result: str = truncate_list_of_indices(indices=str_indices)
    assert result == "four, five, six, seven"

    result: str = truncate_list_of_indices(indices=str_indices, max_index=2)
    assert result == "four, five, ..."


def test_build_count_and_index_table():
    partial_unexpected_counts = [
        {"count": 1, "value": "giraffe"},
        {"count": 1, "value": "lion"},
        {"count": 1, "value": "zebra"},
    ]
    unexpected_index_list = [
        {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
        {"animals": "lion", "pk_1": 4, "pk_2": "four"},
        {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
    ]
    unexpected_count = 3
    unexpected_index_column_names = ["pk_1", "pk_2"]

    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Unexpected Value", "Count", "pk_1", "pk_2"]
    assert table_rows == [
        ["giraffe", 1, "3", "three"],
        ["lion", 1, "4", "four"],
        ["zebra", 1, "5", "five"],
    ]


def test_build_count_and_index_table_sampled():
    partial_unexpected_counts = [
        {"count": 1, "value": "giraffe"},
        {"count": 1, "value": "lion"},
        {"count": 1, "value": "zebra"},
    ]
    unexpected_index_list = [
        {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
        {"animals": "lion", "pk_1": 4, "pk_2": "four"},
        {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
    ]
    unexpected_count = 100
    unexpected_index_column_names = ["pk_1", "pk_2"]

    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Sampled Unexpected Values", "Count", "pk_1", "pk_2"]
    assert table_rows == [
        ["giraffe", 1, "3", "three"],
        ["lion", 1, "4", "four"],
        ["zebra", 1, "5", "five"],
    ]


def test_build_count_and_index_table_with_empty_string():
    partial_unexpected_counts = [
        {"count": 1, "value": ""},
    ]
    unexpected_index_list = [
        {"animals": "", "pk_1": 5, "pk_2": "five"},
    ]
    unexpected_count = 100
    unexpected_index_column_names = ["pk_1", "pk_2"]

    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Sampled Unexpected Values", "Count", "pk_1", "pk_2"]
    assert table_rows == [
        ["EMPTY", 1, "5", "five"],
    ]


def test_build_count_and_index_table_with_multi_column():
    partial_unexpected_counts = [
        {"value": (20, 20, 20), "count": 1},
        {"value": (30, 30, 30), "count": 1},
        {"value": (40, 40, 40), "count": 1},
        {"value": (50, 50, 50), "count": 1},
        {"value": (60, 60, 60), "count": 1},
    ]
    unexpected_index_list = [
        {"a": 20, "pk_1": 1, "b": 20, "c": 20},
        {"a": 30, "pk_1": 2, "b": 30, "c": 30},
        {"a": 40, "pk_1": 3, "b": 40, "c": 40},
        {"a": 50, "pk_1": 4, "b": 50, "c": 50},
        {"a": 60, "pk_1": 5, "b": 60, "c": 60},
    ]
    unexpected_count = 5
    unexpected_index_column_names = ["pk_1"]
    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Unexpected Value", "Count", "pk_1"]
    assert table_rows == [
        ["('20', '20', '20')", 1, "1"],
        ["('30', '30', '30')", 1, "2"],
        ["('40', '40', '40')", 1, "3"],
        ["('50', '50', '50')", 1, "4"],
        ["('60', '60', '60')", 1, "5"],
    ]


def test_build_count_and_index_table_with_column_pair():
    partial_unexpected_counts = [{"value": ("eraser", "desk"), "count": 3}]
    unexpected_index_list = [
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "three"},
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "four"},
        {"ordered_item": "eraser", "received_item": "desk", "pk_2": "five"},
    ]
    unexpected_count = 3
    unexpected_index_column_names = ["pk_2"]
    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Unexpected Value", "Count", "pk_2"]
    assert table_rows == [  # noqa: PLR1714 # FIXME CoP
        ["('desk', 'eraser')", 3, "three, four, five"]
    ] or table_rows == [["('eraser', 'desk')", 3, "three, four, five"]]


def test_build_count_and_index_table_with_null():
    partial_unexpected_counts = [
        {"count": 1, "value": None},
    ]
    unexpected_index_list = [
        {"animals": None, "pk_1": 5, "pk_2": "five"},
    ]
    unexpected_count = 100
    unexpected_index_column_names = ["pk_1", "pk_2"]

    header_row, table_rows = build_count_and_index_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_index_list=unexpected_index_list,
        unexpected_count=unexpected_count,
        unexpected_index_column_names=unexpected_index_column_names,
    )
    assert header_row == ["Sampled Unexpected Values", "Count", "pk_1", "pk_2"]
    assert table_rows == [
        ["null", 1, "5", "five"],
    ]


def test_build_count_table():
    partial_unexpected_counts = [
        {"count": 3, "value": "giraffe"},
        {"count": 2, "value": "lion"},
        {"count": 1, "value": "zebra"},
    ]
    unexpected_count = 6

    header_row, table_rows = build_count_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_count=unexpected_count,
    )
    assert header_row == ["Unexpected Value", "Count"]
    assert table_rows == [["giraffe", 3], ["lion", 2], ["zebra", 1]]


def test_build_count_table_sampled():
    partial_unexpected_counts = [
        {"count": 3, "value": "giraffe"},
        {"count": 2, "value": "lion"},
        {"count": 1, "value": "zebra"},
    ]
    unexpected_count = 100

    header_row, table_rows = build_count_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_count=unexpected_count,
    )
    assert header_row == ["Sampled Unexpected Values"]
    assert table_rows == [["giraffe"], ["lion"], ["zebra"]]


def test_build_count_table_with_empty_string():
    partial_unexpected_counts = [
        {"count": 1, "value": ""},
    ]
    unexpected_count = 100

    header_row, table_rows = build_count_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_count=unexpected_count,
    )
    assert header_row == ["Sampled Unexpected Values"]
    assert table_rows == [
        ["EMPTY"],
    ]


def test_build_count_table_with_null():
    partial_unexpected_counts = [
        {"count": 1, "value": None},
    ]
    unexpected_count = 100

    header_row, table_rows = build_count_table(
        partial_unexpected_counts=partial_unexpected_counts,
        unexpected_count=unexpected_count,
    )
    assert header_row == ["Sampled Unexpected Values"]
    assert table_rows == [["null"]]
