import vk_api
from vk_api.upload import VkUpload
import requests
from bs4 import BeautifulSoup
import os
import random
import sys
import time
from datetime import datetime, timedelta
import yt_dlp

# Настройки
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')  # Первая группа
GROUP_ID_2 = os.environ.get('GROUP_ID_2')  # Вторая группа
CLIP_TITLE = "#приколы #ржака #юмор"

# Донорские паблики, из которых берем контент
SOURCES = [
    "dobriememes",
    "porno_yumor",
    "club99177290",
]

def get_topmemas_memes(max_items=80):
    items = []
    try:
        resp = requests.get("https://topmemas.top/", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            alt = (img.get("alt") or "").strip()
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("/"):
                src = "https://topmemas.top" + src
            if not src.startswith("http"):
                continue
            if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                items.append((src, alt))
            if len(items) >= max_items:
                break
        # dedupe by url
        seen = set()
        uniq = []
        for url, alt in items:
            if url in seen:
                continue
            seen.add(url)
            uniq.append((url, alt))
        return uniq
    except Exception as e:
        print(f"Ошибка парсинга topmemas: {e}")
        return []

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

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

def get_top_posts_from_sources(vk_session):
    """Возвращает список топовых постов за последние сутки из SOURCES"""
    vk = vk_session.get_api()
    now_ts = int(time.time())
    day_ago = now_ts - 24 * 60 * 60
    candidates = []

    for source in SOURCES:
        try:
            posts = vk.wall.get(domain=source, count=100, filter='owner')
        except Exception as e:
            print(f"Ошибка получения постов из {source}: {e}")
            continue

        for post in posts.get('items', []):
            post_date = post.get('date', 0)
            if post_date < day_ago:
                continue

            likes = post.get('likes', {}).get('count', 0)
            reposts = post.get('reposts', {}).get('count', 0)
            comments = post.get('comments', {}).get('count', 0)
            views = post.get('views', {}).get('count', 0)

            score = likes * 3 + reposts * 5 + comments * 2 + views * 0.001
            candidates.append((score, source, post))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [p for _, _, p in candidates]


def clone_post_to_group(vk_session, group_id, post, used_ids):
    """Клонирует пост: видео как клип, мем как картинку"""
    post_key = f"{post.get('owner_id')}_{post.get('id')}"
    if post_key in used_ids:
        return None, None
    used_ids.add(post_key)

    text = post.get('text', '') or ''
    if len(text) > 300:
        text = text[:297] + "..."

    attachments = post.get('attachments', [])
    video_data = None
    photo_data = None

    for att in attachments:
        if att.get('type') == 'video' and video_data is None:
            video_data = att.get('video')
        if att.get('type') == 'photo' and photo_data is None:
            photo_data = att.get('photo')

    if video_data is not None:
        video_url = f"https://vk.com/video{video_data['owner_id']}_{video_data['id']}"
        print(f"  Клонируем видео: {video_url}")

        filepath, _ = download_video(video_url)
        if filepath and os.path.exists(filepath):
            final_title = CLIP_TITLE
            attachment = upload_video_to_vk(vk_session, group_id, filepath, final_title)
            os.remove(filepath)

            if attachment:
                message = text or final_title
                return message, attachment
            else:
                print("  Не удалось загрузить видео в группу")
        else:
            print("  Не удалось скачать видео")

    if photo_data is not None:
        sizes = photo_data.get('sizes', [])
        if sizes:
            best_size = sorted(sizes, key=lambda x: x.get('width', 0))[-1]
            img_url = best_size.get('url')
            if img_url:
                msg, attachment = upload_photo_to_vk(vk_session, group_id, img_url)
                message = text or msg
                return message, attachment

    return None, None


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

def get_last_post_type(vk_session, group_id):
    try:
        vk = vk_session.get_api()
        posts = vk.wall.get(owner_id=-int(group_id), count=1)
        if not posts['items']: return 'unknown'
        post = posts['items'][0]
        if 'attachments' in post:
            att_type = post['attachments'][0]['type']
            if att_type in ['photo', 'video']: return att_type
        return 'text'
    except:
        return 'unknown'

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

def get_next_type(current_type):
    if current_type == 'text': return 'photo'
    if current_type == 'photo': return 'video'
    if current_type == 'video': return 'text'
    return 'text'

def get_clip_for_group(vk_session, group_id, used_video_sources):
    vk = vk_session.get_api()
    queries = ["ржака", "приколы", "мемы", "смешное", "юмор", "угар", "funny"]
    for attempt in range(10):
        query = random.choice(queries)
        offset = random.randint(0, 100)
        try:
            res = vk.video.search(q=query, sort=2, filters='short', count=20, offset=offset, adult=0)
        except Exception as e:
            print(f"Ошибка поиска видео: {e}")
            continue
        items = res.get("items", [])
        random.shuffle(items)
        for v in items:
            source_id = f"{v.get('owner_id')}_{v.get('id')}"
            if source_id in used_video_sources:
                continue
            used_video_sources.add(source_id)
            video_url = f"https://vk.com/video{source_id}"
            filepath, _ = download_video(video_url)
            if filepath and os.path.exists(filepath):
                attachment = upload_video_to_vk(vk_session, group_id, filepath, CLIP_TITLE)
                os.remove(filepath)
                if attachment:
                    return CLIP_TITLE, attachment
    return None, None

def process_group(vk_session, group_id, memes, used_video_sources, used_meme_urls):
    print(f"\n--- Обработка группы {group_id} (Мемы topmemas) ---")
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
        msg, attachment = upload_photo_to_vk(vk_session, group_id, img_url)
        message = (alt or "").strip() or msg
        if message or attachment:
            publish_time = start_time + timedelta(hours=scheduled+1)
            post_to_vk(vk_session, group_id, message, attachment, int(publish_time.timestamp()))
            scheduled += 1
            time.sleep(2)
        else:
            print("  Не удалось загрузить мем из topmemas")

def main():
    print("Запуск бота...")
    vk_session = get_vk_session()
    memes = get_topmemas_memes(80)
    used_video_sources = set()
    used_meme_urls = set()
    
    if GROUP_ID:
        process_group(vk_session, GROUP_ID, memes, used_video_sources, used_meme_urls)
    else:
        print("GROUP_ID не задан")
        
    if GROUP_ID_2:
        process_group(vk_session, GROUP_ID_2, memes, used_video_sources, used_meme_urls)
    else:
        print("GROUP_ID_2 не задан (вторая группа пропущена)")

if __name__ == "__main__":
    main()
