"""Increment 1 — the package exists and advertises a version string."""


def test_provisio_exposes_version() -> None:
    import provisio

    assert isinstance(provisio.__version__, str)
    assert provisio.__version__
