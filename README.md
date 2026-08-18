# Point of Sale (POS) System

A web-based Point of Sale system built to manage products, barcode scanning, shopping carts, sales, and digital payments. The project is designed as a practical, modular POS solution with a Python/Flask backend and a JavaScript-based frontend.

## Features

* Barcode-based product scanning
* Product lookup and management
* Dynamic shopping cart
* Automatic subtotal and total calculation
* Sales and transaction management
* M-PESA payment integration through the Safaricom Daraja API
* Payment callback handling
* JSON-based product and sales data
* REST API endpoints for frontend-backend communication
* Camera-based barcode scanning
* Responsive web interface

## Tech Stack

### Backend

* Python
* Flask
* SQLite
* OpenCV
* NumPy

### Frontend

* HTML
* CSS
* JavaScript
* Fetch API
* Browser Camera API

### Payments

* Safaricom M-PESA Daraja API

## How It Works

```text
Barcode Scanner
      |
      v
Frontend
      |
      v
Flask API
      |
      v
Product Database
      |
      v
Shopping Cart
      |
      v
Checkout
      |
      v
M-PESA STK Push
      |
      v
Payment Callback
      |
      v
Transaction Record
```

## Barcode Scanning

The system can access a device camera from the browser and capture frames for barcode detection. The captured image is sent to the Flask backend, where OpenCV processes the image and attempts to identify the barcode.

Once a barcode is detected, the backend searches the product data and returns the matching product information to the frontend.

## Payment Flow

The checkout process is designed around the M-PESA Daraja API.

1. Customer proceeds to checkout.
2. The system calculates the total amount.
3. The customer provides their M-PESA phone number.
4. The backend initiates an STK Push.
5. The customer enters their M-PESA PIN.
6. Safaricom processes the transaction.
7. Safaricom sends the transaction result to the callback endpoint.
8. The backend verifies the result and updates the transaction record.
9. coming soon - paypal + cards + cash payment methods.


## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/your-pos-repository.git
cd your-pos-repository
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the Flask application:

```bash
python app.py
```

The application will then be available through the local Flask server.

## M-PESA Configuration

The M-PESA integration requires valid Daraja API credentials.

Configure the required credentials in your environment rather than hard-coding them into the source code.

Typical configuration includes:

```text
CONSUMER_KEY
CONSUMER_SECRET
PASSKEY
SHORTCODE
CALLBACK_URL
```

For development, use the M-PESA Daraja sandbox environment.

## API

Example endpoints include:

```text
POST /api/barcode/scan
POST /api/cart
GET  /api/products
POST /api/checkout
POST /api/payment/mpesa/stkpush
POST /api/payment/mpesa/callback
```

The API handles communication between the frontend, product data, sales system, and payment services.

## Future Improvements

* MySQL/PostgreSQL database support
* Authentication and role-based access
* Inventory management
* Stock alerts
* Sales analytics and reporting
* Printable receipts
* User/customer accounts
* Multiple payment methods
* Admin dashboard
* Improved barcode detection
* Deployment-ready production configuration

## Disclaimer

This project is developed for learning and practical software development purposes. Payment functionality should be properly secured and configured before being used in a production environment.
Note that some sensitive data is hardcoded for now later will be added to .env just to let you know its hardcoded. BUT I KNOW HOW TO HIDE SENSITIVE DATA ITS JUST THAT ITS NOT THAT IMPORTANT DATA 😂
