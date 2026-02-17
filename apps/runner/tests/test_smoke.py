def test_runner_imports():
    """Verify all runner submodules can be imported without errors."""
    import runner
    import runner.detector
    import runner.scanner
    import runner.patchgen
    import runner.validator
    import runner.packaging
    import runner.sandbox

    assert runner is not None
