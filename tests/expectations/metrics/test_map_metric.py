import pandas as pd
import pytest

import great_expectations.expectations as gxe
from great_expectations.compatibility import sqlalchemy
from great_expectations.compatibility.pydantic import ValidationError
from great_expectations.compatibility.sqlalchemy_compatibility_wrappers import (
    add_dataframe_to_db,
)
from great_expectations.core import (
    ExpectationValidationResult,
    IDDict,
)
from great_expectations.core.batch import Batch, LegacyBatchDefinition
from great_expectations.core.metric_function_types import (
    MetricPartialFunctionTypes,
    MetricPartialFunctionTypeSuffixes,
    SummarizationMetricNameSuffixes,
)
from great_expectations.data_context import AbstractDataContext
from great_expectations.data_context.util import file_relative_path
from great_expectations.execution_engine import (
    PandasExecutionEngine,
    SparkDFExecutionEngine,
    SqlAlchemyExecutionEngine,
)
from great_expectations.expectations.expectation_configuration import (
    ExpectationConfiguration,
)
from great_expectations.expectations.metrics import (
    ColumnMax,
    ColumnValuesNonNull,
    CompoundColumnsUnique,
)
from great_expectations.expectations.metrics.map_metric_provider import (
    ColumnMapMetricProvider,
    MapMetricProvider,
)
from great_expectations.util import convert_to_json_serializable
from great_expectations.validator.validation_graph import MetricConfiguration
from great_expectations.validator.validator import Validator


@pytest.fixture
def sqlite_table_for_unexpected_rows_with_index(
    test_backends,
) -> sqlalchemy.Engine:
    if "sqlite" in test_backends:
        try:
            from great_expectations.compatibility.sqlalchemy import sqlalchemy as sa

            sqlite_path = file_relative_path(__file__, "../../test_sets/metrics_test.db")
            sqlite_engine = sa.create_engine(f"sqlite:///{sqlite_path}")
            df = pd.DataFrame(
                {
                    "pk_1": [0, 1, 2, 3, 4, 5],
                    "pk_2": ["zero", "one", "two", "three", "four", "five"],
                    "animals": [
                        "cat",
                        "fish",
                        "dog",
                        "giraffe",
                        "lion",
                        "zebra",
                    ],
                }
            )
            # use try-except block to ensure we don't keep modifying the database
            # adapted from https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html
            try:
                add_dataframe_to_db(
                    df=df,
                    name="animal_names",
                    con=sqlite_engine,
                    index=False,
                    if_exists="fail",
                )
            except ValueError:
                pass

            return sqlite_engine
        except ImportError:
            sa = None
    else:
        pytest.skip("SqlAlchemy tests disabled; not testing views")


@pytest.fixture()
def expected_evr_without_unexpected_rows():
    return ExpectationValidationResult(
        success=False,
        expectation_config={
            "expectation_type": "expect_column_values_to_be_in_set",
            "kwargs": {
                "column": "animals",
                "value_set": ["cat", "fish", "dog"],
            },
            "meta": {},
        },
        result={
            "element_count": 6,
            "missing_count": 0,
            "missing_percent": 0.0,
            "partial_unexpected_counts": [
                {"count": 1, "value": "giraffe"},
                {"count": 1, "value": "lion"},
                {"count": 1, "value": "zebra"},
            ],
            "partial_unexpected_index_list": [3, 4, 5],
            "partial_unexpected_list": ["giraffe", "lion", "zebra"],
            "unexpected_count": 3,
            "unexpected_index_list": [3, 4, 5],
            "unexpected_index_query": "df.filter(items=[3, 4, 5], axis=0)",
            "unexpected_list": ["giraffe", "lion", "zebra"],
            "unexpected_percent": 50.0,
            "unexpected_percent_nonmissing": 50.0,
            "unexpected_percent_total": 50.0,
        },
        exception_info={
            "raised_exception": False,
            "exception_traceback": None,
            "exception_message": None,
        },
        meta={},
    )


