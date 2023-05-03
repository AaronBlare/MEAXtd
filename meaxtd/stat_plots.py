import pyqtgraph as pg
import numpy as np


def raster_plot(data, start):
    start_index = np.searchsorted(data.time, start * 60, side='left')
    num_signals = data.stream.shape[1]
    num_spikes = 0
    for signal_id in range(0, num_signals):
        num_spikes += len(data.spikes[signal_id])
    scatter = pg.ScatterPlotItem(size=2, brush=pg.mkBrush('k'))
    nodes = np.empty([num_spikes, 2])
    node_id = 0
    for signal_id in range(0, num_signals):
        curr_spikes = data.spikes[signal_id]
        for curr_spike in curr_spikes:
            nodes[node_id, 0] = data.time[start_index] + data.time[curr_spike]
            nodes[node_id, 1] = signal_id + 1
            node_id += 1
    spots = [{'pos': nodes[i, :], 'data': 1} for i in range(num_spikes)] + [{'pos': [0, 0], 'data': 1}]
    scatter.addPoints(spots)
    return scatter


def tsr_plot(data):
    curve = pg.PlotCurveItem()
    curr_data = data.TSR
    curve.setData(x=data.TSR_times, y=curr_data, pen=pg.mkPen('k'))
    return curve


def tsr_plot_threshold(data, thr):
    curve = pg.PlotCurveItem()
    x = data.TSR_times
    y = np.zeros(x.shape) + thr
    curve.setData(x=x, y=y, pen=pg.mkPen('r', width=2))
    return curve


def colormap_plot(data):
    data = np.insert(data, 0, None)
    data = np.insert(data, 7, None)
    data = np.insert(data, 56, None)
    data = np.insert(data, 63, None)
    data.resize((8, 8))
    img = pg.ImageItem(image=data)
    return img
