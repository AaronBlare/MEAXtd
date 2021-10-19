from pyqtgraph.exporters.Exporter import Exporter

from PySide6 import QtCore
from PySide6.QtWidgets import QGraphicsItem, QApplication
from PySide6.QtGui import QPainter, QPdfWriter, QPagedPaintDevice, QPageSize
from PySide6.QtCore import QMarginsF, Qt, QSizeF, QRectF


class PDFExporter(Exporter):

    def __init__(self, item):
        Exporter.__init__(self, item)
        if isinstance(item, QGraphicsItem):
            scene = item.scene()
        else:
            scene = item
        bgbrush = scene.views()[0].backgroundBrush()
        bg = bgbrush.color()
        if bgbrush.style() == Qt.NoBrush:
            bg.setAlpha(0)
        self.background = bg

        try:
            from pyqtgraph.graphicsItems.ViewBox.ViewBox import ChildGroup
            for item in self.getPaintItems():
                if isinstance(item, ChildGroup):
                    if item.flags() & QGraphicsItem.ItemClipsChildrenToShape:
                        item.setFlag(QGraphicsItem.ItemClipsChildrenToShape, False)
        except:
            pass

    def export(self, filename=None, add_margin=False):
        pw = QPdfWriter(filename)
        dpi = int(QApplication.primaryScreen().logicalDotsPerInch())
        pw.setResolution(dpi)
        pw.setPageMargins(QMarginsF(0, 0, 0, 0))
        size = QPageSize(self.getTargetRect().size())
        pw.setPageSize(size)
        painter = QPainter(pw)
        try:
            self.setExportMode(True, {'antialias': True,
                                      'background': self.background,
                                      'painter': painter})
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.LosslessImageRendering, True)
            source_rect = self.getSourceRect()
            if add_margin:
                source_rect.setWidth(source_rect.width() + 25)
            self.getScene().render(painter,
                                   QRectF(self.getTargetRect()),
                                   QRectF(source_rect))
        finally:
            self.setExportMode(False)
        painter.end()
