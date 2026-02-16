import tkinter as tk
from controllers.app_controller import AppController

def main():
    root = tk.Tk()
    root.title("LMJ Rice Retailing POS")
    app = AppController(root)
    root.mainloop()

if __name__ == "__main__":
    main()
