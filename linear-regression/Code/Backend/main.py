import os

from flask_cors import CORS
from app import create_app

# Cargar variables de entorno desde .env si existe (sin pisar las ya definidas).
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = create_app()
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
CORS(app, resources={r"/*": {"origins": "*"}})

if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes", "on")
    app.run(host=host, port=port, debug=debug)
