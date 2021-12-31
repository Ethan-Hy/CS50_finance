# CS50: Finance - Ethan Hy
#### Description:
https://cs50.harvard.edu/x/2021/psets/9/finance/

This is my implementation of the problem set finance for CS50 where we implement a website to create an account, log in, buy and sell stocks. An initial skeleton for the website is first provided but the rest is my own implementation.

The tech stack used is Python, Flask, Jinja, sqlight3, html, CSS.
Instead of using the CS50 package I am using sqlight3 and this website will use flask to run locally.

#### Requirements:
Python, Flask, Flask-Session, requests


#### Instructions for Use:
First obtain an IEX API from https://iexcloud.io/console/tokens (with an account).

Go to the CS50_finance directory.

Set the environment variable API_KEY=YOUR API KEY. e.g. on Windows use: `set API_KEY=123456789`.

Install requirements: `pip install -r requirements.txt`

Start Flask's built-in web sever: `flask run`

Copy and paste the link into a web browser.
