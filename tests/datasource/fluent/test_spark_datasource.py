from __future__ import annotations

import copy
import logging
import pathlib
from typing import TYPE_CHECKING

import pytest

from great_expectations.datasource.fluent import TestConnectionError
from great_expectations.datasource.fluent.spark_datasource import (
    DataFrameAsset,
    SparkConfig,
)
from great_expectations.exceptions.exceptions import BuildBatchRequestError
from great_expectations.execution_engine.sparkdf_batch_data import SparkDFBatchData
from great_expectations.util import is_candidate_subset_of_target

if TYPE_CHECKING:
    import pandas as pd

    from great_expectations.data_context import AbstractDataContext


logger = logging.getLogger(__file__)


@pytest.fixture
def valid_file_path(csv_path: pathlib.Path) -> pathlib.Path:
    return csv_path / "yellow_tripdata_sample_2018-03.csv"


@pytest.mark.spark
def test_dataframe_asset(
    empty_data_context: AbstractDataContext,
    spark_session,
    spark_df_from_pandas_df,
    test_df_pandas,
):
    datasource = empty_data_context.data_sources.add_spark(name="my_spark_datasource")

    pandas_df = test_df_pandas
    spark_df = spark_df_from_pandas_df(spark_session, pandas_df)

    dataframe_asset = datasource.add_dataframe_asset(
        name="my_dataframe_asset",
    )
    assert isinstance(dataframe_asset, DataFrameAsset)
    assert dataframe_asset.name == "my_dataframe_asset"
    assert len(datasource.assets) == 1

    datasource.add_dataframe_asset(
        name="my_second_dataframe_asset",
    )
    assert len(datasource.assets) == 2

    for i, asset in enumerate(datasource.assets):
        bd = asset.add_batch_definition_whole_dataframe(name=f"bd_{i}")
        batch = bd.get_batch(batch_parameters={"dataframe": spark_df})
        assert isinstance(batch.data, SparkDFBatchData)
        assert batch.data.dataframe.toPandas().equals(pandas_df)


@pytest.mark.spark
def test_spark_data_asset_batch_metadata(
    empty_data_context: AbstractDataContext,
    valid_file_path: pathlib.Path,
    test_df_pandas: pd.DataFrame,
    spark_session,
    spark_df_from_pandas_df,
):
    my_config_variables = {"pipeline_filename": __file__}
    empty_data_context.config_variables.update(my_config_variables)

    spark_df = spark_df_from_pandas_df(spark_session, test_df_pandas)

    spark_datasource = empty_data_context.data_sources.add_spark("my_spark_datasource")

    batch_metadata = {
        "no_curly_pipeline_filename": "$pipeline_filename",
        "curly_pipeline_filename": "${pipeline_filename}",
        "pipeline_step": "transform_3",
    }

    dataframe_asset = spark_datasource.add_dataframe_asset(
        name="my_dataframe_asset",
        batch_metadata=batch_metadata,
    )
    assert dataframe_asset.batch_metadata == batch_metadata

    batch = dataframe_asset.get_batch(
        dataframe_asset.build_batch_request(options={"dataframe": spark_df})
    )
    substituted_batch_metadata = copy.deepcopy(batch_metadata)
    substituted_batch_metadata.update(
        {
            "no_curly_pipeline_filename": __file__,
            "curly_pipeline_filename": __file__,
        }
    )
    assert batch.metadata == substituted_batch_metadata


@pytest.mark.spark
@pytest.mark.parametrize("persist", [True, False])
def test_spark_config_passed_to_execution_engine(
    empty_data_context: AbstractDataContext,
    persist,
    spark_session,
):
    spark_config: SparkConfig = {
        "spark.app.name": "gx_spark_fluent_datasource_test",
        "spark.default.parallelism": 4,
        "spark.master": "local[*]",
    }
    datasource = empty_data_context.data_sources.add_spark(
        name="my_spark_datasource",
        spark_config=spark_config,
        persist=persist,
    )
    execution_engine_spark_config = datasource.get_execution_engine().config["spark_config"]
    assert is_candidate_subset_of_target(
        candidate=spark_config,
        target=execution_engine_spark_config,
    )


@pytest.mark.spark
def test_build_batch_request_raises_if_missing_dataframe(
    empty_data_context: AbstractDataContext,
    spark_session,
):
    dataframe_asset = empty_data_context.data_sources.add_spark(
        name="my_spark_datasource"
    ).add_dataframe_asset(name="my_dataframe_asset")

    with pytest.raises(BuildBatchRequestError) as e:
        dataframe_asset.build_batch_request()

    assert "options must contain exactly 1 key, 'dataframe'" in str(e.value)


@pytest.mark.spark
def test_unmodifiable_config_option_warning(
    empty_data_context: AbstractDataContext,
    spark_session,
):
    spark_config = {"spark.executor.memory": "700m"}
    with pytest.warns(RuntimeWarning):
        _ = empty_data_context.data_sources.add_spark(
            name="my_spark_datasource",
            spark_config=spark_config,  # type: ignore[arg-type] # FIXME CoP
        )


@pytest.mark.unit
def test_spark_test_connection(
    empty_data_context: AbstractDataContext,
):
    # no spark marker means pyspark is not installed when this is run
    with pytest.raises(TestConnectionError):
        _ = empty_data_context.data_sources.add_spark(name="my_spark_datasource")
