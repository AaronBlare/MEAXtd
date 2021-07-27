import os
import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.exporters
import datetime
from intervaltree import IntervalTree
from PySide2.QtGui import QPixmap, QImage, QPainter


def find_spikes(data, excluded_channels, method, coefficient, start, end, progress_callback):
    num_signals = data.stream.shape[1]

    start_index = np.where(data.time == start * 60)[0][0]
    if end < int(np.ceil(data.time[-1] / 60)):
        end_index = np.where(data.time == end * 60)[0][0]
    else:
        end_index = np.where(data.time == data.time[-1])[0][0]

    total_time_in_ms = int(np.ceil((data.time[end_index] - data.time[start_index]) * 1000))
    data.TSR = np.zeros(int(total_time_in_ms / 50), dtype=int)
    data.TSR_times = np.arange(data.time[start_index], data.time[end_index], 0.05)
    data.TSR_channels = np.empty(int(total_time_in_ms / 50), dtype=object)
    for signal_id in range(0, num_signals):
        progress_callback.emit(round(signal_id * 30 / num_signals))

        if signal_id in excluded_channels:
            data.spikes[signal_id] = np.asarray([])
            data.spikes_starts[signal_id] = np.asarray([])
            data.spikes_ends[signal_id] = np.asarray([])
            data.spikes_amplitudes[signal_id] = np.asarray([])

            data.spike_stream[signal_id] = np.empty(len(data.stream[start_index:end_index, signal_id]))
            data.spike_stream[signal_id][:] = np.nan

        else:
            if method == 'Median':
                noise_mad = np.median(np.absolute(data.stream[start_index:end_index, signal_id])) / 0.6745
                crossings = detect_threshold_crossings(data.stream[start_index:end_index, signal_id], data.fs,
                                                       coefficient * noise_mad, 0.001)
            elif method == 'RMS':
                noise_rms = np.sqrt(np.mean(data.stream[start_index:end_index, signal_id] ** 2))
                crossings = detect_threshold_crossings(data.stream[start_index:end_index, signal_id], data.fs,
                                                       coefficient * noise_rms, 0.001)
            elif method == 'std':
                noise_std = np.std(data.stream[start_index:end_index, signal_id])
                crossings = detect_threshold_crossings(data.stream[start_index:end_index, signal_id], data.fs,
                                                       coefficient * noise_std, 0.001)

            spikes = get_spike_peaks(data.stream[start_index:end_index, signal_id], data.fs, crossings, 0.001)
            spikes_ends, spikes_maxima = get_spike_ends(data.stream[start_index:end_index, signal_id], data.fs,
                                                        crossings, 0.001)
            spikes_amplitudes = [data.stream[start_index:end_index, signal_id][spikes_maxima[spike_id]] -
                                 data.stream[start_index:end_index, signal_id][spikes[spike_id]]
                                 for spike_id in range(0, len(spikes))]

            data.spikes[signal_id] = np.asarray(spikes)
            data.spikes_starts[signal_id] = np.asarray(crossings)
            data.spikes_ends[signal_id] = np.asarray(spikes_ends)
            data.spikes_amplitudes[signal_id] = np.asarray(spikes_amplitudes)

            data.spike_stream[signal_id] = np.empty(len(data.stream[:, signal_id]))
            data.spike_stream[signal_id][:] = np.nan
            for peak_id in range(0, len(spikes)):
                TSR_index = int(np.ceil(spikes[peak_id] * data.time[1] * 1000 / 50))
                data.TSR[TSR_index - 1] += 1
                if data.TSR_channels[TSR_index - 1]:
                    data.TSR_channels[TSR_index - 1].append(signal_id)
                else:
                    data.TSR_channels[TSR_index - 1] = [signal_id]
                for curr_id in range(crossings[peak_id], spikes_ends[peak_id] + 1):
                    curr_id_mod = start_index + curr_id
                    data.spike_stream[signal_id][curr_id_mod] = data.stream[curr_id_mod, signal_id]


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


