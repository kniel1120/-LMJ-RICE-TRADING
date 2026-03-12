from datetime import date

class AccountReceivable:
    def __init__(self, id, customer_name, address, contact, amount, partial_amount, due_date, status):
        self.id = id
        self.customer_name = customer_name
        self.address = address
        self.contact = contact
        self.amount = amount
        self.partial_amount = partial_amount
        self.due_date = due_date
        self.status = status  # 'Pending', 'Partial', or 'Paid'

    def mark_as_paid(self):
        self.status = 'Paid'

    def add_partial(self, partial):
        self.partial_amount += partial
        if self.partial_amount >= self.amount:
            self.status = 'Paid'
        elif self.partial_amount > 0:
            self.status = 'Partial'

    def balance(self):
        return self.amount - self.partial_amount

    def is_due(self):
        return date.today() >= self.due_date
