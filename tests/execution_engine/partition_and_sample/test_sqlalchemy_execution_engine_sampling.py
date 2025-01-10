from __future__ import annotations

import datetime
import os
from typing import List

import pandas as pd
import pytest
from dateutil.parser import parse

from great_expectations.compatibility.sqlalchemy_compatibility_wrappers import (
    add_dataframe_to_db,
)
from great_expectations.core.batch_spec import SqlAlchemyDatasourceBatchSpec
from great_expectations.core.id_dict import BatchSpec
from great_expectations.data_context.util import file_relative_path
from great_expectations.execution_engine import SqlAlchemyExecutionEngine
from great_expectations.execution_engine.partition_and_sample.sqlalchemy_data_sampler import (
    SqlAlchemyDataSampler,
)
from great_expectations.execution_engine.sqlalchemy_batch_data import (
    SqlAlchemyBatchData,
)
from great_expectations.execution_engine.sqlalchemy_dialect import GXSqlDialect
from great_expectations.self_check.util import build_sa_execution_engine
from great_expectations.util import import_library_module

try:
    sqlalchemy = pytest.importorskip("sqlalchemy")
except ImportError:
    sqlalchemy = None


pytestmark = [
    pytest.mark.sqlalchemy_version_compatibility,
    pytest.mark.external_sqldialect,
]


@pytest.mark.unit
@pytest.mark.parametrize(
    "underscore_prefix",
    [
        pytest.param("_", id="underscore prefix"),
        pytest.param("", id="no underscore prefix"),
    ],
)
@pytest.mark.parametrize(
    "sampler_method_name",
    [
        pytest.param(sampler_method_name, id=sampler_method_name)
        for sampler_method_name in [
            "sample_using_limit",
            "sample_using_random",
            "sample_using_mod",
            "sample_using_a_list",
            "sample_using_md5",
        ]
    ],
)
def test_get_sampler_method(underscore_prefix: str, sampler_method_name: str):
    """What does this test and why?

    This test is to ensure that the sampler methods are accessible with and without underscores.
    When new sampling methods are added, the parameter list should be updated.
    """
    data_partitioner: SqlAlchemyDataSampler = SqlAlchemyDataSampler()

    sampler_method_name_with_prefix = f"{underscore_prefix}{sampler_method_name}"

    assert data_partitioner.get_sampler_method(sampler_method_name_with_prefix) == getattr(
        data_partitioner, sampler_method_name
    )


def clean_query_for_comparison(query_string: str) -> str:
    """Remove whitespace and case from query for easy comparison.

    Args:
        query_string: query string to convert.

    Returns:
        String with removed whitespace and converted to lowercase.
    """
    """Remove """
    return query_string.replace("\n", "").replace("\t", "").replace(" ", "").lower()


@pytest.fixture
def dialect_name_to_sql_statement():
    def _dialect_name_to_sql_statement(dialect_name: GXSqlDialect) -> str:
        dialect_name_to_sql_statement: dict = {
            GXSqlDialect.POSTGRESQL: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE LIMIT 10",  # noqa: E501 # FIXME CoP
            GXSqlDialect.MYSQL: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE = 1 LIMIT 10",
            GXSqlDialect.ORACLE: "SELECT * FROM test_schema_name.test_table WHERE 1 = 1 AND ROWNUM <= 10",  # noqa: E501 # FIXME CoP
            GXSqlDialect.MSSQL: "SELECT TOP 10 * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE 1 = 1",
            GXSqlDialect.SQLITE: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE 1 = 1 LIMIT 10 OFFSET 0",  # noqa: E501 # FIXME CoP
            GXSqlDialect.BIGQUERY: "SELECT * FROM `TEST_SCHEMA_NAME`.`TEST_TABLE` WHERE TRUE LIMIT 10",  # noqa: E501 # FIXME CoP
            GXSqlDialect.SNOWFLAKE: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE LIMIT 10",
            GXSqlDialect.REDSHIFT: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE LIMIT 10",
            GXSqlDialect.AWSATHENA: 'SELECT * FROM "TEST_SCHEMA_NAME"."TEST_TABLE" WHERE TRUE LIMIT 10',  # noqa: E501 # FIXME CoP
            GXSqlDialect.DREMIO: 'SELECT * FROM "TEST_SCHEMA_NAME"."TEST_TABLE" WHERE 1 = 1 LIMIT 10',  # noqa: E501 # FIXME CoP
            GXSqlDialect.TERADATASQL: "SELECT TOP 10 * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE 1 = 1",  # noqa: E501 # FIXME CoP
            GXSqlDialect.TRINO: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE LIMIT 10",
            GXSqlDialect.HIVE: "SELECT * FROM `TEST_SCHEMA_NAME`.`TEST_TABLE` WHERE TRUE LIMIT 10",
            GXSqlDialect.VERTICA: "SELECT * FROM TEST_SCHEMA_NAME.TEST_TABLE WHERE TRUE LIMIT 10",
        }
        return dialect_name_to_sql_statement[dialect_name]

    return _dialect_name_to_sql_statement


