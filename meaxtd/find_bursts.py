import numpy as np
from intervaltree import IntervalTree


def find_spikes(data):
    signals = data.stream
    num_signals = signals.shape[1]
    for signal_id in range(0, num_signals):
        noise_std = np.std(signals[:, signal_id])
        noise_rms = np.sqrt(np.mean(signals[:, signal_id] ** 2))
        noise_mad = np.median(np.absolute(signals[:, signal_id])) / 0.6745

        crossings = detect_threshold_crossings(signals[:, signal_id], data.fs, -5.0 * noise_mad, 0.003)
        spikes = get_spike_peaks(signals[:, signal_id], data.fs, crossings, 0.002)
        spikes_ends, spikes_maxima = get_spike_ends(signals[:, signal_id], data.fs, crossings, 0.002)
        spikes_amplitudes = [signals[:, signal_id][spikes_maxima[spike_id]] - signals[:, signal_id][spikes[spike_id]]
                             for spike_id in range(0, len(spikes))]

        data.spikes[signal_id] = np.asarray(spikes)
        data.spikes_starts[signal_id] = np.asarray(crossings)
        data.spikes_ends[signal_id] = np.asarray(spikes_ends)
        data.spikes_amplitudes[signal_id] = np.asarray(spikes_amplitudes)

        data.spike_stream[signal_id] = np.empty(len(signals[:, signal_id]))
        data.spike_stream[signal_id][:] = np.nan
        for peak_id in range(0, len(spikes)):
            for curr_id in range(crossings[peak_id], spikes_ends[peak_id] + 1):
                data.spike_stream[signal_id][curr_id] = signals[curr_id, signal_id]


def detect_threshold_crossings(signal, fs, threshold, dead_time):
    dead_time_idx = dead_time * fs
    threshold_crossings = np.diff((signal <= threshold).astype(int) > 0).nonzero()[0]
    distance_sufficient = np.insert(np.diff(threshold_crossings) >= dead_time_idx, 0, True)
    while not np.all(distance_sufficient):
        threshold_crossings = threshold_crossings[distance_sufficient]
        distance_sufficient = np.insert(np.diff(threshold_crossings) >= dead_time_idx, 0, True)
    return threshold_crossings


def get_next_minimum(signal, index, max_samples_to_search):
    search_end_idx = min(index + max_samples_to_search, signal.shape[0])
    min_idx = np.argmin(signal[index:search_end_idx])
    return index + min_idx


def get_spike_peaks(signal, fs, threshold_crossings, search_range):
    search_end = int(search_range * fs)
    spikes_peaks = [get_next_minimum(signal, t, search_end) for t in threshold_crossings]
    return np.array(spikes_peaks)


def get_next_maximum(signal, index, max_samples_to_search):
    search_end_idx = min(index + max_samples_to_search, signal.shape[0])
    max_idx = np.argmax(signal[index:search_end_idx])
    return index + max_idx


def get_next_zero_crossing(signal, index, max_samples_to_search):
    search_end_idx = min(index + max_samples_to_search, signal.shape[0])
    for i in range(index, search_end_idx):
        if signal[i] <= 0.0:
            zero_crossing_idx = i
            break
    if 'zero_crossing_idx' not in locals():
        zero_crossing_idx = i
    return zero_crossing_idx


def get_spike_ends(signal, fs, minima, search_range):
    search_end = int(search_range * fs)
    spikes_maxima = [get_next_maximum(signal, t, search_end) for t in minima]
    spikes_ends = [get_next_zero_crossing(signal, t, search_end) for t in spikes_maxima]
    return np.array(spikes_ends), np.array(spikes_maxima)


def find_burstlets(data):
    if not data.spikes:
        find_spikes(data)
    signals = data.stream
    spikes = data.spikes
    num_signals = signals.shape[1]
    window = 100 * 10  # 100 ms
    for signal_id in range(0, num_signals):
        data.burstlets[signal_id] = []
        num_spikes = len(spikes[signal_id])
        curr_burstlet = []
        burstlet_amplitude = []
        burstlet_start = []
        burstlet_end = []
        for spike_id in range(0, num_spikes - 1):
            if spikes[signal_id][spike_id + 1] - spikes[signal_id][spike_id] < window:
                curr_burstlet.append(spikes[signal_id][spike_id])
            else:
                if len(curr_burstlet) >= 5:
                    curr_burstlet.append(spikes[signal_id][spike_id])
                    data.burstlets[signal_id].append(curr_burstlet)
                    curr_start_id = np.where(spikes[signal_id] == curr_burstlet[0])[0][0]
                    curr_end_id = np.where(spikes[signal_id] == curr_burstlet[-1])[0][0]
                    burstlet_amplitude.append(max(signals[:, signal_id][curr_burstlet[0]:curr_burstlet[-1]]) -
                                              min(signals[:, signal_id][curr_burstlet[0]:curr_burstlet[-1]]))
                    burstlet_start.append(data.spikes_starts[signal_id][curr_start_id])
                    burstlet_end.append(data.spikes_ends[signal_id][curr_end_id])
                curr_burstlet = []
        data.burstlets_starts[signal_id] = np.asarray(burstlet_start)
        data.burstlets_ends[signal_id] = np.asarray(burstlet_end)
        data.burstlets_amplitudes[signal_id] = np.asarray(burstlet_amplitude)

        data.burstlet_stream[signal_id] = np.empty(len(signals[:, signal_id]))
        data.burstlet_stream[signal_id][:] = np.nan
        for peak_id in range(0, len(data.burstlets[signal_id])):
            for curr_id in range(burstlet_start[peak_id], burstlet_end[peak_id] + 1):
                data.burstlet_stream[signal_id][curr_id] = signals[curr_id, signal_id]


def create_interval_tree(data):
    tree = IntervalTree()
    num_signals = data.stream.shape[1]
    for signal_id in range(0, num_signals):
        for burstlet_id in range(0, len(data.burstlets[signal_id])):
            curr_burstlet_start = data.burstlets_starts[signal_id][burstlet_id]
            curr_burstlet_end = data.burstlets_ends[signal_id][burstlet_id]
            tree[curr_burstlet_start:curr_burstlet_end] = {'signal_id': signal_id, 'burstlet_id': burstlet_id}
    return tree


def find_bursts(data):
    if not data.burstlets:
        find_burstlets(data)
    signals = data.stream
    signal_len = len(signals[:, 0])
    num_signals = signals.shape[1]
    burst_detection_function = np.empty(signal_len, dtype=int)
    burst_detection_function[:] = 0
    for signal_id in range(0, num_signals):
        for burstlet_id in range(0, len(data.burstlets[signal_id])):
            curr_burstlet_start = data.burstlets_starts[signal_id][burstlet_id]
            curr_burstlet_end = data.burstlets_ends[signal_id][burstlet_id]
            burst_detection_function[curr_burstlet_start:curr_burstlet_end] += 1
    threshold_crossings = np.diff(burst_detection_function > 5, prepend=False)
    threshold_crossings_ids = np.argwhere(threshold_crossings)[:, 0]
    interval_tree = create_interval_tree(data)

