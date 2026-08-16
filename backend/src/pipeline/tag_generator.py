import logging
import re
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

class TagGenerator:
    """
    [Node 3.5.1] Comprehensive Multi-Domain Taxonomy Tag Generator.
    Implements 6-Category Tag Hierarchy:
    - Subject (主体): 人物、美食、动物、自然、交通、科技、艺术等
    - ColorStyle (色彩风格): 胶片、极简、暖色、冷色、莫兰迪、赛博朋克等
    - Scene (场景空间): 室内、户外、座舱、街头、原野、展厅等
    - Emotion (情绪氛围): 治愈、俏皮、浪漫、活力、宁静、高级感等
    - Composition (构图景深): 特写、中心构图、留白、对角线、大景深等
    - Entity (具体实体): 自动从视觉大模型描述中提取核心具体名词实体
    """

    ONTOLOGY = {
        "Subject": {
            "人物肖像": ["人物", "女性", "女孩", "少女", "男士", "自拍", "人像", "模特", "女人", "男人", "面容"],
            "萌宠动物": ["猫", "狗", "犬", "宠物", "鸟", "野生动物", "小狗", "小猫", "幼犬", "幼崽", "动物", "金毛", "柯基", "柴犬", "毛茸茸", "飞鸟", "兔", "鱼"],
            "美食料理": ["美食", "料理", "菜品", "食材", "生蚝", "海鲜", "水果", "甜点", "肉质", "餐盘", "烘焙", "饮品", "咖啡", "佳肴"],
            "自然风光": ["山川", "风景", "自然", "湖泊", "河流", "森林", "天空", "雪山", "草原", "日落", "海洋", "沙滩", "日出", "海景"],
            "车辆交通": ["汽车", "车辆", "跑车", "车身", "座舱", "后视镜", "驾驶", "机车", "飞机", "轮船", "高铁", "公路"],
            "城市建筑": ["建筑", "高楼", "街景", "城市", "桥梁", "地标", "房屋", "街道", "夜景", "天际线", "广场"],
            "数码科技": ["数码", "手机", "电脑", "科技", "屏幕", "芯片", "机器人", "仪器", "电子", "硬件", "智能设备"],
            "服饰穿搭": ["服饰", "服装", "上衣", "裙子", "外套", "穿搭", "时尚", "珠宝", "鞋履", "饰品", "包袋"],
            "植物花卉": ["花卉", "植物", "绿植", "花瓣", "树木", "盆栽", "多肉", "枫叶", "樱花", "草地", "花朵"],
            "艺术设计": ["插画", "动漫", "雕塑", "画作", "艺术", "手办", "图形", "极简设计", "平面设计", "海报"]
        },
        "ColorStyle": {
            "粉色柔和": ["粉色", "粉白", "粉调", "樱花粉", "少女粉", "柔粉"],
            "暖色调": ["暖色", "暖光", "金黄", "夕阳色", "橙黄", "柔和暖光", "温馨色调", "暖调"],
            "冷色调": ["冷色", "蓝调", "冷青", "冰蓝", "深蓝", "清冷", "蓝灰色", "冷调"],
            "极简风": ["极简", "简约", "素雅", "纯净", "干净", "简练", "留白"],
            "胶片复古": ["胶片", "复古", "质感", "怀旧", "颗粒感", "老照片", "胶片色调"],
            "黑白高级": ["黑白", "灰度", "单色", "高对比黑白", "影调"],
            "高饱和绚丽": ["绚丽", "明亮", "鲜艳", "高饱和", "五彩", "斑斓", "明艳"],
            "莫兰迪色系": ["莫兰迪", "高级灰", "低饱和", "素净", "淡雅", "柔和色调"],
            "赛博朋克": ["赛博朋克", "霓虹", "荧光", "紫蓝光", "未来感光效", "光影交错"],
            "自然采光": ["自然光", "柔光", "侧光", "逆光", "透亮", "阳光透射", "晨光", "光影协调"]
        },
        "Scene": {
            "车内私密空间": ["车内", "后视镜", "驾驶座", "副驾驶", "车厢", "车载", "挡风玻璃"],
            "室内居所": ["室内", "卧室", "客厅", "阳台", "书房", "房间", "居家", "窗边", "床榻"],
            "餐厅咖啡厅": ["餐厅", "咖啡厅", "餐桌", "酒吧", "吧台", "餐馆", "厨房", "茶室"],
            "自然野外": ["户外", "森林", "山地", "海边", "湖畔", "田野", "草原", "公园", "雪地", "草坪"],
            "都市街头": ["街头", "马路", "人行道", "商场", "商业街", "市中心", "斑马线", "地铁"],
            "办公商务": ["办公室", "写字楼", "会议室", "工位", "书桌", "商务场所"],
            "展厅舞台": ["展厅", "博物馆", "舞台", "画廊", "秀场", "聚光灯下"]
        },
        "Emotion": {
            "治愈宁静": ["治愈", "宁静", "安详", "静谧", "惬意", "舒适", "平静", "放松", "温馨"],
            "俏皮害羞": ["俏皮", "害羞", "羞涩", "灵动", "甜美", "可爱", "微笑", "俏丽"],
            "浪漫唯美": ["浪漫", "唯美", "温存", "深情", "梦幻", "优雅", "柔美"],
            "孤独深沉": ["孤独", "深沉", "忧郁", "沉思", "冷峻", "神秘", "凝视"],
            "激情活力": ["活力", "热烈", "运动", "动感", "欢快", "兴奋", "朝气", "活泼"],
            "高端奢华": ["奢华", "高贵", "典雅", "精致", "高级感", "典重", "质感"],
            "鲜活诱人": ["新鲜", "诱人", "鲜活", "晶莹", "饱满", "美味", "光泽"]
        },
        "Composition": {
            "特写微距": ["特写", "近景", "局部", "微距", "细节放大", "面部特写", "特写视角"],
            "中心构图": ["中心", "对称", "正中", "居中", "聚焦中心", "中心视角"],
            "景深虚化": ["景深", "虚化", "大光圈", "背景虚化", "前景虚化", "浅景深"],
            "后视镜倒影": ["后视镜", "倒影", "镜面反射", "镜子", "反射视角"],
            "对角线延伸": ["对角线", "斜角", "延伸感", "倾斜构图", "视线引导"],
            "三分法构图": ["三分法", "黄金分割", "黄金比例", "侧边构图"],
            "全景俯瞰": ["俯拍", "全景", "俯瞰", "鸟瞰", "高空视角", "广角宏大"]
        },
        "Entity": {
            "人像服饰": ["服饰", "上衣", "外套", "发型", "眼镜", "妆容", "手饰", "帽子"],
            "汽车配件": ["后视镜", "方向盘", "中控台", "车窗", "座椅", "遮阳板"],
            "生鲜食材": ["生蚝", "蚝壳", "柠檬", "酱料", "冰块", "盘皿", "食材"],
            "电子产品": ["手机", "平板", "笔记本", "镜头", "相机", "耳机"],
            "萌宠宠物": ["小狗", "幼犬", "金毛", "猫咪", "宠物", "毛发"],
            "自然植物": ["花朵", "枝叶", "树干", "草丛", "流水", "岩石", "草坪"]
        }
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
            if re.search(r"主体|细节|人物|对象|动物", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"主体", "细节", "特征", "画面", "呈现", "如图"})
                for phrase in extracted:
                    if phrase not in result["Subject"] and len(phrase) >= 2:
                        result["Subject"].append(phrase)
            elif re.search(r"色彩|光影|基调|色调", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"色彩", "光影", "基调", "色调", "呈现", "搭配"})
                for phrase in extracted:
                    if phrase not in result["ColorStyle"] and len(phrase) >= 2:
                        result["ColorStyle"].append(phrase)
            elif re.search(r"场景|空间|环境|背景", line_str):
                extracted = self._extract_key_phrases(cleaned_text, exclude={"场景", "空间", "环境", "背景", "设置", "处于"})
                for phrase in extracted:
                    if phrase not in result["Scene"] and len(phrase) >= 2:
                        result["Scene"].append(phrase)
            elif re.search(r"情绪|氛围|风格|意境", line_str):
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
            "后视镜", "遮阳板", "手机", "汽车", "生蚝", "眼镜", "发饰", "上衣", "餐盘",
            "杯子", "项链", "手表", "鲜花", "背包", "幼犬", "小狗", "猫咪", "草坪", "树木", "椅子"
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
            result[cat] = result[cat][:4]

        return result

    def _clean_header(self, text: str) -> str:
        """Strip leading numbering and section labels like '1. 主体与细节：'."""
        return re.sub(r'^[0-9一二三四五六七八九十\.\s、\-\*#]*[^\n：:]{1,20}[：:]\s*', '', text).strip()

    def _extract_key_phrases(self, text: str, exclude: Set[str]) -> List[str]:
        """Helper to extract clean candidate tag tokens from sentence."""
        cleaned = re.sub(r"【.*?】", "", text)
        cleaned = re.sub(r"[，。！？；;：:\(\)（）]", " ", cleaned)
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 2 and len(t.strip()) <= 8]
        valid = [t for t in tokens if t not in exclude and not any(ex in t for ex in ["分析", "结果", "主要", "整体", "呈现", "采用"])]
        return valid[:2]

    def flatten_tags(self, text_description: str) -> List[str]:
        """Get flattened list of unique tags across all categories."""
        cat_tags = self.generate_categorized_tags(text_description)
        flat = []
        for tags in cat_tags.values():
            flat.extend(tags)
        return list(set(flat))

tag_generator = TagGenerator()


