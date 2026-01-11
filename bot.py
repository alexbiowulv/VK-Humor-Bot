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

# --- Логика для Группы 1 (Anekdot.ru) ---

def get_random_joke():
    """Парсит случайный анекдот с anekdot.ru"""
    try:
        url = 'https://www.anekdot.ru/random/anekdot/'
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        jokes_list = soup.find_all('div', class_='text')
        
        if not jokes_list: return None, None
            
        joke_div = random.choice(jokes_list)
        for br in joke_div.find_all("br"): br.replace_with("\n")
        return joke_div.get_text().strip(), None
    except Exception as e:
        print(f"Ошибка (joke): {e}")
        return None, None

def get_anekdot_meme(vk_session, group_id):
    """Парсит случайный мем с anekdot.ru"""
    try:
        url = 'https://www.anekdot.ru/random/mem/'
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        images = soup.select('div.text img')
        if not images: return None, None
            
        img_url = random.choice(images).get('src')
        if not img_url.startswith('http'): img_url = 'https:' + img_url
            
        return upload_photo_to_vk(vk_session, group_id, img_url)
    except Exception as e:
        print(f"Ошибка (meme): {e}")
        return None, None

def get_vk_video(vk_session):
    """Ищет видео в ВК"""
    try:
        vk = vk_session.get_api()
        queries = ["смешное видео", "ржака", "прикол", "funny video", "мем видео"]
        videos = vk.video.search(q=random.choice(queries), sort=2, filters='short', count=20, adult=0)
        
        if not videos['items']: return None, None
        video = random.choice(videos['items'])
        return video.get('title', 'Видео'), f"video{video['owner_id']}_{video['id']}"
    except Exception as e:
        print(f"Ошибка (video): {e}")
        return None, None

# --- Логика для Группы 2 (Meme API) ---

def get_meme_from_api(vk_session, group_id):
    """Получает мем через Meme API (Reddit)"""
    try:
        # Ищем в русских сабреддитах
        subreddits = ['pikabu', 'ru_memes', 'PikabuPolitics', 'KafkaFPS']
        subreddit = random.choice(subreddits)
        url = f"https://meme-api.com/gimme/{subreddit}"
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if 'url' not in data: return None, None
        
        # Заголовок поста как текст
        title = data.get('title', '')
        image_url = data.get('url')
        
        # Загружаем картинку
        msg, attachment = upload_photo_to_vk(vk_session, group_id, image_url)
        return title, attachment
        
    except Exception as e:
        print(f"Ошибка (API meme): {e}")
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

def process_group(vk_session, group_id, mode='anekdot'):
    print(f"\n--- Обработка группы {group_id} (Режим: {mode}) ---")
    last_type = get_last_post_type(vk_session, group_id)
    current_type = last_type
    
    start_time = datetime.now()
    posts_count = 10
    
    for i in range(posts_count):
        current_type = get_next_type(current_type)
        message, attachment = None, None
        
        if mode == 'anekdot':
            # Логика первой группы
            if current_type == 'photo':
                message, attachment = get_anekdot_meme(vk_session, group_id)
                if not attachment: current_type = 'text'
            
            if current_type == 'video':
                message, attachment = get_vk_video(vk_session)
                if not attachment: current_type = 'text'
                
            if current_type == 'text':
                message, attachment = get_random_joke()
                
        elif mode == 'meme_api':
            # Логика второй группы (преимущественно мемы из API)
            # Иногда можно разбавлять видео
            if random.random() < 0.2: # 20% шанс на видео
                 message, attachment = get_vk_video(vk_session)
            else:
                 message, attachment = get_meme_from_api(vk_session, group_id)

        if message or attachment:
            publish_time = start_time + timedelta(hours=i+1)
            post_to_vk(vk_session, group_id, message, attachment, int(publish_time.timestamp()))
        else:
            print("  Не удалось получить контент")
            
        time.sleep(2)

def main():
    print("Запуск бота...")
    vk_session = get_vk_session()
    
    if GROUP_ID:
        process_group(vk_session, GROUP_ID, mode='anekdot')
    else:
        print("GROUP_ID не задан")
        
    if GROUP_ID_2:
        process_group(vk_session, GROUP_ID_2, mode='meme_api')
    else:
        print("GROUP_ID_2 не задан (вторая группа пропущена)")

if __name__ == "__main__":
    main()
