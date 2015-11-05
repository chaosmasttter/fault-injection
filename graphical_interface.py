from tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
from tkinter.filedialog import asksaveasfile
import tkinter.ttk as themed
from canvasvg import SVGdocument, convert

from grouping import Grouping, Interval

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, time_labels, position_groups,
                 mirror = False):

        style = themed.Style()
        style.configure('.', background = 'white')


        self.data = data
        self.coloring = coloring
        self.explanation = explanation
        self.time_labels = time_labels

        self.current_zoom = 1.0
        self.minimal_zoom = 1.0
        self.maximal_zoom = 10.0

        # the frame containing all widgets needed for the visualisation
        self.mainframe = themed.Frame(parent, padding = 5)

        self.content         = Canvas(self.mainframe)
        self.time_labels     = Canvas(self.mainframe)
        self.position_labels = Canvas(self.mainframe)
        self.legend          = Canvas(self.mainframe)

        self.location_label = themed.Label(self.mainframe)

        # set the background color of the canvases
        # to match that of the themed widgets
        self.background_color = style.lookup('.', 'background')
        for canvas in self.content, self.time_labels, self.position_labels, self.legend:
            canvas['background'] = self.background_color
            canvas['highlightthickness'] = 0

        self.content.no_managing = False

        default_text = self.time_labels.create_text(0, 0, anchor = 'n')
        self.time_labels.default_text_size = self.time_labels.bbox(default_text)[3]
        self.time_labels.delete(default_text)

        self.plot(time_labels, position_groups, None, mirror)

        self.scroll_horizontal = themed.Scrollbar(self.mainframe, orient = HORIZONTAL)
        self.scroll_vertical   = themed.Scrollbar(self.mainframe, orient = VERTICAL)

        def scroll_all_horizontal(*arguments):
            for canvas in [self.content, self.time_labels]:
                canvas.xview(*arguments)

        def scroll_all_vertical(*arguments):
            for canvas in [self.content, self.position_labels]:
                canvas.yview(*arguments)

        def bind_scroll_command(scroll_event, scroll_function, direction):
            self.mainframe.bind_all(scroll_event, lambda _: self.force
                                    (scroll_function, 'scroll', direction, 'units'))

        # set the right callbacks for the scrollbars
        for canvas in [self.content, self.time_labels]:
            canvas['xscrollcommand'] = self.scroll_horizontal.set

        for canvas in [self.content, self.position_labels]:
            canvas['yscrollcommand'] = self.scroll_vertical.set

        self.scroll_horizontal['command'] = scroll_all_horizontal
        self.scroll_vertical  ['command'] = scroll_all_vertical

        self.mainframe.event_add('<<ScrollUp>>',    '<Up>',    '<Button-4>')
        self.mainframe.event_add('<<ScrollDown>>',  '<Down>',  '<Button-5>')
        self.mainframe.event_add('<<ScrollLeft>>',  '<Left>',  '<Shift-Button-4>')
        self.mainframe.event_add('<<ScrollRight>>', '<Right>', '<Shift-Button-5>')

        bind_scroll_command('<<ScrollUp>>',    scroll_all_vertical,   - 1)
        bind_scroll_command('<<ScrollDown>>',  scroll_all_vertical,   + 1)
        bind_scroll_command('<<ScrollLeft>>',  scroll_all_horizontal, - 1)
        bind_scroll_command('<<ScrollRight>>', scroll_all_horizontal, + 1)

        self.content.event_add('<<ZoomIn>>',  '+', '<Control-Button-4>')
        self.content.event_add('<<ZoomOut>>', '-', '<Control-Button-5>')
        
        self.content.bind('<<ZoomIn>>',  lambda event: self.zoom(1.1, event)) 
        self.content.bind('<<ZoomOut>>', lambda event: self.zoom(0.9, event))

        self.legend .bind('<Configure>', self.plot_legend)
        self.content.bind('<Configure>', self.manage_content)

        self.content.bind('<Enter>', lambda _: self.content  .focus_set())
        self.content.bind('<Leave>', lambda _: self.mainframe.focus_set())

        self.mainframe.bind_all('s', lambda _: self.save_screenshot())

        # place everything on the screen
        self.time_labels      .grid(column = 1, row = 0, sticky = 'nsew')
        self.position_labels  .grid(column = 0, row = 1, sticky = 'nsew')
        self.content          .grid(column = 1, row = 1, sticky = 'nsew')
        self.scroll_vertical  .grid(column = 2, row = 1, sticky = 'nsew')
        self.scroll_horizontal.grid(column = 1, row = 2, sticky = 'nsew')
        self.legend           .grid(column = 1, row = 3, sticky = 'nsew')
        self.location_label   .grid(column = 1, row = 4, sticky = 'nsew')

        self.mainframe.columnconfigure(1, weight = 1)
        self.mainframe.rowconfigure(   1, weight = 1)

    def force(self, function = None, *arguments):
        if callable(function): function(*arguments)
        self.mainframe.update_idletasks()

    def save_screenshot(self):
        document = SVGdocument()

        def set_view_box(graphic, width, height, x, y, X = None, Y = None):
            if X is None: X = width
            else: X -= x
            if Y is None: Y = height
            else: Y -= y

            graphic.setAttribute('width',   "%0.3f" % width)
            graphic.setAttribute('height',  "%0.3f" % height)
            graphic.setAttribute('viewBox', "%0.3f %0.3f %0.3f %0.3f" % (x, y, X, Y))
            return graphic

        def create_graphic(canvas):
            graphic = document.createElement('svg')

            width  = canvas.winfo_width()
            height = canvas.winfo_height()

            x = canvas.canvasx(0)
            y = canvas.canvasy(0)
            X = canvas.canvasx(width)
            Y = canvas.canvasy(height)

            set_view_box(graphic, width, height, x, y, X, Y)

            for element in convert(document, canvas, canvas.find_overlapping(x, y, X, Y)):
                graphic.appendChild(element)

            document.documentElement.appendChild(graphic)

            return graphic, width, height

        content_width, content_height = create_graphic(self.content)[1:]

        time_labels_graphic, _, time_labels_height = create_graphic(self.time_labels)
        time_labels_graphic.setAttribute('y', "-%0.3f" % time_labels_height)

        position_labels_graphic, position_labels_width, _ = create_graphic(self.position_labels)
        position_labels_graphic.setAttribute('x', "-%0.3f" % position_labels_width)

        content_height += 5

        legend_graphic, _, legend_height = create_graphic(self.legend)
        legend_graphic.setAttribute('y', "%0.3f" % content_height)

        set_view_box(document.documentElement,
                     position_labels_width + content_width,
                     time_labels_height + content_height + legend_height,
                     - position_labels_width, - time_labels_height)

        savefile = asksaveasfile(defaultextension = '.svg',
                                 initialfile = 'screenshot.svg',
                                 title = 'Select file to store the screenshot in.',
                                 parent = self.mainframe)

        if savefile:
            with savefile as screenshot:
                screenshot.write(document.toxml())

    def zoom(self, scale, event):
        x, y = self.content.canvasx(event.x), self.content.canvasy(event.y)

        if scale < 1: self.content.bind('<<ZoomIn>>',  lambda event: self.zoom(1.1, event))
        if scale > 1: self.content.bind('<<ZoomOut>>', lambda event: self.zoom(0.9, event))

        if scale * self.current_zoom > self.maximal_zoom:
            scale = self.maximal_zoom / self.current_zoom
            self.content.unbind('<<ZoomIn>>')
        if scale * self.current_zoom < self.minimal_zoom:
            scale = self.minimal_zoom / self.current_zoom
            self.content.unbind('<<ZoomOut>>')

        self.current_zoom *= scale

        self.content        .scale('all', x, y, scale, scale)
        self.time_labels    .scale('all', x, y, scale, 1,   )
        self.position_labels.scale('all', x, y, 1,     scale)

        self.manage_content()

    def manage_content(self, event = None):
        if self.content.no_managing:
            self.content.no_managing = False
            return

        self.manage_time_labels()
        self.manage_position_labels()
        self.set_scroll_regions(self.drawing_regions())

        if event is not None:
            if int(self.time_labels['height']) > event.height:
                self.time_labels['height'] = 0
                self.content.no_managing = True
            if int(self.position_labels['width']) > event.width:
                self.position_labels['width'] = 0
                self.content.no_managing = True

            self.minimal_zoom = min(float(event.width)  / self.content.width,
                                    float(event.height) / self.content.height)

    def manage_time_labels(self, event = None):
        self.time_labels.delete('line')
        self.time_labels.itemconfigure('all', state = 'normal')

        text_size = self.time_labels.default_text_size

        offset = {}
        line_start = []

        height = None

        for label in self.time_labels.find_all():
            lower_x, lower_y, upper_x, upper_y = self.time_labels.bbox(label)

            line = 0
            while line in offset and lower_x < offset[line] + text_size: line += 1

            distance = line * text_size - lower_y
            self.time_labels.move(label, 0, distance)
            line_start.append((label, lower_x + 1, upper_y + distance))
            offset[line] = upper_x

            try: height = max(upper_y, height)
            except TypeError: height = upper_y

        if height is not None:
            height += text_size
            for label, x, y in line_start:
                line = self.time_labels.create_line(x, y, x, height, tags = 'line', fill = 'lightgrey')
                self.time_labels.lines[label] = self.time_labels.lines[label][0], (line, True)
            self.time_labels.tag_lower('line')

    def manage_position_labels(self, event = None):
        dependency = self.position_labels.dependency
        labels = []

        self.position_labels.itemconfigure('label', state = 'normal')
        for label, below in self.position_labels.labels.values():
            todo = []
            while label in dependency:
                todo.append(label)
                label = dependency[label]

            box = self.position_labels.bbox(label)
            label_list = [(label, box)]
            if below: index, parent_index = 1, 3
            else: index, parent_index = 3, 1

            while todo:
                label = todo.pop()
                parent_box = box
                box = self.position_labels.bbox(label)

                distance = parent_box[parent_index] - box[index]
                self.position_labels.move(label, 0, distance)

                label_list.append((label, (box[0], box[1] + distance + 1, box[2], box[3] + distance - 1)))
            labels.append(label_list)

        while labels:
            hide = False
            label_list = labels.pop()
            for label, box in label_list:
                if hide: self.position_labels.itemconfigure(label, state = 'hidden')
                elif self.position_labels.find_overlapping(*box) != tuple([label]):
                    self.position_labels.itemconfigure(label, state = 'hidden')
                    hide = True

    def plot(self, time_labels, position_groups, location_information, mirror = True):
        self.time_labels.lines = {}
        self.position_labels.lines = {}

        vertical_lines = {}
        horizontal_lines = {}

        unit_point = self.content.create_rectangle(1, 1, 1, 1, width = 0, state = 'hidden')

        def show_location(correction, event):
            x = self.content.canvasx(event.x) / self.content.coords(unitPoint)[0] - correction[0]
            y = self.content.canvasx(event.y) / self.content.coords(unitPoint)[1] - correction[1]

            self.locationLabel['text'] = location_information(x,y)
    
        def show_lines(label, canvas):
            for line, on_canvas in canvas.lines[label]:
                if on_canvas:
                    line_canvas = canvas
                else:
                    line_canvas = self.content
                line_canvas.tag_raise(line)
                line_canvas.itemconfigure(line, fill = 'black')

        def hide_lines(label, canvas):
            for line, on_canvas in canvas.lines[label]:
                if on_canvas:
                    line_canvas = canvas
                else:
                    line_canvas = self.content
                line_canvas.tag_lower(line)
                line_canvas.itemconfigure(line, fill = 'lightgrey')

        def create_label(text, distance, above_line = None, indentation = 0):
            anchor = 'nw'
            if above_line is None:
                canvas = self.time_labels
                position = distance, 0
            else:
                canvas = self.position_labels
                position = indentation, distance
                if above_line: anchor = 'sw'

            label = canvas.create_text(*position, text = text, tag = 'label', anchor = anchor)
            canvas.tag_bind(label, '<Enter>',
                            lambda _, label = label: canvas.after_idle(show_lines, label, canvas))
            canvas.tag_bind(label, '<Leave>',
                            lambda _, label = label: canvas.after_idle(hide_lines, label, canvas))

            if canvas is self.time_labels:
                vertical_lines[label] = distance
            else:
                horizontal_lines[label] = distance, indentation

            return label

        offset = -10
        indentation = 0
        groups = []
        dependency = {}
        labels = {}
        for interval, grouping in position_groups.items():
            assert isinstance(grouping, Grouping)
            assert isinstance(interval, Interval)
            grouping.seen = True

            new_groups = []
            while grouping.parent and not grouping.parent.seen:
                new_groups.append(grouping)
                grouping = grouping.parent
                grouping.seen = True

            child_label = None
            while groups and groups[-1] is not grouping.parent:
                old_grouping = groups.pop()
                label = create_label(old_grouping.footer, offset, True, indentation)
                indentation -= 20
                if child_label is not None:
                    dependency[child_label] = label
                    child_label = label
                else: labels[offset] = label, False

            offset += 10
            indentation += 20

            parent_label = create_label(grouping.header, offset, False, indentation)
            groups.append(grouping)
            while new_groups:
                grouping = new_groups.pop()
                groups.append(grouping)
                indentation += 20
                label = create_label(grouping.header, offset, False, indentation)
                dependency[label] = parent_label
                parent_label = label

            labels[offset] = parent_label, True
            lower, upper = interval

            if mirror: position_range = range(upper - 1, lower - 1, - 1)
            else:      position_range = range(lower, upper)

            for position in position_range:
                try:
                    for time, value in self.data[position].items():
                        if mirror: location = offset + upper - position - 1
                        else:      location = offset + position - lower

                        box = time[0], location, time[1], location + 1
                        point = self.content.create_rectangle(box, width = 0, fill = self.coloring[value], tag = 'value{:x}'.format(value))
