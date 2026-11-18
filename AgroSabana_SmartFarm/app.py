from datetime import datetime
import math
import os
import random
import socket
import sqlite3
from flask import Flask, jsonify, render_template, request
from chat_seguro import registrar_chat, cifrar_mensaje, descifrar_mensaje, es_admin


try:
    import pyodbc
    TIENE_PYODBC = True
except ImportError:
    TIENE_PYODBC = False

app = Flask(__name__)

MENSAJE_BLOQUEADO = "🔒 Contenido cifrado: solo visible para personal autorizado"

# =========================================================================
# GESTIÓN DE CONEXIÓN A BASE DE DATOS (SQL SERVER + RESPALDO SQLITE)
# =========================================================================
NOMBRE_BD = "AgroSabanaDB"

_CONN_STR_OK = None
_ULTIMO_ERROR_SQL = None


def _detectar_driver():
    """Elige el mejor driver ODBC de SQL Server instalado en el equipo."""
    if not TIENE_PYODBC:
        return None
    instalados = pyodbc.drivers()
    preferidos = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    for d in preferidos:
        if d in instalados:
            return d
    return None


def _servidores_candidatos():
    """Lista de servidores a probar, en orden. Puedes forzar uno con la
    variable de entorno AGRO_SQL_SERVER (ej. 'ASUS_doncel' o 'localhost')."""
    candidatos = []
    forzado = os.environ.get("AGRO_SQL_SERVER")
    if forzado:
        candidatos.append(forzado)
    candidatos += [
        "localhost",                 
        ".",
        "(local)",
        socket.gethostname(),        
        "localhost\\SQLEXPRESS",     
    ]
   
    vistos, unicos = set(), []
    for s in candidatos:
        if s not in vistos:
            vistos.add(s)
            unicos.append(s)
    return unicos


def _conectar_sqlserver():
    """Intenta conectar a SQL Server. Devuelve la conexión o None."""
    global _CONN_STR_OK, _ULTIMO_ERROR_SQL

    if not TIENE_PYODBC:
        _ULTIMO_ERROR_SQL = "pyodbc no está instalado (pip install pyodbc)"
        print("⚠️ ", _ULTIMO_ERROR_SQL)
        return None

    if _CONN_STR_OK:
        try:
            return pyodbc.connect(_CONN_STR_OK)
        except Exception as e:
            print("⚠️ La conexión guardada dejó de funcionar:", e)
            _CONN_STR_OK = None

    driver = _detectar_driver()
    if not driver:
        _ULTIMO_ERROR_SQL = (
            "No hay driver ODBC de SQL Server. Drivers encontrados: "
            + str(pyodbc.drivers())
        )
        print("⚠️ ", _ULTIMO_ERROR_SQL)
        return None

    # 2) Probar cada servidor candidato
    errores = []
    for servidor in _servidores_candidatos():
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={servidor};"
            f"DATABASE={NOMBRE_BD};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
            "Connection Timeout=3;"
        )
        try:
            conn = pyodbc.connect(conn_str)
            _CONN_STR_OK = conn_str
            _ULTIMO_ERROR_SQL = None
            print(f"✅ Conectado a SQL Server → servidor: {servidor} | driver: {driver}")
            return conn
        except Exception as e:
            errores.append(f"[{servidor}] {e}")

    _ULTIMO_ERROR_SQL = " | ".join(errores)
    print("⚠️ No se pudo conectar a SQL Server. Intentos:")
    for err in errores:
        print("   -", err)
    return None


