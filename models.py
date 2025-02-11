from peewee import Model, CharField, TextField, SqliteDatabase, DateField, FloatField, ForeignKeyField, AutoField, IntegerField

# Enable foreign key support in SQLite
db = SqliteDatabase("invoices.db", pragmas={'foreign_keys': 1})

class BaseModel(Model):
    class Meta:
        database = db

class Customer(BaseModel):
    full_name = CharField(200)
    address = TextField()

class Invoice(BaseModel):
    invoice_id = AutoField()
    customer = ForeignKeyField(Customer, backref="invoices", on_delete="CASCADE")
    date = DateField()
    total_amount = FloatField()
    tax_percent = FloatField()
    payable_amount = FloatField()
    gov_arn = CharField(null = True)

class InvoiceItem(BaseModel):
    item_name = CharField(200)
    qty = IntegerField()
    rate = FloatField()
    amount = FloatField()
    invoice = ForeignKeyField(Invoice, backref="items", lazy_load=False, on_delete="CASCADE")