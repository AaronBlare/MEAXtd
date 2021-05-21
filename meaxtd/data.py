import numpy as np


class Data:
    def __init__(self):
        self.stream = np.empty(shape=(1, 1))
        self.time = np.empty(shape=(1, 1))
        self.spikes = {}
        self.spikes_starts = {}
        self.spikes_ends = {}
        self.spikes_amplitudes = {}
        self.spike_stream = {}
        self.burstlets = {}
        self.burstlets_starts = {}
        self.burstlets_ends = {}
        self.burstlets_amplitudes = {}
        self.burstlet_stream = {}
        self.bursts = []
        self.bursts_starts = {}
        self.bursts_ends = {}
        self.bursts_burstlets = {}
        self.burst_stream = {}
        self.burst_borders = {}
        self.global_characteristics = {}
        self.channel_characteristics = {}
        self.burst_characteristics = {}

    def clear_calculated(self):
        self.spikes = {}
        self.spikes_starts = {}
        self.spikes_ends = {}
        self.spikes_amplitudes = {}
        self.spike_stream = {}
        self.burstlets = {}
        self.burstlets_starts = {}
        self.burstlets_ends = {}
        self.burstlets_amplitudes = {}
        self.burstlet_stream = {}
        self.bursts = []
        self.bursts_starts = {}
        self.bursts_ends = {}
        self.bursts_burstlets = {}
        self.burst_stream = {}
        self.burst_borders = {}
