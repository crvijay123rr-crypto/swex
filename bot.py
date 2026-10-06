import os
import json
import urllib.parse
import re
import math
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests

# ================= CONFIGURATION =================
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # Apna Telegram Bot Token yahan dalein
USER_ID = "2086041"                     # Apna User ID
AUTH_TOKEN = ""                         # Premium/Locked notes nikalne ke liye apna Auth Token yahan dalein (e.g., "Bearer eyJhb...")
API_COURSES_FILE = "api_courses.json"   # Naye batches yahan save honge
ITEMS_PER_PAGE = 30                     # Ek page par 30 batches
# =================================================

# ================= OLD BATCHES LIST =================
RAW_OLD_BATCHES = """
6ab9209e04d63dccd41ed518|UPSI 2026 दरोगा बैच
6ab25570b2d758e23476cd66|Maths Special VOD 8.0
6ab2555fb2d758e23476cd5d|English Special VOD 6.0
6ab2555bb2d758e23476cd58|Reasoning foundation Vod 3.0
6ab25556b2d758e23476cd48|GS Special VOD 3.0
6ab25547b2d758e23476cd2f|Selection Batch VOD 6.0
6aabf36eb861d1748aedea09|Science Foundation Batch 3.0
6aabf366b861d1748aede9fe|Railway Foundation 8.0
6a9c1a854d63c7a67104bba6|Selection Batch 12.0
6a9c1a754d63c7a6710471af|Maths Special 12.0
6a9c1a6b4d63c7a6710471a3|English Special 12.0
6a9c1a594d63c7a67104719d|Reasoning Special 12.0
6a9c1a484d63c7a671047177|Reasoning Foundation 2.0
6a9c19224d63c7a671047094|GS Special 12.0
6a9c19044d63c7a671047074|GS Foundation 2.0
6a8d695d6a1aff889c4dccf2|Selection Batch VOD 5.0
6a8d69566a1aff889c4dcce0|Maths Special VOD 7.0
6a8d694c6a1aff889c4dccdb|English Special VOD 5.0
6a8d686d6a1aff889c4cad17|Reasoning foundation VOD 2.0
6a8d68256a1aff889c4cace7|GS Special VOD 2.0
6a8afeacb81ad24d70be0414|Maths Basic Foundation 1.0
6a8afd9184792b4078b5f41d|परमवीर बैच SSC GD 2027
6a8313e74691f0ed5fe23507|Railway Foundation 7.0
6a8313e14691f0ed5fe23501|Science Foundation Batch 2.0
6a7b12ffb50d9d2997e30125|UPSSSC PET 2026
6a79b656bf0cd1e453764d62|हिंदी Special Batch
6a79b653bf0cd1e453764d4b|MP GK + Science Special
6a79b650bf0cd1e453764d46|MP GK special
6a747d308c3766ca13017a9c|GS Foundation 1.0
6a747d2d8c3766ca13017a97|GS Special 11.0
6a673b894700100f9d394551|Reasoning Special 11.0
6a673b854700100f9d39454b|English Special 11.0
6a673b824700100f9d394545|Maths Special 11.0
6a673b7e4700100f9d39452d|Selection Batch 11.0
6a673b434700100f9d394486|GS Special VOD 1.0
6a5e38ca8eefdd1ae59a2a2f|Reasoning Crash Course
6a5a11838eefdd1ae57e6b1e|English Special VOD 4.0
6a5a117b8eefdd1ae57e6b09|Selection Batch VOD 4.0
6a5a116e8eefdd1ae57e6aec|Maths Special VOD 6.0
6a5a11668eefdd1ae57e6ae7|Reasoning Foundation 1.0
6a5a11608eefdd1ae57e6ae1|Reasoning foundation VOD 1.0
6a4e376d5bac0ae4bab5a040|Railway Foundation 6.0
6a4e35315bac0ae4bab52444|Science special Foundation Batch
6a462e62b927c1a84a8b7879|Selection Batch - 10
6a462e5db927c1a84a8b7858|Maths Special - 10
6a462e56b927c1a84a8b7852|English Special - 10
6a462e4eb927c1a84a8b784c|GS Special - 10
6a462e48b927c1a84a8b7846|Reasoning Special - 10
6a3fe6b8b927c1a84a453df2|Maths संपूर्ण Batch 30 days
6a268ce8b927c1a84a018468|SSC special 5000 MCQ batch
6a268a36b927c1a84afff936|Selection Batch - 9
6a268a30b927c1a84afff930|Maths Special - 9
6a268a2bb927c1a84afff927|English Special - 9
6a268a23b927c1a84afff921|GS Special - 9
6a268a1bb927c1a84afff91b|Reasoning Special - 9
6a1fe6bbb927c1a84abc606f|CGL RAPID BATCH
6a1fe6b8b927c1a84abc6051|Banking Special Maths 1.0
6a1fe6b6b927c1a84abc604b|English Special VOD 3.0
6a1fe6b3b927c1a84abc6046|Maths Special VOD 5.0
6a1fe6acb927c1a84abc603d|Selection Batch VOD 3.0
6a1d6b27b927c1a84a934528|Railway Foundation Batch -5
6a06e488b927c1a84a90a818|Selection Batch VOD 2.0
6a06e47eb927c1a84a90a809|English Special VOD Batch-2.0
6a06e470b927c1a84a90a804|Maths Special VOD Batch-4.0
69f990f7b927c1a84afd2673|Selection Batch - 8
69f990f3b927c1a84afcf32f|Maths Special-8
69f990eeb927c1a84afcbff8|English Special-8
69f990e6b927c1a84afcbff2|GS Special -8
69f990e0b927c1a84afcbfed|Reasoning Special-8
69eb26c022cc6f4d5fd1b02e|Railway Foundation Batch -4
69e0c897e59683658c6e86e9|testing
69d4b8c322cc6f4d5f00839f|Selection Batch - 7
69d4b8ba22cc6f4d5f008399|Maths Special-7
69d4b8b422cc6f4d5f008386|English Special-7
69d4b8af22cc6f4d5f008380|GS Special - 7
69d4b8a822cc6f4d5f00837b|Reasoning Special-7
69d3ccb430735a1ba7ee7fe6|Railway one shot
69ce5531059a63537911ff23|English Practice batch (Pre + mains)
69c212d958a075a6c9aef2ab|English Special VOD Batch-1
69c212d658a075a6c9aef2a6|Maths Special VOD Batch-3
69bbb54302b07cbc32f33240|Selection Batch VOD 1.0
69b3caab9d14466cd0cb01f6|BSE for ALP CBT 2
69ae9daca2b1ae04337afa9a|Selection Batch -6
69ae9da7a2b1ae04337afa89|Maths Special-6
69ae9da2a2b1ae04337afa76|English Special-6
69ae9d95a2b1ae04337ad475|GS Special-6
69ae9d8fa2b1ae04337a8875|Reasoning Special-6
69ad2434a2b1ae0433673e61|आरम्भ Batch
699eb686a2b1ae04330b857f|Railway Foundation Batch -3
69904a6f466e8361a4fb8066|Maths Special VOD Batch-2
698487d5fdd21a8a2d1a5270|GS संपूर्ण Batch
698481ddfdd21a8a2d18ac80|English Special-5
698481d9fdd21a8a2d18ac76|Maths Special-5
698481d5fdd21a8a2d18ac70|GS Special-5
698481cefdd21a8a2d18ac6a|Reasoning Special-5
698481c9fdd21a8a2d18ac5b|Selection Batch-5
697df3954ca8c7fbe8f501ee|RRB Group D Batch
69622fc8027f25d29ebca4f6|तथास्तु BATCH 2026
695b8c2d2feca20f81c25e5b|Selection Batch-4
695b8c282feca20f81c25e55|Reasoning Special-4
695b8c232feca20f81c25e4f|English Special-4
695b8c1e2feca20f81c25e48|GS Special-4
695b8c182feca20f81c25e42|Maths Special-4
69550afab54cadeb6105fa51|उप्र कांस्टेबल सिपाही BATCH
6946ab747610406230d5e1b8|Eduquity Revision Batch
694403528b3dd15b95906023|Railway Reasoning Batch
6943f165cd0a679bc120abf4|Science Booster Batch
6943f10fcd0a679bc1207d93|Railway Foundation Batch -2
69416bb56385517afa46f6fe|UP Lekhpal Special
693ff2801f7d472f7eeac163|NTPC PSYCHO BATCH
693aa8016385517afa84329d|UP होमगार्ड Batch
69367eb033d222e80e32c6de|Reasoning Special-3
69367ea733d222e80e32c6d9|English Special-3
69367ea133d222e80e32c6ce|Selection Batch-3
69367e9933d222e80e32c6c9|Maths Special-3
69367c0233d222e80e32ab9a|GS Special-3
6933f618dd258fd3232fcf33|UPSI 2025 POLITY +मूलविधि
6933f35cdd258fd32320c55d|UPSI 2025 दरोगा बैच
69329844dd258fd3230f50d7|SSC GD Target Batch
69204beb39642e9188a548b9|NCERT Science Foundation Batch 2026-27
69204816dd258fd323a45956|Railway Foundation Batch
691d6de4dd258fd32356421a|Railway Group-D Science VOD Batch
69150be0932c0deb70330767|Maths Special VOD Batch
690b0fa65085387730114664|Maths Special-2
690b0ee719fedfd663790697|English Special-2
690b0e556aeca24e9398c340|Reasoning Special-2
690b0cdc6aeca24e9397ab6f|Selection Batch-2
690afc8bf48d1caffd0c0319|GS Special-2
68ef76338b84905b84eebde7|Vocab Mastery VOD Batch
68e7b92dd191c00e5c8d713e|SSC MAINS MATHS BATCH
68e7b6e6aaf4383d1192dfb6|SSC MAINS ENGLISH BATCH
68e27174dfde12332485c494|SSC Mains Batch
68dbd603f975d67976534e12|Selection Batch-1
68dbdf3a63a1698bf4194576|Group D 40 days science Batch
68dbd69163a1698bf4194575|GS Special-1
68dbd66763a1698bf4194574|Reasoning Special-1
68dbd51563a1698bf4194573|English Special-1
68dbd32801d050d5b62e45cc|Science Special foundation Batch
68d7a797209cc08d6e31f672|maths recorded gagan pratap sir
68d6550a99a6043c5d2dbca1|SSC 2024 Exams Best Questions Solution
68ce5fe8bb3c8f24bb3d4f77|Maths Special-1
68be7de9a721af475c9b04b4|सम्पूर्ण BATCH MATHS SPECIAL
68bc5c26a721af475c9ac2a5|RAILWAY FREE BATCH
68bc5bc8a721af475c9ac21f|RAILWAY ADVANCE MATHS
68bc5ba8a721af475c9ac19b|SSC MATHS PYQ SERIES
68bc5b80a721af475c9ac115|COMPLETE ADVANCE MATHS
684050f55db342bb13da8211|SSC Recorded Batch
683def9c2f4523ef6c8b18cb|Defence all in one
68a6be03a741c9fd7187fca3|Railway all in one - 2
683def9c2f4523ef6c8b18c5|Defence- all in one
683def9c2f4523ef6c8b18bd|Railways- all in one
683def9c2f4523ef6c8b18b7|SSC all in one
683def9c2f4523ef6c8b18ae|Railway all in one
"""

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