def get_db_connection():
    """Conecta a SQL Server; si falla, usa SQLite local como respaldo
    (y lo avisa claramente en la consola)."""
    conn = _conectar_sqlserver()
    if conn is not None:
        return conn, 'sqlserver'

    print("⚠️ USANDO RESPALDO SQLITE (agrosabana_backup.db). "
          "Los datos NO se están guardando en SQL Server.")

    conn = sqlite3.connect('agrosabana_backup.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Mensajes_Tickets (
            id_ticket INTEGER PRIMARY KEY AUTOINCREMENT,
            canal TEXT NOT NULL,
            nombre_remitente TEXT NOT NULL,
            municipio TEXT NOT NULL,
            codigo_torre TEXT,
            asunto TEXT NOT NULL,
            mensaje_cifrado TEXT NOT NULL,
            fecha_registro TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Resenas_Comunidad (
            id_resena INTEGER PRIMARY KEY AUTOINCREMENT,
            estrellas INTEGER NOT NULL,
            nombre_agricultor TEXT NOT NULL,
            finca_cultivo TEXT NOT NULL,
            comentario TEXT NOT NULL,
            fecha_publicacion TEXT DEFAULT (date('now', 'localtime'))
        )
    """)
    conn.commit()
    return conn, 'sqlite'


@app.route('/api/estado-db')
def estado_db():
    """Diagnóstico (solo admin): http://localhost:5000/api/estado-db?token=TU_TOKEN"""
    if not es_admin():
        return jsonify({'error': 'No autorizado. Usa ?token=TU_TOKEN_ADMIN'}), 401

    conn, motor = get_db_connection()
    info = {
        'motor_activo': motor,
        'pyodbc_instalado': TIENE_PYODBC,
        'drivers_odbc': pyodbc.drivers() if TIENE_PYODBC else [],
        'driver_elegido': _detectar_driver(),
        'ultimo_error_sqlserver': _ULTIMO_ERROR_SQL,
    }
    if motor == 'sqlserver':
        cur = conn.cursor()
        cur.execute("SELECT @@SERVERNAME, DB_NAME()")
        fila = cur.fetchone()
        info['servidor'] = fila[0]
        info['base_de_datos'] = fila[1]
        cur.execute("SELECT COUNT(*) FROM dbo.Mensajes_Tickets")
        info['total_tickets'] = cur.fetchone()[0]
    conn.close()
    return jsonify(info)

# =========================================================================
# CATÁLOGO CENTRALIZADO DE TORRES AGROCLIMÁTICAS (SABANA CENTRO)
# =========================================================================
TORRES_AGRO = [
    {
        "id": "TR-SOPO-CHU-01",
        "municipio": "Sopó",
        "vereda": "Chuscal",
        "finca": "Finca San Rafael",
        "agricultor": "Don Carlos Mendoza",
        "telefono_alerta": "+57 311 482 9012",
        "cultivo": "Hortalizas de Hoja (Lechuga y Espinaca)",
        "etapa": "Crecimiento Vegetativo",
        "hectareas": 4.5,
        "suelo": "Franco-Arcilloso",
        "lat": 4.912300,
        "lon": -73.945100,
        "altitud": 2580,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + Pluviómetro + LDR",
        "base": {"temp": 16.8, "humA": 74.0, "humS": 62.0, "lum": 78.0, "prec": 12.0, "et0": 2.4}
    },
    {
        "id": "TR-SOPO-MER-02",
        "municipio": "Sopó",
        "vereda": "Mercenario",
        "finca": "Hacienda El Mercenario",
        "agricultor": "Sra. Lucía Gómez",
        "telefono_alerta": "+57 314 290 1184",
        "cultivo": "Maíz Amarillo Tecnificado",
        "etapa": "Floración",
        "hectareas": 12.0,
        "suelo": "Orgánico Profundo",
        "lat": 4.901120,
        "lon": -73.952300,
        "altitud": 2570,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Sonda Suelo + Pluviómetro",
        "base": {"temp": 17.4, "humA": 71.0, "humS": 58.0, "lum": 82.0, "prec": 8.0, "et0": 2.7}
    },
    {
        "id": "TR-SOPO-MEU-03",
        "municipio": "Sopó",
        "vereda": "Meusa",
        "finca": "Ganadería La Pradera de Meusa",
        "agricultor": "Ing. Jorge Alberto Ruiz",
        "telefono_alerta": "+57 320 845 3319",
        "cultivo": "Pastos Kikuyo y Raygrass (Lechería)",
        "etapa": "Rotación de Potreros",
        "hectareas": 28.0,
        "suelo": "Franco",
        "lat": 4.938900,
        "lon": -73.910200,
        "altitud": 2600,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + Anemómetro",
        "base": {"temp": 16.2, "humA": 76.0, "humS": 66.0, "lum": 75.0, "prec": 15.0, "et0": 2.2}
    },
    {
        "id": "TR-CHIA-YER-01",
        "municipio": "Chía",
        "vereda": "Yerbabuena",
        "finca": "Invernaderos Santa Elena",
        "agricultor": "Familia Cárdenas Nieto",
        "telefono_alerta": "+57 310 554 7820",
        "cultivo": "Flores de Exportación (Rosa y Clavel)",
        "etapa": "Corte y Cosecha",
        "hectareas": 6.2,
        "suelo": "Franco-Arenoso",
        "lat": 4.882100,
        "lon": -74.021500,
        "altitud": 2565,
        "energia": "Red Agrícola 110V + Respaldo UPS",
        "sensores": "ESP32 + DHT22 + Sonda Suelo + Radiación PAR",
        "base": {"temp": 19.2, "humA": 64.0, "humS": 54.0, "lum": 86.0, "prec": 5.0, "et0": 3.1}
    },
    {
        "id": "TR-CHIA-FAG-02",
        "municipio": "Chía",
        "vereda": "Fagua",
        "finca": "Parcela Agroecológica El Roble",
        "agricultor": "Don Álvaro Prieto",
        "telefono_alerta": "+57 313 771 0943",
        "cultivo": "Acelga, Brócoli y Cilantro",
        "etapa": "Desarrollo de Cabeza",
        "hectareas": 3.0,
        "suelo": "Franco-Limoso",
        "lat": 4.868500,
        "lon": -74.048200,
        "altitud": 2562,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + Pluviómetro",
        "base": {"temp": 18.5, "humA": 68.0, "humS": 60.0, "lum": 84.0, "prec": 6.0, "et0": 2.9}
    },
    {
        "id": "TR-CAJI-CAP-01",
        "municipio": "Cajicá",
        "vereda": "Capellanía",
        "finca": "Cultivos Berries de la Sabana",
        "agricultor": "Sra. Martha Isabel León",
        "telefono_alerta": "+57 315 629 4410",
        "cultivo": "Fresa Albion y Frambuesa",
        "etapa": "Fructificación",
        "hectareas": 5.0,
        "suelo": "Franco-Limoso",
        "lat": 4.918000,
        "lon": -74.032000,
        "altitud": 2558,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Sonda Suelo + Pluviómetro",
        "base": {"temp": 18.0, "humA": 69.0, "humS": 63.0, "lum": 81.0, "prec": 9.0, "et0": 2.8}
    },
    {
        "id": "TR-ZIPA-JOR-01",
        "municipio": "Zipaquirá",
        "vereda": "San Jorge",
        "finca": "Predio El Páramo de San Jorge",
        "agricultor": "Don Hernando Torres",
        "telefono_alerta": "+57 312 908 6531",
        "cultivo": "Papa Sabanera y Criolla",
        "etapa": "Tuberización",
        "hectareas": 15.0,
        "suelo": "Andisol Franco",
        "lat": 5.031200,
        "lon": -73.998100,
        "altitud": 2720,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Sensor Heladas + Humedad Suelo",
        "base": {"temp": 13.8, "humA": 82.0, "humS": 72.0, "lum": 68.0, "prec": 22.0, "et0": 1.9}
    },
    {
        "id": "TR-ZIPA-RIO-02",
        "municipio": "Zipaquirá",
        "vereda": "Río Frío",
        "finca": "Hacienda Lechera Río Frío",
        "agricultor": "Don Gustavo Salgado",
        "telefono_alerta": "+57 318 340 1298",
        "cultivo": "Pastos de Corte y Avena Forrajera",
        "etapa": "Pre-corte",
        "hectareas": 22.0,
        "suelo": "Franco-Arcilloso",
        "lat": 5.012400,
        "lon": -74.025100,
        "altitud": 2630,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + Pluviómetro",
        "base": {"temp": 15.1, "humA": 79.0, "humS": 68.0, "lum": 72.0, "prec": 18.0, "et0": 2.1}
    },
    {
        "id": "TR-TOCA-ESM-01",
        "municipio": "Tocancipá",
        "vereda": "La Esmeralda",
        "finca": "Agropecuaria La Esmeralda",
        "agricultor": "Don Pedro Pablo Rodríguez",
        "telefono_alerta": "+57 311 209 8745",
        "cultivo": "Maíz Forrajero y Arveja Verde",
        "etapa": "Llenado de Vaina",
        "hectareas": 9.5,
        "suelo": "Franco-Arcilloso",
        "lat": 4.965000,
        "lon": -73.945000,
        "altitud": 2600,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + LDR",
        "base": {"temp": 17.1, "humA": 70.0, "humS": 56.0, "lum": 80.0, "prec": 10.0, "et0": 2.6}
    },
    {
        "id": "TR-GACH-ROB-01",
        "municipio": "Gachancipá",
        "vereda": "Roble Centro",
        "finca": "Finca Los Cerezos",
        "agricultor": "Sra. Blanca Inés Mora",
        "telefono_alerta": "+57 316 492 7103",
        "cultivo": "Zanahoria y Remolacha",
        "etapa": "Engrosamiento de Raíz",
        "hectareas": 7.0,
        "suelo": "Franco-Arenoso",
        "lat": 4.991200,
        "lon": -73.872500,
        "altitud": 2568,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Sonda Suelo + Pluviómetro",
        "base": {"temp": 16.5, "humA": 73.0, "humS": 61.0, "lum": 79.0, "prec": 11.0, "et0": 2.5}
    },
    {
        "id": "TR-NEMO-MIN-01",
        "municipio": "Nemocón",
        "vereda": "Patio Bonito",
        "finca": "Granja Integral El Salitre",
        "agricultor": "Don Luis Eduardo Buitrago",
        "telefono_alerta": "+57 314 812 5509",
        "cultivo": "Cebada, Trigo y Pasto Azul",
        "etapa": "Espigado",
        "hectareas": 18.0,
        "suelo": "Franco",
        "lat": 5.066000,
        "lon": -73.876000,
        "altitud": 2610,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Capacitivo Suelo + Pluviómetro",
        "base": {"temp": 15.8, "humA": 72.0, "humS": 52.0, "lum": 83.0, "prec": 7.0, "et0": 2.6}
    },
    {
        "id": "TR-COGU-SUS-01",
        "municipio": "Cogua",
        "vereda": "Susaguá",
        "finca": "Hacienda Mirador del Neusa",
        "agricultor": "Familia Pachón Herrera",
        "telefono_alerta": "+57 321 903 4421",
        "cultivo": "Papa Pastusa Suprema",
        "etapa": "Floración",
        "hectareas": 11.5,
        "suelo": "Andisol Volcánico",
        "lat": 5.061500,
        "lon": -73.981000,
        "altitud": 2690,
        "energia": "Panel Solar 50W + LiFePO4",
        "sensores": "ESP32 + DHT22 + Sensor Heladas + Humedad Suelo",
        "base": {"temp": 14.2, "humA": 81.0, "humS": 70.0, "lum": 70.0, "prec": 20.0, "et0": 2.0}
    }
]

# =========================================================================
# RUTAS DE VISTAS HTML (PLANTILLAS JINJA2)
# =========================================================================
@app.route('/')
def dashboard():
    return render_template('dashboard.html', active_page='dashboard', torres=TORRES_AGRO)

@app.route('/torres')
def torres():
    return render_template('torres.html', active_page='torres', torres=TORRES_AGRO)

@app.route('/app-movil')
def app_movil():
    return render_template('app_movil.html', active_page='app_movil', torres=TORRES_AGRO)

@app.route('/documentacion')
def documentacion():
    return render_template('documentacion.html', active_page='documentacion')

@app.route('/contacto')
def contacto():
    return render_template('soporte_comunidad.html', active_page='contacto')

@app.route('/powerbi')
def powerbi():
    return render_template('DashBoard_PowerBi.html', active_page='powerbi')

@app.route('/visualizacion-registros')
def visualizacion_registros():
    return render_template('visualizacion_registros.html', active_page='visualizacion_registros')

@app.route('/agente')
def panel_agente():
    return render_template('agente.html')

# =========================================================================
# API DE TELEMETRÍA EN TIEMPO REAL
# =========================================================================
@app.route('/api/telemetria')
def api_telemetria():
    torre_id = request.args.get('torre_id', 'TODAS')
    municipio = request.args.get('municipio', 'TODOS')
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lecturas = []
    for t in TORRES_AGRO:
        if torre_id != 'TODAS' and t['id'] != torre_id:
            continue
        if municipio != 'TODOS' and t['municipio'] != municipio:
            continue

        b = t['base']
        temp = round(max(2.0, min(32.0, b['temp'] + random.uniform(-1.1, 1.1))), 1)
        hum_aire = round(max(30.0, min(99.0, b['humA'] + random.uniform(-2.5, 2.5))), 1)
        hum_suelo = round(max(18.0, min(95.0, b['humS'] + random.uniform(-2.0, 2.0))), 1)
        lum = round(max(10.0, min(100.0, b['lum'] + random.uniform(-4.0, 4.0))), 1)
        prec = round(max(0.0, min(100.0, b['prec'] + random.uniform(-3.0, 8.0 if random.random() < 0.15 else 2.0))), 1)
        et0 = round(max(0.8, b['et0'] + random.uniform(-0.2, 0.2)), 2)

        if temp <= 5.5:
            estado = "RIESGO HELADA"
            nivel = "critico"
            recomendacion = "Activar riego por aspersión antihelada o cobertura térmica nocturna."
        elif hum_suelo < 35.0:
            estado = "DEFICIT HIDRICO"
            nivel = "alerta"
            recomendacion = "Programar pulso de riego de 25 min en el lote para evitar estrés radicular."
        elif prec > 55.0:
            estado = "LLUVIA INTENSA"
            nivel = "lluvia"
            recomendacion = "Suspender fertirriego programado y verificar drenajes superficiales."
        else:
            estado = "OPTIMO AGRO"
            nivel = "optimo"
            recomendacion = "Condiciones microclimáticas estables para desarrollo fenológico."

        lecturas.append({
            "id": t["id"],
            "municipio": t["municipio"],
            "vereda": t["vereda"],
            "finca": t["finca"],
            "agricultor": t["agricultor"],
            "cultivo": t["cultivo"],
            "etapa": t["etapa"],
            "temperatura": temp,
            "humedad_aire": hum_aire,
            "humedad_suelo": hum_suelo,
            "luminosidad": lum,
            "precipitacion": prec,
            "evapotranspiracion": et0,
            "estado": estado,
            "nivel": nivel,
            "recomendacion": recomendacion,
            "hora": ahora
        })

    return jsonify({
        "timestamp": ahora,
        "total_estaciones": len(lecturas),
        "lecturas": lecturas
    })

# =========================================================================
# API DE TICKETS ASINCRÓNICOS (SOPORTE_COMUNIDAD.HTML)
# El chat sincrónico vive en chat_seguro.py (/api/chat/...) y el panel del
# agente en /agente.
# =========================================================================
@app.route('/api/guardar-ticket', methods=['POST'])
def guardar_ticket():
    try:
        data = request.get_json(silent=True) or {}
        for campo in ('canal', 'nombre', 'municipio', 'asunto'):
            if not str(data.get(campo, '')).strip():
                return jsonify({'error': f'Falta el campo: {campo}'}), 400

        msg_cifrado = cifrar_mensaje(str(data.get('mensaje', '')))
        torre = str(data.get('torre', '')).strip() or 'No especificada'

        conn, motor = get_db_connection()
        cursor = conn.cursor()

        if motor == 'sqlserver':
            cursor.execute("""
                INSERT INTO dbo.Mensajes_Tickets (canal, nombre_remitente, municipio, codigo_torre, asunto, mensaje_cifrado)
                OUTPUT INSERTED.id_ticket
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['canal'], data['nombre'], data['municipio'], torre, data['asunto'], msg_cifrado))
            nuevo_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO Mensajes_Tickets (canal, nombre_remitente, municipio, codigo_torre, asunto, mensaje_cifrado)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['canal'], data['nombre'], data['municipio'], torre, data['asunto'], msg_cifrado))
            nuevo_id = cursor.lastrowid

        conn.commit()
        conn.close()
        print(f"🎫 Ticket #{nuevo_id} guardado en: {motor}")
        return jsonify({
            'id_ticket': nuevo_id,
            'motor': motor,
            'hash_muestra': msg_cifrado[:34] + '...'
        }), 201
    except Exception as e:
        print("❌ Error en guardar_ticket:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/obtener-tickets', methods=['GET'])
def obtener_tickets():
    try:
        admin = es_admin()   # solo el personal autorizado ve el texto descifrado

        conn, motor = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_ticket, canal, nombre_remitente, municipio, codigo_torre, asunto, mensaje_cifrado, fecha_registro
            FROM Mensajes_Tickets
            ORDER BY id_ticket DESC
        """)
        filas = cursor.fetchall()
        conn.close()

        tickets = []
        for f in filas:
            fecha_str = f[7].strftime('%Y-%m-%d %H:%M') if hasattr(f[7], 'strftime') else str(f[7])[:16]
            tickets.append({
                'id': f[0],
                'canal': f[1],
                'nombre': f[2],
                'municipio': f[3],
                'torre': f[4],
                'asunto': f[5],
                'mensaje_descifrado': descifrar_mensaje(f[6]) if admin else MENSAJE_BLOQUEADO,
                'mensaje_cifrado_sql': f[6][:32] + '...',
                'fecha': fecha_str
            })
        return jsonify(tickets)
    except Exception as e:
        print("❌ Error en obtener_tickets:", e)
        return jsonify({'error': str(e)}), 500

# =========================================================================
# API DE CALIFICACIONES Y RESEÑAS DE LA COMUNIDAD
# =========================================================================
@app.route('/api/guardar-resena', methods=['POST'])
def guardar_resena():
    try:
        data = request.get_json(silent=True) or {}
        estrellas = int(data.get('estrellas', 5))
        if not 1 <= estrellas <= 5:
            return jsonify({'error': 'Las estrellas deben ir de 1 a 5'}), 400

        conn, _ = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Resenas_Comunidad (estrellas, nombre_agricultor, finca_cultivo, comentario)
            VALUES (?, ?, ?, ?)
        """, (estrellas, data['nombre'], data['finca'], data['comentario']))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'}), 201
    except Exception as e:
        print("❌ Error en guardar_resena:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/obtener-resenas', methods=['GET'])
def obtener_resenas():
    try:
        conn, _ = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT estrellas, nombre_agricultor, finca_cultivo, comentario, fecha_publicacion
            FROM Resenas_Comunidad
            ORDER BY id_resena DESC
        """)
        filas = cursor.fetchall()
        conn.close()

        resenas = []
        for f in filas:
            fecha_str = f[4].strftime('%Y-%m-%d') if hasattr(f[4], 'strftime') else str(f[4])[:10]
            resenas.append({
                'estrellas': f[0],
                'nombre': f[1],
                'finca': f[2],
                'comentario': f[3],
                'fecha': fecha_str
            })

        promedio = sum(r['estrellas'] for r in resenas) / len(resenas) if resenas else 5.0
        return jsonify({'promedio': promedio, 'resenas': resenas})
    except Exception as e:
        print("❌ Error en obtener_resenas:", e)
        return jsonify({'error': str(e)}), 500

