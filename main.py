from flask import Flask, render_template, request, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
import json
import pymysql
import os
import  math

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = 'super-secret-key'


# Load config file
with open('config.json', 'r') as c:
    params = json.load(c)["params"]
app.config['UPLOAD_FOLDER'] = params['location_upload']
# Fix capitalization issues in MAIL config
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=465,  # Should be an integer, not a string
    MAIL_USE_SSL=True,  # Fixed key name
    MAIL_USERNAME=params['gmail-user'],
    MAIL_PASSWORD=params['gmail-password']
)

mail = Mail(app)

# Database connection
local_server = True
if local_server:
    app.config["SQLALCHEMY_DATABASE_URI"] = params['local_uri']
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = params['prod_uri']

db = SQLAlchemy(app)


# Database model
class Contact(db.Model):
    srno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email_address = db.Column(db.String(120), nullable=False)
    phone_num = db.Column(db.String(12), nullable=False)
    msg = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(12), nullable=True)


class Post(db.Model):
    __tablename__ = 'posts'
    srno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    content = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now)
    img_file = db.Column(db.String(12), nullable=True)
    sub_title = db.Column(db.String(12), nullable=True)


@app.route("/")
def home():
    posts = Post.query.all()
    per_page = int(params['no_of_post'])  # Number of posts per page
    last = math.ceil(len(posts) / per_page)  # Ensure rounding up

    # Get the page number from request, default to 1
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    if page > last:
        page = last

    # Slicing posts for pagination
    posts = posts[(page - 1) * per_page: page * per_page]

    # Setting prev and next buttons correctly
    prev = f"/?page={page - 1}" if page > 1 else "#"
    next = f"/?page={page + 1}" if page < last else "#"

    return render_template('index.html', params=params, posts=posts, prev=prev, next=next)

@app.route("/logout")
def logout():
    session.pop('user')
    return redirect("/dashboard")

@app.route("/delete/<string:srno>", methods=['GET', 'POST'])
def delete(srno):
    if 'user' in session and session['user'] == params['admin_user']:
        posts = Post.query.filter_by(srno=srno).first()
        db.session.delete(posts)
        db.session.commit()
    return redirect("/dashboard")


@app.route("/uploader", methods=['GET', 'POST'])
def upload():
    if 'user' in session and session['user'] == params['admin_user']:
        if request.method == 'POST':
            f = request.files['file1']
            upload_folder = app.config['UPLOAD_FOLDER']

            # Ensure the upload directory exists
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)  # Create folder if it doesn't exist

            file_path = os.path.join(upload_folder, secure_filename(f.filename))
            f.save(file_path)
            return "Uploaded successfully"

    return "Unauthorized access"



@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('Phone')
        message = request.form.get('message')

        entry = Contact(name=name, email_address=email, phone_num=phone, date=datetime.now(), msg=message)
        db.session.add(entry)
        db.session.commit()

        msg = (Message
            (
            subject='A new message from ' + name,
            sender=email,
            recipients=[params['gmail-user']],  # Fixed typo
            body=message + "\nPhone: " + phone
        ))
        print(msg)
        mail.send(msg)

    return render_template('contact.html', params=params)


@app.route("/about")
def about():
    return render_template('about.html', params=params)


@app.route("/dashboard", methods=['GET', 'POST'])
def dashboard():
    if 'user' in session and session['user'] == params['admin_user']:
        posts = Post.query.all()
        return render_template("dashboard.html", params=params, posts=posts)

    if request.method == 'POST':
        username = request.form.get('uname')
        userpass = request.form.get('pass')
        if username == params['admin_user'] and userpass == params['admin_password']:
            session['user'] = username
            posts = Post.query.all()
            return render_template('dashboard.html', params=params, posts=posts)

    return render_template('form.html', params=params)


@app.route("/edit/<string:srno>", methods=['GET', 'POST'])
def edit(srno):
    if 'user' in session and session['user'] == params['admin_user']:
        if request.method == 'POST':
            box_title = request.form.get('title')
            sub_title = request.form.get('sub_title')
            slug = request.form.get('slug')
            content = request.form.get('content')
            img_file = request.form.get('img_file')
            date = datetime.now()

            if srno == '0':  # New post
                post = Post(title=box_title, slug=slug, sub_title=sub_title, content=content, img_file=img_file, date=date)
                db.session.add(post)
                db.session.commit()
                return redirect(f"/edit/{post.srno}")  # Redirect to edit the new post

            else:
                post = Post.query.filter_by(srno=srno).first()
                if post:
                    post.title = box_title
                    post.slug = slug
                    post.content = content
                    post.sub_title = sub_title
                    post.img_file = img_file
                    post.date = date
                    db.session.commit()
                return redirect(f"/edit/{srno}")

        post = Post.query.filter_by(srno=srno).first()

        # If post is None, create an empty object to prevent Jinja errors
        if not post:
            post = Post(srno=0, title="", sub_title="", slug="", content="", img_file="", date=datetime.now())

        return render_template('edit.html', params=params, post=post)




@app.route("/post/<string:post_slug>", methods=['GET'])
def post_route(post_slug):
    post = Post.query.filter_by(slug=post_slug).first()
    return render_template('post.html', params=params, post=post)


if __name__ == "__main__":
    app.run(debug=True)
