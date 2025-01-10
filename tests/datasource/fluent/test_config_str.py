from __future__ import annotations

from typing import Callable, List, Union

import pytest
from pytest import MonkeyPatch

from great_expectations.compatibility import pydantic
from great_expectations.core.config_provider import (
    _ConfigurationProvider,
    _EnvironmentConfigurationProvider,
)
from great_expectations.datasource.fluent.config_str import (
    ConfigStr,
    ConfigUri,
    SecretStr,
)
from great_expectations.datasource.fluent.fluent_base_model import FluentBaseModel
from great_expectations.exceptions import MissingConfigVariableError

pytestmark = pytest.mark.unit


class MyClass(FluentBaseModel):
    normal_field: str
    secret_field: SecretStr
    config_field: ConfigStr
    config_field_w_default: ConfigStr = r"hey-${MY_SECRET}"  # type: ignore[assignment] # FIXME CoP


@pytest.fixture
def env_config_provider() -> _ConfigurationProvider:
    config_provider = _ConfigurationProvider()
    config_provider.register_provider(_EnvironmentConfigurationProvider())
    return config_provider


def test_config_provider_substitution(
    monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
):
    monkeypatch.setenv("MY_CONFIG", "bar")

    my_dict = {"my_key": r"foo${MY_CONFIG}", "another_key": r"${MY_CONFIG}"}
    subbed = env_config_provider.substitute_config(my_dict)

    assert subbed == {"my_key": "foobar", "another_key": "bar"}
    assert subbed != my_dict


def test_config_provider_substitution_raises_error(
    monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
):
    monkeypatch.setenv("NOT_MY_CONFIG", "bar")

    my_dict = {"my_key": r"foo${MY_CONFIG}", "another_key": r"${MY_CONFIG}"}

    with pytest.raises(MissingConfigVariableError):
        env_config_provider.substitute_config(my_dict)


def test_config_str_validation():
    with pytest.raises(pydantic.ValidationError, match="ConfigStr"):
        m = MyClass(normal_field="normal", secret_field="secret", config_field="invalid config")
        print(m)


@pytest.mark.parametrize(
    ["input_value", "expected"],
    [
        (r"${VALID_CONFIG_STR}", r"${VALID_CONFIG_STR}"),
        (
            r"postgres://user:${VALID_CONFIG_STR}@host/dbname",
            r"postgres://user:${VALID_CONFIG_STR}@host/dbname",
        ),
        ("postgres://userName@hostname", "postgres://userName@hostname"),
    ],
)
def test_as_union_file_type(input_value, expected):
    class MyClass(FluentBaseModel):
        my_field: Union[ConfigStr, pydantic.networks.PostgresDsn]

    m = MyClass(my_field=input_value)
    print(m)

    assert str(m.my_field) == expected


def test_config_substitution(monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider):
    monkeypatch.setenv("MY_ENV_VAR", "success")

    m = MyClass(
        normal_field="normal",
        secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
        config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
        config_field_w_default=r"hello-${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
    )
    assert m.config_field.get_config_value(env_config_provider) == "success"
    assert m.config_field_w_default.get_config_value(env_config_provider) == "hello-success"


def test_config_substitution_dict(
    monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
):
    monkeypatch.setenv("MY_ENV_VAR", "success")

    m = MyClass(
        normal_field="normal",
        secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
        config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
    )

    d = m.dict(config_provider=env_config_provider)
    assert d["config_field"] == "success"


def test_config_nested_substitution_dict(
    monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
):
    monkeypatch.setenv("MY_ENV_VAR", "success")

    class MyCollection(FluentBaseModel):
        my_classes: List[MyClass] = []

    MyCollection.update_forward_refs(MyClass=MyClass)

    m = MyCollection(
        my_classes=[
            MyClass(
                normal_field="normal",
                secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
                config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
            )
        ]
    )

    d = m.dict(config_provider=env_config_provider)
    assert d["my_classes"][0]["config_field"] == "success"


