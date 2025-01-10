from __future__ import annotations

import logging
import sys
from pprint import pformat as pf
from typing import TYPE_CHECKING, Any, Callable, Final, Generator, Literal

import pandas as pd
import pytest
from packaging.version import Version

import great_expectations.core.batch_spec
from great_expectations.datasource.fluent import BatchRequest
from great_expectations.datasource.fluent.fabric import (
    FabricPowerBIDatasource,
    _PowerBIAsset,
)
from great_expectations.exceptions.exceptions import BuildBatchRequestError

if TYPE_CHECKING:
    from great_expectations.data_context import AbstractDataContext

param = pytest.param

LOGGER = logging.getLogger(__name__)

PYTHON_VERSION: Version = Version(f"{sys.version_info.major}.{sys.version_info.minor}")

_DUMMY_POWER_BI_DATASET_ID: Final[str] = "0993ddd1-f01d-4c8f-a64e-9c4e5b8905e8"


@pytest.fixture
def empty_data_context(empty_data_context: AbstractDataContext) -> AbstractDataContext:
    return empty_data_context


@pytest.fixture
def patch_power_bi_datasource(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Monkeypatch the PowerBI datasource to enable datasource creation even without `semantic-link` installed
    """  # noqa: E501 # FIXME CoP
    monkeypatch.setattr(FabricPowerBIDatasource, "test_connection", lambda _: True)


@pytest.fixture
def power_bi_datasource(
    empty_data_context: AbstractDataContext, patch_power_bi_datasource: None
) -> FabricPowerBIDatasource:
    datasource = empty_data_context.data_sources.add_fabric_powerbi(
        "my_power_bi_datasource",
        dataset=_DUMMY_POWER_BI_DATASET_ID,
        workspace=None,
    )
    return datasource


@pytest.fixture
def capture_reader_fn_params(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[list[tuple], list[dict]], None, None]:
    """
    Capture the `reader_options` arguments being passed to the `PandasExecutionEngine`.

    Note this fixture is heavily reliant on the implementation details of `PandasExecutionEngine`,
    should this change this fixture will need to change.
    """
    captured_args: list[tuple] = []
    captured_kwargs: list[dict[str, Any]] = []

    def reader_fn_spy(*args, **kwargs) -> pd.DataFrame:
        LOGGER.info(f"reader_fn_spy() called with...\n{args}\n{kwargs}")
        captured_args.append(args)
        captured_kwargs.append(kwargs)
        return pd.DataFrame.from_dict({"foo": ["bar"]})

    monkeypatch.setattr(
        great_expectations.core.batch_spec.FabricBatchSpec,
        "get_reader_function",
        lambda _: reader_fn_spy,
        raising=True,
    )
    LOGGER.info("Patcehd core.batch_spec.FabricBatchSpec.reader_method")

    yield captured_args, captured_kwargs


@pytest.mark.unit
class TestFabricPowerBI:
    @pytest.mark.parametrize(
        ["asset_type", "asset_kwargs"],
        [
            param("powerbi_dax", {"dax_string": "my_dax_string"}, id="dax min_args"),
            param(
                "powerbi_measure",
                {
                    "measure": "my_measure",
                },
                id="measure min_args",
            ),
            param(
                "powerbi_measure",
                {
                    "measure": "my_measure",
                    "groupby_columns": ["foo[Bar]", "'fizz with space'[Buzz]"],
                    "filters": {
                        "State[Region]": ["East", "Central"],
                        "State[State]": ["WA", "CA"],
                    },
                    "fully_qualified_columns": True,
                    "num_rows": 100,
                    "use_xmla": True,
                },
                id="measure all_args",
            ),
            param("powerbi_table", {"table": "my_table_name"}, id="table min_args"),
        ],
    )
    def test_reader_options_passthrough(
        self,
        power_bi_datasource: FabricPowerBIDatasource,
        capture_reader_fn_params: tuple[list[tuple], list[dict]],
        asset_type: Literal["powerbi_dax", "powerbi_measure", "powerbi_table"],
        asset_kwargs: dict,
    ):
        """Test that the `reader_options` are passed through to the `PandasExecutionEngine`"""
        print(power_bi_datasource)
        # intitial datasource should have no assets
        assert not power_bi_datasource.assets

        add_asset_fn: Callable[[str], _PowerBIAsset] = getattr(
            power_bi_datasource, f"add_{asset_type}_asset"
        )
        my_asset = add_asset_fn(f"my_{asset_type}_asset", **asset_kwargs)
        batch_request = my_asset.build_batch_request()
        my_asset.get_batch(batch_request)

        _, captured_kwargs = capture_reader_fn_params
        print(f"keyword args:\n{pf(captured_kwargs[-1])}")
        for asset_kwarg in asset_kwargs:
            assert asset_kwarg in captured_kwargs[-1]

    @pytest.mark.parametrize(
        ["asset_type", "asset_kwargs"],
        [
            param("powerbi_dax", {"dax_string": "my_dax_string"}, id="dax min_args"),
            param(
                "powerbi_measure",
                {
                    "measure": "my_measure",
                },
                id="measure min_args",
            ),
            param(
                "powerbi_measure",
                {
                    "measure": "my_measure",
                    "groupby_columns": ["foo[Bar]", "'fizz with space'[Buzz]"],
                    "filters": {
                        "State[Region]": ["East", "Central"],
                        "State[State]": ["WA", "CA"],
                    },
                    "fully_qualified_columns": True,
                    "num_rows": 100,
                    "use_xmla": True,
                },
                id="measure all_args",
            ),
            param("powerbi_table", {"table": "my_table_name"}, id="table min_args"),
        ],
    )
    def test_valid_build_batch_request_params(
        self,
        power_bi_datasource: FabricPowerBIDatasource,
        asset_type: Literal["powerbi_dax", "powerbi_measure", "powerbi_table"],
        asset_kwargs: dict,
    ):
        """
        Test that passing valid keyword parameters to `build_batch_request` does not error.

        This test is a bit redundant since mypy should enforce that the method signature is correct,
        but we experienced an error here as part of the initial 1.0 release.
        """
        add_asset_fn: Callable[[str], _PowerBIAsset] = getattr(
            power_bi_datasource, f"add_{asset_type}_asset"
        )
        my_asset = add_asset_fn(f"my_{asset_type}_asset", **asset_kwargs)

        batch_request = my_asset.build_batch_request(
            options=None, batch_slice=None, partitioner=None
        )
        assert isinstance(batch_request, BatchRequest)

    def test_invalid_build_batch_request_params(self, power_bi_datasource: FabricPowerBIDatasource):
        """Test that passing invalid parameters to `build_batch_request` raises an error"""
        with pytest.raises(BuildBatchRequestError):
            power_bi_datasource.add_powerbi_dax_asset(
                "my_dax_asset", dax_string="my_dax_string"
            ).build_batch_request(options={"not": "valid"})


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
