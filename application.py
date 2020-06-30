import os, requests

from flask import Flask, session, render_template, redirect, request, flash, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["GET", "POST"])
def index():
    if session.get('user_id'):
        return render_template("index.html")
    
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("index.html", errors=True, message="Please, insert your username")
        if not request.form.get("password"):
            return render_template("index.html", errors=True, message="Please, insert your password")

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")}).fetchone()
        if not user:
            return render_template("index.html", errors=True, message="Username does not exist!")
        if user[2] != request.form.get("password"):
            return render_template("index.html", errors=True, message="Invalid password. Please, try again.")
        else:
            session["user_id"]   = user[0]
            session["username"] = user[1]
            return render_template("index.html")

    else:   
        return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if session.get('user_id'):
        return redirect("/")

    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("register.html", errors=True, message="Please, choose a username")
        if not request.form.get("email"):
            return render_template("register.html", errors=True, message="Please, provide your email")
        if not request.form.get("password"):
            return render_template("register.html", errors=True, message="Please, choose a password")
        if not request.form.get("first_name"):
            return render_template("register.html", errors=True, message="Please, provide your first name")
        if not request.form.get("last_name"):
            return render_template("register.html", errors=True, message="Please, provide your last name")

        if request.form.get("email") != request.form.get("confirm_email"):
            return render_template("register.html", errors=True, message="Emails don't match!")
        if request.form.get("password") != request.form.get("confirm_password"):
            return render_template("register.html", errors=True, message="Passwords don't match!")

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")}).fetchone()
        if user:
            return render_template("register.html", errors=True, message="Username already exists")

        db.execute("INSERT INTO users (username, password, email, first_name, last_name) VALUES (:username, :password, :email, :first_name, :last_name)",
                            {"username":request.form.get("username"), "password":request.form.get("password"), "email":request.form.get("email"),
                             "first_name":request.form.get("first_name"), "last_name":request.form.get("last_name")})
        db.commit()

        return render_template("index.html", register=True)

    else:    
        return render_template("register.html")

@app.route("/search", methods=["GET", "POST"])
def search():
    if not session.get('user_id'):
        return redirect("/")
    
    if request.method == "POST":
        if not request.form.get("searchingfor"):
            return render_template("search.html", errors=True)

        search_by  = request.form.get("searchingby")
        search_for = f"%{request.form.get('searchingfor')}%"

        books = db.execute(f"SELECT id, title, author, year, isbn FROM books WHERE LOWER({search_by}) LIKE LOWER(:query) ORDER BY year", 
                           {"query":search_for}).fetchall()

        if not books:
            return render_template("search.html", errors=True)
        else:
            return render_template("search.html", books=books)

    else:
        return render_template("search.html")

@app.route("/book<isbn>", methods=['GET','POST'])
def book(isbn):
    if not session.get('user_id'):
        return redirect("/")

    book = db.execute(f"SELECT id, title, author, year, isbn FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()

    reviews = db.execute("SELECT users.username, comment, mark, to_char(posting_date, 'DD Mon YY - HH24:MI:SS') as posting_date \
                            FROM users INNER JOIN reviews ON users.id = reviews.user_id WHERE book_id = :book_id \
                            ORDER BY posting_date DESC", {"book_id": book[0]}).fetchall()

    key      = os.getenv("GOODREADS_KEY")
    query    = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": isbn})
    response = query.json()
    api      = response['books'][0]
    
    if request.method == "POST":

        check = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id", {"user_id": session['user_id'], "book_id": book[0]})
        if check.rowcount == 1:
            return render_template("book.html", book=book, api=api, reviews=reviews, errors=True)

        mark    = int(request.form.get("rating"))
        comment = request.form.get("review")

        db.execute("INSERT INTO reviews (user_id, book_id, comment, mark) VALUES \
                    (:user_id, :book_id, :comment, :rating)",
                    {"user_id": session['user_id'], 
                    "book_id": book[0], 
                    "comment": comment, 
                    "rating": mark})

        db.commit()

        return redirect(url_for("book", isbn=book[4]))

    else:
        return render_template("book.html", book=book, api=api, reviews=reviews)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/<isbn>", methods=['GET'])
def api_call(isbn):

    cursor = db.execute("SELECT title, author, year, isbn, COUNT(reviews.id) as review_count, AVG(reviews.mark) as average_score \
                      FROM books INNER JOIN reviews ON books.id = reviews.book_id \
                      WHERE isbn = :isbn  GROUP BY title, author, year, isbn",
                      {"isbn": isbn})

    if cursor.rowcount != 1:
        return jsonify({"Error": "Provided ISBN did not match"}), 404
   
    row    = cursor.fetchone()
    result = dict(row.items())

    result['average_score'] = round(float(result['average_score']), 2)

    return jsonify(result)