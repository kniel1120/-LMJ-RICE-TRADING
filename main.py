
# Use flaskwebgui to run Flask app in a desktop window
from flaskwebgui import FlaskUI
import app as lmj_app

if __name__ == "__main__":
    # FlaskUI(app, server, width, height)
    ui = FlaskUI(app=lmj_app.app, server="flask", width=1200, height=800)
    ui.run()
