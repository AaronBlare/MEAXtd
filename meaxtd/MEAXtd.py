import sys
import re
import traceback
import pyqtgraph as pg
import numpy as np
import logging
from meaxtd.read_h5 import read_h5_file
from meaxtd.hdf5plot import HDF5PlotXY
from meaxtd.find_bursts import find_spikes, find_bursts, calculate_characteristics
from meaxtd.construct_graph import construct_delayed_spikes_graph
from meaxtd.save_result import save_tables_to_file, save_plots_to_file, save_params_to_file, save_graph_to_file
from meaxtd.stat_plots import raster_plot, tsr_plot, colormap_plot, tsr_plot_threshold
from PySide6.QtCore import Qt, QRunnable, Slot, QThreadPool, QObject, Signal, QPoint, QRectF
from PySide6.QtGui import QIcon, QFont, QAction, QScreen, QPixmap, QBrush, QColor
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QLayout, QFrame, QSizePolicy,
                               QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget, QTabWidget, QSpacerItem,
                               QGroupBox, QGridLayout, QPushButton, QComboBox, QRadioButton, QPlainTextEdit,
                               QProgressBar, QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
                               QStyleFactory, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem)

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOption('imageAxisOrder', 'row-major')


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
        self.kwargs['progress_callback'] = self.signals.progress

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


class MyLog(QObject):
    signal = Signal(str)

    def __init__(self):
        super().__init__()


class ThreadLogger(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log = MyLog()

    def emit(self, record):
        msg = self.format(record)
        self.log.signal.emit(msg)


class TableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return self.text() < other.text()


class PhotoViewer(QGraphicsView):
    photoClicked = Signal(QPoint)

    def __init__(self, parent):
        super(PhotoViewer, self).__init__(parent)
        self._zoom = 0
        self._empty = True
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._photo.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._photo)
        self.setScene(self._scene)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(255, 255, 255)))
        self.setFrameShape(QFrame.NoFrame)

    def hasPhoto(self):
        return not self._empty

    def fitInView(self, scale=True):
        rect = QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.hasPhoto():
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self._zoom = 0

    def setPhoto(self, pixmap=None):
        self._zoom = 0
        self._scene.clear()
        self.viewport().update()
        # if len(self.scene().items()) > 1:
        #     for item_id in range(len(self.scene().items()) - 1, -1, -1):
        #         curr_item = self.scene().items()[item_id]
        #         self.scene().removeItem(curr_item)
        self._photo = QGraphicsPixmapItem()
        self._photo.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
            self._scene.addItem(self._photo)
            self.fitInView()
        else:
            self._empty = True
            self.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())
            self._scene.addItem(self._photo)

    def wheelEvent(self, event):
        if self.hasPhoto():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1
            else:
                factor = 0.8
                self._zoom -= 1
            self.scale(factor, factor)

    def toggleDragMode(self):
        if self.dragMode() == QGraphicsView.ScrollHandDrag:
            self.setDragMode(QGraphicsView.NoDrag)
        elif not self._photo.pixmap().isNull():
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def mousePressEvent(self, event):
        if self._photo.isUnderMouse():
            self.photoClicked.emit(self.mapToScene(event.pos()).toPoint())
        super(PhotoViewer, self).mousePressEvent(event)


