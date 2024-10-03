from google.cloud import datastore
from flask import Flask, request, url_for, render_template, make_response
from jose import jwt
from urllib.request import urlopen
from authlib.integrations.flask_client import OAuth
from werkzeug.exceptions import HTTPException
import json
import dogs
import toys
import verify_jwt
import constants

app = Flask(__name__)
app.register_blueprint(dogs.bp)
app.register_blueprint(toys.bp)
app.register_blueprint(verify_jwt.bp)
app.secret_key = 'SUPER KEY'

client = datastore.Client()

# override flask errorhanlder to return json instead of html
@app.errorhandler(HTTPException)
def handle_exception(e):
    response = e.get_response()
    response.data = json.dumps({
        "Error": e.name,
    })
    response.content_type = "application/json"
    return response

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=constants.CLIENT_ID,
    client_secret=constants.CLIENT_SECRET,
    api_base_url="https://" + constants.DOMAIN,
    access_token_url="https://" + constants.DOMAIN + "/oauth/token",
    authorize_url="https://" + constants.DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
    server_metadata_url="https://" + constants.DOMAIN + "/.well-known/openid-configuration"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri = url_for('user_info', _external=True)
    )

@app.route('/user_info')
def user_info():
    """
    Get and save user info with login
    """
    token = oauth.auth0.authorize_access_token()
    user = token['userinfo']
    query = client.query(kind=constants.USERS)
    key_query = client.key(constants.USERS, user['sub'])
    query.add_filter('__key__', '=', key_query)
    result = list(query.fetch())
    if len(result) == 0:
        new_user = datastore.Entity(key=client.key(constants.USERS, user['sub']))
        new_user.update({
            'name': user['nickname'],
            'email': user['email'],
            'dogs': []
        })
        client.put(new_user)
    return render_template('user_info.html', token=token)

@app.route('/users', methods=['GET'])
def get_users():
    """
    Returns list of all users in database
    """
    if request.method == 'GET':
        if request.accept_mimetypes.accept_json:
            query = client.query(kind=constants.USERS)
            results = list(query.fetch())
            for user in results:
                user['id'] = user.key.name
            res = make_response(json.dumps(results))
            res.mimetype = 'application/json'
            res.status_code = 200
            return res
        else:
            msg = {'Error': 'Can only return JSON'}
            res = make_response(json.dumps(msg))
            res.mimetype = 'application/json'
            res.status_code = 406
            return res
    else:
        msg = {'Error': 'Method not recognized'}
        res = make_response(json.dumps(msg))
        res.status_code = 405
        res.mimetype = 'application/json'
        res.headers.set('Allow', 'GET')
        return res

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