def get_headers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.selectionway.com/",
        "Accept": "application/json"
    }
    if AUTH_TOKEN:
        headers["Authorization"] = AUTH_TOKEN if "Bearer" in AUTH_TOKEN else f"Bearer {AUTH_TOKEN}"
    return headers

# ================= LIST MANAGEMENT =================

def get_old_batches():
    batches = []
    for line in RAW_OLD_BATCHES.strip().split('\n'):
        if '|' in line:
            b_id, b_title = line.split('|', 1)
            batches.append({"id": b_id.strip(), "title": b_title.strip()})
    return batches

def find_courses_in_json(data, seen_ids):
    courses = []
    if isinstance(data, dict):
        c_id = data.get("id") or data.get("_id")
        c_title = data.get("title") or data.get("courseName")
        if c_id and c_title and str(c_id) not in seen_ids:
            if len(str(c_title)) > 2:
                courses.append({"id": str(c_id), "title": str(c_title)})
                seen_ids.add(str(c_id))
        for key, value in data.items():
            courses.extend(find_courses_in_json(value, seen_ids))
    elif isinstance(data, list):
        for item in data:
            courses.extend(find_courses_in_json(item, seen_ids))
    return courses

def fetch_api_batches():
    courses_list = []
    seen_ids = set()
    endpoints = [
        f"https://gdgoenkaratia.com/api/courses/active?userId={USER_ID}",
        f"https://gdgoenkaratia.com/api/courses/purchased?userId={USER_ID}",
        "https://www.selectionway.com/_next/data/KtYrAUsK86sxjti_V4hrD/en-US/user/batches.json",
        "https://www.selectionway.com/_next/data/KtYrAUsK86sxjti_V4hrD/en-US/user/batches/live.json?slug=live",
        "https://www.selectionway.com/_next/data/KtYrAUsK86sxjti_V4hrD/en-US/user/batches/recorded.json?slug=recorded"
    ]
    for url in endpoints:
        try:
            res = requests.get(url, headers=get_headers(), timeout=15)
            if res.status_code == 200:
                found = find_courses_in_json(res.json(), seen_ids)
                courses_list.extend(found)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            
    if courses_list:
        with open(API_COURSES_FILE, "w", encoding="utf-8") as f:
            json.dump(courses_list, f, indent=4, ensure_ascii=False)
    return courses_list

