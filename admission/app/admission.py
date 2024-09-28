import os
import json
import base64
import logging
import jsonpatch

from flask import Flask
from flask import request
from flask import jsonify

ADMISSION_CFG_ENFORCE_MODE = not os.environ.get("ADMISSION_AUDIT_MODE")
ADMISSION_CFG_LOG_LEVEL = os.environ.get("ADMISSION_LOG_LEVEL", "debug").lower()
ADMISSION_CFG_ALLOW_IMAGES_FILENAME = os.environ.get("ADMISSION_ALLOW_IMAGES", "images.allowed")
ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME = os.environ.get("ADMISSION_EXEMPT_NAMESPACES", "namespaces.exempt")
ADMISSION_CFG_MUTATE_WORKLOADS_FILENAME = os.environ.get("ADMISSION_MUTATE_WORKLOADS", "mutate.workloads")

ADMISSION_CFG_ALLOW_IMAGES = []
ADMISSION_CFG_EXEMPT_NAMESPACES = []
ADMISSION_CFG_MUTATE_WORKLOADS = {}

controller = Flask(__name__)
controller.logger.setLevel(level=logging.DEBUG)

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
controller.logger.debug(f"ADMISSION_CFG_MUTATE_WORKLOADS_FILENAME: [{ADMISSION_CFG_MUTATE_WORKLOADS_FILENAME}]")

with open(ADMISSION_CFG_EXEMPT_NAMESPACES_FILENAME) as handle:
    for item in handle:
        controller.logger.debug(f"Exempt namespace: [{item.rstrip()}]")
        ADMISSION_CFG_EXEMPT_NAMESPACES.append(item.rstrip())

with open(ADMISSION_CFG_ALLOW_IMAGES_FILENAME) as handle:
    for item in handle:
        controller.logger.debug(f"Allow image: [{item.rstrip()}]")
        ADMISSION_CFG_ALLOW_IMAGES.append(item.rstrip())

with open(ADMISSION_CFG_MUTATE_WORKLOADS_FILENAME) as handle:
    ADMISSION_CFG_MUTATE_WORKLOADS = json.load(handle)


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
        response["response"]["patch"] = base64.b64encode(patch).decode("utf-8")
        response["response"]["patchType"] = "JSONPatch"

    return jsonify(response)


@controller.route(rule="/mutate", methods=["POST"])
def mutate():
    request_json = request.get_json()
    request_kind = request_json["request"]["kind"]["kind"]
    request_name = request_json["request"]["name"]
    request_namespace = request_json["request"]["namespace"]
    request_operation = request_json["request"]["operation"]
    request_uid = request_json["request"]["uid"]

    controller.logger.debug(f"Mutating: [{request_kind}][{request_namespace}][{request_name}][{request_operation}][{request_uid}]")

    response = {
        "uid": request_uid,
        "allowed": True,
        "patches": None,
        "message": f"Mutated: [{request_kind}][{request_namespace}][{request_name}]"
    }

    if request_operation in ["CREATE", "UPDATE"] and request_kind == "Deployment":
        if request_namespace not in ADMISSION_CFG_EXEMPT_NAMESPACES:

            response["patches"] = []

            if "labels" not in request_json["request"]["object"]["metadata"]:
                response["patches"].append({"op": "add", "path": "/metadata/labels", "value": {}})
            response["patches"].append({"op": "add", "path": "/metadata/labels/mutated", "value": request_name})

            container_mutate_rule = ADMISSION_CFG_MUTATE_WORKLOADS.get(request_namespace)

            for index, request_container in enumerate(request_json["request"]["object"]["spec"]["template"]["spec"]["containers"]):
                container_name = request_container["name"]
                container_image = request_container["image"]
                controller.logger.info(f"Detected container image: [{container_name}][{container_image}]")

                if container_mutate_rule and container_image == container_mutate_rule["deploy-image"]:
                    container_patch_path = f"/spec/template/spec/containers/{index}/image"
                    container_patch_value = container_mutate_rule["mutate-image"]
                    response["patches"].append({"op": "replace", "path": container_patch_path, "value": container_patch_value})
                    controller.logger.info(f"Mutating container image: [{container_patch_path}][{container_patch_value}]")

    return respond(**response)


@controller.route(rule="/validate", methods=["POST"])
def validate():
    request_json = request.get_json()
    request_kind = request_json["request"]["kind"]["kind"]
    request_name = request_json["request"]["name"]
    request_namespace = request_json["request"]["namespace"]
    request_operation = request_json["request"]["operation"]
    request_uid = request_json["request"]["uid"]

    controller.logger.debug(f"Validating: [{request_kind}][{request_namespace}][{request_name}][{request_operation}][{request_uid}]")

    response = {
        "uid": request_uid,
        "allowed": True,
        "message": f"Validated: [{request_kind}][{request_namespace}][{request_name}]"
    }

    if request_operation in ["CREATE", "UPDATE"] and request_kind == "Deployment":
        if request_namespace not in ADMISSION_CFG_EXEMPT_NAMESPACES:

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