class MEAXtd(QMainWindow):
    """Create the main window that stores all of the widgets necessary for the application."""

    def __init__(self, rect, parent=None):
        """Initialize the components of the main window."""
        super(MEAXtd, self).__init__(parent)
        self.setWindowTitle('MEAXtd')

        # window_icon = pkg_resources.resource_filename('meaxtd.images', 'ic_insert_drive_file_black_48dp_1x.png')
        # self.setWindowIcon(QIcon(window_icon))

        self.av_width = rect.width()
        self.av_height = rect.height()
        # self.setMaximumSize(self.av_width, self.av_height)
        self.resize(int(self.av_width * 0.9), int(self.av_height * 0.75))

        self.menu_bar = self.menuBar()
        self.about_dialog = AboutDialog()
        # self.status_bar = self.statusBar()
        # self.status_bar.showMessage('Ready')
        self.file_menu()
        self.help_menu()

        self.central_widget = QWidget(self)
        central_size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        central_size_policy.setHorizontalStretch(0)
        central_size_policy.setVerticalStretch(0)
        central_flag = self.central_widget.sizePolicy().hasHeightForWidth()
        central_size_policy.setHeightForWidth(central_flag)
        self.central_widget.setSizePolicy(central_size_policy)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSizeConstraint(QLayout.SetNoConstraint)

        self.tabs = QTabWidget(self.central_widget)
        tab_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_size_policy.setHorizontalStretch(0)
        tab_size_policy.setVerticalStretch(15)
        tab_size_policy_flag = self.tabs.sizePolicy().hasHeightForWidth()
        tab_size_policy.setHeightForWidth(tab_size_policy_flag)
        self.tabs.setSizePolicy(tab_size_policy)
        self.tabs.setFocusPolicy(Qt.ClickFocus)

        self.main_tab = QWidget()
        self.main_tab_upper_layout = QVBoxLayout(self.main_tab)
        self.create_main_upper_layout()

        self.plot_tab = QWidget()
        self.plot_tab_layout = QVBoxLayout(self.plot_tab)
        self.create_plot_upper_layout()
        self.create_plot_bottom_layout()

        self.stat_tab = QWidget()
        self.stat_tab_layout = QHBoxLayout(self.stat_tab)
        self.create_stat_layout()

        self.char_tab = QWidget()
        self.char_tab_layout = QGridLayout(self.char_tab)
        self.create_char_layout()

        self.graph_tab = QWidget()
        self.graph_tab_layout = QHBoxLayout(self.graph_tab)
        self.create_graph_layout()

        self.tabs.addTab(self.main_tab, "Main")
        self.tabs.addTab(self.plot_tab, "Signal")
        self.tabs.addTab(self.stat_tab, "Plots")
        self.tabs.addTab(self.char_tab, "Characteristics")
        self.tabs.addTab(self.graph_tab, "Graphs")

        self.main_layout.addWidget(self.tabs)

        self.create_logging_layout()

        self.setCentralWidget(self.central_widget)
        self.center()

        self.threadpool = QThreadPool()
        self.param_change = False
        self.excluded_channels = []

    def center(self):
        frame_gm = self.frameGeometry()
        center_point = QScreen.availableGeometry(QApplication.primaryScreen()).center()  # pyside6 and pyside2 diff
        frame_gm.moveCenter(center_point)  # pyside6 and pyside2 diff
        self.move(frame_gm.topLeft())

    def clear_all(self):
        self.highlight_none_rb.setCheckable(False)
        self.highlight_spike_rb.setCheckable(False)
        self.highlight_burstlet_rb.setCheckable(False)
        self.highlight_burst_rb.setCheckable(False)
        self.plot_navigation_back_button.setEnabled(False)
        self.plot_navigation_next_button.setEnabled(False)
        self.plot.remove_data(self.plot_grid)
        self.stat.remove_plots(self.stat_left_groupbox_layout, self.stat_right_groupbox_layout)
        self.create_char_layout()

    @Slot()
    def spinbox_change(self):
        self.process_graph()

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

    def read_h5_data(self, filename, progress_callback):
        data = read_h5_file(filename, progress_callback)
        return data

    def set_data(self, data):
        self.data = data

    def configure_buttons_after_open(self):
        if self.data:
            self.logger.info(f"File loaded.")
            self.processqbtn.setEnabled(True)
            self.processqbtn.setAutoDefault(True)
            self.processqbtn.setFocus()
            self.plot.set_data(self.data, 0, int(np.ceil(self.data.time[-1] / 60)))
            self.stat.set_data(self.data, 0, int(np.ceil(self.data.time[-1] / 60)))
            self.plot.plot_signals(self.plot_grid)
            self.signal_start.setValue(0)
            self.signal_end.setValue(int(np.ceil(self.data.time[-1] / 60)))
            self.signal_start.valueChanged.connect(self.start_time_spinbox_change)
            self.signal_end.valueChanged.connect(self.end_time_spinbox_change)

    def set_progress_value(self, value):
        if value > self.progressBar.value() or self.progressBar.value() > 99:
            self.progressBar.setValue(value)

    def open_file(self):
        """Open a QFileDialog to allow the user to open a file into the application."""
        filename, accepted = QFileDialog.getOpenFileName(self, 'Open File', filter="*.h5")
        self.filename = filename

        if accepted:
            self.signal_start.valueChanged.disconnect()
            self.signal_end.valueChanged.disconnect()
            if getattr(self, 'data', None) is not None:
                self.data.clear_calculated()
                self.clear_all()
                self.plot.remove_signals(self.plot_grid)
            self.logger.info(f"File {filename} loading...")
            worker = Worker(self.read_h5_data, filename=filename)
            worker.signals.result.connect(self.set_data)
            worker.signals.finished.connect(self.configure_buttons_after_open)
            worker.signals.progress.connect(self.set_progress_value)
            self.threadpool.start(worker)

    def spike_combobox_change(self):
        self.logger.info(f"Spike method: {self.spike_method_combobox.currentText()}")
        self.param_change = True

    def burst_combobox_change(self):
        self.logger.info(f"Burst method: {self.burst_method_combobox.currentText()}")
        if self.burst_method_combobox.currentText() == 'Burstlet':
            self.burst_param_label.setText("Num channels")
            self.burst_param_label.setToolTip("Minimal number of channels for burst")
            self.burst_param.setDecimals(0)
            self.burst_param.setMinimum(0)
            self.burst_param.setMaximum(60)
            self.burst_param.setValue(5)
        if self.burst_method_combobox.currentText() == 'TSR':
            self.burst_param_label.setText("Threshold coefficient")
            self.burst_param_label.setToolTip("Coefficient for threshold: mean(TSR) + coeff * std(TSR)")
            self.burst_param.setDecimals(2)
            self.burst_param.setMinimum(-100.0)
            self.burst_param.setMaximum(100.0)
            self.burst_param.setValue(0.1)
        self.param_change = True

    def spike_spinbox_change(self):
        self.logger.info(f"Spike coefficient: {self.spike_coeff.value()}")
        self.param_change = True

    def burst_window_spinbox_change(self):
        self.logger.info(f"Burst window: {self.burst_window_size.value()} ms")
        self.param_change = True

    def burst_parameter_spinbox_change(self):
        if self.burst_method_combobox.currentText() == 'Burstlet':
            self.logger.info(f"Num channels for bursting: {int(self.burst_param.value())}")
        if self.burst_method_combobox.currentText() == 'TSR':
            self.logger.info(f"TSR threshold coefficient: {self.burst_param.value()}")
        self.param_change = True

    def start_time_spinbox_change(self):
        self.logger.info(f"Start time: {self.signal_start.value()} min")
        self.plot.set_data(self.data, self.signal_start.value(), self.signal_end.value())
        self.stat.set_data(self.data, self.signal_start.value(), self.signal_end.value())
        self.param_change = True

    def end_time_spinbox_change(self):
        self.logger.info(f"End time: {self.signal_end.value()} min")
        self.plot.set_data(self.data, self.signal_start.value(), self.signal_end.value())
        self.stat.set_data(self.data, self.signal_start.value(), self.signal_end.value())
        self.param_change = True

    def include_exclude_channel(self, button):
        if button.styleSheet() == u"background-color: rgb(85, 255, 127);":
            button.setStyleSheet(u"background-color: rgb(255, 85, 127);")
            self.logger.info(f"Channel {button.text()} excluded.")
            self.excluded_channels.append(int(button.text()) - 1)
            self.param_change = True
        else:
            button.setStyleSheet(u"background-color: rgb(85, 255, 127);")
            self.logger.info(f"Channel {button.text()} included.")
            self.excluded_channels.remove(int(button.text()) - 1)
            self.param_change = True

    def configure_signal_button(self, button):
        size_policy_flag = button.sizePolicy().hasHeightForWidth()
        self.signal_btn_size_policy.setHeightForWidth(size_policy_flag)
        button.setSizePolicy(self.signal_btn_size_policy)
        button.setMinimumSize(1, 1)  # pyside6 and pyside2 diff
        button.setStyleSheet(u"background-color: rgb(85, 255, 127);")
        button.setFont(self.signal_btn_font)

        button.clicked.connect(lambda curr_button=button: self.include_exclude_channel(button))

    def delta_spinbox_change(self):
        self.logger.info(f"Delta: {self.graph_params_delta_spinbox.value()}")

    def tau_spinbox_change(self):
        self.logger.info(f"Number of frames: {self.graph_params_tau_spinbox.value()}")

    def cutoff_spinbox_change(self):
        self.logger.info(f"Cutoff: {self.graph_params_cutoff_spinbox.value()}% from top")

    def burst_id_spinbox_change(self):
        self.logger.info(f"Build graph for burst {self.burst_id_spinbox.value()}")

    def create_main_upper_layout(self):
        self.main_tab_upper_groupbox = QGroupBox(self.main_tab)
        main_tab_upper_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_tab_upper_size_policy.setHorizontalStretch(0)
        main_tab_upper_size_policy.setVerticalStretch(0)
        policy_flag = self.main_tab_upper_groupbox.sizePolicy().hasHeightForWidth()
        main_tab_upper_size_policy.setHeightForWidth(policy_flag)
        self.main_tab_upper_groupbox.setSizePolicy(main_tab_upper_size_policy)

        self.main_tab_upper_groupbox_layout = QHBoxLayout(self.main_tab_upper_groupbox)

        # Frame for Load and Process buttons
        self.frame = QFrame(self.main_tab_upper_groupbox)
        button_frame_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        button_frame_size_policy.setHorizontalStretch(1)
        button_frame_size_policy.setVerticalStretch(0)
        policy_flag = self.frame.sizePolicy().hasHeightForWidth()
        button_frame_size_policy.setHeightForWidth(policy_flag)
        self.frame.setSizePolicy(button_frame_size_policy)
        self.main_tab_button_layout = QVBoxLayout(self.frame)
        self.main_tab_button_layout.setContentsMargins(70, 50, 70, 50)
        self.load_button()

        self.verticalSpacer = QSpacerItem(20, 200, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.main_tab_button_layout.addItem(self.verticalSpacer)

        self.process_button()
        self.main_tab_upper_groupbox_layout.addWidget(self.frame)

        # Frame for parameters groupboxes
        self.params_frame = QFrame(self.main_tab_upper_groupbox)
        params_frame_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        params_frame_size_policy.setHorizontalStretch(2)
        params_frame_size_policy.setVerticalStretch(0)
        policy_flag = self.params_frame.sizePolicy().hasHeightForWidth()
        params_frame_size_policy.setHeightForWidth(policy_flag)
        self.params_frame.setSizePolicy(params_frame_size_policy)
        self.params_frame.setMinimumSize(300, 300)  # pyside6 and pyside2 diff
        self.params_frame.setFrameShape(QFrame.StyledPanel)
        self.params_frame.setFrameShadow(QFrame.Raised)

        self.params_frame_layout = QVBoxLayout(self.params_frame)

        # Signal Editing Groupbox
        self.signal_param_groupbox = QGroupBox(self.params_frame, title="Signal Editing")

        self.gbox_font = QFont()
        self.gbox_font.setPointSize(18)

        self.signal_param_groupbox.setFont(self.gbox_font)
        self.signal_param_grid_layout = QGridLayout(self.signal_param_groupbox)
        self.signal_param_grid_layout.setContentsMargins(50, 20, 50, 20)

        self.signal_start_label = QLabel(self.signal_param_groupbox, text="Signal start, min")
        self.signal_start_label.setToolTip("Set signal start")
        self.signal_start_label.setToolTipDuration(1000)
        self.signal_param_grid_layout.addWidget(self.signal_start_label, 0, 0, 1, 1)

        self.signal_start = QSpinBox(self.signal_param_groupbox)
        self.size_policy1 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        self.size_policy1.setHorizontalStretch(0)
        self.size_policy1.setVerticalStretch(0)
        policy_flag = self.signal_start.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.signal_start.setSizePolicy(self.size_policy1)
        self.signal_start.setMinimum(0)
        self.signal_start.setMaximum(1000)
        self.signal_start.setValue(0)
        self.signal_start.valueChanged.connect(self.start_time_spinbox_change)
        self.signal_param_grid_layout.addWidget(self.signal_start, 0, 1, 1, 1)

        self.signal_end_label = QLabel(self.signal_param_groupbox, text="Signal end, min")
        self.signal_end_label.setToolTip("Set signal end")
        self.signal_end_label.setToolTipDuration(1000)
        self.signal_param_grid_layout.addWidget(self.signal_end_label, 1, 0, 1, 1)

        self.signal_end = QSpinBox(self.signal_param_groupbox)
        policy_flag = self.signal_end.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.signal_end.setSizePolicy(self.size_policy1)
        self.signal_end.setMinimum(0)
        self.signal_end.setMaximum(1000)
        self.signal_end.setValue(0)
        self.signal_end.valueChanged.connect(self.end_time_spinbox_change)
        self.signal_param_grid_layout.addWidget(self.signal_end, 1, 1, 1, 1)

        self.params_frame_layout.addWidget(self.signal_param_groupbox)

        # Spike Parameters Groupbox
        self.spike_params_groupbox = QGroupBox(self.main_tab_upper_groupbox, title="Spike Parameters")

        self.spike_params_groupbox.setFont(self.gbox_font)
        self.spike_grid_layout = QGridLayout(self.spike_params_groupbox)
        self.spike_grid_layout.setContentsMargins(50, 20, 50, 20)

        self.spike_method_label = QLabel(self.spike_params_groupbox, text="Method")
        self.spike_method_label.setToolTip("Method for spike searching")
        self.spike_method_label.setToolTipDuration(1000)
        self.spike_grid_layout.addWidget(self.spike_method_label, 0, 0, 1, 1)

        self.spike_method_combobox = QComboBox(self.spike_params_groupbox)
        policy_flag = self.spike_method_combobox.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.spike_method_combobox.setSizePolicy(self.size_policy1)
        spike_methods = ['Median', 'RMS', 'std']
        self.spike_method_combobox.addItems(spike_methods)
        self.spike_method_combobox.currentIndexChanged.connect(self.spike_combobox_change)
        self.spike_grid_layout.addWidget(self.spike_method_combobox, 0, 1, 1, 1)

        self.spike_coeff_label = QLabel(self.spike_params_groupbox, text="Coefficient")
        self.spike_coeff_label.setToolTip("Coefficient for noise value")
        self.spike_coeff_label.setToolTipDuration(1000)
        self.spike_grid_layout.addWidget(self.spike_coeff_label, 1, 0, 1, 1)

        self.spike_coeff = QDoubleSpinBox(self.spike_params_groupbox)
        policy_flag = self.spike_coeff.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.spike_coeff.setSizePolicy(self.size_policy1)
        self.spike_coeff.setMinimum(-5000.0)
        self.spike_coeff.setMaximum(5000.0)
        self.spike_coeff.setValue(-5.0)
        self.spike_coeff.valueChanged.connect(self.spike_spinbox_change)
        self.spike_grid_layout.addWidget(self.spike_coeff, 1, 1, 1, 1)

        self.params_frame_layout.addWidget(self.spike_params_groupbox)

        # Burst Parameters Groupbox
        self.burst_param_groupbox = QGroupBox(self.main_tab_upper_groupbox, title="Burst Parameters")
        self.burst_param_groupbox.setFont(self.gbox_font)
        self.burst_grid_layout = QGridLayout(self.burst_param_groupbox)
        self.burst_grid_layout.setContentsMargins(50, 20, 50, 20)

        self.burst_method_label = QLabel(self.burst_param_groupbox, text="Method")
        self.burst_method_label.setToolTip("Method for burst searching")
        self.burst_method_label.setToolTipDuration(1000)
        self.burst_grid_layout.addWidget(self.burst_method_label, 0, 0, 1, 1)

        self.burst_method_combobox = QComboBox(self.burst_param_groupbox)
        policy_flag = self.burst_method_combobox.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.burst_method_combobox.setSizePolicy(self.size_policy1)
        burst_methods = ['TSR', 'Burstlet']
        self.burst_method_combobox.addItems(burst_methods)
        self.burst_method_combobox.currentIndexChanged.connect(self.burst_combobox_change)
        self.burst_grid_layout.addWidget(self.burst_method_combobox, 0, 1, 1, 1)

        self.burst_window_label = QLabel(self.burst_param_groupbox, text="Window size, ms")
        self.burst_window_label.setToolTip("Window size for burst")
        self.burst_window_label.setToolTipDuration(1000)
        self.burst_grid_layout.addWidget(self.burst_window_label, 1, 0, 1, 1)

        self.burst_window_size = QSpinBox(self.burst_param_groupbox)
        policy_flag = self.burst_window_size.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.burst_window_size.setSizePolicy(self.size_policy1)
        self.burst_window_size.setMinimum(0)
        self.burst_window_size.setMaximum(1000)
        self.burst_window_size.setValue(100)
        self.burst_window_size.valueChanged.connect(self.burst_window_spinbox_change)
        self.burst_grid_layout.addWidget(self.burst_window_size, 1, 1, 1, 1)

        self.burst_param_label = QLabel(self.burst_param_groupbox)
        if self.burst_method_combobox.currentText() == 'Burstlet':
            self.burst_param_label.setText("Num channels")
            self.burst_param_label.setToolTip("Minimal number of channels for burst")
        if self.burst_method_combobox.currentText() == 'TSR':
            self.burst_param_label.setText("Threshold coefficient")
            self.burst_param_label.setToolTip("Coefficient for threshold: mean(TSR) + coeff * std(TSR)")
        self.burst_param_label.setToolTipDuration(1000)
        self.burst_grid_layout.addWidget(self.burst_param_label, 2, 0, 1, 1)

        self.burst_param = QDoubleSpinBox(self.burst_param_groupbox)
        policy_flag = self.burst_param.sizePolicy().hasHeightForWidth()
        self.size_policy1.setHeightForWidth(policy_flag)
        self.burst_param.setSizePolicy(self.size_policy1)
        if self.burst_method_combobox.currentText() == 'Burstlet':
            self.burst_param.setDecimals(0)
            self.burst_param.setMinimum(0.0)
            self.burst_param.setMaximum(60.0)
            self.burst_param.setValue(5.0)
        if self.burst_method_combobox.currentText() == 'TSR':
            self.burst_param.setDecimals(2)
            self.burst_param.setMinimum(-100.0)
            self.burst_param.setMaximum(100.0)
            self.burst_param.setValue(0.1)
        self.burst_param.valueChanged.connect(self.burst_parameter_spinbox_change)
        self.burst_grid_layout.addWidget(self.burst_param, 2, 1, 1, 1)

        self.params_frame_layout.addWidget(self.burst_param_groupbox)

        self.main_tab_upper_groupbox_layout.addWidget(self.params_frame)

        # Channels Groupbox
        self.channels_enabled_groupbox = QGroupBox(self.main_tab_upper_groupbox, title="Include/Exclude channels")
        self.channels_enabled_groupbox.setFont(self.gbox_font)
        channels_groupbox_size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        channels_groupbox_size_policy.setHorizontalStretch(2)
        channels_groupbox_size_policy.setVerticalStretch(0)
        policy_flag = self.channels_enabled_groupbox.sizePolicy().hasHeightForWidth()
        channels_groupbox_size_policy.setHeightForWidth(policy_flag)
        self.channels_enabled_groupbox.setSizePolicy(channels_groupbox_size_policy)

        self.channels_enabled_layout = QGridLayout(self.channels_enabled_groupbox)

        self.signal_btn_size_policy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.signal_btn_size_policy.setHorizontalStretch(0)
        self.signal_btn_size_policy.setVerticalStretch(0)
        self.signal_btn_font = QFont()
        self.signal_btn_font.setPointSize(20)

        self.add_signal_buttons()

        self.main_tab_upper_groupbox_layout.addWidget(self.channels_enabled_groupbox)
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

    def process_all(self, progress_callback):
        spike_method = self.spike_method_combobox.currentText()
        spike_coeff = self.spike_coeff.value()
        start = self.signal_start.value()
        end = self.signal_end.value()
        self.logger.info("Spikes and bursts finding...")
        find_spikes(self.data, self.excluded_channels, spike_method, spike_coeff, start, end, progress_callback)

        if self.data.spikes:
            self.logger.info("Spikes found.")
            self.highlight_none_rb.setCheckable(True)
            self.highlight_none_rb.setChecked(True)
            self.highlight_spike_rb.setCheckable(True)
            self.stat.plot_raster(self.stat_left_groupbox_layout)
            self.stat.plot_tsr(self.stat_left_groupbox_layout)

        burst_method = self.burst_method_combobox.currentText()
        burst_window = self.burst_window_size.value()
        if burst_method == 'Burstlet':
            burst_param = int(self.burst_param.value())
        if burst_method == 'TSR':
            burst_param = self.burst_param.value()
        find_bursts(self.data, self.excluded_channels, spike_method, spike_coeff, burst_method, burst_window,
                    burst_param, start, end, progress_callback)

        self.TSR_threshold = np.mean(self.data.TSR) + burst_param * np.std(self.data.TSR)
        self.stat.set_threshold(self.TSR_threshold)
        self.stat.plot_tsr(self.stat_left_groupbox_layout)

        self.logger.info(f"TSR threshold: {np.mean(self.data.TSR) + burst_param * np.std(self.data.TSR)}")
        self.logger.info(f"TSR mean: {np.mean(self.data.TSR)}; TSR std: {np.std(self.data.TSR)}")

        self.tabs.setCurrentWidget(self.stat_tab)
        self.tabs.setCurrentWidget(self.main_tab)

        excluded_channels = self.excluded_channels
        excluded_channels.sort()
        excluded_channels = [channel + 1 for channel in excluded_channels]

        params_dict = {'Signal start, min': start,
                       'Signal end, min': end,
                       'Spike method': spike_method,
                       'Spike coefficient': spike_coeff,
                       'Burst method': burst_method,
                       'Burst window, ms': burst_window,
                       'Burst param': burst_param,
                       'Excluded channels': excluded_channels}

        if self.data.bursts:
            self.logger.info("Bursts found.")
            self.highlight_none_rb.setCheckable(True)
            self.highlight_none_rb.setChecked(True)
            self.highlight_spike_rb.setCheckable(True)
            if self.burst_method_combobox.currentText() == 'Burstlet':
                self.highlight_burstlet_rb.setCheckable(True)
            self.highlight_burst_rb.setCheckable(True)
            self.stat.plot_colormap(self.stat_right_groupbox_layout)

        self.logger.info("Characteristics calculating...")
        calculate_characteristics(self.data, start, end, progress_callback)

        if self.data.global_characteristics:
            self.logger.info("Characteristics calculated.")
            self.char_global_table.setRowCount(len(list(self.data.global_characteristics.keys())))
            for n, key in enumerate(self.data.global_characteristics):
                curr_tab_item_0 = TableWidgetItem()
                curr_tab_item_0.setData(Qt.EditRole, key)
                self.char_global_table.setItem(n, 0, curr_tab_item_0)

                curr_item = round(self.data.global_characteristics[key], 4)
                curr_tab_item_1 = TableWidgetItem(str(curr_item))
                self.char_global_table.setItem(n, 1, curr_tab_item_1)

        if self.data.channel_characteristics:
            headers = list(self.data.channel_characteristics.keys())
            self.char_channel_table.setColumnCount(len(headers))
            self.char_channel_table.setHorizontalHeaderLabels(headers)
            signal_shift = 0
            for signal_id in range(0, self.data.stream.shape[1]):
                if signal_id not in self.excluded_channels:
                    for n, key in enumerate(self.data.channel_characteristics):
                        curr_item = self.data.channel_characteristics[key][signal_id]
                        if isinstance(self.data.channel_characteristics[key][signal_id], float):
                            curr_item = round(self.data.channel_characteristics[key][signal_id], 4)
                            curr_tab_item = TableWidgetItem(str(curr_item))
                            self.char_channel_table.setItem(signal_id - signal_shift, n, curr_tab_item)
                        elif isinstance(self.data.channel_characteristics[key][signal_id], np.int32):
                            curr_tab_item = TableWidgetItem(str(curr_item))
                            self.char_channel_table.setItem(signal_id - signal_shift, n, curr_tab_item)
                        else:
                            curr_tab_item = TableWidgetItem()
                            curr_tab_item.setData(Qt.EditRole, curr_item)
                            self.char_channel_table.setItem(signal_id - signal_shift, n, curr_tab_item)
                else:
                    signal_shift += 1
            self.char_channel_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        if self.data.burst_characteristics:
            headers = list(self.data.burst_characteristics.keys())
            self.char_burst_table.setColumnCount(len(headers))
            self.char_burst_table.setRowCount(len(self.data.bursts))
            self.char_burst_table.setHorizontalHeaderLabels(headers)

            self.graph_table.setColumnCount(len(headers))
            self.graph_table.setRowCount(len(self.data.bursts))
            self.graph_table.setHorizontalHeaderLabels(headers)

            for burst_id in range(0, len(self.data.bursts)):
                for n, key in enumerate(self.data.burst_characteristics):
                    curr_item = self.data.burst_characteristics[key][burst_id]
                    if isinstance(self.data.burst_characteristics[key][burst_id], float):
                        curr_item = round(self.data.burst_characteristics[key][burst_id], 2)
                        if curr_item == 0.0:
                            curr_item = round(self.data.burst_characteristics[key][burst_id], 6)
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.char_burst_table.setItem(burst_id, n, curr_tab_item)
                    elif isinstance(self.data.burst_characteristics[key][burst_id], np.int32):
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.char_burst_table.setItem(burst_id, n, curr_tab_item)
                    else:
                        curr_tab_item = TableWidgetItem()
                        curr_tab_item.setData(Qt.EditRole, curr_item)
                        self.char_burst_table.setItem(burst_id, n, curr_tab_item)

            for burst_id in range(0, len(self.data.bursts)):
                for n, key in enumerate(self.data.burst_characteristics):
                    curr_item = self.data.burst_characteristics[key][burst_id]
                    if isinstance(self.data.burst_characteristics[key][burst_id], float):
                        curr_item = round(self.data.burst_characteristics[key][burst_id], 2)
                        if curr_item == 0.0:
                            curr_item = round(self.data.burst_characteristics[key][burst_id], 6)
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.graph_table.setItem(burst_id, n, curr_tab_item)
                    elif isinstance(self.data.burst_characteristics[key][burst_id], np.int32):
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.graph_table.setItem(burst_id, n, curr_tab_item)
                    else:
                        curr_tab_item = TableWidgetItem()
                        curr_tab_item.setData(Qt.EditRole, curr_item)
                        self.graph_table.setItem(burst_id, n, curr_tab_item)

            self.char_burst_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.graph_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

            self.burst_id_spinbox.setMinimum(1)
            self.burst_id_spinbox.setMaximum(len(self.data.bursts))

        if self.data.time_characteristics:
            headers = list(self.data.time_characteristics.keys())
            self.char_time_table.setColumnCount(len(headers))
            self.char_time_table.setRowCount(len(self.data.bursts))
            self.char_time_table.setHorizontalHeaderLabels(headers)
            for minute_id in range(0, len(self.data.time_characteristics['Start'])):
                for n, key in enumerate(self.data.time_characteristics):
                    curr_item = self.data.time_characteristics[key][minute_id]
                    if isinstance(self.data.time_characteristics[key][minute_id], float):
                        curr_item = round(self.data.time_characteristics[key][minute_id], 2)
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.char_time_table.setItem(minute_id, n, curr_tab_item)
                    elif isinstance(self.data.time_characteristics[key][minute_id], np.int32):
                        curr_tab_item = TableWidgetItem(str(curr_item))
                        self.char_time_table.setItem(minute_id, n, curr_tab_item)
                    else:
                        curr_tab_item = TableWidgetItem()
                        curr_tab_item.setData(Qt.EditRole, curr_item)
                        self.char_time_table.setItem(minute_id, n, curr_tab_item)
            self.char_time_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.char_global_table.setSortingEnabled(True)
        self.char_channel_table.setSortingEnabled(True)
        self.char_channel_table.sortItems(0, Qt.AscendingOrder)
        self.char_burst_table.setSortingEnabled(True)
        self.char_burst_table.sortItems(0, Qt.AscendingOrder)
        self.char_time_table.setSortingEnabled(True)
        self.char_time_table.sortItems(0, Qt.AscendingOrder)
        self.graph_table.setSortingEnabled(True)
        self.graph_table.sortItems(0, Qt.AscendingOrder)

        self.path_to_save = save_tables_to_file(self.data, self.filename, progress_callback)

        save_plots_to_file(self.path_to_save, progress_callback,
                           self.stat_left_groupbox, self.stat_right_groupbox,
                           self.stat_left_groupbox_layout, self.stat_right_groupbox_layout)

        save_params_to_file(self.path_to_save, progress_callback, params_dict)

        if self.data.bursts:
            self.build_graph_btn.setEnabled(True)
            self.burst_id_spinbox.setEnabled(True)
            self.curr_burst_id = None
            # setKeyboardTracking(False)

    def save_characteristics(self):
        self.logger.info(f"Characteristics saved to {self.path_to_save}")
        self.param_change = False

    def process(self):
        if self.signal_start.value() >= self.signal_end.value():
            self.logger.info("End time must be later than Start time.")
        elif self.signal_end.value() > int(np.ceil(self.data.time[-1] / 60)):
            self.signal_end.setValue(int(np.ceil(self.data.time[-1] / 60)))
            self.logger.info(f"End time is set to {self.signal_end.value()}")
        else:
            if self.param_change:
                self.data.clear_calculated()
                self.clear_all()
            if not self.data.spikes:
                worker = Worker(self.process_all)
                worker.signals.finished.connect(self.save_characteristics)
                worker.signals.progress.connect(self.set_progress_value)
                self.threadpool.start(worker)
            else:
                self.logger.info("Spikes and bursts already found.")

    def process_graph_pipeline(self, progress_callback):
        burst_method = self.burst_method_combobox.currentText()

        delta = self.graph_params_delta_spinbox.value()
        num_frames = self.graph_params_tau_spinbox.value()
        cutoff = self.graph_params_cutoff_spinbox.value()
        burst_id = self.burst_id_spinbox.value() - 1

        if burst_id == self.curr_burst_id:
            return

        self.logger.info(f"Graph for burst {burst_id + 1} building...")

        construct_delayed_spikes_graph(self.data, progress_callback, burst_method, delta, num_frames, cutoff, burst_id)
        self.curr_burst_id = burst_id

        if len(self.data.graph_hub['Electrode']) > 0:
            self.logger.info(f"Graph for burst {burst_id + 1} built.")
            graph_file = save_graph_to_file(self.path_to_save, progress_callback,
                                            self.data.graph, self.data.graph_hub, burst_id)
        else:
            self.logger.info(f"Graph for burst {burst_id + 1} is empty.")
            graph_file = None

        self.graph_picture.setPhoto(QPixmap(graph_file))

    def process_graph(self):
        if self.data.bursts:
            worker = Worker(self.process_graph_pipeline)
            worker.signals.progress.connect(self.set_progress_value)
            self.threadpool.start(worker)

    def create_param_groupbox(self):
        self.param_layout = QHBoxLayout(self.main_tab_param_widget)
        self.param_groupbox = QGroupBox(self.main_tab_param_widget, title="Parameters")
        self.gbox_font = QFont()
        self.gbox_font.setPointSize(18)
        self.param_groupbox.setFont(self.gbox_font)
        self.param_layout.addWidget(self.param_groupbox)

    def add_signal_buttons(self):
        self.signal_button_1 = QPushButton('{}'.format(1), self)
        self.configure_signal_button(self.signal_button_1)
        self.channels_enabled_layout.addWidget(self.signal_button_1, 0, 1, 1, 1)
        self.signal_button_2 = QPushButton('{}'.format(2), self)
        self.configure_signal_button(self.signal_button_2)
        self.channels_enabled_layout.addWidget(self.signal_button_2, 0, 2, 1, 1)
        self.signal_button_3 = QPushButton('{}'.format(3), self)
        self.configure_signal_button(self.signal_button_3)
        self.channels_enabled_layout.addWidget(self.signal_button_3, 0, 3, 1, 1)
        self.signal_button_4 = QPushButton('{}'.format(4), self)
        self.configure_signal_button(self.signal_button_4)
        self.channels_enabled_layout.addWidget(self.signal_button_4, 0, 4, 1, 1)
        self.signal_button_5 = QPushButton('{}'.format(5), self)
        self.configure_signal_button(self.signal_button_5)
        self.channels_enabled_layout.addWidget(self.signal_button_5, 0, 5, 1, 1)
        self.signal_button_6 = QPushButton('{}'.format(6), self)
        self.configure_signal_button(self.signal_button_6)
        self.channels_enabled_layout.addWidget(self.signal_button_6, 0, 6, 1, 1)

        self.signal_button_7 = QPushButton('{}'.format(7), self)
        self.configure_signal_button(self.signal_button_7)
        self.channels_enabled_layout.addWidget(self.signal_button_7, 1, 0, 1, 1)
        self.signal_button_8 = QPushButton('{}'.format(8), self)
        self.configure_signal_button(self.signal_button_8)
        self.channels_enabled_layout.addWidget(self.signal_button_8, 1, 1, 1, 1)
        self.signal_button_9 = QPushButton('{}'.format(9), self)
        self.configure_signal_button(self.signal_button_9)
        self.channels_enabled_layout.addWidget(self.signal_button_9, 1, 2, 1, 1)
        self.signal_button_10 = QPushButton('{}'.format(10), self)
        self.configure_signal_button(self.signal_button_10)
        self.channels_enabled_layout.addWidget(self.signal_button_10, 1, 3, 1, 1)
        self.signal_button_11 = QPushButton('{}'.format(11), self)
        self.configure_signal_button(self.signal_button_11)
        self.channels_enabled_layout.addWidget(self.signal_button_11, 1, 4, 1, 1)
        self.signal_button_12 = QPushButton('{}'.format(12), self)
        self.configure_signal_button(self.signal_button_12)
        self.channels_enabled_layout.addWidget(self.signal_button_12, 1, 5, 1, 1)
        self.signal_button_13 = QPushButton('{}'.format(13), self)
        self.configure_signal_button(self.signal_button_13)
        self.channels_enabled_layout.addWidget(self.signal_button_13, 1, 6, 1, 1)
        self.signal_button_14 = QPushButton('{}'.format(14), self)
        self.configure_signal_button(self.signal_button_14)
        self.channels_enabled_layout.addWidget(self.signal_button_14, 1, 7, 1, 1)
        self.signal_button_15 = QPushButton('{}'.format(15), self)
        self.configure_signal_button(self.signal_button_15)

        self.channels_enabled_layout.addWidget(self.signal_button_15, 2, 0, 1, 1)
        self.signal_button_16 = QPushButton('{}'.format(16), self)
        self.configure_signal_button(self.signal_button_16)
        self.channels_enabled_layout.addWidget(self.signal_button_16, 2, 1, 1, 1)
        self.signal_button_17 = QPushButton('{}'.format(17), self)
        self.configure_signal_button(self.signal_button_17)
        self.channels_enabled_layout.addWidget(self.signal_button_17, 2, 2, 1, 1)
        self.signal_button_18 = QPushButton('{}'.format(18), self)
        self.configure_signal_button(self.signal_button_18)
        self.channels_enabled_layout.addWidget(self.signal_button_18, 2, 3, 1, 1)
        self.signal_button_19 = QPushButton('{}'.format(19), self)
        self.configure_signal_button(self.signal_button_19)
        self.channels_enabled_layout.addWidget(self.signal_button_19, 2, 4, 1, 1)
        self.signal_button_20 = QPushButton('{}'.format(20), self)
        self.configure_signal_button(self.signal_button_20)
        self.channels_enabled_layout.addWidget(self.signal_button_20, 2, 5, 1, 1)
        self.signal_button_21 = QPushButton('{}'.format(21), self)
        self.configure_signal_button(self.signal_button_21)
        self.channels_enabled_layout.addWidget(self.signal_button_21, 2, 6, 1, 1)
        self.signal_button_22 = QPushButton('{}'.format(22), self)
        self.configure_signal_button(self.signal_button_22)
        self.channels_enabled_layout.addWidget(self.signal_button_22, 2, 7, 1, 1)
        self.signal_button_23 = QPushButton('{}'.format(23), self)
        self.configure_signal_button(self.signal_button_23)

        self.channels_enabled_layout.addWidget(self.signal_button_23, 3, 0, 1, 1)
        self.signal_button_24 = QPushButton('{}'.format(24), self)
        self.configure_signal_button(self.signal_button_24)
        self.channels_enabled_layout.addWidget(self.signal_button_24, 3, 1, 1, 1)
        self.signal_button_25 = QPushButton('{}'.format(25), self)
        self.configure_signal_button(self.signal_button_25)
        self.channels_enabled_layout.addWidget(self.signal_button_25, 3, 2, 1, 1)
        self.signal_button_26 = QPushButton('{}'.format(26), self)
        self.configure_signal_button(self.signal_button_26)
        self.channels_enabled_layout.addWidget(self.signal_button_26, 3, 3, 1, 1)
        self.signal_button_27 = QPushButton('{}'.format(27), self)
        self.configure_signal_button(self.signal_button_27)
        self.channels_enabled_layout.addWidget(self.signal_button_27, 3, 4, 1, 1)
        self.signal_button_28 = QPushButton('{}'.format(28), self)
        self.configure_signal_button(self.signal_button_28)
        self.channels_enabled_layout.addWidget(self.signal_button_28, 3, 5, 1, 1)
        self.signal_button_29 = QPushButton('{}'.format(29), self)
        self.configure_signal_button(self.signal_button_29)
        self.channels_enabled_layout.addWidget(self.signal_button_29, 3, 6, 1, 1)
        self.signal_button_30 = QPushButton('{}'.format(30), self)
        self.configure_signal_button(self.signal_button_30)
        self.channels_enabled_layout.addWidget(self.signal_button_30, 3, 7, 1, 1)

        self.signal_button_31 = QPushButton('{}'.format(31), self)
        self.configure_signal_button(self.signal_button_31)
        self.channels_enabled_layout.addWidget(self.signal_button_31, 4, 0, 1, 1)
        self.signal_button_32 = QPushButton('{}'.format(32), self)
        self.configure_signal_button(self.signal_button_32)
        self.channels_enabled_layout.addWidget(self.signal_button_32, 4, 1, 1, 1)
        self.signal_button_33 = QPushButton('{}'.format(33), self)
        self.configure_signal_button(self.signal_button_33)
        self.channels_enabled_layout.addWidget(self.signal_button_33, 4, 2, 1, 1)
        self.signal_button_34 = QPushButton('{}'.format(34), self)
        self.configure_signal_button(self.signal_button_34)
        self.channels_enabled_layout.addWidget(self.signal_button_34, 4, 3, 1, 1)
        self.signal_button_35 = QPushButton('{}'.format(35), self)
        self.configure_signal_button(self.signal_button_35)
        self.channels_enabled_layout.addWidget(self.signal_button_35, 4, 4, 1, 1)
        self.signal_button_36 = QPushButton('{}'.format(36), self)
        self.configure_signal_button(self.signal_button_36)
        self.channels_enabled_layout.addWidget(self.signal_button_36, 4, 5, 1, 1)
        self.signal_button_37 = QPushButton('{}'.format(37), self)
        self.configure_signal_button(self.signal_button_37)
        self.channels_enabled_layout.addWidget(self.signal_button_37, 4, 6, 1, 1)
        self.signal_button_38 = QPushButton('{}'.format(38), self)
        self.configure_signal_button(self.signal_button_38)
        self.channels_enabled_layout.addWidget(self.signal_button_38, 4, 7, 1, 1)

        self.signal_button_39 = QPushButton('{}'.format(39), self)
        self.configure_signal_button(self.signal_button_39)
        self.channels_enabled_layout.addWidget(self.signal_button_39, 5, 0, 1, 1)
        self.signal_button_40 = QPushButton('{}'.format(40), self)
        self.configure_signal_button(self.signal_button_40)
        self.channels_enabled_layout.addWidget(self.signal_button_40, 5, 1, 1, 1)
        self.signal_button_41 = QPushButton('{}'.format(41), self)
        self.configure_signal_button(self.signal_button_41)
        self.channels_enabled_layout.addWidget(self.signal_button_41, 5, 2, 1, 1)
        self.signal_button_42 = QPushButton('{}'.format(42), self)
        self.configure_signal_button(self.signal_button_42)
        self.channels_enabled_layout.addWidget(self.signal_button_42, 5, 3, 1, 1)
        self.signal_button_43 = QPushButton('{}'.format(43), self)
        self.configure_signal_button(self.signal_button_43)
        self.channels_enabled_layout.addWidget(self.signal_button_43, 5, 4, 1, 1)
        self.signal_button_44 = QPushButton('{}'.format(44), self)
        self.configure_signal_button(self.signal_button_44)
        self.channels_enabled_layout.addWidget(self.signal_button_44, 5, 5, 1, 1)
        self.signal_button_45 = QPushButton('{}'.format(45), self)
        self.configure_signal_button(self.signal_button_45)
        self.channels_enabled_layout.addWidget(self.signal_button_45, 5, 6, 1, 1)
        self.signal_button_46 = QPushButton('{}'.format(46), self)
        self.configure_signal_button(self.signal_button_46)
        self.channels_enabled_layout.addWidget(self.signal_button_46, 5, 7, 1, 1)

        self.signal_button_47 = QPushButton('{}'.format(47), self)
        self.configure_signal_button(self.signal_button_47)
        self.channels_enabled_layout.addWidget(self.signal_button_47, 6, 0, 1, 1)
        self.signal_button_48 = QPushButton('{}'.format(48), self)
        self.configure_signal_button(self.signal_button_48)
        self.channels_enabled_layout.addWidget(self.signal_button_48, 6, 1, 1, 1)
        self.signal_button_49 = QPushButton('{}'.format(49), self)
        self.configure_signal_button(self.signal_button_49)
        self.channels_enabled_layout.addWidget(self.signal_button_49, 6, 2, 1, 1)
        self.signal_button_50 = QPushButton('{}'.format(50), self)
        self.configure_signal_button(self.signal_button_50)
        self.channels_enabled_layout.addWidget(self.signal_button_50, 6, 3, 1, 1)
        self.signal_button_51 = QPushButton('{}'.format(51), self)
        self.configure_signal_button(self.signal_button_51)
        self.channels_enabled_layout.addWidget(self.signal_button_51, 6, 4, 1, 1)
        self.signal_button_52 = QPushButton('{}'.format(52), self)
        self.configure_signal_button(self.signal_button_52)
        self.channels_enabled_layout.addWidget(self.signal_button_52, 6, 5, 1, 1)
        self.signal_button_53 = QPushButton('{}'.format(53), self)
        self.configure_signal_button(self.signal_button_53)
        self.channels_enabled_layout.addWidget(self.signal_button_53, 6, 6, 1, 1)
        self.signal_button_54 = QPushButton('{}'.format(54), self)
        self.configure_signal_button(self.signal_button_54)
        self.channels_enabled_layout.addWidget(self.signal_button_54, 6, 7, 1, 1)

        self.signal_button_55 = QPushButton('{}'.format(55), self)
        self.configure_signal_button(self.signal_button_55)
        self.channels_enabled_layout.addWidget(self.signal_button_55, 7, 1, 1, 1)
        self.signal_button_56 = QPushButton('{}'.format(56), self)
        self.configure_signal_button(self.signal_button_56)
        self.channels_enabled_layout.addWidget(self.signal_button_56, 7, 2, 1, 1)
        self.signal_button_57 = QPushButton('{}'.format(57), self)
        self.configure_signal_button(self.signal_button_57)
        self.channels_enabled_layout.addWidget(self.signal_button_57, 7, 3, 1, 1)
        self.signal_button_58 = QPushButton('{}'.format(58), self)
        self.configure_signal_button(self.signal_button_58)
        self.channels_enabled_layout.addWidget(self.signal_button_58, 7, 4, 1, 1)
        self.signal_button_59 = QPushButton('{}'.format(59), self)
        self.configure_signal_button(self.signal_button_59)
        self.channels_enabled_layout.addWidget(self.signal_button_59, 7, 5, 1, 1)
        self.signal_button_60 = QPushButton('{}'.format(60), self)
        self.configure_signal_button(self.signal_button_60)
        self.channels_enabled_layout.addWidget(self.signal_button_60, 7, 6, 1, 1)

    @Slot(str)
    def write_log(self, log_text):
        self.log_window.appendPlainText(log_text)
        self.log_window.centerCursor()

    def create_plot_upper_layout(self):
        self.plot_groupbox = QGroupBox(self.plot_tab)
        size_policy_plot = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_plot.setHorizontalStretch(0)
        size_policy_plot.setVerticalStretch(5)
        size_policy_plot_flag = self.plot_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_plot.setHeightForWidth(size_policy_plot_flag)
        self.plot_groupbox.setSizePolicy(size_policy_plot)
        self.plot_grid = QGridLayout(self.plot_groupbox)
        self.plot = PlotDialog(self.plot_grid)
        self.plot_tab_layout.addWidget(self.plot_groupbox)

    def create_plot_bottom_layout(self):
        self.plot_bot_groupbox = QGroupBox(self.plot_tab)
        size_policy_bot_groupbox = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_bot_groupbox.setHorizontalStretch(0)
        size_policy_bot_groupbox.setVerticalStretch(1)
        size_policy_bot_groupbox_flag = self.plot_bot_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_bot_groupbox.setHeightForWidth(size_policy_bot_groupbox_flag)
        self.plot_bot_groupbox.setSizePolicy(size_policy_bot_groupbox)

        self.plot_bottom_layout = QHBoxLayout(self.plot_bot_groupbox)

        # Groupbox for highlighting elements (spikes, bursts, etc.)
        self.plot_highlight_groupbox = QGroupBox(self.plot_bot_groupbox, title="Highlight")
        size_policy_highlight = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_highlight.setHorizontalStretch(1)
        size_policy_highlight.setVerticalStretch(0)
        size_policy_highlight_flag = self.plot_highlight_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_highlight.setHeightForWidth(size_policy_highlight_flag)
        self.plot_highlight_groupbox.setSizePolicy(size_policy_highlight)
        self.plot_highlight_groupbox.setFont(self.gbox_font)

        self.plot_highlight_grid = QGridLayout(self.plot_highlight_groupbox)
        self.plot_highlight_grid.setContentsMargins(50, -1, 50, -1)

        self.highlight_none_rb = QRadioButton(self.plot_highlight_groupbox, text="None")
        self.highlight_none_rb.toggled.connect(lambda: self.remove_plot_data())
        self.plot_highlight_grid.addWidget(self.highlight_none_rb, 0, 0, 1, 1)
        self.highlight_spike_rb = QRadioButton(self.plot_highlight_groupbox, text="Spikes")
        self.highlight_spike_rb.toggled.connect(lambda: self.add_plot_spike_data())
        self.plot_highlight_grid.addWidget(self.highlight_spike_rb, 1, 0, 1, 1)
        self.highlight_burst_rb = QRadioButton(self.plot_highlight_groupbox, text="Bursts")
        self.highlight_burst_rb.toggled.connect(lambda: self.add_plot_burst_data())
        self.plot_highlight_grid.addWidget(self.highlight_burst_rb, 1, 1, 1, 1)
        self.highlight_burstlet_rb = QRadioButton(self.plot_highlight_groupbox, text="Burstlets")
        self.highlight_burstlet_rb.toggled.connect(lambda: self.add_plot_burstlet_data())
        self.plot_highlight_grid.addWidget(self.highlight_burstlet_rb, 0, 1, 1, 1)
        if not hasattr(self, 'data'):
            self.highlight_none_rb.setCheckable(False)
            self.highlight_spike_rb.setCheckable(False)
            self.highlight_burstlet_rb.setCheckable(False)
            self.highlight_burst_rb.setCheckable(False)

        self.plot_bottom_layout.addWidget(self.plot_highlight_groupbox)

        # Navigation groupbox
        self.plot_navigation_groupbox = QGroupBox(self.plot_bot_groupbox, title="Navigation")
        size_policy_navigation = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_navigation.setHorizontalStretch(2)
        size_policy_navigation.setVerticalStretch(0)
        size_policy_navigation_flag = self.plot_navigation_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_navigation.setHeightForWidth(size_policy_navigation_flag)
        self.plot_navigation_groupbox.setSizePolicy(size_policy_navigation)
        self.plot_navigation_groupbox.setFont(self.gbox_font)

        self.plot_navigation_layout = QHBoxLayout(self.plot_navigation_groupbox)

        self.plot_channel_frame = QFrame(self.plot_navigation_groupbox)
        self.plot_channel_frame.setAutoFillBackground(False)
        self.plot_channel_frame.setFrameShape(QFrame.NoFrame)
        self.plot_channel_frame.setFrameShadow(QFrame.Raised)
        self.plot_channel_frame_layout = QVBoxLayout(self.plot_channel_frame)
        self.plot_channel_frame_layout.setContentsMargins(80, -1, 80, -1)
        self.plot_channel_label = QLabel(self.plot_channel_frame, text="# Channel")
        self.plot_channel_frame_layout.addWidget(self.plot_channel_label)
        self.plot_channel_combobox = QComboBox(self.plot_channel_frame)
        signal_numbers = list(range(1, 61))
        self.plot_channel_combobox.addItems([str(num) for num in signal_numbers])
        self.plot_channel_combobox.currentIndexChanged.connect(lambda: self.plot_channel_change())
        self.plot_channel_frame_layout.addWidget(self.plot_channel_combobox)
        self.plot_navigation_layout.addWidget(self.plot_channel_frame)

        self.plot_navigation_button_frame = QFrame(self.plot_navigation_groupbox)
        self.plot_navigation_button_layout = QHBoxLayout(self.plot_navigation_button_frame)
        self.plot_navigation_button_layout.setContentsMargins(50, 20, 50, 9)
        self.plot_navigation_back_button = QPushButton(self.plot_navigation_button_frame, text="<")
        size_policy_navigation_button = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        size_policy_navigation_button.setHorizontalStretch(0)
        size_policy_navigation_button.setVerticalStretch(0)
        size_policy_navigation_button_flag = self.plot_navigation_back_button.sizePolicy().hasHeightForWidth()
        size_policy_navigation_button.setHeightForWidth(size_policy_navigation_button_flag)
        self.plot_navigation_back_button.setSizePolicy(size_policy_navigation_button)
        self.plot_navigation_back_button.setEnabled(False)
        if self.highlight_none_rb.isChecked():
            self.plot_navigation_back_button.setEnabled(False)
        self.plot_navigation_back_button.clicked.connect(lambda: self.change_plot_range_prev())
        self.plot_navigation_button_layout.addWidget(self.plot_navigation_back_button)
        self.plot_navigation_next_button = QPushButton(self.plot_navigation_button_frame, text=">")
        size_policy_navigation_button_flag = self.plot_navigation_next_button.sizePolicy().hasHeightForWidth()
        size_policy_navigation_button.setHeightForWidth(size_policy_navigation_button_flag)
        self.plot_navigation_next_button.setSizePolicy(size_policy_navigation_button)
        self.plot_navigation_next_button.setEnabled(False)
        self.plot_navigation_next_button.clicked.connect(lambda: self.change_plot_range_next())
        self.plot_navigation_button_layout.addWidget(self.plot_navigation_next_button)
        self.plot_navigation_layout.addWidget(self.plot_navigation_button_frame)

        self.plot_item_frame = QFrame(self.plot_navigation_groupbox)
        self.plot_item_layout = QVBoxLayout(self.plot_item_frame)
        self.plot_item_layout.setContentsMargins(80, -1, 80, -1)
        self.plot_item_label = QLabel(self.plot_item_frame, text="# Item")
        self.plot_item_layout.addWidget(self.plot_item_label)
        self.plot_item_spinbox = QLabel(self.plot_item_frame, text="0")
        self.plot_item_layout.addWidget(self.plot_item_spinbox)
        self.plot_navigation_layout.addWidget(self.plot_item_frame)

        self.plot_bottom_layout.addWidget(self.plot_navigation_groupbox)

        self.plot_tab_layout.addWidget(self.plot_bot_groupbox)

    def plot_channel_change(self):
        self.plot_item_spinbox.setText("0")
        if getattr(self.plot, 'spike_id', None) is not None:
            self.plot.spike_id = None
        if getattr(self.plot, 'burstlet_id', None) is not None:
            self.plot.burstlet_id = None
        if getattr(self.plot, 'burst_id', None) is not None:
            self.plot.burst_id = None
        self.plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(0, 1)

    def remove_plot_data(self):
        if self.highlight_none_rb.isChecked():
            self.plot_navigation_back_button.setEnabled(False)
            self.plot_navigation_next_button.setEnabled(False)
        elif self.highlight_spike_rb.isChecked() or self.highlight_burstlet_rb.isChecked() \
                or self.highlight_burst_rb.isChecked():
            self.plot_navigation_back_button.setEnabled(True)
            self.plot_navigation_next_button.setEnabled(True)
        self.plot.remove_data(self.plot_grid)

    def add_plot_spike_data(self):
        if self.highlight_spike_rb.isChecked():
            self.remove_plot_data()
            self.plot.add_spike_data(self.plot_grid)

    def add_plot_burstlet_data(self):
        if self.highlight_burstlet_rb.isChecked():
            self.remove_plot_data()
            self.plot.add_burstlet_data(self.plot_grid)

    def add_plot_burst_data(self):
        if self.highlight_burst_rb.isChecked():
            self.remove_plot_data()
            self.plot.add_burst_data(self.plot_grid)

    def change_plot_range_next(self):
        if self.highlight_spike_rb.isChecked():
            data_type = 'spike'
        if self.highlight_burstlet_rb.isChecked():
            data_type = 'burstlet'
        if self.highlight_burst_rb.isChecked():
            data_type = 'burst'
        signal_id = int(self.plot_channel_combobox.currentText())
        self.plot.change_range_next(self.plot_grid, data_type, signal_id)
        if data_type == 'spike':
            self.plot_item_spinbox.setText(str(self.plot.spike_id + 1))
        if data_type == 'burstlet':
            self.plot_item_spinbox.setText(str(self.plot.burstlet_id + 1))
        if data_type == 'burst':
            self.plot_item_spinbox.setText(str(self.plot.burst_id + 1))

    def change_plot_range_prev(self):
        if self.highlight_spike_rb.isChecked():
            data_type = 'spike'
        if self.highlight_burstlet_rb.isChecked():
            data_type = 'burstlet'
        if self.highlight_burst_rb.isChecked():
            data_type = 'burst'
        signal_id = int(self.plot_channel_combobox.currentText())
        self.plot.change_range_prev(self.plot_grid, data_type, signal_id)
        if data_type == 'spike':
            self.plot_item_spinbox.setText(str(self.plot.spike_id + 1))
        if data_type == 'burstlet':
            self.plot_item_spinbox.setText(str(self.plot.burstlet_id + 1))
        if data_type == 'burst':
            self.plot_item_spinbox.setText(str(self.plot.burst_id + 1))

    def create_stat_layout(self):
        self.stat_left_groupbox = QGroupBox(self.stat_tab)
        size_policy_stat_left = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_stat_left.setHorizontalStretch(4)
        size_policy_stat_left.setVerticalStretch(0)
        size_policy_stat_left_flag = self.stat_left_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_stat_left.setHeightForWidth(size_policy_stat_left_flag)
        self.stat_left_groupbox.setSizePolicy(size_policy_stat_left)
        self.stat_left_groupbox_layout = QGridLayout(self.stat_left_groupbox)
        self.stat_left_groupbox_layout.setHorizontalSpacing(0)
        self.stat_left_groupbox_layout.setVerticalSpacing(2)
        self.stat_tab_layout.addWidget(self.stat_left_groupbox)

        self.stat_right_groupbox = QGroupBox(self.stat_tab)
        size_policy_stat_right = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_stat_right.setHorizontalStretch(1)
        size_policy_stat_right.setVerticalStretch(0)
        size_policy_stat_right_flag = self.stat_right_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_stat_right.setHeightForWidth(size_policy_stat_right_flag)
        self.stat_right_groupbox.setSizePolicy(size_policy_stat_right)
        self.stat_right_groupbox_layout = QGridLayout(self.stat_right_groupbox)
        self.stat_tab_layout.addWidget(self.stat_right_groupbox)

        self.stat = StatDialog(self.stat_left_groupbox_layout, self.stat_right_groupbox_layout)

    def create_char_layout(self):
        self.char_global_table = QTableWidget(self.char_tab)
        size_policy_char_left = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_char_left.setHorizontalStretch(1)
        size_policy_char_left.setVerticalStretch(0)
        size_policy_char_left_flag = self.char_global_table.sizePolicy().hasHeightForWidth()
        size_policy_char_left.setHeightForWidth(size_policy_char_left_flag)
        self.char_global_table.setSizePolicy(size_policy_char_left)
        headers = ['Characteristic', 'Value']
        self.char_global_table.setColumnCount(2)
        self.char_global_table.setHorizontalHeaderLabels(headers)
        self.char_global_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.char_global_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.char_global_table.verticalHeader().setVisible(False)
        self.char_tab_layout.addWidget(self.char_global_table, 1, 0, 1, 1)

        self.char_channel_table = QTableWidget(self.char_tab)
        size_policy_char_center = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_char_center.setHorizontalStretch(2)
        size_policy_char_center.setVerticalStretch(0)
        size_policy_char_center_flag = self.char_channel_table.sizePolicy().hasHeightForWidth()
        size_policy_char_center.setHeightForWidth(size_policy_char_center_flag)
        self.char_channel_table.setSizePolicy(size_policy_char_center)
        self.char_channel_table.setRowCount(60)
        self.char_channel_table.verticalHeader().setVisible(False)
        self.char_tab_layout.addWidget(self.char_channel_table, 1, 2, 1, 1)

        self.char_burst_table = QTableWidget(self.char_tab)
        size_policy_char_right = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_char_right.setHorizontalStretch(2)
        size_policy_char_right.setVerticalStretch(0)
        size_policy_char_right_flag = self.char_burst_table.sizePolicy().hasHeightForWidth()
        size_policy_char_right.setHeightForWidth(size_policy_char_right_flag)
        self.char_burst_table.setSizePolicy(size_policy_char_right)
        self.char_burst_table.verticalHeader().setVisible(False)
        self.char_tab_layout.addWidget(self.char_burst_table, 1, 3, 1, 1)

        self.char_time_table = QTableWidget(self.char_tab)
        size_policy_char_right = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_char_right.setHorizontalStretch(2)
        size_policy_char_right.setVerticalStretch(0)
        size_policy_char_right_flag = self.char_time_table.sizePolicy().hasHeightForWidth()
        size_policy_char_right.setHeightForWidth(size_policy_char_right_flag)
        self.char_time_table.setSizePolicy(size_policy_char_right)
        self.char_time_table.verticalHeader().setVisible(False)
        self.char_tab_layout.addWidget(self.char_time_table, 1, 4, 1, 1)

        self.char_global_label = QLabel(text="Global characteristics")
        self.char_global_label.setFont(self.gbox_font)
        self.char_tab_layout.addWidget(self.char_global_label, 0, 0, 1, 1)

        self.char_channel_label = QLabel(text="Channel characteristics")
        self.char_channel_label.setFont(self.gbox_font)
        self.char_tab_layout.addWidget(self.char_channel_label, 0, 2, 1, 1)

        self.char_burst_label = QLabel(text="Burst characteristics")
        self.char_burst_label.setFont(self.gbox_font)
        self.char_tab_layout.addWidget(self.char_burst_label, 0, 3, 1, 1)

        self.char_time_label = QLabel(text="Time characteristics")
        self.char_time_label.setFont(self.gbox_font)
        self.char_tab_layout.addWidget(self.char_time_label, 0, 4, 1, 1)

    def choose_burst_cell(self):
        curr_row = self.graph_table.currentRow()
        cell_value = self.graph_table.item(curr_row, 0).text()
        burst_id = int(cell_value)
        self.burst_id_spinbox.setValue(burst_id)

    def create_graph_layout(self):
        self.graph_info_panel = QWidget(self.graph_tab)
        size_policy_graph_left = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_graph_left.setHorizontalStretch(1)
        size_policy_graph_left.setVerticalStretch(0)
        size_policy_graph_left_flag = self.graph_info_panel.sizePolicy().hasHeightForWidth()
        size_policy_graph_left.setHeightForWidth(size_policy_graph_left_flag)
        self.graph_info_panel.setSizePolicy(size_policy_graph_left)
        self.graph_info_panel_layout = QGridLayout(self.graph_info_panel)

        self.graph_table = QTableWidget(self.graph_info_panel)
        self.graph_table.cellClicked.connect(lambda: self.choose_burst_cell())
        self.graph_info_panel_layout.addWidget(self.graph_table, 0, 0, 1, 1)
        self.graph_table.verticalHeader().setVisible(False)

        self.graph_params_panel = QWidget(self.graph_info_panel)
        self.graph_params_panel_layout = QVBoxLayout(self.graph_params_panel)

        self.graph_params_groupbox = QGroupBox(self.graph_params_panel, title="Graph Parameters")
        size_policy_graph_params = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_graph_params.setHorizontalStretch(0)
        size_policy_graph_params.setVerticalStretch(2)
        size_policy_graph_params_flag = self.graph_params_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_graph_params.setHeightForWidth(size_policy_graph_params_flag)
        self.graph_params_groupbox.setSizePolicy(size_policy_graph_params)
        self.graph_params_groupbox.setFont(self.gbox_font)
        self.graph_params_groupbox_layout = QGridLayout(self.graph_params_groupbox)

        self.graph_delta_param_label = QLabel(self.graph_params_groupbox, text="Delta, ms")
        self.graph_params_groupbox_layout.addWidget(self.graph_delta_param_label, 0, 0, 1, 1)
        self.graph_delta_param_label.setToolTip("Size of delayed spike detection step")
        self.graph_delta_param_label.setToolTipDuration(1000)

        self.graph_params_delta_spinbox = QDoubleSpinBox(self.graph_params_groupbox)
        self.graph_params_delta_spinbox.setMinimum(0)
        self.graph_params_delta_spinbox.setMaximum(10)
        self.graph_params_delta_spinbox.setValue(0.05)
        self.graph_params_delta_spinbox.valueChanged.connect(self.delta_spinbox_change)
        self.graph_params_groupbox_layout.addWidget(self.graph_params_delta_spinbox, 0, 1, 1, 1)

        self.graph_tau_param_label = QLabel(self.graph_params_groupbox, text="Num frames")
        self.graph_params_groupbox_layout.addWidget(self.graph_tau_param_label, 1, 0, 1, 1)
        self.graph_tau_param_label.setToolTip("Maximum correlation time-shift in frames")
        self.graph_tau_param_label.setToolTipDuration(1000)

        self.graph_params_tau_spinbox = QSpinBox(self.graph_params_groupbox)
        self.graph_params_tau_spinbox.setMinimum(0)
        self.graph_params_tau_spinbox.setMaximum(1000)
        self.graph_params_tau_spinbox.setValue(50)
        self.graph_params_tau_spinbox.valueChanged.connect(self.tau_spinbox_change)
        self.graph_params_groupbox_layout.addWidget(self.graph_params_tau_spinbox, 1, 1, 1, 1)

        self.graph_cutoff_param_label = QLabel(self.graph_params_groupbox, text="Cutoff top, %")
        self.graph_params_groupbox_layout.addWidget(self.graph_cutoff_param_label, 2, 0, 1, 1)
        self.graph_cutoff_param_label.setToolTip("Choose top % of C_ij")
        self.graph_cutoff_param_label.setToolTipDuration(1000)

        self.graph_params_cutoff_spinbox = QSpinBox(self.graph_params_groupbox)
        self.graph_params_cutoff_spinbox.setMinimum(0)
        self.graph_params_cutoff_spinbox.setMaximum(100)
        self.graph_params_cutoff_spinbox.setValue(5)
        self.graph_params_cutoff_spinbox.valueChanged.connect(self.cutoff_spinbox_change)
        self.graph_params_groupbox_layout.addWidget(self.graph_params_cutoff_spinbox, 2, 1, 1, 1)

        self.graph_params_panel_layout.addWidget(self.graph_params_groupbox)

        self.graph_navigation_groupbox = QGroupBox(self.graph_params_panel, title="Navigation")
        size_policy_graph_navigation = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_graph_navigation.setHorizontalStretch(0)
        size_policy_graph_navigation.setVerticalStretch(1)
        size_policy_graph_navigation_flag = self.graph_navigation_groupbox.sizePolicy().hasHeightForWidth()
        size_policy_graph_navigation.setHeightForWidth(size_policy_graph_navigation_flag)
        self.graph_navigation_groupbox.setSizePolicy(size_policy_graph_navigation)
        self.graph_navigation_groupbox.setFont(self.gbox_font)
        self.graph_navigation_groupbox_layout = QGridLayout(self.graph_navigation_groupbox)
        self.graph_navigation_groupbox_layout.setContentsMargins(50, 20, 50, 20)
        self.graph_navigation_groupbox_layout.setSpacing(40)

        self.burst_id_label = QLabel(self.graph_navigation_groupbox, text="Burst")
        self.graph_navigation_groupbox_layout.addWidget(self.burst_id_label, 0, 0, 1, 1)

        self.burst_id_spinbox = QSpinBox(self.graph_navigation_groupbox)
        self.burst_id_spinbox.setDisabled(True)
        self.burst_id_spinbox.setValue(1)
        self.burst_id_spinbox.valueChanged.connect(self.burst_id_spinbox_change)
        self.burst_id_spinbox.editingFinished.connect(self.spinbox_change)
        self.graph_navigation_groupbox_layout.addWidget(self.burst_id_spinbox, 0, 1, 1, 1)

        self.build_graph_btn = QPushButton(self.graph_navigation_groupbox, text="Build Graph")
        size_policy_build_graph_btn = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        size_policy_build_graph_btn.setHorizontalStretch(0)
        size_policy_build_graph_btn.setVerticalStretch(0)
        size_policy_build_graph_btn_flag = self.build_graph_btn.sizePolicy().hasHeightForWidth()
        size_policy_build_graph_btn.setHeightForWidth(size_policy_build_graph_btn_flag)
        self.build_graph_btn.setSizePolicy(size_policy_build_graph_btn)
        self.build_graph_btn.setDisabled(True)
        self.build_graph_btn.clicked.connect(lambda: self.process_graph())

        self.graph_navigation_groupbox_layout.addWidget(self.build_graph_btn, 1, 0, 1, 2)

        self.graph_info_panel_layout.addWidget(self.graph_params_panel, 0, 1, 1, 1)

        self.graph_params_panel_layout.addWidget(self.graph_navigation_groupbox)
        self.graph_tab_layout.addWidget(self.graph_info_panel)

        self.graph_picture_panel = QWidget(self.graph_tab)
        size_policy_graph_right = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy_graph_right.setHorizontalStretch(1)
        size_policy_graph_right.setVerticalStretch(0)
        size_policy_graph_right_flag = self.graph_picture_panel.sizePolicy().hasHeightForWidth()
        size_policy_graph_right.setHeightForWidth(size_policy_graph_right_flag)
        self.graph_picture_panel.setSizePolicy(size_policy_graph_right)
        self.graph_picture_panel_layout = QVBoxLayout(self.graph_picture_panel)

        self.graph_picture = PhotoViewer(self.graph_picture_panel)
        self.graph_picture_panel_layout.addWidget(self.graph_picture)

        self.graph_tab_layout.addWidget(self.graph_picture_panel)

    def create_logging_layout(self):
        self.main_logging_groupbox = QGroupBox(self.central_widget)
        main_logging_size_policy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Ignored)
        main_logging_size_policy.setHorizontalStretch(0)
        main_logging_size_policy.setVerticalStretch(1)
        policy_flag = self.main_logging_groupbox.sizePolicy().hasHeightForWidth()
        main_logging_size_policy.setHeightForWidth(policy_flag)
        self.main_logging_groupbox.setSizePolicy(main_logging_size_policy)

        self.logger_font = QFont()
        self.logger_font.setPointSize(10)

        self.main_logging_groupbox.setFont(self.logger_font)
        self.log_groupbox_layout = QHBoxLayout(self.main_logging_groupbox)

        self.progressBar = QProgressBar(self.main_logging_groupbox)
        self.progressBar.setValue(100)
        self.log_groupbox_layout.addWidget(self.progressBar)

        self.logger = logging.getLogger('log')
        self.log_handler = ThreadLogger()
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', "%Y-%m-%d %H:%M:%S"))
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.INFO)

        self.log_window = QPlainTextEdit(self.main_logging_groupbox)
        self.log_window.setReadOnly(True)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(1)
        size_policy_flag = self.log_window.sizePolicy().hasHeightForWidth()
        size_policy.setHeightForWidth(size_policy_flag)
        self.log_window.setSizePolicy(size_policy)
        self.log_groupbox_layout.addWidget(self.log_window)

        self.log_handler.log.signal.connect(self.write_log)

        self.main_layout.addWidget(self.main_logging_groupbox)


