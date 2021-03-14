import pyqtgraph as pg
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen


class HDF5Plot(pg.PlotCurveItem):
    def __init__(self, *args, **kwds):
        self.hdf5 = None
        self.limit = 10000
        pg.PlotCurveItem.__init__(self, *args, **kwds)

    def setHDF5(self, data):
        self.hdf5 = data
        self.updateHDF5Plot()

    def viewRangeChanged(self):
        self.updateHDF5Plot()

    def updateHDF5Plot(self):
        if self.hdf5 is None:
            self.setData([])
            return

        vb = self.getViewBox()
        if vb is None:
            return

        xrange = vb.viewRange()[0]
        start = max(0, int(xrange[0]) - 1)
        stop = min(len(self.hdf5), int(xrange[1] + 2))

        ds = int((stop - start) / self.limit) + 1

        if ds == 1:
            visible = self.hdf5[start:stop]
            scale = 1
        else:
            samples = 1 + ((stop - start) // ds)
            visible = np.zeros(samples * 2, dtype=self.hdf5.dtype)
            sourcePtr = start
            targetPtr = 0

            chunkSize = (1000000 // ds) * ds
            while sourcePtr < stop - 1:
                chunk = self.hdf5[sourcePtr:min(stop, sourcePtr + chunkSize)]

                sourcePtr += len(chunk)

                chunk = chunk[:(len(chunk) // ds) * ds].reshape(len(chunk) // ds, ds)

                chunkMax = chunk.max(axis=1)
                chunkMin = chunk.min(axis=1)

                visible[targetPtr:targetPtr + chunk.shape[0] * 2:2] = chunkMin
                visible[1 + targetPtr:1 + targetPtr + chunk.shape[0] * 2:2] = chunkMax

                targetPtr += chunk.shape[0] * 2

            visible = visible[:targetPtr]
            scale = ds * 0.5

        self.setData(visible)
        self.setPos(start, 0)
        self.resetTransform()
        self.scale(scale, 1)


class HDF5Point(pg.ScatterPlotItem):
    def __init__(self, *args, **kwds):
        self.x = None
        self.y = None
        self.limit = 10000
        pg.ScatterPlotItem.__init__(self, *args, **kwds)

    def setHDF5(self, x, y):
        self.x = x
        self.y = y
        self.updateHDF5Plot()

    def viewRangeChanged(self):
        self.updateHDF5Plot()

    def updateHDF5Plot(self):
        if self.x is None:
            self.setData([])
            return

        vb = self.getViewBox()
        if vb is None:
            return

        xrange = vb.viewRange()[0]
        start = max(0, int(xrange[0]) - 1)
        stop = min(len(self.x), int(xrange[1] + 2))

        ds = int((stop - start) / self.limit) + 1

        if ds == 1:
            xvisible = self.x[start:stop]
            yvisible = self.y[start:stop]
            scale = 1
        else:
            samples = 1 + ((stop - start) // ds)
            xvisible = np.zeros(samples * 2, dtype=self.x.dtype)
            yvisible = np.zeros(samples * 2, dtype=self.y.dtype)
            sourcePtr = start
            targetPtr = 0

            chunkSize = (1000000 // ds) * ds
            while sourcePtr < stop - 1:
                xchunk = [self.x[i] for i in range(0, len(self.x)) if
                          self.x[i] >= sourcePtr and self.x[i] < min(stop, sourcePtr + chunkSize)]
                ychunk = [self.y[i] for i in range(0, len(self.y)) if
                          self.y[i] >= sourcePtr and self.y[i] < min(stop, sourcePtr + chunkSize)]

                sourcePtr += min(stop, sourcePtr + chunkSize) - sourcePtr + 1

                xchunk = xchunk[:(len(xchunk) // ds) * ds].reshape(len(xchunk) // ds, ds)
                ychunk = ychunk[:(len(ychunk) // ds) * ds].reshape(len(ychunk) // ds, ds)

                xchunkMax = xchunk.max(axis=1)
                ychunkMax = ychunk.max(axis=1)
                xchunkMin = xchunk.min(axis=1)
                ychunkMin = ychunk.min(axis=1)

                xvisible[targetPtr:targetPtr + xchunk.shape[0] * 2:2] = xchunkMin
                yvisible[targetPtr:targetPtr + ychunk.shape[0] * 2:2] = ychunkMin
                xvisible[1 + targetPtr:1 + targetPtr + xchunk.shape[0] * 2:2] = xchunkMax
                yvisible[1 + targetPtr:1 + targetPtr + ychunk.shape[0] * 2:2] = ychunkMax

                targetPtr += xchunk.shape[0] * 2

            xvisible = xvisible[:targetPtr]
            yvisible = yvisible[:targetPtr]
            scale = ds * 0.5

        self.setData(x=self.x, y=self.y, size=10, pen=pg.mkPen(None), brush='b', symbol='o', symbolBrush='w')
        self.setPos(start, 0)
        self.resetTransform()
        self.scale(scale, 1)
