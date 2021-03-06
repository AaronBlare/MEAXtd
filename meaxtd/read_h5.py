import McsPy.McsData
import McsPy.McsCMOS
import numpy as np
from McsPy import ureg, Q_
from meaxtd.data import Data


def read_h5_file(data_path, progress_callback):

    progress_callback.emit(0)

    channel_raw_data = McsPy.McsData.RawData(data_path)

    progress_callback.emit(10)

    fs = int(channel_raw_data.recordings[0].analog_streams[0].channel_infos[0].sampling_frequency.magnitude)
    analog_stream_0 = channel_raw_data.recordings[0].analog_streams[0]
    analog_stream_0_data = analog_stream_0.channel_data

    progress_callback.emit(25)

    np_analog_stream_0_data = np.transpose(analog_stream_0_data)

    progress_callback.emit(50)

    stream = channel_raw_data.recordings[0].analog_streams[0]
    time = stream.get_channel_sample_timestamps(0, 0)
    scale_factor_for_second = Q_(1, time[1]).to(ureg.s).magnitude
    time_in_sec = time[0] * scale_factor_for_second

    progress_callback.emit(75)

    data = Data()
    data.stream = np_analog_stream_0_data / 1000000
    data.time = np.asarray(time_in_sec)
    data.fs = fs

    progress_callback.emit(100)

    return data
