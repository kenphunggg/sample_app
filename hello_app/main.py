from flask import Flask
import os

app = Flask(__name__)

# Renamed this function to 'home'
@app.route('/')
def home():
   hostname = os.getenv('NODE_NAME', 'unknown')
   username = os.getenv('USER_NAME', 'unknown')
   return f'Hello from {username} | {hostname}\n'

# Renamed this function to 'get_nodename'
@app.route('/nodename')
def get_nodename():
   hostname = os.getenv('NODE_NAME', 'unknown')
   return f'{hostname}\n'

if __name__ == '__main__':
   app.run(host="0.0.0.0", port=5000)