class AboutDialog(QDialog):
    """Create the necessary elements to show helpful text in a dialog."""

    def __init__(self, parent=None):
        """Display a dialog that shows application information."""
        super(AboutDialog, self).__init__(parent)

        self.setWindowTitle('About')
        # help_icon = pkg_resources.resource_filename('meaxtd.images', 'ic_help_black_48dp_1x.png')
        # self.setWindowIcon(QIcon(help_icon))
        self.resize(300, 200)

        author = QLabel('Aaron Blare')
        author.setAlignment(Qt.AlignCenter)

        # icons = QLabel('Material design icons created by Google')
        # icons.setAlignment(Qt.AlignCenter)

        github = QLabel('GitHub: AaronBlare')
        github.setAlignment(Qt.AlignCenter)

        email = QLabel('Email: kalyakulina.alena@gmail.com')
        email.setAlignment(Qt.AlignCenter)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignVCenter)

        self.layout.addWidget(author)
        # self.layout.addWidget(icons)
        self.layout.addWidget(github)
        self.layout.addWidget(email)

        self.setLayout(self.layout)


class PlotDialog(QDialog):

    def __init__(self, plot_grid, data=None):
        super().__init__()
        self.data = data
        self.init_ui(plot_grid)

    def set_data(self, data, start, end):
        self.data = data
        self.start = start
        self.end = end

    def init_ui(self, plot_grid):
        self.fill_grid_layout(plot_grid)

    def fill_grid_layout(self, plot_grid):
        num_rows = 10
        num_columns = 6

        plots = []

        for row_id in range(0, num_rows):
            plot_grid.setColumnStretch(row_id, num_columns)
        for column_id in range(0, num_columns):
            plot_grid.setRowStretch(column_id, num_rows)

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
                plot_grid.addWidget(curr_plot, col_id, row_id)
                plots.append(curr_plot)
                if curr_id > 0:
                    plots[curr_id - 1].getViewBox().setXLink(plots[curr_id])
                    plots[curr_id - 1].getViewBox().setYLink(plots[curr_id])

    def plot_signals(self, plot_grid):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                curve = HDF5PlotXY()
                curr_data = self.data.stream[:, curr_id]
                curve.setHDF5(self.data.time, curr_data, self.data.fs)
                plot_grid.layout().itemAtPosition(col_id, row_id).widget().addItem(curve)

    def remove_data(self, plot_grid):
        if getattr(self, 'spike_id', None) is not None:
            self.spike_id = None
        if getattr(self, 'burstlet_id', None) is not None:
            self.burstlet_id = None
        if getattr(self, 'burst_id', None) is not None:
            self.burst_id = None
        curr_curves = plot_grid.layout().itemAtPosition(0, 0).widget().plotItem.curves
        if len(curr_curves) > 1:
            num_rows = 10
            num_columns = 6
            for curve_id in range(len(curr_curves) - 1, 0, -1):
                for col_id in range(0, num_columns):
                    for row_id in range(0, num_rows):
                        curr_plot_item = plot_grid.layout().itemAtPosition(col_id, row_id).widget().plotItem
                        curr_plot_item.removeItem(curr_plot_item.curves[curve_id])

    def remove_signals(self, plot_grid):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_plot_item = plot_grid.layout().itemAtPosition(col_id, row_id).widget().plotItem
                curr_plot_item.removeItem(curr_plot_item.curves[0])

    def add_spike_data(self, plot_grid):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                spikes = HDF5PlotXY()
                curr_spike_data = self.data.spike_stream[curr_id]
                spikes.setHDF5(self.data.time, curr_spike_data, self.data.fs, pen=pg.mkPen(color='k', width=2))
                plot_grid.layout().itemAtPosition(col_id, row_id).widget().addItem(spikes)

    def add_burstlet_data(self, plot_grid):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                burstlets = HDF5PlotXY()
                curr_burstlet_data = self.data.burstlet_stream[curr_id]
                burstlets.setHDF5(self.data.time, curr_burstlet_data, self.data.fs,
                                  pen=pg.mkPen(color='g', width=2))
                plot_grid.layout().itemAtPosition(col_id, row_id).widget().addItem(burstlets)

    def add_burst_data(self, plot_grid):
        num_rows = 10
        num_columns = 6
        for col_id in range(0, num_columns):
            for row_id in range(0, num_rows):
                curr_id = col_id * num_rows + row_id
                bursts = HDF5PlotXY()
                curr_burst_data = self.data.burst_stream[curr_id]
                bursts.setHDF5(self.data.time, curr_burst_data, self.data.fs,
                               pen=pg.mkPen(color='b', width=2))
                plot_grid.layout().itemAtPosition(col_id, row_id).widget().addItem(bursts)
                bursts_borders = HDF5PlotXY()
                # curr_burst_borders = self.data.burst_borders[curr_id]
                # bursts_borders.setHDF5(self.data.time, curr_burst_borders, self.data.fs,
                #                       pen=pg.mkPen(color='r', width=1.5))
                plot_grid.layout().itemAtPosition(col_id, row_id).widget().addItem(bursts_borders)

    def change_range_next(self, plot_grid, data_type, signal_id):
        start_index = np.where(self.data.time == self.start * 60)[0][0]
        curr_signal = signal_id - 1
        if data_type == 'spike':
            if getattr(self, 'spike_id', None) is None:
                self.spike_id = 0
            else:
                if self.spike_id < len(self.data.spikes[curr_signal]) - 1:
                    self.spike_id += 1
            if curr_signal in self.data.spikes and self.data.spikes[curr_signal].size > 0:
                curr_spike = self.data.spikes[curr_signal][self.spike_id] + start_index
                curr_spike_amplitude = self.data.spikes_amplitudes[curr_signal][self.spike_id]
                left_border = max(0, self.data.time[curr_spike] - 0.5)
                right_border = min(len(self.data.time), self.data.time[curr_spike] + 0.5)
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
                if curr_spike_amplitude > 0.004:
                    top_border = max(0.002, curr_spike_amplitude / 2 + 0.0001)
                    bottom_border = min(-0.002, curr_spike_amplitude / 2 - 0.0001)
                    plot_grid.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if data_type == 'burstlet':
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            else:
                if self.burstlet_id < len(self.data.burstlets[curr_signal]) - 1:
                    self.burstlet_id += 1
            if curr_signal in self.data.burstlets and len(self.data.burstlets[curr_signal]) > 0:
                curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_len = self.data.time[curr_burstlet_end] - self.data.time[curr_burstlet_start]
                if curr_burstlet_len > 1:
                    left_border = self.data.time[curr_burstlet_start] - 0.1
                    right_border = self.data.time[curr_burstlet_end] + 0.1
                else:
                    left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) / 2
                    right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) / 2
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
                curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
                if curr_burstlet_amplitude > 0.004:
                    top_border = max(0.002, curr_burstlet_amplitude / 2 + 0.0001)
                    bottom_border = min(-0.002, curr_burstlet_amplitude / 2 - 0.0001)
                    plot_grid.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if data_type == 'burst':
            if getattr(self, 'burst_id', None) is None:
                self.burst_id = 0
            else:
                if self.burst_id < len(self.data.bursts_starts[curr_signal]) - 1:
                    self.burst_id += 1
            if curr_signal in self.data.bursts_starts and len(self.data.bursts_starts[curr_signal]) > 0:
                curr_burst_start = self.data.bursts_starts[curr_signal][self.burst_id] + start_index
                curr_burst_end = self.data.bursts_ends[curr_signal][self.burst_id] + start_index
                curr_burst_len = self.data.time[curr_burst_end] - self.data.time[curr_burst_start]
                if curr_burst_len > 1:
                    left_border = self.data.time[curr_burst_start] - 0.1
                    right_border = self.data.time[curr_burst_end] + 0.1
                else:
                    left_border = self.data.time[curr_burst_start] - (1 - curr_burst_len) / 2
                    right_border = self.data.time[curr_burst_end] + (1 - curr_burst_len) / 2
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)

    def change_range_prev(self, plot_grid, data_type, signal_id):
        start_index = np.where(self.data.time == self.start * 60)[0][0]
        curr_signal = signal_id - 1
        if data_type == 'spike':
            if getattr(self, 'spike_id', None) is None:
                self.spike_id = 0
            else:
                if self.spike_id > 0:
                    self.spike_id -= 1
            if curr_signal in self.data.spikes and self.data.spikes[curr_signal].size > 0:
                curr_spike = self.data.spikes[curr_signal][self.spike_id] + start_index
                curr_spike_amplitude = self.data.spikes_amplitudes[curr_signal][self.spike_id]
                left_border = max(0, self.data.time[curr_spike] - 0.5)
                right_border = min(len(self.data.time), self.data.time[curr_spike] + 0.5)
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
                if curr_spike_amplitude > 0.004:
                    top_border = max(0.002, curr_spike_amplitude / 2 + 0.0001)
                    bottom_border = min(-0.002, curr_spike_amplitude / 2 - 0.0001)
                    plot_grid.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if data_type == 'burstlet':
            if getattr(self, 'burstlet_id', None) is None:
                self.burstlet_id = 0
            else:
                if self.burstlet_id > 0:
                    self.burstlet_id -= 1
            if curr_signal in self.data.burstlets and len(self.data.burstlets[curr_signal]) > 0:
                curr_burstlet = self.data.burstlets[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_start = self.data.burstlets_starts[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_end = self.data.burstlets_ends[curr_signal][self.burstlet_id] + start_index
                curr_burstlet_len = curr_burstlet_end - curr_burstlet_start
                if curr_burstlet_len > 1:
                    left_border = self.data.time[curr_burstlet_start] - 0.1
                    right_border = self.data.time[curr_burstlet_end] + 0.1
                else:
                    left_border = self.data.time[curr_burstlet_start] - (1 - curr_burstlet_len) / 2
                    right_border = self.data.time[curr_burstlet_end] + (1 - curr_burstlet_len) / 2
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)
                curr_burstlet_amplitude = self.data.burstlets_amplitudes[curr_signal][self.burstlet_id]
                if curr_burstlet_amplitude > 0.004:
                    top_border = max(0.002, curr_burstlet_amplitude / 2 + 0.0001)
                    bottom_border = min(-0.002, curr_burstlet_amplitude / 2 - 0.0001)
                    plot_grid.layout().itemAtPosition(0, 0).widget().setYRange(top_border, bottom_border)
        if data_type == 'burst':
            if getattr(self, 'burst_id', None) is None:
                self.burst_id = 0
            else:
                if self.burst_id > 0:
                    self.burst_id -= 1
            if curr_signal in self.data.bursts_starts and len(self.data.bursts_starts[curr_signal]) > 0:
                curr_burst_start = self.data.bursts_starts[curr_signal][self.burst_id] + start_index
                curr_burst_end = self.data.bursts_ends[curr_signal][self.burst_id] + start_index
                curr_burst_len = self.data.time[curr_burst_end] - self.data.time[curr_burst_start]
                if curr_burst_len > 1:
                    left_border = self.data.time[curr_burst_start] - 0.1
                    right_border = self.data.time[curr_burst_end] + 0.1
                else:
                    left_border = self.data.time[curr_burst_start] - (1 - curr_burst_len) / 2
                    right_border = self.data.time[curr_burst_end] + (1 - curr_burst_len) / 2
                plot_grid.layout().itemAtPosition(0, 0).widget().setXRange(left_border, right_border)


class StatDialog(QDialog):

    def __init__(self, left_layout, right_layout, data=None):
        super().__init__()
        self.data = data
        self.init_ui(left_layout, right_layout)

    def set_data(self, data, start, end):
        self.data = data
        self.start = start
        self.end = end

    def set_threshold(self, thr):
        self.TSR_threshold = thr

    def init_ui(self, left_layout, right_layout):
        self.configure_left(left_layout)
        self.configure_right(right_layout)

    def configure_left(self, left_layout):

        t_plot = pg.PlotWidget()
        t_plot.enableAutoRange(False, False)
        t_plot.setXRange(0, 60)
        t_plot.setLabel('left', 'TSR, spikes per bin')
        t_plot.setLabel('bottom', 'Time (s)')
        t_plot.setLimits(yMin=-1, yMax=500, minYRange=1)
        if self.data:
            if self.data.spikes:
                tplot = tsr_plot(self.data)
                t_plot.addItem(tplot)
        left_layout.addWidget(t_plot, 0, 0)

        r_plot = pg.PlotWidget()
        r_plot.enableAutoRange(False, False)
        r_plot.setXRange(0, 60)
        t_plot.setYRange(0, 60.5)
        r_plot.setLabel('left', 'Electrode')
        r_plot.setLabel('bottom', 'Time (s)')
        r_plot.setLimits(yMin=0, yMax=62, minYRange=1)
        if self.data:
            if self.data.spikes:
                rplot = raster_plot(self.data)
                r_plot.addItem(rplot)
        r_plot.getViewBox().setXLink(t_plot)
        left_layout.addWidget(r_plot, 1, 0)

    def configure_right(self, right_layout):

        act_plot = pg.PlotWidget(title='Burst activation')
        act_plot.setXRange(0, 8)
        act_plot.setYRange(0, 8)
        act_plot.getViewBox().invertY(True)
        act_plot.setLabel('left', 'Electrode')
        act_plot.setLabel('bottom', 'Electrode')
        right_layout.addWidget(act_plot, 0, 0)

        deact_plot = pg.PlotWidget(title='Burst deactivation')
        deact_plot.setXRange(0, 8)
        deact_plot.setYRange(0, 8)
        deact_plot.getViewBox().invertY(True)
        deact_plot.setLabel('left', 'Electrode')
        deact_plot.setLabel('bottom', 'Electrode')
        right_layout.addWidget(deact_plot, 1, 0)

    def plot_raster(self, left_layout):
        rplot = raster_plot(self.data, self.start)
        left_layout.layout().itemAtPosition(1, 0).widget().addItem(rplot)
        left_layout.layout().itemAtPosition(1, 0).widget().setLimits(xMin=0, xMax=self.data.time[-1])
        left_layout.layout().itemAtPosition(1, 0).widget().setXRange(0, self.data.time[-1])

    def plot_tsr(self, left_layout):
        tplot = tsr_plot(self.data)
        left_layout.layout().itemAtPosition(0, 0).widget().addItem(tplot)
        left_layout.layout().itemAtPosition(0, 0).widget().plotItem.items[0].opts['symbol'] = None
        left_layout.layout().itemAtPosition(0, 0).widget().plotItem.items[0].opts['symbolPen'] = None
        left_layout.layout().itemAtPosition(0, 0).widget().plotItem.items[0].opts['symbolBrush'] = None
        left_layout.layout().itemAtPosition(0, 0).widget().plotItem.items[0].opts['symbolSize'] = None
        if hasattr(self, 'TSR_threshold'):
            tplot_thr = tsr_plot_threshold(self.data, self.TSR_threshold)
            left_layout.layout().itemAtPosition(0, 0).widget().addItem(tplot_thr)
        left_layout.layout().itemAtPosition(0, 0).widget().setLimits(yMin=-0.1, yMax=max(self.data.TSR) + 1,
                                                                     xMin=0, xMax=self.data.time[-1])
        left_layout.layout().itemAtPosition(0, 0).widget().setYRange(-1, max(self.data.TSR) + 1)
        left_layout.layout().itemAtPosition(0, 0).widget().setXRange(0, self.data.time[-1])
        # left_layout.layout().itemAtPosition(0, 0).widget().getPlotItem().hideAxis('bottom')

    def plot_colormap(self, right_layout):
        cm = pg.colormap.get('CET-R4')
        act_max_value = np.max(self.data.burst_activation)
        act_plot = colormap_plot(self.data.burst_activation)
        right_layout.layout().itemAtPosition(0, 0).widget().addItem(act_plot)
        if right_layout.layout().itemAtPosition(0, 0).widget().plotItem.layout.itemAt(2, 5):
            act_bar = right_layout.layout().itemAtPosition(0, 0).widget().plotItem.layout.itemAt(2, 5)
            act_bar.setLevels(values=(0, act_max_value))
        else:
            act_bar = pg.ColorBarItem(interactive=False,
                                      values=(0, act_max_value),
                                      cmap=cm,
                                      label="Spike times, ms")
        act_bar.setImageItem(act_plot, insert_in=right_layout.layout().itemAtPosition(0, 0).widget().plotItem)

        deact_max_value = np.max(self.data.burst_deactivation)
        deact_plot = colormap_plot(self.data.burst_deactivation)
        right_layout.layout().itemAtPosition(1, 0).widget().addItem(deact_plot)
        if right_layout.layout().itemAtPosition(1, 0).widget().plotItem.layout.itemAt(2, 5):
            deact_bar = right_layout.layout().itemAtPosition(1, 0).widget().plotItem.layout.itemAt(2, 5)
            deact_bar.setLevels(values=(0, deact_max_value))
        else:
            deact_bar = pg.ColorBarItem(interactive=False,
                                        values=(0, deact_max_value),
                                        cmap=cm,
                                        label="Spike times, ms")
        deact_bar.setImageItem(deact_plot, insert_in=right_layout.layout().itemAtPosition(1, 0).widget().plotItem)

    def remove_plots(self, left_layout, right_layout):
        left_layout.layout().itemAtPosition(0, 0).widget().clear()
        left_layout.layout().itemAtPosition(1, 0).widget().clear()
        right_layout.layout().itemAtPosition(0, 0).widget().clear()
        right_layout.layout().itemAtPosition(1, 0).widget().clear()


def main(args=sys.argv):
    application = QApplication(args)
    application.setStyle(QStyleFactory.create('Fusion'))
    screen = application.primaryScreen()
    rect = screen.availableGeometry()
    window = MEAXtd(rect)
    window.show()
    sys.exit(application.exec_())