def test_config_nested_substitution_dict_raises_error_for_missing_config_var(
    monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
):
    monkeypatch.setenv("NOT_MY_ENV_VAR", "failure")

    class MyCollection(FluentBaseModel):
        my_classes: List[MyClass] = []

    MyCollection.update_forward_refs(MyClass=MyClass)

    m = MyCollection(
        my_classes=[
            MyClass(
                normal_field="normal",
                secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
                config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
            )
        ]
    )

    with pytest.raises(MissingConfigVariableError):
        m.dict(config_provider=env_config_provider)


@pytest.mark.parametrize("method", ["yaml", "dict", "json"])
def test_serialization_returns_original(monkeypatch: MonkeyPatch, method: str):
    monkeypatch.setenv("MY_ENV_VAR", "dont_serialize_me")

    m = MyClass(
        normal_field="normal",
        secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
        config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
    )
    serialize_method: Callable = getattr(m, method)
    dumped = str(serialize_method())
    assert "dont_serialize_me" not in dumped
    assert r"${MY_ENV_VAR}" in dumped


@pytest.mark.parametrize("method", ["yaml", "dict", "json"])
def test_nested_serialization_returns_original(monkeypatch: MonkeyPatch, method: str):
    # TODO: fix this
    class MyCollection(FluentBaseModel):
        my_classes: List[MyClass] = []

    MyCollection.update_forward_refs(MyClass=MyClass)

    monkeypatch.setenv("MY_ENV_VAR", "dont_serialize_me")

    m = MyCollection(
        my_classes=[
            MyClass(
                normal_field="normal",
                secret_field="secret",  # type: ignore[arg-type] # FIXME CoP
                config_field=r"${MY_ENV_VAR}",  # type: ignore[arg-type] # FIXME CoP
            )
        ]
    )
    serialize_method: Callable = getattr(m, method)
    dumped = str(serialize_method())
    assert "dont_serialize_me" not in dumped
    assert r"${MY_ENV_VAR}" in dumped


class TestSecretMasking:
    def test_validation_error(self):
        class MyUnionFields(FluentBaseModel):
            config_field: ConfigStr
            dsn_field: pydantic.PostgresDsn
            union_field: Union[ConfigStr, pydantic.PostgresDsn]

        with pytest.raises(pydantic.ValidationError) as exc_info:
            m = MyUnionFields(
                config_field="invalid_config",
                dsn_field="postgress://:invalid_config@localhost",
                union_field="invalid_config",
            )
            print(m)
        assert "invalid_config" not in str(exc_info.value)

    def test_repr(self):
        m = MyClass(
            normal_field="normal",
            secret_field="secret",
            config_field=r"${MY_ENV_VAR}",
        )
        assert repr(m.config_field) == r"ConfigStr('${MY_ENV_VAR}')"

    def test_str(self):
        m = MyClass(
            normal_field="normal",
            secret_field="secret",
            config_field=r"${MY_ENV_VAR}",
        )
        assert str(m.config_field) == r"${MY_ENV_VAR}"

    def test_serialization(
        self, monkeypatch: MonkeyPatch, env_config_provider: _ConfigurationProvider
    ):
        monkeypatch.setenv("MY_SECRET", "dont_serialize_me")
        m = MyClass(
            normal_field="normal",
            secret_field="my_secret",  # type: ignore[arg-type] # FIXME CoP
            config_field=r"${MY_SECRET}",  # type: ignore[arg-type] # FIXME CoP
        )

        # but it should not actually be used
        for dumped_str in [str(m.dict()), m.yaml(), m.json()]:
            print(dumped_str, "\n\n")
            assert "my_secret" not in dumped_str
            assert "dont_serialize_me" not in dumped_str
            assert r"${MY_SECRET}" in dumped_str


