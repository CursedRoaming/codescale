# 码尺 CodeScale · 跨境选品数据台

> 外部账号（Kalodata 试用到期日、归谁、谁付钱）记在 `ACCOUNTS.md`。密码不在那里，也不在任何文件里。

一句话：**跑一遍，出一页行情看板加一份日报，数字从哪来能一条条查回去。**

自动的那一半是真的：`.github/workflows/daily.yml` 每天 20:00 会跑完并提交。
但**数据不会自己进来**——Kalodata 没有公开 API（见下），CSV 得有人放。
这两件事必须分开说，不然会以为配好了就万事大吉。

这是独立于 `紫竹/FDE` 新建的一套东西。取了她那套东西的**口径与页面语感**，没有取她的代码——
她的 `dashboard.js` 是 189 KB 单文件，数据以 `const D={...}` 的形式焊在渲染逻辑里，
改一次数据要重新生成整个文件，接不上任何自动更新。要自动更新，数据必须离开渲染层。

---

## 跑起来

```bash
python pipeline/run.py              # 今天
python pipeline/run.py --date 2026-11-20
python pipeline/run.py --dry        # 只打印不落盘
```

只用 Python 标准库。不装 pandas、不联网也能跑（本地样本源）。

改过 CSV 导入器之后跑一遍测试：

```bash
python -m unittest discover -s pipeline/tests -v     # 34 个用例
```

测四块：巴西数字格式与三套表头、单品链接判定、变化检测的阈值边界、规模刻度的算术。
这些地方算错了不会报错，只会静默给出错的数，所以规则和断言都写死在代码与测试里，
不靠运行时判断。改过任何一处都要重跑。

看页面两种方式：

- 直接双击 `index.html`（`data/latest.js` 是镜像，专门给这种情况兜底）
- 或者 `python -m http.server 8000`，开 `http://localhost:8000`（走 `data/latest.json`）

---

## 目录

```
index.html  app.js  theme.css        前端。无依赖、无构建、无框架
data/
  latest.json                        最新一份快照（真源）
  latest.js                          file:// 兜底镜像
  history/YYYY-MM-DD.json            每日不可变快照
  history/index.json                 归档索引
reports/
  YYYY-MM-DD.html                    当日日报（自包含，可直接微信发）
  YYYY-MM-DD.md                      微信短版
pipeline/
  run.py                             入口：采集 → 归一 → 去重 → 指标 → 落盘 → 报告
  config.json                        品牌、成本、数据源清单
  core/cost.py                       成本模型与保本价
  core/normalize.py                  规格/品牌/去重键
  core/metrics.py                    指标计算
  core/store.py                      落盘
  core/report.py                     日报渲染
  sources/base.py                    适配器接口 + HTTP + 读凭据
  sources/seed.py                    本地样本（当前唯一有数的一路）
  sources/kalodata.py                Kalodata CSV 导入（inbox/）
  tests/test_kalodata.py             CSV 导入：数字格式、表头、错位行
  tests/test_metrics.py              链接判定、变化检测、规模刻度
  sources/marketplaces.py            TK / Shopee / 美客多（未接入，原因写死）
  seed/market_expanded.json          75 条公开样本，随仓库走，保证克隆即可跑
  inbox/                             Kalodata 导出的 CSV 放这里，丢文件即读
    README.md                        导出怎么选格式、认哪些表头、会丢什么
.github/workflows/daily.yml          每天 20:00 北京时间自动跑并提交
```

---

## 加一个数据源

1. 在 `pipeline/sources/` 写一个 `fetch(cfg, ctx) -> Result`
2. 在 `pipeline/sources/__init__.py` 的 `REGISTRY` 里登记
3. 在 `pipeline/config.json` 的 `sources` 里加一条

适配器只负责产出**原始记录**，不许自己算指标、不许自己写文件。归一化与去重统一在
`core/normalize.py` 做，这样换平台时只改一个文件，页面和报告不用动。

---

## 现在的真实状态

| 数据源 | 状态 | 卡在哪 |
|---|---|---|
| 本地样本（75 条） | 已接入 | 采集日 2026-11-06，只能回放 |
| Kalodata | inbox 为空 | 无公开 API，从网页导出 CSV 放进 `pipeline/inbox/` |
| TikTok Shop | 未接入 | 需卖家授权或 Partner API |
| Shopee BR | 未接入 | 需 Open Platform 账号与企业资质 |
| Mercado Livre | 未接入 | 11-19 实测：站点元数据 200，商品搜索 403，需 access_token |

**可回溯率 9%（7/75）**。这一项 2026-11-20 查清了原因，比之前写的更糟：

75 条记录只对应 18 个链接，其中真指向具体商品的只有 7 个，其余是搜索列表页和店铺首页。
也就是说，**75 条里有 68 条点进去找不到这条价格的原处**。快照留存率同样是 0%。

原因不在「没存截图」，在源头：11-06 那批数据是按搜索页采的，抓的是列表里的价格，
但没有把每一条对应的商品链接存下来。要补，得重新采，一条一条拿单品 URL。
先补报告里用到的那 20 条即可，不必全量。

