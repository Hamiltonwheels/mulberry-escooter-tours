import os
from flask import Flask
from config import Config
from models import db

def create_app():
          app = Flask(__name__)
          app.config.from_object(Config)
          db.init_app(app)
          with app.app_context():
                        db.create_all()
                    @app.route('/')
    def index():
                  return '>h1>Mulberry E-Scooter Tours>/h1>>p>Site is live! Full version coming soon.>/p>'
              @app.route('/health')
    def health():
                  return 'OK', 200
              return app

app = create_app()

if __name__ == '__main__':
          app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
