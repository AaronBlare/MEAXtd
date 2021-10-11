import os
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.exporters
import datetime
import json
from pathlib import Path
import cairosvg
from meaxtd.pdf_export import PDFExporter


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
        Path(path).mkdir(parents=True)

    global_df = pd.DataFrame(data=data.global_characteristics, index=[0])
    global_df.to_excel(path + 'global.xlsx', index=False)

    progress_callback.emit(91)

    channel_df = pd.DataFrame(data=data.channel_characteristics)
    channel_df.to_excel(path + 'channel.xlsx', index=False)

    progress_callback.emit(92)

    burst_df = pd.DataFrame(data=data.burst_characteristics)
    small_burst_df = burst_df.loc[burst_df['Burst type'] == 'small']
    large_burst_df = burst_df.loc[burst_df['Burst type'] == 'large']
    with pd.ExcelWriter(path + 'burst.xlsx') as writer:
        burst_df.to_excel(writer, sheet_name='all', index=False)
        small_burst_df.to_excel(writer, sheet_name='small', index=False)
        large_burst_df.to_excel(writer, sheet_name='large', index=False)

    progress_callback.emit(93)

    time_df = pd.DataFrame(data=data.time_characteristics)
    time_df.to_excel(path + 'time.xlsx', index=False)

    progress_callback.emit(94)
    return path


def save_plots_to_file(path, progress_callback, left_groupbox, right_groupbox, left_layout, right_layout):
    tsr_exporter_pdf = PDFExporter(left_layout.layout().itemAtPosition(0, 0).widget().scene())
    tsr_exporter_pdf.export(path + 'TSR.pdf')

    progress_callback.emit(95)

    plot_exporter_pdf = PDFExporter(left_layout.layout().itemAtPosition(1, 0).widget().scene())
    plot_exporter_pdf.export(path + 'plot.pdf')

    progress_callback.emit(96)

    act_exporter_pdf = PDFExporter(right_layout.layout().itemAtPosition(0, 0).widget().scene())
    act_exporter_pdf.export(path + 'activation.pdf', add_margin=True)

    progress_callback.emit(97)

    deact_exporter_pdf = PDFExporter(right_layout.layout().itemAtPosition(1, 0).widget().scene())
    deact_exporter_pdf.export(path + 'deactivation.pdf', add_margin=True)

    progress_callback.emit(97)

    tsr_exporter_png = pg.exporters.ImageExporter(left_groupbox.layout().itemAtPosition(0, 0).widget().scene())
    tsr_exporter_png.export(path + 'TSR.png')

    plot_exporter_png = pg.exporters.ImageExporter(left_groupbox.layout().itemAtPosition(1, 0).widget().scene())
    plot_exporter_png.export(path + 'plot.png')

    act_exporter_png = pg.exporters.ImageExporter(right_groupbox.layout().itemAtPosition(0, 0).widget().scene())
    act_exporter_png.export(path + 'activation.png')

    deact_exporter_png = pg.exporters.ImageExporter(right_groupbox.layout().itemAtPosition(1, 0).widget().scene())
    deact_exporter_png.export(path + 'deactivation.png')

    # tsr_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(0, 0).widget().scene())
    # tsr_exporter_svg.export(path + 'TSR.svg')

    # tsr_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(0, 0).widget().scene())
    # tsr_svg = tsr_exporter_svg.export(toBytes=True)
    # tsr_pdf = cairosvg.svg2pdf(tsr_svg, write_to=path + 'TSR.pdf')

    # plot_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(1, 0).widget().scene())
    # plot_exporter_svg.export(path + 'plot.svg')

    # plot_exporter_svg = pg.exporters.SVGExporter(left_layout.layout().itemAtPosition(1, 0).widget().scene())
    # plot_svg = plot_exporter_svg.export(toBytes=True)
    # plot_pdf = cairosvg.svg2pdf(plot_svg, write_to=path + 'plot.pdf')

    # act_exporter_svg = pg.exporters.SVGExporter(right_layout.layout().itemAtPosition(0, 0).widget().scene())
    # act_exporter_svg.export(path + 'activation.svg')

    # act_exporter_svg = pg.exporters.SVGExporter(right_groupbox.layout().itemAtPosition(0, 0).widget().scene())
    # act_svg = act_exporter_svg.export(toBytes=True)
    # act_pdf = cairosvg.svg2pdf(act_svg, write_to=path + 'activation.pdf')

    # deact_exporter_svg = pg.exporters.SVGExporter(right_layout.layout().itemAtPosition(1, 0).widget().scene())
    # deact_exporter_svg.export(path + 'deactivation.svg')

    # deact_exporter_svg = pg.exporters.SVGExporter(right_groupbox.layout().itemAtPosition(1, 0).widget().scene())
    # deact_svg = deact_exporter_svg.export(toBytes=True)
    # deact_pdf = cairosvg.svg2pdf(deact_svg, write_to=path + 'deactivation.pdf')

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

    with open(path + 'params.json', 'w') as f:
        json.dump(params_dict, f)

    progress_callback.emit(100)


def save_graph_to_file(path, progress_callback, graph, hub, burst_id):
    path = f"{path}/graph/"
    if not os.path.isdir(path):
        Path(path).mkdir(parents=True)

    graph.draw(path + 'graph_burst_' + str(burst_id + 1) + '.png')
    graph.draw(path + 'graph_burst_' + str(burst_id + 1) + '.pdf')
    graph.draw(path + 'graph_burst_' + str(burst_id + 1) + '.dot')

    hub_df = pd.DataFrame(data=hub)
    hub_df.to_excel(path + 'hubs_burst_' + str(burst_id + 1) + '.xlsx', index=False)

    progress_callback.emit(100)

    return path + 'graph_burst_' + str(burst_id + 1) + '.png'
