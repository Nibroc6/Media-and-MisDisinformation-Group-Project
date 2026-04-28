"""
Aggregation queries for the visualization dashboard.
Provides data aggregations for network graphs, timelines, statistics, etc.
"""
import networkx as nx
from db_connector import execute_query, execute_query_single


def get_network_data(min_engagement=0, date_start=None, date_end=None):
    """
    Get nodes and edges for network visualization.
    
    Args:
        min_engagement: Minimum favourites_count to include a user
        date_start: ISO format date string (optional)
        date_end: ISO format date string (optional)
    
    Returns:
        dict with 'nodes' and 'edges' lists
    """
    # Get all users involved in the network (as authors or interaction targets)
    user_query = """
    SELECT DISTINCT u.id, u.username, u.display_name, 
           u.followers_count, u.statuses_count,
           COUNT(DISTINCT p.id) as post_count,
           SUM(p.reblogs_count) as total_reblogs,
           SUM(p.favourites_count) as total_favourites,
           MAX(p.created_at) as last_post_date
    FROM users u
    LEFT JOIN posts p ON u.id = p.author_id
    WHERE (
        EXISTS (
            SELECT 1 FROM edges e 
            WHERE e.source_user_id = u.id 
            AND e.target_user_id != u.id
    """
    params = []
    
    if date_start:
        user_query += " AND e.created_at >= ?"
        params.append(date_start)
    
    if date_end:
        user_query += " AND e.created_at <= ?"
        params.append(date_end)
    
    user_query += """
        )
        OR EXISTS (
            SELECT 1 FROM edges e 
            WHERE e.target_user_id = u.id 
            AND e.source_user_id != u.id
    """
    
    if date_start:
        user_query += " AND e.created_at >= ?"
        params.append(date_start)
    
    if date_end:
        user_query += " AND e.created_at <= ?"
        params.append(date_end)
    
    user_query += """
        )
    )
    """
    
    if date_start or date_end:
        user_query += " AND ("
        if date_start:
            user_query += "p.created_at >= ?"
            params.append(date_start)
        if date_start and date_end:
            user_query += " AND "
        if date_end:
            user_query += "p.created_at <= ?"
            params.append(date_end)
        user_query += " OR p.id IS NULL)"
    
    user_query += " GROUP BY u.id HAVING (SUM(p.favourites_count) IS NULL OR SUM(p.favourites_count) >= ?)"
    params.append(min_engagement)
    
    users = execute_query(user_query, params)
    
    # Create nodes from users
    nodes = []
    for user in users:
        nodes.append({
            "id": user["id"],
            "label": user["username"] or user["display_name"] or user["id"][:8],
            "display_name": user["display_name"],
            "followers": user["followers_count"] or 0,
            "post_count": user["post_count"] or 0,
            "total_reblogs": user["total_reblogs"] or 0,
            "total_favourites": user["total_favourites"] or 0,
            "size": max(10, min(50, (user["followers_count"] or 0) / 1000 + 10)),  # Scale for visualization
            "engagement": user["total_favourites"] or 0
        })
    
    # Get all edges with interaction types
    edge_query = """
    SELECT source_user_id, target_user_id, interaction_type,
           MAX(post_id) as post_id,
           COUNT(*) as count, 
           SUM(CASE WHEN interaction_type = 'reblog' THEN 1 ELSE 0 END) as reblog_count,
           SUM(CASE WHEN interaction_type = 'reply' THEN 1 ELSE 0 END) as reply_count,
           SUM(CASE WHEN interaction_type = 'mention' THEN 1 ELSE 0 END) as mention_count
    FROM edges
    WHERE source_user_id != target_user_id
    """
    edge_params = []
    
    if date_start:
        edge_query += " AND created_at >= ?"
        edge_params.append(date_start)
    
    if date_end:
        edge_query += " AND created_at <= ?"
        edge_params.append(date_end)
    
    edge_query += " GROUP BY source_user_id, target_user_id, interaction_type"
    
    edges = execute_query(edge_query, edge_params)
    
    # Create set of valid node IDs for filtering edges
    valid_node_ids = set(node["id"] for node in nodes)
    
    edges_list = []
    for edge in edges:
        # Only include edges where both source and target nodes exist in the filtered nodes
        if edge["source_user_id"] in valid_node_ids and edge["target_user_id"] in valid_node_ids:
            edges_list.append({
                "source": edge["source_user_id"],
                "target": edge["target_user_id"],
                "type": edge["interaction_type"],
                "post_id": edge.get("post_id"),
                "weight": edge["count"],
                "reblog_count": edge["reblog_count"] or 0,
                "reply_count": edge["reply_count"] or 0,
                "mention_count": edge["mention_count"] or 0
            })
    
    return {
        "nodes": nodes,
        "edges": edges_list,
        "node_count": len(nodes),
        "edge_count": len(edges_list)
    }


