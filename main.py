import os
import time
import requests
import threading
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TOKEN = "8107696402:AAEwS9w1AcFYY8jY-vrENEtcvkEcAjuq-QI"
CHAT_ID = -1003994301891  # Identificador de Telegram sin espacios ocultos

# Bounding Box Regional para Sismos Generales (México + Guatemala)
REGION_BOUNDS = {
    "lat_min": 12.0,  
    "lat_max": 35.0,  
    "lon_min": -118.0, 
    "lon_max": -87.0  
}

# Coordenadas Específicas Actualizadas para el Perímetro del Popocatépetl
POPO_LAT_MIN, POPO_LAT_MAX = 18.7, 19.3
POPO_LON_MIN, POPO_LON_MAX = -98.8, -98.3  # Ordenado de menor a mayor para la validación matemática

# Registros de Namespaces obligatorios para el XML de la NOAA / NHC
NAMESPACES = {
    'georss': 'http://www.georss.org/georss',
    'nhc': 'https://www.nhc.noaa.gov'
}

# --- MEMORIA GLOBAL DE NOTIFICACIONES ---
notificados_sismos = set()
vistos_huracanes = set()
vistos_volcanes = set()

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"Error de Telegram (Status {response.status_code}): {response.text}")
    except Exception as e:
        print(f"Error crítico enviando a Telegram: {e}")

# --- 1. MONITOREO DE SISMOS GENERALES (USGS) ---
def monitorear_sismos():
    global notificados_sismos
    print("Iniciando monitoreo sísmico regional (MX-GT)...")
    
    while True:
        try:
            # Feed de la ÚLTIMA HORA para optimizar consumo y procesar eventos inmediatos
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for sismo in data.get('features', []):
                    s_id = sismo['id']
                    
                    if s_id in notificados_sismos:
                        continue

                    coords = sismo['geometry']['coordinates']
                    lon, lat = coords[0], coords[1]
                    
                    # Filtro Geográfico Regional
                    if (REGION_BOUNDS["lat_min"] <= lat <= REGION_BOUNDS["lat_max"] and 
                        REGION_BOUNDS["lon_min"] <= lon <= REGION_BOUNDS["lon_max"]):
                        
                        props = sismo['properties']
                        mag = props.get('mag')
                        
                        # Filtro de Magnitud para sismos generales cotidianos (Mínimo 4.0)
                        if mag is not None and mag >= 4.0:
                            fecha_local = datetime.fromtimestamp(props['time'] / 1000.0) - timedelta(hours=6)
                            hora_txt = fecha_local.strftime('%d/%m/%Y %H:%M:%S')
                            
                            mensaje = (f"⚠️ **SISMO DETECTADO (REGIONAL)**\n\n"
                                       f"📈 **Magnitud:** {mag}\n"
                                       f"🕒 **Hora local (UTC-6):** {hora_txt}\n"
                                       f"📍 **Lugar:** {props['place']}\n"
                                       f"🌐 [Ver mapa y detalles]({props['url']})")
                            
                            enviar_telegram(mensaje)
                            notificados_sismos.add(s_id) 
            else:
                print(f"USGS respondió con código de error: {response.status_code}")
                                
        except Exception as e:
            print(f"Error en hilo de sismos: {e}")
            
        time.sleep(30)  # Revisión cada 30 segundos

