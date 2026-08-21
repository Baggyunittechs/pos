import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, make_response,redirect,url_for,flash,session,send_file, render_template_string
import os
import json
import uuid
import requests
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io

app = Flask(__name__)
last_scanned_barcode = None
app.secret_key = "secret123"
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app)
DATABASE = "users.db"

def load_sales():
    with open('sales.json', 'r') as f:
        return json.load(f)

def save_sales(sales):
    with open('sales.json', 'w') as f:
        json.dump(sales, f, indent=2)

@app.route('/api/receipt/generate', methods=['POST'])
@csrf.exempt 
def generate_receipt():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        sales_id = data.get('sales_id')
        if not sales_id:
            return jsonify({'success': False, 'message': 'Sales ID required'}), 400
        
        # Load sales
        sales = load_sales()
        sale = None
        for s in sales:
            if s.get('sales_id') == sales_id:
                sale = s
                break
        
        if not sale:
            return jsonify({'success': False, 'message': f'Sale {sales_id} not found'}), 404
        
        # Get items for this sale
        items = sale.get('items', [])
        
        # If items are empty, try to get from cart
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
        
        # Save receipt data
        os.makedirs('receipts', exist_ok=True)
        receipt_file = f'receipts/{sales_id}.json'
        with open(receipt_file, 'w') as f:
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
    """Build the receipt PDF from receipt data and return it as a BytesIO buffer.

    Shared by the download endpoint and the email endpoint so both produce
    the exact same PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#001846')
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor('#333333')
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4,
        textColor=colors.HexColor('#000000')
    )

    right_style = ParagraphStyle(
        'RightStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#000000')
    )

    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#000000'),
        fontName='Helvetica-Bold'
    )

    story.append(Paragraph(data['business_name'], title_style))
    story.append(Paragraph(f"Tel: {data['phone']}", header_style))
    story.append(Paragraph(data['location'], header_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(f"Ticket: {data['ticket_number']}", body_style))
    story.append(Paragraph(f"Date: {data['date']}", body_style))
    story.append(Paragraph(f"Served by: {data['served_by']}", body_style))
    if data.get('customer_name'):
        story.append(Paragraph(f"Customer: {data['customer_name']}", body_style))
    story.append(Spacer(1, 0.2*inch))

    table_data = [['Item', 'Qty', 'Price', 'Total']]
    for item in data['items']:
        name = item.get('name', 'Unknown')
        qty = item.get('quantity', 1)
        price = float(item.get('price', 0))
        total = price * qty
        table_data.append([
            name[:35],
            str(qty),
            f"{price:.2f}",
            f"{total:.2f}"
        ])

    table = Table(table_data, colWidths=[2.8*inch, 0.6*inch, 1.0*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001846')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB'))
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(f"Subtotal: {data['subtotal']:.2f} KSh", right_style))
    story.append(Paragraph(f"Total: {data['total']:.2f} KSh", bold_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"{data['payment_method']}: {data['amount_paid']:.2f} KSh", right_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CCCCCC')))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph(data['company'], body_style))
    story.append(Paragraph(f"Tel: {data['phone']}", body_style))
    story.append(Paragraph(data['email'], body_style))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph(data['thank_you'], title_style))
    story.append(Paragraph(data['policy'], body_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(data['powered_by'], body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


@app.route('/api/receipt/download/<sales_id>', methods=['GET'])
@csrf.exempt 
def download_receipt_pdf(sales_id):
    try:
        receipt_file = f'receipts/{sales_id}.json'

        if not os.path.exists(receipt_file):
            # Try to generate receipt first
            return jsonify({'success': False, 'message': 'Receipt not found. Please generate receipt first.'}), 404

        with open(receipt_file, 'r') as f:
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
            # Try to generate receipt first
            return jsonify({'success': False, 'message': 'Receipt not found. Please generate receipt first.'}), 404
        
        with open(receipt_file, 'r') as f:
            receipt_data = json.load(f)
        
        html_content = generate_receipt_html(receipt_data)
        pdf_buffer = build_receipt_pdf(receipt_data)

        msg = EmailMessage()
        msg["Subject"] = f"Receipt {sales_id} - EDMA ELECTRICALS"
        msg["From"] = "unitbaggy3@gmail.com"
        msg["To"] = email
        msg.set_content("Your receipt is attached. Please view this email in an HTML-compatible client to see it inline.")
        msg.add_alternative(html_content, subtype="html")
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
                <td style="text-align:right;">{price:.2f}</td>
                <td style="text-align:right;">{total:.2f}</td>
            </tr>
        """
    
    customer_info = ''
    if data.get('customer_name'):
        customer_info += f"<div><strong>Customer:</strong> {data['customer_name']}</div>"
    if data.get('customer_phone'):
        customer_info += f"<div><strong>Phone:</strong> {data['customer_phone']}</div>"
    if data.get('customer_email'):
        customer_info += f"<div><strong>Email:</strong> {data['customer_email']}</div>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Receipt {data['ticket_number']}</title>
        <style>
            body {{ font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
            .receipt {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 3px solid #001846; padding-bottom: 15px; margin-bottom: 20px; }}
            .business {{ font-size: 24px; font-weight: bold; color: #001846; }}
            .info {{ text-align: center; margin: 10px 0; font-size: 14px; color: #555; }}
            .customer-info {{ background: #f8f9fa; padding: 10px 15px; border-radius: 4px; margin: 10px 0; font-size: 13px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #001846; color: white; padding: 10px; text-align: left; font-size: 13px; }}
            td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
            .totals {{ text-align: right; margin: 15px 0; padding: 10px 0; border-top: 2px solid #001846; }}
            .totals div {{ padding: 3px 0; font-size: 14px; }}
            .total {{ font-size: 18px; font-weight: bold; color: #001846; }}
            .footer {{ text-align: center; border-top: 2px solid #001846; padding-top: 20px; margin-top: 20px; }}
            .thank-you {{ font-size: 18px; font-weight: bold; color: #001846; }}
            .policy {{ font-size: 12px; color: #666; margin-top: 10px; }}
            .powered {{ font-size: 11px; color: #999; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                <div class="business">{data['business_name']}</div>
                <div>Tel: {data['phone']}</div>
                <div>{data['location']}</div>
            </div>
            
            <div class="info">
                <div><strong>Ticket:</strong> {data['ticket_number']}</div>
                <div><strong>Date:</strong> {data['date']}</div>
                <div><strong>Served by:</strong> {data['served_by']}</div>
            </div>
            
            {f'<div class="customer-info">{customer_info}</div>' if customer_info else ''}
            
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th style="text-align:center;">Qty</th>
                        <th style="text-align:right;">Price</th>
                        <th style="text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>
            
            <div class="totals">
                <div>Subtotal: {data['subtotal']:.2f} KSh</div>
                <div class="total">Total: {data['total']:.2f} KSh</div>
                <div>{data['payment_method']}: {data['amount_paid']:.2f} KSh</div>
            </div>
            
            <div class="footer">
                <div class="thank-you">{data['thank_you']}</div>
                <div class="policy">{data['policy']}</div>
                <div class="powered">{data['powered_by']}</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html






def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
      """)
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(
            "unitbaggy3@gmail.com",
            "pdzy fphw zjkg zxoh",
        )
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

def load_products():
    json_path = os.path.join(app.root_path, "products2.json")
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file).get("products", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

detector = cv2.barcode.BarcodeDetector()

@app.route("/api/barcode/scan", methods=["POST"])
@csrf.exempt 
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
        if product.get("barcode") == barcode_data:
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
            # Still return success for the scan even if cart save fails
        
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
    
def generate_sales_id():
    sales_id = f"SALE_{uuid.uuid4().hex[:4].upper()}"
    return sales_id







@app.route('/api/products', methods=['GET'])
def get_products():
    products = load_products()
    instock_products = []
    for product in products:
        if product.get("instock") > 0:
            instock_products.append(product)

    search= request.args.get('search')
    if search:
        search = search.lower().strip()
        def matches_search(p):
            name = p.get('name', '').lower()
            tags = ' '.join(p.get('tags', [])).lower()
            cat = p.get('category', '').lower()
            return search in name or search in tags or search in cat
        filtered_products = []
        for product in load_products():
            if matches_search(product):
                filtered_products.append(product)
        return jsonify(filtered_products)
    return jsonify(instock_products)

CART_FILE = os.path.join(app.root_path, 'data', 'cart.json')
def load_json_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
def save_json_file(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        print("cart file not found")
        return jsonify({"status":"error", "message":"cart file not found"})
def get_user_key():
    return request.cookies.get('user_key') or str(uuid.uuid4())

@app.route('/api/cart', methods=['GET'])
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
def add_to_cart():
    data = request.json
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))
    
    if not product_id:
        return jsonify({'success': False, 'message': 'Product ID required'}), 400
    
    user_key = get_user_key()
    carts = load_json_file(CART_FILE)
    cart = carts.get(user_key, [])
    
    # Check if product already exists in cart
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
def update_cart():
    data = request.json
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
def remove_from_cart():
    data = request.json
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
def sales():
    data = request.get_json()
    items = data.get("items", [])  # Each item should have barcode and quantity
    
    products = load_products()
    sales_items = []
    total = 0
   
    
    for item in items:
        barcode = item.get("barcode")
        quantity = item.get("quantity", 1)  # Get quantity, default to 1
        
        
        found_product = None
        for product in products:
            if product.get("barcode") == barcode:
                found_product = product
                break
                
        if found_product:
            price = found_product.get("price", 0)
            buying_price = found_product.get("buying_price")
            item_total = price * quantity
            total += item_total
            profit = price - buying_price
            overal_profit = profit * quantity

            
            sales_items.append({
                "barcode": barcode,
                "name": found_product.get("name"),
                "price": price,
                "quantity": quantity, 
                
                "item_total": item_total
            })
    
    sales_id = generate_sales_id()
    status = "pending"
    created_at =datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sales_dict = {
        "sales": [{
            "sales_id": sales_id,
            "profit": overal_profit,
            "status": status,
            "created_at": created_at,
            "total": total,
            "items": sales_items
        }]
    }

    try:
        with open("sales.json", "r", encoding="utf-8") as file:
            existing_sales = json.load(file)
        existing_sales["sales"].append(sales_dict["sales"][0])
        with open("sales.json", "w", encoding="utf-8") as file:
            json.dump(existing_sales, file, indent=4)
    except FileNotFoundError:
        with open("sales.json", "w", encoding="utf-8") as file:
            json.dump(sales_dict, file, indent=4)

    return jsonify({
        "status": "success", 
        "message": "Sale created successfully", 
        "sales_id": sales_id, 
        "total": total,
        'created_at': created_at
    })

def load_sales():
    sales_path = os.path.join(app.root_path, "sales.json")
    try:
        with open(sales_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("sales", [])          
    except (FileNotFoundError, json.JSONDecodeError):
        return []

@app.route("/api/checkout", methods=["GET"])
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

def save_sales(sales):
    with open("sales.json", "w", encoding="utf-8") as f:
        json.dump({"sales": sales}, f, indent=2) 

def get_access_token(consumer_key, consumer_secret):
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url,auth=(consumer_key, consumer_secret),timeout=40)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to get access token: {response.text}")


def generate_password(shortcode, passkey):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data_to_encode = shortcode + passkey + timestamp
    encoded = base64.b64encode(data_to_encode.encode())
    return encoded.decode(), timestamp


def initiate_stk_prompt(phone, amount, callback_url, sales_id):
    try:
        consumer_secret = "56NGUdD2OyAgbdK6JpsXAOEspHXoYg7XApM0mQZtAdj0AWwg2w9xoxTcSRKzpuYQ"
        consumer_key = "IfQIojwCKZWj2KF5egPYiWi1fBNxMyJNUFGf1JRETcEFvPjS"
        shortcode = '174379'
        passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"

        access_token = get_access_token(consumer_key,consumer_secret)
        password, timestamp = generate_password(shortcode,passkey)
        base_url = "https://sandbox.safaricom.co.ke"
        url = f"{base_url}/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": sales_id,
            "TransactionDesc": "Your purchased goods payments"
        }

        response = requests.post(url,headers=headers,json=payload,timeout=30)
        response_data = response.json()
        return response_data
    except Exception as e:
        print(f"STK Error: {str(e)}")
        return {"error": str(e)}



def get_total(sales_id):
    sales = load_sales()
    for sale in sales:
        if sale.get("sales_id") == sales_id:
            return sale.get("total")
    return None


@app.route("/api/sales/payments/mpesa", methods=["POST"])
@csrf.exempt 
def payments():
    data = request.json

    if not data:
        return jsonify({"status": "error","message": "data not provided"}), 400
    sales_id = data.get("sales_id")
    mpesa_phone = data.get("phone")
    if not mpesa_phone or not sales_id:
        return jsonify({ "status": "error", "message": "data not provided"}), 400

    total = get_total(sales_id)
    if total is None:
        return jsonify({
            "status": "error",
            "message": "sales_id not found"
        }), 404

    sales = load_sales()
    found = False
    for sale in sales:
        if sale.get("sales_id") == sales_id:
            found = True
            break

    if not found:
        return jsonify({"status": "error","message": "sales_id not found"}), 404
    callback_url = "https://thats-persons-terrorist-james.trycloudflare.com/api/payment/mpesa/callback"
    try:
        response = initiate_stk_prompt(mpesa_phone,total,callback_url,sales_id)
        checkout_request_id = response.get("CheckoutRequestID")

        if checkout_request_id:
            sales = load_sales()
            for sale in sales:
                if sale.get("sales_id") == sales_id:
                    sale["checkout_request_id"] = checkout_request_id
                    save_sales(sales)
                    break

        return jsonify(response), 200

    except Exception as e:
        print(f"STK Error: {str(e)}")
        return jsonify({"status": "error","message": str(e)}), 500

@app.route("/api/payment/mpesa/callback", methods=["POST"])
@csrf.exempt 
def callback():
    data = request.json

    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 200

    stk_callback = data.get("Body", {}).get("stkCallback", {})

    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc")
    checkout_request_id = stk_callback.get("CheckoutRequestID")

    if not checkout_request_id:
        return jsonify({
            "status": "error",
            "message": "checkout_request_id missing from callback"
        }), 200

    sales = load_sales()
    sales_id = None
    salle = None

    for sale in sales:
        if sale.get("checkout_request_id") == checkout_request_id:
            salle = sale
            sales_id = sale.get("sales_id")
            break

    if sales_id is None:                          
        print(f"No matching sale for CheckoutRequestID: {checkout_request_id}")
        return jsonify({
            "status": "error",
            "message": "sales_id not found",
            "checkout_request_id": checkout_request_id
        }), 200

    if result_code == 0:
        print("Payment successful")
        

        callback_metadata = stk_callback.get("CallbackMetadata", {})
        items = callback_metadata.get("Item", [])

        mpesa_receipt = None
        amount_paid = None
        phone_number = None
        transaction_date = None

        for item in items:
            name = item.get("Name")
            if name == "MpesaReceiptNumber":
                mpesa_receipt = item.get("Value")
            elif name == "Amount":
                amount_paid = item.get("Value")
            elif name == "PhoneNumber":
                phone_number = item.get("Value")
            elif name == "TransactionDate":
                transaction_date = item.get("Value")

        updated = update_sale_status(
            sales_id,
            "paid",
            mpesa_receipt=mpesa_receipt,
            transaction_date=transaction_date,
            payment_method = "M-pesa"
        )
        

        if not updated:
            return jsonify({
                "status": "error",
                "message": "sale could not be updated",
                "sales_id": sales_id
            }), 200
        update_sell_count(sales_id)
        return jsonify({
            "status": "success",
            "message": "payment successful",
            "sales_id": sales_id,
            "checkout_request_id": checkout_request_id,
            "receipt": mpesa_receipt,
            "amount": amount_paid,
            "phone": phone_number,
            "transaction_date": transaction_date
        }), 200

    else:
        print(f"Payment failed: {result_code} - {result_desc}")

        update_sale_status(sales_id, "failed")

        return jsonify({
            "status": "failed",
            "message": result_desc,
            "sales_id": sales_id,
            "checkout_request_id": checkout_request_id
        }), 200


@app.route("/api/payment/mpesa/callback/status", methods=["POST"])
@csrf.exempt 
def callback_status():
    data = request.json
    
    if not data:
        return jsonify({"status": "error", "message": "data not provided"}), 400
    
    sales_id = data.get("sales_id")
    
    if not sales_id:
        return jsonify({"status": "error", "message": "sales_id required"}), 400
    
    sales = load_sales()
    sale = None
    
    for s in sales:
        if s.get("sales_id") == sales_id:
            sale = s
            break
    
    if not sale:
        return jsonify({"status": "error", "message": "sale not found"}), 404
    
    status = sale.get("status", "pending")
    
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
def cash_payment():
    data = request.json
    if not data:
        return jsonify({"status": "error","message": "missing data"}), 404
    sales_id = data.get("sales_id")
    sales = load_sales()
    found = False
    salle = None
    if data:
        for sale in sales:
            if sale.get("sales_id") == sales_id:
                transaction_date = sale.get("created_at")
                found = True
                salle = sale
                break
        if salle.get("status") == "paid":
             return jsonify({"status": "error","message": "This sale has already been paid"}), 400
        if not found:
            return jsonify({"status": "error","message": "sales_id not found"}), 404
        updated = update_sale_status(
            sales_id,
            "paid",
            transaction_date=transaction_date,
            payment_method = "Cash",
            mpesa_receipt = "No transactionID"
            
        )
        if not updated:
            return jsonify({
                "status": "error",
                "message": "sale could not be updated",
                "sales_id": sales_id
            }), 200
        
        update_sell_count(sale=salle)
        return jsonify({
            "status": "success",
            "message": "payment successful",
            "sales_id": sales_id,
        }), 200
    else:
        print(f"Payment failed")

        update_sale_status(sales_id, "failed")

        return jsonify({
            "status": "failed",
            "message": "sales id was not found please make another sale",
            "sales_id": sales_id,
            
        }), 200



@app.route("/api/sales/payments/hybrid", methods=["POST"])
@csrf.exempt 
def hybrid_payment():

    data = request.json

    if not data:
        return jsonify({
            "status": "error",
            "message": "data not provided"
        }), 400

    sales_id = data.get("sales_id")
    phone = data.get("phone")
    cash_amount = data.get("cash_amount", 0)
    mpesa_amount = data.get("mpesa_amount", 0)


    if not sales_id:
        return jsonify({
            "status": "error",
            "message": "sales_id required"
        }), 400

    if not phone:
        return jsonify({
            "status": "error",
            "message": "phone required"
        }), 400

    try:
        cash_amount = float(cash_amount)
        mpesa_amount = float(mpesa_amount)
    except (ValueError, TypeError):

        return jsonify({
            "status": "error",
            "message": "Invalid payment amounts"
        }), 400


    sales = load_sales()

    sale = None

    for s in sales:
        if s.get("sales_id") == sales_id:
            sale = s
            break

    if sale.get("status") == "paid":
        return jsonify({
            "status": "error",
            "message": "This sale has already been paid"
        }), 400
    
    if not sale:
        return jsonify({
            "status": "error",
            "message": "Sale not found"
        }), 404


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
    callback_url = (
        "https://your-domain.com"
        "/api/payment/mpesa/callback"
    )
    try:
        response = initiate_stk_prompt(
            phone,
            mpesa_amount,
            callback_url,
            sales_id
        )
    except Exception as e:

        sale["payments"]["mpesa"]["status"] = "failed"
        save_sales(sales)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500



    checkout_request_id = response.get(
        "CheckoutRequestID"
    )

    if not checkout_request_id:
        sale["payments"]["mpesa"]["status"] = "failed"
        save_sales(sales)
        return jsonify({
            "status": "error",
            "message": "M-PESA STK Push failed",
            "mpesa_response": response
        }), 400

    sale["payments"]["mpesa"]["checkout_request_id"] = (
        checkout_request_id
    )
    save_sales(sales)
    update_sell_count(sale)


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
        quantity = item.get("quantity", 1)
        for product in products:
            if str(product.get("barcode")) == str(barcode):
                current_count = product.get("sell_count", 0)
                product["sell_count"] = current_count + quantity
                break

    try:
        with open("products2.json", "w", encoding="utf-8") as file:
            json.dump(
                {"products": products},
                file,
                indent=4,
                ensure_ascii=False
            )

        return True

    except Exception as e:
        print(f"Failed to update product sell counts: {e}")
        return False



@app.route("/api/admin/sales/summary", methods=["GET"])
@csrf.exempt 
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
        start_of_next_month = today.replace(
            year=today.year + 1,
            month=1,
            day=1
        )
    else:
        start_of_next_month = today.replace(
            month=today.month + 1,
            day=1
        )

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

        created_at = datetime.strptime(
            sale.get("created_at"),
            "%Y-%m-%d %H:%M:%S"
        )

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
def sales_history():
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
def weekly_sales():
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=6)

    weekly_revenue = {
        "Sunday": 0,
        "Monday": 0,
        "Tuesday": 0,
        "Wednesday": 0,
        "Thursday": 0,
        "Friday": 0,
        "Saturday": 0
    }

    weekly_sales = {
        "Sunday": 0,
        "Monday": 0,
        "Tuesday": 0,
        "Wednesday": 0,
        "Thursday": 0,
        "Friday": 0,
        "Saturday": 0
    }

    sales = load_sales()

    for sale in sales:
        if sale.get("status") != "paid":
            continue

        created_at = datetime.strptime(
            sale.get("created_at"),
            "%Y-%m-%d %H:%M:%S"
        )

        sale_date = created_at.date()

        if sunday <= sale_date <= saturday:
            day_name = sale_date.strftime("%A")
            weekly_revenue[day_name] += sale.get("total", 0)
            weekly_sales[day_name] += 1

    return jsonify({
        "status": "success",
        "week": {
            "sunday": sunday.isoformat(),
            "saturday": saturday.isoformat()
        },
        "revenue": weekly_revenue,
        "sales": weekly_sales
    }), 200




@app.route("/api/admin/items/stock", methods=["GET"])
@csrf.exempt 
def load_outofstock_products():
    products = load_products()
    filtered_products = []
    out_of_stock = False
    for product in products:
        if product.get("instock") == 0:
            out_of_stock = True
            filtered_products.append(product)

    if out_of_stock:
        return jsonify({
            "status": "success",
            "out_of_stock_items": filtered_products
        }), 200
    else:
        return []

    

@app.route("/api/admin/items/stock/edit", methods=["POST"])
@csrf.exempt 
def edit_stock():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "missing fields"})
    barcode = data.get("barcode")
    stock_quantity = data.get("stock_quantity")
    products = load_products()
    for product in products:
        if product.get("barcode") == barcode:
            product["instock"] = stock_quantity
            break

    try:
        with open("products2.json", "w", encoding="utf-8") as file:
            json.dump(products, file, indent=4)

        return True

    except Exception as e:
        print(f"Failed to update product sell counts: {e}")
        return False



ALLOWED_EXTENSIONS = {''
'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/admin/items/upload', methods=['POST'])
@csrf.exempt 
def admin_add_product():
    
    
    name = request.form.get('name', '').strip()
    price = request.form.get('price')
    barcode = request.form.get('barcode')
    tags_raw = request.form.get('tags', '').strip()
    buying_price = request.form.get('buying price')
    stock_amount = request.form.get('stock_amount', 1).strip()
    
    if not all([name, buying_price, price, stock_amount]):
        return jsonify({"error": "Missing required fields:name, buying price, price, stock amount"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"error": "Price must be a number"}), 400

    if buying_price:
        try:
            buying_price = float(buying_price)
        except ValueError:
            return jsonify({"error": "old_price must be a number"}), 400
    else:
        buying_price = None

    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    

    main_image_file = request.files.get('main_image')
    if not main_image_file or main_image_file.filename == '':
        return jsonify({"error": "main_image is required"}), 400

    if not allowed_file(main_image_file.filename):
        return jsonify({"error": "Invalid file type for main_image"}), 400

    main_filename = secure_filename(barcode + '_main_' + main_image_file.filename)
    main_path = os.path.join(app.root_path, 'static', 'images', main_filename)
    main_image_file.save(main_path)

    image_files = request.files.getlist('images')
    image_paths = []
    for img_file in image_files:
        if img_file and img_file.filename and allowed_file(img_file.filename):
            img_filename = secure_filename(barcode + '_' + img_file.filename)
            img_path = os.path.join(app.root_path, 'static', 'images', img_filename)
            img_file.save(img_path)
            image_paths.append('/static/images/' + img_filename)

    stock_interger = int(stock_amount)
    main_image_url = '/static/images/' + main_filename
    new_product = {
        "barcode": barcode,
        "name": name,
        "price": price,
        "buying_price": buying_price,
        "tags": tags,
        "instock": stock_interger,
        "image": main_image_url,
    }

    products = load_products()
    if any(p.get('barcode') == barcode for p in products):
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
def stock_value():
    products = load_products()
    stock_value = 0
    for product in products:
        value = product.get("price") * product.get("instock")
        stock_value += value
        
    return jsonify({"status": "success", "stock_value": stock_value}), 200
    


if __name__ == "__main__":
    print("Starting Flask...")
    app.run(debug=True, host="0.0.0.0", port=5000)