def get_force_directed_network(min_engagement=0, date_start=None, date_end=None, iterations=50, is_3d=False):
    """
    Get network data with force-directed layout computed by NetworkX.
    
    Args:
        min_engagement: Minimum favourites_count to include a user
        date_start: ISO format date string (optional)
        date_end: ISO format date string (optional)
        iterations: Number of spring layout iterations (higher = better but slower)
        is_3d: If True, compute 3D layout; if False, compute 2D
    
    Returns:
        dict with positioned nodes and directed edges
    """
    # Get base network data
    data = get_network_data(min_engagement, date_start, date_end)
    nodes = data['nodes']
    edges = data['edges']
    
    if not nodes:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}
    
    # Build NetworkX directed graph
    G = nx.DiGraph()
    
    # Add nodes with attributes
    for node in nodes:
        G.add_node(node['id'], 
                   label=node['label'],
                   followers=node['followers'],
                   engagement=node['engagement'],
                   post_count=node['post_count'],
                   size=node['size'])
    
    # Add directed edges
    for edge in edges:
        G.add_edge(edge['source'], edge['target'],
                   weight=edge['weight'],
                   type=edge['type'],
                   reblog_count=edge['reblog_count'],
                   reply_count=edge['reply_count'],
                   mention_count=edge['mention_count'])
    
    # Compute force-directed layout
    if is_3d:
        # 3D layout using spring_layout with z-coordinate
        pos_2d = nx.spring_layout(G, k=0.5, iterations=iterations, seed=42)
        import random
        random.seed(42)
        pos_3d = {node: (pos_2d[node][0], pos_2d[node][1], random.uniform(-1, 1)) 
                  for node in pos_2d}
        positions = pos_3d
        dimension = 3
    else:
        # 2D layout
        positions = nx.spring_layout(G, k=0.5, iterations=iterations, seed=42)
        dimension = 2
    
    # Enrich nodes with positions
    positioned_nodes = []
    for node in nodes:
        node_id = node['id']
        if node_id in positions:
            pos = positions[node_id]
            node['x'] = float(pos[0])
            node['y'] = float(pos[1])
            if dimension == 3:
                node['z'] = float(pos[2])
            positioned_nodes.append(node)
    
    # Enrich edges with source and target positions for drawing arrows
    positioned_edges = []
    for edge in edges:
        if edge['source'] in positions and edge['target'] in positions:
            source_pos = positions[edge['source']]
            target_pos = positions[edge['target']]
            edge['source_x'] = float(source_pos[0])
            edge['source_y'] = float(source_pos[1])
            edge['target_x'] = float(target_pos[0])
            edge['target_y'] = float(target_pos[1])
            if dimension == 3:
                edge['source_z'] = float(source_pos[2])
                edge['target_z'] = float(target_pos[2])
            positioned_edges.append(edge)
    
    return {
        "nodes": positioned_nodes,
        "edges": positioned_edges,
        "node_count": len(positioned_nodes),
        "edge_count": len(positioned_edges),
        "dimension": dimension,
        "is_directed": True
    }


def get_timeline_data(date_start=None, date_end=None):
    """
    Get daily post/engagement data for timeline visualization.
    
    Returns:
        list of dicts with date, post_count, reblogs, favourites, replies
    """
    query = """
    SELECT DATE(created_at) as date,
           COUNT(*) as post_count,
           SUM(reblogs_count) as total_reblogs,
           SUM(favourites_count) as total_favourites,
           SUM(replies_count) as total_replies,
           COUNT(DISTINCT author_id) as unique_authors
    FROM posts
    WHERE 1=1
    """
    params = []
    
    if date_start:
        query += " AND created_at >= ?"
        params.append(date_start)
    
    if date_end:
        query += " AND created_at <= ?"
        params.append(date_end)
    
    query += " GROUP BY DATE(created_at) ORDER BY date ASC"
    
    return execute_query(query, params)


