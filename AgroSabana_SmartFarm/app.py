from flask import Flask, render_template, request, jsonify
from datetime import datetime
import random
import os

app = Flask(__name__)

# Catálogo centralizado de Torres Agroclimáticas por Municipio y Agricultor (Sabana Centro)
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

        # Evaluación agronómica automática
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
