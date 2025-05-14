# visualization/plotter.py
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches  # For creating legend handles
import networkx as nx  # type: ignore
import random
import os
from collections import deque  # For BFS/DFS in node selection

# If type hinting FamilyTree:
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.family_tree import FamilyTree  # Relative import for type checker

# Global config (ideally from a central config, or set by main script)
VERBOSE_LOGGING = True  # Example default


def visualize_family_tree_snapshot(family_tree_obj: 'FamilyTree',  # Use forward reference string
                                   year: int,
                                   filename_suffix: str = "",
                                   display_mode: str = "monarch_focus"):
    """
    Generates and saves a visualization of the current family tree snapshot.
    Nodes are colored based on status/title, and includes a legend.
    display_mode options: "monarch_focus", "living_nobles", "all_living".
    """
    if not family_tree_obj.members:
        if VERBOSE_LOGGING: print(f"Year {year}: Visualization skipped - no members in the family tree.")
        return

    display_graph = nx.DiGraph()
    nodes_to_display = set()  # IDs of people to include in this snapshot
    theme_cfg = family_tree_obj.theme_config  # Current theme configuration

    # --- Determine nodes to display based on the selected mode ---
    if display_mode == "monarch_focus" and \
            family_tree_obj.current_monarch and \
            family_tree_obj.current_monarch.id in family_tree_obj.members:

        root_node_for_focus = family_tree_obj.current_monarch.id
        nodes_to_display.add(root_node_for_focus)

        # Max depth for ancestors and descendants to show in monarch_focus
        max_ancestor_depth_viz = theme_cfg.get("viz_ancestor_depth", 2)
        max_descendant_depth_viz = theme_cfg.get("viz_descendant_depth", 3)

        # Ancestors BFS/DFS
        ancestor_queue = deque([(root_node_for_focus, 0)])
        visited_in_anc_search = {root_node_for_focus}
        while ancestor_queue:
            current_person_id, current_depth = ancestor_queue.popleft()
            if current_depth >= max_ancestor_depth_viz:
                continue
            person_obj = family_tree_obj.get_person(current_person_id)
            if person_obj:
                for parent_attr_name in ["father", "mother"]:
                    parent_obj = getattr(person_obj, parent_attr_name)
                    if parent_obj and parent_obj.id in family_tree_obj.members and \
                            parent_obj.id not in visited_in_anc_search:
                        nodes_to_display.add(parent_obj.id)
                        ancestor_queue.append((parent_obj.id, current_depth + 1))
                        visited_in_anc_search.add(parent_obj.id)

        # Descendants BFS/DFS (including monarch's spouse's line for context)
        descendant_queue = deque()
        visited_in_desc_search = set()

        # Start descent from monarch
        descendant_queue.append((root_node_for_focus, 0))
        visited_in_desc_search.add(root_node_for_focus)
        nodes_to_display.add(root_node_for_focus)  # Ensure monarch is in

        # Also start descent from monarch's spouse, if they exist and are valid
        if family_tree_obj.current_monarch.spouse and \
                family_tree_obj.current_monarch.spouse.id in family_tree_obj.members and \
                family_tree_obj.current_monarch.spouse.id not in visited_in_desc_search:
            spouse_id_for_desc = family_tree_obj.current_monarch.spouse.id
            descendant_queue.append((spouse_id_for_desc, 0))  # Spouse line starts at depth 0 from themselves
            visited_in_desc_search.add(spouse_id_for_desc)
            nodes_to_display.add(spouse_id_for_desc)

        while descendant_queue:
            current_person_id, current_depth = descendant_queue.popleft()
            # nodes_to_display.add(current_person_id) # Already added when put in queue or if it's root/spouse
            if current_depth >= max_descendant_depth_viz:
                continue

            person_obj = family_tree_obj.get_person(current_person_id)
            if person_obj:
                for child_character_obj in person_obj.children:
                    # Ensure child is valid and not yet visited for descendant search
                    if child_character_obj and child_character_obj.id in family_tree_obj.members and \
                            child_character_obj.id not in visited_in_desc_search:
                        nodes_to_display.add(child_character_obj.id)  # Add child to display set
                        descendant_queue.append((child_character_obj.id, current_depth + 1))
                        visited_in_desc_search.add(child_character_obj.id)  # Mark as visited

    elif display_mode == "living_nobles":
        nodes_to_display.update(person_id for person_id, person_obj_ln in family_tree_obj.members.items()
                                if person_obj_ln.is_alive(year) and person_obj_ln.is_noble)
    elif display_mode == "all_living":
        nodes_to_display.update(person_id for person_id, person_obj_al in family_tree_obj.members.items()
                                if person_obj_al.is_alive(year))

    if not nodes_to_display:  # Fallback if no nodes selected by primary logic
        if VERBOSE_LOGGING: print(
            f"Viz (Yr {year}): No nodes from '{display_mode}'. Using fallback display (first 30 living or 15 total).")
        fallback_nodes_list = [pid for pid, p_obj_fb in family_tree_obj.members.items() if p_obj_fb.is_alive(year)][:30]
        if not fallback_nodes_list: fallback_nodes_list = list(family_tree_obj.members.keys())[:15]  # Absolute fallback
        nodes_to_display.update(fallback_nodes_list)

    # --- Build the display_graph using only selected nodes ---
    # Ensure only valid person IDs are used to build the graph
    valid_nodes_for_graph_build = {node_id for node_id in nodes_to_display if
                                   family_tree_obj.get_person(node_id) is not None}

    for node_id_to_add_graph in valid_nodes_for_graph_build:
        person_data_for_node = family_tree_obj.get_person(node_id_to_add_graph)  # Known to exist
        display_graph.add_node(node_id_to_add_graph, data=person_data_for_node)

    # Add edges only between nodes that are confirmed to be in display_graph
    for node_id_in_graph_edges in display_graph.nodes():  # Iterate only over nodes actually added to display_graph
        person_in_graph_data = display_graph.nodes[node_id_in_graph_edges]['data']
        # Parent-child edges (display_graph uses parent -> child for 'dot' layout)
        for child_of_person_in_graph in person_in_graph_data.children:
            if child_of_person_in_graph.id in display_graph:  # Child must also be in the display_graph
                display_graph.add_edge(node_id_in_graph_edges, child_of_person_in_graph.id, type="parent_of")
        # Spouse edges
        if person_in_graph_data.spouse and person_in_graph_data.spouse.id in display_graph:  # Spouse must also be in display_graph
            # Add spouse edge only once (e.g., from lower ID to higher ID to avoid duplicates if graph is treated as undirected for layout)
            if node_id_in_graph_edges < person_in_graph_data.spouse.id:
                display_graph.add_edge(node_id_in_graph_edges, person_in_graph_data.spouse.id, type="spouse_of",
                                       style="dashed", penwidth=1.0, color="dimgray")

    if not display_graph.nodes:
        if VERBOSE_LOGGING: print(
            f"Year {year}: Visualization skipped - no nodes to construct display graph after filtering.")
        return

    # --- Node attributes for drawing ---
    node_labels = {};
    node_colors_list = [];
    node_sizes = []
    # Simplified legend map - actual coloring might be more granular
    legend_color_map = {
        "Leader (Monarch)": "#FFD700",  # Gold
        "Heir / High Noble": "#FFA500",  # Orange
        "Other Noble": "#90EE90",  # LightGreen
        "Placeholder Ancestor": "#F5F5DC",  # Beige
        "Deceased": "#A9A9A9",  # DarkGray
        "Obscure/Pruned Hint": "#E0E0E0"  # Very Light Gray (if used)
    }
    # This map is used for actual node coloring based on keywords in titles or status
    actual_node_coloring_keywords = {  # More granular for coloring
        "King": "#FFD700", "Queen": "#FFD700", "High Luminary": "#FFD700", "Shogun": "#FFD700", "Konungr": "#FFD700",
        "Emperor": "#FFD700",
        "Prince": "#FFA500", "Princess": "#FFA500", "Hime": "#FFA500",
        "Duke": "#8A2BE2", "Duchess": "#8A2BE2", "Jarl": "#8A2BE2", "Daimyo": "#8A2BE2",
        # Violet/Purple for high nobles
        "Patriarca": "#006400", "Matriarca": "#006400",  # Dark Green
        "Lord": "#ADD8E6", "Lady": "#ADD8E6", "Don": "#ADD8E6", "Doña": "#ADD8E6",  # Light Blue for general nobility
        "Knight": "#C0C0C0", "Dame": "#C0C0C0", "Sir": "#C0C0C0",  # Silver
        "Noble (Other)": "#90EE90", "Deceased": "#A9A9A9", "Commoner": "#D3D3D3", "Obscure": "#E0E0E0",
        "PlaceholderParent": "#F5F5DC"
    }

    for node_id_for_attrs in display_graph.nodes():
        person_for_attrs = display_graph.nodes[node_id_for_attrs]['data']

        # Label: First Name, First part of Surname, Monarch Symbol
        label_parts = [person_for_attrs.name.split(' ')[0]]  # First name
        if hasattr(person_for_attrs, 'surname') and person_for_attrs.surname and len(person_for_attrs.surname) > 0:
            label_parts.append(person_for_attrs.surname.split(' ')[0])  # First part of surname
        if person_for_attrs.is_monarch: label_parts.append("👑")
        node_labels[node_id_for_attrs] = "\n".join(label_parts)

        current_node_color_val = actual_node_coloring_keywords["Noble (Other)"]  # Default
        current_node_size_val = 600

        if any("PlaceholderParent" in title for title in person_for_attrs.titles):
            current_node_color_val = actual_node_coloring_keywords["PlaceholderParent"]
            current_node_size_val = 200
            node_labels[node_id_for_attrs] = f"{person_for_attrs.name.split(' ')[0]}\n(Ancestor)"  # Simpler label
        elif not person_for_attrs.is_alive(year):
            current_node_color_val = actual_node_coloring_keywords["Deceased"]
            current_node_size_val = 300
        elif "Obscure" in "".join(person_for_attrs.titles):  # For pruned/obscured individuals if they were shown
            current_node_color_val = actual_node_coloring_keywords["Obscure"]
            current_node_size_val = 250
        else:  # Living, non-placeholder, non-obscure
            primary_title_lower = person_for_attrs.titles[0].lower() if person_for_attrs.titles else ""
            color_was_assigned = False
            if person_for_attrs.is_monarch:
                current_node_color_val = legend_color_map.get("Leader (Monarch)", actual_node_coloring_keywords["King"])
                current_node_size_val = 1500;
                color_was_assigned = True
            else:  # Not monarch, check other important titles against legend keywords for broad categories
                if any(ht_kw.lower() in primary_title_lower for ht_kw in
                       ["prince", "princess", "duke", "duchess", "jarl", "daimyo", "hime"]):
                    current_node_color_val = legend_color_map.get("Heir / High Noble",
                                                                  actual_node_coloring_keywords["Prince"])
                    current_node_size_val = 900;
                    color_was_assigned = True

            if not color_was_assigned and not person_for_attrs.is_noble:  # Non-noble commoner
                current_node_color_val = actual_node_coloring_keywords["Commoner"];
                current_node_size_val = 400
            elif not color_was_assigned and person_for_attrs.is_noble:  # Default "Other Noble"
                current_node_color_val = legend_color_map.get("Other Noble",
                                                              actual_node_coloring_keywords["Noble (Other)"])
                current_node_size_val = 700

        node_colors_list.append(current_node_color_val)
        node_sizes.append(max(150, current_node_size_val))  # Ensure a minimum visible size

    # --- Layout and Drawing ---
    pos = None
    try:
        # For 'dot', parent->child edges are expected by default.
        pos = nx.nx_agraph.graphviz_layout(display_graph, prog='dot',
                                           args="-Gsplines=true -Gnodesep=0.4 -Granksep=0.7 -Gratio=auto -Gconcentrate=false")
    except Exception as e_graphviz:
        if VERBOSE_LOGGING: print(f"PyGraphviz 'dot' layout failed ({e_graphviz}). Using fallback NetworkX layout.")
        temp_undirected_graph_for_layout = display_graph.to_undirected()  # Some layouts prefer undirected
        if not display_graph.nodes():  # Should be caught earlier, but as a safeguard
            if VERBOSE_LOGGING: print("Visualization: No nodes to draw after all filtering."); return

        # Try Kamada-Kawai for connected components, otherwise spring
        if nx.number_connected_components(
                temp_undirected_graph_for_layout) == 1 and display_graph.number_of_nodes() > 2:  # Kamada-Kawai works best on connected
            try:
                pos = nx.kamada_kawai_layout(display_graph)  # Use original directed graph for layout if possible
            except Exception as e_kk:  # Kamada-Kawai can also fail
                if VERBOSE_LOGGING: print(f"Kamada-Kawai layout failed ({e_kk}). Using spring layout.")
                pos = nx.spring_layout(display_graph, k=1.5 / max(1, (len(display_graph.nodes()) ** 0.5)),
                                       iterations=50, seed=year)  # Seed for consistency
        else:  # Disconnected or very small graph, spring_layout is more robust
            pos = nx.spring_layout(display_graph, k=1.5 / max(1, (len(display_graph.nodes()) ** 0.5)), iterations=40,
                                   seed=year)

    if pos is None and display_graph.nodes():  # Absolute fallback if no positions were generated
        pos = nx.random_layout(display_graph, seed=year)
    elif not display_graph.nodes():
        return  # Still no nodes

    fig, ax = plt.subplots(figsize=(max(14, len(nodes_to_display) * 0.4), max(10, len(nodes_to_display) * 0.3)))

    parent_edges_list = [(u, v) for u, v, d_edge in display_graph.edges(data=True) if d_edge.get("type") == "parent_of"]
    spouse_edges_list = [(u, v) for u, v, d_edge in display_graph.edges(data=True) if d_edge.get("type") == "spouse_of"]

    nx.draw_networkx_nodes(display_graph, pos, ax=ax, node_color=node_colors_list,
                           node_size=node_sizes, alpha=0.95, linewidths=0.5, edgecolors='dimgray')
    nx.draw_networkx_labels(display_graph, pos, ax=ax, labels=node_labels,
                            font_size=max(5, 7 - len(nodes_to_display) // 30),  # Adaptive font size
                            font_weight='normal', font_color='#1A1A1A')  # Darker font for readability

    nx.draw_networkx_edges(display_graph, pos, ax=ax, edgelist=parent_edges_list,
                           width=1.0, alpha=0.65, edge_color='black',
                           arrows=True, arrowstyle='-|>', arrowsize=10, connectionstyle='arc3,rad=0.05')
    nx.draw_networkx_edges(display_graph, pos, ax=ax, edgelist=spouse_edges_list,
                           width=0.7, alpha=0.55, edge_color='dimgray', style='dashed', arrows=False)

    # --- Create Legend ---
    legend_handles_list = [mpatches.Patch(color=color_val, label=label_text) for label_text, color_val in
                           legend_color_map.items()]
    legend_handles_list.append(
        plt.Line2D([0], [0], color='black', lw=1.0, label='Parent-Child Link (↓)', linestyle='-'))
    legend_handles_list.append(plt.Line2D([0], [0], color='dimgray', lw=0.8, label='Spousal Link (↔)', linestyle='--'))

    # Position legend to avoid overlapping graph if possible
    ax.legend(handles=legend_handles_list, loc='upper left', bbox_to_anchor=(0.01, 0.99),
              fontsize='xx-small', frameon=True, facecolor='#FFFFFFE0', edgecolor='silver',
              title="Legend", title_fontsize="x-small")
    # --- End Legend ---

    plot_title_text = f"Dynastic Chart: House of {family_tree_obj.dynasty_name} - Year {year}\n" \
                      f"({family_tree_obj.theme_config.get('location_flavor', 'A Realm')}) - View: {display_mode}"
    plt.title(plot_title_text, fontsize=13, loc='center', wrap=True)  # Center title
    plt.axis('off')  # Turn off axis lines and ticks
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])  # Adjust layout to make space for elements

    # Ensure visualizations directory exists
    visualizations_dir_path = "visualizations"
    os.makedirs(visualizations_dir_path, exist_ok=True)
    filename_path = os.path.join(visualizations_dir_path,
                                 f"family_tree_{family_tree_obj.dynasty_name.replace(' ', '_')}_year_{year}_{display_mode}{filename_suffix}.png")

    try:
        plt.savefig(filename_path, dpi=150, bbox_inches='tight')  # Higher DPI for better quality
        if VERBOSE_LOGGING: print(f"Family tree visualization saved to {filename_path}")
    except Exception as e_save_fig:
        print(f"Error saving visualization to {filename_path}: {e_save_fig}")
    plt.show()  # Display in notebook if running interactively
    plt.close(fig)  # Important to close the figure to free memory


print("visualization.plotter module defined with legend and improvements.")