# =========================================================================
# API DE VISUALIZACIÓN DE REGISTROS POR MUNICIPIO
# =========================================================================
@app.route('/api/consultar-municipio', methods=['GET'])
def api_consultar_municipio():
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
        limite = 15
        offset = (pagina - 1) * limite
        municipio = request.args.get('municipio', 'TODOS')

        conn, motor = get_db_connection()
        cursor = conn.cursor()

        if municipio == 'TODOS':
            cursor.execute("SELECT COUNT(*) FROM Mensajes_Tickets")
            total = cursor.fetchone()[0] or 0
            if motor == 'sqlserver':
                cursor.execute("""
                    SELECT id_ticket, municipio, codigo_torre, canal, fecha_registro, asunto
                    FROM Mensajes_Tickets
                    ORDER BY id_ticket DESC
                    OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
                """, (offset, limite))
            else:
                cursor.execute("""
                    SELECT id_ticket, municipio, codigo_torre, canal, fecha_registro, asunto
                    FROM Mensajes_Tickets
                    ORDER BY id_ticket DESC
                    LIMIT ? OFFSET ?
                """, (limite, offset))
        else:
            cursor.execute("SELECT COUNT(*) FROM Mensajes_Tickets WHERE municipio = ?", (municipio,))
            total = cursor.fetchone()[0] or 0
            if motor == 'sqlserver':
                cursor.execute("""
                    SELECT id_ticket, municipio, codigo_torre, canal, fecha_registro, asunto
                    FROM Mensajes_Tickets
                    WHERE municipio = ?
                    ORDER BY id_ticket DESC
                    OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
                """, (municipio, offset, limite))
            else:
                cursor.execute("""
                    SELECT id_ticket, municipio, codigo_torre, canal, fecha_registro, asunto
                    FROM Mensajes_Tickets
                    WHERE municipio = ?
                    ORDER BY id_ticket DESC
                    LIMIT ? OFFSET ?
                """, (municipio, limite, offset))

        filas = cursor.fetchall()
        conn.close()

        registros = []
        for f in filas:
            fecha_str = f[4].strftime('%Y-%m-%d %H:%M') if hasattr(f[4], 'strftime') else str(f[4])[:16]
            registros.append({
                'id': f[0],
                'municipio': f[1],
                'finca': f[3],
                'torre': f[2] or 'General',
                'fecha': fecha_str,
                'temp': 16.5,
                'hum_suelo': 62.0
            })

        return jsonify({
            'total': total,
            'pagina': pagina,
            'total_paginas': math.ceil(total / limite) if total > 0 else 1,
            'stats': {'temp_avg': 16.5, 'temp_min': 4.2, 'hum_avg': 62.0},
            'registros': registros
        })
    except Exception as e:
        print("❌ Error en consultar_municipio:", e)
        return jsonify({'error': str(e)}), 500

# =========================================================================
# CHAT SINCRÓNICO + PANEL DEL AGENTE (módulo chat_seguro.py)
# Debe registrarse DESPUÉS de definir get_db_connection.
# =========================================================================
registrar_chat(app, get_db_connection)


if __name__ == '__main__':
    _c, _m = get_db_connection()
    print(f"\n>>> Motor de base de datos activo al iniciar: {_m.upper()} <<<\n")
    _c.close()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
