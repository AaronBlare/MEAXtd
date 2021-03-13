from scipy.signal import find_peaks
import numpy as np


def find_spikes(data):
    signals = data.stream
    time = data.time
    num_signals = signals.shape[1]
    for signal_id in range(0, num_signals):
        peaks, properties = find_peaks(signals[:, signal_id], height=0)
        curr_std_val = np.std(signals[:, signal_id])
        spikes = []
        for peak_id in range(0, len(peaks)):
            if properties['peak_heights'][peak_id] > 5.0 * curr_std_val:
                spikes.append(peaks[peak_id])
        data.spikes[signal_id] = np.asarray(spikes)
        data.spikes_amplitudes[signal_id] = np.take(signals[:, signal_id], spikes)