def get_new_batches():
    if os.path.exists(API_COURSES_FILE):
        try:
            with open(API_COURSES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def get_all_batches():
    old = get_old_batches()
    new = get_new_batches()
    seen = {c['id'] for c in old}
    combined = list(old)
    for c in new:
        if c['id'] not in seen:
            combined.append(c)
            seen.add(c['id'])
    return combined


# ================= DATA FETCHING (Classes, Sheets, Tests) =================

def fetch_course_sheets(course_id):
    """External Sheets Fetcher (pdfs?groupBy=topic)"""
    url = f"https://gdgoenkaratia.com/api/courses/{course_id}/pdfs?groupBy=topic"
    try:
        res = requests.get(url, headers=get_headers(), timeout=15)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def fetch_course_tests(course_id):
    """External Tests Fetcher"""
    url = f"https://gdgoenkaratia.com/api/courses/{course_id}/tests"
    try:
        res = requests.get(url, headers=get_headers(), timeout=15)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def fetch_topics(course_id):
    url = f"https://gdgoenkaratia.com/api/topic-and-section?courseId={course_id}&userId={USER_ID}"
    try:
        res = requests.get(url, headers=get_headers(), timeout=15)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def fetch_classes(topic_id, course_id):
    url = f"https://gdgoenkaratia.com/api/topics/{topic_id}/classes?courseId={course_id}"
    try:
        res = requests.get(url, headers=get_headers(), timeout=15)
        if res.status_code == 200: return res.json()
    except: pass
    return None

# ================= EXTRACTION LOGIC =================

def check_locked(item_dict):
    for key in ("isLocked", "locked", "is_lock"):
        if item_dict.get(key) in [True, "true", "1"]:
            return True
    return False

def generate_txt_for_course(course_id, course_title, mode="full", quality="480"):
    if mode == "notes": doc_type = "NOTES ONLY (Class PDFs)"
    elif mode == "sheets": doc_type = "EXTRA SHEETS ONLY"
    elif mode == "tests": doc_type = "TESTS ONLY"
    elif mode == "all": doc_type = "EVERYTHING (All Media + Sheets + Tests)"
    else: doc_type = f"FULL BATCH ({quality}p Videos + Notes + Sheets)"

    txt_content = f"Course: {course_title}\nCourse ID: {course_id}\nType: {doc_type}\n" + "="*50 + "\n\n"
    has_content = False
    
    # 1. EXTRA SHEETS EXTRACTION
    if mode in ["sheets", "full", "all"]:
        sheets_data = fetch_course_sheets(course_id)
        if sheets_data and "data" in sheets_data and sheets_data["data"]:
            txt_content += "📚 --- COURSE EXTRA SHEETS ---\n\n"
            for group in sheets_data["data"]:
                topic_name = group.get("_id", "General Sheets")
                txt_content += f"📂 Folder: {topic_name}\n{'-'*30}\n"
                
                for pdf in group.get("pdfs", []):
                    pdf_url = pdf.get('url', '')
                    pdf_name = pdf.get('name', 'Sheet')
                    is_locked = check_locked(pdf)
                    
                    if is_locked or not pdf_url:
                        txt_content += f"    [SHEET] {pdf_name}: [LOCKED/PREMIUM] Need Auth Token.\n"
                    else:
                        encoded_pdf_url = urllib.parse.quote(pdf_url, safe=':/')
                        txt_content += f"    [SHEET] {pdf_name}: {encoded_pdf_url}\n"
                        has_content = True
                txt_content += "\n"
            txt_content += "="*50 + "\n\n"

    # 2. EXTERNAL TESTS EXTRACTION
    if mode in ["tests", "all"]:
        tests_data = fetch_course_tests(course_id)
        if tests_data and "data" in tests_data and tests_data["data"]:
            txt_content += "📝 --- COURSE MOCK TESTS ---\n\n"
            test_list = tests_data["data"]
            if isinstance(test_list, list):
                for test in test_list:
                    t_name = test.get('title', test.get('testName', 'Unnamed Test'))
                    t_url = test.get('url', test.get('testUrl', ''))
                    is_locked = check_locked(test)
                    
                    if is_locked or not t_url:
                        txt_content += f"    [TEST] {t_name}: [LOCKED/PREMIUM] Need Auth Token.\n"
                    else:
                        encoded_t_url = urllib.parse.quote(t_url, safe=':/')
                        txt_content += f"    [TEST] {t_name}: {encoded_t_url}\n"
                        has_content = True
                txt_content += "\n" + "="*50 + "\n\n"

    # 3. REGULAR TOPICS & CLASSES EXTRACTION
    if mode in ["full", "notes", "all", "tests"]:
        topics_data = fetch_topics(course_id)
        if topics_data and "data" in topics_data and "topics" in topics_data["data"]:
            topics = topics_data["data"]["topics"]
            
            for topic in topics:
                t_name = topic.get("topicName", "Unnamed Topic")
                t_id = topic.get("topicId", "")
                
                classes_data = fetch_classes(t_id, course_id)
                if classes_data and "data" in classes_data and "classes" in classes_data["data"]:
                    topic_header_added = False
                    topic_str = ""
                    
                    for cls in classes_data["data"]["classes"]:
                        title = cls.get("title", "Unnamed Class")
                        recordings = cls.get("mp4Recordings", [])
                        
                        pdfs = []
                        for key in ["classPdf", "notes", "handwrittenNotes", "notesPdf", "classNotes", "dpp"]:
                            items = cls.get(key, [])
                            if isinstance(items, list): pdfs.extend(items)
                            elif isinstance(items, dict): pdfs.append(items)
                            
                        tests = []
                        for key in ["tests", "classTests", "mockTests"]:
                            items = cls.get(key, [])
                            if isinstance(items, list): tests.extend(items)
                            elif isinstance(items, dict): tests.append(items)
                        
                        class_str = f"  - Class: {title}\n"
                        items_added = False
                        
                        # Videos (Only for full/all)
                        if mode in ["full", "all"]:
                            for rec in recordings:
                                vid_quality = str(rec.get('quality', ''))
                                vid_url = rec.get('url', '')
                                vid_size = rec.get('size', 'N/A')
                                is_locked = check_locked(rec)
                                
                                if mode == "all" or quality in vid_quality:
                                    items_added = True
                                    if is_locked or not vid_url:
                                        class_str += f"    [MP4 {vid_quality}] [LOCKED/PREMIUM] Need Auth Token to unlock.\n"
                                    else:
                                        encoded_vid_url = urllib.parse.quote(vid_url, safe=':/')
                                        class_str += f"    [MP4 {vid_quality}] Size: {vid_size}MB : {encoded_vid_url}\n"
                                        
                        # PDFs/Notes (For full/all/notes)
                        if mode in ["full", "all", "notes"]:
                            for pdf in pdfs:
                                pdf_url = pdf.get('url', '')
                                pdf_name = pdf.get('name', 'Note/PDF')
                                is_locked = check_locked(pdf)
                                items_added = True
                                
                                if is_locked or not pdf_url:
                                    class_str += f"    [PDF] {pdf_name}: [LOCKED/PREMIUM] Need Auth Token to unlock.\n"
                                else:
                                    encoded_pdf_url = urllib.parse.quote(pdf_url, safe=':/')
                                    class_str += f"    [PDF] {pdf_name}: {encoded_pdf_url}\n"
                                    
                        # Class Tests (For all/tests)
                        if mode in ["all", "tests"]:
                            for test in tests:
                                t_url = test.get('url', test.get('testUrl', ''))
                                t_name = test.get('name', test.get('title', 'Test'))
                                is_locked = check_locked(test)
                                items_added = True
                                
                                if is_locked or not t_url:
                                    class_str += f"    [TEST] {t_name}: [LOCKED/PREMIUM] Need Auth Token.\n"
                                else:
                                    encoded_t_url = urllib.parse.quote(t_url, safe=':/')
                                    class_str += f"    [TEST] {t_name}: {encoded_t_url}\n"
                                    
                        if items_added:
                            if not topic_header_added:
                                topic_str += f"Topic: {t_name} (ID: {t_id})\n{'-'*30}\n"
                                topic_header_added = True
                            topic_str += class_str + "\n"
                            has_content = True
                            
                    if topic_header_added:
                        txt_content += topic_str + "\n"

    if not has_content:
        return None
        
    safe_title = re.sub(r'[\\/*?:"<>|]', "", course_title).strip()
    filename = f"{safe_title}_{mode.capitalize()}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(txt_content)
    return filename

# ================= UI & PAGINATION =================

def get_page_text_and_markup(courses, page, list_type):
    total_pages = max(1, math.ceil(len(courses) / ITEMS_PER_PAGE))
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_courses = courses[start_idx:end_idx]
    
    type_label = "New Batches (API)" if list_type == "new" else "Old Batches" if list_type == "old" else "All Mixed Batches"
    
    text = f"📚 <b>{type_label} (Page {page}/{total_pages})</b>\n"
    text += f"<i>Total Available: {len(courses)} Batches</i>\n\n"
    
    for i, c in enumerate(page_courses, start_idx + 1):
        text += f"<b>{i}. {c['title']}</b>\n"
        text += f"🆔 <code>{c['id']}</code>\n\n"
        
    text += "👉 <i>ID par touch karke copy karein, aur Main Menu se extract karein.</i>"
    
    markup = InlineKeyboardMarkup()
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{list_type}_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{list_type}_{page+1}"))
    
    markup.row(*buttons) if buttons else None
    markup.row(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return text, markup

def get_main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=3)
    # Lists
    markup.add(
        InlineKeyboardButton("🆕 New", callback_data="show_new"),
        InlineKeyboardButton("🗄 Old", callback_data="show_old"),
        InlineKeyboardButton("📚 All", callback_data="show_all")
    )
    # Actions Layer 1
    markup.add(
        InlineKeyboardButton("🎥 Full (480p)", callback_data="ask_full"),
        InlineKeyboardButton("🔥 ALL Media", callback_data="ask_all")
    )
    # Actions Layer 2 (Specifics)
    markup.add(
        InlineKeyboardButton("📝 Notes", callback_data="ask_notes"),
        InlineKeyboardButton("📄 Sheets", callback_data="ask_sheets"),
        InlineKeyboardButton("📝 Tests", callback_data="ask_tests")
    )
    # Utils
    markup.add(
        InlineKeyboardButton("🚀 Bulk Extract All", callback_data="do_bulk"),
        InlineKeyboardButton("🔄 Sync", callback_data="sync")
    )
    return markup


# ================= BOT HANDLERS =================

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    msg = bot.send_message(message.chat.id, "🔄 <i>Fetching latest API updates... Please wait.</i>")
    fetch_api_batches()
    
    text = (
        "🌟 <b>Welcome to Premium Batch Extractor!</b> 🌟\n\n"
        "Choose an option below:\n"
        "• <b>Full:</b> 480p Videos + PDFs + Extra Sheets.\n"
        "• <b>ALL:</b> Sabhi Video Qualities + PDFs + Sheets + Tests.\n"
        "• <b>Notes/Sheets/Tests:</b> Sirf specific content nikalne ke liye.\n\n"
        "<i>Custom Commands:</i>\n"
        "<code>/full ID</code> (Extract 480p)\n"
        "<code>/full 720 ID</code> (Extract 720p)\n"
        "<code>/notes ID</code> | <code>/sheets ID</code> | <code>/tests ID</code>\n"
        "<code>/all ID</code>"
    )
    bot.edit_message_text(text, chat_id=message.chat.id, message_id=msg.message_id, reply_markup=get_main_menu_markup())


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data

    bot.answer_callback_query(call.id)

    if data == "main_menu":
        bot.edit_message_text("🌟 <b>Main Menu</b> 🌟\nChoose an option below:", chat_id=chat_id, message_id=msg_id, reply_markup=get_main_menu_markup())
        
    elif data == "show_new":
        courses = get_new_batches()
        if not courses:
            bot.send_message(chat_id, "❌ No API batches found. Please refresh.")
            return
        text, markup = get_page_text_and_markup(courses, page=1, list_type="new")
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup)

    elif data == "show_old":
        courses = get_old_batches()
        text, markup = get_page_text_and_markup(courses, page=1, list_type="old")
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup)

    elif data == "show_all":
        courses = get_all_batches()
        text, markup = get_page_text_and_markup(courses, page=1, list_type="all")
        bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup)
        
    elif data.startswith('page_'):
        _, list_type, page_str = data.split('_')
        page = int(page_str)
        
        if list_type == "new": courses = get_new_batches()
        elif list_type == "old": courses = get_old_batches()
        else: courses = get_all_batches()
            
        text, markup = get_page_text_and_markup(courses, page, list_type)
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=markup)
        except: pass
        
    elif data == "ask_full":
        msg = bot.send_message(chat_id, "🎥 <b>Send me the Course ID</b> to extract Full Batch:")
        bot.register_next_step_handler(msg, lambda m: process_extraction(chat_id, m.text, mode="full"))
        
    elif data == "ask_notes":
        msg = bot.send_message(chat_id, "📝 <b>Send me the Course ID</b> to extract ONLY Class Notes:")
        bot.register_next_step_handler(msg, lambda m: process_extraction(chat_id, m.text, mode="notes"))

    elif data == "ask_sheets":
        msg = bot.send_message(chat_id, "📄 <b>Send me the Course ID</b> to extract ONLY Extra Sheets:")
        bot.register_next_step_handler(msg, lambda m: process_extraction(chat_id, m.text, mode="sheets"))

    elif data == "ask_tests":
        msg = bot.send_message(chat_id, "📝 <b>Send me the Course ID</b> to extract ONLY Mock Tests:")
        bot.register_next_step_handler(msg, lambda m: process_extraction(chat_id, m.text, mode="tests"))

    elif data == "ask_all":
        msg = bot.send_message(chat_id, "🔥 <b>Send me the Course ID</b> to extract EVERYTHING (All Qualities):")
        bot.register_next_step_handler(msg, lambda m: process_extraction(chat_id, m.text, mode="all"))
        
    elif data == "sync":
        bot.send_message(chat_id, "🔄 Syncing with API...")
        fetch_api_batches()
        bot.send_message(chat_id, "✅ API Sync Complete! Batches updated.")
        
    elif data == "do_bulk":
        execute_bulk(chat_id)


