import logging
import re
from typing import TYPE_CHECKING, List, cast
from unittest import mock

import pytest

from great_expectations.compatibility import azure
from great_expectations.core import IDDict
from great_expectations.core.batch import LegacyBatchDefinition
from great_expectations.core.util import AzureUrl
from great_expectations.datasource.fluent import BatchRequest
from great_expectations.datasource.fluent.data_connector import (
    AzureBlobStorageDataConnector,
)

if TYPE_CHECKING:
    from great_expectations.datasource.fluent.data_connector import (
        DataConnector,
    )


logger = logging.getLogger(__name__)


if not (azure.storage and azure.BlobServiceClient and azure.ContainerClient):  # type: ignore[truthy-function] # False if NotImported
    pytest.skip(
        'Could not import "azure.storage.blob" from Microsoft Azure cloud',
        allow_module_level=True,
    )


class MockContainerClient:
    pass


class MockBlobServiceClient:
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def get_container_client(self, container: str) -> azure.ContainerClient:
        return cast(azure.ContainerClient, MockContainerClient())


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_basic_instantiation(mock_list_keys):
    mock_list_keys.return_value = [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())
    my_data_connector: DataConnector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"alpha-(.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 3
    assert my_data_connector.get_matched_data_references()[:3] == [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_instantiation_batching_regex_does_not_match_paths(mock_list_keys):
    mock_list_keys.return_value = [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())
    my_data_connector: DataConnector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 0
    assert my_data_connector.get_matched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_references()[:3] == [
        "alpha-1.csv",
        "alpha-2.csv",
        "alpha-3.csv",
    ]
    assert my_data_connector.get_unmatched_data_reference_count() == 3


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_return_all_batch_definitions_unsorted(mock_list_keys):
    mock_list_keys.return_value = [
        "abe_20200809_1040.csv",
        "alex_20200809_1000.csv",
        "alex_20200819_1300.csv",
        "eugene_20200809_1500.csv",
        "eugene_20201129_1900.csv",
        "james_20200713_1567.csv",
        "james_20200810_1003.csv",
        "james_20200811_1009.csv",
        "will_20200809_1002.csv",
        "will_20200810_1001.csv",
    ]

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())
    my_data_connector: DataConnector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    # with missing BatchRequest arguments
    with pytest.raises(TypeError):
        # noinspection PyArgumentList
        my_data_connector.get_batch_definition_list()

    # with empty options
    unsorted_batch_definition_list: List[LegacyBatchDefinition] = (
        my_data_connector.get_batch_definition_list(
            BatchRequest(
                datasource_name="my_file_path_datasource",
                data_asset_name="my_azure_blob_storage_data_asset",
                options={},
            )
        )
    )
    expected: List[LegacyBatchDefinition] = [
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "abe_20200809_1040.csv",
                    "name": "abe",
                    "timestamp": "20200809",
                    "price": "1040",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "alex_20200809_1000.csv",
                    "name": "alex",
                    "timestamp": "20200809",
                    "price": "1000",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "alex_20200819_1300.csv",
                    "name": "alex",
                    "timestamp": "20200819",
                    "price": "1300",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "eugene_20200809_1500.csv",
                    "name": "eugene",
                    "timestamp": "20200809",
                    "price": "1500",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "eugene_20201129_1900.csv",
                    "name": "eugene",
                    "timestamp": "20201129",
                    "price": "1900",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "james_20200713_1567.csv",
                    "name": "james",
                    "timestamp": "20200713",
                    "price": "1567",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "james_20200810_1003.csv",
                    "name": "james",
                    "timestamp": "20200810",
                    "price": "1003",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "james_20200811_1009.csv",
                    "name": "james",
                    "timestamp": "20200811",
                    "price": "1009",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "will_20200809_1002.csv",
                    "name": "will",
                    "timestamp": "20200809",
                    "price": "1002",
                }
            ),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict(
                {
                    "path": "will_20200810_1001.csv",
                    "name": "will",
                    "timestamp": "20200810",
                    "price": "1001",
                }
            ),
        ),
    ]
    assert expected == unsorted_batch_definition_list

    # with specified Batch query options
    unsorted_batch_definition_list = my_data_connector.get_batch_definition_list(
        BatchRequest(
            datasource_name="my_file_path_datasource",
            data_asset_name="my_azure_blob_storage_data_asset",
            options={"name": "alex", "timestamp": "20200819", "price": "1300"},
        )
    )
    assert expected[2:3] == unsorted_batch_definition_list


