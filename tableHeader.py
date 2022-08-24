from TermTk.TTkWidgets.Fancy.tableview import _TTkFancyTableViewHeader
from TermTk.TTkCore.signal import pyTTkSignal


class Header(_TTkFancyTableViewHeader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.activated = pyTTkSignal(int) # Value
        self.double_activated = pyTTkSignal(int)

    def mousePressEvent(self, evt):
        w,h = self.size()
        total = 0
        variableCols = 0
        # Retrieve the free size
        for width in self._columns:
            if width > 0:
                total += width
            else:
                variableCols += 1
        # Define the list of cols sizes
        sizes = []
        for width in self._columns:
            if width > 0:
                sizes.append(width)
            else:
                sizes.append((w-total)//variableCols)
                variableCols -= 1

        x, _ = evt.x, evt.y
        for index, size in enumerate(sizes):
            if x < sum(sizes[:index + 1]):
                self.activated.emit(index)
                return True
        self.activated.emit(-1)
        return True
