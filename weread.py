import json
import time
import re
import sys
import requests
from notion_client import Client

def get_weread_notes(cookie):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Cookie": cookie
    }
    # 获取书架
    url_bookshelf = "https://weread.qq.com/web/bookListInCategory/reading"
    resp = requests.get(url_bookshelf, headers=headers)
    books = resp.json().get("books", [])
    all_notes = []
    for b in books:
        book_id = b["bookId"]
        book_title = b["book"]["title"]
        book_author = b["book"]["author"]
        # 获取笔记
        url_note = f"https://weread.qq.com/web/book/note/list?bookId={book_id}"
        r_note = requests.get(url_note, headers=headers)
        note_data = r_note.json()
        marks = note_data.get("marks", [])
        for mark in marks:
            note_item = {
                "book_id": book_id,
                "book_title": book_title,
                "book_author": book_author,
                "mark_text": mark.get("markText", ""),
                "note_text": mark.get("noteText", ""),
                "chapter_title": mark.get("chapterTitle", ""),
                "range": mark.get("range", ""),
                "create_time": mark.get("createTime", int(time.time()*1000))
            }
            all_notes.append(note_item)
    return all_notes


def init_notion_client(notion_token):
    # ==========关键修改：指定旧API版本，兼容新版 notion‑client ==========
    client = Client(auth=notion_token, notion_version="2022-06-28")
    return client


def query_exist_book_map(client, database_id):
    """查询数据库已存在记录，book_id -> page_id"""
    book_map = {}
    response = client.databases.query(database_id=database_id)
    results = response["results"]
    for page in results:
        props = page["properties"]
        bid = props.get("book_id", {}).get("rich_text", [])
        if bid:
            bid_val = bid[0]["text"]["content"]
            book_map[bid_val] = page["id"]
    return book_map


def build_notion_page_properties(note_item):
    props = {
        "book_id": {"rich_text": [{"text": {"content": note_item["book_id"]}}]},
        "书名": {"title": [{"text": {"content": note_item["book_title"]}}]},
        "作者": {"rich_text": [{"text": {"content": note_item["book_author"]}}]},
        "章节": {"rich_text": [{"text": {"content": note_item["chapter_title"]}}]},
        "划线内容": {"rich_text": [{"text": {"content": note_item["mark_text"]}}]},
        "我的笔记": {"rich_text": [{"text": {"content": note_item["note_text"]}}]},
        "位置": {"rich_text": [{"text": {"content": note_item["range"]}}]}
    }
    return props


def main():
    if len(sys.argv) !=4:
        print("usage: python weread.py WEREAD_COOKIE NOTION_TOKEN NOTION_DATABASE_ID")
        return
    weread_cookie = sys.argv[1]
    notion_token = sys.argv[2]
    database_id = sys.argv[3]

    client = init_notion_client(notion_token)
    print("开始获取微信读书笔记...")
    note_list = get_weread_notes(weread_cookie)
    print(f"共获取 {len(note_list)} 条笔记")
    exist_map = query_exist_book_map(client, database_id)

    for note in note_list:
        bid = note["book_id"]
        props = build_notion_page_properties(note)
        if bid in exist_map:
            page_id = exist_map[bid]
            print(f"更新已有记录 book_id:{bid}")
            client.pages.update(page_id=page_id, properties=props)
        else:
            print(f"新建记录 book_id:{bid}")
            client.pages.create(parent={"database_id": database_id}, properties=props)
        time.sleep(0.3)
    print("同步完成")

if __name__ == "__main__":
    main()
