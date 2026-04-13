import plotly
import plotly.graph_objects as go
import pyomo.environ as pyo
import npap
import networkx as nx
import pandas as pd
from sklearn.cluster import KMeans



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


def store_dual_in_npap_graph(model: pyo.Model, power_system, constraint_name: str, graph_attribute_type: str):
    """ 
    Gets duals of defined constraint_name from model and stores as attribute in the graph of the power_system
    """
    # Fix 1: Check if the string name exists as a component on the model
    constr_component = getattr(model, constraint_name, None)
    if constr_component is None or not isinstance(constr_component, pyo.Constraint):
        raise KeyError(f"The defined constraint: {constraint_name}, is not defined or active in {model.name}")
    
    valid_graph_attribute_types = ['nodes', 'edges']
    if graph_attribute_type not in valid_graph_attribute_types:
        raise ValueError(f"The defined graph_attribute_type: {graph_attribute_type} is not defined as {valid_graph_attribute_types}")

    duals_for_constraint = {}
    
    # Fix 2: Iterate over the component object we successfully retrieved above
    for idx, constr_obj in constr_component.items():
        dual_value = model.dual.get(constr_obj, 0.0)
        duals_for_constraint[idx] = dual_value

    if graph_attribute_type == 'nodes':
        nx.set_node_attributes(power_system._current_graph, duals_for_constraint, name=f'duals_of_{constraint_name}')
    else:
        # Fix 3: Use set_edge_attributes instead of set_line_attributes
        nx.set_edge_attributes(power_system._current_graph, duals_for_constraint, name=f'duals_of_{constraint_name}')

    return power_system


def get_clustered_bus_mapping(ps: npap.PartitionAggregatorManager, attribute_name: str, n_clusters: int) -> dict:
    """
    Performs K-Means clustering on a specific node attribute and returns 
    a mapping dictionary of {cluster_id: [list_of_nodes]}.
    """
    # 1. Extract the specific attribute from all nodes into a dictionary
    node_attr_dict = nx.get_node_attributes(ps._current_graph, attribute_name)
    
    if not node_attr_dict:
        raise KeyError(f"The attribute '{attribute_name}' was not found on any nodes.")

    # 2. Convert to a Pandas DataFrame (Scikit-learn requires a 2D array)
    # Orient='index' ensures the node IDs become the index of the DataFrame
    df = pd.DataFrame.from_dict(node_attr_dict, orient='index', columns=[attribute_name])
    
    # Drop any nodes that might be missing this attribute (NaNs crash KMeans)
    df = df.dropna()

    # 3. Perform K-Means Clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(df[[attribute_name]])

    # 4. Generate the Mapping Dictionary
    # df.groupby('cluster_id').groups returns a dict mapping cluster IDs to their index values (Node IDs)
    bus_mapping = {int(cluster): list(nodes) for cluster, nodes in df.groupby('cluster_id').groups.items()}
    
    return bus_mapping
