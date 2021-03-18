import numpy as np


class Data:
    def __init__(self):
        self.stream = np.empty(shape=(1, 1))
        self.time = np.empty(shape=(1, 1))
        self.spikes = {}
        self.spikes_amplitudes = {}
        self.spikes_starts = {}
        self.spikes_ends = {}
        self.bursts = {}
