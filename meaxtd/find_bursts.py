from scipy.signal import find_peaks
import numpy as np


def find_spikes(data):
    signals = data.stream
    num_signals = signals.shape[1]
    for signal_id in range(0, num_signals):
        peaks, properties = find_peaks(signals[:, signal_id], height=0)
        curr_std_val = np.std(signals[:, signal_id])
        curr_rms_val = np.sqrt(np.mean(signals[:, signal_id] ** 2))
        spikes = []
        spike_amplitude = []
        spike_start = []
        spike_end = []
        for peak_id in range(0, len(peaks)):
            if properties['peak_heights'][peak_id] > 5.0 * curr_rms_val:
                curr_spike = peaks[peak_id]
                spikes.append(curr_spike)
                curr_id = curr_spike
                while signals[:, signal_id][curr_id - 1] < signals[:, signal_id][curr_id] and curr_id > 0:
                    curr_id -= 1
                spike_start.append(curr_id)
                curr_id = curr_spike
                while signals[:, signal_id][curr_id + 1] < signals[:, signal_id][curr_id] and curr_id + 1 < len(
                        signals[:, signal_id]) - 1:
                    curr_id += 1
                spike_end.append(curr_id + 1)
                curr_spike_amplitude = max(signals[:, signal_id][spike_start[-1]:spike_end[-1]]) - min(
                    signals[:, signal_id][spike_start[-1]:spike_end[-1]])
                spike_amplitude.append(curr_spike_amplitude)
        data.spikes[signal_id] = np.asarray(spikes)
        data.spikes_starts[signal_id] = np.asarray(spike_start)
        data.spikes_ends[signal_id] = np.asarray(spike_end)
        data.spikes_amplitudes[signal_id] = np.asarray(spike_amplitude)

        data.spike_stream[signal_id] = np.empty(len(signals[:, signal_id]))
        data.spike_stream[signal_id][:] = np.nan
        for peak_id in range(0, len(spikes)):
            for curr_id in range(spike_start[peak_id], spike_end[peak_id] + 1):
                data.spike_stream[signal_id][curr_id] = signals[curr_id, signal_id]


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
