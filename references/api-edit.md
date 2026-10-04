# API 编辑通道

仅在选用 API、配置 API 或诊断 API 问题时读取。宿主通道不需要安装以下依赖。

## 兼容范围

支持同步的 OpenAI Images 编辑协议：向配置根地址下的 `/images/edits` 发出 multipart 请求，上传当前原图和明确关联的参考图，接收 `data[0].b64_json` 或 HTTPS `data[0].url`。不支持仅有 `/images/generations` 的纯文生图服务、聊天接口生图、异步任务协议或其他响应结构。不能把“兼容 OpenAI”宣传语当作图像编辑能力证明。

接入时依据服务商文档确认：模型具有原图编辑能力、所需参考图数量可接受、尺寸/质量/格式/蒙版参数受支持。脚本不探测付费能力，不枚举或猜测模型，也不把官方模型限制套给第三方服务。

官方协议对照：[图像编辑接口](https://developers.openai.com/api/reference/python/resources/images/methods/edit)。第三方的参数限制、实际能力和计费以该服务文档及实际结果为准。蒙版只提供编辑区域引导，不保证商品结构或区域逐像素不变；仍须视觉 QA。

## 本地 config.yaml

唯一默认路径：`~/.config/polarisark-product-beautifier/config.yaml`，其中 `~` 指执行脚本的用户主目录，与安装位置、当前项目及宿主名称无关。同一机器的宿主可共用；换机器需自行配置。不要在 skill 安装目录寻找同名文件。

首次选择 API 且配置不存在时，说明路径、第三方服务和所需字段，引导用户建立配置；用户要求代为配置时可创建。已有文件只按用户明确要求修改，不整体覆盖。当前服务未确定时不要写入示例占位值作为可用配置。

以下只是格式示例，需替换接口地址和模型名称：

```yaml
backend: api
api:
  base_url: https://your-provider.example/v1
  model: your-image-edit-model
  api_key_env: BEAUTIFIER_API_KEY
```

- `backend` 可为 `host` 或 `api`，缺省为 `host`；有密钥不代表选择了 API。当前任务的明确选择优先，不回写配置。
- API 模式需有效的 `base_url`、`model` 和密钥环境变量；`api_key_env` 缺省为 `BEAUTIFIER_API_KEY`。模型可由当前任务的明确要求覆盖。
- `base_url` 是包含服务所需路径前缀的根地址，例如 `/v1`，不要填写完整 `/images/edits` 地址。使用 HTTPS，不内嵌用户名、密码或查询参数；本地模拟仅允许 loopback HTTP。
- 密钥从所指定的本地环境变量读取，不写入 YAML、Prompt、命令参数或日志；不借用宿主的 `OPENAI_API_KEY`、API 地址或 `.netrc` 凭据。脚本不读取代理环境变量。
- 配置缺失且未选择 API 时采用 `host`；API 配置缺失、无效或密钥缺失时阻止请求。已存在的不可读、空文件、重复字段或无效 YAML 报错，不当作缺失；本次明确 `host` 时无需读取配置。
- 安装、更新、重装和卸载 skill 不修改或删除本地配置。脚本只读配置；未知新增字段保留，可选字段通过读取默认值兼容，不自动回写或迁移。缺少必填字段或不兼容时说明所需修改，不降级到其他通道。

## 调用

需要 Python 3.9+，建议使用带现代 OpenSSL 的 Python 虚拟环境。以下命令在已激活的虚拟环境和所安装的 skill 目录执行；实际调用也可使用脚本绝对路径。仅 API 通道需要依赖：

```bash
python3 -m pip install -r scripts/requirements.txt
python3 scripts/image_api.py --check
python3 scripts/image_api.py --check --backend api
```

`--check` 只检查本地配置及密钥是否存在，不联网、不显示密钥、不证明服务可用。显式 `--backend api` 覆盖本次选择；配置默认 API 时可省略。不要因为只是安装依赖就自动执行生成。

宿主用其进程调用工具把内部 Prompt 直接送入标准输入，不建立 Prompt 文件或输出到日志。例如参数形状：

```bash
python3 scripts/image_api.py --backend api \
  --image /path/to/original.png \
  --reference /path/to/authenticity-reference.png \
  --out-dir /path/to/workspace/tmp/beautifier
```

`--reference` 可重复，无参考图时省略；不要上传批次其他目标图。脚本始终把 `--image` 放在第一张，随后按参数顺序上传参考图；Prompt 明确各自角色。首轮和每轮纠正均重新传入同一原始图片，由宿主保留累计纠正约束和次数。

可按用户要求和服务能力传入 `--model`、`--size WIDTHxHEIGHT`、`--quality`、`--output-format png|jpeg|webp`、`--mask`。可选参数不默认发送，不发送模型特有的 `input_fidelity` 等参数。缺省仅发送模型、Prompt、图片和 `n=1`；不要用移除硬性参数来绕过接口拒绝。蒙版须为含 alpha 的 PNG，尺寸与原图一致，服务也必须支持。

一次执行仅有一次生成 POST，没有自动重试，拒绝 API POST 重定向。默认连接超时 10 秒、读取超时 300 秒，可用 `--timeout` 指定有限正数。URL 图片下载不附带 API 密钥或 `.netrc` 凭据。

## 结果、QA 与失败

标准输出为一条 JSON，成功退出码为 0；错误退出码为 1。参数用法错误由命令行解析器报告。

- `status=configured`：仅完成本地配置检查，`remote_verified=false`。
- `status=candidate`：取得可解码图片，返回 `image_path`、实际 `width`/`height`/`format`、接口根地址、`requested_model` 和 `qa=pending`。服务明确返回时才附带 `reported_model` 或请求 ID；请求模型不是实际模型证明。
- `status=failed|unknown`：返回简短 `code`、`message` 和 `scope`，必要时包含 HTTP 状态或实际尺寸，不输出响应正文、Prompt 或密钥。

候选名称为 `candidate_<随机编号>.<实际格式>`，独占创建，不覆盖原图或其他文件；脚本不创建最终 `beautified` 名称。`--size` 为具体尺寸时检查实际像素，指定格式时检查实际文件格式，错误则不输出候选。脚本不评定商品真实性、纯白背景或视觉质量。宿主仍须按 SKILL.md 对照原图完成 QA，通过后再落实最终命名；交付后清理候选及中间资产，失败候选不交付。

- `scope=item`：输入图、蒙版、参数或单项结果错误。标记本项并继续后续目标；结果未知单独说明，不能当作“未生成”。
- `scope=batch`：配置/依赖/密钥缺失，鉴权、余额、限流、接口不兼容、重定向或服务整体错误。停止剩余队列并列出未处理项。
- 超时、连接中断、HTTP 202/408/5xx 或生成后结果获取/保存失败可能已经生成或收费。不得自动重提生成，不将“调用错误不计为纠正”解释为无限重试额度。用户授权处理后才恢复，已有候选优先检查，不重置纠正上限；不静默更换服务商、模型或通道。

每张正常生成最多首轮加 3 次纠正；每次都可能产生第三方费用。预算更紧时按用户明确限制提前停止。API 返回不合格图片只能由宿主在 QA 后按已获授权进行定向纠正；脚本不会自行循环。
