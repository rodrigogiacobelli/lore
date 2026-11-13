def pytest_configure(config):
    config.addinivalue_line("markers", "qa_matrix: slice of the independent lore init QA matrix (scripts/qa_init_matrix.py)")
