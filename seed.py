"""
seed.py — 產生假班級 (30 人) 個資 + 32 個帳號 (30 學生 + 1 學藝股長 + 1 註冊組長)
資料純為測試用途，所有姓名/身分證/地址/電話皆為虛構。
"""
import json
import os
import random
import hashlib

random.seed(20260429)  # 可重現

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ── 假名來源 ────────────────────────────────────────────────────
SURNAMES = list("陳林黃張李王吳劉蔡楊許鄭謝郭洪邱曾廖賴徐周葉蘇莊呂江何蕭羅高")
GIVEN_M = ["志明", "建宏", "俊傑", "家豪", "宗翰", "冠廷", "承恩", "柏翰",
           "勝文", "睿宏", "彥廷", "宇辰", "祐霆", "子翔", "凱翔", "竣豪"]
GIVEN_F = ["雅婷", "怡君", "美玲", "佳穎", "詩涵", "宛庭", "靜怡", "馨儀",
           "若芸", "心瑜", "婕妤", "庭瑄", "芯彤", "采蓁", "依璇", "品瑜"]
RELIGIONS = ["無", "佛教", "基督教", "天主教", "道教", "一貫道"]
BLOOD = ["A", "B", "O", "AB"]
JOBS = ["軟體工程師", "教師", "護理師", "公務員", "業務", "會計", "餐飲業",
        "工程師", "家管", "醫師", "建築師", "設計師", "店員", "司機", "農夫"]
DISTRICTS = ["大安區", "信義區", "中正區", "松山區", "中山區", "士林區",
             "內湖區", "南港區", "文山區", "北投區"]
RELS = ["父親", "母親", "兄", "姐", "舅舅", "姑姑", "祖父", "祖母"]


def gen_student_id(seat_idx):
    """學號：1153 + 班級代碼 5 + 三位座號"""
    return f"1153 5{seat_idx:03d}"


def gen_national_id(gender):
    """虛構身分證字號 — 第 1 碼英文 (戶籍縣市)，第 2 碼性別 (1男2女)，後 8 碼隨機"""
    region = random.choice("ABCDEFGHJKLMNPQRSTUV")  # 不用 IO 以免混淆
    sex = "1" if gender == "男" else "2"
    rest = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{region}{sex}{rest}"


def gen_phone():
    return f"09{random.randint(10, 99)}-{random.randint(100, 999)}-{random.randint(100, 999)}"


def gen_landline():
    return f"02-{random.randint(2000, 2999)}-{random.randint(1000, 9999)}"


def gen_address():
    dist = random.choice(DISTRICTS)
    road = random.choice(["和平", "中山", "光復", "民生", "復興", "敦化", "羅斯福", "忠孝", "信義", "仁愛"])
    direction = random.choice(["東", "西", "南", "北"])
    section = random.choice(["", "一段", "二段", "三段", "四段"])
    num = random.randint(10, 999)
    floor = random.randint(1, 12)
    return f"台北市{dist}{road}{direction}路{section}{num}號{floor}樓"


def gen_dob():
    year = random.choice([2008, 2009])
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def gen_name(gender):
    surname = random.choice(SURNAMES)
    given = random.choice(GIVEN_M if gender == "男" else GIVEN_F)
    return surname + given


# ── 產生 30 位學生 ──────────────────────────────────────────────
students = []
for i in range(1, 31):
    gender = random.choice(["男", "女"])
    name = gen_name(gender)
    father_name = random.choice(SURNAMES) + random.choice(GIVEN_M[:8])
    mother_name = random.choice(SURNAMES) + random.choice(GIVEN_F[:8])
    addr = gen_address()
    rec = {
        "seat": i,                                      # 座號 1~30
        "student_id": gen_student_id(i),                # 學號
        "name": name,                                   # 姓名
        "gender": gender,                               # 性別
        "national_id": gen_national_id(gender),         # 身分證
        "dob": gen_dob(),                               # 生日
        "blood": random.choice(BLOOD),                  # 血型
        "religion": random.choice(RELIGIONS),           # 宗教
        "address_household": addr,                      # 戶籍地址
        "address_mailing": addr,                        # 通訊地址 (常一樣)
        "phone": gen_phone(),                           # 學生電話
        "father_name": father_name,                     # 父
        "father_phone": gen_phone(),
        "father_job": random.choice(JOBS),
        "mother_name": mother_name,                     # 母
        "mother_phone": gen_phone(),
        "mother_job": random.choice(JOBS),
        "emergency_name": random.choice([father_name, mother_name]),
        "emergency_phone": gen_phone(),
        "emergency_relation": random.choice(RELS[:2]),
        "home_phone": gen_landline(),
        "confirmed": False,                             # 預設未確認
        "confirmed_at": None,                           # 確認時間
        "note": "",                                     # 學生備註 (有錯時填)
    }
    students.append(rec)


# ── 產生帳號 ────────────────────────────────────────────────────
def hash_pw(p):
    """簡單 SHA-256 雜湊 (不用 bcrypt 保持 stdlib only)"""
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


users = []
# 30 位學生帳號：test01 ~ test30，密碼=帳號
for i in range(1, 31):
    uname = f"test{i:02d}"
    users.append({
        "username": uname,
        "password_hash": hash_pw(uname),
        "role": "student",
        "linked_seat": i,                # 對應到 students.seat
        "display_name": students[i - 1]["name"],
    })

# 學藝股長：officer01 / officer01，順便當班上 13 號學生
users.append({
    "username": "officer01",
    "password_hash": hash_pw("officer01"),
    "role": "officer",
    "linked_seat": 13,                   # 學藝股長本人也是學生
    "display_name": "學藝股長 " + students[12]["name"],
})

# 註冊組長：registrar01 / registrar01
users.append({
    "username": "registrar01",
    "password_hash": hash_pw("registrar01"),
    "role": "registrar",
    "linked_seat": None,
    "display_name": "註冊組長",
})


# ── 班級資訊 ────────────────────────────────────────────────────
classroom = {
    "school": "示範高級中學",
    "grade": "高三",
    "class_name": "忠班",
    "class_code": "11353",
    "homeroom_teacher": "王志明",
    "academic_year": "114",
    "semester": "上學期",
    "total_students": 30,
}


# ── 寫檔 ────────────────────────────────────────────────────────
def write_json(name, data):
    p = os.path.join(DATA_DIR, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ {p}  ({len(json.dumps(data))} bytes)")


write_json("students.json", students)
write_json("users.json", users)
write_json("classroom.json", classroom)

print(f"\n產生完成：{len(students)} 位學生，{len(users)} 個帳號")
print("帳號清單：")
print(f"  - 學生：test01 ~ test30 (密碼 = 帳號)")
print(f"  - 學藝股長：officer01 / officer01 (兼 13 號學生)")
print(f"  - 註冊組長：registrar01 / registrar01")
