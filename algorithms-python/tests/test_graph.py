def test_graph_traversal():
    from algorithms.graph import bfs, dfs
    graph = {
        'A': ['B','C'],
        'B': ['D'],
        'C': [],
        'D': []
    }
    assert bfs(graph, 'A') == ['A','B','C','D']
    # DFS order may vary based on neighbor ordering; our implementation visits A, B, D, C
    assert dfs(graph, 'A') == ['A','B','D','C']
