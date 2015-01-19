from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL, N, S, W, E
import ttk as themed

class Visualisation(object):
    def __init__(self, parent):

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


root = Tk()
Visualisation(root, None, None, None, None).mainframe.grid(column = 0, row = 0, sticky = (N, S, W, E))
root.columnconfigure( 0, weight = 1 )
root.rowconfigure(    0, weight = 1 )
root.mainloop()
