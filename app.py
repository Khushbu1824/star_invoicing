import json

import requests

import io

from flask import Flask, render_template, request, redirect, url_for, make_response, Response

from peewee import SqliteDatabase

from models import Customer, Invoice, InvoiceItem

from weasyprint import HTML

app = Flask(__name__)

db = SqliteDatabase("invoices.db")
db.create_tables([Customer, Invoice, InvoiceItem])


@app.route("/")
def index():
    return "Home Page"


@app.route("/new-customer")
def create_customer_form():
    return render_template("create-customer.html")


@app.route("/customers", methods=["POST", "GET"])
def customers():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        address = request.form.get("address")

        customer = Customer(full_name=full_name, address=address)
        customer.save()
        return redirect("/customers")

    else:
        customers = Customer.select()
        return render_template("list-customer.html", customers=customers)


@app.route("/new-invoice")
def create_invoice_form():
    customers = Customer.select()
    return render_template("create-invoice.html", customers=customers)


@app.route("/invoices", methods=["GET", "POST"])
def invoices():
    if request.method == "POST":
        data = request.form
        total_amount = float(data.get("total_amount"))
        tax_percent = float(data.get("tax_percent"))

        items_json = data.get("invoice_items")
        items = json.loads(items_json)

        invoice = Invoice(
            customer=data.get("customer"),
            date=data.get("date"),
            total_amount=total_amount,
            tax_percent=tax_percent,
            payable_amount=total_amount + (total_amount * tax_percent) / 100,
        )
        invoice.save()

        for item in items:
            InvoiceItem(
                invoice=invoice,
                item_name=item.get("item_name"),
                qty=item.get("qty"),
                rate=item.get("price"),
                amount=int(item.get("qty")) * float(item.get("price"))
            ).save()

        # e-Invoicing API Integration
        payload = {
            "customer_name": data.get("customer"),
            "invoice_id": invoice.invoice_id,
            "payable_amount": invoice.payable_amount
        }

        try:
            response = requests.post("https://frappe.school/api/method/generate-pro-einvoice-id", json=payload)
            response_data = response.json()

            if "arn" in response_data:
                invoice.gov_arn = response_data["arn"]
                invoice.save()
        except requests.RequestException as e:
            print(f"Failed to fetch ARN: {e}")

        return redirect("/invoices")
    else:
        return render_template("list-invoice.html", invoices=Invoice.select())


@app.route("/download/<int:invoice_id>")
def download_pdf(invoice_id):
    invoice = Invoice.get_by_id(invoice_id)
    html = HTML(string=render_template("print/invoice.html", invoice=invoice))
    pdf = html.write_pdf()

    response = Response(pdf, content_type="application/pdf")
    response.headers["Content-Disposition"] = f"inline; filename=invoice_{invoice_id}.pdf"

    return response


@app.route("/delete-customer/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):
    try:
        customer = Customer.get_or_none(id=customer_id)
        if customer:
            customer.delete_instance(recursive=True)
            return redirect("/customers")
        else:
            return "Customer not found", 404
    except Exception as e:
        return str(e), 500


@app.route("/edit-customer/<int:customer_id>")
def edit_customer_form(customer_id):
    customer = Customer.get_or_none(id=customer_id)
    if not customer:
        return "Customer not found", 404
    return render_template("edit-customer.html", customer=customer)


@app.route("/update-customer/<int:customer_id>", methods=["POST"])
def update_customer(customer_id):
    try:
        customer = Customer.get_or_none(id=customer_id)
        if not customer:
            return "Customer not found", 404
        
        customer.full_name = request.form.get("full_name")
        customer.address = request.form.get("address")
        customer.save()

        return redirect(url_for("customers"))
    except Exception as e:
        return str(e), 500


@app.route("/delete-invoice/<int:invoice_id>", methods=["POST"])
def delete_invoice(invoice_id):
    try:
        invoice = Invoice.get_or_none(Invoice.invoice_id == invoice_id)
        if invoice:
            invoice.delete_instance(recursive=True)
            return redirect(url_for("invoices"))
        return "Invoice not found", 404
    except Exception as e:
        return str(e), 500


@app.route("/edit-invoice/<int:invoice_id>")
def edit_invoice_form(invoice_id):
    invoice = Invoice.get_or_none(Invoice.invoice_id == invoice_id)
    if not invoice:
        return "Invoice not found", 404
    return render_template("edit-invoice.html", invoice=invoice)


@app.route("/update-invoice/<int:invoice_id>", methods=["POST"])
def update_invoice(invoice_id):
    try:
        invoice = Invoice.get_or_none(Invoice.invoice_id == invoice_id)
        if not invoice:
            return "Invoice not found", 404

        invoice.date = request.form.get("date")
        invoice.tax_percent = float(request.form.get("tax_percent"))

        existing_items = {item.id: item for item in invoice.items}
        InvoiceItem.delete().where(InvoiceItem.invoice == invoice).execute()

        item_names = request.form.getlist("item_name[]")
        quantities = request.form.getlist("qty[]")
        rates = request.form.getlist("rate[]")
        amounts = request.form.getlist("amount[]")

        total_amount = 0

        for i in range(len(item_names)):
            qty = int(quantities[i])
            rate = float(rates[i])
            amount = qty * rate
            total_amount += amount

            InvoiceItem.create(
                invoice=invoice,
                item_name=item_names[i],
                qty=qty,
                rate=rate,
                amount=amount
            )

        invoice.total_amount = total_amount
        invoice.payable_amount = total_amount + (total_amount * invoice.tax_percent / 100)
        invoice.save()

        return redirect(url_for("invoices"))

    except Exception as e:
        return str(e), 500