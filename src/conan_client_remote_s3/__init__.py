import functools
import json
import traceback

import boto3
from werkzeug.routing import Map, Rule, Submount
from werkzeug.wrappers import Request, Response
from werkzeug.wrappers.json import JSONMixin
from werkzeug.wsgi import responder

import wsgiadapter

from .logger import logger

SERVER_CAPS = set()
# SERVER_CAPS.add("revisions")
S3_PRESIGNED_EXPIRY = 3600


def fail_on_remaining(args):
    if args:
        raise RuntimeError(f"unknown query arguments: {args}")


class JSONRequest(JSONMixin, Request):
    pass


def json_response(data):
    return Response(json.dumps(data), mimetype="application/json")


@functools.lru_cache()
def s3_bucket(bucket_name):
    client = boto3.client("s3")
    region = client.get_bucket_location(Bucket=bucket_name).get("LocationConstraint", "us-east-1")

    return boto3.resource(
        "s3",
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=boto3.session.Config(
            s3=dict(addressing_style="virtual"),
            signature_version="s3v4",
        ),
    ).Bucket(bucket_name)


def bucket_from_request(request):
    return s3_bucket(request.environ["SERVER_NAME"])


def ep_ping(request):
    logger.debug("conan_client_remote_s3 ping")
    fail_on_remaining(request.args)
    return Response(
        headers=[
            ("X-Conan-Server-Capabilities", ",".join(sorted(SERVER_CAPS))),
        ],
    )


def ep_users_check_credentials(request):
    logger.debug("conan_client_remote_s3 users check_credentials")
    fail_on_remaining(request.args)
    return Response()


def ep_digest(request, path):
    logger.debug("conan_client_remote_s3 digest: %s", path)
    fail_on_remaining(request.args)

    bucket = bucket_from_request(request)

    digest = {}

    for k in ["conanmanifest.txt"]:
        key = f"{path}/{k}"

        try:
            bucket.Object(key).e_tag
        except bucket.meta.client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return Response(status=404)
            else:
                raise

        digest[k] = bucket.meta.client.generate_presigned_url(
            "get_object",
            Params=dict(Bucket=bucket.name, Key=key),
            ExpiresIn=S3_PRESIGNED_EXPIRY,
        )

    return json_response(digest)


def ep_download_urls(request, path):
    logger.debug("conan_client_remote_s3 download_urls %s", path)
    fail_on_remaining(request.args)

    bucket = bucket_from_request(request)

    return json_response({
        k.key[len(path) + 1:]: bucket.meta.client.generate_presigned_url(
            "get_object",
            Params=dict(Bucket=bucket.name, Key=k.key),
            ExpiresIn=S3_PRESIGNED_EXPIRY,
        )
        for k in bucket.objects.filter(Prefix=f"{path}/", Delimiter="/")
    })


def ep_snapshot(request, path):
    logger.debug("conan_client_remote_s3 snapshot %s", path)
    fail_on_remaining(request.args)

    bucket = bucket_from_request(request)

    # note: S3 e-tag is MD5 except of multi-part uploads which we do not do
    return json_response({
        k.key[len(path) + 1:]: bucket.Object(k.key).e_tag[1:-1]
        for k in bucket.objects.filter(Prefix=f"{path}/", Delimiter="/")
    })


def ep_upload_urls(request, path):
    logger.debug("conan_client_remote_s3 upload_urls %s %s", path, request.json)
    fail_on_remaining(request.args)

    bucket = bucket_from_request(request)

    return json_response({
        k: bucket.meta.client.generate_presigned_url(
            "put_object",
            Params=dict(
                Bucket=bucket.name,
                Key=f"{path}/{k}",
            ),
            ExpiresIn=S3_PRESIGNED_EXPIRY,
        )
        for k, v in request.json.items()
    })


def ep_search(request):
    logger.debug("conan_client_remote_s3 search %s", request.args)

    args = request.args.copy()
    pattern = args.pop("q", None)
    ignorecase = args.pop("ignorecase", True)

    fail_on_remaining(args)

    return json_response({"results": []})


def ep_path_search(request, path):
    logger.debug("conan_client_remote_s3 path search %s", request.args, path)
    fail_on_remaining(request.args)
    return json_response({})


URL_MAP = Map([
    Submount(
        "/v1",
        [
            Rule("/ping", endpoint=ep_ping),
            Rule("/users/check_credentials", endpoint=ep_users_check_credentials),
            Submount(
                "/conans",
                [
                    Rule("/search", endpoint=ep_search),
                    Rule("/<path:path>/search", endpoint=ep_path_search),
                    Rule("/<path:path>/digest", endpoint=ep_digest),
                    Rule("/<path:path>/download_urls", endpoint=ep_download_urls),
                    Rule("/<path:path>/upload_urls", endpoint=ep_upload_urls, methods=["POST"]),
                    Rule("/<path:path>", endpoint=ep_snapshot),
                ],
            )
        ],
    ),
])


@responder
def application(environ, start_response):
    logger.debug("\nconan_client_remote_s3.application %s", environ)
    # traceback.print_stack()
    request = JSONRequest(environ)
    urls = URL_MAP.bind_to_environ(environ)
    return urls.dispatch(
        lambda e, v: e(request, **v),
        catch_http_exceptions=True
    )


def create():
    return wsgiadapter.WSGIAdapter(application)
