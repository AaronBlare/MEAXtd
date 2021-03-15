from scipy.signal import find_peaks
import numpy as np


def find_spikes(data):
    signals = data.stream
    time = data.time
    num_signals = signals.shape[1]
    for signal_id in range(0, num_signals):
        peaks, properties = find_peaks(signals[:, signal_id], height=0)
        curr_std_val = np.std(signals[:, signal_id])
        curr_rms_val = np.sqrt(np.mean(signals[:, signal_id]**2))
        spikes = []
        for peak_id in range(0, len(peaks)):
            if properties['peak_heights'][peak_id] > 5.0 * curr_rms_val:
                spikes.append(peaks[peak_id])
        data.spikes[signal_id] = np.asarray(spikes)
        data.spikes_amplitudes[signal_id] = np.take(signals[:, signal_id], spikes)


def find_bursts(data):
    if not data.spikes:
        find_spikes(data)
    signals = data.stream
    time = data.time
    spikes = data.spikes
    num_signals = signals.shape[1]
    window = 100 * 10  # 100 ms
    for signal_id in range(0, num_signals):
        data.bursts[signal_id] = []
        num_spikes = len(spikes[signal_id])
        curr_burst = []
        for spike_id in range(0, num_spikes - 1):
            if spikes[signal_id][spike_id + 1] - spikes[signal_id][spike_id] < window:
                curr_burst.append(spikes[signal_id][spike_id])
            else:
                if len(curr_burst) >= 5:
                    curr_burst.append(spikes[signal_id][spike_id])
                    data.bursts[signal_id].append(curr_burst)
                curr_burst = []
