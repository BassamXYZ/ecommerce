from hashlib import sha256
from django.conf import settings

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def hash_payeer_sign(*args):
    list_of_value_for_sign = map(str, [*args])
    result_string = ":".join(list_of_value_for_sign)
    sign_hash = sha256(result_string)
    sign = sign_hash.hexdigest().upper()
    return sign