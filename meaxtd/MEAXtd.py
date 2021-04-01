import sys
import pkg_resources
import pyqtgraph as pg
from meaxtd.read_h5 import read_h5_file
from meaxtd.hdf5plot import HDF5Plot, HDF5PlotXY
from meaxtd.find_bursts import find_spikes, find_burstlets
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import (QAction, QApplication, QDesktopWidget, QDialog, QFileDialog,
                               QHBoxLayout, QLabel, QMainWindow, QToolBar, QVBoxLayout, QWidget, QTabWidget,
                               QGroupBox, QGridLayout, QPushButton, QComboBox, QRadioButton)


class MEAXtd(QMainWindow):
    """Create the main window that stores all of the widgets necessary for the application."""

    def __init__(self, parent=None):
        """Initialize the components of the main window."""
        super(MEAXtd, self).__init__(parent)
        self.setWindowTitle('MEAXtd')
        window_icon = pkg_resources.resource_filename('meaxtd.images',
                                                      'ic_insert_drive_file_black_48dp_1x.png')
        self.setWindowIcon(QIcon(window_icon))
        self.resize(2000, 900)

        self.menu_bar = self.menuBar()
        self.about_dialog = AboutDialog()
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('Ready', 5000)
        self.file_menu()
        self.help_menu()

        self.tabs = QTabWidget(self)
        self.main_tab = QWidget()

        self.main_tab.layout = QHBoxLayout(self)
        self.spike_button(self.main_tab.layout)
        self.tool_bar_items()
        self.main_tab.setLayout(self.main_tab.layout)

        self.plot_tab = QWidget()
        self.plot = PlotDialog()
        self.plot_tab.layout = QVBoxLayout(self)
        self.plot_tab.layout.addWidget(self.plot.horizontalGroupBox)
        self.plot_tab.layout.addWidget(self.plot.buttonGroupBox)
        self.plot_tab.setLayout(self.plot_tab.layout)

        self.tabs.addTab(self.main_tab, "Main")
        self.tabs.addTab(self.plot_tab, "Plot")

        self.setCentralWidget(self.tabs)

    def file_menu(self):
        """Create a file submenu with an Open File item that opens a file dialog."""
        self.file_sub_menu = self.menu_bar.addMenu('File')

        self.open_action = QAction('Open File', self)
        self.open_action.setStatusTip('Open a file into MEAXtd.')
        self.open_action.setShortcut('CTRL+O')
        self.open_action.triggered.connect(self.open_file)

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

    def tool_bar_items(self):
        """Create a tool bar for the main window."""
        self.tool_bar = QToolBar()
        # self.addToolBar(Qt.TopToolBarArea, self.tool_bar)
        # self.tool_bar.setMovable(False)
        # open_icon = pkg_resources.resource_filename('meaxtd.images', 'ic_open_in_new_black_48dp_1x.png')
        # tool_bar_open_action = QAction(QIcon(open_icon), 'Open File', self)
        # tool_bar_open_action.triggered.connect(self.open_file)
        # self.tool_bar.addAction(tool_bar_open_action)

    def open_file(self):
        """Open a QFileDialog to allow the user to open a file into the application."""
        filename, accepted = QFileDialog.getOpenFileName(self, 'Open File', filter="*.h5")

        if accepted:
            self.data = read_h5_file(filename)
            self.spikeqbtn.setEnabled(True)
            self.plot.set_data(self.data)
            self.plot.plot_signals()

    def spike_button(self, layout):
        self.spikeqbtn = QPushButton('Find Bursts', self)
        self.spikeqbtn.setEnabled(False)
        self.spikeqbtn.resize(100, 50)
        self.spikeqbtn.move(100, 250)
        layout.addWidget(self.spikeqbtn)
        layout.addStretch(1)
        self.setLayout(layout)
        self.spikeqbtn.clicked.connect(lambda: self.find_burstlets())

    def find_burstlets(self):
        if not self.data.burstlets:
            find_burstlets(self.data)
        self.plot.signalrbtn.setCheckable(True)
        self.plot.signalrbtn.setChecked(True)
        self.plot.spikerbtn.setCheckable(True)
        self.plot.burstletrbtn.setCheckable(True)


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
        self.initUI()

    def set_data(self, data):
        self.data = data

    def initUI(self):
        self.createGridLayout()
        self.createButtonLayout()

    def createGridLayout(self):
        self.horizontalGroupBox = QGroupBox()
        layout = QGridLayout()

        num_rows = 12
        num_columns = 5

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

    def createButtonLayout(self):
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

        if not self.data:
            self.signalrbtn.setCheckable(False)
            self.spikerbtn.setCheckable(False)
            self.burstletrbtn.setCheckable(False)

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
        num_rows = 12
        num_columns = 5
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
        elif self.spikerbtn.isChecked() or self.burstletrbtn.isChecked():
            self.prevqbtn.setEnabled(True)
            self.nextqbtn.setEnabled(True)
        if getattr(self, 'spike_id', None) is not None:
            self.spike_id = None
        if getattr(self, 'burstlet_id', None) is not None:
            self.burstlet_id = None
        curr_curves = self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().plotItem.curves
        if len(curr_curves) > 1:
            num_rows = 12
            num_columns = 5
            for curve_id in range(1, len(curr_curves)):
                for col_id in range(0, num_columns):
                    for row_id in range(0, num_rows):
                        curr_plot_item = self.horizontalGroupBox.layout().itemAtPosition(col_id,
                                                                                         row_id).widget().plotItem
                        curr_plot_item.removeItem(curr_plot_item.curves[curve_id])

    def add_spike_data(self):
        if self.spikerbtn.isChecked():
            self.remove_data()
            num_rows = 12
            num_columns = 5
            for col_id in range(0, num_columns):
                for row_id in range(0, num_rows):
                    curr_id = col_id * num_rows + row_id
                    spikes = HDF5PlotXY()
                    curr_spike_data = self.data.spike_stream[curr_id]
                    spikes.setHDF5(self.data.time, curr_spike_data, self.data.fs, pen=pg.mkPen(color='r', width=2))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(spikes)

    def add_burstlet_data(self):
        if self.burstletrbtn.isChecked():
            self.remove_data()
            num_rows = 12
            num_columns = 5
            for col_id in range(0, num_columns):
                for row_id in range(0, num_rows):
                    curr_id = col_id * num_rows + row_id
                    burstlets = HDF5PlotXY()
                    curr_burstlet_data = self.data.burstlet_stream[curr_id]
                    burstlets.setHDF5(self.data.time, curr_burstlet_data, self.data.fs,
                                      pen=pg.mkPen(color='r', width=2))
                    self.horizontalGroupBox.layout().itemAtPosition(col_id, row_id).widget().addItem(burstlets)

    def change_range_forward(self):
        if self.spikerbtn.isChecked():
            if getattr(self, 'spike_id', None) is None:
                self.spike_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_spike = self.data.spikes[curr_signal][self.spike_id]
            curr_spike_amplitude = self.data.spikes_amplitudes[curr_signal][self.spike_id]
            if self.spike_id < len(self.data.spikes[curr_signal]):
                self.spike_id += 1
            left_border = max(0, self.data.time[curr_spike] - 0.5)
            right_border = min(len(self.data.time), self.data.time[curr_spike] + 0.5)
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            if curr_spike_amplitude > 0.004:
                top_border = max(0.002, curr_spike_amplitude // 2 + 0.0001)
                bottom_border = min(-0.002, curr_spike_amplitude // 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstletrbtn.isChecked():
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id]
            curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id]
            curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id]
            if self.burstlet_id < len(self.data.burstlets[curr_signal]):
                self.burstlet_id += 1
            curr_burstlet_len = self.data.time[curr_burstlet_end] - self.data.time[curr_burstlet_start]
            if curr_burstlet_len > 1:
                left_border = self.data.time[curr_burstlet_start] - 0.1
                right_border = self.data.time[curr_burstlet_end] + 0.1
            else:
                left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) // 2
                right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) // 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
            if curr_burstlet_amplitude > 0.004:
                top_border = max(0.002, curr_burstlet_amplitude // 2 + 0.0001)
                bottom_border = min(-0.002, curr_burstlet_amplitude // 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)

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
                top_border = max(0.002, curr_spike_amplitude // 2 + 0.0001)
                bottom_border = min(-0.002, curr_spike_amplitude // 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if self.burstletrbtn.isChecked():
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            curr_signal = int(self.signalComboBox.currentText()) - 1
            curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id]
            curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id]
            curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id]
            if self.burstlet_id < len(self.data.burstlets[curr_signal]):
                self.burstlet_id -= 1
            curr_burstlet_len = curr_burstlet_end - curr_burstlet_start
            if curr_burstlet_len > 1:
                left_border = self.data.time[curr_burstlet_start] - 0.1
                right_border = self.data.time[curr_burstlet_end] + 0.1
            else:
                left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) // 2
                right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) // 2
            self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
            curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
            if curr_burstlet_amplitude > 0.004:
                top_border = max(0.002, curr_burstlet_amplitude // 2 + 0.0001)
                bottom_border = min(-0.002, curr_burstlet_amplitude // 2 - 0.0001)
                self.horizontalGroupBox.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)


def main(args=sys.argv):
    application = QApplication(args)
    window = MEAXtd()
    desktop = QDesktopWidget().availableGeometry()
    width = (desktop.width() - window.width()) / 4
    height = (desktop.height() - window.height()) / 4
    window.show()
    window.move(width, height)
    sys.exit(application.exec_())
