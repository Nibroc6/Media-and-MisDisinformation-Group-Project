# Truth Social Misinformation Dashboard

## Overview

An interactive web-based dashboard for visualizing the spread of misinformation on Truth Social, specifically focused on the **autism-tylenol link conspiracy theory**.

### Key Features

- **Network Graph Visualizations**: See how users are connected through reposts, replies, and mentions
- **Timeline Analysis**: Track how misinformation spreads over time with engagement metrics
- **Statistics Dashboard**: View key metrics including top influencers, interaction types, and engagement patterns
- **Influence Heatmap**: Identify the most influential users and their interaction patterns
- **Community Detection**: Analyze clustering of users who share and amplify misinformation
- **Top Posts View**: Browse the most engaged posts in the dataset

## Quick Start

### 1. Install Dependencies

```bash
pip install -r ../requirements.txt
```

### 2. Run the Dashboard

From the root of the truthbrush project:

```bash
python -m dashboard.app
```

The dashboard will start on `http://localhost:5000`

### 3. Access the Interface

Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

### Main Dashboard

The dashboard opens with a statistics summary at the top showing:
- Total Users
- Total Posts
- Total Interactions
- Total Reblogs, Favourites, and Replies

### Filter Controls

Use the filter panel to:
- Select a date range (Start Date / End Date)
- Set a minimum engagement threshold
- Apply filters to all visualizations

### Tabs

