import streamlit as st
import os
from dotenv import load_dotenv
import sqlite3
import pandas as pd
import requests
from PIL import Image
from io import BytesIO
import base64

DB_NAME = "data.db"

COVER_WIDTH = 96
COVER_HEIGHT = 144

load_dotenv()

# -----------------------------
# DB初期化
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS books(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        read_date TEXT,
        title TEXT,
        author TEXT,
        thumbnail TEXT,
        impression TEXT
    )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# 画像リサイズ
# -----------------------------
@st.cache_data(ttl=3600)
def get_cover_data_url(thumbnail_url):

    if not thumbnail_url:
        img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), color=(200,200,200))
    else:
        img=None

        try:
            resp=requests.get(thumbnail_url,timeout=5)

            if resp.status_code==200:
                img=Image.open(BytesIO(resp.content)).convert("RGB")
                img=img.resize((COVER_WIDTH,COVER_HEIGHT),Image.LANCZOS)

        except Exception:
            img=None

        if img is None:
            img=Image.new("RGB",(COVER_WIDTH,COVER_HEIGHT),color=(200,200,200))

    buf=BytesIO()
    img.save(buf,format="PNG")

    b64=base64.b64encode(buf.getvalue()).decode("ascii")

    return f"data:image/png;base64,{b64}"


# -----------------------------
# CRUD
# -----------------------------
def insert_book(read_date,title,author,thumbnail,impression):

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()

    c.execute("""
        INSERT INTO books
        (read_date,title,author,thumbnail,impression)
        VALUES (?,?,?,?,?)
    """,(read_date,title,author,thumbnail,impression))

    conn.commit()
    conn.close()


def get_books():

    conn=sqlite3.connect(DB_NAME)

    df=pd.read_sql(
        "SELECT * FROM books ORDER BY read_date DESC",
        conn
    )

    conn.close()

    return df


def get_book(book_id):

    conn=sqlite3.connect(DB_NAME)
    conn.row_factory=sqlite3.Row
    c=conn.cursor()

    c.execute("SELECT * FROM books WHERE id=?",(book_id,))
    row=c.fetchone()

    conn.close()

    return dict(row) if row else None


def delete_book(book_id):

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()

    c.execute("DELETE FROM books WHERE id=?",(book_id,))

    conn.commit()
    conn.close()


def update_book_impression(book_id,impression):

    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()

    c.execute(
        "UPDATE books SET impression=? WHERE id=?",
        (impression,book_id)
    )

    conn.commit()
    conn.close()


# -----------------------------
# Google Books API
# -----------------------------
def search_books(query):

    url="https://www.googleapis.com/books/v1/volumes"

    params={
        "q":query,
        "maxResults":10,
        "key":os.environ.get("GOOGLE_BOOKS_API_KEY","")
    }

    response=requests.get(url,params=params)

    if response.status_code!=200:
        return []

    data=response.json()

    results=[]

    for item in data.get("items",[]):

        info=item.get("volumeInfo",{})

        title=info.get("title","")
        author=", ".join(info.get("authors",[]))
        thumbnail=info.get("imageLinks",{}).get("thumbnail","")

        results.append({
            "title":title,
            "author":author,
            "thumbnail":thumbnail
        })

    return results


# -----------------------------
# 初期化
# -----------------------------
init_db()

st.set_page_config(
    page_title="読書記録アプリ",
    page_icon="📚",
    layout="wide"
)

st.title("📚 本棚")

if "operation_message" not in st.session_state:
    st.session_state.operation_message = ""

if st.session_state.operation_message:
    st.toast(st.session_state.operation_message)
    st.session_state.operation_message = ""


# -----------------------------
# session state
# -----------------------------
if "operation_message" not in st.session_state:
    st.session_state.operation_message=""

if "search_results" not in st.session_state:
    st.session_state.search_results=[]

if "selected_book" not in st.session_state:
    st.session_state.selected_book={}

if "add_book_dialog_open" not in st.session_state:
    st.session_state.add_book_dialog_open=False

if "selected_book_id" not in st.session_state:
    st.session_state.selected_book_id=None


# -----------------------------
# URLから選択
# -----------------------------
selected_book_id=st.query_params.get("book")

if isinstance(selected_book_id,list):
    selected_book_id=selected_book_id[0]

if selected_book_id:
    try:
        st.session_state.selected_book_id=int(selected_book_id)
    except:
        pass