@pytest.mark.parametrize(
    "uri",
    [
        "http://my_user:${MY_PW}@example.com:8000/the/path/?query=here#fragment=is;this=bit",
        "http://${MY_USER}:${MY_PW}@example.com:8000/the/path/?query=here#fragment=is;this=bit",
        "http://${MY_USER}:${MY_PW}@example.com:8000/the/path/?query=here&query=again&query=and_again",
        "snowflake://my_user:${MY_PW}@account/db",
        "snowflake://${MY_USER}:${MY_PW}@account/db",
        "postgresql+psycopg2://my_user:${MY_PW}@host/db",
        "postgresql+psycopg2://${MY_USER}:${MY_PW}@host/db",
    ],
)
class TestConfigUri:
    def test_parts(
        self,
        env_config_provider: _ConfigurationProvider,
        monkeypatch: MonkeyPatch,
        uri: str,
    ):
        monkeypatch.setenv("MY_USER", "my_user")
        monkeypatch.setenv("MY_PW", "super_secret")

        parsed = pydantic.parse_obj_as(ConfigUri, uri)

        # ensure attributes are set
        assert parsed.scheme
        assert parsed.host
        assert parsed.path
        # ensure no attribute errors
        _ = parsed.query
        _ = parsed.fragment

        # ensure that the password (and user) are not substituted
        assert parsed.password == "${MY_PW}"
        assert parsed.user in ["${MY_USER}", "my_user"]

    def test_substitution(
        self,
        env_config_provider: _ConfigurationProvider,
        monkeypatch: MonkeyPatch,
        uri: str,
    ):
        monkeypatch.setenv("MY_USER", "my_user")
        monkeypatch.setenv("MY_PW", "super_secret")

        parsed = pydantic.parse_obj_as(ConfigUri, uri)

        substituted = parsed.get_config_value(env_config_provider)

        # ensure attributes are set
        assert substituted.scheme
        assert substituted.host
        assert substituted.path
        # ensure no attribute errors
        _ = substituted.query
        _ = substituted.fragment

        # ensure that the password (and user) are not substituted
        assert substituted.password == "super_secret"
        assert substituted.user == "my_user"

    def test_leakage(
        self,
        env_config_provider: _ConfigurationProvider,
        monkeypatch: MonkeyPatch,
        uri: str,
    ):
        """
        Ensure the config values are not leaked in the repr or str of the object
        or the component parts.
        """
        monkeypatch.setenv("MY_USER", "my_user")
        monkeypatch.setenv("MY_PW", "super_secret")

        parsed = pydantic.parse_obj_as(ConfigUri, uri)
        assert "super_secret" not in str(parsed)
        assert "super_secret" not in repr(parsed)
        assert parsed.password
        assert "super_secret" not in parsed.password

        if "my_user" not in uri:
            assert "my_user" not in str(parsed)
            assert "my_user" not in repr(parsed)
            assert parsed.user
            assert "my_user" not in parsed.user

    def test_params(self, uri: str):
        parsed = pydantic.parse_obj_as(ConfigUri, uri)
        assert isinstance(parsed.params, dict)

        if parsed.query:
            for q_key, values in parsed.params.items():
                for value in values:
                    assert f"{q_key}={value}" in parsed.query


class TestConfigUriInvalid:
    @pytest.mark.parametrize("uri", ["invalid_uri", "http:/example.com"])
    def test_invalid_uri(self, uri: str):
        with pytest.raises(pydantic.ValidationError):
            _ = pydantic.parse_obj_as(ConfigUri, uri)

    @pytest.mark.parametrize(
        "uri",
        [
            "${MY_SCHEME}://me:secret@account/db/schema",
            "snowflake://me:secret@${MY_ACCOUNT}/db/schema",
            "snowflake://me:secret@account/${MY_DB}/schema",
            "snowflake://me:secret@account/db/${MY_SCHEMA}",
            "snowflake://me:secret@account/db/my_schema?${MY_QUERY_PARAMS}",
            "snowflake://me:secret@account/db/my_schema?role=${MY_ROLE}",
        ],
    )
    def test_disallowed_substitution(self, uri: str):
        with pytest.raises(pydantic.ValidationError):
            _ = pydantic.parse_obj_as(ConfigUri, uri)

    def test_no_template_str(self):
        with pytest.raises(pydantic.ValidationError):
            _ = pydantic.parse_obj_as(ConfigUri, "snowflake://me:password@account/db")


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
