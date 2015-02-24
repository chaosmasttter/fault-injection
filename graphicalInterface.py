from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
import ttk as themed
import random

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, timeLabeling, positionLabeling):
        self.data = data
        self.coloring = coloring
        self.explanation = explanation
        self.timeLabeling = timeLabeling
        self.positionLabeling = positionLabeling

        # the frame containing all widgets needed for the visualisation
        self.mainframe = themed.Frame(parent, padding = 5)

        self.content        = Canvas(self.mainframe)
        self.timeLabels     = Canvas(self.mainframe)
        self.positionLabels = Canvas(self.mainframe)
        self.legend         = Canvas(self.mainframe)

        # set the background color of the canvases
        # to match that of the themed widgets
        color = themed.Style().lookup("TFrame", "background")
        for canvas in \
          [self.content, self.timeLabels, self.positionLabels, self.legend]:
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

        self.legend.bind('<Configure>', self.plotLegend)

        # place everything on the screen
        self.timeLabels      .grid( column = 1, row = 0, sticky = 'nsew' )
        self.positionLabels  .grid( column = 0, row = 1, sticky = 'nsew' )
        self.content         .grid( column = 1, row = 1, sticky = 'nsew' )
        self.scrollHorizontal.grid( column = 1, row = 2, sticky = 'nsew' )
        self.scrollVertical  .grid( column = 2, row = 1, sticky = 'nsew' )
        self.legend          .grid( column = 1, row = 3, sticky = 'nsew'
                                  , pady = 5 )
        self.mainframe.columnconfigure( 1, weight = 1 )
        self.mainframe.rowconfigure(    1, weight = 1 )

    def plot(self):
        self.timeLabels.line = {}
        self.positionLabels.line = {}

        verticalLines = {}
        horizontalLines = {}

        def showLine(label, canvas):
            line = canvas.line[label]
            self.content.tag_raise(line)
            self.content.itemconfigure(line, fill = 'black')

        def hideLine(label, canvas):
            line = canvas.line[label]
            self.content.tag_lower(line)
            self.content.itemconfigure(line, fill = 'grey')

        offset = 0
        textSize = self.getDefaultTextSize(self.positionLabels)

        for (lower, upper), labels in sorted(self.positionLabeling.items()):
            for position in range(lower, upper):
                try:
                    for time, value in self.data[position].items():
                        y = offset + 2 * (position - lower)
                        point = self.content.create_rectangle(
                            2 * time[0], y, 2 * time[1], y + 2,
                            width = 0, fill = self.coloring[value])
                except KeyError: pass

            newOffset = offset
            for (position, labelText) in sorted(labels.items()):
                position = offset + 2 * (position - lower)
                if position < newOffset:  continue
                label = self.positionLabels.create_text(
                    0, position, text = labelText, anchor = 'nw')
                newOffset = self.positionLabels.bbox(label)[3]

                horizontalLines[label] = position
                self.positionLabels.tag_bind(label, '<Enter>',
                    lambda _, label = label: showLine(label, self.positionLabels))
                self.positionLabels.tag_bind(label, '<Leave>',
                    lambda _, label = label: hideLine(label, self.positionLabels))
            offset = max(offset + 2 * (upper - lower), newOffset) + textSize / 2

        offset = {}
        textSize = self.getDefaultTextSize(self.timeLabels)
        lineStart = {}

        for time, labelText in sorted(self.timeLabeling.items()):
            time *= 2
            line = 0
            while line in offset and offset[line] > time: line += 1

            label = self.timeLabels.create_text(
                time, line * textSize * 3 / 2, text = labelText, anchor = 'nw')
            _, _, x, y = self.timeLabels.bbox(label)
            offset[line] = x + textSize / 2
            lineStart[time] = y

            verticalLines[label] = time
            self.timeLabels.tag_bind(label, '<Enter>',
                lambda _, label = label: showLine(label, self.timeLabels))
            self.timeLabels.tag_bind(label, '<Leave>',
                lambda _, label = label: hideLine(label, self.timeLabels))

        try:
            height = self.timeLabels.bbox('all')[3] + textSize / 2
            for x, y in lineStart.items():
                self.timeLabels.create_line(
                    x, y, x, height, tags = 'line', fill = 'grey')
                self.timeLabels.tag_lower('line')
        except TypeError: pass # if the canvas is empty bbox('all') returns no tuple

        try:
            lowerX, lowerY, upperX, upperY = self.content.bbox('all')
            for label, time in verticalLines.items():
                self.timeLabels.line[label] = self.content.create_line(
                    time, lowerY, time, upperY)
                hideLine(label, self.timeLabels)
            for label, position in horizontalLines.items():
                self.positionLabels.line[label] = self.content.create_line(
                    lowerX, position, upperX, position)
                hideLine(label, self.positionLabels)
        except TypeError:
            def showLine(line, canvas): pass
            def hideLine(line, canvas): pass

    def plotLegend(self, event):
        self.legend.delete('all')

        x, y = 0, 0
        yend = 0

        for value, explanationText in self.explanation.items():
            rectangle = self.legend.create_rectangle(
                x, y, x + 10, y + 10, fill = self.coloring[value])
            label = self.legend.create_text(
                x + 15, y, text = explanationText, anchor = 'nw')

            _, _, xend, yend = self.legend.bbox(label)
            yend = max(y + 15, yend)

            if xend < event.width: x = xend + 10
            elif x == 0:
                self.legend.delete('all')
                yend = 0
                break
            else:
                ychange = yend - y
                self.legend.move(rectangle, - x, ychange)
                self.legend.move(label,     - x, ychange)
                x, y = xend - x + 10, yend
                yend += ychange

        self.legend['height'] = yend

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

        try:
            timeLabelsLowerY = timeLabelsBoundingBox[1]
            timeLabelsUpperY = timeLabelsBoundingBox[3]
        except TypeError: timeLabelsLowerY, timeLabelsUpperY = 0, 0
        self.timeLabels['scrollregion'] = lowerX, timeLabelsLowerY, \
                                          upperX, timeLabelsUpperY
        self.timeLabels['height'] = timeLabelsUpperY - timeLabelsLowerY

        try:
            positionLabelsLowerX = positionLabelsBoundingBox[0]
            positionLabelsUpperX = positionLabelsBoundingBox[2]
        except TypeError: positionLabelsLowerX, positionLabelsUpperX = 0, 0
        self.positionLabels['scrollregion'] = positionLabelsLowerX, lowerY, \
                                              positionLabelsUpperX, upperY
        self.positionLabels['width'] = positionLabelsUpperX - positionLabelsLowerX

    def getDefaultTextSize(_, canvas):
        text = canvas.create_text(0, 0, anchor = 'n')
        size = canvas.bbox(text)[3]
        canvas.delete(text)
        return size
