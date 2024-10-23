import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import json
from datetime import datetime
import base64
import json
from datetime import datetime
from pathlib import Path

class WordPressPublisher:
    def __init__(self, wp_url, username, application_password):
        self.wp_url = wp_url.rstrip('/')
        self.api_url = f"{self.wp_url}/wp-json/wp/v2"
        self.auth_header = self._get_auth_header(username, application_password)

    def _get_auth_header(self, username, application_password):
        credentials = f"{username}:{application_password}"
        encoded_credentials = base64.b64encode(credentials.encode('ascii')).decode('ascii')
        return {'Authorization': f'Basic {encoded_credentials}'}

    def create_post(self, title, content, status='draft'):
        endpoint = f"{self.api_url}/posts"
        
        # HTML 형식으로 콘텐츠 구성
        formatted_content = content
        if not content.startswith('<'):  # HTML 태그로 시작하지 않는 경우
            formatted_content = f"<div>{content.replace('\n', '<br>')}</div>"
        
        post_data = {
            'title': title,
            'content': formatted_content,
            'status': status
        }
        
        try:
            response = requests.post(
                endpoint,
                headers={
                    **self.auth_header,
                    'Content-Type': 'application/json'
                },
                json=post_data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Error creating WordPress post: {e}")
            return None

class CNNNewsCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_url = 'https://edition.cnn.com'

    def get_headlines(self, url='https://edition.cnn.com/world', num_headlines=5):
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            headlines = []
            possible_classes = [
                'container__headline',
                'container_lead-plus-headlines__headline',
                'card__headline',
                'headline'
            ]
            
            for class_name in possible_classes:
                headlines.extend(soup.find_all(['h3', 'h2', 'a'], class_=lambda x: x and class_name in x))
            
            news_items = []
            seen_titles = set()
            
            for headline in headlines:
                link_elem = headline.find('a') if headline.name != 'a' else headline
                if not link_elem:
                    continue
                    
                title = link_elem.get_text().strip()
                
                if not title or title in seen_titles:
                    continue
                    
                link = link_elem.get('href', '')
                if link:
                    full_link = urljoin(self.base_url, link)
                    news_items.append((title, full_link))
                    seen_titles.add(title)
                
                if len(news_items) >= num_headlines:
                    break
            
            return news_items[:num_headlines]
            
        except requests.RequestException as e:
            print(f"Error fetching CNN headlines: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []

    def get_article_content(self, url):
        """특정 기사의 상세 내용을 크롤링하는 메서드"""
        try:
            time.sleep(2)
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 제목 추출
            title = ""
            headline_tags = soup.find_all(['h1'], class_=lambda x: x and 'headline' in x.lower())
            if headline_tags:
                title = headline_tags[0].get_text().strip()
            
            # 본문 내용 추출
            content = self._extract_content(soup)
            
            # 내용이 없으면 None 반환
            if not content.strip():
                print(f"No content found for URL: {url}")
                return None
            
            return {
                'title': title,
                'url': url,
                'content': content
            }
            
        except requests.RequestException as e:
            print(f"Error fetching article content from {url}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error while processing {url}: {e}")
            return None

    def _extract_content(self, soup):
        """기사 본문 내용을 추출하는 보조 메서드"""
        content_html = []
        
        # 1. 본문 컨테이너 찾기
        content_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
            container in x.lower() for container in [
                'article__content',
                'article-body',
                'body-text',
                'article-body__content',
                'basic-article',
                'article-content'
            ]
        ))
        
        if not content_containers:
            return ""
        
        for container in content_containers:
            # 2. 단락 추출
            paragraphs = container.find_all(['p', 'h2', 'h3', 'ul', 'ol'])
            
            for element in paragraphs:
                # 불필요한 요소 제거
                [x.decompose() for x in element.find_all(class_='social-share')]
                [x.decompose() for x in element.find_all(class_='advertisement')]
                
                # 텍스트 정제
                text = element.get_text().strip()
                
                # 의미 있는 내용만 포함
                if text and len(text) > 20:
                    if element.name in ['h2', 'h3']:
                        content_html.append(f"<h3>{text}</h3>")
                    elif element.name in ['ul', 'ol']:
                        list_items = element.find_all('li')
                        list_html = "\n".join([f"<li>{item.get_text().strip()}</li>" for item in list_items])
                        content_html.append(f"<{element.name}>{list_html}</{element.name}>")
                    else:
                        content_html.append(f"<p>{text}</p>")
        
        return "\n".join(content_html)


