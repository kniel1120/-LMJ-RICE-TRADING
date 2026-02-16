import tkinter as tk

class MainView:
    def __init__(self, root):
        self.root = root
        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="LMJ Rice Retailing POS", font=("Arial", 18)).pack(pady=10)
        tk.Button(self.root, text="Suppliers", command=self.open_suppliers).pack(pady=5)
        tk.Button(self.root, text="Inventory", command=self.open_inventory).pack(pady=5)
        tk.Button(self.root, text="Customers", command=self.open_customers).pack(pady=5)
        tk.Button(self.root, text="Sales", command=self.open_sales).pack(pady=5)

    def open_suppliers(self):
        win = tk.Toplevel(self.root)
        win.title("Suppliers")
        tk.Label(win, text="Supplier Management", font=("Arial", 14)).pack(pady=10)
        # Placeholder: Add supplier management widgets here

    def open_inventory(self):
        win = tk.Toplevel(self.root)
        win.title("Inventory")
        tk.Label(win, text="Inventory Management", font=("Arial", 14)).pack(pady=10)
        # Placeholder: Add inventory management widgets here

    def open_customers(self):
        win = tk.Toplevel(self.root)
        win.title("Customers")
        tk.Label(win, text="Customer Management", font=("Arial", 14)).pack(pady=10)
        # Placeholder: Add customer management widgets here

    def open_sales(self):
        win = tk.Toplevel(self.root)
        win.title("Sales")
        tk.Label(win, text="Sales Processing", font=("Arial", 14)).pack(pady=10)
        # Placeholder: Add sales processing widgets here