#### 🔗 Network Graph (Default)
- **What it shows**: Visual representation of how users are connected through the misinformation network
- **Technology**: [Force-Graph](https://github.com/vasturiano/3d-force-graph) with WebGL/Three.js for high-performance rendering
- **Layout options**:
  - **Force 2D**: 2D force-directed layout using Force-Graph (highly interactive, WebGL accelerated)
  - **Force 3D**: Full 3D force simulation with rotation, zoom, pan (perfect for complex networks)
  - **Circular**: Users arranged in a circle (good for seeing all users at once)
- **Node size**: Proportional to follower count
- **Node color**: Red glow indicates engagement level (higher engagement = more red)
- **Directed edges with arrows**: Lines show direction of content spread (source → target)
- **Interactive features**:
  - **Hover**: See user details tooltip
  - **Click**: Center on user and zoom in
  - **Drag**: Pan the view (2D) or rotate/zoom (3D with mouse)
  - **Scroll**: Zoom in/out
- **Animated particles**: Small particles flow along edges to show active spread paths
- **Interaction types**: Reblogs (reposts), replies, mentions
- **Layout iterations**: Adjust convergence (higher = better spacing, but slower computation)
- **Performance**: Handles thousands of nodes smoothly thanks to WebGL
- **Use case**: Identify key influencers, trace information flow, discover amplifier clusters
- **For presentations**: 
  - Force 2D shows natural clustering clearly
  - Force 3D lets you explore the network depth in real-time during Q&A

#### 📈 Timeline
- **What it shows**: Daily evolution of the misinformation spread
- **Left axis**: Number of posts per day
- **Right axis**: Total engagement (favourites)
- **Use case**: See when the conspiracy theory gained traction and peak activity periods

#### 📊 Statistics
- **Top Influencers**: Users with the most followers engaging with this misinformation
- **Interaction Type Breakdown**: Pie chart showing distribution of reposts vs replies vs mentions
- **Use case**: Understand the mechanics of how content spreads (organic shares vs discussions)

#### 🔥 Influence Heatmap
- **What it shows**: Matrix visualization of top 20 users and their interactions
- **Rows**: Source users (who posts)
- **Columns**: Target users (who receives/interacts)
- **Intensity**: Number of interactions between users
- **Use case**: Spot power users and key amplifiers

#### 🎯 Clustering
- **What it shows**: Groups of users who behave similarly in amplifying misinformation
- **Community detection**: Identifies clusters of users who interact frequently
- **Use case**: Understand organized vs organic spreading patterns

#### 💬 Top Posts
- **What it shows**: Most engaged posts (by reblogs + favourites + replies)
- **Sorted by**: Total engagement
- **Shows**: Author, post content (truncated), engagement metrics
- **Use case**: Identify specific content that resonates with spreaders

### Export Options

Each visualization can be exported:
- **📥 Download PNG**: Save the visualization as a high-quality image for presentations
- **📥 Download Data**: Get raw JSON/CSV data for further analysis

## Database

The dashboard queries from `cache.db` (configurable via `DB_PATH` environment variable).

### Database Schema

```sql
-- Users table
users(id, username, display_name, created_at, followers_count, following_count, statuses_count, raw_data)

-- Posts table
posts(id, author_id, content, created_at, reblogs_count, replies_count, favourites_count, source_tag, raw_data)

-- Network edges (interactions between users)
edges(source_user_id, target_user_id, post_id, interaction_type, created_at)
```

## Performance Notes

- **Network graph**: Optimized for up to ~5,000 nodes; performs well with Plotly
- **Large datasets**: If >10k nodes, filter by date range or engagement threshold
- **Initial load**: First load caches data in memory; subsequent filter changes update quickly

## Architecture

```
dashboard/
├── app.py              # Flask application and routes
├── db_connector.py     # SQLite connection management
├── queries.py          # Data aggregation and analysis queries
├── __init__.py         # Package initialization
├── templates/
│   ├── base.html       # Base template with navigation
│   └── index.html      # Main dashboard with all tabs and visualizations
└── static/
    └── style.css       # Custom styling
```

## Technology Stack

### Backend
- **Flask**: Lightweight web framework
- **NetworkX**: Graph algorithms and force-directed layout computation
- **Pandas/SQLite**: Data aggregation and queries

### Frontend
- **Force-Graph**: High-performance 3D network visualization with WebGL
  - Uses Three.js under the hood
  - WebWorker support for large graphs (5k+ nodes)
  - True 3D force simulation in browser
  - Interactive controls (rotate, zoom, pan)
- **Plotly**: Statistical visualizations (timeline, heatmap, bar charts)
- **Bootstrap 5**: Responsive UI framework

### Why Force-Graph instead of Plotly for Networks?
Plotly is great for general plotting, but Force-Graph is superior for network visualization because:
- ✅ **WebGL acceleration**: 10-100x faster rendering than Plotly for large graphs
- ✅ **True 3D simulation**: Physics-based force direction in full 3D space (not just projection)
- ✅ **Interactivity**: Smooth real-time rotation, zoom, and pan
- ✅ **Graph-specific**: Built specifically for node-link diagrams with features like directed arrows and particle flow
- ✅ **Performance**: Handles 5k+ nodes without lag; Plotly struggles at 1k+

## API Reference

The dashboard exposes JSON APIs for programmatic access:

### `/api/network?min_engagement=0&date_start=2024-01-01&date_end=2024-12-31`
Returns network nodes and edges

### `/api/timeline?date_start=2024-01-01&date_end=2024-12-31`
Returns daily aggregated engagement data

### `/api/statistics`
Returns overall statistics (user count, post count, top influencers, etc.)

### `/api/influence-heatmap`
Returns top 20 users and their interaction matrix

### `/api/clustering`
Returns user clustering analysis

### `/api/top-posts?limit=10&date_start=2024-01-01&date_end=2024-12-31`
Returns top N most engaged posts

## For Presentations

### Best Practices

1. **Network Graph**: Emphasize node colors (engagement) and size (influence)
   - Red nodes with large size = high-reach amplifiers
   - Tight clusters = coordinated spreading communities

2. **Timeline**: Highlight peaks in engagement
   - Show correlation with major news events
   - Demonstrate sustained vs. spike-driven spread

3. **Statistics**: Lead with top influencers
   - Show how few users drive the narrative
   - Display interaction type breakdown (organic vs. coordinated)

4. **Heatmap**: Identify key player-to-player interactions
   - Show dependency chains (who amplifies whom)
   - Highlight key gatekeepers in the network

### Exporting for Slides

1. Click "📥 Download PNG" on each visualization
2. Images export at high resolution suitable for presentation
3. Use the accompanying statistics for context

## Troubleshooting

### Dashboard Won't Start
- Ensure `cache.db` exists in the project root
- Check that Flask is installed: `pip install flask`
- Verify the database path in environment variable `DB_PATH`

### No Data Showing
- Confirm the scraper has populated `cache.db` with posts
- Check filters aren't too restrictive
- Try resetting filters and reloading

### Network Graph is Slow
- Reduce node count by increasing `min_engagement` filter
- Try filtering by a specific date range
- Check browser console for errors

### Export/Download Not Working
- Ensure browser allows downloads
- Check browser console for CORS errors
- Try a different browser or disable extensions

## Configuration

Environment variables (from `.env` or `scraper/config.py`):

```
DB_PATH=cache.db                 # Path to SQLite database
```

The dashboard automatically uses the same database path configured for the scraper.

## Further Development Ideas

- **Real-time updates**: Auto-refresh when new data arrives
- **Custom export**: Export network as graphML/JSON for network analysis tools
- **Advanced filtering**: Filter by keyword, language, user type
- **Community resolution**: Use NetworkX Louvain algorithm for better clustering
- **D3.js integration**: Interactive network with force simulation (if performance needs optimization)
- **Comparative analysis**: Compare spread patterns across multiple misinformation narratives

## License

See parent project README for license information.
