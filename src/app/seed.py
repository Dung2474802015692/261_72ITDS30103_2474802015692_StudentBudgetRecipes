"""Sample data so the app is usable on first run.

The prices below are SAMPLE prices typed by hand. They are not real Emart prices;
edit them on the Prices page.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import PriceItem, Recipe, RecipeIngredient

# name|unit|VND per unit|category
ITEMS = """
thịt heo ba rọi|kg|130000|thịt
thịt heo nạc vai|kg|120000|thịt
sườn heo|kg|150000|thịt
thịt gà ức|kg|85000|thịt
đùi gà|kg|70000|thịt
cánh gà|kg|80000|thịt
thịt bò|kg|260000|thịt
thịt heo xay|kg|110000|thịt
chả lụa|kg|140000|thịt
xúc xích|gói|25000|thịt
cá basa fillet|kg|75000|hải sản
cá thu|kg|120000|hải sản
cá diêu hồng|kg|85000|hải sản
tôm thẻ|kg|190000|hải sản
mực ống|kg|180000|hải sản
chả cá|kg|120000|hải sản
trứng gà|quả|3500|trứng
trứng vịt|quả|4000|trứng
trứng cút|quả|800|trứng
đậu hũ|miếng|5000|đậu
đậu hũ chiên|miếng|6000|đậu
rau muống|kg|20000|rau
cải ngọt|kg|25000|rau
cải thìa|kg|28000|rau
cải thảo|kg|25000|rau
bắp cải|kg|18000|rau
cà chua|kg|30000|rau
cà rốt|kg|25000|rau
khoai tây|kg|30000|rau
khoai lang|kg|28000|rau
khoai môn|kg|40000|rau
bí đỏ|kg|22000|rau
bí xanh|kg|20000|rau
dưa leo|kg|25000|rau
cà tím|kg|30000|rau
đậu cove|kg|40000|rau
đậu bắp|kg|35000|rau
giá đỗ|kg|15000|rau
hành lá|kg|40000|rau
hành tây|kg|28000|rau
tỏi|kg|60000|rau
gừng|kg|50000|rau
sả|kg|30000|rau
ớt|kg|60000|rau
bông cải xanh|kg|55000|rau
mướp|kg|25000|rau
su su|kg|22000|rau
củ cải trắng|kg|20000|rau
rau dền|kg|20000|rau
mồng tơi|kg|20000|rau
bắp ngô|quả|8000|rau
rau thơm|bó|5000|rau
nấm rơm|kg|90000|rau
nấm bào ngư|kg|50000|rau
nấm kim châm|gói|15000|rau
chanh|kg|40000|rau
gạo|kg|20000|tinh bột
mì gói|gói|4500|tinh bột
bún tươi|kg|22000|tinh bột
bún khô|kg|35000|tinh bột
miến|kg|60000|tinh bột
mì trứng|kg|40000|tinh bột
bánh mì|ổ|5000|tinh bột
bột mì|kg|22000|tinh bột
bột năng|kg|30000|tinh bột
đậu xanh|kg|50000|tinh bột
đậu đen|kg|45000|tinh bột
nước mắm|chai|35000|gia vị
dầu ăn|lít|55000|gia vị
đường|kg|25000|gia vị
muối|kg|8000|gia vị
nước tương|chai|20000|gia vị
tiêu|gói|10000|gia vị
hạt nêm|gói|25000|gia vị
tương ớt|chai|18000|gia vị
dầu hào|chai|30000|gia vị
giấm|chai|12000|gia vị
bột chiên giòn|gói|15000|gia vị
nước cốt dừa|hộp|20000|gia vị
sa tế|hũ|22000|gia vị
tương cà|chai|20000|gia vị
mè rang|gói|12000|gia vị
bột cà ri|gói|15000|gia vị
sữa tươi|lít|32000|sữa
sữa chua|hộp|7000|sữa
sữa đặc|hộp|22000|sữa
sữa đậu nành|lít|20000|sữa
phô mai|gói|35000|sữa
bơ lạt|gói|40000|sữa
chuối|kg|25000|trái cây
cam|kg|40000|trái cây
táo|kg|70000|trái cây
dưa hấu|kg|20000|trái cây
đu đủ|kg|25000|trái cây
ổi|kg|30000|trái cây
đậu phộng|kg|70000|khác
rong biển|gói|18000|khác
nấm đông cô khô|gói|30000|khác
mộc nhĩ|gói|15000|khác
tôm khô|gói|40000|khác
"""

# name, servings, [(ingredient, quantity in that ingredient's unit)]
RECIPES = [
    ("Cơm trứng chiên", 1, [("gạo", .12), ("trứng gà", 2), ("hành lá", .02), ("dầu ăn", .02), ("nước mắm", .03)]),
    ("Cơm gà chiên nước mắm", 1, [("gạo", .12), ("đùi gà", .25), ("nước mắm", .05), ("đường", .01), ("tỏi", .01), ("dầu ăn", .03), ("cải ngọt", .1)]),
    ("Cơm sườn", 1, [("gạo", .12), ("sườn heo", .15), ("dưa leo", .1), ("cà chua", .05), ("nước mắm", .03), ("dầu ăn", .02), ("tỏi", .01)]),
    ("Canh bí đỏ thịt heo", 1, [("gạo", .12), ("thịt heo nạc vai", .1), ("bí đỏ", .2), ("hành lá", .02), ("nước mắm", .03), ("hạt nêm", .02)]),
    ("Mì gói trứng rau", 1, [("mì gói", 1), ("trứng gà", 1), ("cải thìa", .1), ("hành lá", .01)]),
    ("Bún thịt nướng", 1, [("bún tươi", .2), ("thịt heo ba rọi", .15), ("dưa leo", .1), ("giá đỗ", .05), ("rau thơm", 1), ("nước mắm", .05), ("đường", .01)]),
    ("Đậu hũ sốt cà", 1, [("gạo", .12), ("đậu hũ", 2), ("cà chua", .15), ("hành lá", .02), ("nước mắm", .03), ("dầu ăn", .02)]),
    ("Rau muống xào tỏi và trứng", 1, [("gạo", .12), ("rau muống", .2), ("tỏi", .02), ("trứng gà", 1), ("dầu ăn", .03)]),
    ("Cá basa kho", 1, [("gạo", .12), ("cá basa fillet", .15), ("nước mắm", .05), ("đường", .02), ("tiêu", .1), ("hành lá", .02)]),
    ("Bò xào hành tây", 1, [("gạo", .12), ("thịt bò", .12), ("hành tây", .1), ("dầu hào", .05), ("dầu ăn", .02), ("tỏi", .01)]),
    ("Tôm rang", 1, [("gạo", .12), ("tôm thẻ", .15), ("tỏi", .02), ("nước mắm", .03), ("đường", .01), ("dầu ăn", .02)]),
    ("Cháo gà", 1, [("gạo", .1), ("thịt gà ức", .15), ("hành lá", .02), ("gừng", .01), ("nước mắm", .03)]),
    ("Trứng chiên cà chua", 1, [("gạo", .12), ("trứng gà", 2), ("cà chua", .15), ("hành lá", .01), ("dầu ăn", .02)]),
    ("Miến xào rau", 1, [("miến", .1), ("cà rốt", .05), ("cải thảo", .1), ("trứng gà", 1), ("dầu ăn", .03), ("nước mắm", .03)]),
    ("Bánh mì trứng", 1, [("bánh mì", 1), ("trứng gà", 2), ("dưa leo", .05), ("dầu ăn", .02)]),
]


def seed(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(PriceItem)):
        return
    for line in ITEMS.strip().splitlines():
        name, unit, price, category = line.split("|")
        db.add(PriceItem(name=name, unit=unit, price=int(price), category=category))
    db.flush()
    by_name = {i.name: i for i in db.scalars(select(PriceItem))}
    for name, servings, ingredients in RECIPES:
        db.add(Recipe(
            name=name,
            servings=servings,
            ingredients=[RecipeIngredient(item=by_name[n], quantity=q) for n, q in ingredients],
        ))
    db.commit()
