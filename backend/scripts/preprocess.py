"""
数据预处理脚本 v3.0 — 电商数据集（5表星型模型）

表结构:
  1. customers       — 客户维度表 (100行)
  2. products        — 商品维度表 (40行)
  3. orders          — 订单事实表 (300行, 含NULL)
  4. monthly_targets — 月度销售目标 (192行)
  5. refunds         — 退款记录表 (25行, 稀疏)

复杂度:
  - INNER JOIN / LEFT JOIN / 多表关联
  - 子查询 / CTE / 窗口函数 / HAVING
  - NULL值处理 / CASE WHEN
  - 同比环比 / 达成率

使用方法:
  python scripts/preprocess.py
"""
import os, sys, csv, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import DATASET_DIR

random.seed(42)

def write_csv(filepath, headers, rows):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  [OK] {os.path.basename(filepath)} ({len(rows)} 行)")

# ============================================================
# 数据集1: customers — 客户维度表 (100行)
# ============================================================
def generate_customers():
    surnames = ["王","李","张","刘","陈","杨","黄","赵","周","吴","徐","孙","马","朱","胡","郭","何","高","林","郑"]
    given_names_m = ["伟","强","磊","军","勇","杰","涛","明","超","华","建国","志强","文博","子涵","浩然"]
    given_names_f = ["芳","敏","静","丽","娟","秀英","艳","慧","娜","霞","雪","玲","桂英","婷","欣怡"]
    provinces = ["广东","江苏","山东","浙江","北京","上海","四川","湖北","福建","湖南"]
    levels = ["金牌","银牌","铜牌","普通"]
    level_weights = [0.08, 0.22, 0.30, 0.40]

    headers = ["客户ID","姓名","年龄","性别","注册日期","会员等级","所在省份"]
    rows = []
    for i in range(1, 101):
        cid = f"C{str(i).zfill(3)}"
        gender = random.choice(["男","女"])
        if gender == "男":
            name = random.choice(surnames) + random.choice(given_names_m)
        else:
            name = random.choice(surnames) + random.choice(given_names_f)
        age = random.randint(18, 65)
        reg_date = datetime(2020,1,1) + timedelta(days=random.randint(0,1500))
        level = random.choices(levels, weights=level_weights, k=1)[0]
        province = random.choice(provinces)
        rows.append([cid, name, age, gender, reg_date.strftime("%Y-%m-%d"), level, province])
    write_csv(os.path.join(DATASET_DIR, "customers.csv"), headers, rows)
    return len(rows)

# ============================================================
# 数据集2: products — 商品维度表 (40行)
# ============================================================
def generate_products():
    product_data = {
        "电子": [
            ("P001","智能手机Pro",2499.00,4299.00),
            ("P002","轻薄笔记本",3899.00,6499.00),
            ("P003","无线耳机",149.00,299.00),
            ("P004","智能手表",599.00,1099.00),
            ("P005","平板电脑",1899.00,3299.00),
        ],
        "服装": [
            ("P006","纯棉T恤",29.00,89.00),
            ("P007","牛仔裤",69.00,199.00),
            ("P008","羽绒服",199.00,599.00),
            ("P009","运动鞋",99.00,299.00),
            ("P010","连衣裙",79.00,259.00),
        ],
        "食品": [
            ("P011","有机大米5kg",19.00,49.90),
            ("P012","橄榄油礼盒",49.00,128.00),
            ("P013","坚果大礼包",39.00,99.00),
            ("P014","进口奶粉",69.00,168.00),
            ("P015","茶叶礼盒",59.00,149.00),
        ],
        "家居": [
            ("P016","乳胶枕",79.00,199.00),
            ("P017","蚕丝被",199.00,499.00),
            ("P018","智能台灯",89.00,229.00),
            ("P019","空气净化器",599.00,1299.00),
            ("P020","收纳柜",149.00,399.00),
        ],
        "美妆": [
            ("P021","保湿面霜",49.00,129.00),
            ("P022","防晒霜SPF50",39.00,99.00),
            ("P023","口红礼盒",59.00,169.00),
            ("P024","精华液",99.00,259.00),
            ("P025","眼霜",69.00,189.00),
        ],
        "运动": [
            ("P026","瑜伽垫",29.00,79.00),
            ("P027","跑步机",1299.00,2999.00),
            ("P028","哑铃套装",149.00,399.00),
            ("P029","运动手环",99.00,249.00),
            ("P030","羽毛球拍",79.00,199.00),
        ],
        "图书": [
            ("P031","Python编程入门",29.00,69.00),
            ("P032","数据分析实战",39.00,89.00),
            ("P033","经济学原理",49.00,99.00),
            ("P034","心理学与生活",35.00,79.00),
            ("P035","百年孤独",29.00,55.00),
        ],
        "母婴": [
            ("P036","纸尿裤大包",39.00,89.00),
            ("P037","婴儿推车",299.00,699.00),
            ("P038","儿童安全座椅",399.00,899.00),
            ("P039","早教益智玩具",79.00,199.00),
            ("P040","婴儿奶粉",99.00,239.00),
        ],
    }
    brands = {"电子":"TechPro","服装":"StyleFit","食品":"GreenFarm","家居":"HomeEase","美妆":"BeautyGlow","运动":"SportMax","图书":"ReadWorld","母婴":"BabyCare"}

    headers = ["商品ID","商品名称","品类","品牌","成本价_元","售价_元","上架日期"]
    rows = []
    # 生成随机上架日期
    all_dates = []
    for _ in range(40):
        d = datetime(2022,1,1) + timedelta(days=random.randint(0,365))
        all_dates.append(d)
    all_dates.sort()

    idx = 0
    for cat, items in product_data.items():
        for pid, pname, cost, price in items:
            rows.append([pid, pname, cat, brands[cat], cost, price, all_dates[idx].strftime("%Y-%m-%d")])
            idx += 1
    write_csv(os.path.join(DATASET_DIR, "products.csv"), headers, rows)
    return len(rows)

