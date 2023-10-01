import datetime
import hashlib
import secrets
import string
import time
import datetime
import random
from tokenize import generate_tokens
from PIL import Image
from flask import Flask, redirect, render_template, request, send_file, send_from_directory, session, url_for, flash
from flask_pymongo import PyMongo
import jinja2
from weasyprint import HTML, CSS, default_url_fetcher
import qrcode
import base64
import io
from pdf2image import convert_from_path
import requests
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from datetime import datetime, timedelta




# Generate a random string of characters for the secret key
def generate_secret_key(length=24):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for _ in range(length))


app = Flask(__name__)
# MongoDB configuration
app.config['MONGO_URI'] = 'mongodb://localhost:27017/cert'
mongo = PyMongo(app)

app.config['MAILGUN_API_KEY'] = 'apikey'
app.config['MAILGUN_DOMAIN'] = 'domain'

# Use the generated key as your secret_key
app.secret_key = generate_secret_key()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    error_message = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query the MongoDB collection for admin credentials
        admin = mongo.db.admin.find_one({'username': username, 'password': password})

        if admin:
            # Set a session variable to indicate that the user is logged in as an admin
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Login Fail, check your username & Password.', 'danger')
            error_message = 'Invalid credentials. Please try again.'


    return render_template('login.html', error_message=error_message)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' in session:
        return render_template('dashboard.html')
    else:
        return redirect(url_for('login'))
    
@app.route('/to/dashboard')
def todashboard():
    return render_template('dashboard.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


# Function to generate a secure random token
def generate_reset_token():
    return secrets.token_hex(16)

# Function to check if the reset token has expired (e.g., expires in 1 hour)
def is_token_expired(expiry_time):
    current_time = datetime.datetime.utcnow()
    return current_time > expiry_time

# Route for requesting a password reset
@app.route('/admin/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        user = mongo.db.admin.find_one({'email': email})

        if user:
            # Generate a reset token and set an expiry time (e.g., 1 hour from now)
            reset_token = generate_reset_token()
            expiry_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            mongo.db.admin.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'reset_token': reset_token,
                        'reset_token_expiry': expiry_time
                    }
                }
            )

            # Send an email with a reset link
            # In a real app, you'd send an email with a reset link
            flash('Password reset email sent. Check your inbox.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found.', 'danger')

    return render_template('resetrequest.html')

# Route for resetting the password
@app.route('/admin/reset_password/<reset_token>', methods=['GET', 'POST'])
def reset_password(reset_token):
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Check if the reset token exists in the database
        user = mongo.db.admin.find_one({'reset_token': reset_token})

        if user:
            # Check if the reset token has expired
            expiry_time = user.get('reset_token_expiry')
            if expiry_time and is_token_expired(expiry_time):
                flash('Reset token has expired. Please request a new one.', 'danger')
                return redirect(url_for('login'))

            # Check if the new password matches the confirmation
            if new_password == confirm_password:
                # Hash the new password and update it in the database
                hashed_password = generate_password_hash(new_password)
                mongo.db.admin.update_one({'_id': user['_id']}, {'$set': {'password': hashed_password}})
                
                # Remove the reset token and expiry time from the user's document
                mongo.db.admin.update_one({'_id': user['_id']}, {'$unset': {'reset_token': 1, 'reset_token_expiry': 1}})
                
                flash('Password reset successfully. You can now log in with your new password.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Passwords do not match.', 'danger')
        else:
            flash('Invalid or expired reset token.', 'danger')

    return render_template('resetpassword.html', reset_token=reset_token)


# Load the template
template_loader = jinja2.FileSystemLoader(searchpath="./templates")
template_env = jinja2.Environment(loader=template_loader)
template = template_env.get_template("certificate.html")