def get_statistics():
    """
    Get overall statistics about the dataset.
    """
    stats = {}
    
    # Total users
    result = execute_query_single("SELECT COUNT(*) as count FROM users")
    stats["total_users"] = result["count"] if result else 0
    
    # Total posts
    result = execute_query_single("SELECT COUNT(*) as count FROM posts")
    stats["total_posts"] = result["count"] if result else 0
    
    # Total interactions
    result = execute_query_single("SELECT COUNT(*) as count FROM edges")
    stats["total_interactions"] = result["count"] if result else 0
    
    # Total engagement
    result = execute_query_single("SELECT SUM(reblogs_count) as reblogs, SUM(favourites_count) as favourites, SUM(replies_count) as replies FROM posts")
    if result:
        stats["total_reblogs"] = result["reblogs"] or 0
        stats["total_favourites"] = result["favourites"] or 0
        stats["total_replies"] = result["replies"] or 0
    else:
        stats["total_reblogs"] = 0
        stats["total_favourites"] = 0
        stats["total_replies"] = 0
    
    # Top influencers (by followers)
    top_users = execute_query("""
    SELECT username, display_name, followers_count, statuses_count,
           COUNT(DISTINCT p.id) as post_count
    FROM users u
    LEFT JOIN posts p ON u.id = p.author_id
    GROUP BY u.id
    ORDER BY followers_count DESC
    LIMIT 10
    """)
    stats["top_influencers"] = top_users
    
    # Interaction type breakdown
    interaction_breakdown = execute_query("""
    SELECT interaction_type, COUNT(*) as count
    FROM edges
    GROUP BY interaction_type
    ORDER BY count DESC
    """)
    stats["interaction_breakdown"] = interaction_breakdown
    
    # Date range
    date_range = execute_query_single("""
    SELECT MIN(created_at) as start_date, MAX(created_at) as end_date
    FROM posts
    """)
    if date_range:
        stats["date_range"] = {
            "start": date_range["start_date"],
            "end": date_range["end_date"]
        }
    
    return stats


def get_influence_heatmap():
    """
    Get user-to-user interaction matrix for heatmap visualization.
    Returns top N users by engagement and their interaction patterns.
    """
    # Get top 20 users by total engagement
    top_users_query = """
    SELECT u.id, u.username, 
           SUM(p.reblogs_count + p.favourites_count + p.replies_count) as total_engagement
    FROM users u
    LEFT JOIN posts p ON u.id = p.author_id
    GROUP BY u.id
    ORDER BY total_engagement DESC
    LIMIT 20
    """
    top_users = execute_query(top_users_query)
    top_user_ids = [u["id"] for u in top_users]
    
    if not top_user_ids:
        return {"users": [], "matrix": []}
    
    # Get interaction matrix between top users
    placeholders = ",".join("?" * len(top_user_ids))
    matrix_query = f"""
    SELECT source_user_id, target_user_id, COUNT(*) as interaction_count
    FROM edges
    WHERE source_user_id IN ({placeholders}) AND target_user_id IN ({placeholders})
    GROUP BY source_user_id, target_user_id
    """
    
    interactions = execute_query(matrix_query, top_user_ids + top_user_ids)
    
    return {
        "users": [{"id": u["id"], "username": u["username"]} for u in top_users],
        "interactions": interactions
    }


def get_clustering_data():
    """
    Get clustering analysis data.
    Returns users grouped by their community (using simple betweenness-based grouping).
    This is a simplified approach; full clustering would use NetworkX on the backend.
    """
    # For now, return users grouped by their primary interaction pattern
    # In a full implementation, this would use NetworkX community detection
    
    # Get nodes with their interaction patterns
    query = """
    SELECT u.id, u.username, u.followers_count,
           COUNT(DISTINCT CASE WHEN e.source_user_id = u.id THEN e.target_user_id END) as outgoing_connections,
           COUNT(DISTINCT CASE WHEN e.target_user_id = u.id THEN e.source_user_id END) as incoming_connections
    FROM users u
    LEFT JOIN edges e ON (e.source_user_id = u.id OR e.target_user_id = u.id)
    GROUP BY u.id
    ORDER BY (outgoing_connections + incoming_connections) DESC
    """
    
    users = execute_query(query)
    
    return {
        "nodes": users,
        "cluster_count": 3,  # Placeholder; would be computed by NetworkX
        "note": "Clustering data requires full network analysis with NetworkX"
    }


def get_top_posts(limit=10, date_start=None, date_end=None):
    """
    Get most engaged posts (by reblogs + favourites + replies).
    """
    query = """
    SELECT p.id, p.author_id, u.username, p.content,
           p.created_at, p.reblogs_count, p.favourites_count, p.replies_count,
           (p.reblogs_count + p.favourites_count + p.replies_count) as total_engagement
    FROM posts p
    JOIN users u ON p.author_id = u.id
    WHERE 1=1
    """
    params = []
    
    if date_start:
        query += " AND p.created_at >= ?"
        params.append(date_start)
    
    if date_end:
        query += " AND p.created_at <= ?"
        params.append(date_end)
    
    query += " ORDER BY total_engagement DESC LIMIT ?"
    params.append(limit)
    
    return execute_query(query, params)