def _expecation_configuration_to_validation_result_pandas(
    expectation_configuration: ExpectationConfiguration,
    dataframe: pd.DataFrame,
    context: AbstractDataContext,
) -> ExpectationValidationResult:
    """
    Helper method used by pandas tests in this suite. Takes in a ExpectationConfiguration and returns an EVR
    after building an ExecutionEngine, DataConnector and Validator.

    Args:
        expectation_configuration (ExpectationConfiguration): configuration that is being tested

    """  # noqa: E501 # FIXME CoP
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    batch_definition = LegacyBatchDefinition(
        datasource_name="pandas_datasource",
        data_connector_name="runtime_data_connector",
        data_asset_name="my_asset",
        batch_identifiers=IDDict({}),
        batch_spec_passthrough=None,
    )
    batch = Batch(
        data=dataframe,
        batch_definition=batch_definition,
    )
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        data_context=context,
        batches=[
            batch,
        ],
    )
    result = expectation.validate_(validator)
    return result


def _expecation_configuration_to_validation_result_sql(
    expectation_configuration: ExpectationConfiguration,
    context: AbstractDataContext,
) -> ExpectationValidationResult:
    """
    Helper method used by sql tests in this suite. Takes in a ExpectationConfiguration and returns an EVR
    after building an ExecutionEngine, DataConnector and Validator.

    Args:
        expectation_configuration (ExpectationConfiguration): configuration that is being tested

    """  # noqa: E501 # FIXME CoP
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    sqlite_path = file_relative_path(__file__, "../../test_sets/metrics_test.db")
    connection_string = f"sqlite:///{sqlite_path}"
    engine = SqlAlchemyExecutionEngine(
        connection_string=connection_string,
        create_temp_table=False,
    )
    datasource = context.data_sources.add_sqlite(
        "my_test_datasource", connection_string=connection_string
    )
    asset = datasource.add_table_asset("my_asset", table_name="animal_names")
    batch_definition = asset.add_batch_definition_whole_table("all of it")
    validator = Validator(
        execution_engine=engine,
        data_context=context,
        batches=[
            batch_definition.get_batch(),
        ],
    )
    result = expectation.validate_(validator)
    return result


@pytest.mark.sqlite
def test_get_table_metric_provider_metric_dependencies(empty_sqlite_db):
    mp = ColumnMax()
    metric = MetricConfiguration(
        metric_name="column.max", metric_domain_kwargs={}, metric_value_kwargs=None
    )
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=SqlAlchemyExecutionEngine(engine=empty_sqlite_db)
    )
    assert (
        dependencies["metric_partial_fn"].id[0]
        == f"column.max.{MetricPartialFunctionTypes.AGGREGATE_FN.metric_suffix}"
    )

    mp = ColumnMax()
    metric = MetricConfiguration(
        metric_name="column.max", metric_domain_kwargs={}, metric_value_kwargs=None
    )
    dependencies = mp.get_evaluation_dependencies(metric, execution_engine=PandasExecutionEngine())

    table_column_types_metric: MetricConfiguration = dependencies["table.column_types"]
    table_columns_metric: MetricConfiguration = dependencies["table.columns"]
    table_row_count_metric: MetricConfiguration = dependencies["table.row_count"]
    assert dependencies == {
        "table.column_types": table_column_types_metric,
        "table.columns": table_columns_metric,
        "table.row_count": table_row_count_metric,
    }
    assert dependencies["table.columns"].id == (
        "table.columns",
        (),
        (),
    )


