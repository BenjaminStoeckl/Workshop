import plotly
import plotly.graph_objects as go


def highlight_congested_lines(model, power_system, figure, tolerance=1e-6):
    """
    Identifies congested lines in the solved Pyomo model and adds a highlighted
    red trace to the provided Plotly figure.
    """
    congested_lats = []
    congested_lons = []
    G = power_system._current_graph

    for (u, v) in model.lines:
        # Check if flow in either direction is at (or very close to) capacity
        is_pos_congested = pyo.value(model.flow_pos[u, v]) >= pyo.value(model.line_cap[u, v]) - tolerance
        is_neg_congested = pyo.value(model.flow_neg[u, v]) >= pyo.value(model.line_cap[u, v]) - tolerance

        if is_pos_congested or is_neg_congested:
            # Get coordinates from the internal graph
            node_u = G.nodes[u]
            node_v = G.nodes[v]

            # Add coordinates for the red line segment (using None to break the line between segments)
            congested_lats.extend([node_u['lat'], node_v['lat'], None])
            congested_lons.extend([node_u['lon'], node_v['lon'], None])

    # Add the highlighted trace to the existing figure
    if congested_lats:
        figure.add_trace(go.Scattermapbox(
            lat=congested_lats,
            lon=congested_lons,
            mode='lines',
            line=dict(width=2, color='red'),
            name='Congested Lines (At Capacity)',
            hoverinfo='name'
        ))

    return figure