
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from database.db import execute_db
from flask import Flask

app = Flask(__name__)


def clear_all_data():
    with app.app_context():
        execute_db('DELETE FROM sales')
        execute_db('DELETE FROM inventory')
        execute_db('DELETE FROM expenses')
        print('All data cleared.')

if __name__ == '__main__':
    clear_all_data()
