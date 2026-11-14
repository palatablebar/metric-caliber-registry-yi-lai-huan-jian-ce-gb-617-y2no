"""演示账号与种子数据：星野零售 · 指标体系组。

口径规模与 batch-plan「seed」一致：
  48 个指标（5 处同名不同口径）、12 张报表（4 张核心）、1 个 3 节点依赖环、6 张待审批变更单。
指标 DSL 与报表引用关系是「算法 A 解析 + 算法 B 环/冲突/影响面」的真实输入。
"""

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@metricreg.io", "林可 · 指标管理员", "admin"),
    ("analyst@metricreg.io", "周棠 · 指标专员", "analyst"),
    ("viewer@metricreg.io", "陈默 · 报表只读", "viewer"),
]

ORG = "星野零售 · 指标体系组"

# (code, name, domain, tier, unit, owner, dsl_text, description)
METRICS = [
    # ---- 交易 15 ----
    (
        "gmv", "GMV", "trade", "core", "元", "林可",
        "gmv = sum(dwd.order.amount) where order_status = 'paid' group by dt",
        "已支付订单金额合计；不含退款，月会口径争议点之一。",
    ),
    (
        "gmv_net", "GMV", "trade", "core", "元", "周棠",
        "gmv_net = sum(dwd.order.amount) - sum(dwd.refund.amount) where order_status = 'paid' group by dt",
        "扣减退款后的净 GMV；与 gmv 同名但口径不同，长期未对齐。",
    ),
    (
        "order_cnt", "支付订单数", "trade", "core", "单", "林可",
        "order_cnt = count(dwd.order.id) where order_status = 'paid' group by dt",
        "已支付订单笔数。",
    ),
    (
        "aov", "客单价", "trade", "normal", "元", "苏敏",
        "aov = avg(dwd.order.amount) where order_status = 'paid' group by dt",
        "支付订单均价，按订单口径。",
    ),
    (
        "ticket_size", "客单价", "trade", "normal", "元", "何川",
        "ticket_size = avg(dwd.order.gross_amount) where order_status = 'paid' group by dt",
        "另一份客单价，用的是毛额字段，与 aov 同名不同字段。",
    ),
    (
        "refund_amt", "退款金额", "trade", "normal", "元", "周棠",
        "refund_amt = sum(dwd.refund.amount) where refund_status = 'done' group by dt",
        "已完成退款金额。",
    ),
    (
        "refund_rate", "退货率", "trade", "normal", "%", "周棠",
        "refund_rate = avg(dwd.refund.ratio) where refund_status = 'done' group by dt",
        "按退款记录的比例字段平均。",
    ),
    (
        "refund_rate_alt", "退货率", "trade", "normal", "%", "苏敏",
        "refund_rate_alt = sum(dwd.refund.ratio) where refund_status = 'done' group by dt",
        "另一份退货率按单量计数，与 refund_rate 同名不同算法。",
    ),
    (
        "net_revenue", "净营收", "trade", "core", "元", "林可",
        "net_revenue = sum(@gmv) - sum(dwd.refund.amount) where refund_status = 'done' group by dt",
        "引用 GMV 再扣退款。",
    ),
    (
        "pay_rate", "支付转化率", "trade", "normal", "%", "何川",
        "pay_rate = avg(dwd.order.pay_ratio) group by dt",
        "下单到支付的比例。",
    ),
    (
        "cancel_rate", "取消率", "trade", "normal", "%", "何川",
        "cancel_rate = avg(dwd.order.cancel_ratio) group by channel",
        "按渠道统计的取消比例。",
    ),
    (
        "item_per_order", "客单件数", "trade", "normal", "件", "苏敏",
        "item_per_order = avg(dwd.order.item_count) where order_status = 'paid'",
        "每笔订单商品件数。",
    ),
    (
        "repeat_amt", "复购金额", "trade", "normal", "元", "林可",
        "repeat_amt = sum(@gmv) where is_repurchase = 1 group by dt",
        "复购订单贡献的 GMV。",
    ),
    (
        "channel_gmv", "渠道GMV", "trade", "normal", "元", "周棠",
        "channel_gmv = sum(@gmv) group by channel",
        "按渠道拆分的 GMV。",
    ),
    (
        "order_gross", "订单毛额", "trade", "normal", "元", "苏敏",
        "order_gross = sum(dwd.order.gross_amount) where order_status in ('paid', 'shipped')",
        "含已发货订单的毛额。",
    ),
    # ---- 流量 10 ----
    (
        "active_users", "活跃用户", "traffic", "core", "人", "何川",
        "active_users = distinct_count(dwd.user.id) where platform = 'app' group by dt",
        "App 端去重活跃用户。",
    ),
    (
        "active_users_app", "活跃用户", "traffic", "normal", "人", "苏敏",
        "active_users_app = distinct_count(dwd.user.id) where platform in ('app', 'mini') group by dt",
        "另一份活跃用户，字段相同但含小程序端，与 active_users 同名不同范围。",
    ),
    (
        "pv", "浏览量", "traffic", "normal", "次", "何川",
        "pv = count(traffic.visit.id) group by dt",
        "访问明细计数。",
    ),
    (
        "uv_web", "网站UV", "traffic", "normal", "人", "何川",
        "uv_web = distinct_count(traffic.web.uid) where platform = 'web' group by dt",
        "PC 网站去重访客。",
    ),
    (
        "search_uv", "搜索UV", "traffic", "normal", "人", "苏敏",
        "search_uv = distinct_count(traffic.search.uid) group by dt",
        "发生过搜索的去重用户。",
    ),
    (
        "bounce_rate", "跳出率", "traffic", "normal", "%", "何川",
        "bounce_rate = avg(traffic.session.bounce_ratio) group by dt",
        "单页会话占比。",
    ),
    (
        "session_cnt", "会话数", "traffic", "normal", "个", "苏敏",
        "session_cnt = count(traffic.session.id) group by dt",
        "会话明细计数。",
    ),
    (
        "app_launch", "App启动次数", "traffic", "normal", "次", "林可",
        "app_launch = count(traffic.launch.id) where platform = 'app' group by dt",
        "App 冷启动次数。",
    ),
    (
        "channel_uv", "渠道UV", "traffic", "normal", "人", "周棠",
        "channel_uv = distinct_count(traffic.visit.uid) group by channel",
        "按渠道拆分的去重访客。",
    ),
    (
        "page_depth", "页面深度", "traffic", "normal", "页", "何川",
        "page_depth = avg(traffic.session.page_count) group by platform",
        "单会话平均浏览页数。",
    ),
    # ---- 会员 7 ----
    (
        "member_cnt", "会员总数", "member", "core", "人", "陈默",
        "member_cnt = count(dwd.member.id) where member_level >= 1",
        "有效会员数。",
    ),
    (
        "new_member", "新增会员", "member", "normal", "人", "陈默",
        "new_member = count(dwd.member.id) where is_new = 1 group by dt",
        "当日新注册会员。",
    ),
    (
        "member_gmv", "会员GMV", "member", "normal", "元", "陈默",
        "member_gmv = sum(@gmv) where member_level >= 2 group by dt",
        "金卡及以上会员贡献 GMV。",
    ),
    (
        "member_repurchase", "会员复购率", "member", "normal", "%", "陈默",
        "member_repurchase = avg(dwd.member.repurchase_ratio) group by dt",
        "会员复购比例。",
    ),
    (
        "points_issued", "积分发放", "member", "normal", "分", "苏敏",
        "points_issued = sum(dwd.member.points_delta) where points_type = 'earn' group by dt",
        "积分获取合计。",
    ),
    (
        "coupon_used", "券核销数", "member", "normal", "张", "苏敏",
        "coupon_used = count(dwd.coupon.use_id) where coupon_status = 'used' group by dt",
        "优惠券核销笔数。",
    ),
    (
        "member_arpu", "会员ARPU", "member", "normal", "元", "陈默",
        "member_arpu = avg(dwd.member.paid_amount) group by member_level",
        "分等级会员人均消费。",
    ),
    # ---- 商品 7 ----
    (
        "sku_on_sale", "在售SKU", "goods", "normal", "个", "何川",
        "sku_on_sale = count(dwd.sku.id) where sku_status = 'on_sale'",
        "在售 SKU 数。",
    ),
    (
        "sku_stockout", "缺货SKU", "goods", "normal", "个", "何川",
        "sku_stockout = count(dwd.sku.id) where stock_qty = 0",
        "零库存 SKU 数。",
    ),
    (
        "gross_margin", "毛利率", "goods", "core", "%", "林可",
        "gross_margin = avg(dwd.order.gross_margin) where order_status = 'paid' group by dt",
        "按订单毛利字段平均。",
    ),
    (
        "gross_margin_v2", "毛利率", "goods", "normal", "%", "何川",
        "gross_margin_v2 = avg(dwd.sku.margin_ratio) group by category",
        "另一份毛利率按 SKU 维度，与 gross_margin 同名不同维度。",
    ),
    (
        "category_gmv", "品类GMV", "goods", "normal", "元", "周棠",
        "category_gmv = sum(@gmv) group by category",
        "按品类拆分的 GMV。",
    ),
    (
        "stock_turnover", "库存周转", "goods", "normal", "天", "苏敏",
        "stock_turnover = avg(dwd.sku.turnover_days) group by category",
        "库存周转天数。",
    ),
    (
        "price_index", "价格指数", "goods", "normal", "指数", "何川",
        "price_index = avg(dwd.sku.price_index) group by category",
        "品类价格指数。",
    ),
    # ---- 财务 6 ----
    (
        "revenue", "营业收入", "finance", "core", "元", "林可",
        "revenue = sum(dwd.finance.revenue) where period_type = 'month' group by dt",
        "财务口径营业收入。",
    ),
    (
        "cost_total", "营业成本", "finance", "core", "元", "周棠",
        "cost_total = sum(dwd.finance.cost) where period_type = 'month' group by dt",
        "财务口径营业成本。",
    ),
    (
        "gross_profit", "毛利额", "finance", "core", "元", "林可",
        "gross_profit = sum(@revenue) - sum(@cost_total) group by dt",
        "引用收入与成本两个指标的推导指标。",
    ),
    (
        "finance_tax", "税金", "finance", "normal", "元", "周棠",
        "finance_tax = sum(dwd.finance.tax) where period_type = 'month' group by dt",
        "当月税金。",
    ),
    (
        "cash_in", "现金流入", "finance", "normal", "元", "苏敏",
        "cash_in = sum(dwd.finance.cash_in) where period_type = 'month' group by dt",
        "经营现金流入。",
    ),
    (
        "ar_balance", "应收余额", "finance", "normal", "元", "陈默",
        "ar_balance = sum(dwd.finance.ar) where period_type = 'month' group by dt",
        "期末应收余额。",
    ),
    # ---- 依赖环 3（cycle_a → cycle_b → cycle_c → cycle_a）----
    (
        "cycle_a", "循环指标A", "finance", "normal", "元", "陈默",
        "cycle_a = sum(@cycle_b) group by dt",
        "历史遗留指标：引用 B，B 引用 C，C 又引用 A。",
    ),
    (
        "cycle_b", "循环指标B", "finance", "normal", "元", "陈默",
        "cycle_b = sum(@cycle_c) group by dt",
        "环上的第二环。",
    ),
    (
        "cycle_c", "循环指标C", "finance", "normal", "元", "陈默",
        "cycle_c = sum(@cycle_a) group by dt",
        "环上的第三环，回到 A。",
    ),
]