@pytest.fixture
def pytest_parsed_arguments(request):
    return request.config.option


# Despite being parameterized over GXSqlDialect, this test skips if the flag corresponding to that dialect isn't  # noqa: E501 # FIXME CoP
# passed in. Most of these dialects are never run in CI.
@pytest.mark.all_backends
@pytest.mark.parametrize(
    "dialect_name",
    [
        pytest.param(dialect_name, id=dialect_name.value, marks=pytest.mark.external_sqldialect)
        for dialect_name in GXSqlDialect.get_all_dialects()
    ],
)
def test_sample_using_limit_builds_correct_query_where_clause_none(  # noqa: C901 # FIXME CoP
    dialect_name: GXSqlDialect,
    dialect_name_to_sql_statement,
    sa,
    pytest_parsed_arguments,
):
    """What does this test and why?

    partition_on_limit should build the appropriate query based on input parameters.
    This tests dialects that differ from the standard dialect, not each dialect exhaustively.
    """
    if hasattr(pytest_parsed_arguments, str(dialect_name.value)):
        if not getattr(pytest_parsed_arguments, str(dialect_name.value)):
            pytest.skip(
                f"Skipping {dialect_name.value!s} since the --{dialect_name.value!s} pytest flag was not set"  # noqa: E501 # FIXME CoP
            )
    else:
        pytest.skip(
            f"Skipping {dialect_name.value!s} since the dialect is not runnable via pytest flag"
        )

    # 1. Setup
    class MockSqlAlchemyExecutionEngine:
        def __init__(self, dialect_name: GXSqlDialect):
            self._dialect_name = dialect_name
            self._connection_string = self.dialect_name_to_connection_string(dialect_name)

        DIALECT_TO_CONNECTION_STRING_STUB: dict = {
            GXSqlDialect.POSTGRESQL: "postgresql://",
            GXSqlDialect.MYSQL: "mysql+pymysql://",
            GXSqlDialect.ORACLE: "oracle+cx_oracle://",
            GXSqlDialect.MSSQL: "mssql+pyodbc://",
            GXSqlDialect.SQLITE: "sqlite:///",
            GXSqlDialect.BIGQUERY: "bigquery://",
            GXSqlDialect.SNOWFLAKE: "snowflake://",
            GXSqlDialect.REDSHIFT: "redshift+psycopg2://",
            GXSqlDialect.AWSATHENA: "awsathena+rest://@athena.us-east-1.amazonaws.com/some_test_db?s3_staging_dir=s3://some-s3-path/",
            GXSqlDialect.DREMIO: "dremio://",
            GXSqlDialect.TERADATASQL: "teradatasql://",
            GXSqlDialect.TRINO: "trino://",
            GXSqlDialect.HIVE: "hive://",
            GXSqlDialect.VERTICA: "vertica+vertica_python://",
        }

        @property
        def dialect_name(self) -> str:
            return self._dialect_name.value

        def dialect_name_to_connection_string(self, dialect_name: GXSqlDialect) -> str:
            return self.DIALECT_TO_CONNECTION_STRING_STUB.get(dialect_name)

        _BIGQUERY_MODULE_NAME = "sqlalchemy_bigquery"

        @property
        def dialect(self) -> sa.engine.Dialect:
            # TODO: AJB 20220512 move this dialect retrieval to a separate class from the SqlAlchemyExecutionEngine  # noqa: E501 # FIXME CoP
            #  and then use it here.
            dialect_name: GXSqlDialect = self._dialect_name
            if dialect_name == GXSqlDialect.ORACLE:
                # noinspection PyUnresolvedReferences
                return import_library_module(module_name="sqlalchemy.dialects.oracle").dialect()
            elif dialect_name == GXSqlDialect.SNOWFLAKE:
                # noinspection PyUnresolvedReferences
                return import_library_module(
                    module_name="snowflake.sqlalchemy.snowdialect"
                ).dialect()
            elif dialect_name == GXSqlDialect.DREMIO:
                # WARNING: Dremio Support is experimental, functionality is not fully under test
                # noinspection PyUnresolvedReferences
                return import_library_module(module_name="sqlalchemy_dremio.pyodbc").dialect()
            # NOTE: AJB 20220512 Redshift dialect is not yet fully supported.
            # The below throws an `AttributeError: type object 'RedshiftDialect_psycopg2' has no attribute 'positional'`  # noqa: E501 # FIXME CoP
            # elif dialect_name == "redshift":
            #     return import_library_module(
            #         module_name="sqlalchemy_redshift.dialect"
            #     ).RedshiftDialect
            elif dialect_name == GXSqlDialect.BIGQUERY:
                # noinspection PyUnresolvedReferences
                return import_library_module(module_name=self._BIGQUERY_MODULE_NAME).dialect()
            elif dialect_name == GXSqlDialect.TERADATASQL:
                # WARNING: Teradata Support is experimental, functionality is not fully under test
                # noinspection PyUnresolvedReferences
                return import_library_module(module_name="teradatasqlalchemy.dialect").dialect()
            else:
                return sa.create_engine(self._connection_string).dialect

    mock_execution_engine: MockSqlAlchemyExecutionEngine = MockSqlAlchemyExecutionEngine(
        dialect_name=dialect_name
    )

    data_sampler: SqlAlchemyDataSampler = SqlAlchemyDataSampler()

    # 2. Create query using sampler
    table_name: str = "test_table"
    batch_spec = BatchSpec(
        table_name=table_name,
        schema_name="test_schema_name",
        sampling_method="sample_using_limit",
        sampling_kwargs={"n": 10},
    )
    query = data_sampler.sample_using_limit(
        execution_engine=mock_execution_engine, batch_spec=batch_spec, where_clause=None
    )

    if not isinstance(query, str):
        query_str: str = clean_query_for_comparison(
            str(
                query.compile(
                    dialect=mock_execution_engine.dialect,
                    compile_kwargs={"literal_binds": True},
                )
            )
        )
    else:
        query_str: str = clean_query_for_comparison(query)

    expected: str = clean_query_for_comparison(dialect_name_to_sql_statement(dialect_name))

    assert query_str == expected


