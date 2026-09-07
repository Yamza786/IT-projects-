from collections import deque

def bfs(graph, start):
    """Breadth-first search returning list of visited nodes in order."""
    visited = set()
    order = []
    q = deque([start])
    visited.add(start)
    while q:
        node = q.popleft()
        order.append(node)
        for nbr in graph.get(node, []):
            if nbr not in visited:
                visited.add(nbr)
                q.append(nbr)
    return order


def dfs(graph, start):
    """Depth-first search (iterative) returning list of visited nodes in order."""
    visited = set()
    order = []
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        # add neighbors in reversed order for deterministic traversal
        for nbr in reversed(graph.get(node, [])):
            if nbr not in visited:
                stack.append(nbr)
    return order
