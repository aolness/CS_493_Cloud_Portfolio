from flask import make_response
from verify_jwt import AuthError
import json

def check_mimes(request):
    if not request.accept_mimetypes.accept_json:
        msg = {'Error': 'Can only return JSON'}
        res = make_response(json.dumps(msg))
        res.mimetype = 'application/json'
        res.status_code = 406
        return res
    if request.content_type != 'application/json':
        msg = {'Error': 'Can only accept JSON'}
        res = make_response(json.dumps(msg))
        res.mimetype = 'application/json'
        res.status_code = 415
        return res
    
def missing_attribute():
    msg = {"Error": "The request object has missing or invalid input"}
    res = make_response(json.dumps(msg))
    res.mimetype = 'application/json'
    res.status_code = 400
    return res

def verify_owner(dog, owner):
    if dog['owner'] != owner['sub']:
        raise AuthError({"code": "Not Owner",
                         "description": "You are not the owner of this dog"}, 403)
    return