from flask import Flask, request, jsonify, render_template
from geopy.distance import geodesic
import sqlite3
import pyotp
import geocoder  # For automatic IP-based location fetching
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

class LocationBasedOTPSystem:
    def __init__(self):
        self.connection = sqlite3.connect('devices.db', check_same_thread=False)
        self.cursor = self.connection.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS devices
                            (id INTEGER PRIMARY KEY, name TEXT, location TEXT, otp TEXT)''')
        self.connection.commit()

    def register_device(self, name, location):
        otp = pyotp.random_base32()
        self.cursor.execute("INSERT INTO devices (name, location, otp) VALUES (?, ?, ?)", (name, location, otp))
        self.connection.commit()

    def get_devices_in_radius(self, target_location, radius=50):
        devices = []
        self.cursor.execute("SELECT * FROM devices")
        registered_devices = self.cursor.fetchall()
        for device in registered_devices:
            device_location = device[2]
            device_location = tuple(map(float, device_location[1:-1].split(',')))
            distance = geodesic(target_location, device_location).meters
            if distance <= radius:
                devices.append(device)
        return devices

    def generate_otp_for_devices(self, devices):
        otps = {}
        for device in devices:
            otp = pyotp.random_base32()
            self.cursor.execute("UPDATE devices SET otp = ? WHERE id = ?", (otp, device[0]))
            otps[device[1]] = otp
        self.connection.commit()
        return otps

    def close(self):
        self.connection.close()

system = LocationBasedOTPSystem()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        data = request.json
        name = data['name']
        location = f"({data['latitude']},{data['longitude']})"
        system.register_device(name, location)
        return jsonify({'status': 'Device registered successfully'})
    except Exception as e:
        app.logger.error(f"Error registering device: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_otps', methods=['POST'])
def generate_otps():
    try:
        data = request.json
        teacher_location = (data['latitude'], data['longitude'])
        devices_in_radius = system.get_devices_in_radius(teacher_location)
        if not devices_in_radius:
            return jsonify({'status': 'No devices found within the radius'})
        otps = system.generate_otp_for_devices(devices_in_radius)
        return jsonify(otps)
    except Exception as e:
        app.logger.error(f"Error generating OTPs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_teacher_location', methods=['GET'])
def get_teacher_location():
    # Automatically fetch the teacher's location using geocoder
    g = geocoder.ip('me')  # Fetches the location based on IP address
    return jsonify({'latitude': g.latlng[0], 'longitude': g.latlng[1]})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
