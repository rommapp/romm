import os

import pytest
from tasks.update_launchbox_metadata import UpdateLaunchboxMetadataTask


@pytest.fixture
def task():
    """Create a task instance for testing"""
    return UpdateLaunchboxMetadataTask()


@pytest.fixture
def sample_zip_content():
    test_dir = os.path.dirname(__file__)
    sample_path = os.path.join(test_dir, "fixtures", "sample_metadata.zip")

    with open(sample_path, "rb") as f:
        return f.read()


@pytest.fixture
def corrupt_zip_content():
    """Create corrupt ZIP content for testing error handling"""
    return b"not a valid zip file"
