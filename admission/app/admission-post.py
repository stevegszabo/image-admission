import sys
import pprint
import requests

if __name__ == "__main__":

    request = {
        "request": {
            "name": "name",
            "namespace": "namespace",
            "operation": "CREATE",
            "uid": "uid",
            "kind": {
                "kind": "Deployment"
            },
            "object": {
                "metadata": {},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "name",
                                    "image": "image",
                                    "resources": {
                                        "requests": {},
                                        "limits": {}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    try:
        response = requests.post(url="http://192.168.2.180:8443/validate", json=request, timeout=10)
    except Exception as err:
        print(f"Unable to post: [{err}]")
        sys.exit(1)

    if response.status_code != 200:
        print(f"code: [{response.status_code}]")
        print(f"text: [{response.text}]")
        sys.exit(1)

    pprint.pprint(response.json())
    sys.exit(0)
