import os

import sqlite3

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, isNumeric


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
connection = sqlite3.connect("finance.db", check_same_thread=False)
db = connection.cursor()

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = (session["user_id"],)
    accounts_data = db.execute("SELECT * FROM accounts WHERE user_id = ?", user_id).fetchall()
    total = 0

    # get stock name, price and calculate totals
    n = 0
    accounts = []
    for account in accounts_data:
        accounts.append({})
        # lookup stock data
        stock = lookup(account[1])
        accounts[n]["symbol"] = account[1]
        accounts[n]["name"] = stock["name"]
        accounts[n]["price"] = stock["price"]
        accounts[n]["shares"] = account[2]
        accounts[n]["total"] = stock["price"] * account[2]
        total += accounts[n]["total"]
        n += 1

    cash = db.execute("SELECT cash FROM users WHERE id =?", user_id).fetchone()
    cash = float(cash[0])
    total += cash
    return render_template("index.html", accounts=accounts, cash=cash, total=total)
    
    
@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """add more cash"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure cash was submitted
        if not request.form.get("cash"):
            return apology("must provide amount of cash")
        # Ensure cash is numeric
        if not isNumeric(request.form.get("cash")):
            return apology("provide a number", 400)
        # Ensure cash is positive and non zero
        if float(request.form.get("cash")) < 1:
            return apology("number must be greater than 0", 400)
        # Ensure cash is to 2 decimals
        if len(request.form.get("cash").rsplit('.')) != 2:
            return apology("don't forget the cents", 400)
        if len(request.form.get("cash").rsplit('.')[1]) != 2:
            return apology("don't forget the cents", 400)
        
        # Get user info
        user_id = (session["user_id"],)
        user = db.execute("SELECT * FROM users WHERE id =?", user_id).fetchone()
        
        cash_current = user[3]
        
        # update user cash
        new_cash = (cash_current + float(request.form.get("cash")), session["user_id"])
        db.execute("UPDATE users SET cash = ? WHERE id =?", new_cash)
        connection.commit()
        
        # Redirect user to home page
        flash("Wow you're rich!")
        return redirect("/")
    # User reached route via GET
    else:
        return render_template("cash.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Use lookup to get values for stock (name, price, symbol)
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("unable to find stock", 400)
        price = stock["price"]

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("must provide shares", 400)
        # Ensure shares is numeric
        if not request.form.get("shares").isnumeric():
            return apology("invalid shares", 400)
        # Ensure shares is positive and non zero
        if float(request.form.get("shares")) < 1:
            return apology("invalid shares", 400)
        # Ensure shares is an integer
        if float(request.form.get("shares")) % 1 != 0:
            return apology("invalid shares", 400)
        
        # Get user info
        user_id = (session["user_id"],)
        user = db.execute("SELECT * FROM users WHERE id =?", user_id).fetchone()
        cash = user[3]

        # Check that user has enough cash to complete purchase
        cost = price * int(request.form.get("shares"))
        if cost > cash:
            return apology("not enough cash", 400)

        # complete purchase
        else:
            # Update database for new purchase
            # Take away cost from cash
            new_cash = (cash - cost, session["user_id"])
            db.execute("UPDATE users SET cash = ? WHERE id =?", new_cash)
            connection.commit()
            # record purchase
            new_purchase = (session["user_id"], stock["symbol"], stock["price"], int(request.form.get("shares")))
            db.execute("INSERT INTO transactions (user_id, symbol, price, shares) VALUES(?, ?, ?, ?)", new_purchase)
            connection.commit()

            # Update account
            # Check if stock is currently owned
            check_stock = (session["user_id"], request.form.get("symbol"))
            current = db.execute("SELECT * FROM accounts WHERE user_id =? AND symbol =?", check_stock).fetchone()
            current_length = db.execute("SELECT COUNT(1) FROM accounts WHERE user_id =? AND symbol =?", check_stock).fetchone()[0]
            # None owned yet
            if current_length == 0:
                new_stock = (session["user_id"], request.form.get("symbol"), request.form.get("shares"))
                db.execute("INSERT INTO accounts (user_id, symbol, shares) VALUES(?, ?, ?)", new_stock)
                connection.commit()
            # Already owned so update shares
            else:
                update_stock = (current[2] + int(request.form.get("shares")), session["user_id"], request.form.get("symbol"))
                db.execute("UPDATE accounts SET shares = ? WHERE user_id =? AND symbol =?", update_stock)
                connection.commit()

        # Redirect user to home page
        flash("Bought!")
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = (session["user_id"],)

    transactions_data = db.execute("SELECT * FROM transactions WHERE user_id =?", user_id).fetchall()

    # get stock name, price and calculate totals
    n = 0
    transactions = []
    for transaction in transactions_data:
        transactions.append({})
        # lookup stock data
        transactions[n]["symbol"] = transaction[2]
        transactions[n]["price"] = transaction[3]
        transactions[n]["shares"] = transaction[4]
        transactions[n]["time"] = transaction[5]
        n += 1
    
    return render_template("history.html", transactions=transactions)


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
        username = (request.form.get("username"),)
        rows = db.execute("SELECT * FROM users WHERE username = ?", username).fetchone()
        rows_length = db.execute("SELECT COUNT(1) FROM users WHERE username = ?", username).fetchone()

        # Ensure username exists and password is correct
        if rows_length[0] != 1 or not check_password_hash(rows[2], request.form.get("password")):
            return apology("invalid username and/or password", 403)


        # Remember which user has logged in
        session["user_id"] = rows[0]

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
    # User reached route via POST (submitted a stock)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Use lookup to get values for stock (name, price, symbol)
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("unable to find stock", 400)

        return render_template("quoted.html", stock=stock)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure username does not already exist
        # Query database for username
        username = (request.form.get("username"),)
        # Should return nothing if username doesn't exist
        rows_length = db.execute("SELECT COUNT(1) FROM users WHERE username = ?", username).fetchone()[0]
        if rows_length != 0:
            return apology("username already exists", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password", 400)

        # Ensure password and confirmation are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        username = request.form.get("username")
        hash_password = generate_password_hash(request.form.get("password"))

        # Insert new user into database, hashing the password
        new_user = (username, hash_password)
        db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", new_user)
        connection.commit()

        # return the user to the login page
        return render_template("login.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Ensure user submitted a symbol
        if not request.form.get("symbol"):
            return apology("select a symbol", 400)

        # Ensure user has shares of this symbol
        check_symbol = (session["user_id"], request.form.get("symbol"))
        shares = db.execute("SELECT shares FROM accounts WHERE user_id =? AND symbol =?", check_symbol).fetchone()
        shares = shares[0]
        if shares < 1:
            return apology("you have no shares of this stock", 400)

        # Ensure user inputs a positive number of shares
        if not request.form.get("shares"):
            return apology("input number of shares", 400)
        # Ensure shares is numeric
        if not request.form.get("shares").isnumeric():
            return apology("invalid shares", 400)
        shares_sell = int(request.form.get("shares"))
        if shares_sell < 1:
            return apology("invalid number of shares", 400)
        # Ensure user inputs an integer
        if float(request.form.get("shares")) % 1 != 0:
            return apology("invalid shares", 400)
        
        # Ensure user has enough shares to sell
        if shares_sell > shares:
            return apology("you do not have enough shares to sell", 400)

        # Use lookup to get values for stock (name, price, symbol)
        
        if not lookup(request.form.get("symbol")):
            return apology("unable to find stock", 400)
        stock = lookup(request.form.get("symbol"))
        price = stock["price"]

        cost = price * shares_sell
        # Get user info
        user_id = (session["user_id"],)
        user = db.execute("SELECT * FROM users WHERE id =?", user_id).fetchone()
        cash = user[3]

        # complete sale
        
        # Update database for new sale
        # Add on cost to cash
        update_cash = (cash + cost, session["user_id"])
        db.execute("UPDATE users SET cash = ? WHERE id =?", update_cash)
        connection.commit()
        # record purchase
        new_purchase = (session["user_id"], stock["symbol"], stock["price"], 0 - int(request.form.get("shares")))
        db.execute("INSERT INTO transactions (user_id, symbol, price, shares) VALUES(?, ?, ?, ?)", new_purchase)
        connection.commit()

        # Update account
        # Remove if shares is now 0
        if shares_sell == shares:
            update_shares = (session["user_id"], request.form.get("symbol"))
            db.execute("DELETE FROM accounts WHERE user_id =? AND symbol =?", update_shares)
            connection.commit()

        # Update shares if none 0
        else:
            update_shares = (shares - shares_sell, session["user_id"], request.form.get("symbol"))
            db.execute("UPDATE accounts SET shares = ? WHERE user_id =? AND symbol =?", update_shares)
            connection.commit()

        # Redirect user to home page
        flash("Sold!")
        return redirect("/")

    else:
        user_id = (session["user_id"],)
        accounts_data = db.execute("SELECT * FROM accounts WHERE user_id = ?", user_id).fetchall()
        total = 0

        # get stock name, price and calculate totals
        n = 0
        accounts = []
        for account in accounts_data:
            accounts.append({})
            accounts[n]["symbol"] = account[1]
            n += 1

        return render_template("sell.html", accounts=accounts)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