def find_burstlets(data, excluded_channels, spike_method, spike_coeff, burst_window, start, end, progress_callback):
    if not data.spikes:
        find_spikes(data, excluded_channels, spike_method, spike_coeff, start, end, progress_callback)

    start_index = np.where(data.time == start * 60)[0][0]
    if end < int(np.ceil(data.time[-1] / 60)):
        end_index = np.where(data.time == end * 60)[0][0]
    else:
        end_index = np.where(data.time == data.time[-1])[0][0]

    num_signals = data.stream.shape[1]
    window = 10 * burst_window  # sampling frequency 0.1 ms
    for signal_id in range(0, num_signals):
        progress_callback.emit(30 + round(signal_id * 30 / num_signals))
        data.burstlets[signal_id] = []

        if signal_id in excluded_channels:
            data.burstlets_starts[signal_id] = np.asarray([])
            data.burstlets_ends[signal_id] = np.asarray([])
            data.burstlets_amplitudes[signal_id] = np.asarray([])

            data.burstlet_stream[signal_id] = np.empty(len(data.stream[start_index:end_index, signal_id]))
            data.burstlet_stream[signal_id][:] = np.nan

        else:
            num_spikes = len(data.spikes[signal_id])
            curr_burstlet = []
            burstlet_amplitude = []
            burstlet_start = []
            burstlet_end = []
            for spike_id in range(0, num_spikes - 1):
                if data.spikes[signal_id][spike_id + 1] - data.spikes[signal_id][spike_id] < window:
                    curr_burstlet.append(data.spikes[signal_id][spike_id])
                else:
                    if len(set(curr_burstlet)) >= 5:
                        curr_burstlet.append(data.spikes[signal_id][spike_id])
                        data.burstlets[signal_id].append(curr_burstlet)
                        curr_start_id = np.where(data.spikes[signal_id] == curr_burstlet[0])[0][0]
                        curr_end_id = np.where(data.spikes[signal_id] == curr_burstlet[-1])[0][0]
                        burstlet_amplitude.append(
                            max(data.stream[start_index:end_index, signal_id][curr_burstlet[0]:curr_burstlet[-1]]) -
                            min(data.stream[start_index:end_index, signal_id][curr_burstlet[0]:curr_burstlet[-1]]))
                        burstlet_start.append(data.spikes_starts[signal_id][curr_start_id])
                        burstlet_end.append(data.spikes_ends[signal_id][curr_end_id])
                    curr_burstlet = []
            data.burstlets_starts[signal_id] = np.asarray(burstlet_start)
            data.burstlets_ends[signal_id] = np.asarray(burstlet_end)
            data.burstlets_amplitudes[signal_id] = np.asarray(burstlet_amplitude)

            data.burstlet_stream[signal_id] = np.empty(len(data.stream[:, signal_id]))
            data.burstlet_stream[signal_id][:] = np.nan
            for peak_id in range(0, len(data.burstlets[signal_id])):
                for curr_id in range(burstlet_start[peak_id], burstlet_end[peak_id] + 1):
                    curr_id_mod = curr_id + start_index
                    data.burstlet_stream[signal_id][curr_id_mod] = data.stream[curr_id_mod, signal_id]


def create_interval_tree(data):
    tree = IntervalTree()
    num_signals = data.stream.shape[1]
    for signal_id in range(0, num_signals):
        for burstlet_id in range(0, len(data.burstlets[signal_id])):
            curr_burstlet_start = data.burstlets_starts[signal_id][burstlet_id]
            curr_burstlet_end = data.burstlets_ends[signal_id][burstlet_id]
            tree[curr_burstlet_start:curr_burstlet_end] = {'signal_id': signal_id, 'burstlet_id': burstlet_id}
    return tree