@pytest.mark.sqlite
def test_sqlite_sample_using_limit(sa):
    csv_path: str = file_relative_path(
        os.path.dirname(os.path.dirname(__file__)),  # noqa: PTH120 # FIXME CoP
        os.path.join(  # noqa: PTH118 # FIXME CoP
            "test_sets",
            "taxi_yellow_tripdata_samples",
            "ten_trips_from_each_month",
            "yellow_tripdata_sample_10_trips_from_each_month.csv",
        ),
    )
    df: pd.DataFrame = pd.read_csv(csv_path)
    engine: SqlAlchemyExecutionEngine = build_sa_execution_engine(df, sa)

    n: int = 10
    batch_spec: SqlAlchemyDatasourceBatchSpec = SqlAlchemyDatasourceBatchSpec(
        table_name="test",
        schema_name="main",
        sampling_method="sample_using_limit",
        sampling_kwargs={"n": n},
    )
    batch_data: SqlAlchemyBatchData = engine.get_batch_data(batch_spec=batch_spec)

    # Right number of rows?
    num_rows: int = batch_data.execution_engine.execute_query(
        sa.select(sa.func.count()).select_from(batch_data.selectable)
    ).scalar()
    assert num_rows == n

    # Right rows?
    rows: list[sa.RowMapping] = (
        batch_data.execution_engine.execute_query(
            sa.select(sa.text("*")).select_from(batch_data.selectable)
        )
        .mappings()
        .fetchall()
    )

    row_dates: List[datetime.datetime] = [parse(row["pickup_datetime"]) for row in rows]
    for row_date in row_dates:
        assert row_date.month == 1
        assert row_date.year == 2018


