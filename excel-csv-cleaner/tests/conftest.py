"""Fixtures partagées : génère un jeu de données fictif dans un dossier temporaire."""

import pytest

from cleaner.normalize import load_reference
from cleaner.pipeline import clean_directory
from generate_sample_data import generate


@pytest.fixture(scope="session")
def dataset(tmp_path_factory):
    """(dossier data, référentiel clients, vérité terrain)."""
    root = tmp_path_factory.mktemp("demo")
    truth = generate(root / "data", root / "clients.csv", seed=42)
    return root / "data", load_reference(root / "clients.csv"), truth


@pytest.fixture(scope="session")
def result(dataset):
    data_dir, reference, _ = dataset
    return clean_directory(data_dir, reference)
