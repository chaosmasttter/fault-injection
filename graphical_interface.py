from tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL
from tkinter.filedialog import asksaveasfile
from tkinter.font import Font
import tkinter.ttk as themed
from canvasvg import SVGdocument, convert
from sortedcontainers import SortedDict
from collections import namedtuple

from grouping import Grouping, Interval

class Visualisation(object):
    def __init__(self, parent, data, coloring,
                 explanation, time_labels, position_groups,
                 location_information, mirror = True):

        self.style = themed.Style()
        self.style.configure('.', background = 'white')

        self.coloring = coloring
        self.explanation = explanation

        self.minimal_zoom = 0.1
        self.maximal_zoom = 10.0

        # the frame containing all widgets needed for the visualisation
        self.mainframe = themed.Frame(parent, padding = 5)

        self.content         = Canvas(self.mainframe)
        self.time_labels     = Canvas(self.mainframe)
        self.position_labels = Canvas(self.mainframe)
        self.legend          = Canvas(self.mainframe)

        self.location_label = themed.Label(self.mainframe, font = '-size 9')

        # set the background color of the canvases
        # to match that of the themed widgets
        self.background_color = self.style.lookup('.', 'background')
        for canvas in self.content, self.time_labels, self.position_labels, self.legend:
            canvas['background'] = self.background_color
            canvas['highlightthickness'] = 0

        default_text = self.time_labels.create_text(0, 0, anchor = 'n')
        self.time_labels.default_text_size = self.time_labels.bbox(default_text)[3]
        self.time_labels.delete(default_text)

        self.content.origin     = self.content.create_rectangle(0, 0, 0, 0, width = 0, state = 'hidden')
        self.content.unit_point = self.content.create_rectangle(1, 1, 1, 1, width = 0, state = 'hidden')

        self.mirror = mirror
        self.content.no_managing = False
        self.content.cancel_identifier = None

        self.time_labels.inner_lines = {}
        self.time_labels.outer_lines = {}
        self.time_labels.labels = SortedDict()
        self.position_labels.labels = SortedDict()

        self.content        .event_add('<<Inside>>', '<Enter>', '<Motion>')
        self.time_labels    .event_add('<<Inside>>', '<Enter>', '<Motion>')
        self.position_labels.event_add('<<Inside>>', '<Enter>', '<Motion>')

        self.plot(data, time_labels, position_groups, location_information)

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
        
        self.content.bind('<<ZoomIn>>',  lambda _: self.zoom(1.1)) 
        self.content.bind('<<ZoomOut>>', lambda _: self.zoom(0.9))

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
        self.location_label   .grid(column = 1, row = 2, sticky = 'nsew')
        self.scroll_horizontal.grid(column = 1, row = 3, sticky = 'nsew')
        self.legend           .grid(column = 1, row = 4, sticky = 'nsew')
        self.scroll_vertical  .grid(column = 2, row = 1, sticky = 'nsew')

        self.mainframe.columnconfigure(1, weight = 1)
        self.mainframe.rowconfigure(   1, weight = 1)

    def force(self, function = None, *arguments):
        if callable(function): function(*arguments)
        self.mainframe.update_idletasks()

    def normalize_coordinates(self, x, y):
        position = (self.content.canvasx(x), self.content.canvasy(y))
        origin_coordinates = self.content.coords(self.content.origin)
        unit_coordinates   = self.content.coords(self.content.unit_point)
        return map(lambda a, b, c: (a - c) // (b - c), position, unit_coordinates, origin_coordinates)

    def manage_focus_loss(self):
        self.mainframe.focus_set()
        self.hide_pointer()

    def manage_pointer(self, event):
        self.hide_pointer()
        self.content.cancel_identifier = self.content.after(200, self.show_pointer, event.x, event.y)

    def show_marker(self, labels, canvas, lines):
        for label in labels:
            canvas.itemconfigure(label, fill = 'darkblue')
            canvas.addtag_withtag('active_marker_label', label)

        for line, canvas in lines:
            canvas.tag_raise(line)
            canvas.itemconfigure(line, fill = 'black')
            canvas.addtag_withtag('active_marker_line', line)

    def hide_marker(self):
        for canvas in [self.content, self.time_labels, self.position_labels]:
            canvas.tag_lower('active_marker_line')
            canvas.itemconfigure('active_marker_line', fill = 'lightgrey', tag = 'line')

        for canvas in [self.time_labels, self.position_labels]:
            canvas.itemconfigure('active_marker_label', fill = 'black')
            canvas.dtag('active_marker_label', 'active_marker_label')

    def show_time_marker(self, label):
        self.show_marker([label], self.time_labels,
                        [ (self.time_labels.inner_lines[label], self.time_labels)
                        , (self.time_labels.outer_lines[label], self.content) ] )

    def show_position_marker(self, group):
        labels = []
        if group.header is not None: labels.append(group.header)
        if group.footer is not None: labels.append(group.footer)
        self.show_marker(labels, self.position_labels,
                        [ (line, self.position_labels) for line in group.inner_lines ] +
                        [ (line, self.content)         for line in group.outer_lines ] )

    def show_pointer(self, x, y):
        self.content.cancel_identifier = None
        x, y = self.normalize_coordinates(x, y)
        if self.mirror: y = - y

        time_index = self.time_labels.labels.bisect(x)
        if time_index:
            time_label = self.time_labels.labels[self.time_labels.labels.keys()[time_index - 1]]
            self.show_time_marker(time_label)

        interval_index = self.position_labels.labels.bisect((y,y))
        intervals = self.position_labels.labels.keys()
        interval = intervals[interval_index - 1]
    
        group = self.position_labels.labels[interval]
        if interval.upper <= y:
            try:
                next_group = self.position_labels.labels[intervals[interval_index]]
            except IndexError: return

            depth_difference = group.depth - next_group.depth
            if depth_difference > 0:
                for _ in range(depth_difference):
                    group = group.parent
            elif depth_difference < 0:
                for _ in range(- depth_difference):
                    next_group = next_group.parent
            while group is not next_group:
                group = group.parent
                next_group = next_group.parent
                if group is next_group is None: return
                assert group is not None and next_group is not None
    
        while group is not None:
            self.show_position_marker(group)
            group = group.parent

    def hide_pointer(self):
        if self.content.cancel_identifier is not None:
            self.content.after_cancel(self.content.cancel_identifier)
            self.content.cancel_identifier = None

        self.hide_marker()

    def zoom(self, scale):
        x = self.content.canvasx(self.content.winfo_pointerx())
        y = self.content.canvasy(self.content.winfo_pointery())

        if scale < 1: self.content.bind('<<ZoomIn>>',  lambda _: self.zoom(1.1))
        if scale > 1: self.content.bind('<<ZoomOut>>', lambda _: self.zoom(0.9))

        current_zoom = self.content.coords(self.content.unit_point)[0] - self.content.coords(self.content.origin)[0]

        if scale * current_zoom > self.maximal_zoom:
            scale = self.maximal_zoom / current_zoom
            self.content.unbind('<<ZoomIn>>')
        if scale * current_zoom < self.minimal_zoom:
            scale = self.minimal_zoom / current_zoom
            self.content.unbind('<<ZoomOut>>')

        self.content        .scale('all', x, y, scale, scale)
        self.time_labels    .scale('all', x, y, scale, 1,   )
        self.position_labels.scale('all', x, y, 1,     scale)

        self.manage_content()

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
                self.time_labels.inner_lines[label] = line
            self.time_labels.tag_lower('line')

    def manage_position_labels(self, event = None):
        self.position_labels.itemconfigure('label', state = 'hidden', fill = 'black')
        for group in self.position_labels.labels.values():
            if group.header_moveable or group.footer_moveable:
                pass


    def plot(self, data, time_labels, position_groups, location_information):
        group_number = 0

        def show_location(event, correction):
            x, y = self.normalize_coordinates(event.x, event.y)
            if self.mirror: y = - y
            coordinates = map(lambda a, b: a - b, (x, y), correction)
            self.location_label['text'] = location_information(*coordinates)
    
        def create_time_label(label_text, distance):
            label = self.time_labels.create_text(distance, 0, text = label_text, tag = 'label', anchor = 'nw')

            self.time_labels.tag_bind(label, '<<Inside>>', lambda _, local_label = label:
                                      self.time_labels.after_idle(self.show_time_marker, local_label))
            self.time_labels.tag_bind(label, '<Leave>', lambda _: self.time_labels.after_idle(self.hide_marker))

            return label

        def create_group_labels(group, interval, parent = None):
            nonlocal group_number
            group_tag = 'group{:x}'.format(group_number)
            group_number += 1

            if self.mirror:
                lower = - interval.lower
                upper = - interval.upper
            else:
                lower = + interval.upper
                upper = + interval.lower
            
            if not group.header: header_label = None
            else: header_label = self.position_labels.create_text(group.depth * 20, upper,
                                                                  text = group.header, tags = ('label', group_tag),
                                                                  anchor = 'nw')


            if not group.footer: footer_label = None
            else: footer_label = self.position_labels.create_text(group.depth * 20, lower,
                                                                  text = group.footer, tags = ('label', group_tag),
                                                                  anchor = 'sw')

            label_group = Grouping(header_label, footer_label, parent)

            self.position_labels.tag_bind(group_tag, '<<Inside>>', lambda _, local_label_group = label_group:
                                          self.position_labels.after_idle(self.show_position_marker, local_label_group))
            self.position_labels.tag_bind(group_tag, '<Leave>', lambda _: self.position_labels.after_idle(self.hide_marker))
 
            return label_group

        GroupData = namedtuple('GroupData', ['group', 'interval', 'leaf'])

        offset = 0
        groups_list = []
        depth = 0

        for interval, group in position_groups.items():
            for position in range(*interval):
                try:
                    for time, value in data[position].items():
                        location = Interval(offset + position - interval.lower, 1, length_given = True)
                        if self.mirror: box = time[0], - location[0], time[1], - location[1]
                        else:           box = time[0], + location[0], time[1], + location[1]

                        point = self.content.create_rectangle(box, width = 0, fill = self.coloring[value], tag = 'value{:x}'.format(value))
                        self.content.tag_bind(point, '<<Inside>>',  lambda event, correction = (0, offset - interval.lower): show_location(event, correction))
                        self.content.tag_bind(point, '<Leave>',     lambda _: self.location_label.configure(text = ''))
                except KeyError: pass

            groups_list.append(GroupData(group, Interval(offset, interval.length, True), True))
            depth = max(group.depth, depth)

            offset += interval.length + 10

        depth_stack = []

        while depth >= 0:
            rest_list = []
            current_list = []

            parent_group = None
            parent_lower = None
            parent_upper = None

            for group_data in groups_list:
                group, interval = group_data[:2]
                if group.depth == depth:
                    current_list.append(group_data)
                    if group.parent is not None:
                        if parent_group is group.parent:
                            parent_upper = interval.upper
                        else:
                            if parent_group is not None:
                                rest_list.append(GroupData(parent_group, Interval(parent_lower, parent_upper), False))
                            parent_group = group.parent
                            parent_lower, parent_upper = interval
                    else: assert parent_group is None
                else:
                    if parent_group is not None:
                        rest_list.append(GroupData(parent_group, Interval(parent_lower, parent_upper), False))
                        parent_group = None
                    rest_list.append(group_data)
            if parent_group is not None:
                rest_list.append(GroupData(parent_group, Interval(parent_lower, parent_upper), False))

            depth_stack.append(current_list)
            groups_list = rest_list
            depth -= 1

        assert not groups_list

        LabelGroupData = namedtuple('LabelGroupData', ['group', 'interval'])
        groups = [] 

        while depth_stack:
            current_list = depth_stack.pop()
            last_parent = None
            last_label_group = None

            for group, interval, leaf in current_list:
                if group.parent is not None: parent_label_group = group.parent.label_group
                else:                        parent_label_group = None

                label_group = create_group_labels(group, interval, parent_label_group)

                if last_parent is not group.parent:
                    if last_label_group is not None:
                        last_label_group.footer_moveable = True
                    label_group.header_moveable = True
                    last_parent = group.parent
                else:
                    if last_label_group is not None:
                        last_label_group.footer_moveable = False
                    label_group.header_moveable = False

                label_group.inner_lines = []
                label_group.outer_lines = []

                groups.append(LabelGroupData(label_group, interval))

                if leaf: self.position_labels.labels[interval] = label_group
                else: group.label_group = label_group
                last_label_group = label_group

            if last_parent is not None:
                assert last_label_group is not None
                last_label_group.footer_moveable = True

        for time, text in sorted(time_labels):
            label = create_time_label(text, time)
            self.time_labels.labels[time] = label

        drawing_regions = self.drawing_regions()
        lower_x, upper_x, lower_y, upper_y, _, _, positions_lower_x, positions_upper_x = drawing_regions

        position_labels_width = positions_upper_x - positions_lower_x
        horizontal_lines = {}

        for group, interval in groups:
            for position in interval:
                if self.mirror: position = - position
                line = self.position_labels.create_line(20 * group.depth, position, position_labels_width, position, tag = 'line', fill = 'lightgrey')
                group.inner_lines.append(line)

                if position in horizontal_lines:
                    group.outer_lines.append(horizontal_lines[position])
                else:
                    line = self.content.create_line(lower_x, position, upper_x, position, tag = 'line', fill = 'lightgrey')
                    group.outer_lines.append(line)
                    horizontal_lines[position] = line

        for time, label in self.time_labels.labels.items():
            self.time_labels.outer_lines[label] = self.content.create_line(time, lower_y, time, upper_y, tag = 'line', fill = 'lightgrey')

        self.content.tag_lower('line')

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

            graphic.setAttribute('width',   '{:0.3f}'.format(width))
            graphic.setAttribute('height',  '{:0.3f}'.format(height))
            graphic.setAttribute('viewBox', '{:0.3f} {:0.3f} {:0.3f} {:0.3f}'.format(x, y, X, Y))
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

        def create_label(label, vertical_offset):
            element = document.createElement('text')
            element.appendChild(document.createTextNode(self.location_label['text']))

            # get font parameters
            font = Font(name = self.style.lookup('TLabel', 'font'), exists = True, font = self.location_label['font'])
            font_parameters = font.actual()

            # set font type
            element.setAttribute('font-family', font_parameters['family'])
            if font_parameters['slant'] != 'roman':
                element.setAttribute('font-style', font_parameters['slant'])
            if font_parameters['weight'] != 'normal':
                element.setAttribute('font-weight', font_parameters['weight'])

            # set font size
            size = float(font_parameters['size'])
            if size > 0: size_text = '{:f} pt'.format(+ size) # size in points
            else:        size_text = '{:f}'   .format(- size) # size in pixels
            element.setAttribute('font-size', size_text)

            # set font decorations
            decorations = []
            if font_parameters['underline' ]: decoration.append('underline')
            if font_parameters['overstrike']: decoration.append('line-through')
            if decorations: element.setAttribute('text-decoration', ' '.join(decorations))

            # set label vertical coordinate
            element.setAttribute('y', '{:d}'.format(vertical_offset + font.metrics('ascent'))) 

            document.documentElement.appendChild(element)
            return font.metrics('linespace')

        content_width, content_height = create_graphic(self.content)[1:]

        time_labels_graphic, time_labels_height = create_graphic(self.time_labels)[::2]
        time_labels_graphic.setAttribute('y', '{:0.3f}'.format(- time_labels_height))

        position_labels_graphic, position_labels_width = create_graphic(self.position_labels)[:2]
        position_labels_graphic.setAttribute('x', '{:0.3f}'.format(- position_labels_width))

        information_height = create_label(self.location_label, content_height)

        legend_graphic, legend_height = create_graphic(self.legend)[::2]
        legend_graphic.setAttribute('y', '{:0.3f}'.format(content_height + information_height + 5))

        set_view_box(document.documentElement,
                     position_labels_width + content_width,
                     time_labels_height + content_height + information_height + legend_height + 5,
                     - position_labels_width, - time_labels_height)

        savefile = asksaveasfile(defaultextension = '.svg',
                                 initialfile = 'screenshot.svg',
                                 title = 'Select file to store the screenshot in.',
                                 parent = self.mainframe)

        if savefile:
            with savefile as screenshot:
                screenshot.write(document.toxml())
