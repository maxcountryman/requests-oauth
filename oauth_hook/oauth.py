'''
    oauth_hook.oauth
    ----------------

    A module providing various OAuth related containers.
'''

import base64
import hmac
import urlparse

from urllib import quote, urlencode
from hashlib import sha1


class OAuthObject(object):
    '''A base class for OAuth token objects.'''
    verifier = None

    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

        # ensure key and secret are set
        if None in (key, secret):
            raise ValueError('Key and Secret must be set!')


class Consumer(OAuthObject):
    '''The consumer token object.'''
    pass


class Token(OAuthObject):
    '''The access token object.'''
    pass


class SignatureMethod(object):
    '''A base class for signature methods providing a set of common methods.'''
    def _to_utf8(self, s):
        return unicode(s, 'utf-8').encode('utf-8')

    def _escape(self, s):
        return quote(self._to_utf8(s), safe='~')

    def _normalize_request_parameters(self, request):
        '''The OAuth 1.0/a specs indicate that parameter and body data must be
        normalized. The specifics of this operation are detailed in the
        respective specs.

        Here we have to ensure that parameter and body data is properly
        handled. This means that the case of params or data being strings is
        taken care of.

        Essentially this is achieved by checking that `request.data` and
        `request.params` are not strings. This being the case we can then
        construct a unified list of tuples from them.

        Otherwise we build a series intermediary lists of tuples depending on
        the type of `request.params` and `request.data`.
        '''

        if not type(request.params) == str and not type(request.data) == str:
            # neither params nor data is a string, i.e. both are dicts

            # we concatenate the respective dicts
            data_and_params = \
                    dict(request.data.items() + request.params.items())

            normalized = []
            for k, v in data_and_params.items():
                normalized += [(k, v)]
        elif type(request.params) == str and type(request.data) == str:
            # if both params and data are strings
            params = urlparse.urlparse.parse_qs(request.params)
            data = urlparse.parse_qsl(request.data)
            normalized = params + data
        elif type(request.params) == str:
            # parse the string into a list of tuples
            normalized = urlparse.parse_qsl(request.params)

            # extract any data
            for k, v in request.data.items():
                normalized += [(k, v)]
        elif type(request.data) == str:
            # and we do the same if data
            normalized = urlparse.parse_qsl(request.data)

            # extract any params
            for k, v in request.params.items():
                normalized += [(k, v)]

        # extract values from our list of tuples and escape them
        escaped_normalized = []
        for t in normalized:
            k, v = t
            k, v = self._to_utf8(k), self._to_utf8(v)

            # save escaped key/value pairs to the request and our list
            request.data_and_params[k] = v
            escaped_normalized += [(k, v)]

        # stuff all the params from request.data_and_params in normalized
        for k, v in request.data_and_params.items():
            escaped_normalized += [(k, v)]

        # sort the params as per the OAuth spec
        escaped_normalized.sort()

        # finally encode the params as a string
        escaped_normalized = urlencode(escaped_normalized)
        return escaped_normalized.replace('+', '%20').replace('%7E', '~')


class HmacSha1Signature(SignatureMethod):
    '''HMAC-SHA1 Signature Method.

    This is a signature method, as per the OAuth 1.0/a and 2.0 specs. As the
    name might suggest, this method signs parameters with HMAC using SHA1.
    '''
    name = 'HMAC-SHA1'

    def sign(self, request, consumer, token=None):
        '''Sign request parameters.'''

        # the necessary parameters we'll sign
        params_and_data = self._normalize_request_parameters(request)
        parameters = [self._escape(request.method),
                      self._escape(request.url),
                      params_and_data]

        # set our key
        key = self._escape(consumer.secret) + '&'
        if token is not None:
            key += self._escape(token.secret)

        # build a Signature Base String, escaping '='
        signature_base_string = '&'.join(parameters).replace('=', '%3D')

        hashed = hmac.new(key, signature_base_string, sha1)
        oauth_signature = base64.b64encode(hashed.digest())[:-1]
        oauth_signature = self._escape(oauth_signature)

        # add the signature to the request params
        request.data_and_params['oauth_signature'] = oauth_signature
