import os
import json
import telebot
import requests

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)
COURSES_FILE = "courses.json"
USER_ID = "2086041"

def fetch_all_courses():
    url = f"https://gdgoenkaratia.com/api/courses/active?userId={USER_ID}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.selectionway.com/"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            res_json = res.json()
            if "data" in res_json:
                courses_list = []
                for item in res_json["data"]:
                    c_id = item.get("id")
                    c_title = item.get("title")
                    if c_id and c_title:
                        courses_list.append({"id": c_id, "title": c_title})
                if courses_list:
                    with open(COURSES_FILE, "w", encoding="utf-8") as f:
                        json.dump(courses_list, f, indent=4, ensure_ascii=False)
                    return courses_list
    except Exception as e:
        print(f"Error fetching active courses: {e}")
        
    if os.path.exists(COURSES_FILE):
        try:
            with open(COURSES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def fetch_topics(course_id):
    url = f"https://gdgoenkaratia.com/api/topic-and-section?courseId={course_id}&userId={USER_ID}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.selectionway.com/"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def fetch_classes(topic_id, course_id):
    url = f"https://gdgoenkaratia.com/api/topics/{topic_id}/classes?courseId={course_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.selectionway.com/"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def generate_txt_for_course(course_id, course_title):
    topics_data = fetch_topics(course_id)
    if topics_data and "data" in topics_data and "topics" in topics_data["data"]:
        topics = topics_data["data"]["topics"]
        txt_content = f"Course: {course_title}\nCourse ID: {course_id}\n" + "="*50 + "\n\n"
        
        for topic in topics:
            t_name = topic.get("topicName")
            t_id = topic.get("topicId")
            txt_content += f"Topic: {t_name} (ID: {t_id})\n{'-'*30}\n"
            
            classes_data = fetch_classes(t_id, course_id)
            if classes_data and "data" in classes_data and "classes" in classes_data["data"]:
                for cls in classes_data["data"]["classes"]:
                    title = cls.get("title")
                    pdfs = cls.get("classPdf", [])
                    recordings = cls.get("mp4Recordings", [])
                    
                    txt_content += f"  - Class: {title}\n"
                    for pdf in pdfs:
                        txt_content += f"    [PDF] {pdf.get('name')}: {pdf.get('url')}\n"
                    for rec in recordings:
                        txt_content += f"    [MP4 {rec.get('quality')}] Size: {rec.get('size')}MB : {rec.get('url')}\n"
                    txt_content += "\n"
            txt_content += "\n"
            
        # Clean filename using course title
        safe_title = "".join(c for c in course_title if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{safe_title}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(txt_content)
        return filename
    return None

@bot.message_handler(commands=['start', 'courses'])
def send_welcome(message):
    courses = fetch_all_courses()
    if not courses:
        bot.send_message(message.chat.id, "❌ Active batches load nahi ho paaye.")
        return
        
    text = f"📚 *Active Batches Found ({len(courses)}):*\n\n"
    for idx, c in enumerate(courses, 1):
        text += f"*{idx}*. {c['title']}\n`ID: {c['id']}`\n\n"
    text += "👉 Reply with the **Batch Number**, paste **Course ID**, or type /bulk to download all `.txt` files at once!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['bulk'])
def handle_bulk(message):
    courses = fetch_all_courses()
    if not courses:
        bot.send_message(message.chat.id, "❌ No active courses found for bulk extraction.")
        return
        
    bot.send_message(message.chat.id, f"🚀 Bulk extraction started for *{len(courses)} batches*. Please wait, files will be sent one by one...", parse_mode="Markdown")
    
    for c in courses:
        c_id = c['id']
        c_title = c['title']
        bot.send_message(message.chat.id, f"⏳ Extracting: *{c_title}*...", parse_mode="Markdown")
        
        filename = generate_txt_for_course(c_id, c_title)
        if filename and os.path.exists(filename):
            with open(filename, "rb") as doc:
                bot.send_document(message.chat.id, doc, caption=f"✅ Extracted Batch: {c_title}")
            os.remove(filename)
        else:
            bot.send_message(message.chat.id, f"❌ Failed to extract: *{c_title}*", parse_mode="Markdown")
            
    bot.send_message(message.chat.id, "🎉 Bulk extraction process completed successfully!")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text.strip()
    courses = fetch_all_courses()
    
    selected_course_id = ""
    selected_title = "Custom Batch"
    
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(courses):
            selected_course_id = courses[idx]['id']
            selected_title = courses[idx]['title']
    
    if not selected_course_id:
        selected_course_id = text
        for c in courses:
            if c['id'] == text:
                selected_title = c['title']
                break
                
    bot.send_message(message.chat.id, f"⏳ Extracting data for: *{selected_title}*...\nPlease wait.", parse_mode="Markdown")
    
    filename = generate_txt_for_course(selected_course_id, selected_title)
    if filename and os.path.exists(filename):
        with open(filename, "rb") as doc:
            bot.send_document(message.chat.id, doc, caption=f"✅ Extracted successfully!\nBatch: {selected_title}")
        os.remove(filename)
    else:
        bot.send_message(message.chat.id, "❌ Failed to fetch batch data. Invalid Course ID.")

if __name__ == "__main__":
    print("🤖 Telegram Bot is running with Bulk & Auto Features...")
    bot.infinity_polling()