class PublishLogger:
    def __init__(self, log_dir="logs"):
        """
        게시 로그를 관리하는 클래스
        
        Args:
            log_dir: 로그 파일을 저장할 디렉토리
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_date = datetime.now().strftime('%Y%m%d')
        self.published_data = []
        self.failed_data = []

    def add_success(self, article_data, wp_response):
        """성공적으로 게시된 기사 정보 추가"""
        self.published_data.append({
            'timestamp': datetime.now().isoformat(),
            'article': article_data,
            'wordpress_post_id': wp_response.get('id'),
            'wordpress_post_url': wp_response.get('link'),
            'status': 'success'
        })

    def add_failure(self, article_data, error_msg):
        """게시 실패한 기사 정보 추가"""
        self.failed_data.append({
            'timestamp': datetime.now().isoformat(),
            'article': article_data,
            'error': str(error_msg),
            'status': 'failed'
        })

    def save_logs(self):
        """로그를 JSON 파일로 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 성공한 게시물 저장
        if self.published_data:
            success_file = self.log_dir / f'published_articles_{timestamp}.json'
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_published': len(self.published_data),
                    'published_date': self.current_date,
                    'articles': self.published_data
                }, f, ensure_ascii=False, indent=2)
            print(f"\nSuccessfully published articles saved to: {success_file}")

        # 실패한 게시물 저장
        if self.failed_data:
            failed_file = self.log_dir / f'failed_articles_{timestamp}.json'
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_failed': len(self.failed_data),
                    'date': self.current_date,
                    'articles': self.failed_data
                }, f, ensure_ascii=False, indent=2)
            print(f"Failed articles saved to: {failed_file}")

def main():
    # WordPress 설정
    WP_URL = 'https://---'
    WP_USER = '---'
    WP_APP_PASSWORD = 'M9sD 0ywd TsGX zHr7 NJ0l azaN'
    
    # 크롤러, 퍼블리셔, 로거 초기화
    crawler = CNNNewsCrawler()
    publisher = WordPressPublisher(WP_URL, WP_USER, WP_APP_PASSWORD)
    logger = PublishLogger()
    
    # 헤드라인 수집
    print("Collecting headlines...")
    headlines = crawler.get_headlines(num_headlines=3)
    
    if not headlines:
        print("No headlines found.")
        return
    
    # 각 기사 처리 및 WordPress 게시
    print("\nProcessing articles and publishing to WordPress...")
    
    for idx, (title, url) in enumerate(headlines, 1):
        print(f"\nProcessing article {idx}/{len(headlines)}")
        print(f"URL: {url}")
        
        # 기사 내용 수집
        try:
            article_data = crawler.get_article_content(url)
            
            # 내용이 없으면 다음 기사로 진행
            if not article_data or not article_data['content'].strip():
                error_msg = "Empty or no content found"
                print(f"Skipping article: {error_msg}")
                logger.add_failure({'title': title, 'url': url}, error_msg)
                continue
                
            # WordPress 포스트 내용 구성
            post_content = f"""
{article_data['content']}

<hr>

<p>원문: <a href="{article_data['url']}" target="_blank">{article_data['url']}</a></p>
"""
            
            # WordPress에 포스트 생성
            result = publisher.create_post(
                title=article_data['title'],
                content=post_content,
                status='publish'  # 또는 'draft'
            )
            
            if result:
                print(f"Successfully published: {article_data['title']}")
                print(f"Post URL: {result.get('link', 'N/A')}")
                logger.add_success(article_data, result)
            else:
                error_msg = "Failed to create WordPress post"
                print(f"Failed to publish: {article_data['title']}")
                logger.add_failure(article_data, error_msg)
            
        except Exception as e:
            error_msg = f"Error processing article: {str(e)}"
            print(error_msg)
            logger.add_failure({'title': title, 'url': url}, error_msg)
        
        # 과도한 요청 방지를 위한 딜레이
        time.sleep(3)
    
    # 로그 파일 저장
    logger.save_logs()
    
    # 실행 결과 요약 출력
    print("\nExecution Summary:")
    print(f"Total articles processed: {len(headlines)}")
    print(f"Successfully published: {len(logger.published_data)}")
    print(f"Failed to publish: {len(logger.failed_data)}")

if __name__ == "__main__":
    main()
