from tools.search_datasets import clean_search_query


def test_clean_search_query_removes_generic_stop_words() -> None:
    query = "données transports csv"
    assert clean_search_query(query) == "transports"


def test_clean_search_query_keeps_specific_terms() -> None:
    query = "prix immobilier paris"
    assert clean_search_query(query) == "prix immobilier paris"
