import sys
import json
import requests

if __name__ == "__main__":

    create_deployment = {
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
                                    "name": "container-01",
                                    "image": "docker.io/steveszabo/webapp:v1.1.2",
                                    "resources": {
                                        "requests": {},
                                        "limits": {}
                                    }
                                },
                                {
                                    "name": "container-02",
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
        response = requests.post(url="http://127.0.0.1:8443/mutate", json=create_deployment, timeout=10)
    except Exception as err:
        print(f"Unable to post: [{err}]")
        sys.exit(1)

    if response.status_code != 200:
        print(f"code: [{response.status_code}]")
        print(f"text: [{response.text}]")
        sys.exit(1)

    print(json.dumps(response.json()))
    sys.exit(0)