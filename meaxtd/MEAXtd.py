import sys
import pkg_resources
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QAction, QApplication, QDesktopWidget, QDialog, QFileDialog,
                             QHBoxLayout, QLabel, QMainWindow, QToolBar, QVBoxLayout, QWidget,
                             QGroupBox, QGridLayout, QPushButton)
from meaxtd.read_h5 import read_h5_file
from meaxtd.hdf5plot import HDF5Plot


class MEAXtd(QMainWindow):
    """Create the main window that stores all of the widgets necessary for the application."""

    def __init__(self, parent=None):
        """Initialize the components of the main window."""
        super(MEAXtd, self).__init__(parent)
        self.resize(1024, 768)
        self.setWindowTitle('MEAXtd')
        window_icon = pkg_resources.resource_filename('meaxtd.images',
                                                      'ic_insert_drive_file_black_48dp_1x.png')
        self.setWindowIcon(QIcon(window_icon))

        self.widget = QWidget()
        self.layout = QHBoxLayout(self.widget)

        self.menu_bar = self.menuBar()
        self.about_dialog = AboutDialog()

        self.status_bar = self.statusBar()
        self.status_bar.showMessage('Ready', 5000)

        self.file_menu()
        self.help_menu()
        self.plot_button()

        self.tool_bar_items()

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

    def plot_button(self):
        hbox = QHBoxLayout()
        self.qbtn = QPushButton('Plot Signals', self)
        self.qbtn.setEnabled(False)
        self.qbtn.resize(300, 100)
        self.qbtn.move(100, 100)
        hbox.addWidget(self.qbtn)
        hbox.addStretch(1)
        self.setLayout(hbox)
        self.qbtn.clicked.connect(lambda: self.plot_data())

    def open_file(self):
        """Open a QFileDialog to allow the user to open a file into the application."""
        filename, accepted = QFileDialog.getOpenFileName(self, 'Open File', filter="*.h5")

        if accepted:
            self.data = read_h5_file(filename)
            self.qbtn.setEnabled(True)

    def plot_data(self):
        self.plot = PlotDialog(self.data)
        self.plot.show()


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

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()

    def initUI(self):
        self.createGridLayout()
        self.resize(2000, 800)
        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.horizontalGroupBox)
        self.setLayout(windowLayout)
        self.show()

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
                curr_plot.setXRange(0, 500)
                curve = HDF5Plot()
                curr_data = self.data.stream[:, curr_id]
                curve.setHDF5(curr_data)
                curr_plot.addItem(curve)
                layout.addWidget(curr_plot, col_id, row_id)
                plots.append(curr_plot)
                if curr_id > 0:
                    plots[curr_id - 1].getViewBox().setXLink(plots[curr_id])
                    plots[curr_id - 1].getViewBox().setYLink(plots[curr_id])

        self.horizontalGroupBox.setLayout(layout)


def main(args=sys.argv):
    application = QApplication(args)
    window = MEAXtd()
    desktop = QDesktopWidget().availableGeometry()
    width = (desktop.width() - window.width()) / 4
    height = (desktop.height() - window.height()) / 4
    window.show()
    window.move(width, height)
    sys.exit(application.exec_())
