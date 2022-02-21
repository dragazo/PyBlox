class $service_name:
$service_desc
    def __init__(self, client):
        self._client = client
    def __getattr__(self, attr):
        if isinstance(attr, str) and not attr.startswith('_'):
            res = getattr(self, f'_{attr}', None)
            if res is not None: return res
        raise AttributeError(f'No attribute {attr}')
$rpcs