# ============================================================
# 数据集3: orders — 订单事实表 (300行, 含NULL)
# ============================================================
def generate_orders():
    # 为生成可控数据，手动构造订单列表
    provinces = ["广东","江苏","山东","浙江","北京","上海","四川","湖北","福建","湖南"]
    payments = ["微信支付","支付宝","银行卡","货到付款"]
    payment_weights = [0.40, 0.35, 0.15, 0.10]
    statuses = ["已完成","已取消","已退款"]
    status_weights = [0.88, 0.05, 0.07]

    # 预定义产品ID列表来自products表
    product_ids = [f"P{str(i).zfill(3)}" for i in range(1, 41)]

    headers = ["订单ID","日期","客户ID","商品ID","数量","售价_元","订单金额_元","折扣金额_元","实付金额_元","支付方式","订单状态","收货省份"]
    rows = []

    for i in range(1, 301):
        oid = f"ORD{str(i).zfill(4)}"
        # 日期: 2023-01-01 ~ 2024-12-31
        d = datetime(2023,1,1) + timedelta(days=random.randint(0,730))
        cid = f"C{str(random.randint(1,100)).zfill(3)}"
        pid = random.choice(product_ids)
        qty = random.choices([1,2,3,4,5], weights=[0.40,0.25,0.15,0.10,0.10], k=1)[0]

        # 售价根据商品估算 (简化: 用随机值模拟不同价格段)
        # 电子产品价格高，图书价格低
        cat_num = int(pid[1:])  # 1-40
        if cat_num <= 5:
            price = round(random.uniform(200, 5000), 2)
        elif cat_num <= 10:
            price = round(random.uniform(50, 500), 2)
        elif cat_num <= 15:
            price = round(random.uniform(20, 150), 2)
        elif cat_num <= 20:
            price = round(random.uniform(80, 1200), 2)
        elif cat_num <= 25:
            price = round(random.uniform(40, 250), 2)
        elif cat_num <= 30:
            price = round(random.uniform(30, 2500), 2)
        elif cat_num <= 35:
            price = round(random.uniform(25, 90), 2)
        else:
            price = round(random.uniform(40, 800), 2)

        amount = round(price * qty, 2)

        # 折扣金额: 30%概率有折扣, 70%为NULL
        if random.random() < 0.30:
            discount = round(random.uniform(5, amount*0.3), 2)
            paid = round(amount - discount, 2)
        else:
            discount = None
            paid = amount

        payment = random.choices(payments, weights=payment_weights, k=1)[0]
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        province = random.choice(provinces)

        row = [oid, d.strftime("%Y-%m-%d"), cid, pid, qty, price, amount,
               discount if discount is not None else "",  # NULL作为空字符串（类型推断为REAL后为NULL）
               paid, payment, status, province]
        rows.append(row)

    write_csv(os.path.join(DATASET_DIR, "orders.csv"), headers, rows)

    # 统计
    null_discounts = sum(1 for r in rows if r[7] == "")
    print(f"      折扣为NULL的订单: {null_discounts}/{len(rows)}")
    return len(rows)

