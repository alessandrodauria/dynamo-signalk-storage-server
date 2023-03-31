import os
import tempfile
import xml.etree.cElementTree as ET

from flask_restx import Api, Resource
from flask import current_app, send_file, render_template, request, Response
from sqlalchemy import create_engine
from werkzeug.datastructures import FileStorage
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash
from http import HTTPStatus
from werkzeug.exceptions import Conflict, BadRequest

from app import app, auth, get_conf, log, queues

# Create the api object using restx
api = Api(app)
"""
Create a new user
       
@api.route('/signup')
class SignUp(Resource):

    def post(self):
       
        data = request.get_json()

        try:
            new_user = User(
                username = data.get('username'),
                email = data.get('email'),
                password_hash = generate_password_hash(data.get('password'))
            )
            new_user.save()
            return new_user, HTTPStatus.CREATED

        except Exception as e:
            raise Conflict(f"User with email {data.get('email')} exists")

""" 

"""

Generate a JWT 

@api.route.route('/login')
class Login(Resource):

    def post(self):

        data = request.get_json()

        email = data.get('email')
        password = data.get('password')

        user=User.query.filter_by(email=email).first()

        if(user is not None) and check_password_hash(user.password_hash,password):
            access_token = create_access_token(identity = user.username)
            refresh_token = create_refresh_token(identity = user.username)

            response = {
                'access_token': access_token,
                'refresh_token':refresh_token
            }

            return response,HTTPStatus.OK

        raise BadRequest("Invali username or password")

"""
"""
Refresh a JWT 

@api.route('/refresh')
class Refresh(Resource):

    @jwt_required(refresh=True)
    def post(self):

        username = get_jwt_identity()
        access_token = create_access_token(identity=username)

        return {'access_token':access_token }, HTTPStatus.OK
"""


@api.route('/publickey')
class PublicKey(Resource):
    def get(self):
        conf = get_conf()
        log.debug("public_key_filename:"+conf["public_key_filename"])
        return send_file(conf["public_key_filename"], as_attachment=True)


@auth.verify_password
def authenticate(username, password):
    if username and password:
        if username == 'admin' and password == 'password':
            return True
        else:
            return False
    return False


# Create an api parser for public key upload
upload_publickey_parser = api.parser()

# Add parser for file storage
upload_publickey_parser.add_argument('file', location='files', type=FileStorage, required=True,
                                     help='DYNAMO Public Key -public.pem file')


@api.route('/upload/publickey/<self_id>')
@api.expect(upload_publickey_parser)
class PublicKeyUpload(Resource):
    @auth.login_required
    def post(self, self_id):
        # This is FileStorage instance
        uploaded_file = request.files['file']

        # Check if the mime is plain/text
        if uploaded_file.mimetype == 'application/x-x509-ca-cert':

            # Compose the destination file path name
            file_path = os.path.join(current_app.config.get('PUBLIC_KEY_ROOT'), str(self_id) + "-public.pem")

            # Save the uploaded file as the file path
            uploaded_file.save(file_path)

            # Log the status
            log.debug("Saved public key as: " + file_path)

            return {"result": "ok", "user": auth.current_user()}, 200

        else:
            return {"result": "fail", "error": "File mimetype must be application/x-x509-ca-cert"}, 422


# Create an api parser
upload_parser = api.parser()

# Add parser for file storage
upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='DYNAMO log.gz.enc file')

# Add parser for session id
upload_parser.add_argument('sessionId', required=True, help="Session unique identifier")


@api.route('/upload/<self_id>')
@api.expect(upload_parser)
class ParcelUpload(Resource):
    def post(self, self_id):

        # This is FileStorage instance
        uploaded_file = request.files['file']

        # Check if the myme is application/octet-stream
        if uploaded_file.mimetype == 'application/octet-stream':

            # Compose the destination directory
            destination = os.path.join(current_app.config.get('MEDIA_ROOT'), str(self_id) + "/")

            # Check if the directory exists
            if not os.path.exists(destination):
                # Make the directory if needed
                os.makedirs(destination)

            # Set the file path
            file_path = ""

            # Set the file name
            temp_name = ""

            # Until the random temporary file name is not unique...
            done = False
            while not done:

                # Generate a temporary file name
                temp_name = next(tempfile._get_candidate_names())

                # Create a file name
                file_path = '%s%s%s' % (destination, temp_name, '.log.gz.enc')

                # Check if the file already exists
                if os.path.isfile(file_path) is False:
                    # If the file doesn't exist, exit the cycle
                    done = True

            # Save the uploaded file as the file path
            uploaded_file.save(file_path)

            # Enqueue the task
            queues.enqueue({"directory": self_id, "file_item": temp_name + '.log.gz.enc', "conf": get_conf()})

            return {'result': 'ok'}, 200
        else:
            return {'result': 'fail', "error": "File mimetype must be application/octet-stream"}, 422


