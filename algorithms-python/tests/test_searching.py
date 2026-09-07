def test_binary_search():
    from algorithms.searching import binary_search
    assert binary_search([], 1) == -1
    assert binary_search([1], 1) == 0
    assert binary_search([1,2,3,4,5], 3) == 2
    assert binary_search([1,2,3,4,5], 6) == -1
