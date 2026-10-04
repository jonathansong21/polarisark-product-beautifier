#!/usr/bin/env python3
"""Submit one image edit; leave QA, corrections and final naming to the host."""

import argparse
import base64
import binascii
import io
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid


class EditError(Exception):
    def __init__(self, code, message, scope="item", status="failed", **details):
        self.result = dict(status=status, code=code, message=message,
                           scope=scope, **details)


def config_path():
    return Path.home() / ".config/polarisark-product-beautifier/config.yaml"


def read_config():
    path = config_path()
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        raise EditError("dependency_missing", "读取配置需要 PyYAML。", "batch")

    class ConfigLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str) or key in result:
                raise ValueError("Invalid or duplicate configuration key")
            result[key] = loader.construct_object(value_node)
        return result

    ConfigLoader.add_constructor("tag:yaml.org,2002:map", mapping)
    try:
        config = yaml.load(path.read_text(encoding="utf-8"), Loader=ConfigLoader)
    except (OSError, UnicodeError, yaml.YAMLError, ValueError):
        raise EditError("config_invalid", "config.yaml 无法读取或 YAML 无效。", "batch")
    if not isinstance(config, dict):
        raise EditError("config_invalid", "config.yaml 必须是字段映射。", "batch")
    if config.get("backend", "host") not in ("host", "api"):
        raise EditError("config_invalid", "backend 必须为 host 或 api。", "batch")
    return config


def api_settings(config, model_override=None):
    api = config.get("api", {})
    if not isinstance(api, dict):
        raise EditError("config_invalid", "api 必须是字段映射。", "batch")
    base_url = api.get("base_url")
    model = model_override if model_override is not None else api.get("model")
    key_env = api.get("api_key_env", "BEAUTIFIER_API_KEY")
    if not all(isinstance(value, str) and value.strip()
               for value in (base_url, model, key_env)):
        raise EditError("config_missing", "API 需要 base_url、model 和密钥环境变量名。", "batch")
    base_url, model, key_env = base_url.strip(), model.strip(), key_env.strip()
    try:
        parsed = urlsplit(base_url)
        parsed.port
    except ValueError:
        raise EditError("config_invalid", "base_url 不是有效根地址。", "batch")
    # HTTP is only allowed for loopback development and mock tests.
    if (not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment
            or not (parsed.scheme == "https" or
                    (parsed.scheme == "http" and parsed.hostname in
                     ("localhost", "127.0.0.1", "::1")))):
        raise EditError("config_invalid", "base_url 需要无内嵌凭据的 HTTPS 根地址。", "batch")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
        raise EditError("config_invalid", "api_key_env 必须为合法环境变量名。", "batch")
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise EditError("key_missing", "本地密钥环境变量未设置。", "batch")
    return base_url.rstrip("/"), model, key


def image_info(raw):
    from PIL import Image

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            fmt, size = image.format, image.size
    except (OSError, ValueError, Image.DecompressionBombError):
        raise EditError("image_invalid", "图片无法解码或文件不完整。")
    if fmt not in ("PNG", "JPEG", "WEBP"):
        raise EditError("image_invalid", "只支持 PNG、JPEG、WebP 图片。")
    return fmt.lower(), size