@app.route('/admin/issue', methods=["GET", "POST"])
def issue_certificate():
    if request.method == 'POST':
        global unique_id
        timestamp = int(time.time() * 1000)  # Convert to milliseconds
        unique_id = f"{timestamp}{random.randint(0, 9999)}"

        # Retrieve form data
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        date_of_issue = request.form['date_of_issue']
        issuer_name = request.form['issuer_name']
        reason_for_issue = request.form['reason_for_issue']
        email = request.form['email']

         # Generate the QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f'https://example.com/verifypage/{unique_id}')  # Replace with your verification URL
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert the QR code image to base64
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

        # Create a dictionary to represent the certificate data
        certificate_data = {
            'first_name': first_name,
            'last_name': last_name,
            'date_of_issue': date_of_issue,
            'issuer_name': issuer_name,
            'reason_for_issue': reason_for_issue,
            'email': email,
            'uniqueid': unique_id,
            'qr_code' : qr_base64
        }

         # Insert the certificate data into the MongoDB collection
        mongo.db.cdata.insert_one(certificate_data)

       
        # Create a dictionary to represent the certificate data
        data = {
            "FNAME": first_name,
            "LNAME": last_name,
            "REASON": reason_for_issue,
            "ISSUEBY": issuer_name,
            "DATE": date_of_issue,
            "UNIQUEID": unique_id,
            "QR_CODE": qr_base64  # Add the base64-encoded QR code to data
        }

       
        # Render the template with actual data
        rendered_html = template.render(data)

        # Create a PDF from the rendered HTML using WeasyPrint
        pdf_output_path = f'certificate_{unique_id}.pdf'  # Save each certificate with a unique name
        HTML(string=rendered_html).write_pdf(pdf_output_path)

         # Send the certificate via email
        email_response = send_certificate_email(email, pdf_output_path)

        # Check the email response and handle any errors
        if email_response.status_code == 200:
            flash('Certificate issued successfully and sent via email!', 'success')
        else:
            flash('Failed to send the email. Please check your email settings.', 'danger')

        # Provide a download link for the generated PDF
        return send_file(pdf_output_path, as_attachment=True)

    return render_template('issue.html')

def send_certificate_email(email, pdf_path):
    # Mailgun API endpoint and credentials
    mailgun_api_key = app.config['MAILGUN_API_KEY']
    mailgun_domain = app.config['MAILGUN_DOMAIN']

    mailgun_base_url = f'https://api.mailgun.net/v3/{mailgun_domain}/messages'
    auth = ('api', mailgun_api_key)

    # Recipient's email address
    recipient_email = email
    
    # Email subject and content
    subject = 'Congratulations! Here is your certificate'
    html_body = f'''
        <html>
            <body>
                <p>Your certificate with unique ID {unique_id} is attached.</p>
                <p>Star this email for future reference.</p>
                <p>See the attached certificate for details.</p>
            </body>
        </html>
    '''

    # Create a request to send the email with HTML body
    response = requests.post(
        f"{mailgun_base_url}",
        auth=auth,
        data={
            'from': 'Your Name <your_email@example.com>',  # Replace with your email and name
            'to': recipient_email,
            'subject': subject,
            'html': html_body
        },
        files=[
            ("attachment", ("certificate.pdf", open(pdf_path, "rb").read()))
        ]
    )

    return response



@app.route('/admin/verify', methods=["GET", "POST"])
def verify_certificate():
    if request.method == 'POST':
        unique_id = request.form['unique_id']

        # Check if the certificate with the provided unique ID exists in the database
        certificate = mongo.db.cdata.find_one({'uniqueid': unique_id})
        if certificate:
           
            flash('Certificate verified successfully!', 'success')
            return render_template('verify.html', certificate=certificate)
        else:
            # Certificate not found, display an error message
            flash('Certificate not found with the provided Unique ID.', 'error')

    return render_template('verify.html')


@app.route('/admin/delete', methods=["GET", "POST"])
def delete_certificate():
    if request.method == 'POST':
        unique_id = request.form['unique_id']

        # Check if the certificate with the provided unique ID exists in the database
        certificate = mongo.db.cdata.find_one({'uniqueid': unique_id})

        if certificate:
            # Certificate found, perform deletion action here

            # Delete the certificate from the database (you'll need to implement this)
            mongo.db.cdata.delete_one({'uniqueid': unique_id})

            # Display a flash message for successful deletion
            flash('Certificate deleted successfully!', 'success')
        else:
            # Certificate not found, display an error message
            flash('Certificate not found with the provided Unique ID.', 'error')

    return render_template('delete.html')

