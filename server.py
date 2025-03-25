from flask import Flask, render_template+


app = Flask(__name__)
app.secret_key = "1234456789"

########################################
# Routes des pages principales du site #
########################################

@app.get("/")
def home():
    # print("Sessions dans home:", session)
    return render_template("index.html")