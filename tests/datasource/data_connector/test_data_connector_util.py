from unittest import mock

import pytest

from great_expectations.compatibility import google
from great_expectations.core.batch import IDDict, LegacyBatchDefinition
from great_expectations.datasource.fluent.data_connector.file_path_data_connector import (
    _invert_regex_to_data_reference_template,
    convert_batch_identifiers_to_data_reference_string_using_regex,
    map_batch_definition_to_data_reference_string_using_regex,
)
from great_expectations.datasource.fluent.data_connector.google_cloud_storage_data_connector import (  # noqa: E501 # FIXME CoP
    list_gcs_keys,
)


@pytest.mark.unit
def test_map_batch_definition_to_data_reference_string_using_regex():
    # not BatchDefinition
    my_batch_definition = "I_am_a_string"
    group_names = ["name", "timestamp", "price"]
    regex_pattern = r"^(.+)_(\d+)_(\d+)\.csv$"
    with pytest.raises(TypeError):
        # noinspection PyUnusedLocal,PyTypeChecker
        my_data_reference = map_batch_definition_to_data_reference_string_using_regex(
            batch_definition=my_batch_definition,
            regex_pattern=regex_pattern,
            group_names=group_names,
        )

    # group names do not match
    my_batch_definition = LegacyBatchDefinition(
        datasource_name="test_environment",
        data_connector_name="general_filesystem_data_connector",
        data_asset_name="TestFiles",
        batch_identifiers=IDDict({"name": "eugene", "timestamp": "20200809", "price": "1500"}),
    )
    group_names = ["i", "wont", "match"]
    regex_pattern = r"^(.+)_(\d+)_(\d+)\.csv$"
    with pytest.raises(KeyError):
        # noinspection PyUnusedLocal
        my_data_reference = map_batch_definition_to_data_reference_string_using_regex(
            batch_definition=my_batch_definition,
            regex_pattern=regex_pattern,
            group_names=group_names,
        )

    # success
    my_batch_definition = LegacyBatchDefinition(
        datasource_name="test_environment",
        data_connector_name="general_filesystem_data_connector",
        data_asset_name="TestFiles",
        batch_identifiers=IDDict({"name": "eugene", "timestamp": "20200809", "price": "1500"}),
    )
    group_names = ["name", "timestamp", "price"]
    regex_pattern = r"^(.+)_(\d+)_(\d+)\.csv$"

    my_data_reference = map_batch_definition_to_data_reference_string_using_regex(
        batch_definition=my_batch_definition,
        regex_pattern=regex_pattern,
        group_names=group_names,
    )
    assert my_data_reference == "eugene_20200809_1500.csv"


@pytest.mark.unit
def test_convert_batch_identifiers_to_data_reference_string_using_regex():
    pattern = r"^(.+)_(\d+)_(\d+)\.csv$"
    group_names = ["name", "timestamp", "price"]
    batch_identifiers = IDDict(
        **{
            "name": "alex",
            "timestamp": "20200809",
            "price": "1000",
        }
    )
    assert (
        convert_batch_identifiers_to_data_reference_string_using_regex(
            batch_identifiers=batch_identifiers,
            regex_pattern=pattern,
            group_names=group_names,
        )
        == "alex_20200809_1000.csv"
    )

    # Test an example with an uncaptured regex group (should return a WildcardDataReference)
    pattern = r"^(.+)_(\d+)_\d+\.csv$"
    group_names = ["name", "timestamp"]
    batch_identifiers = IDDict(
        **{
            "name": "alex",
            "timestamp": "20200809",
            "price": "1000",
        }
    )
    assert (
        convert_batch_identifiers_to_data_reference_string_using_regex(
            batch_identifiers=batch_identifiers,
            regex_pattern=pattern,
            group_names=group_names,
        )
        == "alex_20200809_*.csv"
    )

    # Test an example with an uncaptured regex group (should return a WildcardDataReference)
    pattern = r"^.+_(\d+)_(\d+)\.csv$"
    group_names = ["timestamp", "price"]
    batch_identifiers = IDDict(
        **{
            "name": "alex",
            "timestamp": "20200809",
            "price": "1000",
        }
    )
    assert (
        convert_batch_identifiers_to_data_reference_string_using_regex(
            batch_identifiers=batch_identifiers,
            regex_pattern=pattern,
            group_names=group_names,
        )
        == "*_20200809_1000.csv"
    )


