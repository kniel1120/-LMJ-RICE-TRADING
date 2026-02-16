from database.init_db import initialize_database
from views.main_view import MainView

class AppController:
    def __init__(self, root):
        initialize_database()
        self.view = MainView(root)