def find_bursts(data, excluded_channels, spike_method, spike_coeff, burst_window, burst_num_channels, start, end,
                progress_callback):
    method = 'TSR'

    start_index = np.where(data.time == start * 60)[0][0]
    if end < int(np.ceil(data.time[-1] / 60)):
        end_index = np.where(data.time == end * 60)[0][0]
    else:
        end_index = np.where(data.time == data.time[-1])[0][0]

    signal_len = len(data.stream[start_index:end_index, 0])
    num_signals = data.stream.shape[1]

    if method == 'burstlet':
        if not data.burstlets:
            find_burstlets(data, excluded_channels, spike_method, spike_coeff, burst_window, start, end,
                           progress_callback)

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
            progress_callback.emit(60 + int(interval_id * 10 / (len(threshold_crossings_ids) // 2)))
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

    if method == 'TSR':
        tsr_function = data.TSR
        tsr_mean = np.mean(tsr_function)
        tsr_std = np.std(tsr_function)
        tsr_threshold = tsr_mean + 1.0 * tsr_std
        threshold_crossings = np.diff(tsr_function > tsr_threshold, prepend=False)
        threshold_crossings_ids = np.argwhere(threshold_crossings)[:, 0]
        for signal_id in range(0, num_signals):
            data.bursts_starts[signal_id] = []
            data.bursts_ends[signal_id] = []
        for interval_id in range(0, len(threshold_crossings_ids) // 2):
            progress_callback.emit(30 + int(interval_id * 10 / (len(threshold_crossings_ids) // 2)))
            interval_start = threshold_crossings_ids[interval_id * 2]
            interval_end = threshold_crossings_ids[interval_id * 2 + 1]
            if interval_end - interval_start >= burst_window / 50:
                curr_channels = []
                for interval_bin in range(interval_start, interval_end):
                    curr_channels.extend(data.TSR_channels[interval_bin])
                curr_channels = list(set(curr_channels))
                curr_channels.sort()
                for curr_channel in curr_channels:
                    data.bursts_starts[curr_channel].append(int(interval_start * 50 / (data.time[1] * 1000)))
                    data.bursts_ends[curr_channel].append(int(interval_end * 50 / (data.time[1] * 1000)))
                data.bursts.append({'start': int(interval_start * 50 / (data.time[1] * 1000)),
                                    'end': int(interval_end * 50 / (data.time[1] * 1000)),
                                    'channels': curr_channels})

        burst_activation_vector = np.empty(shape=(len(data.bursts), num_signals))
        burst_activation_vector[:] = np.nan
        burst_deactivation_vector = np.empty(shape=(len(data.bursts), num_signals))
        burst_deactivation_vector[:] = np.nan
        for burst_id in range(0, len(data.bursts)):
            curr_burst = data.bursts[burst_id]
            activation_time = curr_burst['start']
            deactivation_time = curr_burst['end']
            for signal_id in curr_burst['channels']:
                first_spike_id = np.searchsorted(data.spikes[signal_id], activation_time, 'left')
                first_spike_time = data.spikes[signal_id][first_spike_id]
                curr_activation_time = data.time[first_spike_time] - data.time[activation_time]
                burst_activation_vector[burst_id, signal_id] = curr_activation_time
                last_spike_id = np.searchsorted(data.spikes[signal_id], deactivation_time, 'left')
                last_spike_time = data.spikes[signal_id][last_spike_id - 1]
                curr_deactivation_time = data.time[deactivation_time] - data.time[last_spike_time]
                burst_deactivation_vector[burst_id, signal_id] = curr_deactivation_time

    data.burst_activation = np.zeros(num_signals)
    data.burst_deactivation = np.zeros(num_signals)
    for signal_id in range(0, num_signals):
        if signal_id not in excluded_channels:
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
        data.burst_stream[signal_id] = np.empty(len(data.stream[:, signal_id]))
        data.burst_stream[signal_id][:] = np.nan
        if data.burstlets:
            progress_callback.emit(70 + round(signal_id * 10 / num_signals))
            data.burst_borders[signal_id] = np.empty(len(data.stream[:, signal_id]))
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
                        curr_id_mod = curr_id + start_index
                        data.burst_stream[signal_id][curr_id_mod] = data.stream[curr_id_mod, signal_id]
        else:
            progress_callback.emit(40 + round(signal_id * 40 / num_signals))
            for burst_id in range(0, len(data.bursts_starts[signal_id])):
                curr_start = data.bursts_starts[signal_id][burst_id] + start_index
                curr_end = data.bursts_ends[signal_id][burst_id] + start_index
                data.burst_stream[signal_id][curr_start:curr_end] = data.stream[curr_start:curr_end, signal_id]


def calculate_characteristics(data, start, end, progress_callback):
    progress_callback.emit(80)

    start_index = np.where(data.time == start * 60)[0][0]
    if end < int(np.ceil(data.time[-1] / 60)):
        end_index = np.where(data.time == end * 60)[0][0]
    else:
        end_index = np.where(data.time == data.time[-1])[0][0]

    num_signals = data.stream.shape[1]
    num_seconds = data.time[end_index] - data.time[start_index]
    total_num_spikes = 0
    for signal_id in range(0, num_signals):
        total_num_spikes += len(data.spikes[signal_id])
    num_spikes_per_second = total_num_spikes / num_seconds
    spike_amplitudes = []
    for signal_id in range(0, num_signals):
        for spike_amplitude in data.spikes_amplitudes[signal_id]:
            spike_amplitudes.append(spike_amplitude)
    mean_spike_amplitude = np.mean(spike_amplitudes)
    std_spike_amplitude = np.std(spike_amplitudes)
    median_spike_amplitude = np.median(spike_amplitudes)
    raster_duration_sec = data.time[end_index] - data.time[start_index]
    raster_duration_ms = (data.time[end_index] - data.time[start_index]) * 1000
    total_num_bursts = len(data.bursts)
    num_bursts_per_min = total_num_bursts / (num_seconds / 60)
    time_bin = 50
    mean_num_spikes_time_bin = np.mean(data.TSR)
    std_num_spikes_time_bin = np.std(data.TSR)

    data.global_characteristics['Total number of spikes'] = total_num_spikes
    data.global_characteristics['Num spikes per second'] = num_spikes_per_second
    data.global_characteristics['Mean spike amplitude'] = mean_spike_amplitude
    data.global_characteristics['Std spike amplitude'] = std_spike_amplitude
    data.global_characteristics['Median spike amplitude'] = median_spike_amplitude
    data.global_characteristics['Raster duration in sec'] = raster_duration_sec
    data.global_characteristics['Raster duration in ms'] = raster_duration_ms
    data.global_characteristics['Total number of bursts'] = total_num_bursts
    data.global_characteristics['Num bursts per minute'] = num_bursts_per_min
    data.global_characteristics['Time bin in ms'] = time_bin
    data.global_characteristics['Mean number of spikes in time bin'] = mean_num_spikes_time_bin
    data.global_characteristics['Std number of spikes in time bin'] = std_num_spikes_time_bin

    progress_callback.emit(82)

    num_spikes = []
    for signal_id in range(0, num_signals):
        num_spikes.append(len(data.spikes[signal_id]))
    firing_rate = []
    firing_rate_ms = []
    for signal_id in range(0, num_signals):
        firing_rate.append(num_spikes[signal_id] / num_seconds)
        firing_rate_ms.append(num_spikes[signal_id] / (num_seconds * 1000))

    data.channel_characteristics['Channel'] = [i + 1 for i in range(0, num_signals)]
    data.channel_characteristics['Number of spikes'] = num_spikes
    data.channel_characteristics['Num spikes per second'] = firing_rate
    data.channel_characteristics['Num spikes per ms'] = firing_rate_ms
    data.channel_characteristics['Burst activation mean'] = data.burst_activation

    progress_callback.emit(85)

    bursts_starts = []
    bursts_ends = []
    signals = []
    num_channels = []
    num_spikes_per_burst = []
    num_bursts_per_channel = [0] * 60
    for burst_id in range(0, len(data.bursts)):
        curr_burst = data.bursts[burst_id]
        activation_time = len(data.time)
        deactivation_time = 0
        signal_list = []
        curr_num_spikes = 0
        if data.burstlets:
            for interval in curr_burst:
                if interval.begin < activation_time:
                    activation_time = interval.begin
                if interval.end > deactivation_time:
                    deactivation_time = interval.end
                signal_id = interval.data['signal_id']
                signal_list.append(signal_id + 1)
                num_bursts_per_channel[signal_id] += 1
                burstlet_id = interval.data['burstlet_id']
                curr_burstlet = data.burstlets[signal_id][burstlet_id]
                curr_num_spikes += len(curr_burstlet)
        else:
            if curr_burst['start'] < activation_time:
                activation_time = curr_burst['start']
            if curr_burst['end'] > deactivation_time:
                deactivation_time = curr_burst['end']
            signal_list = curr_burst['channels']
            for signal_id in signal_list:
                num_bursts_per_channel[signal_id] += 1
            curr_start = int(np.ceil(curr_burst['start'] * data.time[1] * 1000 / 50))
            curr_end = int(np.ceil(curr_burst['end'] * data.time[1] * 1000 / 50))
            curr_num_spikes += np.sum([data.TSR[i] for i in range(curr_start, curr_end)])
        bursts_starts.append(data.time[start_index] + data.time[activation_time])
        bursts_ends.append(data.time[start_index] + data.time[deactivation_time])
        signal_set = list(set(signal_list))
        num_channels.append(len(signal_set))
        signal_set.sort()
        signals.append('; '.join([str(item) for item in signal_set]))
        num_spikes_per_burst.append(curr_num_spikes)
    bursts_duration = []
    for burst_id in range(0, len(bursts_starts)):
        bursts_duration.append(bursts_ends[burst_id] - bursts_starts[burst_id])

    data.channel_characteristics['Num bursts'] = num_bursts_per_channel

    burst_type = []
    for burst_num_spikes in num_spikes_per_burst:
        if burst_num_spikes >= 100:
            burst_type.append('large')
        else:
            burst_type.append('small')

    data.burst_characteristics['Burst ID'] = [i + 1 for i in range(0, len(data.bursts))]
    data.burst_characteristics['Start'] = bursts_starts
    data.burst_characteristics['End'] = bursts_ends
    data.burst_characteristics['Duration'] = bursts_duration
    data.burst_characteristics['Number of spikes'] = num_spikes_per_burst
    data.burst_characteristics['Burst type'] = burst_type
    data.burst_characteristics['Number of channels'] = num_channels
    data.burst_characteristics['Channels'] = signals

    num_small_bursts = 0
    num_large_bursts = 0
    for b_type in burst_type:
        if b_type == 'small':
            num_small_bursts += 1
        else:
            num_large_bursts += 1

    data.global_characteristics['Number of small bursts'] = num_small_bursts
    data.global_characteristics['Number of large bursts'] = num_large_bursts
    data.global_characteristics['Mean burst duration'] = np.mean(bursts_duration)

    progress_callback.emit(87)

    num_minutes = num_seconds / 60
    starts = []
    finishes = []
    for time_id in range(start, int(start + num_minutes + 1)):
        starts.append(str(datetime.timedelta(seconds=time_id * 60)))
        finishes.append(str(datetime.timedelta(seconds=(time_id + 1) * 60)))
    finishes[-1] = str(datetime.timedelta(seconds=data.time[end_index]))

    num_bursts_each_minute = [0] * int(num_minutes + 1)
    for burst_start in bursts_starts:
        minute_id = int(burst_start / 60) - start
        num_bursts_each_minute[minute_id] += 1

    num_spikes_each_minute = [0] * int(num_minutes + 1)
    for signal_id in range(0, num_signals):
        for spike in data.spikes[signal_id]:
            spike_time = data.time[start_index] + data.time[spike]
            minute_id = int(spike_time / 60) - start
            num_spikes_each_minute[minute_id] += 1

    if starts[-1] == finishes[-1]:
        del starts[-1]
        del finishes[-1]
        del num_bursts_each_minute[-1]
        del num_spikes_each_minute[-1]

    data.time_characteristics['Start'] = starts
    data.time_characteristics['End'] = finishes
    data.time_characteristics['Num bursts per minute'] = num_bursts_each_minute
    data.time_characteristics['Num spikes per minute'] = num_spikes_each_minute

    progress_callback.emit(89)
