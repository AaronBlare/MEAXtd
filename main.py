import sys
from meaxtd import MEAXtd

sys._excepthook = sys.excepthook


def my_exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = my_exception_hook

if __name__ == '__main__':
    try:
        sys.exit(MEAXtd.main())
    except:
        print("Exiting")
