from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
import ttk as themed
import random

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, timeLabeling, positionLabeling):
        self.data = data
        self.coloring = coloring
        self.explanation = explanation
        self.timeLabeling = sorted(timeLabeling)
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

        self.scrollHorizontal['command'] = self.scrollAllHorizontal
        self.scrollVertical  ['command'] = self.scrollAllVertical

        self.mainframe.bind_all('<Button-4>', lambda _: self.force
                                (self.scrollAllVertical,   'scroll', - 1, 'units'))
        self.mainframe.bind_all('<Button-5>', lambda _: self.force
                                (self.scrollAllVertical,   'scroll', + 1, 'units'))
        self.mainframe.bind_all('<Shift-Button-4>', lambda _: self.force
                                (self.scrollAllHorizontal, 'scroll', - 1, 'units'))
        self.mainframe.bind_all('<Shift-Button-5>', lambda _: self.force
                                (self.scrollAllHorizontal, 'scroll', + 1, 'units'))

        def doUpdate(_): self.mainframe.update_idletasks()

        self.mainframe.bind_all('<Control-Button-4>', doUpdate)
        self.mainframe.bind_all('<Control-Button-5>', doUpdate)

        self.content.bind('<Control-Button-4>', lambda event: self.zoom(1.1, event))
        self.content.bind('<Control-Button-5>', lambda event: self.zoom(0.9, event))

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

    def scrollAllHorizontal(self, *arguments):
        for canvas in [self.content, self.timeLabels]:
            canvas.xview(*arguments)

    def scrollAllVertical(self, *arguments):
        for canvas in [self.content, self.positionLabels]:
            canvas.yview(*arguments)

    def force(self, function, *arguments):
        function(*arguments)
        self.mainframe.update_idletasks()

    def zoom(self, scale, event):
        x, y = self.content.canvasx(event.x), self.content.canvasy(event.y)

        self.content       .scale('all', x, y, scale, scale)
        self.timeLabels    .scale('all', x, y, scale, 1,   )
        self.positionLabels.scale('all', x, y, 1,     scale)

        self.managePositionLabels()
        self.setScrollRegions()

    def maybeHidePositionLabel(self, label):
        box = self.positionLabels.bbox(label)
        overlapping = len(self.positionLabels.find_overlapping(*box)) - 1
        if overlapping != 0:
            self.positionLabels.itemconfigure(label, state = 'hidden')
        

    def managePositionLabels(self):
        for label in self.positionLabels.find_all():
            self.positionLabels.itemconfigure(label, state = 'normal')
            self.maybeHidePositionLabel(label)

    def plot(self):
        self.timeLabels.line = {}
        self.positionLabels.line = {}

        verticalLines = {}
        horizontalLines = {}
        extraHorizontalLines = []

        def showLine(label, canvas):
            line = canvas.line[label]
            self.content.tag_raise(line)
            self.content.itemconfigure(line, fill = 'black')

        def hideLine(label, canvas):
            line = canvas.line[label]
            self.content.tag_lower(line)
            self.content.itemconfigure(line, fill = 'grey')

        def createLabel(canvas, text, position, linePosition = None):
            label = canvas.create_text(*(position), text = text, anchor = 'nw')
            canvas.tag_bind(label, '<Enter>',
                            lambda _, label = label: showLine(label, canvas))
            canvas.tag_bind(label, '<Leave>',
                            lambda _, label = label: hideLine(label, canvas))

            if canvas is self.timeLabels:
                if linePosition is None:
                    verticalLines[label] = position[0]
                else:
                    verticalLines[label] = linePosition
            elif canvas is self.positionLabels:
                if linePosition is None:
                    horizontalLines[label] = position[1]
                else:
                    horizontalLines[label] = linePosition
            else:
                raise ValueError('createLabel: wrong canvas')

            return label

        offset = 0
        textSize = self.getDefaultTextSize(self.positionLabels)

        for (lowerText, upperText), content in self.positionLabeling:
            if lowerText != '':
                createLabel(self.positionLabels, lowerText,
                            (0, offset), offset + textSize)
                offset += textSize

            for (lower, upper), labels in content:
                if lower > upper: lower, upper = upper, lower

                for position in range(lower, upper):
                    try:
                        for time, value in self.data[position].items():
                            y = offset + 2 * (position - lower)
                            point = self.content.create_rectangle(
                                2 * time[0], y, 2 * time[1], y + 2,
                                width = 0, fill = self.coloring[value])
                    except KeyError: pass

                for position, text in labels:
                    if not lower <= position <= upper: continue

                    position = offset + 2 * (position - lower)
                    label = createLabel(self.positionLabels, text, (20, position))
                    self.maybeHidePositionLabel(label)
                offset += 2 * (upper - lower)

            if upperText != '':
                createLabel(self.positionLabels, upperText, (0, offset))
                offset +=  2 * textSize
            else:
                extraHorizontalLines.append(offset)
                offset += textSize

        offset = {}
        textSize = self.getDefaultTextSize(self.timeLabels)
        lineStart = {}

        for time, text in self.timeLabeling:
            time *= 2
            line = 0
            while line in offset and offset[line] > time: line += 1

            label = createLabel(self.timeLabels, text, (time, line * textSize))
            _, _, x, y = self.timeLabels.bbox(label)
            offset[line] = x
            lineStart[time] = y

        try:
            height = self.timeLabels.bbox('all')[3] + textSize / 2
            for x, y in lineStart.items():
                self.timeLabels.create_line(
                    x, y, x, height, tags = 'line', fill = 'grey')
                self.timeLabels.tag_lower('line')
        except TypeError: pass # if the canvas is empty bbox('all') returns no tuple

        try:
            lowerX, _, upperX, upperY = self.content.bbox('all')
            for label, time in verticalLines.items():
                self.timeLabels.line[label] = self.content.create_line(
                    time, 0, time, upperY)
                hideLine(label, self.timeLabels)
            for label, position in horizontalLines.items():
                self.positionLabels.line[label] = self.content.create_line(
                    lowerX, position, upperX, position)
                hideLine(label, self.positionLabels)
            for position in extraHorizontalLines:
                self.content.create_line(lowerX, position, upperX, position,
                                         fill = 'grey')
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

    @staticmethod
    def getDefaultTextSize(canvas):
        text = canvas.create_text(0, 0, anchor = 'n')
        size = canvas.bbox(text)[3]
        canvas.delete(text)
        return size
