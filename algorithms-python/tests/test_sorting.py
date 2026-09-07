# tests for sorting

def test_quicksort_empty():
    from algorithms.sorting import quicksort
    assert quicksort([]) == []


def test_quicksort_sorted():
    from algorithms.sorting import quicksort
    assert quicksort([1,2,3]) == [1,2,3]


def test_quicksort_random():
    from algorithms.sorting import quicksort
    assert quicksort([3,1,2]) == [1,2,3]
