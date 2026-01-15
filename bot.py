import vk_api
from vk_api.upload import VkUpload
import requests
from bs4 import BeautifulSoup
import os
import random
import sys
import time
from datetime import datetime, timedelta
import re

# Настройки
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')  # Первая группа
GROUP_ID_2 = os.environ.get('GROUP_ID_2')  # Вторая группа
CLIP_TITLE = "#приколы #ржака #юмор"

# Донорские паблики, из которых берем контент


def get_reddit_memes(max_items=80):
    items = []
    subs = ["ruAsska", "TheRussianMemeSub", "KafkaFPS"]
    try:
        random.shuffle(subs)
        for sub in subs:
            count = min(50, max_items - len(items))
            if count <= 0:
                break
            url = f"https://meme-api.com/gimme/{sub}/{count}"
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "memes" in data:
                for m in data["memes"]:
                    img = m.get("url")
                    title = (m.get("title") or "").strip()
                    if not re.search(r"[А-Яа-яЁё]", title):
                        continue
                    if not img or not img.startswith("http"):
                        continue
                    if any(ext in img.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                        items.append((img, title))
            elif isinstance(data, dict) and "url" in data:
                img = data.get("url")
                title = (data.get("title") or "").strip()
                if not re.search(r"[А-Яа-яЁё]", title or ""):
                    continue
                if img and img.startswith("http"):
                    items.append((img, title))
    except Exception as e:
        print(f"Ошибка получения мемов Reddit: {e}")
    # dedupe
    seen = set()
    uniq = []
    for url, title in items:
        if url in seen:
            continue
        seen.add(url)
        uniq.append((url, title))
    return uniq[:max_items]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def download_binary(url, suffix):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        fname = f"temp_{random.randint(10000, 99999)}{suffix}"
        with open(fname, "wb") as f:
            f.write(r.content)
        return fname
    except Exception:
        return None
def get_vk_session():
    if not VK_TOKEN:
        print("Ошибка: Не задан VK_TOKEN")
        sys.exit(1)
    return vk_api.VkApi(token=VK_TOKEN)

def download_video(video_url):
    """Скачивает видео с ВК с помощью yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'temp_video_{random.randint(10000, 99999)}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'Video')
    except Exception as e:
        print(f"Ошибка скачивания видео ({video_url}): {e}")
        return None, None

def upload_video_to_vk(vk_session, group_id, filepath, title):
    """Загружает видео в группу ВК"""
    try:
        upload = VkUpload(vk_session)
        # Загружаем видео (оно не публикуется сразу, wallpost=0)
        video = upload.video(
            video_file=filepath,
            name=title,
            description="Uploaded via Bot",
            is_private=0,
            wallpost=0,
            group_id=int(group_id)
        )
        # Возвращает словарь, например {'owner_id': 123, 'video_id': 456}
        if 'video_id' in video:
             # video['owner_id'] может быть положительным (пользователь) или отрицательным (группа)
             # Нам нужен ID владельца видео для attachment
             owner_id = video.get('owner_id')
             video_id = video.get('video_id')
             return f"video{owner_id}_{video_id}"
        return None
    except Exception as e:
        print(f"Ошибка загрузки видео в ВК: {e}")
        return None

# --- Логика выбора топовых постов из донорских пабликов ---

 


 


# --- Общие функции ---

def upload_photo_to_vk(vk_session, group_id, img_url):
    """Скачивает и загружает фото в ВК"""
    try:
        img_data = requests.get(img_url, headers=HEADERS).content
        filename = f'temp_{random.randint(1, 10000)}.jpg'
        
        with open(filename, 'wb') as f:
            f.write(img_data)
            
        upload = VkUpload(vk_session)
        photo = upload.photo_wall(photos=filename, group_id=int(group_id))[0]
        
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        if os.path.exists(filename): os.remove(filename)
        
        return "", attachment
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        if os.path.exists(filename): os.remove(filename)
        return None, None

 

def post_to_vk(vk_session, group_id, message, attachment, publish_date):
    try:
        vk = vk_session.get_api()
        vk.wall.post(
            owner_id=-int(group_id),
            message=message,
            attachment=attachment,
            publish_date=publish_date,
            from_group=1
        )
        date_str = datetime.fromtimestamp(publish_date).strftime('%H:%M')
        print(f"  [Группа {group_id}] Пост запланирован на {date_str}")
    except Exception as e:
        print(f"  [Группа {group_id}] Ошибка публикации: {e}")

 

 

def process_group(vk_session, group_id, memes, used_meme_urls):
    print(f"\n--- Обработка группы {group_id} (Мемы Reddit) ---")
    start_time = datetime.now()
    posts_count = 10

    scheduled = 0
    meme_index = 0
    while scheduled < posts_count and meme_index < len(memes):
        img_url, alt = memes[meme_index]
        meme_index += 1
        if img_url in used_meme_urls:
            continue
        used_meme_urls.add(img_url)
        message = (alt or "").strip()
        attachment = None
        if img_url.lower().endswith(".mp4"):
            filepath = download_binary(img_url, ".mp4")
            if filepath and os.path.exists(filepath):
                attachment = upload_video_to_vk(vk_session, group_id, filepath, message or CLIP_TITLE)
                os.remove(filepath)
        else:
            msg, attachment = upload_photo_to_vk(vk_session, group_id, img_url)
            if not message:
                message = msg
        if message or attachment:
            publish_time = start_time + timedelta(hours=scheduled+1)
            post_to_vk(vk_session, group_id, message, attachment, int(publish_time.timestamp()))
            scheduled += 1
            time.sleep(2)
        else:
            print("  Не удалось загрузить мем")

def main():
    print("Запуск бота...")
    vk_session = get_vk_session()
    memes = get_reddit_memes(80)
    used_meme_urls = set()
    
    if GROUP_ID:
        process_group(vk_session, GROUP_ID, memes, used_meme_urls)
    else:
        print("GROUP_ID не задан")
        
    if GROUP_ID_2:
        process_group(vk_session, GROUP_ID_2, memes, used_meme_urls)
    else:
        print("GROUP_ID_2 не задан (вторая группа пропущена)")

if __name__ == "__main__":
    main()
