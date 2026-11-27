from endpoints.responses.rom import PROVIDER_METADATA_FIELDS, SimpleRomSchema
from models.rom import (
    FIELD_PROVIDER_COLUMNS,
    PROVIDER_METADATA_COLUMNS,
    provider_columns_read_by,
)


def test_every_listed_field_is_a_schema_field() -> None:
    assert set(FIELD_PROVIDER_COLUMNS) <= set(SimpleRomSchema.model_fields) | set(
        SimpleRomSchema.model_computed_fields
    )


def test_every_provider_field_reads_its_column() -> None:
    assert set(PROVIDER_METADATA_FIELDS) <= set(FIELD_PROVIDER_COLUMNS)
    assert {c for cols in FIELD_PROVIDER_COLUMNS.values() for c in cols} >= set(
        PROVIDER_METADATA_COLUMNS
    )


def test_a_response_without_provider_fields_reads_no_provider_column() -> None:
    assert provider_columns_read_by({"id", "name", "fs_name"}) == ()


def test_a_derived_field_reads_the_columns_it_is_computed_from() -> None:
    assert provider_columns_read_by({"path_video"}) == (
        "ss_metadata",
        "launchbox_metadata",
        "gamelist_metadata",
    )
