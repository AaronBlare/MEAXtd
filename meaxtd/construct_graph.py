import numpy as np
import pandas as pd
import datetime
import operator
import pygraphviz as pgv


def get_electrode_info(num_channels):
    electrode_info = {}
    if num_channels == 60:
        electrode_info[0] = {'X': 150.0, 'Y': 0.0}
        electrode_info[1] = {'X': 300.0, 'Y': 0.0}
        electrode_info[2] = {'X': 450.0, 'Y': 0.0}
        electrode_info[3] = {'X': 600.0, 'Y': 0.0}
        electrode_info[4] = {'X': 750.0, 'Y': 0.0}
        electrode_info[5] = {'X': 900.0, 'Y': 0.0}

        electrode_info[6] = {'X': 0.0, 'Y': 150.0}
        electrode_info[7] = {'X': 150.0, 'Y': 150.0}
        electrode_info[8] = {'X': 300.0, 'Y': 150.0}
        electrode_info[9] = {'X': 450.0, 'Y': 150.0}
        electrode_info[10] = {'X': 600.0, 'Y': 150.0}
        electrode_info[11] = {'X': 750.0, 'Y': 150.0}
        electrode_info[12] = {'X': 900.0, 'Y': 150.0}
        electrode_info[13] = {'X': 1050.0, 'Y': 150.0}

        electrode_info[14] = {'X': 0.0, 'Y': 300.0}
        electrode_info[15] = {'X': 150.0, 'Y': 300.0}
        electrode_info[16] = {'X': 300.0, 'Y': 300.0}
        electrode_info[17] = {'X': 450.0, 'Y': 300.0}
        electrode_info[18] = {'X': 600.0, 'Y': 300.0}
        electrode_info[19] = {'X': 750.0, 'Y': 300.0}
        electrode_info[20] = {'X': 900.0, 'Y': 300.0}
        electrode_info[21] = {'X': 1050.0, 'Y': 300.0}

        electrode_info[22] = {'X': 0.0, 'Y': 450.0}
        electrode_info[23] = {'X': 150.0, 'Y': 450.0}
        electrode_info[24] = {'X': 300.0, 'Y': 450.0}
        electrode_info[25] = {'X': 450.0, 'Y': 450.0}
        electrode_info[26] = {'X': 600.0, 'Y': 450.0}
        electrode_info[27] = {'X': 750.0, 'Y': 450.0}
        electrode_info[28] = {'X': 900.0, 'Y': 450.0}
        electrode_info[29] = {'X': 1050.0, 'Y': 450.0}

        electrode_info[30] = {'X': 0.0, 'Y': 600.0}
        electrode_info[31] = {'X': 150.0, 'Y': 600.0}
        electrode_info[32] = {'X': 300.0, 'Y': 600.0}
        electrode_info[33] = {'X': 450.0, 'Y': 600.0}
        electrode_info[34] = {'X': 600.0, 'Y': 600.0}
        electrode_info[35] = {'X': 750.0, 'Y': 600.0}
        electrode_info[36] = {'X': 900.0, 'Y': 600.0}
        electrode_info[37] = {'X': 1050.0, 'Y': 600.0}

        electrode_info[38] = {'X': 0.0, 'Y': 750.0}
        electrode_info[39] = {'X': 150.0, 'Y': 750.0}
        electrode_info[40] = {'X': 300.0, 'Y': 750.0}
        electrode_info[41] = {'X': 450.0, 'Y': 750.0}
        electrode_info[42] = {'X': 600.0, 'Y': 750.0}
        electrode_info[43] = {'X': 750.0, 'Y': 750.0}
        electrode_info[44] = {'X': 900.0, 'Y': 750.0}
        electrode_info[45] = {'X': 1050.0, 'Y': 750.0}

        electrode_info[46] = {'X': 0.0, 'Y': 900.0}
        electrode_info[47] = {'X': 150.0, 'Y': 900.0}
        electrode_info[48] = {'X': 300.0, 'Y': 900.0}
        electrode_info[49] = {'X': 450.0, 'Y': 900.0}
        electrode_info[50] = {'X': 600.0, 'Y': 900.0}
        electrode_info[51] = {'X': 750.0, 'Y': 900.0}
        electrode_info[52] = {'X': 900.0, 'Y': 900.0}
        electrode_info[53] = {'X': 1050.0, 'Y': 900.0}

        electrode_info[54] = {'X': 150.0, 'Y': 1050.0}
        electrode_info[55] = {'X': 300.0, 'Y': 1050.0}
        electrode_info[56] = {'X': 450.0, 'Y': 1050.0}
        electrode_info[57] = {'X': 600.0, 'Y': 1050.0}
        electrode_info[58] = {'X': 750.0, 'Y': 1050.0}
        electrode_info[59] = {'X': 900.0, 'Y': 1050.0}
    elif num_channels == 64:
        for channel_id in range(0, num_channels):
            electrode_info[channel_id] = {'X': channel_id % 8 * 150.0, 'Y': channel_id // 8 * 150.0}
    return electrode_info


def construct_delayed_spikes_graph(data, progress_callback, burst_method, delta, num_frames, cutoff, burst_id):
    num_channels = data.stream.shape[1]
    curr_burst = data.bursts[burst_id]
    if burst_method == 'Burstlet':
        curr_burst = list(curr_burst)
        curr_burst_start = min([curr_burst[start_id].begin for start_id in range(0, len(curr_burst))])
        curr_burst_end = max([curr_burst[end_id].end for end_id in range(0, len(curr_burst))])
        curr_channels = list(
            set([curr_burst[interval_id].data['signal_id'] for interval_id in range(0, len(curr_burst))]))
        curr_channels.sort()
    elif burst_method == 'TSR':
        curr_burst_start = curr_burst['start']
        curr_burst_end = curr_burst['end']
        curr_channels = curr_burst['channels']
    sampling_rate = (data.time[1] - data.time[0]) * 1000  # in ms
    if sampling_rate >= delta:  # frame size = delta (should be equal or higher than sampling rate, default: 0.05 ms)
        frame_size = 1
    else:
        frame_size = int(delta // sampling_rate)
    # num_frames = round((curr_burst_end - curr_burst_start + 1) / frame_size)
    tau_list = list(range(1, num_frames + 1)) * frame_size

    progress_callback.emit(10)

    electrode_info = get_electrode_info(num_channels)
    electrode_frame_dict = {}
    channel_id = 0
    for channel in curr_channels:
        progress_callback.emit(10 + round(channel_id * 20 / len(curr_channels)))
        electrode_frame_dict[channel] = {}
        electrode_frame_dict[channel]['X'] = electrode_info[channel]['X']
        electrode_frame_dict[channel]['Y'] = electrode_info[channel]['Y']
        start_id = np.searchsorted(data.spikes[channel], curr_burst_start)
        end_id = np.searchsorted(data.spikes[channel], curr_burst_end)
        electrode_frame_dict[channel]['Spikes'] = data.spikes[channel][start_id:end_id]
        channel_id += 1

    c_ij_dict = {'Channel 1': [], 'Channel 2': [], 'Num spikes channel 1': [], 'Num spikes channel 2': [],
                 'Num delayed spikes': [], 'C_ij_max': [], 'tau': []}
    channel_id = 0
    for channel_1 in curr_channels:
        progress_callback.emit(30 + round(channel_id * 50 / len(curr_channels)))
        for channel_2 in curr_channels:
            if channel_2 != channel_1:
                spikes_channel_1 = electrode_frame_dict[channel_1]['Spikes']
                spikes_channel_2 = electrode_frame_dict[channel_2]['Spikes']
                if len(spikes_channel_1) > 4 and len(spikes_channel_2) > 4:
                    curr_tau_dict = dict.fromkeys(tau_list, 0)
                    sync_ids = []
                    for spike_1 in spikes_channel_1:
                        curr_distances = [spike_2 - spike_1 for spike_2 in spikes_channel_2]
                        for curr_id in range(0, len(curr_distances)):
                            if curr_id not in sync_ids:
                                curr_distance = curr_distances[curr_id]
                                if curr_distance in curr_tau_dict:
                                    curr_tau_dict[curr_distance] += 1
                                    sync_ids.append(curr_id)
                    max_tau = max(curr_tau_dict.items(), key=operator.itemgetter(1))[0]
                    max_tau_id = tau_list.index(max_tau)
                    num_del_sync_spikes = 0
                    for curr_tau in tau_list[0:(max_tau_id + 1)]:
                        num_del_sync_spikes += curr_tau_dict[curr_tau]
                    c_ij = num_del_sync_spikes / len(spikes_channel_2)
                    if c_ij > 0.0:
                        c_ij_dict['Channel 1'].append(channel_1)
                        c_ij_dict['Channel 2'].append(channel_2)
                        c_ij_dict['Num spikes channel 1'].append(len(spikes_channel_1))
                        c_ij_dict['Num spikes channel 2'].append(len(spikes_channel_2))
                        c_ij_dict['Num delayed spikes'].append(num_del_sync_spikes)
                        c_ij_dict['C_ij_max'].append(c_ij)
                        c_ij_dict['tau'].append(max_tau)
        channel_id += 1

    c_ij_unsorted_df = pd.DataFrame.from_dict(c_ij_dict)
    c_ij_sorted_df = c_ij_unsorted_df.sort_values(by=['C_ij_max'], ascending=False)
    percentile_value = np.percentile(c_ij_sorted_df['C_ij_max'], 100 - cutoff)
    c_ij_top = c_ij_sorted_df[c_ij_sorted_df['C_ij_max'] > percentile_value]

    progress_callback.emit(90)

    graph = pgv.AGraph(directed=True, strict=True)
    curr_nodes = set(c_ij_top['Channel 1']).union(c_ij_top['Channel 2'])
    nodes = {}
    for node in curr_nodes:
        nodes[f"Electrode {node + 1}"] = {'total': 0, 'post': 0}
    for pre_node in list(c_ij_top['Channel 1']):
        nodes[f"Electrode {pre_node + 1}"]['total'] += 1
    for post_node in list(c_ij_top['Channel 2']):
        nodes[f"Electrode {post_node + 1}"]['total'] += 1
        nodes[f"Electrode {post_node + 1}"]['post'] += 1
    total_num_edges = 0
    for node in nodes:
        graph.add_node(node,
                       label=f"{node} [{nodes[node]['total']}]",
                       width=nodes[node]['total'] / 4,
                       height=nodes[node]['total'] / 5)
        total_num_edges += nodes[node]['total']
    for edge_id in range(0, len(c_ij_top['Channel 1'])):
        cell_1 = f"Electrode {list(c_ij_top['Channel 1'])[edge_id] + 1}"
        cell_2 = f"Electrode {list(c_ij_top['Channel 2'])[edge_id] + 1}"
        graph.add_edge(cell_1, cell_2, weight=nodes[cell_2]['post'], label=f"{list(c_ij_top['tau'])[edge_id]}ms")
    graph.layout("dot")
    data.graph = graph

    hub_dict = {'Electrode': [], 'Number of connections': [], 'Hub coefficient': []}
    for node in nodes:
        hub_dict['Electrode'].append(int(node[10:]))
        hub_dict['Number of connections'].append(nodes[node]['total'])
        hub_dict['Hub coefficient'].append(nodes[node]['total'] / total_num_edges)

    data.graph_hub = hub_dict

    progress_callback.emit(99)
