from flask import Blueprint, request, make_response
from google.cloud import datastore
from entitiy_checks import check_mimes, missing_attribute
import json
import constants

client = datastore.Client()

bp = Blueprint('toys', __name__, url_prefix='/toys')

@bp.route('', methods=['GET', 'POST'])
def toys_get_post():

    # create toy
    if request.method == 'POST':
        mimes = check_mimes(request)
        if mimes:
            return mimes
        content = request.get_json()
        try:
            new_toy = datastore.Entity(key=client.key(constants.TOYS))
            new_toy.update({
                'name': content['name'],
                'size': content['size'],
                'type': content['type'],
                'dog': None
            })
            client.put(new_toy)
            new_toy['id'] = new_toy.key.id
            new_toy['self'] = f"{request.url}/{new_toy.key.id}"
            res = make_response(json.dumps(new_toy))
            res.mimetype = 'application/json'
            res.status_code = 201
            return res
        except Exception:
            return missing_attribute()
    
    # get all toys
    elif request.method == 'GET':
        if request.accept_mimetypes.accept_json:
            query = client.query(kind=constants.TOYS)

            # pagination setup
            q_limit = int(request.args.get('limit', '5'))
            q_offset = int(request.args.get('offset', '0'))
            count = len(list(query.fetch()))
            g_iterator = query.fetch(limit= q_limit, offset=q_offset)
            pages = g_iterator.pages
            results = list(next(pages))
            if g_iterator.next_page_token:
                next_offset = q_offset + q_limit
                next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
            else:
                next_url = None
            for toy in results:
                toy['self'] = f"{request.url}/{toy.key.id}"
                toy['id'] = toy.key.id
            output = {constants.TOYS: results}
            output['total'] = count
            if next_url:
                output["next"] = next_url
            return (output, 200)
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
        res.headers.setlist('Allow', ['POST', 'GET'])
        return res

@bp.route('/<int:toy_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def toys_update_delete(toy_id):
    
    toy_key = client.key(constants.TOYS, toy_id)
    toy = client.get(key=toy_key)
    if toy:

        # get a toy
        if request.method == 'GET':
            if request.accept_mimetypes.accept_json:
                toy['self'] = f"{request.url}/{toy.key.id}"
                toy['id'] = toy.key.id
                res = make_response(json.dumps(toy))
                res.status_code = 200
                res.mimetype = 'application/json'
                return res
            else:
                msg = {'Error': 'Can only return JSON'}
                res = make_response(json.dumps(msg))
                res.mimetype = 'application/json'
                res.status_code = 406
                return res

        # edit a toy
        elif request.method == 'PATCH':
            mimes = check_mimes(request)
            if mimes:
                return mimes
            content = request.get_json()
            toy.update((k, content[k]) for k in toy.keys() & content.keys())
            client.put(toy)
            toy['self'] = request.url
            toy['id'] = toy.key.id
            res = make_response(json.dumps(toy))
            res.mimetype = 'application/json'
            res.status_code = 200
            return res

        # edit a toy again 
        elif request.method == 'PUT':
            mimes = check_mimes(request)
            if mimes:
                return mimes
            content = request.get_json()
            try:
                toy.update({'name': content['name'], 'size': content['size'], 'type': content['type']})
                client.put(toy)
                toy['self'] = request.url
                toy['id'] = toy.key.id
                res = make_response(json.dumps(toy))
                res.mimetype = 'application/json'
                res.status_code = 200
                return res
            except Exception:
                return missing_attribute()

        # delete a toy
        elif request.method == 'DELETE':
            if toy['dog']:
                dog_key = client.key(constants.DOGS, toy['dog'])
                dog = client.get(key=dog_key)
                dog[constants.TOYS].remove(toy_id)
                client.put(dog)
            client.delete(toy_key)
            return ('', 204)

        else:
            msg = {'Error': 'Method not recognized'}
            res = make_response(json.dumps(msg))
            res.status_code = 405
            res.mimetype = 'application/json'
            res.headers.setlist('Allow', ['GET', 'PATCH', 'PUT', 'DELETE'])
            return res
        
    else:
        msg = {'Error': 'No toy with this toy_id exists'}
        res = make_response(json.dumps(msg))
        res.mimetype = 'application/json'
        res.status_code = 404
        return res  