def test_linked_list():
    from algorithms.linked_list import LinkedList
    ll = LinkedList([1,2,3])
    assert ll.to_list() == [1,2,3]
    ll.append(4)
    assert ll.to_list() == [1,2,3,4]

