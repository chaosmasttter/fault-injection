from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
import ttk as themed

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, timeLabels, positionGroups,
                 mirror = True):
        self.data = data
        self.coloring = coloring
        self.explanation = explanation

        self.currentZoom = 1.0
        self.minimalZoom = 1.0
        self.maximalZoom = 10.0

        # the frame containing all widgets needed for the visualisation
        self.mainframe = themed.Frame(parent, padding = 5)

        self.content        = Canvas(self.mainframe)
        self.timeLabels     = Canvas(self.mainframe)
        self.positionLabels = Canvas(self.mainframe)
        self.legend         = Canvas(self.mainframe)

        self.locationLabel = themed.Label(self.mainframe)

        # set the background color of the canvases
        # to match that of the themed widgets
        self.backgroundColor = themed.Style().lookup("TFrame", "background")
        for canvas in \
          self.content, self.timeLabels, self.positionLabels, self.legend:
            canvas['background'] = self.backgroundColor
            canvas['highlightthickness'] = 0

        self.content.noManaging = False

        defaultText = self.timeLabels.create_text(0, 0, anchor = 'n')
        self.timeLabels.defaultTextSize = self.timeLabels.bbox(defaultText)[3]
        self.timeLabels.delete(defaultText)

        self.plot(timeLabels, positionGroups, mirror)

        self.scrollHorizontal = themed.Scrollbar(self.mainframe, orient = HORIZONTAL)
        self.scrollVertical   = themed.Scrollbar(self.mainframe, orient = VERTICAL)

        # set the right callbacks for the scrollbars
        for canvas in [self.content, self.timeLabels]:
            canvas['xscrollcommand'] = self.scrollHorizontal.set

        for canvas in [self.content, self.positionLabels]:
            canvas['yscrollcommand'] = self.scrollVertical.set

        self.scrollHorizontal['command'] = self.scrollAllHorizontal
        self.scrollVertical  ['command'] = self.scrollAllVertical

        def bindScrollCommand(scrollEvent, scrollFunction, direction):
            self.mainframe.bind_all(scrollEvent, lambda _: self.force
                                    (scrollFunction, 'scroll', direction, 'units'))

        self.mainframe.event_add('<<ScrollUp>>',    '<Up>',    '<Button-4>')
        self.mainframe.event_add('<<ScrollDown>>',  '<Down>',  '<Button-5>')
        self.mainframe.event_add('<<ScrollLeft>>',  '<Left>',  '<Shift-Button-4>')
        self.mainframe.event_add('<<ScrollRight>>', '<Right>', '<Shift-Button-5>')

        bindScrollCommand('<<ScrollUp>>',    self.scrollAllVertical,   - 1)
        bindScrollCommand('<<ScrollDown>>',  self.scrollAllVertical,   + 1)
        bindScrollCommand('<<ScrollLeft>>',  self.scrollAllHorizontal, - 1)
        bindScrollCommand('<<ScrollRight>>', self.scrollAllHorizontal, + 1)

        self.content.event_add('<<ZoomIn>>',  '+', '<Control-Button-4>')
        self.content.event_add('<<ZoomOut>>', '-', '<Control-Button-5>')
        
        self.content.bind('<<ZoomIn>>',  lambda event: self.zoom(1.1, event)) 
        self.content.bind('<<ZoomOut>>', lambda event: self.zoom(0.9, event))

        self.legend .bind('<Configure>', self.plotLegend)
        self.content.bind('<Configure>', self.manageContent)

        self.content.bind('<Enter>', lambda _: self.content  .focus_set())
        self.content.bind('<Leave>', lambda _: self.mainframe.focus_set())

        # place everything on the screen
        self.timeLabels      .grid(column = 1, row = 0, sticky = 'nsew')
        self.positionLabels  .grid(column = 0, row = 1, sticky = 'nsew')
        self.content         .grid(column = 1, row = 1, sticky = 'nsew')
        self.scrollHorizontal.grid(column = 1, row = 2, sticky = 'nsew')
        self.scrollVertical  .grid(column = 2, row = 1, sticky = 'nsew')
        self.locationLabel   .grid(column = 1, row = 3, sticky = 'nsew')
        self.legend          .grid(column = 1, row = 4, sticky = 'nsew')

        self.mainframe.columnconfigure(1, weight = 1)
        self.mainframe.rowconfigure(   1, weight = 1)

    def scrollAllHorizontal(self, *arguments):
        for canvas in [self.content, self.timeLabels]:
            canvas.xview(*arguments)

    def scrollAllVertical(self, *arguments):
        for canvas in [self.content, self.positionLabels]:
            canvas.yview(*arguments)

    def force(self, function = None, *arguments):
        if callable(function): function(*arguments)
        self.mainframe.update_idletasks()

    def zoom(self, scale, event):
        x, y = self.content.canvasx(event.x), self.content.canvasy(event.y)

        if scale < 1: self.content.bind('<<ZoomIn>>',  lambda event: self.zoom(1.1, event))
        if scale > 1: self.content.bind('<<ZoomOut>>', lambda event: self.zoom(0.9, event))

        if scale * self.currentZoom > self.maximalZoom:
            scale = self.maximalZoom / self.currentZoom
            self.content.unbind('<<ZoomIn>>')
        if scale * self.currentZoom < self.minimalZoom:
            scale = self.minimalZoom / self.currentZoom
            self.content.unbind('<<ZoomOut>>')

        self.currentZoom *= scale

        self.content       .scale('all', x, y, scale, scale)
        self.timeLabels    .scale('all', x, y, scale, 1,   )
        self.positionLabels.scale('all', x, y, 1,     scale)

        self.manageContent()

    def manageContent(self, event = None):
        if self.content.noManaging:
            self.content.noManaging = False
            return

        self.manageTimeLabels()
        self.managePositionLabels()
        self.setScrollRegions(self.drawingRegions())

        if event is not None:
            if int(self.timeLabels['height']) > event.height:
                self.timeLabels['height'] = 0
                self.content.noManaging = True
            if int(self.positionLabels['width']) > event.width:
                self.positionLabels['width'] = 0
                self.content.noManaging = True

            self.minimalZoom = min(float(event.width)  / self.content.width,
                                   float(event.height) / self.content.height)

    def manageTimeLabels(self, event = None):
        self.timeLabels.delete('line')
        self.timeLabels.itemconfigure('all', state = 'normal')

        textSize = self.timeLabels.defaultTextSize

        offset = {}
        lineStart = []

        maxX, maxY = None, None

        for label in self.timeLabels.find_all():
            lowerX, lowerY, upperX, upperY = self.timeLabels.bbox(label)

            line = 0
            while line in offset and lowerX < offset[line] + textSize: line += 1

            distance = line * textSize - lowerY
            self.timeLabels.move(label, 0, distance)
            offset[line] = upperX
            lineStart.append((label, lowerX + 1, upperY + distance ))

            maxX = max(upperX, maxX)
            maxY = max(upperY, maxY)

        if maxY is not None:
            height = maxY + textSize
            for label, x, y in lineStart:
                line = self.timeLabels.create_line(x, y, x, height, tags = 'line', fill = 'grey')
                self.timeLabels.lines[label] = self.timeLabels.lines[label][0], (line, True)
            self.timeLabels.tag_lower('line')

    def managePositionLabels(self, event = None):
        self.positionLabels.itemconfigure('label', state = 'hidden')

        structure = self.positionLabels.structure[:]
        superstructure = []

        while structure or superstructure:
            while structure:
                (lowerLabel, lowerFree, lowerText), (upperLabel, upperFree, upperText), substructure = structure.pop()
                self.positionLabels.itemconfigure(lowerLabel, state = 'normal')
                _, lower, _, upper = self.positionLabels.bbox(lowerLabel)
                if lowerText:
                    if lowerFree:
                        self.positionLabels.move(lowerLabel, 0, lowerBound - lower)
                        lowerBound += upper - lower
                    else: lowerBound = upper
                elif not lowerFree: lowerBound = lower

                self.positionLabels.itemconfigure(upperLabel, state = 'normal')
                _, lower, _, upper = self.positionLabels.bbox(upperLabel)
                if upperText:
                    if upperFree:
                        self.positionLabels.move(upperLabel, 0, upperBound - upper)
                        upperBound += lower - upper
                    else: upperBound = lower
                elif not upperFree: upperBound = upper

                if lowerBound < upperBound:
                    superstructure.append(structure)
                    structure = substructure[:]
                else:
                    self.positionLabels.itemconfigure(lowerLabel, state = 'hidden')
                    self.positionLabels.itemconfigure(upperLabel, state = 'hidden')
            if superstructure: structure = superstructure.pop()

    def plot(self, timeLabels, positions, locationInformation, mirror = True):
        self.timeLabels.lines = {}
        self.positionLabels.lines = {}

        verticalLines = {}
        horizontalLines = {}

        unitPoint = self.content.create_rectangle(1, 1, 1, 1, width = 0, state = 'hidden')

        def showLocation(correction, event):
            x = self.content.canvasx(event.x) / self.content.coords(unitPoint)[0] - correction[0]
            y = self.content.canvasx(event.y) / self.content.coords(unitPoint)[1] - correction[1]

            self.locationLabel['text'] = locationInformation(x,y)
    
        def showLines(label, canvas):
            for line, onCanvas in canvas.lines[label]:
                if onCanvas:
                    lineCanvas = canvas
                else:
                    lineCanvas = self.content
                lineCanvas.tag_raise(line)
                lineCanvas.itemconfigure(line, fill = 'black')

        def hideLines(label, canvas):
            for line, onCanvas in canvas.lines[label]:
                if onCanvas:
                    lineCanvas = canvas
                else:
                    lineCanvas = self.content
                lineCanvas.tag_lower(line)
                lineCanvas.itemconfigure(line, fill = 'grey')

        def createLabel(text, distance, aboveLine = None, indentation = 0):
            anchor = 'nw'
            if aboveLine is None:
                canvas = self.timeLabels
                position = distance, 0
            else:
                canvas = self.positionLabels
                position = indentation, distance
                if aboveLine: anchor = 'sw'

            label = canvas.create_text(*position, text = text, tag = 'label', anchor = anchor)
            canvas.tag_bind(label, '<Enter>',
                            lambda _, label = label: canvas.after_idle(showLines, label, canvas))
            canvas.tag_bind(label, '<Leave>',
                            lambda _, label = label: canvas.after_idle(hideLines, label, canvas))

            if canvas is self.timeLabels:
                verticalLines[label] = distance
            else:
                horizontalLines[label] = distance, indentation

            return label

        tags = []
        offset = 0
        indentation = 0
        changeOffset = False

        parents = []
        superlabels = []
        if not mirror:
            stack = [(None, positions)]
            while stack:
                _, subpositions = stack.pop()
                if not isinstance(subpositions, list): continue
                stack.extend(subpositions[:])
                subpositions.reverse()

        structures = [[]]
        while positions or parents:
            while isinstance(positions, list):
                if not positions: break

                if changeOffset: offset += 20
                changeOffset = False

                labels, subpositions = positions.pop()
                lowerLabel, upperLabel = labels
                if mirror: lowerLabel, upperLabel = upperLabel, lowerLabel
                
                label = createLabel(lowerLabel, offset, False, indentation)
                superlabels.append([label, bool(lowerLabel)])
                structures.append([])
                
                parents.append((upperLabel, positions))
                positions = subpositions
                indentation += 20

            if isinstance(positions, tuple):
                lower, upper = positions
                if lower > upper: lower, upper = upper, lower

                if mirror:
                    positionRange = range(upper - 1, lower - 1, - 1)
                else:
                    positionRange = range(lower, upper)

                for position in positionRange:
                    try:
                        for time, value in self.data[position].items():
                            if mirror:
                                location = offset + upper - position - 1
                            else:
                                location = offset + position - lower

                            box = time[0], location, time[1], location + 1
                            point = self.content.create_rectangle(box, width = 0, fill = self.coloring[value], tag = 'value{:x}'.format(value))
