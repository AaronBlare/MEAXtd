import os
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.exporters
import datetime
import json


def save_tables_to_file(data, filepath, progress_callback):
    path = filepath[:-3]
    date_time = datetime.datetime.now()
    curr_date = date_time.date()
    curr_time = date_time.time()
    curr_hour = str(curr_time.hour)
    curr_minute = str(curr_time.minute)
    curr_second = str(curr_time.second)
    if len(str(curr_time.hour)) == 1:
        curr_hour = f"0{str(curr_time.hour)}"
    if len(str(curr_time.minute)) == 1:
        curr_minute = f"0{str(curr_time.minute)}"
    if len(str(curr_time.second)) == 1:
        curr_second = f"0{str(curr_time.second)}"
    suffix = f"{str(curr_date)}_{curr_hour}-{curr_minute}-{curr_second}"
    path = f"{path}/{suffix}/"
    if not os.path.isdir(path):
        os.mkdir(path)

    global_df = pd.DataFrame(data=data.global_characteristics, index=[0])
    global_df.to_excel(path + 'global.xlsx', index=False)

    progress_callback.emit(91)

    channel_df = pd.DataFrame(data=data.channel_characteristics)
    channel_df.to_excel(path + 'channel.xlsx', index=False)

    progress_callback.emit(92)

    burst_df = pd.DataFrame(data=data.burst_characteristics)
    burst_df.to_excel(path + 'burst.xlsx', index=False)

    progress_callback.emit(93)

    time_df = pd.DataFrame(data=data.time_characteristics)
    time_df.to_excel(path + 'time.xlsx', index=False)

    progress_callback.emit(94)
    return path


def save_plots_to_file(path, progress_callback, left_groupbox, right_groupbox, left_layout, right_layout):

    # tsr_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(0, 0).widget().getPlotItem())
    # tsr_exporter_svg.export(path + 'TSR.svg')

    tsr_exporter_png = pg.exporters.ImageExporter(left_groupbox.layout().itemAtPosition(0, 0).widget().getPlotItem())
    tsr_exporter_png.export(path + 'TSR.png')

    progress_callback.emit(95)

    # plot_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(1, 0).widget().getPlotItem())
    # plot_exporter_svg.export(path + 'plot.svg')

    plot_exporter_png = pg.exporters.ImageExporter(left_groupbox.layout().itemAtPosition(1, 0).widget().getPlotItem())
    plot_exporter_png.export(path + 'plot.png')

    progress_callback.emit(96)

    # act_exporter_svg = pg.exporters.SVGExporter(right_layout.layout().itemAtPosition(0, 0).widget().getPlotItem())
    # act_exporter_svg.export(path + 'activation.svg')

    act_exporter_png = pg.exporters.ImageExporter(right_groupbox.layout().itemAtPosition(0, 0).widget().getPlotItem())
    act_exporter_png.export(path + 'activation.png')

    progress_callback.emit(99)

    # deact_exporter_svg = pg.exporters.SVGExporter(right_layout.layout().itemAtPosition(1, 0).widget().getPlotItem())
    # deact_exporter_svg.export(path + 'deactivation.svg')

    deact_exporter_png = pg.exporters.ImageExporter(right_groupbox.layout().itemAtPosition(1, 0).widget().getPlotItem())
    deact_exporter_png.export(path + 'deactivation.png')

    progress_callback.emit(98)

    # pixmap = QPixmap.grabWidget(left_groupbox)
    # pixmap.save(path + 'tsr_plot.png', 'png')
    # left_layout.layout().itemAtPosition(0, 0).widget().getPlotItem().showAxis('bottom')


def save_params_to_file(path, progress_callback, params_dict):

    f = open(path + 'params.txt', 'w')
    f.write('Parameter\tValue\n')
    for key in params_dict:
        if isinstance(params_dict[key], list):
            f.write(f"{key}\t{', '.join([str(elem) for elem in params_dict[key]])}\n")
        else:
            f.write(f'{key}\t{str(params_dict[key])}\n')
    f.close()

    progress_callback.emit(99)

    with open(path + 'params.json', 'w') as f:
        json.dump(params_dict, f)

    progress_callback.emit(100)
