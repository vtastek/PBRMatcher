from tkinter import Tk
from OpenGL import GL
from pyopengltk import OpenGLFrame
from modules.constants import SET_PROFILER
from modules.utility_functions import set_profiler
from modules.database_operations import load_database
from modules.gui_components import TextureTagger

if SET_PROFILER:
    set_profiler()

# Main
if __name__ == "__main__":
    db = load_database()
    root = Tk()
    app = TextureTagger(root, db)
    root.mainloop()
