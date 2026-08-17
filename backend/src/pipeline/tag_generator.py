import logging
import re
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

class TagGenerator:
    """
    [Node 3.5.1] Comprehensive Multi-Domain Taxonomy & Deep Fashion/Person Tag Generator.
    Implements 6-Category Standard Hierarchy + Deep Person & Fashion Breakdown:
    - Subject (主体): 人物肖像、服饰穿搭、珠宝首饰、萌宠、美食、自然、车辆等
    - ColorStyle (色彩风格): 胶片、极简、暖色、冷色、莫兰迪、多巴胺、美拉德等
    - Scene (场景空间): 室内、户外、座舱、街头、原野、展厅、职场通勤等
    - Emotion (情绪氛围): 治愈、俏皮、浪漫、活力、宁静、高级感、从容自信等
    - Composition (构图景深): 特写、中心构图、留白、对角线、大景深等
    - Entity (具体实体): 自动从视觉大模型描述中提取核心具体名词实体
    - PersonDetail (人物与穿搭解构): 首饰配饰、发型妆容、上装下装、穿搭风格
    """

    ONTOLOGY = {
        "Subject": {
            "人物肖像": ["人物", "女性", "女孩", "少女", "男士", "自拍", "人像", "模特", "女人", "男人", "面容", "青年", "女士"],
            "服饰穿搭": ["穿搭", "服装", "上衣", "衬衫", "西装", "大衣", "风衣", "裙子", "连衣裙", "牛仔裤", "阔腿裤", "外套", "卫衣", "毛衣", "鞋履", "高跟鞋"],
            "珠宝首饰": ["首饰", "珠宝", "项链", "吊坠", "耳环", "耳钉", "耳饰", "戒指", "手镯", "手链", "手串", "腕表", "手表", "发饰", "发夹"],
            "萌宠动物": ["猫", "狗", "犬", "宠物", "鸟", "野生动物", "小狗", "小猫", "幼犬", "幼崽", "动物", "金毛", "柯基", "柴犬", "毛茸茸", "飞鸟", "兔", "鱼"],
            "美食料理": ["美食", "料理", "菜品", "食材", "生蚝", "海鲜", "水果", "甜点", "肉质", "餐盘", "烘焙", "饮品", "咖啡", "佳肴"],
            "自然风光": ["山川", "风景", "自然", "湖泊", "河流", "森林", "天空", "雪山", "草原", "日落", "海洋", "沙滩", "日出", "海景"],
            "车辆交通": ["汽车", "车辆", "跑车", "车身", "座舱", "后视镜", "驾驶", "机车", "飞机", "轮船", "高铁", "公路"],
            "城市建筑": ["建筑", "高楼", "街景", "城市", "桥梁", "地标", "房屋", "街道", "夜景", "天际线", "广场"],
            "数码科技": ["数码", "手机", "电脑", "科技", "屏幕", "芯片", "机器人", "仪器", "电子", "硬件", "智能设备"],
            "植物花卉": ["花卉", "植物", "绿植", "花瓣", "树木", "盆栽", "多肉", "枫叶", "樱花", "草地", "花朵"],
            "艺术设计": ["插画", "动漫", "雕塑", "画作", "艺术", "手办", "图形", "极简设计", "平面设计", "海报"]
        },
        "ColorStyle": {
            "粉色柔和": ["粉色", "粉白", "粉调", "樱花粉", "少女粉", "柔粉"],
            "暖色调": ["暖色", "暖光", "金黄", "夕阳色", "橙黄", "柔和暖光", "温馨色调", "暖调", "焦糖", "美拉德"],
            "冷色调": ["冷色", "蓝调", "冷青", "冰蓝", "深蓝", "清冷", "蓝灰色", "冷调"],
            "极简风": ["极简", "简约", "素雅", "纯净", "干净", "简练", "留白", "黑白灰"],
            "胶片复古": ["胶片", "复古", "质感", "怀旧", "颗粒感", "老照片", "胶片色调", "港风", "法式复古"],
            "黑白高级": ["黑白", "灰度", "单色", "高对比黑白", "影调", "静奢"],
            "高饱和绚丽": ["绚丽", "明亮", "鲜艳", "高饱和", "五彩", "斑斓", "明艳", "多巴胺"],
            "莫兰迪色系": ["莫兰迪", "高级灰", "低饱和", "素净", "淡雅", "柔和色调", "燕麦色", "大地色"],
            "赛博朋克": ["赛博朋克", "霓虹", "荧光", "紫蓝光", "未来感光效", "光影交错"],
            "自然采光": ["自然光", "柔光", "侧光", "逆光", "透亮", "阳光透射", "晨光", "光影协调"]
        },
        "Scene": {
            "职场通勤": ["办公室", "写字楼", "职场", "商务", "会议室", "通勤", "工位", "商务会客"],
            "车内私密空间": ["车内", "后视镜", "驾驶座", "副驾驶", "车厢", "车载", "挡风玻璃"],
            "室内居所": ["室内", "卧室", "客厅", "阳台", "书房", "房间", "居家", "窗边", "床榻"],
            "餐厅咖啡厅": ["餐厅", "咖啡厅", "餐桌", "酒吧", "吧台", "餐馆", "厨房", "茶室", "下午茶"],
            "自然野外": ["户外", "森林", "山地", "海边", "湖畔", "田野", "草原", "公园", "雪地", "草坪"],
            "都市街头": ["街头", "马路", "人行道", "商场", "商业街", "市中心", "斑马线", "地铁", "街拍"],
            "展厅舞台": ["展厅", "博物馆", "舞台", "画廊", "秀场", "聚光灯下", "晚宴", "红毯"]
        },
        "Emotion": {
            "治愈宁静": ["治愈", "宁静", "安详", "静谧", "惬意", "舒适", "平静", "放松", "温馨"],
            "俏皮害羞": ["俏皮", "害羞", "羞涩", "灵动", "甜美", "可爱", "微笑", "俏丽"],
            "浪漫唯美": ["浪漫", "唯美", "温存", "深情", "梦幻", "优雅", "柔美"],
            "孤独深沉": ["孤独", "深沉", "忧郁", "沉思", "冷峻", "神秘", "凝视"],
            "激情活力": ["活力", "热烈", "运动", "动感", "欢快", "兴奋", "朝气", "活泼", "阳光"],
            "从容自信": ["自信", "干练", "从容", "知性", "沉稳", "大方", "英气"],
            "高端奢华": ["奢华", "高贵", "典雅", "精致", "高级感", "典重", "质感", "名媛", "名流"],
            "鲜活诱人": ["新鲜", "诱人", "鲜活", "晶莹", "饱满", "美味", "光泽"]
        },
        "Composition": {
            "特写微距": ["特写", "近景", "局部", "微距", "细节放大", "面部特写", "特写视角", "半身肖像"],
            "中心构图": ["中心", "对称", "正中", "居中", "聚焦中心", "中心视角"],
            "景深虚化": ["景深", "虚化", "大光圈", "背景虚化", "前景虚化", "浅景深"],
            "后视镜倒影": ["后视镜", "倒影", "镜面反射", "镜子", "反射视角"],
            "对角线延伸": ["对角线", "斜角", "延伸感", "倾斜构图", "视线引导"],
            "三分法构图": ["三分法", "黄金分割", "黄金比例", "侧边构图"],
            "全景俯瞰": ["俯拍", "全景", "俯瞰", "鸟瞰", "高空视角", "全身构图", "广角宏大"]
        },
        "Entity": {
            "珠宝首饰": ["项链", "珍珠项链", "锁骨链", "耳环", "耳钉", "耳坠", "戒指", "钻戒", "手镯", "翡翠手镯", "手链", "手表", "腕表", "发饰", "发夹", "胸针"],
            "服饰鞋包": ["衬衫", "西装", "大衣", "风衣", "T恤", "毛衣", "针织衫", "卫衣", "连衣裙", "半身裙", "牛仔裤", "西裤", "阔腿裤", "高跟鞋", "皮鞋", "运动鞋", "单肩包", "斜挎包", "手提包", "托特包", "皮带", "墨镜", "眼镜", "丝巾"],
            "发型妆容": ["长发", "短发", "卷发", "直发", "波浪卷", "高马尾", "丸子头", "齐刘海", "红唇", "淡妆", "素颜", "烟熏妆"],
            "汽车配件": ["后视镜", "方向盘", "中控台", "车窗", "座椅", "遮阳板"],
            "生鲜食材": ["生蚝", "蚝壳", "柠檬", "酱料", "冰块", "盘皿", "食材"],
            "电子产品": ["手机", "平板", "笔记本", "镜头", "相机", "耳机"],
            "萌宠宠物": ["小狗", "幼犬", "金毛", "猫咪", "宠物", "毛发"],
            "自然植物": ["花朵", "枝叶", "树干", "草丛", "流水", "岩石", "草坪"]
        }
    }

    # Fine-grained Person & Fashion Dictionary for deep feature extraction
    PERSON_FASHION_DICT = {
        "jewelry": [
            "珍珠项链", "金属项链", "金项链", "银项链", "锁骨链", "吊坠项链", "钻石项链",
            "珍珠耳环", "金属耳环", "圈状耳环", "水滴耳坠", "钻石耳钉", "耳环", "耳钉", "耳坠",
            "戒指", "钻戒", "素圈戒指", "宝石戒指",
            "手镯", "翡翠手镯", "金手镯", "银手镯", "细手链", "珍珠手链", "手串",
            "机械腕表", "皮带腕表", "钢带手表", "石英表", "智能手表", "手表", "腕表",
            "发夹", "发带", "发箍", "抓夹", "丝绒发饰", "头饰",
            "胸针", "袖扣"
        ],
        "apparel_top": [
            "白衬衫", "真丝衬衫", "雪纺衬衫", "衬衫", "西装外套", "修身西装", "休闲西服", "小香风外套",
            "羊绒大衣", "风衣", "毛呢大衣", "羽绒服", "夹克", "皮衣", "针织开衫", "高领毛衣",
            "圆领T恤", "纯棉T恤", "连帽卫衣", "吊带上衣", "背心", "卫衣", "毛衣", "上衣"
        ],
        "apparel_bottom": [
            "高腰阔腿裤", "直筒牛仔裤", "紧身牛仔裤", "牛仔裤", "西装裤", "西裤", "烟管裤", "工装裤", "短裤",
            "法式连衣裙", "吊带连衣裙", "印花连衣裙", "碎花裙", "百褶裙", "A字裙", "包臀裙", "半身裙", "礼服", "长裙"
        ],
        "footwear_accessories": [
            "尖头高跟鞋", "细高跟鞋", "粗跟单鞋", "乐福鞋", "皮鞋", "小白鞋", "运动鞋", "马丁靴", "长筒靴", "凉鞋",
            "手提包", "单肩包", "斜挎包", "托特包", "链条包", "水桶包", "双肩包", "手拿包",
            "黑框眼镜", "金丝边眼镜", "复古墨镜", "太阳镜", "遮阳帽", "贝雷帽", "棒球帽", "丝巾", "皮带", "腰带"
        ],
        "hair_grooming": [
            "齐肩波浪卷", "大波浪长发", "黑长直发", "长卷发", "及肩短发", "挂耳短发", "高马尾", "丸子头", "齐刘海", "八字刘海",
            "棕褐色发色", "自然黑发", "浅金发色", "红棕发色",
            "精致淡妆", "大地色眼影", "红唇妆", "豆沙唇色", "元气裸妆", "复古红唇", "清透裸妆"
        ],
        "style_aesthetics": [
            "法式复古", "极简通勤", "职场干练", "轻奢名媛", "老钱风", "新中式", "街头潮流",
            "学院风", "多巴胺风格", "美拉德风", "清冷高级", "甜美少女", "优雅知性", "运动休闲", "国风雅致"
        ]
    }

    def generate_categorized_tags(self, text_description: str) -> Dict[str, List[str]]:
        """
        Dynamically extracts structured tags across 6 core categories from rich description.
        Combines ontology match + direct phrase extraction from structured sections.
        """
        result: Dict[str, List[str]] = {cat: [] for cat in self.ONTOLOGY}
        if not text_description:
            return result

        # 1. Match against extensive ontology
        for cat, tag_dict in self.ONTOLOGY.items():
            for tag_name, keywords in tag_dict.items():
                if any(kw in text_description for kw in keywords):
                    if tag_name not in result[cat]:
                        result[cat].append(tag_name)

        # 2. Extract dynamic phrases directly from structured sections
        lines = text_description.split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            cleaned_text = self._clean_header(line_str)
            if re.search(r"主体|细节|人物|对象|服饰|首饰|妆容", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"主体", "细节", "特征", "画面", "呈现", "如图"})
                for phrase in extracted:
                    if phrase not in result["Subject"] and len(phrase) >= 2:
                        result["Subject"].append(phrase)
            elif re.search(r"色彩|光影|基调|色调", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"色彩", "光影", "基调", "色调", "呈现", "搭配"})
                for phrase in extracted:
                    if phrase not in result["ColorStyle"] and len(phrase) >= 2:
                        result["ColorStyle"].append(phrase)
            elif re.search(r"场景|空间|环境|背景|职场", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"场景", "空间", "环境", "背景", "设置", "处于"})
                for phrase in extracted:
                    if phrase not in result["Scene"] and len(phrase) >= 2:
                        result["Scene"].append(phrase)
            elif re.search(r"情绪|氛围|风格|意境|神态", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"情绪", "氛围", "风格", "表达", "营造", "感觉"})
                for phrase in extracted:
                    if phrase not in result["Emotion"] and len(phrase) >= 2:
                        result["Emotion"].append(phrase)
            elif re.search(r"构图|视角|景深|焦距", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"构图", "视角", "拍摄", "采用", "画面"})
                for phrase in extracted:
                    if phrase not in result["Composition"] and len(phrase) >= 2:
                        result["Composition"].append(phrase)

        # 3. Ensure Entity has concrete nouns mentioned in description
        entity_candidates = [
            "珍珠项链", "项链", "耳环", "耳钉", "戒指", "手镯", "手链", "手表", "腕表", "发夹", "墨镜", "眼镜",
            "衬衫", "西装", "大衣", "连衣裙", "裙子", "阔腿裤", "牛仔裤", "高跟鞋", "单肩包", "手提包",
            "后视镜", "遮阳板", "手机", "汽车", "生蚝", "餐盘", "杯子", "鲜花", "背包", "幼犬", "小狗", "猫咪", "树木"
        ]
        for ec in entity_candidates:
            if ec in text_description and ec not in result["Entity"]:
                result["Entity"].append(ec)

        # 4. Fallback defaults if a category has no match
        defaults = {
            "Subject": ["媒体主体"],
            "ColorStyle": ["自然色调"],
            "Scene": ["应用场景"],
            "Emotion": ["真实氛围"],
            "Composition": ["主体视角"],
            "Entity": ["视觉对象"]
        }
        for cat in result:
            if not result[cat]:
                result[cat] = defaults[cat]
            result[cat] = result[cat][:5]

        return result

    def extract_person_details(self, text_description: str) -> Dict[str, Any]:
        """
        Deep Person & Fashion Breakdown Parser.
        Extracts granular jewelry, apparel, grooming, and aesthetics from the rich VLM description.
        """
        details: Dict[str, Any] = {
            "has_person": False,
            "gender_age": "未知",
            "posture_expression": "自然神态",
            "hair_makeup": [],
            "jewelry_accessories": [],
            "apparel_top": [],
            "apparel_bottom": [],
            "footwear_bags": [],
            "style_aesthetics": [],
            "highlights_summary": ""
        }
        if not text_description:
            return details

        # Detect if person is present
        person_indicators = ["人物", "女性", "女孩", "少女", "男士", "自拍", "人像", "模特", "女人", "男人", "面容", "女士", "青年", "头发", "身穿", "佩戴", "服饰", "穿搭"]
        if any(ind in text_description for ind in person_indicators):
            details["has_person"] = True

        # 1. Match Jewelry & Accessories
        for jw in self.PERSON_FASHION_DICT["jewelry"]:
            if jw in text_description and jw not in details["jewelry_accessories"]:
                details["jewelry_accessories"].append(jw)

        # 2. Match Tops
        for top in self.PERSON_FASHION_DICT["apparel_top"]:
            if top in text_description and top not in details["apparel_top"]:
                details["apparel_top"].append(top)

        # 3. Match Bottoms & Dresses
        for bot in self.PERSON_FASHION_DICT["apparel_bottom"]:
            if bot in text_description and bot not in details["apparel_bottom"]:
                details["apparel_bottom"].append(bot)

        # 4. Match Shoes, Bags, Glasses, Hats
        for acc in self.PERSON_FASHION_DICT["footwear_accessories"]:
            if acc in text_description and acc not in details["footwear_bags"]:
                details["footwear_bags"].append(acc)

        # 5. Match Hair & Grooming
        for hr in self.PERSON_FASHION_DICT["hair_grooming"]:
            if hr in text_description and hr not in details["hair_makeup"]:
                details["hair_makeup"].append(hr)

        # 6. Match Style Aesthetics
        for st in self.PERSON_FASHION_DICT["style_aesthetics"]:
            if st in text_description and st not in details["style_aesthetics"]:
                details["style_aesthetics"].append(st)

        # 7. Extract specific section lines if structured
        lines = text_description.split("\n")
        for line in lines:
            line_str = line.strip()
            if "面容" in line_str or "发型" in line_str or "妆容" in line_str:
                phrases = self._extract_key_phrases(self._clean_header(line_str), exclude={"面容", "发型", "妆容", "特征"})
                for p in phrases:
                    if p not in details["hair_makeup"] and len(p) >= 2:
                        details["hair_makeup"].append(p)
            elif "首饰" in line_str or "配饰" in line_str or "珠宝" in line_str or "佩戴" in line_str:
                phrases = self._extract_key_phrases(self._clean_header(line_str), exclude={"首饰", "配饰", "珠宝", "佩戴", "细节"})
                for p in phrases:
                    if p not in details["jewelry_accessories"] and len(p) >= 2:
                        details["jewelry_accessories"].append(p)
            elif "服装" in line_str or "穿搭" in line_str or "上装" in line_str or "下装" in line_str:
                phrases = self._extract_key_phrases(self._clean_header(line_str), exclude={"服装", "穿搭", "上装", "下装", "款式", "搭配"})
                for p in phrases:
                    if p not in details["apparel_top"] and p not in details["apparel_bottom"] and len(p) >= 2:
                        details["apparel_top"].append(p)
            elif "风格" in line_str or "流派" in line_str or "美学" in line_str:
                phrases = self._extract_key_phrases(self._clean_header(line_str), exclude={"风格", "流派", "美学", "质感", "整体"})
                for p in phrases:
                    if p not in details["style_aesthetics"] and len(p) >= 2:
                        details["style_aesthetics"].append(p)

        # 8. Compose highlights summary
        summary_parts = []
        if details["hair_makeup"]:
            summary_parts.append(f"妆发: {', '.join(details['hair_makeup'][:3])}")
        if details["jewelry_accessories"]:
            summary_parts.append(f"首饰配饰: {', '.join(details['jewelry_accessories'][:4])}")
        if details["apparel_top"] or details["apparel_bottom"]:
            clothes = (details["apparel_top"][:2] + details["apparel_bottom"][:2])
            summary_parts.append(f"穿搭: {', '.join(clothes)}")
        if details["style_aesthetics"]:
            summary_parts.append(f"风格: {', '.join(details['style_aesthetics'][:2])}")

        details["highlights_summary"] = " | ".join(summary_parts) if summary_parts else "自然人物肖像与日常穿搭"
        return details

    # Professional Fashion & Apparel Industry Dictionary
    FASHION_INDUSTRY_DICT = {
        "fabrics": [
            "桑蚕丝", "真丝", "重磅真丝", "精梳棉", "重磅纯棉", "有机纯棉", "法国亚麻", "天然亚麻",
            "羊绒", "开司米", "美利奴羊毛", "精纺羊毛", "毛呢", "双面呢",
            "植鞣皮革", "小羊皮", "牛皮革", "麂皮绒", "复古牛仔", "水洗丹宁",
            "高光醋酸", "三醋酸缎面", "雪纺", "欧根纱", "重工蕾丝", "灯芯绒", "天鹅绒", "金丝绒",
            "提花暗纹", "精纺罗纹", "华夫格肌理"
        ],
        "silhouettes": [
            "H型直筒", "A字廓形", "X型收腰", "茧型廓形", "Oversize宽松", "落肩剪裁", "修身合体",
            "立裁垂坠", "及踝长款", "利落短款", "高腰剪裁", "不规则下摆", "侧边开叉"
        ],
        "collars_sleeves": [
            "西装驳领", "戗驳领", "平驳领", "中式立领", "传统盘扣领", "法式方领", "深V领", "古巴领",
            "POLO翻领", "一字领", "圆领挂脖", "法式泡泡袖", "落肩袖", "蝙蝠袖", "法式衬衫叠褶袖", "无袖削肩"
        ],
        "patterns_crafts": [
            "千鸟格纹", "威尔士亲王格", "英伦细条纹", "法式复古波点", "清新碎花", "数码印花", "水墨晕染",
            "手工明线车缝", "天然贝壳扣", "复古牛角扣", "金属五金扣", "隐形拉链", "立体贴袋", "精细压褶"
        ],
        "style_vibes": [
            "静奢老钱风 (Quiet Luxury)", "Cleanfit极简通勤", "法式复古浪漫 (French Chic)",
            "新中式国风 (Neo-Chinese)", "美拉德色系 (Maillard)", "多巴胺高饱和",
            "都市户外机能 (Gorpcore)", "美式复古工装 (Vintage Workwear)", "知识分子知性风", "轻奢名媛风"
        ]
    }

    def extract_fashion_industry_details(self, text_description: str) -> Dict[str, Any]:
        """
        Professional Fashion & Apparel Industry Feature Extractor.
        Deconstructs garment category, fabric/texture, silhouette, collar/sleeve, pattern, craft & aesthetic.
        """
        fashion_data: Dict[str, Any] = {
            "has_fashion_analysis": False,
            "garment_categories": [],
            "fabrics_textures": [],
            "silhouettes": [],
            "collars_sleeves": [],
            "patterns_crafts": [],
            "style_aesthetics": [],
            "fashion_summary": ""
        }
        if not text_description:
            return fashion_data

        fashion_data["has_fashion_analysis"] = True

        # 1. Garment Categories (Tops, Bottoms, Dresses, Outerwear)
        for top in self.PERSON_FASHION_DICT["apparel_top"]:
            if top in text_description and top not in fashion_data["garment_categories"]:
                fashion_data["garment_categories"].append(top)
        for bot in self.PERSON_FASHION_DICT["apparel_bottom"]:
            if bot in text_description and bot not in fashion_data["garment_categories"]:
                fashion_data["garment_categories"].append(bot)

        # 2. Fabrics & Materials
        for fb in self.FASHION_INDUSTRY_DICT["fabrics"]:
            if fb in text_description and fb not in fashion_data["fabrics_textures"]:
                fashion_data["fabrics_textures"].append(fb)

        # 3. Silhouettes & Tailoring
        for sil in self.FASHION_INDUSTRY_DICT["silhouettes"]:
            if sil in text_description and sil not in fashion_data["silhouettes"]:
                fashion_data["silhouettes"].append(sil)

        # 4. Collars & Sleeves
        for cs in self.FASHION_INDUSTRY_DICT["collars_sleeves"]:
            if cs in text_description and cs not in fashion_data["collars_sleeves"]:
                fashion_data["collars_sleeves"].append(cs)

        # 5. Patterns & Crafts
        for pat in self.FASHION_INDUSTRY_DICT["patterns_crafts"]:
            if pat in text_description and pat not in fashion_data["patterns_crafts"]:
                fashion_data["patterns_crafts"].append(pat)

        # 6. Style Aesthetics
        for sty in self.FASHION_INDUSTRY_DICT["style_vibes"]:
            short_name = sty.split()[0]
            if (short_name in text_description or sty in text_description) and sty not in fashion_data["style_aesthetics"]:
                fashion_data["style_aesthetics"].append(sty)

        # Dynamic sentence extraction for fashion lines
        lines = text_description.split("\n")
        for line in lines:
            if any(k in line for k in ["面料", "材质", "手感", "织造"]):
                phrases = self._extract_key_phrases(self._clean_header(line.strip()), exclude={"面料", "材质", "采用", "质感"})
                for p in phrases:
                    if p not in fashion_data["fabrics_textures"] and len(p) >= 2:
                        fashion_data["fabrics_textures"].append(p)
            if any(k in line for k in ["剪裁", "版型", "廓形", "线条"]):
                phrases = self._extract_key_phrases(self._clean_header(line.strip()), exclude={"剪裁", "版型", "廓形", "呈现"})
                for p in phrases:
                    if p not in fashion_data["silhouettes"] and len(p) >= 2:
                        fashion_data["silhouettes"].append(p)

        # Summary compose
        summary_items = []
        if fashion_data["garment_categories"]:
            summary_items.append(f"品类: {', '.join(fashion_data['garment_categories'][:3])}")
        if fashion_data["fabrics_textures"]:
            summary_items.append(f"面料: {', '.join(fashion_data['fabrics_textures'][:3])}")
        if fashion_data["silhouettes"]:
            summary_items.append(f"版型: {', '.join(fashion_data['silhouettes'][:2])}")
        if fashion_data["style_aesthetics"]:
            summary_items.append(f"风格: {', '.join(fashion_data['style_aesthetics'][:2])}")

        fashion_data["fashion_summary"] = " | ".join(summary_items) if summary_items else "专业服装款式与面料设计"
        return fashion_data

    # Professional Hosiery & Socks Industry Dictionary (袜业垂直细分检测)
    HOSIERY_SOCKS_DICT = {
        "socks_types": [
            "船袜", "隐形袜", "浅口袜", "短袜", "低帮踝袜", "中筒袜", "小腿袜", "长筒袜", "及膝长袜", "过膝袜", "大腿袜",
            "堆堆袜", "连裤袜", "丝袜", "打底裤袜", "防勾丝丝袜", "网眼袜", "渔网袜", "蕾丝花边袜", "荷叶边袜",
            "运动毛圈袜", "专业篮球袜", "压力袜", "静脉曲张袜", "五指袜", "分趾袜", "瑜伽防滑袜", "保暖加绒袜", "雪地袜"
        ],
        "colors_denier": [
            "纯黑色", "哑光黑", "纯白色", "奶白色", "象牙白", "米白色", "自然肤色", "浅肤色", "深肤色", "肉色",
            "焦糖色", "咖啡色", "美拉德棕", "浅灰色", "花灰色", "炭灰色", "藏青色", "墨绿色", "酒红色",
            "樱花粉", "马卡龙色", "多巴胺彩色",
            "超薄透肉 (10D-20D)", "薄款微透肉 (30D)", "中厚微透 (50D-80D)", "哑光不透肉 (120D)", "秋冬加厚加绒 (200D+)"
        ],
        "materials_weaves": [
            "精梳纯棉", "高支纯棉", "长绒棉", "桑蚕丝", "尼龙丝滑", "天鹅绒", "包芯丝", "氨纶高弹莱卡",
            "美利奴羊毛", "兔毛混纺", "莫代尔", "天然竹纤维", "冰丝凉感",
            "双针罗纹", "细坑条织造", "粗针罗纹", "平针素面", "毛圈加厚减震底", "透气网眼", "手工无骨缝头", "无痕一片式", "硅胶防滑跟"
        ],
        "patterns_crafts": [
            "纯色素面", "经典双条纹", "英伦格纹", "复古波点", "重工蕾丝花边", "立体木耳边",
            "字母提花刺绣", "卡通提花", "撞色拼接", "蝴蝶结绑带", "小珍珠点缀", "防滑滴胶"
        ],
        "pairing_styles": [
            "搭配乐福鞋", "搭配马丁靴", "搭配运动老爹鞋", "搭配玛丽珍鞋", "搭配高跟鞋", "搭配帆布鞋", "搭配皮鞋",
            "日系学院风", "JK制服风", "极简Cleanfit", "复古文艺风", "美式运动高街", "甜美少女风", "优雅职场风"
        ]
    }

    def extract_socks_details(self, text_description: str) -> Dict[str, Any]:
        """
        Specialized Hosiery & Socks Industry Feature Extractor.
        Deconstructs sock type/length, colors/denier, fabrics/weaves, patterns/crafts, and pairing style.
        """
        socks_data: Dict[str, Any] = {
            "has_socks": False,
            "socks_types": [],
            "colors_denier": [],
            "materials_weaves": [],
            "patterns_crafts": [],
            "pairing_styles": [],
            "socks_summary": ""
        }
        if not text_description:
            return socks_data

        # Detect socks relevance
        socks_keywords = ["袜", "丝袜", "中筒", "短袜", "长袜", "过膝", "船袜", "连裤", "堆堆袜", "袜筒", "脚踝", "足部"]
        if any(k in text_description for k in socks_keywords):
            socks_data["has_socks"] = True

        # 1. Sock Types & Lengths
        for st in self.HOSIERY_SOCKS_DICT["socks_types"]:
            if st in text_description and st not in socks_data["socks_types"]:
                socks_data["socks_types"].append(st)

        # 2. Colors & Denier
        for cd in self.HOSIERY_SOCKS_DICT["colors_denier"]:
            if cd in text_description and cd not in socks_data["colors_denier"]:
                socks_data["colors_denier"].append(cd)

        # 3. Materials & Weaves
        for mw in self.HOSIERY_SOCKS_DICT["materials_weaves"]:
            if mw in text_description and mw not in socks_data["materials_weaves"]:
                socks_data["materials_weaves"].append(mw)

        # 4. Patterns & Crafts
        for pc in self.HOSIERY_SOCKS_DICT["patterns_crafts"]:
            if pc in text_description and pc not in socks_data["patterns_crafts"]:
                socks_data["patterns_crafts"].append(pc)

        # 5. Pairing Styles
        for ps in self.HOSIERY_SOCKS_DICT["pairing_styles"]:
            if ps in text_description and ps not in socks_data["pairing_styles"]:
                socks_data["pairing_styles"].append(ps)

        # Dynamic sentence extraction for sock details
        lines = text_description.split("\n")
        for line in lines:
            if any(k in line for k in ["袜", "丝袜", "袜品"]):
                phrases = self._extract_key_phrases(self._clean_header(line.strip()), exclude={"袜子", "袜品", "搭配", "穿着"})
                for p in phrases:
                    if len(p) >= 2 and p not in socks_data["socks_types"] and p not in socks_data["colors_denier"]:
                        socks_data["socks_types"].append(p)

        # Compose socks summary
        summary_parts = []
        if socks_data["socks_types"]:
            summary_parts.append(f"款式: {', '.join(socks_data['socks_types'][:3])}")
        if socks_data["colors_denier"]:
            summary_parts.append(f"色彩/厚度: {', '.join(socks_data['colors_denier'][:3])}")
        if socks_data["materials_weaves"]:
            summary_parts.append(f"材质工艺: {', '.join(socks_data['materials_weaves'][:2])}")
        if socks_data["pairing_styles"]:
            summary_parts.append(f"搭配: {', '.join(socks_data['pairing_styles'][:2])}")

        socks_data["socks_summary"] = " | ".join(summary_parts) if summary_parts else "专业袜品款式与色彩工艺解构"
        return socks_data

    COMPLIANCE_DICT = {
        "attire_risks": [
            "过于暴露", "领口过低", "透光材质", "未规范着装", "衣着欠妥", "布料过少", "走光风险"
        ],
        "camera_risks": [
            "局部特写过近", "不良视角", "聚焦敏感部位", "过度特写", "机位欠妥"
        ],
        "pose_risks": [
            "诱导性动作", "低俗暗示", "不雅姿态", "挑逗神态", "大幅度动作"
        ],
        "remediation_templates": {
            "attire": "建议在出镜时增加开衫、外套或丝巾外搭，规范领口与着装覆盖度。",
            "camera": "建议将机位拉远至标准半身或中景，避免单一身体局部近距离特写超过2秒。",
            "pose": "建议保持端正、自然出镜姿势，避免大幅度俯身或刻意动作。",
            "scene": "若属舞蹈或专业健身教学，请在标题中明确标注专业属性并选择规范运动场景。"
        }
    }

    def extract_compliance_audit(self, text_description: str) -> Dict[str, Any]:
        """
        Compliance, Appropriateness & Actionable Remediation Parser.
        Evaluates risk level and outputs concrete remediation advice.
        """
        audit_result: Dict[str, Any] = {
            "risk_level": "PASS",       # "PASS" | "REVIEW" | "BLOCK"
            "risk_score": 0.05,
            "issue_tags": [],
            "remediation_advice": [],
            "compliance_summary": "画面内容健康合规，着装与机位符合平台规范。"
        }
        if not text_description:
            return audit_result

        found_attire_risks = [r for r in self.COMPLIANCE_DICT["attire_risks"] if r in text_description]
        found_camera_risks = [r for r in self.COMPLIANCE_DICT["camera_risks"] if r in text_description]
        found_pose_risks = [r for r in self.COMPLIANCE_DICT["pose_risks"] if r in text_description]

        # Explicit block triggers
        block_keywords = ["严重暴露", "露骨", "违禁", "极其不雅", "严重违规"]
        if any(bw in text_description for bw in block_keywords):
            audit_result["risk_level"] = "BLOCK"
            audit_result["risk_score"] = 0.95
            audit_result["issue_tags"].append("严重合规风险_拦截")
            audit_result["remediation_advice"].append("画面存在严重合规违规，无法发布，请重新更换合规素材。")
            audit_result["compliance_summary"] = "检测到严重违规内容，已触发安全拦截。"
            return audit_result

        # Review / Remediation triggers
        if found_attire_risks:
            audit_result["issue_tags"].append("着装需规范")
            audit_result["remediation_advice"].append(self.COMPLIANCE_DICT["remediation_templates"]["attire"])
        if found_camera_risks:
            audit_result["issue_tags"].append("机位需拉远")
            audit_result["remediation_advice"].append(self.COMPLIANCE_DICT["remediation_templates"]["camera"])
        if found_pose_risks:
            audit_result["issue_tags"].append("姿态需调整")
            audit_result["remediation_advice"].append(self.COMPLIANCE_DICT["remediation_templates"]["pose"])

        # Check explicit tags or recommendations mentioned in VLM output
        lines = text_description.split("\n")
        for line in lines:
            if "整改建议" in line or "整改" in line or "建议" in line:
                cleaned = self._clean_header(line.strip())
                if len(cleaned) > 5 and cleaned not in audit_result["remediation_advice"]:
                    audit_result["remediation_advice"].append(cleaned)
            if "合规" in line and ("问题" in line or "风险" in line or "瑕疵" in line):
                cleaned = self._clean_header(line.strip())
                if len(cleaned) > 4:
                    audit_result["issue_tags"].append(cleaned[:12])

        if audit_result["issue_tags"] or len(audit_result["remediation_advice"]) > 0:
            audit_result["risk_level"] = "REVIEW"
            audit_result["risk_score"] = 0.65
            audit_result["compliance_summary"] = "画面存在边缘瑕疵或着装/机位规范建议，请参考整改指南调整后发布。"
        else:
            audit_result["issue_tags"].append("合规达标")

        audit_result["issue_tags"] = list(set(audit_result["issue_tags"]))
        return audit_result

    def _clean_header(self, text: str) -> str:
        """Strip leading numbering and section labels like '1. 主体与细节：'."""
        return re.sub(r'^[0-9一二三四五六七八九十\.\s、\-\*#]*[^\n：:]{1,20}[：:]\s*', '', text).strip()

    def _extract_key_phrases(self, text: str, exclude: Set[str]) -> List[str]:
        """Helper to extract clean candidate tag tokens from sentence."""
        cleaned = re.sub(r"【.*?】", "", text)
        cleaned = re.sub(r"[，。！？；;：:\(\)（）]", " ", cleaned)
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 2 and len(t.strip()) <= 8]
        valid = [t for t in tokens if t not in exclude and not any(ex in t for ex in ["分析", "结果", "主要", "整体", "呈现", "采用", "画面", "表现"])]
        return valid[:2]

    def flatten_tags(self, text_description: str) -> List[str]:
        """Get flattened list of unique tags across all categories."""
        cat_tags = self.generate_categorized_tags(text_description)
        flat = []
        for tags in cat_tags.values():
            flat.extend(tags)
        return list(set(flat))

tag_generator = TagGenerator()


