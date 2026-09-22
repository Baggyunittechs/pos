import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, make_response, redirect, url_for, flash, session, send_file, render_template_string
import os
import json
import uuid
import requests
import hmac
from functools import wraps
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
import base64

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import time
import secrets
import hashlib
import smtplib
from email.message import EmailMessage

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import io

app = Flask(__name__)
last_scanned_barcode = None
app.secret_key = "secret123"
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app)
DATABASE = "users.db"

GIFTED_API_KEY = os.environ.get("GIFTED_API_KEY", "gifted_mpesa_stk_667c1fVj_i6HFZDYFu51nL4ySMxQmd11")
GIFTED_BASE_URL = "https://mpesa.gifted.co.ke/api"

LOGO_PATH = os.path.join('static', 'images/logo.png')
LOGO_CID = 'receipt_logo'
CART_FILE = os.path.join(app.root_path, 'data', 'cart.json')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

detector = cv2.barcode.BarcodeDetector()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def load_products():
    json_path = os.path.join(app.root_path, "products2.json")
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file).get("products", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_sales():
    sales_path = os.path.join(app.root_path, "sales.json")
    try:
        with open(sales_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("sales", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_sales(sales):
    sales_path = os.path.join(app.root_path, "sales.json")
    with open(sales_path, "w", encoding="utf-8") as f:
        json.dump({"sales": sales}, f, indent=2)


def load_json_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_file(filepath, data):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving JSON file {filepath}: {e}")


def get_user_key():
    return request.cookies.get('user_key') or str(uuid.uuid4())


def generate_sales_id():
    return f"SALE_{uuid.uuid4().hex[:4].upper()}"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("429.html"), 429


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("All fields are required", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                (username, email, hashed_password, int(time.time())),
            )
            conn.commit()
            flash("Account successfully created", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists", "danger")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Invalid username or password", "danger")
            return redirect(url_for("login"))

        conn = get_db()
        user = conn.execute(
            "SELECT id, password FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            flash("Login successful", "success")
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


def send_reset_email(to_email, token):
    reset_link = f"http://127.0.0.1:5000/reset-password?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "Password Reset Request"
    msg["From"] = "unitbaggy3@gmail.com"
    msg["To"] = to_email

    msg.set_content(
        f"""You requested a password reset.
Click the link below to reset your password:
{reset_link}
This link expires in 15 minutes.
"""
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login("unitbaggy3@gmail.com", "pdzy fphw zjkg zxoh")
        server.send_message(msg)


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "GET":
        return render_template("forgot-password.html")

    email = request.form.get("email")

    if not email:
        return jsonify({"message": "Invalid request"}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if user:
        token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        expiry = int(time.time()) + 900

        conn.execute(
            "UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
            (hashed_token, expiry, user["id"]),
        )
        conn.commit()
        send_reset_email(email, token)

    conn.close()
    return redirect(url_for("resetmessage"))


@app.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password():
    if request.method == "GET":
        token = request.args.get("token")
        if not token:
            return jsonify({"message": "Invalid request"}), 400
        return render_template("reset-password.html", token=token)

    token = request.form.get("token")
    new_password = request.form.get("new_password")

    if not token or not new_password:
        return jsonify({"message": "Invalid request"}), 400

    hashed_token = hashlib.sha256(token.encode()).hexdigest()

    conn = get_db()
    user = conn.execute(
        "SELECT id FROM users WHERE reset_token = ? AND reset_token_expiry > ?",
        (hashed_token, int(time.time())),
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({"message": "Invalid or expired token"}), 400

    new_hashed_password = generate_password_hash(new_password)

    conn.execute(
        "UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
        (new_hashed_password, user["id"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Password successfully reset"})


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return None

    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            return jsonify({"status": "error", "message": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


@app.route('/api/receipt/generate', methods=['POST'])
@csrf.exempt
@login_required
def generate_receipt():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        sales_id = data.get('sales_id')
        if not sales_id:
            return jsonify({'success': False, 'message': 'Sales ID required'}), 400

        sales = load_sales()
        sale = next((s for s in sales if s.get('sales_id') == sales_id), None)

        if not sale:
            return jsonify({'success': False, 'message': f'Sale {sales_id} not found'}), 404

        items = sale.get('items', [])

        if not items:
            cart = sale.get('cart', [])
            products = load_products()
            for cart_item in cart:
                product_id = cart_item.get('product_id')
                quantity = cart_item.get('quantity', 1)
                for product in products:
                    if str(product.get('barcode')) == str(product_id):
                        items.append({
                            'name': product.get('name', 'Unknown'),
                            'quantity': quantity,
                            'price': product.get('price', 0)
                        })
                        break

        receipt_data = {
            'ticket_number': sale.get('sales_id', 'N/A'),
            'date': sale.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'served_by': sale.get('served_by', 'Eddy'),
            'business_name': 'EDMA ELECTRICALS',
            'phone': '0705470644',
            'location': 'Nairobi',
            'items': items,
            'subtotal': float(sale.get('total', 0)),
            'tax': 0,
            'total': float(sale.get('total', 0)),
            'payment_method': sale.get('payment_method', 'Cash'),
            'amount_paid': float(sale.get('amount_paid', sale.get('total', 0))),
            'change': float(sale.get('change', 0)),
            'customer_name': sale.get('customer_name', ''),
            'customer_email': sale.get('customer_email', ''),
            'customer_phone': sale.get('customer_phone', ''),
            'company': 'Pinchezmedia',
            'email': 'juliuskyuma24@gmail.com',
            'thank_you': 'Thank You For Shopping With Us',
            'policy': 'GOODS ARE NOT RETURNABLE AFTER SALE',
            'powered_by': 'System by Pinchezmedia254'
        }

        os.makedirs('receipts', exist_ok=True)
        receipt_file = f'receipts/{sales_id}.json'
        with open(receipt_file, 'w', encoding='utf-8') as f:
            json.dump(receipt_data, f, indent=2)

        return jsonify({
            'success': True,
            'message': 'Receipt generated successfully',
            'receipt_data': receipt_data
        })

    except Exception as e:
        print(f"Error generating receipt: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


def build_receipt_pdf(data):
    def money(v):
        return f"{float(v):,.2f}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0.6*inch, bottomMargin=0.6*inch,
        leftMargin=2*inch, rightMargin=2*inch
    )
    story = []

    brand_style = ParagraphStyle(
        'Brand', fontName='Courier-Bold', fontSize=13,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#001846')
    )
    center_style = ParagraphStyle(
        'Center', fontName='Courier', fontSize=8.5,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.black
    )
    label_style = ParagraphStyle(
        'Label', fontName='Courier-Bold', fontSize=9,
        alignment=TA_CENTER, spaceBefore=2, spaceAfter=2, textColor=colors.black
    )
    line_style = ParagraphStyle(
        'Line', fontName='Courier', fontSize=8.5,
        alignment=TA_LEFT, spaceAfter=1, textColor=colors.black
    )
    right_style = ParagraphStyle(
        'Right', fontName='Courier', fontSize=8.5,
        alignment=TA_RIGHT, spaceAfter=1, textColor=colors.black
    )
    total_style = ParagraphStyle(
        'Total', fontName='Courier-Bold', fontSize=11,
        alignment=TA_RIGHT, spaceBefore=3, spaceAfter=1, textColor=colors.HexColor('#001846')
    )
    thanks_style = ParagraphStyle(
        'Thanks', fontName='Courier-Bold', fontSize=10,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=4, textColor=colors.HexColor('#001846')
    )
    small_style = ParagraphStyle(
        'Small', fontName='Courier', fontSize=7.5,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#555555')
    )
    faint_style = ParagraphStyle(
        'Faint', fontName='Courier', fontSize=7,
        alignment=TA_CENTER, spaceBefore=6, textColor=colors.HexColor('#999999')
    )

    def dash():
        story.append(HRFlowable(width="100%", thickness=0.75, dash=(2, 2), color=colors.HexColor('#999999'), spaceBefore=4, spaceAfter=4))

    def solid():
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=2, spaceAfter=4))

    logo_shown = False
    if os.path.exists(LOGO_PATH):
        try:
            logo = RLImage(LOGO_PATH)
            target_w = 1.5 * inch
            aspect = logo.imageHeight / float(logo.imageWidth)
            logo.drawWidth = target_w
            logo.drawHeight = target_w * aspect
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 4))
            logo_shown = True
        except Exception:
            logo_shown = False
    if not logo_shown:
        story.append(Paragraph(data['business_name'], brand_style))
    story.append(Paragraph(f"Tel: {data['phone']}", center_style))
    story.append(Paragraph(data['location'], center_style))
    dash()
    story.append(Paragraph("SALES RECEIPT", label_style))
    dash()

    story.append(Paragraph(f"Receipt No : {data['ticket_number']}", line_style))
    story.append(Paragraph(f"Date       : {data['date']}", line_style))
    story.append(Paragraph(f"Served By  : {data['served_by']}", line_style))
    if data.get('customer_name'):
        story.append(Paragraph(f"Customer   : {data['customer_name']}", line_style))
    dash()

    table_data = [['ITEM', 'QTY', 'AMOUNT']]
    for item in data['items']:
        name = item.get('name', 'Unknown')
        qty = item.get('quantity', 1)
        price = float(item.get('price', 0))
        total = price * qty
        table_data.append([name[:32], str(qty), money(total)])

    table = Table(table_data, colWidths=[2.5*inch, 0.5*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Courier-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Courier'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.75, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(table)
    dash()

    story.append(Paragraph(f"Subtotal:  {money(data['subtotal'])} KSh", right_style))
    story.append(Paragraph(f"Tax:       {money(data.get('tax', 0))} KSh", right_style))
    story.append(Paragraph(f"TOTAL:     {money(data['total'])} KSh", total_style))
    solid()
    story.append(Paragraph(f"{data['payment_method'].upper()} PAID: {money(data['amount_paid'])} KSh", right_style))
    if float(data.get('change', 0)) > 0:
        story.append(Paragraph(f"CHANGE DUE: {money(data['change'])} KSh", right_style))
    dash()

    if data.get('company'):
        story.append(Paragraph(data['company'], center_style))
    if data.get('email'):
        story.append(Paragraph(data['email'], center_style))
    story.append(Paragraph(data['thank_you'], thanks_style))
    story.append(Paragraph(data['policy'], small_style))
    story.append(Paragraph(data['powered_by'], faint_style))
    story.append(Paragraph("*** END OF RECEIPT ***", faint_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route('/api/receipt/download/<sales_id>', methods=['GET'])
@csrf.exempt
@login_required
def download_receipt_pdf(sales_id):
    try:
        receipt_file = f'receipts/{sales_id}.json'

        if not os.path.exists(receipt_file):
            return jsonify({'success': False, 'message': 'Receipt not found. Please generate receipt first.'}), 404

        with open(receipt_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        buffer = build_receipt_pdf(data)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'receipt_{sales_id}.pdf',
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"Error downloading receipt: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/receipt/email', methods=['POST'])
@csrf.exempt
@login_required
def send_receipt_email():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        sales_id = data.get('sales_id')
        email = data.get('email')

        if not sales_id:
            return jsonify({'success': False, 'message': 'Sales ID required'}), 400

        if not email:
            return jsonify({'success': False, 'message': 'Email address required'}), 400

        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'message': 'Invalid email address'}), 400

        receipt_file = f'receipts/{sales_id}.json'
        if not os.path.exists(receipt_file):
            return jsonify({'success': False, 'message': 'Receipt not found. Please generate receipt first.'}), 404

        with open(receipt_file, 'r', encoding='utf-8') as f:
            receipt_data = json.load(f)

        html_content = generate_receipt_html(receipt_data)
        pdf_buffer = build_receipt_pdf(receipt_data)

        msg = EmailMessage()
        msg["Subject"] = f"Receipt {sales_id} - EDMA ELECTRICALS"
        msg["From"] = "unitbaggy3@gmail.com"
        msg["To"] = email
        msg.set_content("Your receipt is attached. Please view this email in an HTML-compatible client to see it inline.")
        msg.add_alternative(html_content, subtype="html")

        if os.path.exists(LOGO_PATH):
            html_part = msg.get_body(preferencelist=('html',))
            with open(LOGO_PATH, 'rb') as f:
                html_part.add_related(f.read(), maintype='image', subtype='png', cid=f'<{LOGO_CID}>')

        msg.add_attachment(
            pdf_buffer.read(),
            maintype="application",
            subtype="pdf",
            filename=f"receipt_{sales_id}.pdf"
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("unitbaggy3@gmail.com", "pdzy fphw zjkg zxoh")
            server.send_message(msg)

        return jsonify({
            'success': True,
            'message': f'Receipt sent to {email}'
        })

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


def generate_receipt_html(data):
    def money(v):
        return f"{float(v):,.2f}"

    items_html = ''
    for item in data['items']:
        name = item.get('name', 'Unknown')
        qty = item.get('quantity', 1)
        price = float(item.get('price', 0))
        total = price * qty
        items_html += f"""
            <tr>
                <td>{name}</td>
                <td style="text-align:center;">{qty}</td>
                <td style="text-align:right;">{money(total)}</td>
            </tr>
        """

    customer_info = ''
    if data.get('customer_name'):
        customer_info += f"<div>Customer : {data['customer_name']}</div>"
    if data.get('customer_phone'):
        customer_info += f"<div>Phone    : {data['customer_phone']}</div>"
    if data.get('customer_email'):
        customer_info += f"<div>Email    : {data['customer_email']}</div>"

    change_row = ''
    if float(data.get('change', 0)) > 0:
        change_row = f'<div class="change-row">CHANGE DUE: {money(data["change"])} KSh</div>'

    logo_html = ''
    if os.path.exists(LOGO_PATH):
        logo_html = f'<img src="cid:{LOGO_CID}" alt="{data["business_name"]}" style="width:120px; height:auto; display:block; margin:0 auto 4px;">'
    business_header = logo_html if logo_html else f'<div class="business">{data["business_name"]}</div>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Receipt {data['ticket_number']}</title>
        <style>
            body {{ font-family: 'Courier New', Courier, monospace; margin: 0; padding: 20px; background: #eceff1; }}
            .receipt {{ max-width: 340px; margin: 0 auto; background: white; padding: 24px 22px; border: 1px solid #ddd; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
            .header {{ text-align: center; margin-bottom: 6px; }}
            .business {{ font-size: 19px; font-weight: bold; color: #001846; letter-spacing: 0.5px; }}
            .info {{ text-align: center; font-size: 12px; color: #333; margin: 1px 0; }}
            .dashed {{ border-top: 1px dashed #999; margin: 10px 0; }}
            .solid {{ border-top: 1.5px solid #000; margin: 6px 0; }}
            .label {{ text-align: center; font-weight: bold; font-size: 12px; letter-spacing: 1px; margin: 4px 0; }}
            .ticket-info div {{ font-size: 12px; margin: 1px 0; }}
            .customer-info {{ font-size: 12px; margin: 6px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }}
            th {{ border-bottom: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 11px; }}
            td {{ padding: 3px 2px; font-size: 12px; }}
            .totals {{ text-align: right; font-size: 12px; margin-top: 4px; }}
            .totals div {{ padding: 1px 0; }}
            .total-row {{ font-size: 15px; font-weight: bold; color: #001846; }}
            .paid-row {{ font-size: 12px; margin-top: 4px; }}
            .change-row {{ font-size: 12px; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 10px; }}
            .thank-you {{ font-size: 13px; font-weight: bold; color: #001846; margin: 6px 0; }}
            .policy {{ font-size: 10.5px; color: #555; margin-top: 4px; }}
            .powered {{ font-size: 9px; color: #999; margin-top: 8px; }}
            .end-marker {{ font-size: 9px; color: #999; margin-top: 4px; letter-spacing: 1px; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                {business_header}
                <div class="info">Tel: {data['phone']}</div>
                <div class="info">{data['location']}</div>
            </div>

            <div class="dashed"></div>
            <div class="label">SALES RECEIPT</div>
            <div class="dashed"></div>

            <div class="ticket-info">
                <div>Receipt No : {data['ticket_number']}</div>
                <div>Date       : {data['date']}</div>
                <div>Served By  : {data['served_by']}</div>
            </div>

            {f'<div class="customer-info">{customer_info}</div>' if customer_info else ''}

            <div class="dashed"></div>

            <table>
                <thead>
                    <tr>
                        <th>ITEM</th>
                        <th style="text-align:center;">QTY</th>
                        <th style="text-align:right;">AMOUNT</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            <div class="dashed"></div>

            <div class="totals">
                <div>Subtotal: {money(data['subtotal'])} KSh</div>
                <div>Tax:      {money(data.get('tax', 0))} KSh</div>
                <div class="total-row">TOTAL: {money(data['total'])} KSh</div>
                <div class="solid"></div>
                <div class="paid-row">{data['payment_method'].upper()} PAID: {money(data['amount_paid'])} KSh</div>
                {change_row}
            </div>

            <div class="dashed"></div>

            <div class="footer">
                {f"<div class='info'>{data['company']}</div>" if data.get('company') else ''}
                {f"<div class='info'>{data['email']}</div>" if data.get('email') else ''}
                <div class="thank-you">{data['thank_you']}</div>
                <div class="policy">{data['policy']}</div>
                <div class="powered">{data['powered_by']}</div>
                <div class="end-marker">*** END OF RECEIPT ***</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@app.route("/")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/resetmessage")
def resetmessage():
    return render_template("resetmessage.html")


@app.route("/cart")
def cart_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("cart.html")


@app.route("/shop")
def shop_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("shop.html")


@app.route("/sales")
def sales_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("sales.html")


@app.route("/checkout")
def checkout_page():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("checkout.html")


@app.route("/api/barcode/scan", methods=["POST"])
@csrf.exempt
@login_required
def scan():
    global last_scanned_barcode

    if 'image' not in request.files:
        return jsonify({
            "status": "error",
            "message": "No image uploaded"
        }), 400

    file = request.files['image']
    image_bytes = file.read()

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({
            "status": "error",
            "message": "Invalid image data"
        }), 400

    barcode_data, barcode_type, bbox = detector.detectAndDecode(frame)

    if not barcode_data:
        return jsonify({
            "status": "error",
            "message": "No barcode detected in image"
        }), 404

    if barcode_data == last_scanned_barcode:
        return jsonify({
            "status": "duplicate",
            "message": "Product already scanned",
            "barcode": barcode_data
        }), 404

    products = load_products()
    found_product = None

    for product in products:
        if str(product.get("barcode")) == str(barcode_data):
            found_product = product
            break

    if found_product:
        last_scanned_barcode = barcode_data
        try:
            user_key = get_user_key()
            carts = load_json_file(CART_FILE)
            cart = carts.get(user_key, [])
            found = False
            for item in cart:
                if str(item['product_id']) == str(barcode_data):
                    item['quantity'] += 1
                    found = True
                    break

            if not found:
                cart.append({
                    'product_id': barcode_data,
                    'quantity': 1
                })

            carts[user_key] = cart
            save_json_file(CART_FILE, carts)

        except Exception as e:
            print(f"Error adding to cart: {e}")

        return jsonify({
            "status": "success",
            "message": "Product found and added to cart",
            "product": found_product
        }), 200
    else:
        return jsonify({
            "status": "not_found",
            "message": "Product not in database",
            "barcode": barcode_data
        }), 200


@app.route('/api/products', methods=['GET'])
@login_required
def get_products():
    products = load_products()
    instock_products = [p for p in products if p.get("instock", 0) > 0]

    search = request.args.get('search')
    if search:
        search = search.lower().strip()

        def matches_search(p):
            name = p.get('name', '').lower()
            tags = ' '.join(p.get('tags', [])).lower()
            cat = p.get('category', '').lower()
            return search in name or search in tags or search in cat

        filtered_products = [p for p in products if matches_search(p)]
        return jsonify(filtered_products)

    return jsonify(instock_products)


@app.route('/api/cart', methods=['GET'])
@login_required
def get_cart():
    user_key = get_user_key()
    carts = load_json_file(CART_FILE)
    cart = carts.get(user_key, [])
    products = load_products()

    enriched = []
    total = 0

    for item in cart:
        product = next((p for p in products if str(p.get('barcode')) == str(item['product_id'])), None)
        if product:
            line_total = product['price'] * item['quantity']
            total += line_total
            enriched.append({
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'product': product,
                'line_total': line_total
            })

    response = jsonify({
        'items': enriched,
        'total': total,
        'count': len(cart)
    })
    response.set_cookie('user_key', user_key, max_age=60*60*24*365)
    return response


@app.route('/api/cart/add', methods=['POST'])
@csrf.exempt
@login_required
def add_to_cart():
    data = request.json or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400

    user_key = get_user_key()
    carts = load_json_file(CART_FILE)
    cart = carts.get(user_key, [])

    found = False
    for item in cart:
        if str(item['product_id']) == str(product_id):
            item['quantity'] += quantity
            found = True
            break

    if not found:
        cart.append({
            'product_id': product_id,
            'quantity': quantity
        })

    carts[user_key] = cart
    save_json_file(CART_FILE, carts)

    response = make_response(jsonify({
        'success': True,
        'cart_count': len(cart),
        'message': 'Product added to cart'
    }))
    response.set_cookie('user_key', user_key, max_age=60*60*24*365)
    return response


@app.route('/api/cart/update', methods=['POST'])
@csrf.exempt
@login_required
def update_cart():
    data = request.json or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400

    user_key = get_user_key()
    carts = load_json_file(CART_FILE)
    cart = carts.get(user_key, [])

    for item in cart:
        if str(item['product_id']) == str(product_id):
            if quantity <= 0:
                cart.remove(item)
            else:
                item['quantity'] = quantity
            break

    carts[user_key] = cart
    save_json_file(CART_FILE, carts)

    response = make_response(jsonify({
        'success': True,
        'message': 'Cart updated'
    }))
    response.set_cookie('user_key', user_key, max_age=60*60*24*365)
    return response


@app.route('/api/cart/remove', methods=['POST'])
@csrf.exempt
@login_required
def remove_from_cart():
    data = request.json or {}
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400

    user_key = get_user_key()
    carts = load_json_file(CART_FILE)
    cart = carts.get(user_key, [])

    cart = [item for item in cart if str(item['product_id']) != str(product_id)]

    carts[user_key] = cart
    save_json_file(CART_FILE, carts)

    response = make_response(jsonify({
        'success': True,
        'message': 'Item removed from cart'
    }))
    response.set_cookie('user_key', user_key, max_age=60*60*24*365)
    return response


@app.route("/api/save/sales", methods=["POST"])
@csrf.exempt
@login_required
def sales():
    data = request.get_json() or {}
    items = data.get("items", [])

    products = load_products()
    sales_items = []
    total = 0
    overall_profit = 0

    for item in items:
        barcode = item.get("barcode")
        try:
            quantity = int(item.get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1

        found_product = next((p for p in products if str(p.get("barcode")) == str(barcode)), None)

        if found_product:
            price = float(found_product.get("price", 0))
            buying_price = float(found_product.get("buying_price") if found_product.get("buying_price") is not None else price)

            item_total = price * quantity
            total += item_total

            profit = price - buying_price
            overall_profit += (profit * quantity)

            sales_items.append({
                "barcode": barcode,
                "name": found_product.get("name"),
                "price": price,
                "quantity": quantity,
                "item_total": item_total
            })

    sales_id = generate_sales_id()
    status = "pending"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_sale = {
        "sales_id": sales_id,
        "profit": overall_profit,
        "status": status,
        "created_at": created_at,
        "total": total,
        "items": sales_items
    }

    sales_list = load_sales()
    sales_list.append(new_sale)
    save_sales(sales_list)

    return jsonify({
        "status": "success",
        "message": "Sale created successfully",
        "sales_id": sales_id,
        "total": total,
        "created_at": created_at
    })


@app.route("/api/checkout", methods=["GET"])
@login_required
def checkout():
    sales_id = request.args.get("sales_id")
    if not sales_id:
        return jsonify({
            "status": "error",
            "message": "sales id not provided"
        }), 400

    sales = load_sales()
    for salle in sales:
        if salle.get("sales_id") == sales_id and salle.get("status") != "paid":
            return jsonify({
                "status": "success",
                "sale": salle
            }), 200

    return jsonify({
        "status": "error",
        "message": "sale not found or has already been closed"
    }), 400


def update_sale_status(sales_id, status, **extra_fields):
    sales = load_sales()
    for sale in sales:
        if sale.get("sales_id") == sales_id:
            sale["status"] = status
            sale.update(extra_fields)
            save_sales(sales)
            return True
    return False


def _normalize_phone(raw_phone):
    digits = "".join(ch for ch in str(raw_phone) if ch.isdigit())
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    return digits


def initiate_stk_prompt(phone, amount):
    url = f"{GIFTED_BASE_URL}/payments/process"
    headers = {
        "Authorization": f"Bearer {GIFTED_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "phone_number": _normalize_phone(phone),
        "amount": amount,
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Gifted STK error: {str(e)}")
        return {"success": False, "message": str(e)}


def verify_gifted_transaction(checkout_request_id):
    url = f"{GIFTED_BASE_URL}/payments/verify"
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(
            url, json={"checkoutRequestId": checkout_request_id}, headers=headers, timeout=30
        )
        return response.json()
    except Exception as e:
        print(f"Gifted verify error: {str(e)}")
        return {"success": False, "status": "error", "data": None}


def get_total(sales_id):
    sales = load_sales()
    for sale in sales:
        if sale.get("sales_id") == sales_id:
            return sale.get("total")
    return None


@app.route("/api/sales/payments/mpesa", methods=["POST"])
@csrf.exempt
@login_required
def payments():
    data = request.json or {}

    sales_id = data.get("sales_id")
    mpesa_phone = data.get("phone")
    if not mpesa_phone or not sales_id:
        return jsonify({"status": "error", "message": "data not provided"}), 400

    total = get_total(sales_id)
    if total is None:
        return jsonify({
            "status": "error",
            "message": "sales_id not found"
        }), 404

    try:
        response = initiate_stk_prompt(mpesa_phone, total)
        print(f"Gifted STK response: {response}")

        if not response.get("success"):
            return jsonify({
                "status": "error",
                "message": response.get("message", "Payment initiation failed"),
            }), 400

        checkout_request_id = response.get("checkout_request_id")
        if checkout_request_id:
            sales = load_sales()
            for sale in sales:
                if sale.get("sales_id") == sales_id:
                    sale["checkout_request_id"] = checkout_request_id
                    save_sales(sales)
                    break

        return jsonify({
            "status": "success",
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": response.get("merchant_request_id"),
        }), 200

    except Exception as e:
        print(f"Gifted STK error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/payment/mpesa/callback/status", methods=["POST"])
@csrf.exempt
@login_required
def callback_status():
    data = request.json or {}

    sales_id = data.get("sales_id")

    if not sales_id:
        return jsonify({"status": "error", "message": "sales_id required"}), 400

    sales = load_sales()
    sale = next((s for s in sales if s.get("sales_id") == sales_id), None)

    if not sale:
        return jsonify({"status": "error", "message": "sale not found"}), 404

    status = sale.get("status", "pending")
    is_hybrid = sale.get("payment_method") == "hybrid"

    if status == "pending" and sale.get("checkout_request_id"):
        try:
            verify_result = verify_gifted_transaction(sale["checkout_request_id"])
            gifted_status = verify_result.get("status")

            if gifted_status == "completed":
                tx_data = verify_result.get("data") or {}

                if is_hybrid:
                    sale["payments"]["mpesa"]["status"] = "received"
                    update_sale_status(
                        sales_id,
                        "paid",
                        mpesa_receipt=tx_data.get("mpesa_receipt_number"),
                        transaction_date=tx_data.get("transaction_date"),
                        payments=sale["payments"],
                        amount_paid=sale.get("total", 0)
                    )
                else:
                    update_sale_status(
                        sales_id,
                        "paid",
                        mpesa_receipt=tx_data.get("mpesa_receipt_number"),
                        transaction_date=tx_data.get("transaction_date"),
                        payment_method="M-pesa",
                        amount_paid=sale.get("total", 0)
                    )

                update_sell_count(sale)
                status = "paid"

            elif gifted_status not in ("pending", None):
                if is_hybrid:
                    sale["payments"]["mpesa"]["status"] = "failed"
                    update_sale_status(sales_id, "pending", payments=sale["payments"])
                    status = "pending"
                else:
                    update_sale_status(sales_id, "failed")
                    status = "failed"

        except Exception as e:
            print(f"Gifted verify error: {str(e)}")

    if status == "paid":
        return jsonify({
            "status": "success",
            "message": "Payment successful",
            "sales_id": sales_id,
            "receipt": sale.get("mpesa_receipt"),
            "amount": sale.get("amount_paid") or sale.get("total"),
            "transaction_date": sale.get("transaction_date")
        }), 200
    elif status == "failed":
        return jsonify({
            "status": "failed",
            "message": sale.get("payment_error", "Payment failed"),
            "sales_id": sales_id
        }), 200
    else:
        return jsonify({
            "status": "pending",
            "message": "Payment still processing",
            "sales_id": sales_id
        }), 200


@app.route("/api/payment/cash", methods=["POST"])
@csrf.exempt
@login_required
def cash_payment():
    data = request.json or {}
    sales_id = data.get("sales_id")

    if not sales_id:
        return jsonify({"status": "error", "message": "sales_id required"}), 400

    sales = load_sales()
    salle = next((s for s in sales if s.get("sales_id") == sales_id), None)

    if not salle:
        return jsonify({"status": "error", "message": "sales_id not found"}), 404

    if salle.get("status") == "paid":
        return jsonify({"status": "error", "message": "This sale has already been paid"}), 400

    transaction_date = salle.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    updated = update_sale_status(
        sales_id,
        "paid",
        transaction_date=transaction_date,
        payment_method="Cash",
        mpesa_receipt="No transactionID",
        amount_paid=salle.get("total", 0)
    )

    if not updated:
        return jsonify({
            "status": "error",
            "message": "sale could not be updated",
            "sales_id": sales_id
        }), 400

    update_sell_count(sale=salle)
    return jsonify({
        "status": "success",
        "message": "payment successful",
        "sales_id": sales_id,
    }), 200


@app.route("/api/sales/payments/hybrid", methods=["POST"])
@csrf.exempt
@login_required
def hybrid_payment():
    data = request.json or {}

    sales_id = data.get("sales_id")
    phone = data.get("phone")
    cash_amount = data.get("cash_amount", 0)
    mpesa_amount = data.get("mpesa_amount", 0)

    if not sales_id:
        return jsonify({"status": "error", "message": "sales_id required"}), 400

    if not phone:
        return jsonify({"status": "error", "message": "phone required"}), 400

    try:
        cash_amount = float(cash_amount)
        mpesa_amount = float(mpesa_amount)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid payment amounts"}), 400

    sales = load_sales()
    sale = next((s for s in sales if s.get("sales_id") == sales_id), None)

    if not sale:
        return jsonify({"status": "error", "message": "Sale not found"}), 404

    if sale.get("status") == "paid":
        return jsonify({"status": "error", "message": "This sale has already been paid"}), 400

    sale_total = float(sale.get("total", 0))
    total_payment = cash_amount + mpesa_amount

    if total_payment != sale_total:
        return jsonify({
            "status": "error",
            "message": "Payment amounts do not match sale total",
            "sale_total": sale_total,
            "cash_amount": cash_amount,
            "mpesa_amount": mpesa_amount,
            "total_payment": total_payment
        }), 400

    if cash_amount <= 0 or mpesa_amount <= 0:
        return jsonify({
            "status": "error",
            "message": "Hybrid payment must contain both cash and M-PESA"
        }), 400

    sale["payment_method"] = "hybrid"
    sale["payments"] = {
        "cash": {
            "amount": cash_amount,
            "status": "received"
        },
        "mpesa": {
            "amount": mpesa_amount,
            "status": "pending",
            "phone": phone
        }
    }
    sale["status"] = "pending"
    save_sales(sales)

    response = initiate_stk_prompt(phone, mpesa_amount)
    print(f"Gifted STK response (hybrid): {response}")

    if not response.get("success"):
        sale["payments"]["mpesa"]["status"] = "failed"
        save_sales(sales)
        return jsonify({
            "status": "error",
            "message": response.get("message", "M-PESA STK push failed to initiate"),
            "gifted_response": response
        }), 400

    checkout_request_id = response.get("checkout_request_id")
    sale["payments"]["mpesa"]["checkout_request_id"] = checkout_request_id
    sale["checkout_request_id"] = checkout_request_id
    save_sales(sales)

    return jsonify({
        "status": "pending",
        "message": "Cash received. Waiting for M-PESA payment.",
        "sales_id": sales_id,
        "sale_total": sale_total,
        "cash_amount": cash_amount,
        "mpesa_amount": mpesa_amount,
        "checkout_request_id": checkout_request_id
    }), 200


def update_sell_count(sale):
    products = load_products()
    for item in sale.get("items", []):
        barcode = item.get("barcode")
        try:
            quantity = int(item.get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1

        for product in products:
            if str(product.get("barcode")) == str(barcode):
                current_count = product.get("sell_count", 0)
                product["sell_count"] = current_count + quantity

                current_stock = product.get("instock", 0)
                product["instock"] = max(0, current_stock - quantity)
                break

    try:
        json_path = os.path.join(app.root_path, "products2.json")
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump({"products": products}, file, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Failed to update product sell counts/stock: {e}")
        return False


@app.route("/api/admin/sales/summary", methods=["GET"])
@csrf.exempt
@login_required
def get_daily_orders():
    today = date.today()
    yesterday = today - timedelta(days=1)
    sales = load_sales()

    revenue = 0
    sales_count = 0
    monthly_revenue = 0
    monthly_sales_count = 0
    monthly_profit = 0

    start_of_month = today.replace(day=1)

    if today.month == 12:
        start_of_next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        start_of_next_month = today.replace(month=today.month + 1, day=1)

    end_of_month = start_of_next_month - timedelta(days=1)
    end_of_last_month = start_of_month - timedelta(days=1)
    start_of_last_month = end_of_last_month.replace(day=1)

    yesterday_revenue = 0
    yesterday_sales = 0
    last_month_revenue = 0
    last_month_sales = 0
    last_month_profit = 0

    for sale in sales:
        if sale.get("status") != "paid":
            continue

        try:
            created_at = datetime.strptime(
                sale.get("created_at"),
                "%Y-%m-%d %H:%M:%S"
            )
        except (TypeError, ValueError):
            continue

        sale_date = created_at.date()
        total = sale.get("total", 0)
        profit = sale.get("profit", 0)

        if sale_date == today:
            revenue += total
            sales_count += 1

        if sale_date == yesterday:
            yesterday_revenue += total
            yesterday_sales += 1

        if start_of_month <= sale_date <= end_of_month:
            monthly_revenue += total
            monthly_sales_count += 1
            monthly_profit += profit

        if start_of_last_month <= sale_date <= end_of_last_month:
            last_month_revenue += total
            last_month_sales += 1
            last_month_profit += profit

    return jsonify({
        "status": "success",
        "today": {
            "revenue": revenue,
            "sales_total": sales_count
        },
        "yesterday": {
            "revenue": yesterday_revenue,
            "sales_total": yesterday_sales
        },
        "today_vs_yesterday": {
            "revenue_difference": revenue - yesterday_revenue,
            "sales_difference": sales_count - yesterday_sales
        },
        "this_month": {
            "revenue": monthly_revenue,
            "sales_total": monthly_sales_count,
            "monthly_profit": monthly_profit
        },
        "last_month": {
            "revenue": last_month_revenue,
            "sales_total": last_month_sales,
            "last_month_profit": last_month_profit
        },
        "this_month_vs_last_month": {
            "revenue_difference": monthly_revenue - last_month_revenue
        }
    }), 200


@app.route("/api/admin/sales/history")
@csrf.exempt
@login_required
def sales_history():
    sales = load_sales()

    month_param = request.args.get('month')
    year_param = request.args.get('year')

    today = date.today()

    if month_param and year_param:
        try:
            month = int(month_param)
            year = int(year_param)
            start_of_month = date(year, month, 1)
        except ValueError:
            start_of_month = today.replace(day=1)
    else:
        start_of_month = today.replace(day=1)

    if start_of_month.month == 12:
        start_of_next_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
    else:
        start_of_next_month = start_of_month.replace(month=start_of_month.month + 1, day=1)
    end_of_month = start_of_next_month - timedelta(days=1)

    paid_sales = []

    for sale in sales:
        if sale.get("status") != "paid":
            continue

        created_at = sale.get("created_at")
        if not created_at:
            continue

        try:
            sale_date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                sale_date = datetime.strptime(created_at, "%Y-%m-%d").date()
            except ValueError:
                continue

        if start_of_month <= sale_date <= end_of_month:
            paid_sales.append({
                "sales_id": sale.get("sales_id"),
                "sales_status": sale.get("status"),
                "total": sale.get("total"),
                "transaction_id": sale.get("mpesa_receipt"),
                "date": sale.get("created_at"),
                "profit": sale.get("profit")
            })

    return jsonify({
        "month": start_of_month.strftime("%B %Y"),
        "month_start": start_of_month.isoformat(),
        "month_end": end_of_month.isoformat(),
        "total_sales": len(paid_sales),
        "sales": paid_sales
    }), 200


@app.route("/api/admin/sales/history/all")
@csrf.exempt
@login_required
def sales_history_all():
    sales = load_sales()
    paid_sales = []

    for sale in sales:
        if sale.get("status") == "paid":
            paid_sales.append({
                "sales_id": sale.get("sales_id"),
                "sales_status": sale.get("status"),
                "total": sale.get("total"),
                "transaction_id": sale.get("mpesa_receipt"),
                "date": sale.get("created_at"),
                "profit": sale.get("profit")
            })

    return jsonify(paid_sales), 200


@app.route("/api/admin/sales/weekly", methods=["GET"])
@csrf.exempt
@login_required
def weekly_sales():
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=6)

    weekly_revenue = {
        "Sunday": 0, "Monday": 0, "Tuesday": 0, "Wednesday": 0,
        "Thursday": 0, "Friday": 0, "Saturday": 0
    }

    weekly_sales_count = {
        "Sunday": 0, "Monday": 0, "Tuesday": 0, "Wednesday": 0,
        "Thursday": 0, "Friday": 0, "Saturday": 0
    }

    sales = load_sales()

    for sale in sales:
        if sale.get("status") != "paid":
            continue

        try:
            created_at = datetime.strptime(
                sale.get("created_at"),
                "%Y-%m-%d %H:%M:%S"
            )
        except (TypeError, ValueError):
            continue

        sale_date = created_at.date()

        if sunday <= sale_date <= saturday:
            day_name = sale_date.strftime("%A")
            weekly_revenue[day_name] += sale.get("total", 0)
            weekly_sales_count[day_name] += 1

    return jsonify({
        "status": "success",
        "week": {
            "sunday": sunday.isoformat(),
            "saturday": saturday.isoformat()
        },
        "revenue": weekly_revenue,
        "sales": weekly_sales_count
    }), 200


@app.route("/api/admin/items/stock", methods=["GET"])
@csrf.exempt
@login_required
def load_outofstock_products():
    products = load_products()
    filtered_products = [p for p in products if p.get("instock", 0) == 0]

    return jsonify({
        "status": "success",
        "out_of_stock_items": filtered_products
    }), 200


@app.route("/api/admin/items/stock/edit", methods=["POST"])
@csrf.exempt
@login_required
def edit_stock():
    data = request.json or {}
    barcode = data.get("barcode")
    stock_quantity = data.get("stock_quantity")

    if barcode is None or stock_quantity is None:
        return jsonify({"status": "error", "message": "Missing barcode or stock_quantity"}), 400

    try:
        stock_quantity = int(stock_quantity)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "stock_quantity must be an integer"}), 400

    products = load_products()
    found = False
    for product in products:
        if str(product.get("barcode")) == str(barcode):
            product["instock"] = stock_quantity
            found = True
            break

    if not found:
        return jsonify({"status": "error", "message": "Product barcode not found"}), 404

    try:
        json_path = os.path.join(app.root_path, "products2.json")
        with open(json_path, "w", encoding="utf-8") as file:
            json.dump({"products": products}, file, indent=4, ensure_ascii=False)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Failed to update product stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/admin/items/upload', methods=['POST'])
@csrf.exempt
@login_required
def admin_add_product():
    name = request.form.get('name', '').strip()
    price = request.form.get('price')
    barcode = request.form.get('barcode', '').strip()
    tags_raw = request.form.get('tags', '').strip()
    buying_price = request.form.get('buying_price') or request.form.get('buying price')
    stock_amount = request.form.get('stock_amount', '1').strip()

    if not all([name, price, stock_amount, barcode]):
        return jsonify({"error": "Missing required fields: name, price, stock_amount, barcode"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"error": "Price must be a number"}), 400

    if buying_price:
        try:
            buying_price = float(buying_price)
        except ValueError:
            return jsonify({"error": "buying_price must be a number"}), 400
    else:
        buying_price = price

    try:
        stock_integer = int(stock_amount)
    except ValueError:
        return jsonify({"error": "Stock amount must be an integer"}), 400

    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    main_image_file = request.files.get('main_image')
    if not main_image_file or main_image_file.filename == '':
        return jsonify({"error": "main_image is required"}), 400

    if not allowed_file(main_image_file.filename):
        return jsonify({"error": "Invalid file type for main_image"}), 400

    main_filename = secure_filename(f"{barcode}_main_{main_image_file.filename}")
    main_path = os.path.join(app.root_path, 'static', 'images', main_filename)
    os.makedirs(os.path.dirname(main_path), exist_ok=True)
    main_image_file.save(main_path)

    image_files = request.files.getlist('images')
    image_paths = []
    for img_file in image_files:
        if img_file and img_file.filename and allowed_file(img_file.filename):
            img_filename = secure_filename(f"{barcode}_{img_file.filename}")
            img_path = os.path.join(app.root_path, 'static', 'images', img_filename)
            img_file.save(img_path)
            image_paths.append('/static/images/' + img_filename)

    main_image_url = '/static/images/' + main_filename
    new_product = {
        "barcode": barcode,
        "name": name,
        "price": price,
        "buying_price": buying_price,
        "tags": tags,
        "instock": stock_integer,
        "image": main_image_url,
    }

    products = load_products()
    if any(str(p.get('barcode')) == str(barcode) for p in products):
        return jsonify({"error": "Product with this barcode already exists"}), 409

    products.append(new_product)
    json_path = os.path.join(app.root_path, 'products2.json')
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({"products": products}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"error": f"Failed to save product data: {str(e)}"}), 500

    return jsonify({"success": True, "product": new_product}), 201


@app.route("/api/admin/stock/value", methods=["GET"])
@csrf.exempt
@login_required
def stock_value():
    products = load_products()
    stock_value_total = 0
    for product in products:
        price = float(product.get("price") or 0)
        instock = float(product.get("instock") or 0)
        stock_value_total += (price * instock)

    return jsonify({"status": "success", "stock_value": stock_value_total}), 200


if __name__ == "__main__":
    print("Starting Flask...")
    app.run(debug=True, host="0.0.0.0", port=5000)