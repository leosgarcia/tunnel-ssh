from src.ui.host_manager import validate_host_rows


def test_validate_host_rows_rejects_blank_and_duplicate_names():
    rows = [
        {"host": "host-a", "key": "", "ports": []},
        {"host": "   ", "key": "", "ports": []},
        {"host": "host-a", "key": "", "ports": []},
    ]

    errors = validate_host_rows(rows)

    assert errors == [
        "Preencha todos os nomes de host antes de salvar.",
        "Host duplicado: host-a",
    ]


def test_validate_host_rows_accepts_unique_names():
    rows = [
        {"host": "host-a", "key": "", "ports": []},
        {"host": "host-b", "key": "", "ports": []},
    ]

    assert validate_host_rows(rows) == []
