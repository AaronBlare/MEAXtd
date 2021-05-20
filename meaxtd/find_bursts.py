import numpy as np
from intervaltree import IntervalTree


def find_spikes(data, method, coefficient, progress_callback):
    signals = data.stream
    num_signals = signals.shape[1]
    total_time_in_ms = int(np.ceil(data.time[-1] * 1000))
    data.TSR = np.zeros(int(total_time_in_ms / 50), dtype=int)
    data.TSR_times = np.arange(0, data.time[-1], 0.05)
    for signal_id in range(0, num_signals):
        progress_callback.emit(round(signal_id * 40 / num_signals))
        if method == 'Median':
            noise_mad = np.median(np.absolute(signals[:, signal_id])) / 0.6745
            crossings = detect_threshold_crossings(signals[:, signal_id], data.fs, coefficient * noise_mad, 0.002)
        elif method == 'RMS':
            noise_rms = np.sqrt(np.mean(signals[:, signal_id] ** 2))
            crossings = detect_threshold_crossings(signals[:, signal_id], data.fs, coefficient * noise_rms, 0.002)
        elif method == 'std':
            noise_std = np.std(signals[:, signal_id])
            crossings = detect_threshold_crossings(signals[:, signal_id], data.fs, coefficient * noise_std, 0.002)

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
            TSR_index = int(np.ceil(spikes[peak_id] / 500))
            data.TSR[TSR_index - 1] += 1
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


def find_burstlets(data, spike_method, spike_coeff, burst_window, progress_callback):
    if not data.spikes:
        find_spikes(data, spike_method, spike_coeff, progress_callback)
    signals = data.stream
    spikes = data.spikes
    num_signals = signals.shape[1]
    window = 10 * burst_window  # sampling frequency 0.1 ms
    for signal_id in range(0, num_signals):
        progress_callback.emit(40 + round(signal_id * 40 / num_signals))
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
                if len(set(curr_burstlet)) >= 5:
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


