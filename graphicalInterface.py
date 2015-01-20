from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL, NW, NE, SW, SE, N, S, W, E
import ttk as themed

class Visualisation(object):
    def __init__(self, parent, data, coloring, timeLabeling, positionLabeling):
        self.data = data
        self.coloring = coloring
        self.timeLabeling = timeLabeling
        self.positionLabeling = positionLabeling

        # the frame containing all widgets needed for the visualisation
        self.mainframe = themed.Frame(parent, padding = 5)

        self.content        = Canvas(self.mainframe)
        self.timeLabels     = Canvas(self.mainframe)
        self.positionLabels = Canvas(self.mainframe)
        self.legend         = Canvas(self.mainframe)

        # set the background color of the canvases to match that of the themed widgets
        color = themed.Style().lookup("TFrame", "background")
        for canvas in [self.content, self.timeLabels, self.positionLabels, self.legend]:
            canvas['background'] = color
            canvas['highlightthickness'] = 0

        self.plotTimeLabels()
        self.plotPositionLabelsAndData()

        self.scrollHorizontal = themed.Scrollbar(self.mainframe, orient = HORIZONTAL)
        self.scrollVertical   = themed.Scrollbar(self.mainframe, orient = VERTICAL)

        # set the right callbacks for the scrollbars
        for canvas in [self.content, self.timeLabels]:
            canvas['xscrollcommand'] = self.scrollHorizontal.set

        for canvas in [self.content, self.positionLabels]:
            canvas['yscrollcommand'] = self.scrollVertical.set

        def scrollAllHorizontal(*arguments):
            for canvas in [self.content, self.timeLabels]:
                canvas.xview(*arguments)

        def scrollAllVertical(*arguments):
            for canvas in [self.content, self.positionLabels]:
                canvas.xview(*arguments)

        self.scrollHorizontal['command'] = scrollAllHorizontal
        self.scrollVertical  ['command'] = scrollAllVertical

        # place everything on the screen
        self.timeLabels      .grid( column = 1, row = 0, sticky = (N,S,E,W) )
        self.positionLabels  .grid( column = 0, row = 1, sticky = (N,S,E,W) )
        self.content         .grid( column = 1, row = 1, sticky = (N,S,E,W) )
        self.scrollHorizontal.grid( column = 1, row = 2, sticky = (N,S,E,W) )
        self.scrollVertical  .grid( column = 2, row = 1, sticky = (N,S,E,W) )
        self.legend          .grid( column = 1, row = 3, sticky = (N,S,E,W) )
        self.mainframe.columnconfigure( 1, weight = 1 )
        self.mainframe.rowconfigure(    1, weight = 1 )

    def plotTimeLabels(self):
        nextFree = {}
        lineStart = {}

        textSize = self.getDefaultTextSize(self.timeLabels)
        self.timeLabels.line = {}

        for time, labelText in sorted(self.timeLabeling.items()):
            time *= 2
            line = 0
            while line in nextFree and nextFree[line] > time:
                line += 1

            label = self.timeLabels.create_text(time, line * textSize * 3 / 2, text = labelText, anchor = NW)
            _, _, x, y = self.timeLabels.bbox(label)
            nextFree[line] = x + textSize / 2
            lineStart[time] = y

            self.timeLabels.tag_bind(label, '<Enter>', lambda _, label = label, position = time: addLine(label, position))
            self.timeLabels.tag_bind(label, '<Leave>', lambda _, label = label: removeLine(label))

            def addLine(label, position):
                self.timeLabels.line[label] = self.content.create_line(position, 0, position, self.content['height'])

            def removeLine(label):
                self.content.delete(self.timeLabels.line[label])

        boundingBox = self.timeLabels.bbox('all')
        width  = boundingBox[2]
        height = boundingBox[3] + textSize / 2
        for x, y in lineStart.items():
            self.timeLabels.create_line(x, y, x, height, tags = 'line', fill = 'grey')
        self.timeLabels.tag_lower('line')

        self.timeLabels['height'] = height
        self.timeLabels['scrollregion'] = (0, 0, width, height)

    def plotPositionLabelsAndData(self):
        offset = 0
        width = 0

        textSize = self.getDefaultTextSize(self.positionLabels)
        self.positionLabels.line = {}

        for (lower, upper), labels in sorted(self.positionLabeling.items()):
            for position in range(lower, upper):
                try:
                    for time, value in self.data[position].items():
                        x, y = 2 * time, offset + 2 * position
                        point = self.content.create_rectangle(x, y, x + 2, y + 2, width = 0, fill = self.coloring[value])
                except KeyError:
                    pass

            end = lower
            for (number, labelText) in sorted(labels.items()):
                if number < end: continue
                position = offset + number - end
                label = self.positionLabels.create_text(0, position, text = labelText, anchor = NW)
                _, _, x, y = self.positionLabels.bbox(label)
                offset = y
                width = max(width, x)
                end = position + textSize

                self.positionLabels.tag_bind(label, '<Enter>', lambda _, label = label, position = position: addLine(label, position))
                self.positionLabels.tag_bind(label, '<Leave>', lambda _, label = label: removeLine(label))

                def addLine(label, position):
                    self.positionLabels.line[label] = self.content.create_line(0, position, self.content['width'], position)

                def removeLine(label):
                    self.content.delete(self.positionLabels.line[label])

                offset += textSize / 2

        self.positionLabels['width'] = width
        self.positionLabels['scrollregion'] = (0, 0, width, offset - textSize / 2)

    def getDefaultTextSize(_, canvas):
        text = canvas.create_text(0, 0, anchor = N)
        size = canvas.bbox(text)[3]
        canvas.delete(text)
        return size

root = Tk()
Visualisation(root, { 0 : { 1 : 0, 2 : 0, 3 : 1 }, 1 : { 5 : 0, 6 : 1, 7 : 1 }, 4 : { 1 : 0, 2 : 1, 3 : 0 } }, { 0 : 'black', 1 : 'red' }, {1 : 'start', 20 : 'next', 40 : 'end::end', 50 : 'veryveryveryverylongstring' }, {(0,2): {0 : 'hi', 2 : 'you'}, (2, 10): {3 : 'this'}}).mainframe.grid(column = 0, row = 0, sticky = (N, S, W, E))
root.columnconfigure( 0, weight = 1 )
root.rowconfigure(    0, weight = 1 )
root.mainloop()