# TODO: <Alex>ALEX-UNCOMMENT_WHEN_SORTERS_ARE_INCLUDED_AND_TEST_SORTED_BATCH_DEFINITION_LIST</Alex>
# @pytest.mark.big
# @mock.patch(
#     "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"  # noqa: E501 # FIXME CoP
# )
# def test_return_all_batch_definitions_sorted(
#     mock_list_keys,
#     empty_data_context_stats_enabled,
# ):
#     mock_list_keys.return_value = [
#         "alex_20200809_1000.csv",
#         "eugene_20200809_1500.csv",
#         "james_20200811_1009.csv",
#         "abe_20200809_1040.csv",
#         "will_20200809_1002.csv",
#         "james_20200713_1567.csv",
#         "eugene_20201129_1900.csv",
#         "will_20200810_1001.csv",
#         "james_20200810_1003.csv",
#         "alex_20200819_1300.csv",
#     ]
#
#     azure_client: BlobServiceClient = cast(BlobServiceClient, MockBlobServiceClient())
#     my_data_connector: DataConnector = AzureBlobStorageDataConnector(
#         datasource_name="my_file_path_datasource",
#         data_asset_name="my_azure_blob_storage_data_asset",
#         batching_regex=re.compile(r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>.*)\.csv"),
#         azure_client=azure_client,
#         account_name="my_account",
#         container="my_container",
#         name_starts_with="",
#         file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
#     )
#     # with missing BatchRequest arguments
#     with pytest.raises(TypeError):
#         # noinspection PyArgumentList
#         my_data_connector.get_batch_definition_list()
#
#     # with empty options
#     sorted_batch_definition_list: List[
#         BatchDefinition
#     ] = my_data_connector.get_batch_definition_list(
#         BatchRequest(
#             datasource_name="my_file_path_datasource",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             options={},
#         )
#     )
#     expected: List[BatchDefinition] = [
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "alex_20200809_1000.csv", "name": "alex", "timestamp": "20200809", "price": "1000"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "eugene_20200809_1500.csv", "name": "eugene", "timestamp": "20200809", "price": "1500"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "james_20200811_1009.csv", "name": "james", "timestamp": "20200811", "price": "1009"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "abe_20200809_1040.csv", "name": "abe", "timestamp": "20200809", "price": "1040"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "will_20200809_1002.csv", "name": "will", "timestamp": "20200809", "price": "1002"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "james_20200713_1567.csv", "name": "james", "timestamp": "20200713", "price": "1567"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "eugene_20201129_1900.csv", "name": "eugene", "timestamp": "20201129", "price": "1900"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "will_20200810_1001.csv", "name": "will", "timestamp": "20200810", "price": "1001"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "james_20200810_1003.csv", "name": "james", "timestamp": "20200810", "price": "1003"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#         BatchDefinition(
#             datasource_name="my_file_path_datasource",
#             data_connector_name="fluent",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             batch_identifiers=IDDict(
#                 {"path": "alex_20200819_1300.csv", "name": "alex", "timestamp": "20200819", "price": "1300"}  # noqa: E501 # FIXME CoP
#             ),
#         ),
#     ]
#     assert expected == sorted_batch_definition_list
#
#     # with specified Batch query options
#     sorted_batch_definition_list = my_data_connector.get_batch_definition_list(
#         BatchRequest(
#             datasource_name="my_file_path_datasource",
#             data_asset_name="my_azure_blob_storage_data_asset",
#             options={"name": "alex", "timestamp": "20200819", "price": "1300"},
#         )
#     )
#     assert expected[9:10] == sorted_batch_definition_list
# TODO: <Alex>ALEX</Alex>


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_return_only_unique_batch_definitions(mock_list_keys):
    mock_list_keys.return_value = [
        "A/file_1.csv",
        "A/file_2.csv",
        "A/file_3.csv",
    ]

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())

    my_data_connector: DataConnector

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<name>.+).*\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="A/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "A/file_1.csv",
        "A/file_2.csv",
        "A/file_3.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 3
    assert my_data_connector.get_matched_data_references()[:3] == [
        "A/file_1.csv",
        "A/file_2.csv",
        "A/file_3.csv",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    mock_list_keys.return_value = [
        "B/file_1.csv",
        "B/file_2.csv",
    ]

    expected: List[LegacyBatchDefinition] = [
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict({"path": "B/file_1.csv", "filename": "file_1"}),
        ),
        LegacyBatchDefinition(
            datasource_name="my_file_path_datasource",
            data_connector_name="fluent",
            data_asset_name="my_azure_blob_storage_data_asset",
            batch_identifiers=IDDict({"path": "B/file_2.csv", "filename": "file_2"}),
        ),
    ]

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<filename>.+).*\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="B/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )

    unsorted_batch_definition_list: List[LegacyBatchDefinition] = (
        my_data_connector.get_batch_definition_list(
            BatchRequest(
                datasource_name="my_file_path_datasource",
                data_asset_name="my_azure_blob_storage_data_asset",
                options={},
            )
        )
    )
    assert expected == unsorted_batch_definition_list


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_alpha(mock_list_keys):
    mock_list_keys.return_value = [
        "test_dir_alpha/A.csv",
        "test_dir_alpha/B.csv",
        "test_dir_alpha/C.csv",
        "test_dir_alpha/D.csv",
    ]

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())
    my_data_connector: DataConnector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<part_1>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="test_dir_alpha/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    assert my_data_connector.get_data_reference_count() == 4
    assert my_data_connector.get_data_references()[:3] == [
        "test_dir_alpha/A.csv",
        "test_dir_alpha/B.csv",
        "test_dir_alpha/C.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 4
    assert my_data_connector.get_matched_data_references()[:3] == [
        "test_dir_alpha/A.csv",
        "test_dir_alpha/B.csv",
        "test_dir_alpha/C.csv",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    my_batch_definition_list: List[LegacyBatchDefinition]
    my_batch_definition: LegacyBatchDefinition

    my_batch_request: BatchRequest

    # Try to fetch a batch from a nonexistent asset
    my_batch_request = BatchRequest(datasource_name="BASE", data_asset_name="A", options={})
    my_batch_definition_list = my_data_connector.get_batch_definition_list(
        batch_request=my_batch_request
    )
    assert len(my_batch_definition_list) == 0

    my_batch_request = BatchRequest(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        options={"part_1": "B"},
    )
    my_batch_definition_list = my_data_connector.get_batch_definition_list(
        batch_request=my_batch_request
    )
    assert len(my_batch_definition_list) == 1


@pytest.mark.big
@mock.patch(
    "great_expectations.datasource.fluent.data_asset.data_connector.azure_blob_storage_data_connector.list_azure_keys"
)
def test_foxtrot(mock_list_keys):
    mock_list_keys.return_value = []

    azure_client: azure.BlobServiceClient = cast(azure.BlobServiceClient, MockBlobServiceClient())

    my_data_connector: DataConnector

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<part_1>.+)-(?P<part_2>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )
    assert my_data_connector.get_data_reference_count() == 0
    assert my_data_connector.get_data_references()[:3] == []
    assert my_data_connector.get_matched_data_reference_count() == 0
    assert my_data_connector.get_matched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    mock_list_keys.return_value = [
        "test_dir_foxtrot/A/A-1.csv",
        "test_dir_foxtrot/A/A-2.csv",
        "test_dir_foxtrot/A/A-3.csv",
    ]

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<part_1>.+)-(?P<part_2>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="test_dir_foxtrot/A/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )

    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "test_dir_foxtrot/A/A-1.csv",
        "test_dir_foxtrot/A/A-2.csv",
        "test_dir_foxtrot/A/A-3.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 3
    assert my_data_connector.get_matched_data_references()[:3] == [
        "test_dir_foxtrot/A/A-1.csv",
        "test_dir_foxtrot/A/A-2.csv",
        "test_dir_foxtrot/A/A-3.csv",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    mock_list_keys.return_value = [
        "test_dir_foxtrot/B/B-1.txt",
        "test_dir_foxtrot/B/B-2.txt",
        "test_dir_foxtrot/B/B-3.txt",
    ]

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<part_1>.+)-(?P<part_2>.*)\.txt"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="test_dir_foxtrot/B/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )

    mock_list_keys.return_value = [
        "test_dir_foxtrot/B/B-1.txt",
        "test_dir_foxtrot/B/B-2.txt",
        "test_dir_foxtrot/B/B-3.txt",
    ]

    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "test_dir_foxtrot/B/B-1.txt",
        "test_dir_foxtrot/B/B-2.txt",
        "test_dir_foxtrot/B/B-3.txt",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 3
    assert my_data_connector.get_matched_data_references()[:3] == [
        "test_dir_foxtrot/B/B-1.txt",
        "test_dir_foxtrot/B/B-2.txt",
        "test_dir_foxtrot/B/B-3.txt",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    my_data_connector = AzureBlobStorageDataConnector(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        batching_regex=re.compile(r"(?P<part_1>.+)-(?P<part_2>.*)\.csv"),
        azure_client=azure_client,
        account_name="my_account",
        container="my_container",
        name_starts_with="test_dir_foxtrot/C/",
        file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
    )

    mock_list_keys.return_value = [
        "test_dir_foxtrot/C/C-2017.csv",
        "test_dir_foxtrot/C/C-2018.csv",
        "test_dir_foxtrot/C/C-2019.csv",
    ]

    assert my_data_connector.get_data_reference_count() == 3
    assert my_data_connector.get_data_references()[:3] == [
        "test_dir_foxtrot/C/C-2017.csv",
        "test_dir_foxtrot/C/C-2018.csv",
        "test_dir_foxtrot/C/C-2019.csv",
    ]
    assert my_data_connector.get_matched_data_reference_count() == 3
    assert my_data_connector.get_matched_data_references()[:3] == [
        "test_dir_foxtrot/C/C-2017.csv",
        "test_dir_foxtrot/C/C-2018.csv",
        "test_dir_foxtrot/C/C-2019.csv",
    ]
    assert my_data_connector.get_unmatched_data_references()[:3] == []
    assert my_data_connector.get_unmatched_data_reference_count() == 0

    my_batch_request = BatchRequest(
        datasource_name="my_file_path_datasource",
        data_asset_name="my_azure_blob_storage_data_asset",
        options={},
    )
    my_batch_definition_list: List[LegacyBatchDefinition] = (
        my_data_connector.get_batch_definition_list(batch_request=my_batch_request)
    )
    assert len(my_batch_definition_list) == 3
