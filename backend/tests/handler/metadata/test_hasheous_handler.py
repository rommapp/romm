from handler.metadata.hasheous_handler import extract_metadata_from_igdb_rom

# The proxy keys expanded collections by id and returns `company` as a bare id,
# unlike IGDB's own list-of-objects shape.
PROXY_ROM = {
    "involved_companies": {
        "148214": {"id": 148214, "company": 70, "developer": True, "publisher": False},
        "225579": {"id": 225579, "company": 812, "developer": False, "publisher": True},
    },
}

IGDB_ROM = {
    "involved_companies": [
        {"company": {"name": "Retro Studios"}, "developer": True, "publisher": False},
        {"company": {"name": "Nintendo"}, "developer": False, "publisher": True},
    ],
}


def test_reads_the_proxys_dict_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(PROXY_ROM)

    assert metadata["companies"] == []
    assert metadata["publishers"] == []
    assert metadata["developers"] == []


def test_reads_igdbs_list_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(IGDB_ROM)

    assert metadata["publishers"] == ["Nintendo"]
    assert metadata["developers"] == ["Retro Studios"]


def test_involvements_are_optional():
    metadata = extract_metadata_from_igdb_rom({})

    assert metadata["publishers"] == []
    assert metadata["developers"] == []
