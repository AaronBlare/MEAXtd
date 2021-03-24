import numpy as np


class Data:
    def __init__(self):
        self.stream = np.empty(shape=(1, 1))
        self.time = np.empty(shape=(1, 1))
        self.spikes = {}
        self.spikes_starts = {}
        self.spikes_ends = {}
        self.spike_stream = {}
        self.burstlets = {}
        self.burstlets_starts = {}
        self.burstlets_ends = {}
        self.burstlet_stream = {}