# TODO: <Alex>Why does this method name have 2 underscores?</Alex>
@pytest.mark.unit
def test__invert_regex_to_data_reference_template():
    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"^(.+)_(\d+)_(\d+)\.csv$",
        group_names=["name", "timestamp", "price"],
    )
    assert returned == "{name}_{timestamp}_{price}.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"^(.+)_(\d+)_\d+\.csv$", group_names=["name", "timestamp"]
    )
    assert returned == "{name}_{timestamp}_*.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"^.+_(\d+)_(\d+)\.csv$", group_names=["timestamp", "price"]
    )
    assert returned == "*_{timestamp}_{price}.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"(^.+)_(\d+)_.\d\W\w[a-z](?!.*::.*::)\d\.csv$",
        group_names=["name", "timestamp"],
    )
    assert returned == "{name}_{timestamp}_*.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"(.*)-([ABC])\.csv", group_names=["name", "type"]
    )
    assert returned == "{name}-{type}.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern="yellow_tripdata_sample_2019-01.csv", group_names=[]
    )
    assert returned == "yellow_tripdata_sample_2019-01.csv"

    returned = _invert_regex_to_data_reference_template(
        regex_pattern=r"(.*)-[A|B|C]\.csv", group_names=["name"]
    )
    assert returned == "{name}-*.csv"

    # From https://github.com/madisonmay/CommonRegex/blob/master/commonregex.py
    date = r"(?:(?<!\:)(?<!\:\d)[0-3]?\d(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan\.?|january|feb\.?|february|mar\.?|march|apr\.?|april|may|jun\.?|june|jul\.?|july|aug\.?|august|sep\.?|september|oct\.?|october|nov\.?|november|dec\.?|december)|(?:jan\.?|january|feb\.?|february|mar\.?|march|apr\.?|april|may|jun\.?|june|jul\.?|july|aug\.?|august|sep\.?|september|oct\.?|october|nov\.?|november|dec\.?|december)\s+(?<!\:)(?<!\:\d)[0-3]?\d(?:st|nd|rd|th)?)(?:\,)?\s*(?:\d{4})?|[0-3]?\d[-\./][0-3]?\d[-\./]\d{2,4}"  # noqa: E501 # FIXME CoP
    time = r"\d{1,2}:\d{2} ?(?:[ap]\.?m\.?)?|\d[ap]\.?m\.?"
    phone = r"""((?:(?<![\d-])(?:\+?\d{1,3}[-.\s*]?)?(?:\(?\d{3}\)?[-.\s*]?)?\d{3}[-.\s*]?\d{4}(?![\d-]))|(?:(?<![\d-])(?:(?:\(\+?\d{2}\))|(?:\+?\d{2}))\s*\d{2}\s*\d{3}\s*\d{4}(?![\d-])))"""  # noqa: E501 # FIXME CoP
    phones_with_exts = r"((?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*(?:[2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|(?:[2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?(?:[2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?(?:[0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(?:\d+)?))"  # noqa: E501 # FIXME CoP
    link = r'(?i)((?:https?://|www\d{0,3}[.])?[a-z0-9.\-]+[.](?:(?:international)|(?:construction)|(?:contractors)|(?:enterprises)|(?:photography)|(?:immobilien)|(?:management)|(?:technology)|(?:directory)|(?:education)|(?:equipment)|(?:institute)|(?:marketing)|(?:solutions)|(?:builders)|(?:clothing)|(?:computer)|(?:democrat)|(?:diamonds)|(?:graphics)|(?:holdings)|(?:lighting)|(?:plumbing)|(?:training)|(?:ventures)|(?:academy)|(?:careers)|(?:company)|(?:domains)|(?:florist)|(?:gallery)|(?:guitars)|(?:holiday)|(?:kitchen)|(?:recipes)|(?:shiksha)|(?:singles)|(?:support)|(?:systems)|(?:agency)|(?:berlin)|(?:camera)|(?:center)|(?:coffee)|(?:estate)|(?:kaufen)|(?:luxury)|(?:monash)|(?:museum)|(?:photos)|(?:repair)|(?:social)|(?:tattoo)|(?:travel)|(?:viajes)|(?:voyage)|(?:build)|(?:cheap)|(?:codes)|(?:dance)|(?:email)|(?:glass)|(?:house)|(?:ninja)|(?:photo)|(?:shoes)|(?:solar)|(?:today)|(?:aero)|(?:arpa)|(?:asia)|(?:bike)|(?:buzz)|(?:camp)|(?:club)|(?:coop)|(?:farm)|(?:gift)|(?:guru)|(?:info)|(?:jobs)|(?:kiwi)|(?:land)|(?:limo)|(?:link)|(?:menu)|(?:mobi)|(?:moda)|(?:name)|(?:pics)|(?:pink)|(?:post)|(?:rich)|(?:ruhr)|(?:sexy)|(?:tips)|(?:wang)|(?:wien)|(?:zone)|(?:biz)|(?:cab)|(?:cat)|(?:ceo)|(?:com)|(?:edu)|(?:gov)|(?:int)|(?:mil)|(?:net)|(?:onl)|(?:org)|(?:pro)|(?:red)|(?:tel)|(?:uno)|(?:xxx)|(?:ac)|(?:ad)|(?:ae)|(?:af)|(?:ag)|(?:ai)|(?:al)|(?:am)|(?:an)|(?:ao)|(?:aq)|(?:ar)|(?:as)|(?:at)|(?:au)|(?:aw)|(?:ax)|(?:az)|(?:ba)|(?:bb)|(?:bd)|(?:be)|(?:bf)|(?:bg)|(?:bh)|(?:bi)|(?:bj)|(?:bm)|(?:bn)|(?:bo)|(?:br)|(?:bs)|(?:bt)|(?:bv)|(?:bw)|(?:by)|(?:bz)|(?:ca)|(?:cc)|(?:cd)|(?:cf)|(?:cg)|(?:ch)|(?:ci)|(?:ck)|(?:cl)|(?:cm)|(?:cn)|(?:co)|(?:cr)|(?:cu)|(?:cv)|(?:cw)|(?:cx)|(?:cy)|(?:cz)|(?:de)|(?:dj)|(?:dk)|(?:dm)|(?:do)|(?:dz)|(?:ec)|(?:ee)|(?:eg)|(?:er)|(?:es)|(?:et)|(?:eu)|(?:fi)|(?:fj)|(?:fk)|(?:fm)|(?:fo)|(?:fr)|(?:ga)|(?:gb)|(?:gd)|(?:ge)|(?:gf)|(?:gg)|(?:gh)|(?:gi)|(?:gl)|(?:gm)|(?:gn)|(?:gp)|(?:gq)|(?:gr)|(?:gs)|(?:gt)|(?:gu)|(?:gw)|(?:gy)|(?:hk)|(?:hm)|(?:hn)|(?:hr)|(?:ht)|(?:hu)|(?:id)|(?:ie)|(?:il)|(?:im)|(?:in)|(?:io)|(?:iq)|(?:ir)|(?:is)|(?:it)|(?:je)|(?:jm)|(?:jo)|(?:jp)|(?:ke)|(?:kg)|(?:kh)|(?:ki)|(?:km)|(?:kn)|(?:kp)|(?:kr)|(?:kw)|(?:ky)|(?:kz)|(?:la)|(?:lb)|(?:lc)|(?:li)|(?:lk)|(?:lr)|(?:ls)|(?:lt)|(?:lu)|(?:lv)|(?:ly)|(?:ma)|(?:mc)|(?:md)|(?:me)|(?:mg)|(?:mh)|(?:mk)|(?:ml)|(?:mm)|(?:mn)|(?:mo)|(?:mp)|(?:mq)|(?:mr)|(?:ms)|(?:mt)|(?:mu)|(?:mv)|(?:mw)|(?:mx)|(?:my)|(?:mz)|(?:na)|(?:nc)|(?:ne)|(?:nf)|(?:ng)|(?:ni)|(?:nl)|(?:no)|(?:np)|(?:nr)|(?:nu)|(?:nz)|(?:om)|(?:pa)|(?:pe)|(?:pf)|(?:pg)|(?:ph)|(?:pk)|(?:pl)|(?:pm)|(?:pn)|(?:pr)|(?:ps)|(?:pt)|(?:pw)|(?:py)|(?:qa)|(?:re)|(?:ro)|(?:rs)|(?:ru)|(?:rw)|(?:sa)|(?:sb)|(?:sc)|(?:sd)|(?:se)|(?:sg)|(?:sh)|(?:si)|(?:sj)|(?:sk)|(?:sl)|(?:sm)|(?:sn)|(?:so)|(?:sr)|(?:st)|(?:su)|(?:sv)|(?:sx)|(?:sy)|(?:sz)|(?:tc)|(?:td)|(?:tf)|(?:tg)|(?:th)|(?:tj)|(?:tk)|(?:tl)|(?:tm)|(?:tn)|(?:to)|(?:tp)|(?:tr)|(?:tt)|(?:tv)|(?:tw)|(?:tz)|(?:ua)|(?:ug)|(?:uk)|(?:us)|(?:uy)|(?:uz)|(?:va)|(?:vc)|(?:ve)|(?:vg)|(?:vi)|(?:vn)|(?:vu)|(?:wf)|(?:ws)|(?:ye)|(?:yt)|(?:za)|(?:zm)|(?:zw))(?:/[^\s()<>]+[^\s`!()\[\]{};:\'".,<>?\xab\xbb\u201c\u201d\u2018\u2019])?)'
    email = r"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"  # noqa: E501 # FIXME CoP
    ip = r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"  # noqa: E501 # FIXME CoP
    ipv6 = r"\s*(?!.*::.*::)(?:(?!:)|:(?=:))(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)){6}(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)[0-9a-f]{0,4}(?:(?<=::)|(?<!:)|(?<=:)(?<!::):)|(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)){3})\s*"  # noqa: E501 # FIXME CoP
    price = r"[$]\s?[+-]?[0-9]{1,3}(?:(?:,?[0-9]{3}))*(?:\.[0-9]{1,2})?"
    hex_color = r"(#(?:[0-9a-fA-F]{8})|#(?:[0-9a-fA-F]{3}){1,2})\\b"
    credit_card = r"((?:(?:\\d{4}[- ]?){3}\\d{4}|\\d{15,16}))(?![\\d])"
    btc_address = (
        r"(?<![a-km-zA-HJ-NP-Z0-9])[13][a-km-zA-HJ-NP-Z0-9]{26,33}(?![a-km-zA-HJ-NP-Z0-9])"
    )
    street_address = r"\d{1,4} [\w\s]{1,20}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\W?(?=\s|$)"  # noqa: E501 # FIXME CoP
    zip_code = r"\b\d{5}(?:[-\s]\d{4})?\b"
    po_box = r"P\.? ?O\.? Box \d+"
    ssn = r"(?!000|666|333)0*(?:[0-6][0-9][0-9]|[0-7][0-6][0-9]|[0-7][0-7][0-2])[- ](?!00)[0-9]{2}[- ](?!0000)[0-9]{4}"  # noqa: E501 # FIXME CoP

    regexes = {
        "dates": date,
        "times": time,
        "phones": phone,
        "phones_with_exts": phones_with_exts,
        "links": link,
        "emails": email,
        "ips": ip,
        "ipv6s": ipv6,
        "prices": price,
        "hex_colors": hex_color,
        "credit_cards": credit_card,
        "btc_addresses": btc_address,
        "street_addresses": street_address,
        "zip_codes": zip_code,
        "po_boxes": po_box,
        "ssn_number": ssn,
    }

    # This is a scattershot approach to making sure that our regex parsing has good coverage.
    # It does not guarantee perfect coverage of all regex patterns.
    for name, regex in regexes.items():
        print(name)
        group_names = ["name", "timestamp"]
        _invert_regex_to_data_reference_template(regex_pattern=regex, group_names=group_names)


@pytest.mark.skipif(
    not google.storage,
    reason="Could not import 'storage' from google.cloud",
)
@mock.patch("great_expectations.compatibility.google.Client")
@pytest.mark.big
def test_list_gcs_keys_overwrites_delimiter(mock_gcs_conn):
    # Set defaults for ConfiguredAssetGCSDataConnector
    query_options = {"delimiter": None}
    with pytest.warns(UserWarning):  # warning from /datasource/data_connector/util.py:383
        list_gcs_keys(mock_gcs_conn, query_options, recursive=False)
    assert query_options["delimiter"] == "/"

    # Set defaults for InferredAssetGCSDataConnector
    query_options = {"delimiter": "/"}
    with pytest.warns(UserWarning):  # warning from /datasource/data_connector/util.py:390
        list_gcs_keys(mock_gcs_conn, query_options, recursive=True)
    assert query_options["delimiter"] is None