# ... (other routes and app setup)




#####STUDENT
@app.route('/student/home')
def student_home():
    return render_template('sdashboard.html')

@app.route('/student/sverify', methods=["GET", "POST"])
def student_verify():
    if request.method == 'POST':
        unique_id = request.form['unique_id']

        # Check if the certificate with the provided unique ID exists in the database
        certificate = mongo.db.cdata.find_one({'uniqueid': unique_id})
        if certificate:
            flash('Certificate verified successfully!', 'success')
            return render_template('sverify.html', certificate=certificate)
        else:
            # Certificate not found, display an error message
            flash('Certificate not found with the provided Unique ID.', 'error')
    return render_template('sverify.html')


# Define the route for certificate download
@app.route('/student/sdownload', methods=["GET", "POST"])
def download_certificate():
    if request.method == 'POST':
        email = request.form['email']
        unique_id = request.form['unique_id']

        # Check if the certificate with the provided unique ID exists in the database
        certificate = mongo.db.cdata.find_one({'uniqueid': unique_id})

        if certificate:
            # Generate the certificate PDF
            pdf_output_path = generate_certificate(certificate)

            # Send the certificate via email
            email_response = send_certificate_email(email, pdf_output_path)

            # Check the email response and handle any errors
            if email_response.status_code == 200:
                flash('Certificate sent successfully via email!', 'success')
            else:
                flash('Failed to send the email. Please check your email settings.', 'danger')

            # Provide a download link for the generated PDF
            return send_file(pdf_output_path, as_attachment=True)

        else:
            flash('Certificate not found with the provided Unique ID.', 'error')

    return render_template('sdownload.html')

def generate_certificate(certificate_data):
    # Create a dictionary to represent the certificate data
    data = {
        "FNAME": certificate_data['first_name'],
        "LNAME": certificate_data['last_name'],
        "REASON": certificate_data['reason_for_issue'],
        "ISSUEBY": certificate_data['issuer_name'],
        "DATE": certificate_data['date_of_issue'],
        "UNIQUEID": certificate_data['uniqueid'],
        "QR_CODE": certificate_data['qr_code']  # Assuming you have a QR code in the database
    }

    # Render the template with actual data
    rendered_html = render_template('certificate.html', **data)  # Pass data as keyword arguments

    # Create a PDF from the rendered HTML using WeasyPrint
    pdf_output_path = f'certificate_{certificate_data["uniqueid"]}.pdf'
    HTML(string=rendered_html).write_pdf(pdf_output_path)

    return pdf_output_path

def send_certificate_email(email, pdf_path):
    # Mailgun API endpoint and credentials
    mailgun_api_key = app.config['MAILGUN_API_KEY']
    mailgun_domain = app.config['MAILGUN_DOMAIN']

    mailgun_base_url = f'https://api.mailgun.net/v3/{mailgun_domain}/messages'
    auth = ('api', mailgun_api_key)

    # Recipient's email address
    recipient_email = email

    # Email subject and content
    subject = 'Congratulations! Here is your certificate'
    html_body = f'''
        <html>
            <body>
                <p>Your certificate is attached.</p>
                <p>Star this email for future reference.</p>
                <p>See the attached certificate for details.</p>
            </body>
        </html>
    '''

    # Create a request to send the email with HTML body
    response = requests.post(
        f"{mailgun_base_url}",
        auth=auth,
        data={
            'from': 'khushal sarode <khushalsarode.in@gmail.com>',  # Replace with your email and name
            'to': recipient_email,
            'subject': subject,
            'html': html_body
        },
        files=[
            ("attachment", ("certificate.pdf", open(pdf_path, "rb").read()))
        ]
    )

    return response



@app.route('/student/dashboard')
def studentdashboard():
    return render_template('sdashboard.html')






if __name__ == '__main__':
    app.run(debug=True)



