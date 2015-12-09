from tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
from tkinter.filedialog import asksaveasfile
import tkinter.ttk as themed
from canvasvg import SVGdocument, convert
from sortedcontainers import SortedDict

from grouping import Grouping, Interval

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, time_labels, position_groups,
                 mirror = True):

        style = themed.Style()
        style.configure('.', background = 'white')

        self.coloring = coloring
        self.explanation = explanation

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

        default_text = self.time_labels.create_text(0, 0, anchor = 'n')
        self.time_labels.default_text_size = self.time_labels.bbox(default_text)[3]
        self.time_labels.delete(default_text)

        self.content.unit_point = self.content.create_rectangle(0, 0, 0, 0, width = 0, state = 'hidden')

        self.content.no_managing = False
        self.content.cancel_identifier = None

        self.time_labels.lines = {}
        self.position_labels.lines = {}
        self.content.lines = []
        self.time_labels.labels = SortedDict()

        self.plot(data, time_labels, position_groups, None, mirror)

        self.scroll_horizontal = themed.Scrollbar(self.mainframe, orient = HORIZONTAL)
        self.scroll_vertical   = themed.Scrollbar(self.mainframe, orient = VERTICAL)

        def scroll_all_horizontal(*arguments):
            self.hide_pointer()
            for canvas in [self.content, self.time_labels]:
                canvas.xview(*arguments)

        def scroll_all_vertical(*arguments):
            self.hide_pointer()
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

        self.content.bind('<Enter>', lambda _: self.content.focus_set())
        self.content.bind('<Leave>', lambda _: self.manage_focus_loss())

        self.content.bind('<Motion>', self.manage_pointer)

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

    def manage_focus_loss(self):
        self.mainframe.focus_set()
        self.hide_pointer()

    def manage_pointer(self, event):
        self.hide_pointer()
        self.content.cancel_identifier = self.content.after(200, self.show_pointer, event.x, event.y)

    def show_pointer(self, x, y):
        self.content.cancel_identifier = None
        x, y = self.normalize_coordinates(self.content.canvasx(x), self.content.canvasy(y))

        time_index = self.time_labels.labels.bisect(x)
        if time_index:
            time_label = self.time_labels.labels[self.time_labels.labels.keys()[time_index - 1]]
            self.show_lines(time_label, self.time_labels)
            self.content.lines.append((time_label, self.time_labels))

    def hide_pointer(self):
        if self.content.cancel_identifier is not None:
            self.content.after_cancel(self.content.cancel_identifier)
            self.content.cancel_identifier = None

        for label, canvas in self.content.lines:
            self.hide_lines(label, canvas)
        self.content.lines = []

    def show_lines(self, label, canvas):
        for line, on_canvas in canvas.lines[label]:
            if on_canvas: line_canvas = canvas
            else: line_canvas = self.content
            line_canvas.tag_raise(line)
            line_canvas.itemconfigure(line, fill = 'black')
        canvas.itemconfigure(label, fill = 'darkblue')

    def hide_lines(self, label, canvas):
        for line, on_canvas in canvas.lines[label]:
            if on_canvas: line_canvas = canvas
            else: line_canvas = self.content
            line_canvas.tag_lower(line)
            line_canvas.itemconfigure(line, fill = 'lightgrey')
        canvas.itemconfigure(label, fill = 'black')

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

    def normalize_coordinates(self, x, y):
        position = (self.content.canvasx(x), self.content.canvasy(y))
        unit_coordinates = self.content.coords(self.content.unit_point)
        return map(lambda a, b: (a - b) // self.current_zoom, position, unit_coordinates)

    def manage_content(self, event = None):
        if self.content.no_managing:
            self.content.no_managing = False
            return

        self.hide_pointer()
        self.manage_time_labels()
        self.manage_position_labels()
        self.set_scroll_regions(self.drawing_regions())

        if event is not None:
            if self.time_labels.winfo_height() > event.height:
                self.time_labels['height'] = 0
                self.content.no_managing = True
            if self.position_labels.winfo_width() > event.width:
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
                self.time_labels.lines[label][1:] = [(line, True)]
            self.time_labels.tag_lower('line')

    def manage_position_labels(self, event = None):
        dependency = self.position_labels.dependency

        self.position_labels.itemconfigure('label', state = 'normal', fill = 'black')
        for lower_label, upper_label in self.position_labels.labels.values():

            lower_todo = []
            while lower_label in dependency:
                lower_todo.append(lower_label)
                lower_label = dependency[lower_label]

            upper_todo = []
            while upper_label in dependency:
                upper_todo.append(upper_label)
                upper_label = dependency[upper_label]

            lower_box = self.position_labels.bbox(lower_label)[1::2]
            upper_box = self.position_labels.bbox(upper_label)[1::2]

            if lower_box[1] > upper_box[0]:
                self.position_labels.itemconfigure(upper_label, state = 'hidden')
                if lower_box[1] > upper_box[1]: self.position_labels.itemconfigure(lower_label, state = 'hidden')
                for label in lower_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                for label in upper_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                lower_todo = upper_todo = []

            lower_limit = lower_box[1]
            upper_limit = upper_box[0]
            while lower_todo and upper_todo:
                lower_label = lower_todo.pop()
                upper_label = upper_todo.pop()
                lower_box = self.position_labels.bbox(lower_label)[1::2]
                upper_box = self.position_labels.bbox(upper_label)[1::2]
                lower_distance = lower_limit - lower_box[0]
                upper_distance = upper_limit - upper_box[1]
                self.position_labels.move(lower_label, 0, lower_distance)
                self.positoin_labels.move(upper_label, 0, upper_distance)
                lower_limit = lower_box[1] + lower_distance
                upper_limit = upper_box[0] + upper_distance

                if lower_limit > upper_limit:
                    self.position_labels.itemconfigure(upper_label, state = 'hidden')
                    if lower_limit > upper_box[1] + upper_distance:
                        self.position_labels.itemconfigure(lower_label, state = 'hidden')
                    for label in lower_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                    for label in upper_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                    lower_todo = upper_todo = []
                    break

            while lower_todo:
                lower_label = lower_todo.pop()
                lower_box = self.position_labels.bbox(lower_label)[1::2]
                lower_distance = lower_limit - lower_box[0]
                self.position_labels.move(lower_label, 0, lower_distance)
                lower_limit = lower_box[1] + lower_distance

                if lower_limit > upper_limit:
                    self.position_labels.itemconfigure(lower_label, state = 'hidden')
                    for label in lower_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                    break

            while upper_todo:
                upper_label = upper_todo.pop()
                upper_box = self.position_labels.bbox(upper_label)[1::2]
                upper_distance = upper_limit - upper_box[1]
                self.positoin_labels.move(upper_label, 0, upper_distance)
                upper_limit = upper_box[0] + upper_distance

                if upper_limit < lower_limit:
                    self.position_labels.itemconfigure(lower_label, state = 'hidden')
                    for label in upper_todo: self.position_labels.itemconfigure(label, state = 'hidden')
                    break

    def plot(self, data, time_labels, position_groups, location_information, mirror = False):
        vertical_lines = {}
        horizontal_lines = {}

        def show_location(correction, event):
            x,y = map(lambda a, b: a + b, self.normalize_coordinates(event.x, event.y), correction)

 #            self.location_label['text'] = location_information(x,y)
    
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
                            lambda _, label = label: canvas.after_idle(self.show_lines, label, canvas))
            canvas.tag_bind(label, '<Leave>',
                            lambda _, label = label: canvas.after_idle(self.hide_lines, label, canvas))

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
        last_label, last_offset = None, None
        label_pairs = []
        unpaired_labels = []


        items = position_groups.items()
        if mirror: items = reversed(items)
        for interval, grouping in items:
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
                paire_label = unpaired_labels.pop()

                if mirror and child_label is None: text = old_grouping.header
                else: text = old_grouping.footer

                if text:
                    label = create_label(text, offset, True, indentation)

                    if not paire_label is None:
                        label_pairs.append((label, paire_label))

                    if child_label is not None:
                        dependency[child_label] = label
                        child_label = label
                    else:
                        assert last_label is not None and last_offset is not None
                        labels[last_offset, offset] = last_label, label
                indentation -= 20

            offset += 10
            indentation += 20

            if mirror and not new_groups: text = grouping.footer
            else: text = grouping.header

            parent_label = create_label(text, offset, False, indentation)

            unpaired_labels.append(parent_label)
            groups.append(grouping)

            while new_groups:
                grouping = new_groups.pop()
                groups.append(grouping)
                indentation += 20

                if mirror and not new_groups: text = grouping.footer
                else: text = grouping.header

                if text:
                    label = create_label(text, offset, False, indentation)
                    unpaired_labels.append(label)
                    dependency[label] = parent_label
                    parent_label = label
                else: unpaired_labels.append(None)

            last_label, last_offset = parent_label, offset
            lower, upper = interval

            if mirror: position_range = range(upper - 1, lower - 1, - 1)
            else:      position_range = range(lower, upper)

            for position in position_range:
                try:
                    for time, value in data[position].items():
                        if mirror: location = offset + upper - position - 1
                        else:      location = offset + position - lower

                        box = time[0], location, time[1], location + 1
                        point = self.content.create_rectangle(box, width = 0, fill = self.coloring[value], tag = 'value{:x}'.format(value))
                        self.content.tag_bind(point, '<Motion>', lambda event, correction = (0, position - location): show_location(correction, event))
                except KeyError: pass
            offset += interval.length

        child_label = None
        while groups:
            grouping = groups.pop()
            paire_label = unpaired_labels.pop()

            if mirror and child_label is None: text = grouping.header
            else: text = grouping.footer

            if text:
                label = create_label(text, offset, True, indentation)

                if paire_label is not None:
                    label_pairs.append((label, paire_label))

                if child_label is not None:
                    dependency[child_label] = label
                    child_label = label
                else:
                    assert last_label is not None and last_offset is not None
                    labels[last_offset, offset] = last_label, label
            indentation -= 20

        for time, text in sorted(time_labels):
            label = create_label(text, time)
            self.time_labels.labels[time] = label

        drawing_regions = self.drawing_regions()
        lower_x, upper_x, lower_y, upper_y, _, _, positions_lower_x, positions_upper_x = drawing_regions

        for label, time in vertical_lines.items():
            self.time_labels.lines[label] \
                = [(self.content.create_line(time, lower_y, time, upper_y), False)]
            self.hide_lines(label, self.time_labels)
        for label, position in horizontal_lines.items():
            position, indentation = position
            self.position_labels.lines[label] = \
                [ (self.content.create_line(lower_x, position, upper_x, position), False) \
                , (self.position_labels.create_line(positions_lower_x + indentation, position, positions_upper_x, position), True) ]
            self.hide_lines(label, self.position_labels)

        for label_1, label_2 in label_pairs:
            list_1 = self.position_labels.lines[label_1]
            list_2 = self.position_labels.lines[label_2]
            self.position_labels.lines[label_1] = self.position_labels.lines[label_2] = list_1 + list_2

        self.position_labels.dependency = dependency
        self.position_labels.labels = labels

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
            self.legend.itemconfigure(rectangle, fill = self.background_color)
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
