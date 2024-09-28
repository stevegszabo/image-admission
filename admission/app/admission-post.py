import sys
import json
import requests

if __name__ == "__main__":

    request = {
        "request": {
            "name": "webapp",
            "namespace": "namespace",
            "operation": "CREATE",
            "uid": "uid",
            "kind": {
                "kind": "Deployment"
            },
            "object": {
                "metadata": {
                    "labels": {
                        "company": "cloudserv.ca"
                    }
                },
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "container",
                                    "image": "docker.io/steveszabo/webapp:v1.1.2",
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
        response = requests.post(url="http://192.168.2.180:8443/mutate", json=request, timeout=10)
    except Exception as err:
        print(f"Unable to post: [{err}]")
        sys.exit(1)

    if response.status_code != 200:
        print(f"code: [{response.status_code}]")
        print(f"text: [{response.text}]")
        sys.exit(1)

    print(json.dumps(response.json()))
    sys.exit(0)
