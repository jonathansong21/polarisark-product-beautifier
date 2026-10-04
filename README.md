# Polarisark Product Beautifier

全品类商品实拍图白底精修 Skill。

它以商品原图为事实来源，将一张或多张商品实拍图独立处理为真实、明亮通透、材质分明的电商白底图，同时尽量保持原机位、商品结构、颜色、材质、Logo 和文字不变。

## 安装

### 方式一：npx 一键安装

使用 [Skills CLI 文档](https://skills.sh/docs/cli) 中的命令从 GitHub 安装：

```bash
npx skills add jonathansong21/polarisark-product-beautifier
```

默认安装到当前项目。希望全局使用时加上 `-g`：

```bash
npx skills add jonathansong21/polarisark-product-beautifier -g
```

只安装到 Codex 并跳过确认时：

```bash
npx skills add jonathansong21/polarisark-product-beautifier -g -a codex -y
```

### 方式二：通过 Git 克隆

适合希望自行管理 skill 文件并通过 `git pull` 更新的场景。以下示例将 skill 全局安装到 Codex：

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/jonathansong21/polarisark-product-beautifier.git \
  ~/.codex/skills/polarisark-product-beautifier
```

如果要安装到当前项目，可将目标目录替换为 `.agents/skills/polarisark-product-beautifier`。

### 方式三：手动安装

下载并解压本仓库后，在仓库根目录执行以下命令，将完整 skill 文件复制到 Codex 全局目录：

```bash
mkdir -p ~/.codex/skills/polarisark-product-beautifier
cp -R SKILL.md agents references scripts ~/.codex/skills/polarisark-product-beautifier/
```

手动安装须包含 `SKILL.md`、`agents`、`references` 和 `scripts`，以保留界面元数据、精修指南和 API 调用能力；用户配置独立保存在包目录外，不随安装复制。

## 使用

在支持 Agent Skills 的工具中调用：

```text
$polarisark-product-beautifier
```

然后提供一张或多张商品原图。可以额外提供明确关联的色卡、产品事实档案或参考图，用于确认颜色和结构；这些辅助资料不会被精修或作为成片交付。

## 生图方式与本地配置

默认使用宿主 Agent 的图像编辑能力，无需 API 配置。也可明确要求使用兼容 OpenAI Images 编辑协议的 API，或把本地配置中的默认方式设为 `api`。两种方式共用商品真实性、QA、纠正和交付规则，失败时不静默切换。

用户配置固定为 `~/.config/polarisark-product-beautifier/config.yaml`，独立于 skill 安装目录，更新或重装包不修改该文件。API 地址、模型和密钥环境变量名由用户配置；实际密钥不写入包或 YAML。本次指定的方式和参数优先，不自动改写默认配置。

配置格式、API 依赖、调用与兼容范围见 [API 编辑说明](references/api-edit.md)。API 模式仅支持上传原图的同步编辑接口，不把聊天兼容或纯文生图视为图像编辑支持。服务商和模型的实际能力及费用需单独确认。

## 处理能力

- 按输入顺序逐张独立精修，单张失败不影响其他图片继续处理。
- 清理确认属于拍摄环境的灰尘、指纹、支架、背景残留和色污染。
- 校正曝光、白平衡、轻微倾斜、畸变、边缘和阴影问题。
- 根据实际材质增强织物、皮革、塑料、玻璃、金属、木质、陶瓷、包装等区域的纹理、反射、光泽和体积感。
- 默认输出纯白 `#FFFFFF` 背景、`1:1` 构图、均衡留白和极轻自然接触阴影；用户明确指定的比例或阴影要求优先。
- 对照原图执行结构与材质 QA，必要时对单张图片最多进行 3 次定向纠正。

## 真实性边界

必须保持：

- 商品仍为同一商品和同一 SKU。
- 原机位、透视、朝向、轮廓、比例和刚性几何不变。
- 部件数量、顺序、连接关系、孔位、接口、Logo 和可见文字不变。
- 真实磨损、划痕、褶皱、纹理和制造特征不被擅自抹除。

链条、绳带、线材、肩带和布料等柔性部件可以整理为自然陈列，但数量、拓扑、连接点和真实长度不能改变；用户要求“摆放不变”时，柔性部件的相对位置也保持不变。

不用于场景合成、广告创意图、模特图、非白底背景、SKU 换色、换款、商品重设计、配件增删、Logo 或标签重绘，也不交付透明背景版本、蒙版或其他中间资产。

## 交付内容

每张输入图都会对应一个结果：

- 合格：白底精修成片和一句处理摘要。
- 失败：具体失败项、风险和必要补充材料，不把失败候选标记为合格成片。

同时返回整批成功/失败数量，必要时单列结果未知和未处理项，并保持输入与输出或失败说明一一对应。

合格成片统一使用 `{原图文件名主体}_beautified.{实际扩展名}`，例如 `photo.jpg` 的 PNG 成片为 `photo_beautified.png`；没有可用原图文件名时，按目标图输入顺序使用 `image_001_beautified.png`，辅助参考图不参与编号，失败不会改变后续序号。

重名时追加 `_02`、`_03` 等编号，不覆盖原图或已有文件；扩展名匹配实际格式，文件名不包含纠正轮次。命名不要求提供品牌或 SKU，交付渠道无法落实实际文件名时会明确说明。

## 目录结构

```text
polarisark-product-beautifier/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── retouching-guide.md
│   └── api-edit.md
└── scripts/
    ├── image_api.py
    └── requirements.txt
```

`SKILL.md` 是安装入口；精修指南、API 说明与调用脚本随包安装，实际 `config.yaml` 留在用户配置目录。API 脚本只生成待 QA 候选图，由宿主检查后命名交付。