def edit(args, config, prompt):
    try:
        import requests
        from PIL import Image  # Validate dependencies before submitting a paid request.
    except ImportError:
        raise EditError("dependency_missing", "API 编辑需要 requests 和 Pillow。", "batch")
    base_url, model, key = api_settings(config, args.model)
    if not prompt.strip():
        raise EditError("prompt_missing", "标准输入中缺少编辑 Prompt。")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise EditError("parameter_invalid", "timeout 必须为有限正数。")
    expected_size = None
    if args.size and args.size != "auto":
        if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", args.size):
            raise EditError("parameter_invalid", "size 必须为 auto 或 WIDTHxHEIGHT。")
        expected_size = tuple(map(int, args.size.split("x")))
    paths = [Path(args.image)] + [Path(path) for path in args.reference]
    uploads = []
    try:
        for index, path in enumerate(paths):
            raw = path.read_bytes()
            fmt, size = image_info(raw)
            if index == 0:
                target_size = size
            filename = ("target" if index == 0 else "reference_" + str(index)) + "." + fmt
            uploads.append(("image[]", (filename, raw, "image/" + fmt)))
        if args.mask:
            raw = Path(args.mask).read_bytes()
            fmt, size = image_info(raw)
            with Image.open(io.BytesIO(raw)) as mask:
                has_alpha = "A" in mask.getbands()
            if fmt != "png" or size != target_size or not has_alpha:
                raise EditError("mask_invalid", "蒙版必须为含 alpha 的 PNG，尺寸与原图相同。")
            uploads.append(("mask", ("mask.png", raw, "image/png")))
        out_dir = Path(args.out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        # Reserve a new candidate before calling the API; never overwrite a file.
        reserve = out_dir / ("candidate_" + uuid.uuid4().hex + ".part")
        with reserve.open("xb"):
            pass
    except OSError:
        raise EditError("file_error", "无法读取输入图或创建候选文件。")
    payload = {"model": model, "prompt": prompt, "n": "1"}
    for name in ("size", "quality", "output_format"):
        value = getattr(args, name)
        if value is not None:
            payload[name] = value
    try:
        with requests.Session() as session:
            # No implicit .netrc credentials, host API settings or automatic retries.
            session.trust_env = False
            try:
                response = session.post(
                    base_url + "/images/edits", data=payload, files=uploads,
                    headers={"Authorization": "Bearer " + key},
                    timeout=(10, args.timeout), allow_redirects=False)
            except requests.RequestException:
                raise EditError("request_unknown", "调用中断；不能确认是否已生成或收费，勿自动重提。",
                                status="unknown")
            if response.status_code != 200:
                code = response.status_code
                scope = "batch" if code in (202, 401, 402, 403, 404, 429) or 300 <= code < 400 or code >= 500 else "item"
                raise EditError("http_error", "编辑接口返回错误；不自动重试或切换接口。",
                                scope, "unknown" if code in (202, 408) or code >= 500 else "failed", http_status=code)
            try:
                body = response.json()
                data = body["data"]
                if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
                    raise ValueError("Expected one image")
                item = data[0]
                if isinstance(item.get("b64_json"), str) and item["b64_json"]:
                    raw = base64.b64decode(item["b64_json"], validate=True)
                elif isinstance(item.get("url"), str):
                    image_url = urlsplit(item["url"])
                    if (image_url.scheme != "https" or not image_url.hostname
                            or image_url.username or image_url.password):
                        raise ValueError("Invalid image URL")
                    downloaded = session.get(item["url"], timeout=(10, args.timeout))
                    downloaded.raise_for_status()
                    raw = downloaded.content
                else:
                    raise ValueError("Missing image")
            except (ValueError, KeyError, TypeError, binascii.Error, requests.RequestException):
                raise EditError("result_unknown", "已提交编辑，但无法获取图片；勿重复提交生成。",
                                status="unknown")
            fmt, size = image_info(raw)
            if expected_size is not None and size != expected_size:
                raise EditError("size_mismatch", "返回图片未达到指定的实际像素尺寸。",
                                width=size[0], height=size[1])
            if args.output_format and fmt != args.output_format:
                raise EditError("format_mismatch", "返回图片格式与要求不符。")
            output = reserve.with_suffix("." + fmt)
            # Exclusive creation also protects against a collision at the final suffix.
            with output.open("xb") as stream:
                try:
                    stream.write(raw)
                except OSError:
                    output.unlink(missing_ok=True)
                    raise
            result = dict(status="candidate", image_path=str(output), width=size[0],
                          height=size[1], format=fmt, api_base_url=base_url,
                          requested_model=model, qa="pending")
            reported_model = body.get("model")
            if isinstance(reported_model, str):
                result["reported_model"] = reported_model.replace(key, "[REDACTED]")
            request_id = response.headers.get("x-request-id")
            if request_id:
                result["request_id"] = request_id.replace(key, "[REDACTED]")
            return result
    except OSError:
        raise EditError("file_error", "已提交编辑，但无法保存候选图片；勿重复提交生成。",
                        status="unknown")
    finally:
        reserve.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only inspect local configuration")
    parser.add_argument("--backend", choices=("host", "api"), help="Override this run only")
    parser.add_argument("--image", help="Original edit target")
    parser.add_argument("--reference", action="append", default=[], help="Associated authenticity reference")
    parser.add_argument("--out-dir", help="Directory for candidates awaiting QA")
    parser.add_argument("--model", help="Override the configured model for this run")
    parser.add_argument("--size", help="Provider-supported auto or WIDTHxHEIGHT")
    parser.add_argument("--quality", help="Provider-supported quality value")
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp"))
    parser.add_argument("--mask", help="Optional PNG alpha mask; requires provider support")
    parser.add_argument("--timeout", type=float, default=300, help="Read timeout in seconds")
    args = parser.parse_args(argv)
    try:
        config = {} if args.backend == "host" else read_config()
        backend = args.backend or config.get("backend", "host")
        if args.check:
            result = dict(status="configured", backend=backend, config_path=str(config_path()),
                          config_exists=config_path().exists(), remote_verified=False)
            if backend == "api":
                base_url, model, _ = api_settings(config, args.model)
                result.update(api_base_url=base_url, requested_model=model)
        else:
            if backend != "api":
                raise EditError("backend_host", "当前选择 host，请由宿主执行图像编辑。", "batch")
            if not args.image or not args.out_dir:
                raise EditError("input_missing", "API 编辑需要 --image 和 --out-dir。")
            result = edit(args, config, sys.stdin.read())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except EditError as exc:
        print(json.dumps(exc.result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
