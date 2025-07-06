import zipfile
from io import BytesIO

import pytest
from tasks.update_launchbox_metadata import UpdateLaunchboxMetadataTask


@pytest.fixture
def task():
    """Create a task instance for testing"""
    return UpdateLaunchboxMetadataTask()


@pytest.fixture
def sample_zip_content():
    """Create sample ZIP content with XML files"""
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        # Add Platforms.xml
        platforms_xml = """<?xml version="1.0" encoding="UTF-8"?>
<LaunchBox>
<Platform>
    <Name>Nintendo 64</Name>
    <PlatformType>Console</PlatformType>
    <ReleaseDate>1996-06-23</ReleaseDate>
</Platform>
<Platform>
    <Name>PlayStation</Name>
    <PlatformType>Console</PlatformType>
    <ReleaseDate>1994-12-03</ReleaseDate>
</Platform>
</LaunchBox>"""
        zip_file.writestr("Platforms.xml", platforms_xml)

        # Add Metadata.xml
        metadata_xml = """<?xml version="1.0" encoding="UTF-8"?>
<LaunchBox>
<Game>
    <DatabaseID>67890</DatabaseID>
    <Name>Crash Bandicoot</Name>
    <Platform>PlayStation</Platform>
    <ReleaseDate>1996-09-09</ReleaseDate>
    <Genre>Platformer</Genre>
</Game>
<Game>
    <DatabaseID>12345</DatabaseID>
    <Name>Super Mario 64</Name>
    <Platform>Nintendo 64</Platform>
    <ReleaseDate>1996-06-23</ReleaseDate>
    <Genre>Platformer</Genre>
</Game>
<GameAlternateName>
    <AlternateName>Super Mario 64 (USA)</AlternateName>
    <DatabaseID>12345</DatabaseID>
</GameAlternateName>
<GameImage>
    <DatabaseID>12345</DatabaseID>
    <FileName>super_mario_64.jpg</FileName>
    <Type>Cover</Type>
</GameImage>
<GameImage>
    <DatabaseID>12345</DatabaseID>
    <FileName>super_mario_64_screenshot.jpg</FileName>
    <Type>Screenshot</Type>
</GameImage>
</LaunchBox>"""
        zip_file.writestr("Metadata.xml", metadata_xml)

        # Add Mame.xml
        mame_xml = """<?xml version="1.0" encoding="UTF-8"?>
<LaunchBox>
<MameFile>
    <FileName>mario.zip</FileName>
    <GameName>mario</GameName>
    <Description>Super Mario Bros.</Description>
</MameFile>
<MameFile>
    <FileName>pacman.zip</FileName>
    <GameName>pacman</GameName>
    <Description>Pac-Man</Description>
</MameFile>
</LaunchBox>"""
        zip_file.writestr("Mame.xml", mame_xml)

        # Add Files.xml
        files_xml = """<?xml version="1.0" encoding="UTF-8"?>
<LaunchBox>
<File>
    <FileName>super_mario_64.z64</FileName>
    <FileType>ROM</FileType>
    <Size>8388608</Size>
</File>
<File>
    <FileName>crash_bandicoot.bin</FileName>
    <FileType>ROM</FileType>
    <Size>524288000</Size>
</File>
</LaunchBox>"""
        zip_file.writestr("Files.xml", files_xml)

    return zip_buffer.getvalue()


@pytest.fixture
def corrupt_zip_content():
    """Create corrupt ZIP content for testing error handling"""
    return b"not a valid zip file"