@pytest.mark.sqlite
def test_sample_using_random(sqlite_view_engine, test_df):
    my_execution_engine: SqlAlchemyExecutionEngine = SqlAlchemyExecutionEngine(
        engine=sqlite_view_engine
    )

    p: float
    batch_spec: SqlAlchemyDatasourceBatchSpec
    batch_data: SqlAlchemyBatchData
    num_rows: int
    rows_0: List[tuple]
    rows_1: List[tuple]

    # First, make sure that degenerative case never passes.

    test_df_0: pd.DataFrame = test_df.iloc[:1]
    add_dataframe_to_db(df=test_df_0, name="test_table_0", con=my_execution_engine.engine)

    p = 1.0
    batch_spec = SqlAlchemyDatasourceBatchSpec(
        table_name="test_table_0",
        schema_name="main",
        sampling_method="_sample_using_random",
        sampling_kwargs={"p": p},
    )

    batch_data = my_execution_engine.get_batch_data(batch_spec=batch_spec)
    num_rows = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(batch_data.selectable)
    ).scalar()
    assert num_rows == round(p * test_df_0.shape[0])

    rows_0: List[tuple] = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.text("*")).select_from(batch_data.selectable)
    ).fetchall()

    batch_data = my_execution_engine.get_batch_data(batch_spec=batch_spec)
    num_rows = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(batch_data.selectable)
    ).scalar()
    assert num_rows == round(p * test_df_0.shape[0])

    rows_1: List[tuple] = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.text("*")).select_from(batch_data.selectable)
    ).fetchall()

    assert len(rows_0) == len(rows_1) == 1

    assert rows_0 == rows_1

    # Second, verify that realistic case always returns different random sample of rows.

    test_df_1: pd.DataFrame = test_df
    add_dataframe_to_db(df=test_df_1, name="test_table_1", con=my_execution_engine.engine)

    p = 2.0e-1
    batch_spec = SqlAlchemyDatasourceBatchSpec(
        table_name="test_table_1",
        schema_name="main",
        sampling_method="_sample_using_random",
        sampling_kwargs={"p": p},
    )

    batch_data = my_execution_engine.get_batch_data(batch_spec=batch_spec)
    num_rows = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(batch_data.selectable)
    ).scalar()
    assert num_rows == round(p * test_df_1.shape[0])

    rows_0 = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.text("*")).select_from(batch_data.selectable)
    ).fetchall()

    batch_data = my_execution_engine.get_batch_data(batch_spec=batch_spec)
    num_rows = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(batch_data.selectable)
    ).scalar()
    assert num_rows == round(p * test_df_1.shape[0])

    rows_1 = batch_data.execution_engine.execute_query(
        sqlalchemy.select(sqlalchemy.text("*")).select_from(batch_data.selectable)
    ).fetchall()

    assert len(rows_0) == len(rows_1)

    assert rows_0 != rows_1


@pytest.mark.unit
def test_sample_using_random_batch_spec_test_table_name_required():
    fake_execution_engine = None
    batch_spec = BatchSpec()
    with pytest.raises(ValueError) as e:
        SqlAlchemyDataSampler.sample_using_random(
            execution_engine=fake_execution_engine, batch_spec=batch_spec
        )
    assert "table name must be specified" in str(e.value)


@pytest.mark.unit
def test_sample_using_random_batch_spec_test_sampling_kwargs_required():
    fake_execution_engine = None
    batch_spec = BatchSpec(table_name="table")
    with pytest.raises(ValueError) as e:
        SqlAlchemyDataSampler.sample_using_random(
            execution_engine=fake_execution_engine, batch_spec=batch_spec
        )
        assert "sample_using_random" in str(e.value)


@pytest.mark.unit
@pytest.mark.parametrize("sampling_kwargs", [{}, "a_string", []])
def test_sample_using_random_batch_spec_test_sampling_kwargs_p_required(
    sampling_kwargs,
):
    fake_execution_engine = None
    batch_spec = BatchSpec(table_name="table", sampling_kwargs=sampling_kwargs)
    with pytest.raises(ValueError) as e:
        SqlAlchemyDataSampler.sample_using_random(
            execution_engine=fake_execution_engine, batch_spec=batch_spec
        )
        assert "sample_using_random" in str(e.value)
