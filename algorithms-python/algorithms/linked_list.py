class Node:
    def __init__(self, value, nxt=None):
        self.value = value
        self.next = nxt

class LinkedList:
    """A simple singly linked list for educational purposes."""
    def __init__(self, iterable=None):
        self.head = None
        if iterable:
            for item in reversed(list(iterable)):
                self.head = Node(item, self.head)

    def to_list(self):
        out = []
        cur = self.head
        while cur:
            out.append(cur.value)
            cur = cur.next
        return out

    def append(self, value):
        if not self.head:
            self.head = Node(value)
            return
        cur = self.head
        while cur.next:
            cur = cur.next
        cur.next = Node(value)
