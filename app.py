import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    rows = db.execute("SELECT * FROM stocks WHERE id = ? ORDER BY symbol ASC", session["user_id"])

    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    sum = 0.0

    for i in range(len(rows)):
        stock = lookup(rows[i]["symbol"])
        rows[i]["name"] = stock["name"]
        rows[i]["price"] = stock["price"]
        rows[i]["stokssum"] = stock["price"] * rows[i]["shares"]
        sum += rows[i]["stokssum"]



    return render_template("index.html", rows = rows, cash=user[0]["cash"], sum=sum + user[0]["cash"])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        quoterow = lookup(request.form.get("symbol"))
        if quoterow == None :
            return apology("quote error")

        try:
            if int(request.form.get('shares')) < 0:
                return apology('invalid input of shares', 400)
        except:
            return apology('invalid input for shares', 400)

        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]['cash'] - quoterow['price'] * int(request.form.get("shares"))

        if cash < 0:
            return apology("no money")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        shares = db.execute("SELECT shares FROM stocks WHERE id = ? and symbol = ?", session["user_id"], quoterow['symbol'])

        if len(shares) == 1:
            db.execute("UPDATE stocks SET shares = ? WHERE id = ? and symbol = ?", int(shares[0]['shares']) + int(request.form.get("shares")), session["user_id"], quoterow['symbol'])
        else:
            db.execute("INSERT INTO stocks (id, symbol, shares) VALUES (?, ?, ?)", session["user_id"], quoterow['symbol'], int(request.form.get("shares")))

        db.execute("INSERT INTO transactions (id, symbol, shares, price, datetime) VALUES (?, ?, ?, ?, ?)", session["user_id"], quoterow['symbol'], int(request.form.get("shares")), quoterow['price'], datetime.datetime.now())
        return redirect("/")
    else:
        return render_template("buy.html")
    #return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE id = ?", session["user_id"])
    if len(rows) == 0 :
       return apology("No history")
    return render_template("history.html", rows = rows)

    #return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        quoterow = lookup(request.form.get("symbol"))
        if quoterow == None :
            return apology("symbol error")
        return render_template("quoted.html", quoterow=quoterow['name'] + '(' + quoterow['symbol'] + ')' +' cost ' + usd(quoterow['price']))


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")
    #return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was confirmated
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("must confirmate password", 400)

        rows = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 0:
            return apology("username is already registered", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    #return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        quoterow = lookup(request.form.get("symbol"))
        if quoterow == None :
            return apology("quote error")

        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]['cash']

        rows = db.execute("SELECT * FROM stocks WHERE id = ? AND symbol = ?", session["user_id"], quoterow['symbol'])


        if len(rows) == None :
            return apology("no such shares")
        elif int(rows[0]['shares']) < int(request.form.get("shares")):
            return apology("not enough shares")
        elif int(rows[0]['shares']) == int(request.form.get("shares")):
            cash = cash + quoterow['price'] * int(request.form.get("shares"))
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
            db.execute("DELETE FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], quoterow['symbol'])

        else:
            cash = cash + quoterow['price'] * int(request.form.get("shares"))
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
            db.execute("UPDATE stocks SET shares = ? WHERE id = ? and symbol = ?", int(rows[0]['shares']) - int(request.form.get("shares")), session["user_id"], quoterow['symbol'])


        db.execute("INSERT INTO transactions (id, symbol, shares, price, datetime) VALUES (?, ?, ?, ?, ?)", session["user_id"], quoterow['symbol'], int(request.form.get("shares")) * (-1), quoterow['price'], datetime.datetime.now())
        return redirect("/")
    else:
        return render_template("sell.html")
    #return apology("TODO")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "POST":
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]['cash']
        cash += int(request.form.get("addcash"))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])
        return redirect("/")
    else:
        return render_template("addcash.html")