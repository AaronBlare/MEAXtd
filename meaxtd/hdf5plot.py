import pyqtgraph as pg
import numpy as np


class HDF5Plot(pg.PlotCurveItem):
    def __init__(self, *args, **kwds):
        self.hdf5 = None
        self.pen = pg.mkPen()
        self.limit = 10000
        pg.PlotCurveItem.__init__(self, *args, **kwds)

    def setHDF5(self, data, pen=pg.mkPen()):
        self.hdf5 = data
        self.pen = pen
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

        self.setData(visible, pen=self.pen, connect="finite")
        self.setPos(start, 0)
        self.resetTransform()
        self.scale(scale, 1)


class HDF5PlotXY(pg.PlotCurveItem):
    def __init__(self, *args, **kwds):
        self.x = None
        self.y = None
        self.fs = None
        self.pen = pg.mkPen()
        self.limit = 20000
        pg.PlotCurveItem.__init__(self, *args, **kwds)

    def setHDF5(self, x, y, fs, pen=pg.mkPen()):
        self.x = x
        self.y = y
        self.fs = fs
        self.pen = pen
        self.updateHDF5Plot()

    def viewRangeChanged(self):
        self.updateHDF5Plot()

    def updateHDF5Plot(self):
        if self.y is None:
            self.setData([])
            return

        vb = self.getViewBox()
        if vb is None:
            return

        xrange = [i * self.fs for i in vb.viewRange()[0]]
        start = max(0, int(xrange[0]) - 1)
        stop = min(len(self.y), int(xrange[1]+2))

        ds = int((stop - start) / self.limit) + 1

        if ds == 1:
            visible_y = self.y[start:stop]
            visible_x = self.x[start:stop]
            scale = 1
        else:
            samples = 1 + ((stop - start) // ds)
            visible_y = np.zeros(samples * 2, dtype=self.y.dtype)
            visible_x = np.zeros(samples * 2, dtype=self.x.dtype)
            sourcePtr = start
            targetPtr = 0

            chunkSize = (1000000 // ds) * ds
            while sourcePtr < stop - 1:
                chunk_y = self.y[sourcePtr:min(stop, sourcePtr + chunkSize)]
                chunk_x = self.x[sourcePtr:min(stop, sourcePtr + chunkSize)]

                sourcePtr += len(chunk_y)

                chunk_y = chunk_y[:(len(chunk_y) // ds) * ds].reshape(len(chunk_y) // ds, ds)
                chunk_x = chunk_x[:(len(chunk_x) // ds) * ds].reshape(len(chunk_x) // ds, ds)

                mx_inds = np.argmax(chunk_y, axis=1)
                mi_inds = np.argmin(chunk_y, axis=1)
                row_inds = np.arange(chunk_y.shape[0])

                chunkMax_y = chunk_y[row_inds, mx_inds]
                chunkMin_y = chunk_y[row_inds, mi_inds]
                chunkMax_x = chunk_x[row_inds, mx_inds]
                chunkMin_x = chunk_x[row_inds, mi_inds]

                visible_y[targetPtr:targetPtr + chunk_y.shape[0] * 2:2] = chunkMin_y
                visible_y[1 + targetPtr:1 + targetPtr + chunk_y.shape[0] * 2:2] = chunkMax_y
                visible_x[targetPtr:targetPtr + chunk_x.shape[0] * 2:2] = chunkMin_x
                visible_x[1 + targetPtr:1 + targetPtr + chunk_x.shape[0] * 2:2] = chunkMax_x

                targetPtr += chunk_x.shape[0] * 2

            visible_x = visible_x[:targetPtr]
            visible_y = visible_y[:targetPtr]
            scale = ds * 0.5

        self.setData(x=visible_x, y=visible_y, pen=self.pen, connect="finite")
        self.resetTransform()