---

## 部署（已完成，2026-11-20）

线上地址：**https://cursedroaming.github.io/codescale/**
仓库：`CursedRoaming/codescale`（公开），Pages 走 `main` 分支根目录，`legacy` 构建。

已完成的三步，留档备查：

1. 建仓库 `codescale`，推 `main`
2. Settings → Pages → Source: `Deploy from a branch`，`main` / 根目录
3. `.nojekyll` 已在仓库里（不加它，下划线开头的路径会被 Jekyll 吞掉）

**没有配置任何 Secret。** 因为 Kalodata 没有 API，管线不向任何外部服务认证，
只读仓库里 `pipeline/inbox/` 的 CSV。早前那版写的 `KOLADATA_KEY` 已删掉，别再建。

`daily.yml` 每天 20:00（北京时间）自动跑，把 `data/` 与 `reports/` 的变更提交回去，
Pages 自动重新发布。**不需要服务器。**

两点要注意：

- GitHub 对「60 天内仓库无提交」的定时任务会暂停。`daily.yml` 自己每天提交一次，
  只要它还在跑就不会触发这条；一旦它被停，得手动点一次 `Run workflow` 唤醒。
- Actions 里的运行日志是公开的。所以**不要把任何 CSV 原件、账号信息放进仓库**，
  `ACCOUNTS.md` 与 `pipeline/inbox/*.csv` 已在 `.gitignore` 里。

---

## 口径（别改，改之前先看这一段）

- 产品：手工甲，10 片/套，单件 20g
- 到仓成本 R$ 19.83 = 采购 13.23 + 头程 3.60 + 仓储 3.00
- 不投流保本 R$ 29.70，投流保本 R$ 46.54
- **19.83 是自家 10 片手工甲的成本，不是 24 片机器甲的成本。**
  拿它减 24 片的市场价是错的，品类不同，这一步错了整份报告的方向都会反。
- 可比池只有一类：`spec==10` 或标题带手工/定制关键词。当前 4 条，中位 R$ 95.00。
  4 条不足以下定价结论，只能当上限参照。

成本口径取自客户成本测算表 NA-001~010 均值，加 D 2026-11-18 口述
（空运 180 BRL/kg × 20g = 3.60）。是表内测算，不是实际发生。

---

## Kalodata 这件事，单独说清楚

2026-11-19 实测三件，都跑过，不是推测：

| 查的 | 结果 |
|---|---|
| `koladata.com`（B 说的名字） | 四个子域全部连不上，DNS 不解析 |
| `www.kalodata.com`（正确名字） | HTTP 200 |
| `api.kalodata.com` / `open.kalodata.com` | 不解析，无公开 API |

所以：**它卖的是网页账号席位，不是接口。** 数据出口只有网页上的导出按钮。
「给个 API key 就能每天自动拉」这条路不存在，不是还没做，是没有。

现在的接法是 CSV 导入，用法见 `pipeline/inbox/README.md`。
2026-11-19 用两套表头（中文 / 葡语）+ 分号分隔 + 巴西数字格式做过端到端验证，
4 条测试数据成功进管线，可比池从 4 条涨到 6 条，10 片手工甲那条被正确识别。

要走真自动，只剩两条：让对方开商务 API，或者换一个有 API 的源。

---

## 这一版新加的两个东西

**一、本版变化检测**（`core/metrics.py` 的 `_delta`）

每天自动跑，源没接通时每次跑出来的数完全一样。若不承认这件事，就会每天发一份内容
相同的「新一期」给客户，那比不发更糟。

所以现在每份快照都会记录：条数变没变、商品增删了几个、价格动了几个、中位价动没动。
四样全没变就判定 `changed=False`，页面上出现一条琥珀色提示，报告里也照实写
「本版没有新数据」。归档页会给那些没变的日期打上「未变」标签。

阈值是 R$0.50，与异动表一致。中位价那一项也过同一阈值——否则会出现「判定有新数据，
但异动表一条都列不出来」的自相矛盾。

**二、规模刻度**（`core/cost.py` 的 `scale`）

B 要的是「提升百分之多少」这类数字。平台原来只能回答「这个价能不能保本」，
回答不了「要卖多少才够本」。

现在给两张表：售价 × 月单量 → 月净利，以及反过来的「要拿到目标月利需要多少单」。
核心结论是一句话：贴着保本线定价（R$29.90）单件只赚 0.13，要 23,077 单才够 R$3,000 月利；
抬到 R$39.90 单件 6.81，441 单就够。

**这是刻度，不是预测。** 单量是假设出来的横轴，不含退货、滞销、活动亏损与汇率波动。
代码注释、页面、报告三处都写死了这句，别删。

---

## 还没做的事

- AI 分析层（B 要的首页日报语）——排在最后，等数据稳定再说
- 销量的真实数据（`sold` / `gmv` 当前 100% 为空，B 要的「什么品爆了」全靠这个）
- 逐条商品链接的回填（现在 91% 的记录点进去找不到原处）
- 平台授权接口
- 用户自接账号