#                            self.content.tag_bind(point, '<Motion>', lambda correction = (position - box[0], time[0] - box[1]), event:
#                                                  showLocation(lowerX, lowerY, position, time, event))
                    except KeyError: pass
                offset += upper - lower

            if parents:
                indentation -= 20
                upperLabel, positions = parents.pop()
                label = createLabel(upperLabel, offset, True, indentation)

                substructure = structures.pop()
                otherLabel, hasText = superlabels.pop()
                if substructure:
                    substructure[ 0][ 0][1] = True
                    substructure[-1][+1][1] = True
                structures[-1].append([ [otherLabel, False, hasText]
                                      , [label, False, bool(upperLabel)]
                                      , substructure ])
                changeOffset = True

        self.positionLabels.structure = structures[0]

        for time, text in sorted(timeLabels):
            createLabel(text, time)

        drawingRegions = self.drawingRegions()
        lowerX, upperX, lowerY, upperY, _, _, positionsLowerX, positionsUpperX = drawingRegions

        for label, time in verticalLines.items():
            self.timeLabels.lines[label] \
                = (self.content.create_line(time, lowerY, time, upperY), False),
            hideLines(label, self.timeLabels)
        for label, (position, indentation) in horizontalLines.items():
            self.positionLabels.lines[label] \
                = (self.content.create_line(lowerX, position, upperX, position), False) \
                , (self.positionLabels.create_line(positionsLowerX + indentation, position, positionsUpperX, position), True)
            hideLines(label, self.positionLabels)

        self.setScrollRegions(drawingRegions)
        self.content.width  = upperX - lowerX
        self.content.height = upperY - lowerY

    def plotLegend(self, event):
        self.legend.delete('all')

        def showContent(value, rectangle):
            self.content.itemconfigure('value{:x}'.format(value), state = 'normal')
            self.legend.itemconfigure(rectangle, fill = self.coloring[value])
            self.legend.tag_bind(rectangle, '<Button-1>', lambda _: hideContent(value, rectangle))

        def hideContent(value, rectangle):
            self.content.itemconfigure('value{:x}'.format(value), state = 'hidden')
            self.legend.itemconfigure(rectangle, fill = self.backgroundColor)
            self.legend.tag_bind(rectangle, '<Button-1>', lambda _: showContent(value, rectangle))

        x, y = 0, 0
        yend = 0

        for value, explanationText in self.explanation.items():
            rectangle = self.legend.create_rectangle(
                x, y, x + 10, y + 10, fill = self.coloring[value])
            label = self.legend.create_text(
                x + 15, y, text = explanationText, anchor = 'nw')

            self.legend.tag_bind(rectangle, '<Button-1>', lambda _, value = value, rectangle = rectangle: hideContent(value, rectangle))

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

    def setScrollRegions(self, drawingRegions):
        lowerX, upperX, lowerY, upperY, \
        timeLabelsLowerY, timeLabelsUpperY, \
        positionLabelsLowerX, positionLabelsUpperX = drawingRegions
        
        self.content['scrollregion'] = lowerX, lowerY, upperX, upperY

        self.timeLabels['scrollregion'] = lowerX, timeLabelsLowerY, \
                                          upperX, timeLabelsUpperY
        self.timeLabels['height'] = timeLabelsUpperY - timeLabelsLowerY

        self.positionLabels['scrollregion'] = positionLabelsLowerX, lowerY, \
                                              positionLabelsUpperX, upperY
        self.positionLabels['width'] = positionLabelsUpperX - positionLabelsLowerX

    def drawingRegions(self):
        contentBox = self.content.bbox('all')
        timeLabelsBox = self.timeLabels.bbox('all')
        positionLabelsBox = self.positionLabels.bbox('all')

        if contentBox is None:
            if timeLabelsBox is None: timeLabelsBox = 0, 0, 0, 0
            lowerX, timeLabelsLowerY, upperX, timeLabelsUpperY = timeLabelsBox

            if positionLabelsBox is None: positionLabelsBox = 0, 0, 0, 0
            positionLabelsLowerX, lowerY, positionLabelsUpperX, upperY = positionLabelsBox

        else:
            if timeLabelsBox is None:
                lowerX, upperX = contentBox[0], contentBox[2]
                timeLabelsLowerY, timeLabelsUpperY = 0, 0
            else:
                lowerX = min(contentBox[0], timeLabelsBox[0])
                upperX = max(contentBox[2], timeLabelsBox[2])
                timeLabelsLowerY = timeLabelsBox[1]
                timeLabelsUpperY = timeLabelsBox[3]

            if positionLabelsBox is None:
                lowerY, upperY = contentBox[1], contentBox[3]
                positionLabelsLowerX, positionLabelsUpperX = 0, 0
            else:
                lowerY = min(contentBox[1], positionLabelsBox[1])
                upperY = max(contentBox[3], positionLabelsBox[3])
                positionLabelsLowerX = positionLabelsBox[0]
                positionLabelsUpperX = positionLabelsBox[2]

        return (lowerX, upperX, lowerY, upperY,
                timeLabelsLowerY, timeLabelsUpperY,
                positionLabelsLowerX, positionLabelsUpperX)
