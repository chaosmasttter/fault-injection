from Tkinter import Tk, Canvas, Scrollbar, HORIZONTAL, VERTICAL, N, S, W, E
import ttk as themed

root = Tk()

# use a themed frame to handle the background color
mainframe = themed.Frame(root, padding = 5)
mainframe.grid(column = 0, row = 0, sticky = (N, S, W, E))
root.columnconfigure( 0, weight = 1 )
root.rowconfigure(    0, weight = 1 )

content        = Canvas(mainframe)
timeLabels     = Canvas(mainframe)
positionLabels = Canvas(mainframe)
legend         = Canvas(mainframe)

# set the background color of the canvases to match that of the themed widgets
color = themed.Style().lookup("TFrame", "background")
for canvas in [content, timeLabels, positionLabels, legend]:
    canvas['background'] = color

scrollHorizontal = themed.Scrollbar(mainframe, orient = HORIZONTAL)
scrollVertical   = themed.Scrollbar(mainframe, orient = VERTICAL)

# set the right callbacks for the scrollbars
for canvas in [content, timeLabels]:
    canvas['xscrollcommand'] = scrollHorizontal.set

for canvas in [content, positionLabels]:
    canvas['yscrollcommand'] = scrollVertical.set

def scrollAllHorizontal(*arguments):
    for canvas in [content, timeLabels]:
        canvas.xview(*arguments)

def scrollAllVertical(*arguments):
    for canvas in [content, positionLabels]:
        canvas.xview(*arguments)

scrollHorizontal['command'] = scrollAllHorizontal
scrollVertical  ['command'] = scrollAllVertical

# place everything on the screen
timeLabels      .grid( column = 1, row = 0, sticky = (N,S,E,W) )
positionLabels  .grid( column = 0, row = 1, sticky = (N,S,E,W) )
content         .grid( column = 1, row = 1, sticky = (N,S,E,W) )
scrollHorizontal.grid( column = 1, row = 2, sticky = (N,S,E,W) )
scrollVertical  .grid( column = 2, row = 1, sticky = (N,S,E,W) )
legend          .grid( column = 1, row = 3, sticky = (N,S,E,W) )
mainframe.columnconfigure( 1, weight = 1 )
mainframe.rowconfigure(    1, weight = 1 )

root.mainloop()
