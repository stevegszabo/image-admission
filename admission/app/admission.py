import os
import base64
import logging
import jsonpatch

from flask import Flask
from flask import request
from flask import jsonify

ADMISSION_CFG_LOG_LEVEL = os.environ.get("ADMISSION_LOG_LEVEL", "debug").lower()
ADMISSION_CFG_ALLOW_IMAGES_FILENAME = os.environ.get("ADMISSION_CFG_ALLOW_IMAGES", "/app/config/images.allowed")
ADMISSION_CFG_ALLOW_IMAGES = []

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

with open(ADMISSION_CFG_ALLOW_IMAGES_FILENAME) as handle:
    for image in handle:
        controller.logger.debug(f"Adding allow image: [{image.rstrip()}]")
        ADMISSION_CFG_ALLOW_IMAGES.append(image.rstrip())


def respond(allowed, uid, message, patch=None):
    response = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed,
            "status": {"message": message}
        }
    }

    if patch:
        response["response"]["patchType"] = "JSONPatch"
        response["response"]["patch"] = base64.b64encode(patch.to_string().encode("utf-8")).decode("utf-8")
    return jsonify(response)


@controller.route(rule="/mutate", methods=["POST"])
def mutate():
    request_json = request.get_json()
    request_kind = request_json["request"]["kind"]["kind"]
    request_name = request_json["request"]["name"]
    request_namespace = request_json["request"]["namespace"]
    request_operation = request_json["request"]["operation"]
    request_uid = request_json["request"]["uid"]
    request_patch_ops = []

    controller.logger.debug(f"Mutation kind: [{request_kind}]")
    controller.logger.debug(f"Mutation name: [{request_name}]")
    controller.logger.debug(f"Mutation namespace: [{request_namespace}]")
    controller.logger.debug(f"Mutation operation: [{request_operation}]")
    controller.logger.debug(f"Mutation uid: [{request_uid}]")

    if request_kind == "Deployment" and request_operation == "CREATE":
        for request_container in request_json["request"]["object"]["spec"]["template"]["spec"]["containers"]:
            controller.logger.debug(f"Validating image: [{request_container['image']}]")
            if request_container["image"] not in ADMISSION_CFG_ALLOW_IMAGES:
                controller.logger.debug(f"Rejecting image: [{request_container['image']}]")
                return respond(allowed=False, uid=request_uid, message=f"Rejected: {request_name}, image is not allowed: {request_container['image']}")

    if 'labels' not in request_json["request"]["object"]["metadata"]:
        request_patch_ops.append({"op": "add", "path": "/metadata/labels", "value": {}})
    request_patch_ops.append({"op": "add", "path": "/metadata/labels/mutated", "value": request_name})
    return respond(allowed=True, uid=request_uid, message=f"Mutated: {request_name}", patch=jsonpatch.JsonPatch(request_patch_ops))


@controller.route(rule="/validate", methods=["POST"])
def validate():
    request_json = request.get_json()
    request_uid = request_json["request"]["uid"]
    request_name = request_json["request"]["name"]
    return respond(allowed=True, uid=request_uid, message=f"Validated: {request_name}")


@controller.route(rule="/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    controller.run(host="0.0.0.0", port=8443)