@api.route('/lastPosition')
class LastPosition(Resource):
    def get(self):
        positions = []

        conf = get_conf()

        connection_string = conf["connection_string"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        try:
            result = conn.execute(
                "SELECT ctx.context, pos.timestamp, ctx.value as info, pos.position FROM public.context ctx, "
                "(SELECT context, timestamp, value as position FROM public.navigation_position np1 WHERE timestamp = "
                "(SELECT MAX(np2.timestamp) FROM public.navigation_position np2 WHERE np1.context = np2.context) "
                "ORDER BY context) pos WHERE ctx.context = pos.context LIMIT 1;"
            )
            for row in result:
                positions.append({
                    "id": row[0].split(":")[-1],
                    "timestamp": str(row[1]),
                    "info": row[2],
                    "position": row[3]
                })
            conn.close()
        except:
            conn.close()

        return positions


@api.route('/gpx/<self_id>')
class GPX(Resource):
    def get(self, self_id):
        query = "SELECT * FROM public.navigation_position WHERE context='" + self_id + "' "
        
        conf = get_conf()

        connection_string = conf["connection_string"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        gpx = ET.Element("gpx", attrib={"xmlns": "http://www.topografix.com/GPX/1/1"})
        trk = ET.SubElement(gpx, "trk")
        trkseg = ET.SubElement(trk, "trkseg")

        start = request.args.get('start')
        end = request.args.get('end')
        hours = request.args.get('hours')
        minutes = request.args.get('minutes')
        seconds = request.args.get('seconds')

        try:
            if start is not None and end is not None:
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif start is not None and (hours is not None or minutes is not None or seconds is not None):
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = startTime + timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif end is not None and (hours is not None or minutes is not None or seconds is not None):
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                startTime = endTime - timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            else:
                query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "
        except Exception as e:
            query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "

        query += "ORDER BY timestamp ASC;"

        try:
            result = conn.execute(query)
            for row in result:
                trkpt = ET.SubElement(trkseg, "trkpt", attrib={"lat": str(row[5]), "lon": str(row[4])})
                ET.SubElement(trkpt, "time").text = str(row[1])

            conn.close()
        except Exception as e:
            conn.close()

        return Response(ET.tostring(gpx), mimetype='text/xml')
    


import json

""" prende il GeoJSON """

@api.route('/geojson/<self_id>')
class GeoJSON(Resource):
    def get(self, self_id):
        query = "SELECT * FROM public.navigation_position WHERE context='" + self_id + "' "
        
        conf = get_conf()

        connection_string = conf["connection_string"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        start = request.args.get('start')
        end = request.args.get('end')
        hours = request.args.get('hours')
        minutes = request.args.get('minutes')
        seconds = request.args.get('seconds')

        try:
            if start is not None and end is not None:
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif start is not None and (hours is not None or minutes is not None or seconds is not None):
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = startTime + timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif end is not None and (hours is not None or minutes is not None or seconds is not None):
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                startTime = endTime - timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            else:
                query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "
        except Exception as e:
            query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "

        query += "ORDER BY timestamp ASC;"

        try:
            result = conn.execute(query)

            # Creazione del dizionario GeoJSON
            geojson = {
                "type": "FeatureCollection",
                "features": []
            }
            for row in result:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[4], row[5]]
                    },
                    "properties": {
                        "time": str(row[1])
                    }
                }
                geojson["features"].append(feature)

            conn.close()
        except Exception as e:
            conn.close()

        # Restituzione del file GeoJSON come stringa JSON
        return Response(json.dumps(geojson), mimetype='application/json')
    


""" converte il json in GeoJSON """

@api.route('/geojsonconvert/<self_id>')
class GeoJSON(Resource):
    def get(self, self_id):
        query = "SELECT * FROM public.navigation_position WHERE context='" + self_id + "' "

        conf = get_conf()

        connection_string = conf["connection_string"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        start = request.args.get('start')
        end = request.args.get('end')
        hours = request.args.get('hours')
        minutes = request.args.get('minutes')
        seconds = request.args.get('seconds')

        try:
            if start is not None and end is not None:
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif start is not None and (hours is not None or minutes is not None or seconds is not None):
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = startTime + timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif end is not None and (hours is not None or minutes is not None or seconds is not None):
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                startTime = endTime - timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            else:
                query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "
        except Exception as e:
            query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "

        query += "ORDER BY timestamp ASC;"

        try:
            result = conn.execute(query)

            features = []
            for row in result:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row[4], row[5]]
                    },
                    "properties": {
                        "timestamp": str(row[1])
                    }
                }
                features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "features": features
            }

            conn.close()

            return Response(json.dumps(geojson), mimetype='application/json')

        except Exception as e:
            conn.close()

            return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')



from flask import send_from_directory

@app.route('/geojson')
def get_geojson():
    return send_from_directory('static/lib/v7.2.2-package/ol-ext-master/examples/data', 'fond_guerre.geojson')


@app.route('/map')
def index():
    return render_template('index.html')
