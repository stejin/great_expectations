from __future__ import annotations

import pytest

from great_expectations.compatibility import pydantic
from great_expectations.datasource.fluent.databricks_sql_datasource import (
    DatabricksSQLDatasource,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "connection_string, expected_errors",
    [
        pytest.param(
            "databricks://token:my_token>@my_host:1234",
            [
                {
                    "loc": ("connection_string",),
                    "msg": "ConfigStr - contains no config template strings in the format '${MY_CONFIG_VAR}' or '$MY_CONFIG_VAR'",  # noqa: E501 # FIXME CoP
                    "type": "value_error",
                },
                {
                    "loc": ("connection_string",),
                    "msg": "URL query is invalid or missing",
                    "type": "value_error.url.query",
                },
            ],
            id="missing query",
        ),
        pytest.param(
            "databricks://token:my_token>@my_host:1234?my_query=data",
            [
                {
                    "loc": ("connection_string",),
                    "msg": "ConfigStr - contains no config template strings in the format '${MY_CONFIG_VAR}' or '$MY_CONFIG_VAR'",  # noqa: E501 # FIXME CoP
                    "type": "value_error",
                },
                {
                    "loc": ("connection_string",),
                    "msg": "'http_path' query param is invalid or missing",
                    "type": "value_error.url.query.http_path",
                },
            ],
            id="missing http_path",
        ),
        pytest.param(
            "databricks://token:my_token>@my_host:1234?http_path=/path/a/&http_path=/path/b/",
            [
                {
                    "loc": ("connection_string",),
                    "msg": "ConfigStr - contains no config template strings in the format '${MY_CONFIG_VAR}' or '$MY_CONFIG_VAR'",  # noqa: E501 # FIXME CoP
                    "type": "value_error",
                },
                {
                    "loc": ("connection_string",),
                    "msg": "Only one `http_path` query entry is allowed",
                    "type": "value_error",
                },
            ],
            id="multiple http_paths",
        ),
        pytest.param(
            "databricks://token:my_token>@my_host:1234?http_path=/a/b/c&schema=dev",
            [
                {
                    "loc": ("connection_string",),
                    "msg": "ConfigStr - contains no config template strings in the format '${MY_CONFIG_VAR}' or '$MY_CONFIG_VAR'",  # noqa: E501 # FIXME CoP
                    "type": "value_error",
                },
                {
                    "loc": ("connection_string",),
                    "msg": "'catalog' query param is invalid or missing",
                    "type": "value_error.url.query.catalog",
                },
            ],
            id="missing catalog",
        ),
        pytest.param(
            "databricks://token:my_token>@my_host:1234?http_path=/a/b/c&catalog=dev",
            [
                {
                    "loc": ("connection_string",),
                    "msg": "ConfigStr - contains no config template strings in the format '${MY_CONFIG_VAR}' or '$MY_CONFIG_VAR'",  # noqa: E501 # FIXME CoP
                    "type": "value_error",
                },
                {
                    "loc": ("connection_string",),
                    "msg": "'schema' query param is invalid or missing",
                    "type": "value_error.url.query.schema",
                },
            ],
            id="missing schema",
        ),
    ],
)
def test_invalid_connection_string_raises_dsn_error(
    connection_string: str, expected_errors: list[dict]
):
    with pytest.raises(pydantic.ValidationError) as exc_info:
        _ = DatabricksSQLDatasource(name="my_databricks", connection_string=connection_string)

    assert expected_errors == exc_info.value.errors()
    assert "my_token" not in str(exc_info.value.errors())
