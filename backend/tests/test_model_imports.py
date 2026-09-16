def test_models_package_imports_all_declared_models():
    import models

    assert hasattr(models, "WbPaidStorage")