# (code, name, owner, is_core, weight, metric_codes, channel)
REPORTS = [
    ("r01", "经营日报", "林可", True, 3, ["gmv", "gmv_net", "aov", "order_cnt", "pay_rate"], "BI"),
    ("r02", "月会GMV看板", "林可", True, 3, ["gmv", "gmv_net", "refund_rate", "repeat_amt"], "BI"),
    ("r03", "财务月结报表", "周棠", True, 3, ["gmv_net", "aov", "revenue", "cost_total", "gross_profit"], "财务系统"),
    ("r04", "门店周报", "苏敏", False, 1, ["gmv", "order_gross", "ticket_size"], "BI"),
    ("r05", "渠道日报", "周棠", False, 1, ["aov", "channel_gmv", "channel_uv", "refund_rate_alt"], "BI"),
    ("r06", "会员月报", "陈默", False, 1, ["member_cnt", "member_gmv", "member_arpu", "new_member", "cycle_a"], "BI"),
    ("r07", "流量日报", "何川", False, 1, ["active_users", "active_users_app", "pv", "uv_web", "bounce_rate"], "BI"),
    ("r08", "商品结构看板", "何川", False, 1, ["gross_margin", "gross_margin_v2", "category_gmv", "stock_turnover"], "BI"),
    ("r09", "核心指标月会", "林可", True, 3, ["gross_margin", "revenue", "gross_profit", "member_cnt", "order_cnt"], "月会"),
    ("r10", "财务成本分析", "周棠", False, 1, ["cost_total", "finance_tax", "cash_in", "ar_balance", "cycle_c"], "财务系统"),
    ("r11", "会员运营周报", "陈默", False, 1, ["coupon_used", "points_issued", "member_repurchase"], "BI"),
    ("r12", "品类价格监控", "苏敏", False, 1, ["price_index", "sku_on_sale", "sku_stockout"], "电商后台"),
]

