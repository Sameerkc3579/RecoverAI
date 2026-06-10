from curl_cffi import requests
print("Timeout:", hasattr(requests.errors, "Timeout"))
print("TimeoutError:", hasattr(requests.errors, "TimeoutError"))
print("RequestsError:", hasattr(requests.errors, "RequestsError"))