# --- 2. MONITOREO DE HURACANES (NHC / NOAA) ---
def monitorear_huracanes():
    global vistos_huracanes
    print("Iniciando monitoreo de ciclones con rastreo de actualizaciones (NHC)...")
    
    while True:
        try:
            urls = ["https://www.nhc.noaa.gov/index-at.xml", "https://www.nhc.noaa.gov/index-ep.xml"]
            
            for url in urls:
                res = requests.get(url, timeout=10)
                if res.status_code != 200:
                    continue
                    
                root = ET.fromstring(res.content)
                cuenca = "ATLÁNTICO / CARIBE" if "index-at" in url else "PACÍFICO ESTE"
                
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    
                    if "no tropical cyclones" in title.lower():
                        continue
                    
                    desc_text = item.find('description').text or ""
                    if "formation is not expected" in desc_text.lower() and "Tropical Weather Outlook" in title:
                        continue
                    
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "No especificada"
                    firma_alerta = f"{title}_{pub_date}"
                    
                    if firma_alerta not in vistos_huracanes:
                        link = item.find('link').text
                        
                        punto_geo = item.find('georss:point', NAMESPACES)
                        coordenadas = punto_geo.text if punto_geo is not None else "No disponible"
                        
                        viento_elem = item.find('nhc:wind', NAMESPACES)
                        presion_elem = item.find('nhc:pressure', NAMESPACES)
                        
                        viento = viento_elem.text if viento_elem is not None else None
                        presion = presion_elem.text if presion_elem is not None else None
                        
                        detalles_tecnicos = ""
                        if coordenadas != "No disponible":
                            detalles_tecnicos += f"📍 **Ubicación (Lat, Lon):** {coordenadas}\n"
                        if viento:
                            try:
                                v_kmh = round(float(viento.split()[0]) * 1.852)
                                detalles_tecnicos += f"💨 **Vientos máximos:** {viento} (~{v_kmh} km/h)\n"
                            except:
                                detalles_tecnicos += f"💨 **Vientos máximos:** {viento}\n"
                        if presion:
                            detalles_tecnicos += f"📉 **Presión Mínima:** {presion}\n"

                        emoji = "🌀"
                        if "Hurricane" in title or "Huracán" in title: emoji = "🔴 **[ACTUALIZACIÓN DE HURACÁN]**"
                        elif "Storm" in title: emoji = "⛈️ **[ACTUALIZACIÓN TORMENTA]**"
                        elif "Depression" in title: emoji = "🌧️ **[ACTUALIZACIÓN DEPRESIÓN]**"
                        elif "Disturbance" in title: emoji = "🟡 **[MONITOREO DE INESTABILIDAD]**"

                        mensaje = (
                            f"{emoji} **ALERTA CICLÓNICA ({cuenca})**\n\n"
                            f"📢 **Fenómeno:** {title}\n"
                            f"{detalles_tecnicos}"
                            f"📅 **Emisión del boletín:** {pub_date}\n\n"
                            f"🌐 [Ver trayectoria y modelos en vivo]({link})"
                        )
                        
                        enviar_telegram(mensaje)
                        vistos_huracanes.add(firma_alerta)
                        
        except Exception as e:
            print(f"Error en hilo de huracanes: {e}")
            
        time.sleep(600)  # Consulta cada 10 minutos

# --- 3. MONITOREO VOLCÁNICO ADAPTADO (USGS API - INMUNE A BLOQUEOS) ---
def monitorear_volcanes():
    global vistos_volcanes
    print("Iniciando monitoreo volcánico continuo vía API global de la USGS...")
    
    while True:
        try:
            # Consultamos el feed de eventos globales de las últimas 24 horas
            url_usgs = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
            response = requests.get(url_usgs, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                for evento in data.get('features', []):
                    ev_id = evento['id']
                    
                    # Si ya lo notificamos en ciclos pasados, lo ignoramos
                    if ev_id in vistos_volcanes:
                        continue
                        
                    coords = evento['geometry']['coordinates']
                    lon, lat = coords[0], coords[1]
                    props = evento['properties']
                    place = props.get('place', '').lower()
                    
                    # Evaluación espacial estricta usando tus coordenadas optimizadas o por etiqueta textual
                    if (POPO_LAT_MIN <= lat <= POPO_LAT_MAX and POPO_LON_MIN <= lon <= POPO_LON_MAX) or "popocatepetl" in place:
                        
                        mag = props.get('mag')
                        # Conversión a Hora local de México (UTC -6)
                        fecha_local = datetime.fromtimestamp(props['time'] / 1000.0) - timedelta(hours=6)
                        hora_txt = fecha_local.strftime('%d/%m/%Y %H:%M:%S')
                        
                        mensaje = (
                            f"🌋 **ACTIVIDAD VOLCÁNICA DETECTADA (USGS)**\n\n"
                            f"📢 **Evento:** Sismo Vulcanotectónico / Exhalación\n"
                            f"📍 **Ubicación:** {props['place']} ({lat}, {lon})\n"
                            f"📈 **Magnitud:** {mag if mag is not None else 'Instrumental'}\n"
                            f"🕒 **Hora local (UTC-6):** {hora_txt}\n\n"
                            f"🌐 [Ver mapa de actividad y telemetría]({props['url']})"
                        )
                        
                        enviar_telegram(mensaje)
                        vistos_volcanes.add(ev_id)  # Registramos el ID único en la memoria global
                        print(f"Alerta volcánica enviada con éxito: ID {ev_id} - Mag {mag}")
            else:
                print(f"La API de USGS respondió con código de error en volcanes: {response.status_code}")
                
        except Exception as e:
            print(f"Error en hilo de monitoreo volcánico: {e}")
            
        time.sleep(120)  # Escaneo automático cada 2 minutos para mantener el canal al día

@app.route('/')
def home():
    return "✅ Centro de Monitoreo Multiamenaza (MX-GT) Activo y Corriendo"

if __name__ == "__main__":
    # Inicialización de hilos en segundo plano
    threading.Thread(target=monitorear_sismos, daemon=True).start()
    threading.Thread(target=monitorear_huracanes, daemon=True).start()
    threading.Thread(target=monitorear_volcanes, daemon=True).start()
    
    # Adaptación de puerto dinámico para Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
