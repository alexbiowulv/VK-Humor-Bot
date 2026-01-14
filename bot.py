import vk_api
from vk_api.upload import VkUpload
import requests
from bs4 import BeautifulSoup
import os
import random
import sys
import time
from datetime import datetime, timedelta

# Настройки
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID') # Первая группа (Anekdot.ru)
GROUP_ID_2 = os.environ.get('GROUP_ID_2') # Вторая группа (Meme API)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_vk_session():
    if not VK_TOKEN:
        print("Ошибка: Не задан VK_TOKEN")
        sys.exit(1)
    return vk_api.VkApi(token=VK_TOKEN)

# --- Логика поиска ВКонтакте ---

def get_vk_search_content(vk_session, group_id, used_ids):
    """Ищет контент (мемы, видео) прямо ВКонтакте"""
    try:
        vk = vk_session.get_api()
        
        # Запросы для поиска
        queries = [
            "ржака", "приколы", "мемы", "смешное", "юмор", 
            "стендап", "fail compilation", "смешные животные",
            "угар", "лол", "memes", "funny"
        ]
        query = random.choice(queries)
        
        # 50% шанс на видео, 50% на картинку (пост)
        is_video = random.choice([True, False])
        
        if is_video:
            # Поиск видео
            # Используем offset для уникальности
            offset = random.randint(0, 50) 
            videos = vk.video.search(
                q=query, 
                sort=2, # по релевантности
                filters='short', # короткие
                count=10, 
                offset=offset,
                adult=0
            )
            
            if not videos['items']: return None, None
            
            # Выбираем видео, которого еще не было
            for _ in range(5):
                video = random.choice(videos['items'])
                video_id = f"video{video['owner_id']}_{video['id']}"
                if video_id not in used_ids:
                    used_ids.add(video_id)
                    title = video.get('title', 'Видео')
                    return title, video_id
                    
        else:
            # Поиск постов (картинки)
            # newsfeed.search ищет по всему ВК
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp())
            
            posts = vk.newsfeed.search(
                q=query,
                count=30,
                start_time=start_time, # Свежее за 24 часа
                extended=1
            )
            
            if not posts['items']: return None, None
            
            # Фильтруем посты с фото
            candidates = []
            for post in posts['items']:
                # Пропускаем репосты (нам нужен оригинал или контент)
                if 'copy_history' in post:
                     # Можно брать из copy_history, но проще искать оригиналы
                     continue
                     
                if 'attachments' in post:
                    for att in post['attachments']:
                        if att['type'] == 'photo':
                            candidates.append((post, att['photo']))
                            break
            
            if not candidates: return None, None
            
            # Выбираем случайный пост
            for _ in range(5):
                post, photo = random.choice(candidates)
                post_id = f"wall{post['owner_id']}_{post['id']}"
                
                if post_id not in used_ids:
                    used_ids.add(post_id)
                    
                    # Берем самую большую картинку
                    sizes = photo.get('sizes', [])
                    if not sizes: continue
                    # Сортируем по width
                    best_size = sorted(sizes, key=lambda x: x['width'])[-1]
                    img_url = best_size['url']
                    
                    # Текст поста (если не слишком длинный)
                    text = post.get('text', '')
                    if len(text) > 200: text = "" # Если слишком длинный, берем только картинку
                    
                    # Загружаем
                    msg, attachment = upload_photo_to_vk(vk_session, group_id, img_url)
                    
                    # Если есть текст, добавляем его
                    final_msg = text if text else msg
                    
                    return final_msg, attachment

        return None, None
        
    except Exception as e:
        print(f"Ошибка поиска VK: {e}")
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

def process_group(vk_session, group_id):
    print(f"\n--- Обработка группы {group_id} (Режим: VK Search) ---")
    
    start_time = datetime.now()
    posts_count = 10
    
    # Множество для отслеживания дубликатов в рамках одного запуска
    used_ids = set()
    
    for i in range(posts_count):
        message, attachment = get_vk_search_content(vk_session, group_id, used_ids)
        
        if message or attachment:
            publish_time = start_time + timedelta(hours=i+1)
            post_to_vk(vk_session, group_id, message, attachment, int(publish_time.timestamp()))
        else:
            print("  Не удалось найти контент")
            
        time.sleep(2)

def main():
    print("Запуск бота...")
    vk_session = get_vk_session()
    
    if GROUP_ID:
        process_group(vk_session, GROUP_ID)
    else:
        print("GROUP_ID не задан")
        
    if GROUP_ID_2:
        process_group(vk_session, GROUP_ID_2)
    else:
        print("GROUP_ID_2 не задан (вторая группа пропущена)")

if __name__ == "__main__":
    main()
