from flask import Flask, render_template, jsonify
import folium
import requests
import pandas as pd
import json
from datetime import datetime

app = Flask(__name__)

# Function to fetch Ghana's regions GeoJSON data

def get_ghana_regions():
    try:
        with open('data/ghana_regions.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load local GeoJSON file: {e}")
        return None

# Function to fetch solar data from NASA's API
def get_solar_data(lat, lon, start_date, end_date):
    url = "https://power.larc.nasa.gov/api/temporal"
    params = {
        'start': start_date,
        'end': end_date,
        'latitude': lat,
        'longitude': lon,
        'parameters': 'ALLSKY_SFC_SW_DWN',  # Solar radiation parameter
        'community': 'AG',
        'format': 'JSON'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for HTTP status codes >= 400
        data = response.json()
        solar_data = pd.DataFrame(data['properties']['parameter']['ALLSKY_SFC_SW_DWN'], index=[0]).transpose()
        solar_data.columns = ['Solar Radiation (MJ/m²)']
        return solar_data
    except Exception as e:
        print(f"Error fetching solar data: {e}")
        return pd.DataFrame()

# Function to calculate the centroid of a region
def calculate_centroid(geometry):
    if geometry['type'] == 'Polygon':
        coordinates = geometry['coordinates'][0]
    elif geometry['type'] == 'MultiPolygon':
        coordinates = geometry['coordinates'][0][0]
    else:
        return None
    
    lon, lat = zip(*coordinates)
    return [sum(lat) / len(lat), sum(lon) / len(lon)]

@app.route('/')
def index():
    ghana_map = get_ghana_regions()
    if not ghana_map:
        return 'Error loading region data', 500

    base_map = folium.Map(location=[7.9465, -1.0232], zoom_start=6)

    for feature in ghana_map['features']:
        region_name = feature['properties'].get('region', 'Unknown Region')
        geometry = feature['geometry']
        centroid = calculate_centroid(geometry)
        if not centroid:
            continue

        start_date = '20190101'
        end_date = '20200107'
        solar_data = get_solar_data(centroid[0], centroid[1], start_date, end_date)

        avg_solar_radiation = (
            solar_data['Solar Radiation (MJ/m²)'].mean()
            if not solar_data.empty else "Data unavailable"
        )

        popup_content = (
            f"<strong>Region:</strong> {region_name}<br>"
            f"<strong>Avg Solar Radiation:</strong> {avg_solar_radiation} MJ/m²"
        )

        if geometry['type'] == 'Polygon':
            folium.Polygon(
                locations=[(lat, lon) for lon, lat in geometry['coordinates'][0]],
                color='blue', fill=True, fill_color='yellow', fill_opacity=0.4,
                popup=folium.Popup(popup_content, max_width=300)
            ).add_to(base_map)
        elif geometry['type'] == 'MultiPolygon':
            for polygon in geometry['coordinates']:
                folium.Polygon(
                    locations=[(lat, lon) for lon, lat in polygon[0]],
                    color='blue', fill=True, fill_color='yellow', fill_opacity=0.4,
                    popup=folium.Popup(popup_content, max_width=300)
                ).add_to(base_map)

    map_html = base_map._repr_html_()
    return render_template('index.html', map=map_html)

@app.route('/region/<region_name>')
def region(region_name):
    ghana_map = get_ghana_regions()
    if not ghana_map:
        return 'Error loading region data', 500

    region_data = [feature for feature in ghana_map['features'] if feature['properties']['region'] == region_name]
    if not region_data:
        return 'Region not found', 404

    region = region_data[0]
    geometry = region['geometry']
    centroid = calculate_centroid(geometry)
    if not centroid:
        return 'Error calculating region centroid', 500

    start_date = '20220101'
    end_date = '20220107'
    solar_data = get_solar_data(centroid[0], centroid[1], start_date, end_date)

    avg_solar_radiation = (
        solar_data['Solar Radiation (MJ/m²)'].mean()
        if not solar_data.empty else 'Data unavailable'
    )

    region_map = folium.Map(location=centroid, zoom_start=8)
    folium.GeoJson(region).add_to(region_map)
    folium.Marker(
        location=centroid,
        popup=(
            f"<strong>Region:</strong> {region_name}<br>"
            f"<strong>Avg Solar Radiation:</strong> {avg_solar_radiation} MJ/m²"
        )
    ).add_to(region_map)

    region_map_html = region_map._repr_html_()
    return render_template('region.html', region_map=region_map_html, region_name=region_name)

if __name__ == '__main__':
    app.run(debug=True)
