import os
import base64
import logging
import jsonpatch
import jsonschema

from flask import Flask
from flask import request
from flask import jsonify

ADMISSION_CFG_ENFORCE_MODE = not os.environ.get("ADMISSION_AUDIT_MODE")
ADMISSION_CFG_LOG_LEVEL = os.environ.get("ADMISSION_LOG_LEVEL", "debug").lower()
ADMISSION_CFG_ALLOW_IMAGES_FILENAME = os.environ.get("ADMISSION_ALLOW_IMAGES", "images.allowed")
ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME = os.environ.get("ADMISSION_EXEMPT_NAMESPACES", "namespaces.exempt")
ADMISSION_CFG_ALLOW_IMAGES = []
ADMISSION_CFG_EXEMPT_NAMESPACES = []

controller = Flask(__name__)
controller.logger.setLevel(level=logging.DEBUG)

jsonschema.validate(instance={
    "name": "123"
}, schema={
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "http://cloudserv.ca/schemas/admission.json",
    "type": "object",
    "properties": {
        "name": {"type": "string"}
    }
})

if ADMISSION_CFG_LOG_LEVEL == "info":
    controller.logger.setLevel(level=logging.INFO)
elif ADMISSION_CFG_LOG_LEVEL == "warning":
    controller.logger.setLevel(level=logging.WARNING)
elif ADMISSION_CFG_LOG_LEVEL == "error":
    controller.logger.setLevel(level=logging.ERROR)
elif ADMISSION_CFG_LOG_LEVEL == "critical":
    controller.logger.setLevel(level=logging.CRITICAL)

controller.logger.debug(f"ADMISSION_CFG_ENFORCE_MODE: [{ADMISSION_CFG_ENFORCE_MODE}]")
controller.logger.debug(f"ADMISSION_CFG_LOG_LEVEL: [{ADMISSION_CFG_LOG_LEVEL}]")
controller.logger.debug(f"ADMISSION_CFG_ALLOW_IMAGES_FILENAME: [{ADMISSION_CFG_ALLOW_IMAGES_FILENAME}]")
controller.logger.debug(f"ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME: [{ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME}]")

with open(ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME) as handle:
    for item in handle:
        controller.logger.debug(f"Exempt namespace: [{item.rstrip()}]")
        ADMISSION_CFG_EXEMPT_NAMESPACES.append(item.rstrip())

with open(ADMISSION_CFG_ALLOW_IMAGES_FILENAME) as handle:
    for item in handle:
        controller.logger.debug(f"Allow image: [{item.rstrip()}]")
        ADMISSION_CFG_ALLOW_IMAGES.append(item.rstrip())


def respond(allowed, uid, message, patches=None):
    response = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed,
            "status": {"message": message}
        }
    }

    if patches:
        patch = jsonpatch.JsonPatch(patches).to_string().encode("utf-8")
        response["response"]["patchType"] = "JSONPatch"
        response["response"]["patch"] = base64.b64encode(patch).decode("utf-8")

    return jsonify(response)


@controller.route(rule="/mutate", methods=["POST"])
def mutate():
    request_json = request.get_json()
    request_kind = request_json["request"]["kind"]["kind"]
    request_name = request_json["request"]["name"]
    request_namespace = request_json["request"]["namespace"]
    request_operation = request_json["request"]["operation"]
    request_uid = request_json["request"]["uid"]

    controller.logger.debug(f"Mutation kind: [{request_kind}]")
    controller.logger.debug(f"Mutation name: [{request_name}]")
    controller.logger.debug(f"Mutation namespace: [{request_namespace}]")
    controller.logger.debug(f"Mutation operation: [{request_operation}]")
    controller.logger.debug(f"Mutation uid: [{request_uid}]")

    response = {
        "uid": request_uid,
        "allowed": True,
        "patches": None,
        "message": f"Mutated: [{request_kind}][{request_namespace}][{request_name}]"
    }

    if request_namespace not in ADMISSION_CFG_EXEMPT_NAMESPACES:
        if request_operation in ["CREATE", "UPDATE"]:
            if request_kind == "Deployment":
                response["patches"] = []
                if "labels" not in request_json["request"]["object"]["metadata"]:
                    response["patches"].append({"op": "add", "path": "/metadata/labels", "value": {}})
                response["patches"].append({"op": "add", "path": "/metadata/labels/mutated", "value": request_name})

    return respond(**response)


@controller.route(rule="/validate", methods=["POST"])
def validate():
    request_json = request.get_json()
    request_kind = request_json["request"]["kind"]["kind"]
    request_name = request_json["request"]["name"]
    request_namespace = request_json["request"]["namespace"]
    request_operation = request_json["request"]["operation"]
    request_uid = request_json["request"]["uid"]

    controller.logger.debug(f"Validation kind: [{request_kind}]")
    controller.logger.debug(f"Validation name: [{request_name}]")
    controller.logger.debug(f"Validation namespace: [{request_namespace}]")
    controller.logger.debug(f"Validation operation: [{request_operation}]")
    controller.logger.debug(f"Validation uid: [{request_uid}]")

    response = {
        "uid": request_uid,
        "allowed": True,
        "message": f"Validated: [{request_kind}][{request_namespace}][{request_name}]"
    }

    if request_namespace not in ADMISSION_CFG_EXEMPT_NAMESPACES:
        if request_operation in ["CREATE", "UPDATE"]:
            if request_kind == "Deployment":
                for request_container in request_json["request"]["object"]["spec"]["template"]["spec"]["containers"]:

                    if "requests" not in request_container["resources"]:
                        response["message"] += ": Rejected due to missing resources.requests element"
                        controller.logger.warning(response["message"])
                        if ADMISSION_CFG_ENFORCE_MODE:
                            response["allowed"] = False
                        return respond(**response)

                    if "limits" not in request_container["resources"]:
                        response["message"] += ": Rejected due to missing resources.limits element"
                        controller.logger.warning(response["message"])
                        if ADMISSION_CFG_ENFORCE_MODE:
                            response["allowed"] = False
                        return respond(**response)

                    if request_container["image"] not in ADMISSION_CFG_ALLOW_IMAGES:
                        response["message"] += f": Rejected due to invalid image: [{request_container['image']}]"
                        controller.logger.warning(response["message"])
                        if ADMISSION_CFG_ENFORCE_MODE:
                            response["allowed"] = False
                        return respond(**response)

    return respond(**response)


@controller.route(rule="/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    controller.run(host="0.0.0.0", port=8443)
