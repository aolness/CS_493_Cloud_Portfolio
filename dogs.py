from flask import Blueprint, request, make_response
from google.cloud import datastore
import json
import constants
from entitiy_checks import check_mimes, missing_attribute, verify_owner
from verify_jwt import verify_jwt


client = datastore.Client()

bp = Blueprint('dogs', __name__, url_prefix='/dogs')


@bp.route('', methods=['GET', 'POST'])
def dogs_get_post():
    """
    Allows creation and retrieval of dogs
    """

    # verify jwt
    payload = verify_jwt(request)

    # create a dog
    if request.method == 'POST':
        mimes = check_mimes(request)
        if mimes:
            return mimes
        owner_key = client.key(constants.USERS, payload['sub'])
        owner = client.get(key=owner_key)
        content = request.get_json()
        query = client.query(kind=constants.DOGS)
        query.add_filter('owner', '=', payload['sub'])
        result = list(query.fetch())

        # verify name is unique to user
        duplicate_dog = next((dog for dog in result if dog['name'] == content['name']), False)
        if duplicate_dog:
            msg = {'Error': 'Owner already has dog with this name'}
            res = make_response(json.dumps(msg))
            res.mimetype = 'application/json'
            res.status_code = 403
            return res 
        
        # try to create dog
        try:
            new_dog = datastore.Entity(key=client.key(constants.DOGS))
            new_dog.update({
                'name': content['name'],
                'age': content['age'],
                'breed': content['breed'],
                'toys': [],
                'owner': payload['sub']
            })
            client.put(new_dog)
            owner[constants.DOGS].append(new_dog.key.id)
            client.put(owner)
            new_dog['id'] = new_dog.key.id
            new_dog['self'] = f"{request.url}/{new_dog.key.id}"
            res = make_response(json.dumps(new_dog))
            res.mimetype = 'application/json'
            res.status_code = 201
            return res
        
        # error creating dog
        except Exception:
            return missing_attribute()

    # get users dogs
    elif request.method == 'GET':
        if request.accept_mimetypes.accept_json:
            query = client.query(kind=constants.DOGS)
            query.add_filter('owner', '=', payload['sub'])

            # set up for pagination
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
            for dog in results:
                dog['self'] = f"{request.url}/{dog.key.id}"
                dog['id'] = dog.key.id
            output = {constants.DOGS: results}
            output['total'] = count
            if next_url:
                output["next"] = next_url
            res = make_response(json.dumps(output))
            res.status_code = 200
            res.mimetype = 'aaplication/json'
            return res
        
        # will not accept JSOn
        else:
                msg = {'Error': 'Can only return JSON'}
                res = make_response(json.dumps(msg))
                res.mimetype = 'application/json'
                res.status_code = 406
                return res
        
    # not GET or POST
    else:
        msg = {'Error': 'Method not recognized'}
        res = make_response(json.dumps(msg))
        res.status_code = 405
        res.mimetype = 'application/json'
        res.headers.setlist('Allow', ['POST', 'GET'])
        return res


