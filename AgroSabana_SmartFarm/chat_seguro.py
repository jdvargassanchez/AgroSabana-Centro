"""
chat_seguro.py  ·  AgroSabana
- Cifrado real con Fernet (AES-128-CBC + firma HMAC-SHA256)
- Chat sincrónico por polling (cliente <-> agente)
- Panel del agente protegido con token de administrador
"""
import os
import re
import secrets
from base64 import b64decode

from cryptography.fernet import Fernet
from flask import jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFIJO_V2 = "AGRO_SECURE_V2_"   # Fernet (real)
PREFIJO_V1 = "AGRO_SECURE_V1_"   # Base64 (registros viejos)
SESION_RE = re.compile(r'^[A-Za-z0-9\-]{8,64}$')



# CLAVES
def _cargar_o_crear(env_name, archivo, generador):
    valor = os.environ.get(env_name)
    if valor:
        return valor.strip()
    ruta = os.path.join(BASE_DIR, archivo)
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as f:
            return f.read().strip()
    valor = generador()
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(valor)
    print(f"🔑 Se creó {archivo}. Guárdalo y NO lo subas a internet/GitHub.")
    return valor


CLAVE_CIFRADO = _cargar_o_crear('AGRO_CLAVE_CIFRADO', 'clave_cifrado.key',
                                lambda: Fernet.generate_key().decode())
ADMIN_TOKEN = _cargar_o_crear('AGRO_ADMIN_TOKEN', 'admin_token.txt',
                              lambda: secrets.token_urlsafe(16))
fernet = Fernet(CLAVE_CIFRADO.encode())


def cifrar_mensaje(texto):
    if not texto:
        return ""
    return PREFIJO_V2 + fernet.encrypt(texto.encode('utf-8')).decode('utf-8')


def descifrar_mensaje(trama):
    try:
        if not trama:
            return ""
        if trama.startswith(PREFIJO_V2):
            return fernet.decrypt(trama[len(PREFIJO_V2):].encode()).decode('utf-8')
        if trama.startswith(PREFIJO_V1):
            return b64decode(trama[len(PREFIJO_V1):].encode()).decode('utf-8')
        return trama
    except Exception:
        return "[Error de descifrado]"


def es_admin():
    token = request.headers.get('X-Admin-Token') or request.args.get('token') or ''
    return bool(token) and secrets.compare_digest(token.encode('utf-8'),
                                                  ADMIN_TOKEN.encode('utf-8'))


def _fmt(f):
    return f.strftime('%Y-%m-%d %H:%M:%S') if hasattr(f, 'strftime') else str(f)[:19]

# TABLA DEL CHAT

def crear_tablas(get_db_connection):
    conn, motor = get_db_connection()
    try:
        cur = conn.cursor()
        if motor == 'sqlserver':
            cur.execute("""
                IF OBJECT_ID(N'dbo.Chat_Mensajes', N'U') IS NULL
                CREATE TABLE dbo.Chat_Mensajes (
                    id_mensaje      INT IDENTITY(1,1) PRIMARY KEY,
                    sesion_id       NVARCHAR(64)  NOT NULL,
                    emisor          NVARCHAR(10)  NOT NULL,
                    mensaje_cifrado NVARCHAR(MAX) NOT NULL,
                    fecha           DATETIME      NOT NULL DEFAULT GETDATE()
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Chat_Mensajes (
                    id_mensaje INTEGER PRIMARY KEY AUTOINCREMENT,
                    sesion_id TEXT NOT NULL,
                    emisor TEXT NOT NULL,
                    mensaje_cifrado TEXT NOT NULL,
                    fecha TEXT DEFAULT (datetime('now','localtime'))
                )
            """)
        conn.commit()
    finally:
        conn.close()



def registrar_chat(app, get_db_connection):
    try:
        crear_tablas(get_db_connection)
    except Exception as e:
        print("❌ No se pudo crear la tabla Chat_Mensajes:", e)

    def insertar(sesion, emisor, texto):
        conn, _ = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO Chat_Mensajes (sesion_id, emisor, mensaje_cifrado) VALUES (?, ?, ?)",
                (sesion, emisor, cifrar_mensaje(texto)))
            conn.commit()
        finally:
            conn.close()

    @app.route('/api/chat/enviar', methods=['POST'])
    def chat_enviar():
        data = request.get_json(silent=True) or {}
        sesion = str(data.get('sesion_id', ''))
        texto = str(data.get('mensaje', '')).strip()
        if not SESION_RE.match(sesion) or not texto or len(texto) > 1000:
            return jsonify({'error': 'Datos inválidos'}), 400
        try:
            insertar(sesion, 'cliente', texto)
            return jsonify({'status': 'ok'}), 201
        except Exception as e:
            print("❌ chat_enviar:", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/chat/mensajes')
    def chat_mensajes():
        sesion = request.args.get('sesion_id', '')
        if not SESION_RE.match(sesion):
            return jsonify([]), 400
        try:
            desde = int(request.args.get('desde', 0))
        except ValueError:
            desde = 0
        try:
            conn, _ = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT id_mensaje, emisor, mensaje_cifrado, fecha
                FROM Chat_Mensajes
                WHERE sesion_id = ? AND id_mensaje > ?
                ORDER BY id_mensaje
            """, (sesion, desde))
            filas = cur.fetchall()
            conn.close()
            return jsonify([{
                'id': f[0], 'emisor': f[1],
                'texto': descifrar_mensaje(f[2]), 'fecha': _fmt(f[3])
            } for f in filas])
        except Exception as e:
            print("❌ chat_mensajes:", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/chat/responder', methods=['POST'])
    def chat_responder():
        if not es_admin():
            return jsonify({'error': 'No autorizado'}), 401
        data = request.get_json(silent=True) or {}
        sesion = str(data.get('sesion_id', ''))
        texto = str(data.get('mensaje', '')).strip()
        if not SESION_RE.match(sesion) or not texto or len(texto) > 1000:
            return jsonify({'error': 'Datos inválidos'}), 400
        try:
            insertar(sesion, 'agente', texto)
            return jsonify({'status': 'ok'}), 201
        except Exception as e:
            print("❌ chat_responder:", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/chat/conversaciones')
    def chat_conversaciones():
        if not es_admin():
            return jsonify({'error': 'No autorizado'}), 401
        try:
            conn, _ = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT sesion_id, MAX(id_mensaje) AS ultimo
                FROM Chat_Mensajes
                GROUP BY sesion_id
                ORDER BY ultimo DESC
            """)
            ultimos = cur.fetchall()
            resultado = []
            for sesion, ultimo in ultimos[:50]:
                cur.execute("""
                    SELECT emisor, mensaje_cifrado, fecha
                    FROM Chat_Mensajes WHERE id_mensaje = ?
                """, (ultimo,))
                emisor, cifrado, fecha = cur.fetchone()
                resultado.append({
                    'sesion_id': sesion,
                    'ultimo_emisor': emisor,
                    'ultimo_texto': descifrar_mensaje(cifrado),
                    'fecha': _fmt(fecha)
                })
            conn.close()
            return jsonify(resultado)
        except Exception as e:
            print("❌ chat_conversaciones:", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/agente')
    def agente():
        return render_template('agente.html')

    print("\n💬 Chat sincrónico listo.")
    print("   Panel del agente : http://localhost:5000/agente")
    print(f"   Token de acceso  : {ADMIN_TOKEN}\n")