#                       self.content.tag_bind(point, '<Motion>', lambda correction = (position - box[0], time[0] - box[1]), event:
#                                                                showLocation(lowerX, lowerY, position, time, event))
                except KeyError: pass
            offset += interval.length

        child_label = None
        while groups:
            grouping = groups.pop()
            label = create_label(grouping.footer, offset, True, indentation)
            indentation -= 20
            if child_label is not None:
                dependency[child_label] = label
                child_label = label
            else: labels[offset] = label, False

        self.position_labels.dependency = dependency
        self.position_labels.labels = labels
#         tags = []
#         offset = 0
#         indentation = 0
#         change_offset = False
# 
#         parents = []
#         superlabels = []
#         if not mirror:
#             stack = [(None, positions)]
#             while stack:
#                 _, subpositions = stack.pop()
#                 if not isinstance(subpositions, list): continue
#                 stack.extend(subpositions[:])
#                 subpositions.reverse()
# 
#         structures = [[]]
#         while positions or parents:
#             while isinstance(positions, list):
#                 if not positions: break
# 
#                 if change_offset: offset += 20
#                 change_offset = False
# 
#                 labels, subpositions = positions.pop()
#                 lower_label, upper_label = labels
#                 if mirror: lower_label, upper_label = upper_label, lower_label
#                 
#                 label = create_label(lower_label, offset, False, indentation)
#                 superlabels.append([label, bool(lower_label)])
#                 structures.append([])
#                 
#                 parents.append((upper_label, positions))
#                 positions = subpositions
#                 indentation += 20
# 
#             if isinstance(positions, tuple):
#                 lower, upper = positions
#                 if lower > upper: lower, upper = upper, lower
# 
#                 if mirror:
#                     position_range = range(upper - 1, lower - 1, - 1)
#                 else:
#                     position_range = range(lower, upper)
# 
#                 for position in position_range:
#                     try:
#                         for time, value in self.data[position].items():
#                             if mirror:
#                                 location = offset + upper - position - 1
#                             else:
#                                 location = offset + position - lower
# 
#                             box = time[0], location, time[1], location + 1
#                             point = self.content.create_rectangle(box, width = 0, fill = self.coloring[value], tag = 'value{:x}'.format(value))
# #                            self.content.tag_bind(point, '<Motion>', lambda correction = (position - box[0], time[0] - box[1]), event:
# #                                                  showLocation(lowerX, lowerY, position, time, event))
#                     except KeyError: pass
#                 offset += upper - lower
# 
#             if parents:
#                 indentation -= 20
#                 upper_label, positions = parents.pop()
#                 label = create_label(upper_label, offset, True, indentation)
# 
#                 substructure = structures.pop()
#                 other_label, has_text = superlabels.pop()
#                 if substructure:
#                     substructure[ 0][ 0][1] = True
#                     substructure[-1][+1][1] = True
#                 structures[-1].append([ [other_label, False, has_text]
#                                       , [label, False, bool(upper_label)]
#                                       , substructure ])
#                 change_offset = True
# 
#         self.position_labels.structure = structures[0]

        for time, text in sorted(time_labels): create_label(text, time)

        drawing_regions = self.drawing_regions()
        lower_x, upper_x, lower_y, upper_y, _, _, positions_lower_x, positions_upper_x = drawing_regions

        for label, time in vertical_lines.items():
            self.time_labels.lines[label] \
                = (self.content.create_line(time, lower_y, time, upper_y), False),
            hide_lines(label, self.time_labels)
        for label, position in horizontal_lines.items():
            position, indentation = position
            self.position_labels.lines[label] \
                = (self.content.create_line(lower_x, position, upper_x, position), False) \
                , (self.position_labels.create_line(positions_lower_x + indentation, position, positions_upper_x, position), True)
            hide_lines(label, self.position_labels)

        self.set_scroll_regions(drawing_regions)
        self.content.width  = upper_x - lower_x
        self.content.height = upper_y - lower_y

    def plot_legend(self, event):
        self.legend.delete('all')

        def show_content(value, rectangle):
            self.content.itemconfigure('value{:x}'.format(value), state = 'normal')
            self.legend.itemconfigure(rectangle, fill = self.coloring[value])
            self.legend.tag_bind(rectangle, '<Button-1>', lambda _: hide_content(value, rectangle))

        def hide_content(value, rectangle):
            self.content.itemconfigure('value{:x}'.format(value), state = 'hidden')
            self.legend.itemconfigure(rectangle, fill = self.backgroundColor)
            self.legend.tag_bind(rectangle, '<Button-1>', lambda _: show_content(value, rectangle))

        x, y = 0, 0
        yend = 0

        for value, explanation_text in self.explanation.items():
            rectangle = self.legend.create_rectangle(
                x, y, x + 10, y + 10, fill = self.coloring[value])
            label = self.legend.create_text(
                x + 15, y, text = explanation_text, anchor = 'nw')

            self.legend.tag_bind(rectangle, '<Button-1>', lambda _, value = value, rectangle = rectangle: hide_content(value, rectangle))

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

    def set_scroll_regions(self, drawing_regions):
        lower_x, upper_x, lower_y, upper_y, \
        time_labels_lower_y, time_labels_upper_y, \
        position_labels_lower_x, position_labels_upper_x = drawing_regions
        
        self.content['scrollregion'] = lower_x, lower_y, upper_x, upper_y

        self.time_labels['scrollregion'] = lower_x, time_labels_lower_y, \
                                           upper_x, time_labels_upper_y
        self.time_labels['height'] = time_labels_upper_y - time_labels_lower_y

        self.position_labels['scrollregion'] = position_labels_lower_x, lower_y, \
                                               position_labels_upper_x, upper_y
        self.position_labels['width'] = position_labels_upper_x - position_labels_lower_x

    def drawing_regions(self):
        content_box = self.content.bbox('all')
        time_labels_box = self.time_labels.bbox('all')
        position_labels_box = self.position_labels.bbox('all')

        if content_box is None:
            if time_labels_box is None: time_labels_box = 0, 0, 0, 0
            lower_x, time_labels_lower_y, upper_x, time_labels_upper_y = time_labels_box

            if position_labels_box is None: position_labels_box = 0, 0, 0, 0
            position_labels_lower_x, lower_y, position_labels_upper_x, upper_y = position_labels_box

        else:
            if time_labels_box is None:
                lower_x, upper_x = content_box[0], content_box[2]
                time_labels_lower_y, time_labels_upper_y = 0, 0
            else:
                lower_x = min(content_box[0], time_labels_box[0])
                upper_x = max(content_box[2], time_labels_box[2])
                time_labels_lower_y = time_labels_box[1]
                time_labels_upper_y = time_labels_box[3]

            if position_labels_box is None:
                lower_y, upper_y = content_box[1], content_box[3]
                position_labels_lower_x, position_labels_upper_x = 0, 0
            else:
                lower_y = min(content_box[1], position_labels_box[1])
                upper_y = max(content_box[3], position_labels_box[3])
                position_labels_lower_x = position_labels_box[0]
                position_labels_upper_x = position_labels_box[2]

        return (lower_x, upper_x, lower_y, upper_y,
                time_labels_lower_y, time_labels_upper_y,
                position_labels_lower_x, position_labels_upper_x)