@bp.route('/<int:dog_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def dog_get_update_delete(dog_id):
    
    payload = verify_jwt(request)
    dog_key = client.key(constants.DOGS, dog_id)
    dog = client.get(key=dog_key)
    if dog:

        # verify user owns dog
        verify_owner(dog, payload)

        # get dog
        if request.method == 'GET':
            if request.accept_mimetypes.accept_json:
                dog['self'] = f"{request.url}/{dog.key.id}"
                dog['id'] = dog.key.id
                res = make_response(json.dumps(dog))
                res.status_code = 200
                res.mimetype = 'application/json'
                return res
            else:
                msg = {'Error': 'Can only return JSON'}
                res = make_response(json.dumps(msg))
                res.mimetype = 'application/json'
                res.status_code = 406
                return res

        # edit dog
        elif request.method == 'PATCH':
            mimes = check_mimes(request)
            if mimes:
                return mimes
            content = request.get_json()

            # only update items in dog and the request
            dog.update((k, content[k]) for k in dog.keys() & content.keys())
            client.put(dog)
            dog['self'] = request.url
            dog['id'] = dog.key.id
            res = make_response(json.dumps(dog))
            res.mimetype = 'application/json'
            res.status_code = 200
            return res
        
        # edit dog
        elif request.method == 'PUT':
            mimes = check_mimes(request)
            if mimes:
                return mimes
            content = request.get_json()

            # require all attributes
            try:
                dog.update({'name': content['name'], 'age': content['age'], 'breed': content['breed']})
                client.put(dog)
                dog['self'] = request.url
                dog['id'] = dog.key.id
                res = make_response(json.dumps(dog))
                res.mimetype = 'application/json'
                res.status_code = 200
                return res
            except Exception:
                return missing_attribute()

        # delete dog
        elif request.method == 'DELETE':
            owner_key = client.key(constants.USERS, payload['sub'])
            owner = client.get(key=owner_key)

            # verify user owns dog
            try:
                owner[constants.DOGS].remove(dog_id)
            except Exception:
                msg = {'Error': 'Dog not owned by owner'}
                res = make_response(json.dumps(msg))
                res.status_code = 403    
                return res

            # if dog has toys
            if dog[constants.TOYS]:
                query = client.query(kind=constants.TOYS)
                query.add_filter('dog', '=', dog.key.id)
                results = list(query.fetch())
                for i in results:
                    i['dog'] = None
                client.put_multi(results)
            client.put(owner)
            client.delete(dog_key)
            return ('', 204)

        else:
            msg = {'Error': 'Method not recognized'}
            res = make_response(json.dumps(msg))
            res.status_code = 405
            res.mimetype = 'application/json'
            res.headers.setlist('Allow', ['GET', 'PATCH', 'PUT', 'DELETE'])
            return res
    else:
        msg = {'Error': 'No dog with this dog_id exists'}
        res = make_response(json.dumps(msg))
        res.mimetype = 'application/json'
        res.status_code = 404
        return res  


@bp.route('/<int:dog_id>/toys/<int:toy_id>', methods=['PATCH', 'PUT', 'DELETE'])
def dogs_add_remove_toy(dog_id, toy_id):
    """
    Allows users to add or remove toys from a dogs toy list
    """
    dog_key = client.key(constants.DOGS, dog_id)
    dog = client.get(key=dog_key)
    toy_key = client.key(constants.TOYS, toy_id)
    toy = client.get(key=toy_key)

    # add toy to dog
    if request.method == 'PATCH' or request.method == 'PUT':
        if request.accept_mimetypes.accept_json:
            if dog and toy:

                # toy cannot alredy be owned
                if toy['dog'] == None:
                    toy.update({'dog': dog_id})
                    dog[constants.TOYS].append(toy_id)
                    client.put_multi([toy, dog])
                    return ('', 204)
                else:
                    msg = {'Error': 'This toy already has a dog'}
                    return (msg, 403)           
            else:
                msg = {'Error': 'The specified dog and/or toy does not exist'}
                return (msg, 404)
        else:
                msg = {'Error': 'Can only return JSON'}
                res = make_response(json.dumps(msg))
                res.mimetype = 'application/json'
                res.status_code = 406
                return res
        
    # remove toy from dog
    elif request.method == 'DELETE':
        if dog and toy:
            if toy_id in dog[constants.TOYS] and toy['dog'] == dog_id:
                    toy.update({'dog': None})
                    dog[constants.TOYS].remove(toy_id)
                    client.put_multi([toy, dog])
                    return ('', 204)
        else:
            msg = {'Error': 'No dog with this dog_id has the toy with this toy_id'}
            return (msg, 404)
    else:
        msg = {'Error': 'Method not recognized'}
        res = make_response(json.dumps(msg))
        res.status_code = 405
        res.mimetype = 'application/json'
        res.headers.setlist('Allow', ['PATCH', 'PUT' 'DELETE'])
        return res
