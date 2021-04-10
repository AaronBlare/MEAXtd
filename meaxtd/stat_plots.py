import pyqtgraph as pg
import numpy as np


def raster_plot(data):
    spikes = data.spikes
    num_signals = data.stream.shape[1]
    num_spikes = 0
    for signal_id in range(0, num_signals):
        num_spikes += len(spikes[signal_id])
    nodes = np.empty([num_spikes, 2])
    edges = np.empty([num_spikes, 2], dtype=int)
    g = pg.GraphItem()
    node_id = 0
    for signal_id in range(0, num_signals):
        curr_spikes = spikes[signal_id]
        for curr_spike in curr_spikes:
            nodes[node_id, 0] = data.time[curr_spike]
            nodes[node_id, 1] = signal_id + 1
            node_id += 1
    g.setData(pos=nodes, adj=edges, symbolPen=pg.mkPen('w', width=1))
    return g
