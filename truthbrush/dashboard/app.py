"""
Flask web dashboard for visualizing Truth Social misinformation networks.
Focuses on autism-tylenol link misinformation spread.
"""
import json
import sys
import os
from datetime import datetime

# Add parent directory to path so we can import dashboard modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

from db_connector import get_db_connection, execute_query
import queries

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['JSON_SORT_KEYS'] = False


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Render main dashboard page."""
    stats = queries.get_statistics()
    return render_template('index.html', stats=stats)


@app.route('/api/network')
def api_network():
    """
    Get network graph data (nodes and edges).
    Force-Graph handles all layout computation in the browser.
    
    Query parameters:
        - min_engagement: Minimum engagement threshold (default: 0)
        - date_start: ISO format date (optional)
        - date_end: ISO format date (optional)
    """
    min_engagement = request.args.get('min_engagement', 0, type=int)
    date_start = request.args.get('date_start', None)
    date_end = request.args.get('date_end', None)
    
    # Return raw nodes and edges - Force-Graph will handle layout
    data = queries.get_network_data(
        min_engagement=min_engagement,
        date_start=date_start,
        date_end=date_end
    )
    
    return jsonify(data)


@app.route('/api/timeline')
def api_timeline():
    """
    Get timeline data for daily engagement chart.
    
    Query parameters:
        - date_start: ISO format date (optional)
        - date_end: ISO format date (optional)
    """
    date_start = request.args.get('date_start', None)
    date_end = request.args.get('date_end', None)
    
    timeline = queries.get_timeline_data(date_start=date_start, date_end=date_end)
    
    return jsonify(timeline)


@app.route('/api/statistics')
def api_statistics():
    """Get overall statistics about the dataset."""
    stats = queries.get_statistics()
    return jsonify(stats)


@app.route('/api/influence-heatmap')
def api_influence_heatmap():
    """Get influence heatmap data (user-to-user interactions)."""
    heatmap = queries.get_influence_heatmap()
    return jsonify(heatmap)


@app.route('/api/clustering')
def api_clustering():
    """Get clustering analysis data."""
    clustering = queries.get_clustering_data()
    return jsonify(clustering)


@app.route('/api/top-posts')
def api_top_posts():
    """
    Get most engaged posts.
    
    Query parameters:
        - limit: Number of posts to return (default: 10)
        - date_start: ISO format date (optional)
        - date_end: ISO format date (optional)
    """
    limit = request.args.get('limit', 10, type=int)
    date_start = request.args.get('date_start', None)
    date_end = request.args.get('date_end', None)
    
    posts = queries.get_top_posts(limit=limit, date_start=date_start, date_end=date_end)
    
    return jsonify(posts)


# ============================================================================
# VISUALIZATION ENDPOINTS (Return HTML with embedded Plotly)
# ============================================================================

@app.route('/viz/network')
def viz_network():
    """
    Generate and return interactive network graph visualization.
    Uses Plotly for rendering.
    """
    data = queries.get_network_data(min_engagement=0)
    nodes = data['nodes']
    edges = data['edges']
    
    if not nodes:
        return jsonify({"error": "No network data available"}), 400
    
    # Create node and edge data for Plotly
    edge_x = []
    edge_y = []
    edge_hover = []
    
    node_positions = {}  # Will be populated with node positions
    
    # For a simple force-directed layout, we'll use a spring layout algorithm
    # For now, use a simple circular layout with some noise
    import math
    n = len(nodes)
    for i, node in enumerate(nodes):
        angle = (2 * math.pi * i) / n
        x = math.cos(angle) * 10
        y = math.sin(angle) * 10
        node_positions[node['id']] = (x, y)
    
    # Build edge traces
    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']
        
        if source_id in node_positions and target_id in node_positions:
            x0, y0 = node_positions[source_id]
            x1, y1 = node_positions[target_id]
            
            edge_x.append(x0)
            edge_x.append(x1)
            edge_x.append(None)
            
            edge_y.append(y0)
            edge_y.append(y1)
            edge_y.append(None)
            
            edge_hover.append(f"{edge['type']}: {edge['weight']} interactions")
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=0.5, color='rgba(125,125,125,0.5)'),
        hoverinfo='text',
        hovertext=edge_hover,
        showlegend=False
    )
    
    # Build node trace
    node_x = [node_positions[node['id']][0] for node in nodes]
    node_y = [node_positions[node['id']][1] for node in nodes]
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(
            size=[node['size'] for node in nodes],
            color=[node['engagement'] for node in nodes],
            colorscale='YlOrRd',
            showscale=True,
            colorbar=dict(
                thickness=15,
                title='Engagement',
                xanchor='left',
                titleside='right'
            ),
            line=dict(width=2, color='white')
        ),
        text=[node['label'][:10] for node in nodes],
        textposition='middle center',
        hoverinfo='text',
        hovertext=[f"<b>{node['label']}</b><br>Followers: {node['followers']}<br>Posts: {node['post_count']}<br>Engagement: {node['engagement']}" for node in nodes],
        showlegend=False
    )
    
    fig = go.Figure(data=[edge_trace, node_trace])
    
    fig.update_layout(
        title='Truth Social Autism-Tylenol Misinformation Network',
        hovermode='closest',
        margin=dict(b=0, l=0, r=0, t=40),
        plot_bgcolor='rgba(240, 240, 240, 0.9)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=700
    )
    
    return jsonify({
        "html": fig.to_html(include_plotlyjs='cdn', div_id='network-graph'),
        "data": data
    })


@app.route('/viz/timeline')
def viz_timeline():
    """Generate timeline visualization."""
    timeline = queries.get_timeline_data()
    
    if not timeline:
        return jsonify({"error": "No timeline data available"}), 400
    
    df = pd.DataFrame(timeline)
    df['date'] = pd.to_datetime(df['date'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['post_count'],
        name='Posts',
        mode='lines+markers',
        yaxis='y1'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['total_favourites'],
        name='Favourites',
        mode='lines',
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='Autism-Tylenol Misinformation Spread Over Time',
        xaxis=dict(title='Date'),
        yaxis=dict(title='Post Count', side='left'),
        yaxis2=dict(title='Engagement', side='right', overlaying='y'),
        hovermode='x unified',
        height=500,
        plot_bgcolor='rgba(240, 240, 240, 0.9)'
    )
    
    return jsonify({
        "html": fig.to_html(include_plotlyjs='cdn', div_id='timeline-graph'),
        "data": timeline
    })


@app.route('/viz/influence-heatmap')
def viz_influence_heatmap():
    """Generate influence heatmap visualization."""
    heatmap_data = queries.get_influence_heatmap()
    
    if not heatmap_data['users']:
        return jsonify({"error": "No influence data available"}), 400
    
    users = heatmap_data['users']
    interactions = heatmap_data['interactions']
    
    # Create matrix
    n = len(users)
    matrix = [[0] * n for _ in range(n)]
    user_id_to_idx = {u['id']: i for i, u in enumerate(users)}
    
    for inter in interactions:
        if inter['source_user_id'] in user_id_to_idx and inter['target_user_id'] in user_id_to_idx:
            i = user_id_to_idx[inter['source_user_id']]
            j = user_id_to_idx[inter['target_user_id']]
            matrix[i][j] = inter['interaction_count']
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[u['username'][:15] for u in users],
        y=[u['username'][:15] for u in users],
        colorscale='Viridis'
    ))
    
    fig.update_layout(
        title='User-to-User Interaction Heatmap (Top 20 Influencers)',
        xaxis=dict(title='Target User'),
        yaxis=dict(title='Source User'),
        height=600,
        width=800
    )
    
    return jsonify({
        "html": fig.to_html(include_plotlyjs='cdn', div_id='heatmap-graph'),
        "data": heatmap_data
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Route not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "details": str(error)}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("Starting Truth Social Misinformation Dashboard...")
    print("Navigate to http://localhost:5000")
    app.run(debug=True, host='localhost', port=5000)