# (seed_key, change_kind, target_ref, metric_code, reason, requester, proposed_dsl)
CHANGE_REQUESTS = [
    (
        "seed-cr-1", "field_type", "dwd.order.amount", None,
        "dwd.order.amount 从 numeric 改为 decimal(18,2)，GMV 链路上游需要确认是否重算。",
        "analyst@metricreg.io", None,
    ),
    (
        "seed-cr-2", "caliber", "gmv_net", "gmv_net",
        "净 GMV 是否含退款，月会已经吵了三次，申请把 gmv_net 口径写死并停用 gmv。",
        "analyst@metricreg.io",
        "gmv_net = sum(dwd.order.amount) - sum(dwd.refund.amount) where order_status = 'paid' and refund_status = 'done' group by dt",
    ),
    (
        "seed-cr-3", "caliber", "refund_rate", "refund_rate",
        "退货率统一改为按单量计数口径（refund_rate_alt 的算法），并下线比例字段版本。",
        "analyst@metricreg.io",
        "refund_rate = count(dwd.refund.id) where refund_status = 'done' group by dt",
    ),
    (
        "seed-cr-4", "formula", "active_users", "active_users",
        "活跃用户口径要含小程序端，和 active_users_app 合并。",
        "analyst@metricreg.io",
        "active_users = distinct_count(traffic.visit.uid) where platform in ('app', 'mini') group by dt",
    ),
    (
        "seed-cr-5", "formula", "channel_gmv", "channel_gmv",
        "渠道日报要按新渠道主数据重算，维度值需要补 shop_offline。",
        "analyst@metricreg.io",
        "channel_gmv = sum(@gmv) where channel <> 'unknown' group by channel",
    ),
    (
        "seed-cr-6", "caliber", "gross_margin", "gross_margin",
        "毛利率统一到订单毛利字段，SKU 维度版本作为辅助口径保留。",
        "analyst@metricreg.io", None,
    ),
]

SEED_RUN_KEY = "seed-run-validate-1"
SEED_RUN_TRIGGER = "seed"
SEED_RUN_OPERATOR = "admin@metricreg.io"

SEED_AUDIT = [
    ("seed-audit-1", "admin@metricreg.io", "admin", "metric.create", "metric", {"code": "gmv"}),
    ("seed-audit-2", "analyst@metricreg.io", "analyst", "run.create", "run", {"run": SEED_RUN_KEY}),
]


def metric_map() -> dict[str, tuple]:
    return {item[0]: item for item in METRICS}


def report_metric_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for code, _name, _owner, _is_core, _weight, metric_codes, _channel in REPORTS:
        for metric_code in metric_codes:
            index.setdefault(metric_code, []).append(code)
    return index