# -----------------------------
# 登録dialog
# -----------------------------
@st.dialog("📖 読書記録を登録")
def add_book_dialog():

    st.subheader("本を検索")

    with st.form("search_form"):

        col1,col2=st.columns([4,1])

        with col1:
            query=st.text_input(
                "タイトル検索",
                key="book_search",
                label_visibility="collapsed",
                placeholder="タイトルを入力"
            )

        with col2:
            search_submitted=st.form_submit_button("検索")

    if search_submitted and query:

        st.session_state.search_results=search_books(query)
        st.rerun()
#テスト

    if st.session_state.search_results:

        st.write("検索結果")

        for i,book in enumerate(st.session_state.search_results):

            col1,col2=st.columns([1,4])

            with col1:
                if book["thumbnail"]:
                    st.image(book["thumbnail"],width=60)

            with col2:

                label=f"{book['title']} / {book['author']}"

                if st.button(label,key=f"result_{i}"):
                    st.session_state.selected_book=book
                    st.session_state.search_results=[]
                    st.rerun()

    selected=st.session_state.selected_book

    title=st.text_input("タイトル",value=selected.get("title",""))
    author=st.text_input("著者",value=selected.get("author",""))
    thumbnail=selected.get("thumbnail","")
    read_date=st.date_input("読んだ日")
    impression=st.text_area("感想")

    col1,col2=st.columns(2)

    with col1:

        if st.button("保存",use_container_width=True):

            insert_book(
                str(read_date),
                title,
                author,
                thumbnail,
                impression
            )

            st.session_state.search_results=[]
            st.session_state.selected_book={}
            st.session_state.add_book_dialog_open=False

            st.rerun()

    with col2:

        if st.button("キャンセル",use_container_width=True):

            st.session_state.search_results=[]
            st.session_state.selected_book={}
            st.session_state.add_book_dialog_open=False

            st.rerun()


# -----------------------------
# 詳細dialog
# -----------------------------
@st.dialog("詳細")
def book_detail_dialog(book_id):

    book=get_book(book_id)

    if not book:
        st.warning("本が見つかりませんでした")
        return

    st.header(book["title"])

    col1,col2=st.columns(2)

    with col1:

        st.write(book["author"])

        if book["thumbnail"]:
            cover=get_cover_data_url(book["thumbnail"])
            st.image(cover,width=200)

    with col2:

        st.write("📅 読了日:",book["read_date"])

        edited=st.text_area(
            "💬 感想",
            value=book["impression"],
            height=200
        )

    confirm_delete=st.checkbox("本当に削除しますか？")

    c1,c2=st.columns(2)

    with c1:

        if st.button("🗑 削除実行", use_container_width=True, disabled=not confirm_delete):

            delete_book(book_id)

            st.session_state.operation_message = "削除しました"
            st.session_state.selected_book_id=None
            st.query_params.clear()

            st.rerun()

    with c2:

        if st.button("💾 感想を保存", use_container_width=True):

            update_book_impression(book_id,edited)

            st.session_state.operation_message = "感想を保存しました"
            st.session_state.selected_book_id = book_id
            st.rerun()


# -----------------------------
# 追加ボタン
# -----------------------------
col1,col2=st.columns([10,1])

with col2:

    if st.button("➕",use_container_width=True):

        st.session_state.selected_book_id=None
        st.session_state.add_book_dialog_open=True


# -----------------------------
# 本棚
# -----------------------------
df=get_books()

if df.empty:

    st.info("まだ読書記録がありません")

else:

    cols_per_row=10
    books=list(df.iterrows())

    for i in range(0,len(books),cols_per_row):

        row_books=books[i:i+cols_per_row]

        cols=st.columns(cols_per_row)

        for col,(_,row) in zip(cols,row_books):

            with col:

                cover=get_cover_data_url(row["thumbnail"])

                st.markdown(
                    f"""
                    <a href="?book={row['id']}" target="_self">
                        <img src="{cover}" width="{COVER_WIDTH}" height="{COVER_HEIGHT}"
                        style="object-fit:cover;border-radius:4px;" />
                    </a>
                    """,
                    unsafe_allow_html=True
                )


# -----------------------------
# dialog制御
# -----------------------------
if st.session_state.add_book_dialog_open:

    add_book_dialog()

elif st.session_state.get("selected_book_id"):

    book_detail_dialog(st.session_state["selected_book_id"])