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

        self.plot()
        self.setScrollRegions()

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
                canvas.yview(*arguments)

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

    def plot(self):
        self.timeLabels.line = {}
        self.positionLabels.line = {}

        def addVerticalLine(label, position):
            y = self.content.canvasy(0)
            self.timeLabels.line[label] = self.content.create_line(position, y, position, y + self.content.winfo_height())

        def addHorizontalLine(label, position):
            x = self.content.canvasx(0)
            self.positionLabels.line[label] = self.content.create_line(x, position, x + self.content.winfo_width(), position)

        def removeVerticalLine(label):
            self.content.delete(self.timeLabels.line[label])

        def removeHorizontalLine(label):
            self.content.delete(self.positionLabels.line[label])

        lineStart = {}
        offset = {}
        textSize = self.getDefaultTextSize(self.timeLabels)

        for time, labelText in sorted(self.timeLabeling.items()):
            time *= 2
            line = 0
            while line in offset and offset[line] > time: line += 1

            label = self.timeLabels.create_text(time, line * textSize * 3 / 2, text = labelText, anchor = NW)
            _, _, x, y = self.timeLabels.bbox(label)
            offset[line] = x + textSize / 2
            lineStart[time] = y

            self.timeLabels.tag_bind(label, '<Enter>', lambda _, label = label, position = time: addVerticalLine(label, position))
            self.timeLabels.tag_bind(label, '<Leave>', lambda _, label = label: removeVerticalLine(label))

        try:
            height = self.timeLabels.bbox('all')[3] + textSize / 2
            for x, y in lineStart.items():
                self.timeLabels.create_line(x, y, x, height, tags = 'line', fill = 'grey')
                self.timeLabels.tag_lower('line')

        except TypeError: pass # if the canvas is empty bbox('all') returns no tuple

        offset = 0
        textSize = self.getDefaultTextSize(self.positionLabels)

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
                offset = self.positionLabels.bbox(label)[2]
                end = position + textSize

                self.positionLabels.tag_bind(label, '<Enter>', lambda _, label = label, position = position: addHorizontalLine(label, position))
                self.positionLabels.tag_bind(label, '<Leave>', lambda _, label = label: removeHorizontalLine(label))

                offset += textSize / 2

    def setScrollRegions(self):
        contentBoundingBox = self.content.bbox('all')
        timeLabelsBoundingBox = self.timeLabels.bbox('all')
        positionLabelsBoundingBox = self.positionLabels.bbox('all')

        if contentBoundingBox is not None and timeLabelsBoundingBox is not None:
            lowerX = min(contentBoundingBox[0], timeLabelsBoundingBox[0])
            upperX = max(contentBoundingBox[2], timeLabelsBoundingBox[2])
        elif contentBoundingBox is not None:
            lowerX = contentBoundingBox[0]
            upperX = contentBoundingBox[2]
        elif timeLabelsBoundingBox is not None:
            lowerX = timeLabelsBoundingBox[0]
            upperX = timeLabelsBoundingBox[2]
        else:
            lowerX = 0
            upperX = 0

        if contentBoundingBox is not None and positionLabelsBoundingBox is not None:
            lowerY = min(contentBoundingBox[1], positionLabelsBoundingBox[1])
            upperY = max(contentBoundingBox[3], positionLabelsBoundingBox[3])
        elif contentBoundingBox is not None:
            lowerY = contentBoundingBox[1]
            upperY = contentBoundingBox[3]
        elif positionLabelsBoundingBox is not None:
            lowerY = positionLabelsBoundingBox[1]
            upperY = positionLabelsBoundingBox[3]
        else:
            lowerY = 0
            upperY = 0

        self.content['scrollregion'] = lowerX, lowerY, upperX, upperY

        timeLabelsLowerY, timeLabelsUpperY = 0, 0
        try: timeLabelsLowerY, timeLabelsUpperY = timeLabelsBoundingBox[1], timeLabelsBoundingBox[3]
        except TypeError: pass
        self.timeLabels['scrollregion'] = lowerX, timeLabelsLowerY, upperX, timeLabelsUpperY
        self.timeLabels['height'] = timeLabelsUpperY - timeLabelsLowerY

        positionLabelsLowerX, positionLabelsUpperX = 0, 0
        try: positionLabelsLowerX, positionLabelsUpperX = positionLabelsBoundingBox[0], positionLabelsBoundingBox[2]
        except TypeError: pass
        self.positionLabels['scrollregion'] = positionLabelsLowerX, lowerY, positionLabelsUpperX, upperY
        self.positionLabels['width'] = positionLabelsUpperX - positionLabelsLowerX

    def getDefaultTextSize(_, canvas):
        text = canvas.create_text(0, 0, anchor = N)
        size = canvas.bbox(text)[3]
        canvas.delete(text)
        return size

root = Tk()
Visualisation(root, {y:{x:0 for x in range(500)} for y in range(500)}, {0:'green'}, {1:'hi', 70:'world'}, {(0,200):{20:'Cool', 210:'Crazy'}, (400,500):{}}).mainframe.grid(column = 0, row = 0, sticky = (N, S, W, E))
root.columnconfigure( 0, weight = 1 )
root.rowconfigure(    0, weight = 1 )
root.mainloop()
