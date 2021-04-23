import sys
import traceback
import pkg_resources
import pyqtgraph as pg
from meaxtd.read_h5 import read_h5_file
from meaxtd.hdf5plot import HDF5PlotXY
from meaxtd.find_bursts import find_spikes, find_bursts
from meaxtd.stat_plots import raster_plot
from PySide2.QtCore import Qt, QRunnable, Slot, QThreadPool, QObject, Signal
from PySide2.QtGui import QIcon, QFont
from PySide2.QtWidgets import (QAction, QApplication, QDialog, QFileDialog, QLayout, QFrame, QSizePolicy,
                               QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget, QTabWidget, QLineEdit,
                               QGroupBox, QGridLayout, QPushButton, QComboBox, QRadioButton, QPlainTextEdit,
                               QProgressBar)


class WorkerSignals(QObject):
    """
        Defines the signals available from a running worker thread.

        Supported signals are:

            finished
                No data

            error
                tuple (exctype, value, traceback.format_exc() )

            result
                object data returned from processing, anything

            progress
                int indicating % progress

    """
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    """
        Worker thread

        Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

        :param callback: The function callback to run on this worker thread. Supplied args and
                         kwargs will be passed through to the runner.
        :type callback: function
        :param args: Arguments to pass to the callback function
        :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @Slot()  # QtCore.Slot
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class MEAXtd(QMainWindow):
    """Create the main window that stores all of the widgets necessary for the application."""

    def __init__(self, rect, parent=None):
        """Initialize the components of the main window."""
        super(MEAXtd, self).__init__(parent)
        self.setWindowTitle('MEAXtd')
        window_icon = pkg_resources.resource_filename('meaxtd.images',
                                                      'ic_insert_drive_file_black_48dp_1x.png')
        self.setWindowIcon(QIcon(window_icon))
        self.av_width = rect.width()
        self.av_height = rect.height()
        self.resize(int(self.av_width * 0.9), int(self.av_height * 0.75))

        self.menu_bar = self.menuBar()
        self.about_dialog = AboutDialog()
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('Ready')
        self.file_menu()
        self.help_menu()

        self.central_widget = QWidget(self)
        central_sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        central_sizePolicy.setHorizontalStretch(0)
        central_sizePolicy.setVerticalStretch(0)
        central_flag = self.central_widget.sizePolicy().hasHeightForWidth()
        central_sizePolicy.setHeightForWidth(central_flag)
        self.central_widget.setSizePolicy(central_sizePolicy)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setSizeConstraint(QLayout.SetNoConstraint)

        self.tabs = QTabWidget(self.central_widget)

        self.main_tab = QWidget()
        self.main_tab_upper_layout = QVBoxLayout(self.main_tab)
        self.create_upper_layout()
        self.create_bottom_layout()

        self.plot_tab = QWidget()
        self.plot = PlotDialog()
        self.plot_tab.layout = QVBoxLayout(self)
        self.plot_tab.layout.addWidget(self.plot.horizontalGroupBox)
        self.plot_tab.layout.addWidget(self.plot.buttonGroupBox)
        self.plot_tab.setLayout(self.plot_tab.layout)

        self.stat_tab = QWidget()
        self.stat = StatDialog()
        self.stat_tab.layout = QVBoxLayout(self)
        self.stat_tab.layout.addWidget(self.stat.horizontalGroupBox)
        self.stat_tab.setLayout(self.stat_tab.layout)

        self.tabs.addTab(self.main_tab, "Main")
        self.tabs.addTab(self.plot_tab, "Plot")
        self.tabs.addTab(self.stat_tab, "Stat")

        self.main_layout.addWidget(self.tabs)
        self.setCentralWidget(self.central_widget)
        self.center()

        self.threadpool = QThreadPool()

    def center(self):
        frame_gm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        center_point = QApplication.desktop().screenGeometry(screen).center()
        frame_gm.moveCenter(center_point)
        self.move(frame_gm.topLeft())

    def file_menu(self):
        """Create a file submenu with an Open File item that opens a file dialog."""
        self.file_sub_menu = self.menu_bar.addMenu('File')

        self.open_action = QAction('Open File', self)
        self.open_action.setStatusTip('Open a file into MEAXtd.')
        self.open_action.setShortcut('CTRL+O')
        self.open_action.triggered.connect(lambda: self.open_file())

        self.exit_action = QAction('Exit Application', self)
        self.exit_action.setStatusTip('Exit the application.')
        self.exit_action.setShortcut('CTRL+Q')
        self.exit_action.triggered.connect(lambda: QApplication.quit())

        self.file_sub_menu.addAction(self.open_action)
        self.file_sub_menu.addAction(self.exit_action)

    def help_menu(self):
        """Create a help submenu with an About item tha opens an about dialog."""
        self.help_sub_menu = self.menu_bar.addMenu('Help')

        self.about_action = QAction('About', self)
        self.about_action.setStatusTip('About the application.')
        self.about_action.setShortcut('CTRL+H')
        self.about_action.triggered.connect(lambda: self.about_dialog.exec_())

        self.help_sub_menu.addAction(self.about_action)

    def read_h5_data(self, filename):
        data = read_h5_file(filename)
        return data

    def set_data(self, data):
        self.data = data

    def configure_buttons_after_open(self):
        if self.data:
            self.processqbtn.setEnabled(True)
            self.plot.set_data(self.data)
            self.stat.set_data(self.data)
            self.plot.plot_signals()

    def open_file(self):
        """Open a QFileDialog to allow the user to open a file into the application."""
        filename, accepted = QFileDialog.getOpenFileName(self, 'Open File', filter="*.h5")

        if accepted:
            worker = Worker(self.read_h5_data, filename=filename)
            worker.signals.result.connect(self.set_data)
            worker.signals.finished.connect(self.configure_buttons_after_open)
            self.threadpool.start(worker)

    def create_upper_layout(self):
        self.main_tab_upper_groupbox = QGroupBox(self.main_tab)
        self.main_tab_upper_groupbox_layout = QHBoxLayout(self.main_tab_upper_groupbox)

        # Frame for Load and Process buttons
        self.frame = QFrame(self.main_tab_upper_groupbox)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.main_tab_button_layout = QVBoxLayout(self.frame)
        self.main_tab_button_layout.setContentsMargins(70, 50, 70, 50)
        self.load_button()
        self.process_button()
        self.main_tab_upper_groupbox_layout.addWidget(self.frame)

        # Spike Parameters Groupbox
        self.spike_params_groupbox = QGroupBox(self.main_tab_upper_groupbox, title="Spike Parameters")

        self.gbox_font = QFont()
        self.gbox_font.setPointSize(18)

        self.spike_params_groupbox.setFont(self.gbox_font)
        self.spike_grid_layout = QGridLayout(self.spike_params_groupbox)
        self.spike_grid_layout.setContentsMargins(50, 20, 50, 20)

        self.spike_method_label = QLabel(self.spike_params_groupbox, text="Method")
        self.spike_grid_layout.addWidget(self.spike_method_label, 0, 0, 1, 1)

        self.spike_method_combobox = QComboBox(self.spike_params_groupbox)
        self.size_policy1 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        self.size_policy1.setHorizontalStretch(0)
        self.size_policy1.setVerticalStretch(0)
        policy_flag = self.spike_method_combobox.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.spike_method_combobox.setSizePolicy(self.size_policy1)
        self.spike_grid_layout.addWidget(self.spike_method_combobox, 0, 1, 1, 1)

        self.spike_coeff_label = QLabel(self.spike_params_groupbox, text="Coefficient")
        self.spike_grid_layout.addWidget(self.spike_coeff_label, 1, 0, 1, 1)

        self.spike_coeff = QLineEdit(self.spike_params_groupbox)
        policy_flag = self.spike_coeff.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.spike_coeff.setSizePolicy(self.size_policy1)
        self.spike_grid_layout.addWidget(self.spike_coeff, 1, 1, 1, 1)

        self.main_tab_upper_groupbox_layout.addWidget(self.spike_params_groupbox)

        # Burst Parameters Groupbox
        self.burst_param_groupbox = QGroupBox(self.main_tab_upper_groupbox, title="Burst Parameters")
        self.burst_param_groupbox.setFont(self.gbox_font)
        self.burst_grid_layout = QGridLayout(self.burst_param_groupbox)
        self.burst_grid_layout.setContentsMargins(50, 20, 50, 20)

        self.burst_window_label = QLabel(self.burst_param_groupbox, text="Window size, ms")
        self.burst_grid_layout.addWidget(self.burst_window_label, 0, 0, 1, 1)

        self.burst_window_size = QLineEdit(self.burst_param_groupbox)
        policy_flag = self.burst_window_size.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.burst_window_size.setSizePolicy(self.size_policy1)
        self.burst_grid_layout.addWidget(self.burst_window_size, 0, 1, 1, 1)

        self.burst_num_channels_label = QLabel(self.burst_param_groupbox, text="Num channels")
        self.burst_grid_layout.addWidget(self.burst_num_channels_label, 1, 0, 1, 1)

        self.burst_num_channels = QLineEdit(self.burst_param_groupbox)
        policy_flag = self.burst_num_channels.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.burst_num_channels.setSizePolicy(self.size_policy1)
        self.burst_grid_layout.addWidget(self.burst_num_channels, 1, 1, 1, 1)

        self.main_tab_upper_groupbox_layout.addWidget(self.burst_param_groupbox)
        self.main_tab_upper_layout.addWidget(self.main_tab_upper_groupbox)

    def load_button(self):
        self.loadqbtn = QPushButton(self.frame, text='Load File')
        self.sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.sizePolicy.setHorizontalStretch(0)
        self.sizePolicy.setVerticalStretch(0)
        self.sizePolicy.setHeightForWidth(self.loadqbtn.sizePolicy().hasHeightForWidth())
        self.loadqbtn.setSizePolicy(self.sizePolicy)

        self.btn_font = QFont()
        self.btn_font.setPointSize(25)

        self.loadqbtn.setFont(self.btn_font)
        self.main_tab_button_layout.addWidget(self.loadqbtn)
        self.loadqbtn.clicked.connect(lambda: self.open_file())

    def process_button(self):
        self.processqbtn = QPushButton(self.frame, text='Process')
        self.sizePolicy.setHeightForWidth(self.processqbtn.sizePolicy().hasHeightForWidth())
        self.processqbtn.setSizePolicy(self.sizePolicy)
        self.processqbtn.setFont(self.btn_font)
        self.processqbtn.setEnabled(False)
        self.main_tab_button_layout.addWidget(self.processqbtn)
        self.processqbtn.clicked.connect(lambda: self.process())

    def process_spikes(self):
        if not self.data.spikes:
            find_spikes(self.data)

    def configure_buttons_after_spike(self):
        if self.data.spikes:
            self.plot.signalrbtn.setCheckable(True)
            self.plot.signalrbtn.setChecked(True)
            self.plot.spikerbtn.setCheckable(True)
            self.stat.plot_raster()

    def process_bursts(self):
        if not self.data.bursts:
            find_bursts(self.data)

    def configure_buttons_after_burst(self):
        if self.data.bursts:
            self.plot.signalrbtn.setCheckable(True)
            self.plot.signalrbtn.setChecked(True)
            self.plot.spikerbtn.setCheckable(True)
            self.plot.burstletrbtn.setCheckable(True)
            self.plot.burstrbtn.setCheckable(True)

    def process(self):
        worker = Worker(self.process_spikes)
        worker.signals.finished.connect(self.configure_buttons_after_spike)
        self.threadpool.start(worker)

        worker = Worker(self.process_bursts)
        worker.signals.finished.connect(self.configure_buttons_after_burst)
        self.threadpool.start(worker)

    def create_param_groupbox(self):
        self.param_layout = QHBoxLayout(self.main_tab_param_widget)
        self.param_groupbox = QGroupBox(self.main_tab_param_widget, title="Parameters")
        self.gbox_font = QFont()
        self.gbox_font.setPointSize(18)
        self.param_groupbox.setFont(self.gbox_font)
        self.param_layout.addWidget(self.param_groupbox)

    def create_bottom_layout(self):
        self.main_tab_bottom_groupbox = QGroupBox(self.main_tab)
        self.main_tab_bottom_groupbox.setFont(self.gbox_font)
        self.log_groupbox_layout = QVBoxLayout(self.main_tab_bottom_groupbox)

        self.log_window = QPlainTextEdit(self.main_tab_bottom_groupbox)
        self.size_policy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.size_policy2.setHorizontalStretch(0)
        self.size_policy2.setVerticalStretch(0)
        size_policy_flag = self.log_window.sizePolicy().hasHeightForWidth()
        self.size_policy2.setHeightForWidth(size_policy_flag)
        self.log_window.setSizePolicy(self.size_policy2)
        self.log_groupbox_layout.addWidget(self.log_window)

        self.progressBar = QProgressBar(self.main_tab_bottom_groupbox)
        self.progressBar.setValue(10)
        self.log_groupbox_layout.addWidget(self.progressBar)

        self.main_tab_upper_layout.addWidget(self.main_tab_bottom_groupbox)


class AboutDialog(QDialog):
    """Create the necessary elements to show helpful text in a dialog."""

    def __init__(self, parent=None):
        """Display a dialog that shows application information."""
        super(AboutDialog, self).__init__(parent)

        self.setWindowTitle('About')
        help_icon = pkg_resources.resource_filename('meaxtd.images',
                                                    'ic_help_black_48dp_1x.png')
        self.setWindowIcon(QIcon(help_icon))
        self.resize(300, 200)

        author = QLabel('Aaron Blare')
        author.setAlignment(Qt.AlignCenter)

        icons = QLabel('Material design icons created by Google')
        icons.setAlignment(Qt.AlignCenter)

        github = QLabel('GitHub: AaronBlare')
        github.setAlignment(Qt.AlignCenter)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignVCenter)

        self.layout.addWidget(author)
        self.layout.addWidget(icons)
        self.layout.addWidget(github)

        self.setLayout(self.layout)


class PlotDialog(QDialog):

    def __init__(self, data=None):
        super().__init__()
        self.data = data
        self.init_ui()

    def set_data(self, data):
        self.data = data

    def init_ui(self):
        self.create_grid_layout()
        self.create_button_layout()

    def create_grid_layout(self):
        self.horizontalGroupBox = QGroupBox()
        layout = QGridLayout()

        num_rows = 10
        num_columns = 6

        plots = []

        for row_id in range(0, num_rows):
            layout.setColumnStretch(row_id, num_columns)

        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                curr_plot = pg.PlotWidget(title='#' + str(curr_id + 1))
                curr_plot.enableAutoRange(False, False)
                curr_plot.setXRange(0, 1)
                curr_plot.setYRange(-0.002, 0.002)
                curr_plot.setLabel('left', 'Voltage (μV)')
                curr_plot.setLabel('bottom', 'Time (s)')
                if self.data:
                    curve = HDF5PlotXY()
                    curr_data = self.data.stream[:, curr_id]
                    curr_time = self.data.time
                    curve.setHDF5(curr_time, curr_data, self.data.fs)
                    curr_plot.addItem(curve)
                layout.addWidget(curr_plot, col_id, row_id)
                plots.append(curr_plot)
                if curr_id > 0:
                    plots[curr_id - 1].getViewBox().setXLink(plots[curr_id])
                    plots[curr_id - 1].getViewBox().setYLink(plots[curr_id])

        self.horizontalGroupBox.setLayout(layout)

    def create_button_layout(self):
        self.buttonGroupBox = QGroupBox()
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()

        self.signalrbtn = QRadioButton('Signal')
        self.signalrbtn.setChecked(True)
        self.signalrbtn.toggled.connect(lambda: self.remove_data())
        buttonLayout.addWidget(self.signalrbtn)

        self.spikerbtn = QRadioButton('Spike')
        self.spikerbtn.toggled.connect(lambda: self.add_spike_data())
        buttonLayout.addWidget(self.spikerbtn)

        self.burstletrbtn = QRadioButton('Burstlet')
        self.burstletrbtn.toggled.connect(lambda: self.add_burstlet_data())
        buttonLayout.addWidget(self.burstletrbtn)

        self.burstrbtn = QRadioButton('Burst')
        self.burstrbtn.toggled.connect(lambda: self.add_burst_data())
        buttonLayout.addWidget(self.burstrbtn)

        if not self.data:
            self.signalrbtn.setCheckable(False)
            self.spikerbtn.setCheckable(False)
            self.burstletrbtn.setCheckable(False)
            self.burstrbtn.setCheckable(False)

        self.signalComboBox = QComboBox()
        signal_numbers = list(range(1, 61))
        self.signalComboBox.addItems([str(num) for num in signal_numbers])
        buttonLayout.addWidget(self.signalComboBox)

        self.prevqbtn = QPushButton('<', self)
        self.prevqbtn.setEnabled(True)
        if self.signalrbtn.isChecked():
            self.prevqbtn.setEnabled(False)
        buttonLayout.addWidget(self.prevqbtn)
        self.prevqbtn.clicked.connect(lambda: self.change_range_backward())

        self.nextqbtn = QPushButton('>', self)
        self.nextqbtn.setEnabled(True)
        if self.signalrbtn.isChecked():
            self.nextqbtn.setEnabled(False)
        buttonLayout.addWidget(self.nextqbtn)
        self.nextqbtn.clicked.connect(lambda: self.change_range_forward())

        buttonLayout.addStretch()
        self.buttonGroupBox.setLayout(buttonLayout)

    def plot_signals(self):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                curve = HDF5PlotXY()
                curr_data = self.data.stream[:, curr_id]
                curve.setHDF5(self.data.time, curr_data, self.data.fs)
                self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(curve)

    def remove_data(self):
        if self.signalrbtn.isChecked():
            self.prevqbtn.setEnabled(False)
            self.nextqbtn.setEnabled(False)
        elif self.spikerbtn.isChecked() or self.burstletrbtn.isChecked() or self.burstrbtn.isChecked():
            self.prevqbtn.setEnabled(True)
            self.nextqbtn.setEnabled(True)
        if getattr(self, 'spike_id', None) is not None:
            self.spike_id = None
        if getattr(self, 'burstlet_id', None) is not None:
            self.burstlet_id = None
        if getattr(self, 'burst_id', None) is not None:
            self.burst_id = None
        curr_curves = self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().plotItem.curves
        if len(curr_curves) > 1:
            num_rows = 10
            num_columns = 6
            for curve_id in range(1, len(curr_curves)):
                for col_id in range(0, num_columns):
                    for row_id in range(0, num_rows):
                        curr_plot_item = self.horizontalGroupBox.layout().itemAtPosition(col_id,
                                                                                         row_id).widget().plotItem
                        curr_plot_item.removeItem(curr_plot_item.curves[curve_id])

    def add_spike_data(self):
        if self.spikerbtn.isChecked():
            self.remove_data()
            num_rows = 10
            num_columns = 6
            for col_id in range(0, num_columns):
                for row_id in range(0, num_rows):
                    curr_id = col_id * num_rows + row_id
                    spikes = HDF5PlotXY()
                    curr_spike_data = self.data.spike_stream[curr_id]
                    spikes.setHDF5(self.data.time, curr_spike_data, self.data.fs, pen=pg.mkPen(color='y', width=2))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(spikes)

    def add_burstlet_data(self):
        if self.burstletrbtn.isChecked():
            self.remove_data()
            num_rows = 10
            num_columns = 6
            for col_id in range(0, num_columns):
                for row_id in range(0, num_rows):
                    curr_id = col_id * num_rows + row_id
                    burstlets = HDF5PlotXY()
                    curr_burstlet_data = self.data.burstlet_stream[curr_id]
                    burstlets.setHDF5(self.data.time, curr_burstlet_data, self.data.fs,
                                      pen=pg.mkPen(color='g', width=2))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(burstlets)

    def add_burst_data(self):
        if self.burstrbtn.isChecked():
            self.remove_data()
            num_rows = 10
            num_columns = 6
            for col_id in range(0, num_columns):
                for row_id in range(0, num_rows):
                    curr_id = col_id * num_rows + row_id
                    bursts = HDF5PlotXY()
                    curr_burst_data = self.data.burst_stream[curr_id]
                    bursts.setHDF5(self.data.time, curr_burst_data, self.data.fs,
                                   pen=pg.mkPen(color='b', width=2))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(bursts)
                    bursts_borders = HDF5PlotXY()
                    curr_burst_borders = self.data.burst_borders[curr_id]
                    bursts_borders.setHDF5(self.data.time, curr_burst_borders, self.data.fs,
                                           pen=pg.mkPen(color='r', width=1.5))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(bursts_borders)

    def change_range_forward(self):
        if self.spikerbtn.isChecked():
            if getattr(self, 'spike_id', None) is None:
                self.spike_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_spike = self.data.spikes[curr_signal][self.spike_id]
            curr_spike_amplitude = self.data.spikes_amplitudes[curr_signal][self.spike_id]
            if self.spike_id < len(self.data.spikes[curr_signal]) - 1:
                self.spike_id += 1
            left_border = max(0, self.data.time[curr_spike] - 0.5)
            right_border = min(len(self.data.time), self.data.time[curr_spike] + 0.5)
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            if curr_spike_amplitude > 0.004:
                top_border = max(0.002, curr_spike_amplitude / 2 + 0.0001)
                bottom_border = min(-0.002, curr_spike_amplitude / 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstletrbtn.isChecked():
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id]
            curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id]
            curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id]
            if self.burstlet_id < len(self.data.burstlets[curr_signal]) - 1:
                self.burstlet_id += 1
            curr_burstlet_len = self.data.time[curr_burstlet_end] - self.data.time[curr_burstlet_start]
            if curr_burstlet_len > 1:
                left_border = self.data.time[curr_burstlet_start] - 0.1
                right_border = self.data.time[curr_burstlet_end] + 0.1
            else:
                left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) / 2
                right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) / 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
            if curr_burstlet_amplitude > 0.004:
                top_border = max(0.002, curr_burstlet_amplitude / 2 + 0.0001)
                bottom_border = min(-0.002, curr_burstlet_amplitude / 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstrbtn.isChecked():
            if getattr(self, 'burst_id', None) is None:
                self.burst_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burst_start = self.data.bursts_starts[curr_signal][self.burst_id]
            curr_burst_end = self.data.bursts_ends[curr_signal][self.burst_id]
            if self.burst_id < len(self.data.bursts) - 1:
                self.burst_id += 1
            curr_burst_len = self.data.time[curr_burst_end] - self.data.time[curr_burst_start]
            if curr_burst_len > 1:
                left_border = self.data.time[curr_burst_start] - 0.1
                right_border = self.data.time[curr_burst_end] + 0.1
            else:
                left_border = self.data.time[curr_burst_start] - (1 - curr_burst_len) / 2
                right_border = self.data.time[curr_burst_end] + (1 - curr_burst_len) / 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)

    def change_range_backward(self):
        if self.spikerbtn.isChecked():
            if getattr(self, 'spike_id', None) is None:
                self.spike_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_spike = self.data.spikes[curr_signal][self.spike_id]
            curr_spike_amplitude = self.data.spikes_amplitudes[curr_signal][self.spike_id]
            if self.spike_id > 0:
                self.spike_id -= 1
            left_border = max(0, self.data.time[curr_spike] - 0.5)
            right_border = min(len(self.data.time), self.data.time[curr_spike] + 0.5)
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            if curr_spike_amplitude > 0.004:
                top_border = max(0.002, curr_spike_amplitude / 2 + 0.0001)
                bottom_border = min(-0.002, curr_spike_amplitude / 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstletrbtn.isChecked():
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id]
            curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id]
            curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id]
            if self.burstlet_id > 0:
                self.burstlet_id -= 1
            curr_burstlet_len = curr_burstlet_end - curr_burstlet_start
            if curr_burstlet_len > 1:
                left_border = self.data.time[curr_burstlet_start] - 0.1
                right_border = self.data.time[curr_burstlet_end] + 0.1
            else:
                left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) / 2
                right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) / 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
            if curr_burstlet_amplitude > 0.004:
                top_border = max(0.002, curr_burstlet_amplitude / 2 + 0.0001)
                bottom_border = min(-0.002, curr_burstlet_amplitude / 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstrbtn.isChecked():
            if getattr(self, 'burst_id', None) is None:
                self.burst_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burst_start = self.data.bursts_starts[curr_signal][self.burst_id]
            curr_burst_end = self.data.bursts_ends[curr_signal][self.burst_id]
            if self.burst_id > 0:
                self.burst_id -= 1
            curr_burst_len = self.data.time[curr_burst_end] - self.data.time[curr_burst_start]
            if curr_burst_len > 1:
                left_border = self.data.time[curr_burst_start] - 0.1
                right_border = self.data.time[curr_burst_end] + 0.1
            else:
                left_border = self.data.time[curr_burst_start] - (1 - curr_burst_len) / 2
                right_border = self.data.time[curr_burst_end] + (1 - curr_burst_len) / 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)


class StatDialog(QDialog):

    def __init__(self, data=None):
        super().__init__()
        self.data = data
        self.init_ui()

    def set_data(self, data):
        self.data = data

    def init_ui(self):
        self.create_plot_layout()

    def create_plot_layout(self):
        self.horizontalGroupBox = QGroupBox()
        layout = QGridLayout()

        num_rows = 1
        num_columns = 1

        plots = []

        for row_id in range(0, num_rows):
            layout.setColumnStretch(row_id, num_columns)

        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                curr_plot = pg.PlotWidget()
                curr_plot.enableAutoRange(False, False)
                curr_plot.setXRange(0, 60)
                curr_plot.setYRange(0, 60.5)
                curr_plot.setLabel('left', 'Electrode')
                curr_plot.setLabel('bottom', 'Time (s)')
                curr_plot.setLimits(yMin=-1, yMax=62, minYRange=1)
                if self.data:
                    if self.data.spikes:
                        rplot = raster_plot(self.data)
                        curr_plot.addItem(rplot)
                layout.addWidget(curr_plot, col_id, row_id)
                plots.append(curr_plot)

        self.horizontalGroupBox.setLayout(layout)

    def plot_raster(self):
        num_rows = 1
        num_columns = 1
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                rplot = raster_plot(self.data)
                self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(rplot)


def main(args=sys.argv):
    application = QApplication(args)
    screen = application.primaryScreen()
    rect = screen.availableGeometry()
    window = MEAXtd(rect)
    window.show()
    sys.exit(application.exec_())
