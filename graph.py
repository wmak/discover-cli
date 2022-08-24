import TermTk as ttk
from TermTk.TTkCore.constant import TTkK


class Graph(ttk.TTkGraph):
    def paintEvent(self):
        if not self._data: return
        w,h = self.size()
        x=0
        if   self._align == TTkK.CENTER:
            y = h//2
        elif self._align == TTkK.TOP:
            y = 0
        else:
            y = h
        v1,v2 = [0],[0]
        i=0
        data = self._data[-w*2:]
        # TTkLog.debug(data)
        # TODO: use deep unpacking technique to grab couples of values
        # https://mathspp.com/blog/pydonts/enumerate-me#deep-unpacking
        mv = max(max(map(max,data)),-min(map(min,data)))
        zoom = 2*h/mv if mv>0 else 1.0
        for i in range(len(data)):
            v2 = v1
            v1 = data[i]
            if i%2==0:
                if self._direction == TTkK.RIGHT:
                    self._canvas.drawHChart(pos=(x+i//2,y),values=(v2,v1), zoom=zoom, color=self.color.modParam(val=-y))
                else:
                    self._canvas.drawHChart(pos=(w-(x+i//2),y),values=(v1,v2), zoom=zoom, color=self.color.modParam(val=-y))
        if i%2==1:
            if self._direction == TTkK.RIGHT:
                self._canvas.drawHChart(pos=(x+i//2+1,y),values=(v1,v1), zoom=zoom, color=self.color.modParam(val=-y))
            else:
                self._canvas.drawHChart(pos=(w-(x+i//2+1),y),values=(v1,v1), zoom=zoom, color=self.color.modParam(val=-y))