def find_bursts(data, spike_method, spike_coeff, burst_window, burst_num_channels, progress_callback):
    if not data.burstlets:
        find_burstlets(data, spike_method, spike_coeff, burst_window, progress_callback)
    signals = data.stream
    signal_len = len(signals[:, 0])
    num_signals = signals.shape[1]
    burst_detection_function = np.empty(signal_len, dtype=int)
    burst_detection_function[:] = 0
    for signal_id in range(0, num_signals):
        data.bursts_starts[signal_id] = []
        data.bursts_ends[signal_id] = []
        data.bursts_burstlets[signal_id] = []
        for burstlet_id in range(0, len(data.burstlets[signal_id])):
            curr_burstlet_start = data.burstlets_starts[signal_id][burstlet_id]
            curr_burstlet_end = data.burstlets_ends[signal_id][burstlet_id]
            burst_detection_function[curr_burstlet_start:curr_burstlet_end] += 1
    threshold_crossings = np.diff(burst_detection_function > burst_num_channels, prepend=False)
    threshold_crossings_ids = np.argwhere(threshold_crossings)[:, 0]
    interval_tree = create_interval_tree(data)
    for interval_id in range(0, len(threshold_crossings_ids) // 2):
        progress_callback.emit(80 + int(interval_id * 10 / (len(threshold_crossings_ids) // 2)))
        interval_start = threshold_crossings_ids[interval_id * 2]
        interval_end = threshold_crossings_ids[interval_id * 2 + 1]
        curr_intervals = interval_tree.overlap(interval_start, interval_end)
        if len(curr_intervals) > burst_num_channels:
            data.bursts.append(curr_intervals)
            curr_signals = []
            curr_burstlets = []
            for interval in curr_intervals:
                curr_data = interval.data
                curr_signals.append(curr_data['signal_id'])
                curr_burstlets.append(curr_data['burstlet_id'])
            curr_start = len(data.time)
            curr_finish = 0
            for i in range(0, len(curr_signals)):
                curr_signal = curr_signals[i]
                curr_burstlet = curr_burstlets[i]
                if data.burstlets_starts[curr_signal][curr_burstlet] < curr_start:
                    curr_start = data.burstlets_starts[curr_signal][curr_burstlet]
                if data.burstlets_ends[curr_signal][curr_burstlet] > curr_finish:
                    curr_finish = data.burstlets_ends[curr_signal][curr_burstlet]
            for i in range(0, len(curr_signals)):
                curr_signal = curr_signals[i]
                curr_burstlet = curr_burstlets[i]
                if len(data.bursts_starts[curr_signal]) == 0 or curr_start > data.bursts_starts[curr_signal][-1]:
                    data.bursts_starts[curr_signal].append(curr_start)
                    data.bursts_ends[curr_signal].append(curr_finish)
                    data.bursts_burstlets[curr_signal].append(curr_burstlet)

    burst_activation_vector = np.empty(shape=(len(data.bursts), num_signals))
    burst_activation_vector[:] = np.nan
    burst_deactivation_vector = np.empty(shape=(len(data.bursts), num_signals))
    burst_deactivation_vector[:] = np.nan
    for burst_id in range(0, len(data.bursts)):
        curr_burst = data.bursts[burst_id]
        activation_time = len(data.time)
        deactivation_time = 0
        for interval in curr_burst:
            if interval.begin < activation_time:
                activation_time = interval.begin
            if interval.end > deactivation_time:
                deactivation_time = interval.end
        for interval in curr_burst:
            signal_id = interval.data['signal_id']
            curr_activation_time = data.time[interval.begin] - data.time[activation_time]
            burst_activation_vector[burst_id, signal_id] = curr_activation_time
            curr_deactivation_time = data.time[deactivation_time] - data.time[interval.end]
            burst_deactivation_vector[burst_id, signal_id] = curr_deactivation_time
    data.burst_activation = np.zeros(num_signals)
    data.burst_deactivation = np.zeros(num_signals)
    for signal_id in range(0, num_signals):
        num_activations = 0
        num_deactivations = 0
        curr_activations = 0
        curr_deactivations = 0
        for burst_id in range(0, len(data.bursts)):
            if not np.isnan(burst_activation_vector[burst_id, signal_id]):
                num_activations += 1
                curr_activations += burst_activation_vector[burst_id, signal_id]
            if not np.isnan(burst_deactivation_vector[burst_id, signal_id]):
                num_deactivations += 1
                curr_deactivations += burst_deactivation_vector[burst_id, signal_id]
        if num_activations > 0:
            data.burst_activation[signal_id] = curr_activations / num_activations
        if num_deactivations > 0:
            data.burst_deactivation[signal_id] = curr_deactivations / num_deactivations

    for signal_id in range(0, num_signals):
        progress_callback.emit(90 + round(signal_id * 10 / num_signals))
        data.burst_stream[signal_id] = np.empty(len(signals[:, signal_id]))
        data.burst_stream[signal_id][:] = np.nan
        data.burst_borders[signal_id] = np.empty(len(signals[:, signal_id]))
        data.burst_borders[signal_id][:] = np.nan
        for burst_id in range(0, len(data.bursts_starts[signal_id])):
            curr_start = data.bursts_starts[signal_id][burst_id]
            curr_end = data.bursts_ends[signal_id][burst_id]
            amplitude = max(data.burstlets_amplitudes[signal_id])
            data.burst_borders[signal_id][curr_start] = amplitude
            data.burst_borders[signal_id][curr_start + 1] = - amplitude
            data.burst_borders[signal_id][curr_end] = amplitude
            data.burst_borders[signal_id][curr_end + 1] = - amplitude
        for burst_id in range(0, len(data.burstlets[signal_id])):
            if burst_id in data.bursts_burstlets[signal_id]:
                for curr_id in range(data.burstlets_starts[signal_id][burst_id],
                                     data.burstlets_ends[signal_id][burst_id]):
                    data.burst_stream[signal_id][curr_id] = signals[curr_id, signal_id]

    progress_callback.emit(100)