@bot.message_handler(commands=['list', 'batches'])
def command_list_batches(message):
    courses = get_all_batches()
    if not courses:
        bot.send_message(message.chat.id, "❌ No courses found.")
        return
    text, markup = get_page_text_and_markup(courses, page=1, list_type="all")
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['bulk'])
def bulk_command(message):
    execute_bulk(message.chat.id)

@bot.message_handler(commands=['full', 'notes', 'sheets', 'tests', 'all'])
def direct_extract_command(message):
    parts = message.text.split()
    command = parts[0].lower().strip("/")
    raw_args = message.text.partition(" ")[2].strip()
    
    if not raw_args:
        bot.reply_to(message, f"⚠ <b>Usage:</b> <code>/{command} [quality] Course_ID</code>")
        return

    mode = command
    custom_quality = "480"

    match = re.match(r"^(360|480|720|1080)p?\s+(.+)$", raw_args, re.IGNORECASE)
    if match:
        custom_quality = match.group(1)
        raw_args = match.group(2).strip()

    process_extraction(message.chat.id, raw_args, mode=mode, quality=custom_quality)


# --- Extraction Executors ---

def process_extraction(chat_id, input_text, mode="full", quality="480"):
    text = input_text.strip()
    courses = get_all_batches()
    
    selected_course_id = text
    selected_title = "Custom Batch"
    
    for c in courses:
        if c['id'] == text or str(courses.index(c)+1) == text:
            selected_course_id = c['id']
            selected_title = c['title']
            break
                
    if mode == "notes": mode_text = "📝 Notes Only"
    elif mode == "sheets": mode_text = "📄 Extra Sheets Only"
    elif mode == "tests": mode_text = "📝 Tests Only"
    elif mode == "all": mode_text = "🔥 Everything (All Qualities)"
    else: mode_text = f"🎥 Full Batch (STRICT {quality}p)"
    
    progress = bot.send_message(chat_id, f"⏳ Extracting: <b>{selected_title}</b>\nMode: {mode_text}\n<i>Please wait...</i>")
    
    filename = generate_txt_for_course(selected_course_id, selected_title, mode=mode, quality=quality)
    
    if filename and os.path.exists(filename):
        with open(filename, "rb") as doc:
            bot.send_document(chat_id, doc, caption=f"✅ <b>Successfully Extracted!</b>\n📚 Batch: {selected_title}\n⚙️ Mode: {mode_text}")
        os.remove(filename)
        bot.delete_message(chat_id, progress.message_id)
    else:
        bot.edit_message_text("❌ <b>Failed to fetch data.</b> Invalid Course ID, locked API, or empty batch for this mode.", chat_id=chat_id, message_id=progress.message_id)

def execute_bulk(chat_id):
    courses = get_all_batches()
    if not courses:
        bot.send_message(chat_id, "❌ No courses found.")
        return
        
    bot.send_message(chat_id, f"🚀 Bulk extraction started for <b>{len(courses)} batches</b> (480p Mode). Please wait...")
    
    for c in courses:
        c_id = c['id']
        c_title = c['title']
        msg = bot.send_message(chat_id, f"⏳ Extracting: <b>{c_title}</b>...")
        
        filename = generate_txt_for_course(c_id, c_title, mode="full", quality="480")
        
        if filename and os.path.exists(filename):
            with open(filename, "rb") as doc:
                bot.send_document(chat_id, doc, caption=f"✅ {c_title} (480p)")
            os.remove(filename)
            bot.delete_message(chat_id, msg.message_id)
        else:
            bot.edit_message_text(f"❌ Failed: <b>{c_title}</b>", chat_id=chat_id, message_id=msg.message_id)
            
    bot.send_message(chat_id, "🎉 <b>Bulk extraction completed!</b>")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    process_extraction(message.chat.id, message.text, mode="full")

if __name__ == "__main__":
    print("🤖 Bot Running: Notes, Sheets, Tests Dedicated Buttons Enabled!")
    bot.infinity_polling()