@pytest.mark.spark
def test_get_aggregate_count_aware_metric_dependencies(basic_spark_df_execution_engine):
    mp = ColumnValuesNonNull()
    metric = MetricConfiguration(
        metric_name=f"column_values.nonnull.{SummarizationMetricNameSuffixes.UNEXPECTED_COUNT.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric, execution_engine=PandasExecutionEngine())
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"column_values.nonnull.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )

    metric = MetricConfiguration(
        metric_name=f"column_values.nonnull.{SummarizationMetricNameSuffixes.UNEXPECTED_COUNT.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=basic_spark_df_execution_engine
    )
    assert (
        dependencies["metric_partial_fn"].id[0]
        == f"column_values.nonnull.{SummarizationMetricNameSuffixes.UNEXPECTED_COUNT.value}.{MetricPartialFunctionTypes.AGGREGATE_FN.metric_suffix}"  # noqa: E501 # FIXME CoP
    )

    metric = MetricConfiguration(
        metric_name=f"column_values.nonnull.{SummarizationMetricNameSuffixes.UNEXPECTED_COUNT.value}.{MetricPartialFunctionTypes.AGGREGATE_FN.metric_suffix}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"column_values.nonnull.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )


@pytest.mark.unit
def test_get_map_metric_dependencies():
    mp = ColumnMapMetricProvider()
    metric = MetricConfiguration(
        metric_name=f"foo.{SummarizationMetricNameSuffixes.UNEXPECTED_COUNT.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"foo.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )

    metric = MetricConfiguration(
        metric_name=f"foo.{SummarizationMetricNameSuffixes.UNEXPECTED_ROWS.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"foo.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )

    metric = MetricConfiguration(
        metric_name=f"foo.{SummarizationMetricNameSuffixes.UNEXPECTED_VALUES.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"foo.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )

    metric = MetricConfiguration(
        metric_name=f"foo.{SummarizationMetricNameSuffixes.UNEXPECTED_VALUE_COUNTS.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"foo.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )

    metric = MetricConfiguration(
        metric_name=f"foo.{SummarizationMetricNameSuffixes.UNEXPECTED_INDEX_LIST.value}",
        metric_domain_kwargs={},
        metric_value_kwargs=None,
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0]
        == f"foo.{MetricPartialFunctionTypeSuffixes.CONDITION.value}"
    )


@pytest.mark.unit
def test_is_sqlalchemy_metric_selectable():
    with pytest.warns(DeprecationWarning) as record:
        assert MapMetricProvider.is_sqlalchemy_metric_selectable(
            map_metric_provider=CompoundColumnsUnique
        )

    assert "MapMetricProvider.is_sqlalchemy_metric_selectable is deprecated." in str(
        record.list[0].message
    )

    with pytest.warns(DeprecationWarning) as record:
        assert not MapMetricProvider.is_sqlalchemy_metric_selectable(
            map_metric_provider=ColumnValuesNonNull
        )

    assert "MapMetricProvider.is_sqlalchemy_metric_selectable is deprecated." in str(
        record.list[0].message
    )