# ============================================================
# 数据集4: monthly_targets — 月度销售目标 (192行)
# ============================================================
def generate_monthly_targets():
    categories = ["电子","服装","食品","家居","美妆","运动","图书","母婴"]
    # 目标按照品类差异化设定，6月和11月有促销目标更高
    base_targets = {"电子": 450, "服装": 280, "食品": 190, "家居": 320, "美妆": 250, "运动": 240, "图书": 120, "母婴": 210}

    headers = ["年份","月份","品类","目标销售额_万元"]
    rows = []
    for year in [2023, 2024]:
        for month in range(1, 13):
            for cat in categories:
                base = base_targets[cat]
                if year == 2024:
                    base *= random.uniform(1.05, 1.20)  # 2024年目标增长
                if month == 6:
                    base *= random.uniform(1.8, 2.3)    # 618促销月
                elif month == 11:
                    base *= random.uniform(2.0, 2.7)    # 双11促销月
                elif month == 12:
                    base *= random.uniform(1.2, 1.5)    # 年末冲刺
                target = round(base, 2)
                rows.append([year, month, cat, target])
    write_csv(os.path.join(DATASET_DIR, "monthly_targets.csv"), headers, rows)
    return len(rows)

# ============================================================
# 数据集5: refunds — 退款记录表 (25行, 稀疏)
# ============================================================
def generate_refunds():
    reasons = ["质量问题","物流损坏","不想要了","尺寸不合适","商品与描述不符","发错货",None]
    reason_weights = [0.15, 0.10, 0.25, 0.20, 0.15, 0.10, 0.05]  # 5%为NULL原因

    headers = ["退款ID","订单ID","退款金额_元","退款日期","退款原因"]
    rows = []
    used_orders = set()
    for i in range(1, 26):
        rid = f"REF{str(i).zfill(3)}"
        # 随机引用订单ID ORD0001~ORD0300
        while True:
            oid = f"ORD{str(random.randint(1, 300)).zfill(4)}"
            if oid not in used_orders:
                used_orders.add(oid)
                break
        # 退款日期: 在原订单日期后1-15天 (这里简化用随机日期)
        ref_date = datetime(2023,1,15) + timedelta(days=random.randint(0,715))
        amount = round(random.uniform(30, 3000), 2)
        reason = random.choices(reasons, weights=reason_weights, k=1)[0]
        rows.append([rid, oid, amount, ref_date.strftime("%Y-%m-%d"), reason if reason else ""])

    write_csv(os.path.join(DATASET_DIR, "refunds.csv"), headers, rows)
    null_reasons = sum(1 for r in rows if r[4] == "")
    print(f"      退款原因为NULL的记录: {null_reasons}/{len(rows)}")
    return len(rows)


def main():
    print("=" * 50)
    print("  智能问数系统 - 数据预处理 v3.0")
    print("  电商数据集 (5表星型模型)")
    print("=" * 50)

    os.makedirs(DATASET_DIR, exist_ok=True)

    n1 = generate_customers()
    n2 = generate_products()
    n3 = generate_orders()
    n4 = generate_monthly_targets()
    n5 = generate_refunds()

    total = n1 + n2 + n3 + n4 + n5
    print(f"\n{'='*50}")
    print(f"  总计: {total} 行数据, 5 张表")
    print(f"  数据集目录: {DATASET_DIR}")
    print(f"\n  NL2SQL 可测试的复杂查询类型:")
    print(f"    - INNER JOIN / LEFT JOIN / 多表关联")
    print(f"    - 子查询 / CTE / 窗口函数")
    print(f"    - NULL值处理 / COALESCE")
    print(f"    - GROUP BY + HAVING")
    print(f"    - 日期范围 / 同比环比")
    print(f"    - 达成率计算 / CASE WHEN")
    print(f"\n  下一步:")
    print(f"    1. pip install -r requirements.txt")
    print(f"    2. python -m app.main  (启动后端)")
    print(f"    3. cd ../frontend && npm run dev  (启动前端)")

if __name__ == "__main__":
    main()
