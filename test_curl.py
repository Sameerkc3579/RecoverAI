import sys
from curl_cffi import requests

print("Dir:", dir(requests.exceptions) if hasattr(requests, "exceptions") else requests.errors.__all__)