@pytest.mark.unit
def test_pandas_unexpected_rows_basic_result_format(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "BASIC",
                "include_unexpected_rows": True,
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
        "unexpected_rows": [
            {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
            {"animals": "lion", "pk_1": 4, "pk_2": "four"},
            {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
        ],
    }


@pytest.mark.unit
def test_pandas_unexpected_rows_summary_result_format_unexpected_rows_explicitly_false(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "SUMMARY",  # SUMMARY will include partial_unexpected* values only
                "include_unexpected_rows": False,  # this is the default value, but making explicit for testing purposes  # noqa: E501 # FIXME CoP
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [3, 4, 5],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.unit
def test_pandas_unexpected_rows_summary_result_format_unexpected_rows_including_unexpected_rows(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "SUMMARY",  # SUMMARY will include partial_unexpected* values only
                "include_unexpected_rows": True,
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [3, 4, 5],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
        "unexpected_rows": [
            {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
            {"animals": "lion", "pk_1": 4, "pk_2": "four"},
            {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
        ],
    }


@pytest.mark.unit
def test_pandas_unexpected_rows_complete_result_format(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
                "include_unexpected_rows": True,
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [3, 4, 5],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_list": [3, 4, 5],
        "unexpected_index_query": "df.filter(items=[3, 4, 5], axis=0)",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
        "unexpected_rows": [
            {"animals": "giraffe", "pk_1": 3, "pk_2": "three"},
            {"animals": "lion", "pk_1": 4, "pk_2": "four"},
            {"animals": "zebra", "pk_1": 5, "pk_2": "five"},
        ],
    }


@pytest.mark.unit
def test_expectation_configuration_has_result_format(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index: pd.DataFrame,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )
    with pytest.warns(UserWarning) as config_warning:
        result: ExpectationValidationResult = (  # noqa: F841 # FIXME CoP
            _expecation_configuration_to_validation_result_pandas(
                expectation_configuration=expectation_configuration,
                dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
                context=in_memory_runtime_context,
            )
        )

    assert "`result_format` configured at the Expectation-level will not be persisted." in str(
        config_warning.list[0].message
    )


@pytest.mark.unit
def test_pandas_default_complete_result_format(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index: pd.DataFrame,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [3, 4, 5],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_list": [3, 4, 5],
        "unexpected_index_query": "df.filter(items=[3, 4, 5], axis=0)",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.unit
def test_pandas_unexpected_rows_complete_result_format_with_id_pk(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index: pd.DataFrame,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_column_names": ["pk_1"],
            },
        },
    )
    # result_format configuration at ExpectationConfiguration-level will emit warning
    with pytest.warns(UserWarning):
        result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
            expectation_configuration=expectation_configuration,
            dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
            context=in_memory_runtime_context,
        )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_column_names": ["pk_1"],
        "unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "unexpected_index_query": "df.filter(items=[3, 4, 5], axis=0)",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.unit
def test_pandas_default_to_not_include_unexpected_rows(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
    expected_evr_without_unexpected_rows,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert result.result == expected_evr_without_unexpected_rows.result


@pytest.mark.unit
def test_pandas_specify_not_include_unexpected_rows(
    in_memory_runtime_context,
    pandas_animals_dataframe_for_unexpected_rows_and_index,
    expected_evr_without_unexpected_rows,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
                "include_unexpected_rows": False,
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_pandas(
        expectation_configuration=expectation_configuration,
        dataframe=pandas_animals_dataframe_for_unexpected_rows_and_index,
        context=in_memory_runtime_context,
    )
    assert result.result == expected_evr_without_unexpected_rows.result


@pytest.mark.unit
def test_include_unexpected_rows_without_explicit_result_format_raises_error():
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "include_unexpected_rows": False,
            },
        },
    )

    with pytest.raises(ValidationError):
        gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)


# Spark
@pytest.mark.spark
def test_spark_single_column_complete_result_format(
    in_memory_runtime_context,
    spark_dataframe_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    batch_definition = LegacyBatchDefinition(
        datasource_name="spark_datasource",
        data_connector_name="runtime_data_connector",
        data_asset_name="my_asset",
        batch_identifiers=IDDict({}),
        batch_spec_passthrough=None,
    )
    batch = Batch(
        data=spark_dataframe_for_unexpected_rows_with_index,
        batch_definition=batch_definition,
    )
    engine = SparkDFExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        data_context=in_memory_runtime_context,
        batches=[
            batch,
        ],
    )
    result = expectation.validate_(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_query": "df.filter(F.expr((animals IS NOT NULL) AND (NOT "
        "(animals IN (cat, fish, dog)))))",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.spark
def test_spark_single_column_complete_result_format_with_id_pk(
    in_memory_runtime_context,
    spark_dataframe_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_column_names": ["pk_1"],
            },
        },
    )
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    batch_definition = LegacyBatchDefinition(
        datasource_name="spark_datasource",
        data_connector_name="runtime_data_connector",
        data_asset_name="my_asset",
        batch_identifiers=IDDict({}),
        batch_spec_passthrough=None,
    )
    batch = Batch(
        data=spark_dataframe_for_unexpected_rows_with_index,
        batch_definition=batch_definition,
    )
    engine = SparkDFExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        data_context=in_memory_runtime_context,
        batches=[
            batch,
        ],
    )

    # result_format configuration at ExpectationConfiguration-level will emit warning
    with pytest.warns(UserWarning):
        result = expectation.validate_(validator)

    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_column_names": ["pk_1"],
        "unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "unexpected_index_query": "df.filter(F.expr((animals IS NOT NULL) AND (NOT "
        "(animals IN (cat, fish, dog)))))",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.spark
def test_spark_single_column_summary_result_format(
    in_memory_runtime_context,
    spark_dataframe_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "SUMMARY",
            },
        },
    )
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    batch_definition = LegacyBatchDefinition(
        datasource_name="spark_datasource",
        data_connector_name="runtime_data_connector",
        data_asset_name="my_asset",
        batch_identifiers=IDDict({}),
        batch_spec_passthrough=None,
    )
    batch = Batch(
        data=spark_dataframe_for_unexpected_rows_with_index,
        batch_definition=batch_definition,
    )
    engine = SparkDFExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        data_context=in_memory_runtime_context,
        batches=[
            batch,
        ],
    )
    result = expectation.validate_(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.spark
def test_spark_single_column_basic_result_format(
    in_memory_runtime_context,
    spark_dataframe_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "BASIC",
            },
        },
    )
    expectation = gxe.ExpectColumnValuesToBeInSet(**expectation_configuration.kwargs)
    batch_definition = LegacyBatchDefinition(
        datasource_name="spark_datasource",
        data_connector_name="runtime_data_connector",
        data_asset_name="my_asset",
        batch_identifiers=IDDict({}),
        batch_spec_passthrough=None,
    )
    batch = Batch(
        data=spark_dataframe_for_unexpected_rows_with_index,
        batch_definition=batch_definition,
    )
    engine = SparkDFExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        data_context=in_memory_runtime_context,
        batches=[
            batch,
        ],
    )
    result = expectation.validate_(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.sqlite
def test_sqlite_single_column_complete_result_format(
    sa,
    in_memory_runtime_context,
    sqlite_table_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_sql(
        expectation_configuration=expectation_configuration,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_query": "SELECT animals \n"
        "FROM animal_names \n"
        "WHERE animals IS NOT NULL AND (animals NOT IN "
        "('cat', 'fish', 'dog'));",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.sqlite
def test_sqlite_single_column_complete_result_format_id_pk(
    sa,
    in_memory_runtime_context,
    sqlite_table_for_unexpected_rows_with_index,
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_column_names": ["pk_1"],
            },
        },
    )

    # result_format configuration at ExpectationConfiguration-level will emit warning
    with pytest.warns(UserWarning):
        result: ExpectationValidationResult = _expecation_configuration_to_validation_result_sql(
            expectation_configuration=expectation_configuration,
            context=in_memory_runtime_context,
        )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_index_column_names": ["pk_1"],
        "unexpected_index_list": [
            {"animals": "giraffe", "pk_1": 3},
            {"animals": "lion", "pk_1": 4},
            {"animals": "zebra", "pk_1": 5},
        ],
        "unexpected_index_query": "SELECT pk_1, animals \n"
        "FROM animal_names \n"
        "WHERE animals IS NOT NULL AND (animals NOT IN "
        "('cat', 'fish', 'dog'));",
        "unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.sqlite
def test_sqlite_single_column_summary_result_format(
    sa, in_memory_runtime_context, sqlite_table_for_unexpected_rows_with_index
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "SUMMARY",
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_sql(
        expectation_configuration=expectation_configuration,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "partial_unexpected_counts": [
            {"count": 1, "value": "giraffe"},
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_count": 3,
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }


@pytest.mark.sqlite
def test_sqlite_single_column_basic_result_format(
    sa, in_memory_runtime_context, sqlite_table_for_unexpected_rows_with_index
):
    expectation_configuration = ExpectationConfiguration(
        type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "animals",
            "value_set": ["cat", "fish", "dog"],
            "result_format": {
                "result_format": "BASIC",
            },
        },
    )
    result: ExpectationValidationResult = _expecation_configuration_to_validation_result_sql(
        expectation_configuration=expectation_configuration,
        context=in_memory_runtime_context,
    )
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_count": 3,
        "partial_unexpected_list": ["giraffe", "lion", "zebra"],
        "unexpected_percent": 50.0,
        "unexpected_percent_nonmissing": 50.0,
        "unexpected_percent_total": 50.0,
    }
