# 북클라이밍 - 독서의 정상에 도전하라  – 2025-05-08 (rev.AUG-28-G)
import streamlit as st, requests, re, json, base64, time, mimetypes, uuid, datetime, random, os
from bs4 import BeautifulSoup
from openai import OpenAI

# ───── API 키 ─────
OPENAI_API_KEY      = st.secrets["OPENAI_API_KEY"]
NAVER_CLIENT_ID     = st.secrets["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
NAVER_OCR_SECRET    = st.secrets.get("NAVER_OCR_SECRET","")
client = OpenAI(api_key=OPENAI_API_KEY)

# ───── 공통 테마 & 유틸 ─────
THEME_CSS = """
<style>
:root{
  --bg:#f7f8fb; --card:#ffffff; --text:#0b1220; --muted:#4b5563; --ring:#e5e7eb;
  --btn-bg:#fef08a; --btn-text:#0b1220; --btn-bg-hover:#fde047; --chip:#eef2ff; --chip-text:#1f2937;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0b1020; --card:#111827; --text:#f3f4f6; --muted:#cbd5e1; --ring:#334155;
    --btn-bg:#a7f3d0; --btn-text:#0b1220; --btn-bg-hover:#86efac; --chip:#1f2937; --chip-text:#e5e7eb;
  }
}
html, body { background: var(--bg) !important; }
section.main > div.block-container{ background: var(--card); border-radius: 14px; padding: 18px 22px; }
h1,h2,h3,h4,h5{ color:var(--text) !important; font-weight:800 }
p, label, span, div{ color:var(--text) }
.stMarkdown small, .badge{ color:var(--muted) }

/* 입력창 대비 */
input, textarea, .stTextInput input, .stTextArea textarea{
  color:var(--text) !important; background: rgba(127,127,127,.08) !important; 
  border:1px solid var(--ring) !important; border-radius:10px !important;
}

/* 사이드바 카드 라디오 */
.stSidebar{ background: var(--bg) !important; }
.sidebar-radio [data-baseweb="radio"] > div{
  border:1px solid var(--ring); border-radius:12px; padding:8px 12px; margin:6px 0;
  background:var(--chip); color:var(--chip-text);
}

/* 버튼 */
.stButton>button, .stDownloadButton>button{
  background: var(--btn-bg) !important; color: var(--btn-text) !important; 
  border:1px solid rgba(0,0,0,.08) !important; border-radius:12px !important;
  padding:10px 16px !important; font-weight:800 !important;
  box-shadow: 0 6px 16px rgba(0,0,0,.12) !important; transition: all .15s ease;
}
.stButton>button:hover{ background: var(--btn-bg-hover) !important; transform: translateY(-1px) }

a.linklike-btn{
  display:inline-block; text-decoration:none; background:var(--btn-bg); color:var(--btn-text) !important;
  padding:10px 16px; border-radius:12px; font-weight:800; border:1px solid rgba(0,0,0,.08);
}
.badge{display:inline-block; padding:4px 10px; border-radius:999px; background:var(--chip); color:var(--chip-text); font-size:0.85rem;}
</style>
"""

def clean_html(t): return re.sub(r"<.*?>","",t or "")
def strip_fence(t): return re.sub(r"^```(json)?|```$", "", t.strip(), flags=re.M)
def gpt(msg,t=0.5,mx=800):
    return client.chat.completions.create(
        model="gpt-4.1",messages=msg,temperature=t,max_tokens=mx
    ).choices[0].message.content.strip()

def to_data_url(url):
    while True:
        try:
            r=requests.get(url,timeout=5); r.raise_for_status()
            mime=r.headers.get("Content-Type") or mimetypes.guess_type(url)[0] or "image/jpeg"
            return f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
        except Exception as e:
            st.warning(f"표지 다운로드 재시도… ({e})"); time.sleep(2)

# ───── 안전(19금 차단 + 비속어 필터) ─────
ADULT_PATTERNS = [
    r"\b19\s*금\b", r"청소년\s*이용\s*불가", r"성인", r"야설", r"에로", r"포르노", r"노출",
    r"선정적", r"음란", r"야한", r"Adult", r"Erotic", r"Porn", r"R-?rated", r"BL\s*성인",
    r"성(관계|행위|묘사)", r"무삭제\s*판", r"금서\s*해제"
]
BAD_WORDS = [
    "씨발","시발","병신","ㅄ","ㅂㅅ","좆","개새끼","새끼","좆같","ㅈ같","니애미","느금","개같",
    "꺼져","죽어","염병","씹","sex","porn"
]
ADULT_RE = re.compile("|".join(ADULT_PATTERNS), re.I)
BAD_RE   = re.compile("|".join(map(re.escape, BAD_WORDS)), re.I)
def is_adult_book(item:dict)->bool:
    if "adult" in item:
        try:
            if bool(item["adult"]): return True
        except: pass
    text = " ".join([
        clean_html(item.get("title","")),
        clean_html(item.get("author","")),
        clean_html(item.get("description","")),
        clean_html(item.get("publisher",""))
    ])
    return bool(ADULT_RE.search(text))
def contains_bad_language(text:str)->bool: return bool(BAD_RE.search(text or ""))
def rewrite_polite(text:str)->str:
    try:
        return gpt([{"role":"user","content":f"다음 문장을 초등학생에게 어울리는 바르고 고운말로 바꿔줘. 의미는 유지하고 공격적 표현은 모두 제거:\n{text}"}],0.2,120)
    except: return "바르고 고운말을 사용해 다시 표현해 보세요."

# ───── NAVER Books & OCR ─────
def nv_search(q):
    hdr={"X-Naver-Client-Id":NAVER_CLIENT_ID,"X-Naver-Client-Secret":NAVER_CLIENT_SECRET}
    res = requests.get("https://openapi.naver.com/v1/search/book.json",
                        headers=hdr,params={"query":q,"display":10}).json().get("items",[])
    return [b for b in res if not is_adult_book(b)]
def crawl_syn(title):
    try:
        hdr={"User-Agent":"Mozilla/5.0"}
        soup=BeautifulSoup(requests.get(f"https://book.naver.com/search/search.nhn?query={title}",headers=hdr,timeout=8).text,"html.parser")
        f=soup.select_one("ul.list_type1 li a")
        if not f: return ""
        intro=BeautifulSoup(requests.get("https://book.naver.com"+f["href"],headers=hdr,timeout=8).text,"html.parser").find("div","book_intro")
        return intro.get_text("\n").strip() if intro else ""
    except: 
        return ""
def synopsis(title,b): 
    d=clean_html(b.get("description","")); c=crawl_syn(title); 
    return (d+"\n\n"+c).strip() if (d or c) else ""
def elem_syn(title,s,level):
    detail = {"쉬움":"초등 저학년, 12~16문장","기본":"초등 중학년, 16~20문장","심화":"초등 고학년, 18~22문장(배경·인물 감정·주제 의식 포함)"}[level]
    return gpt([{"role":"user","content":
        f"아래 원문만 근거로 책 '{title}'의 줄거리를 {detail}로 **3단락** 자세히 써줘. "
        "반드시 (1)배경 (2)주요 인물 (3)갈등/전환점 (4)결말/주제 를 포함하고, "
        "할루시네이션 없이 마무리하세요.\n\n원문:\n"+s}],0.32,3200)
def nv_ocr(img):
    url=st.secrets.get("NAVER_CLOVA_OCR_URL")
    if not url or not NAVER_OCR_SECRET: return "(OCR 설정 필요)"
    payload={"version":"V2","requestId":str(uuid.uuid4()),
             "timestamp":int(datetime.datetime.utcnow().timestamp()*1000),
             "images":[{"name":"img","format":"jpg","data":base64.b64encode(img).decode()}]}
    res=requests.post(url,headers={"X-OCR-SECRET":NAVER_OCR_SECRET,"Content-Type":"application/json"},
                      json=payload,timeout=30).json()
    try: return " ".join(f["inferText"] for f in res["images"][0]["fields"])
    except: return "(OCR 파싱 오류)"

# ───── 퀴즈 ─────
def make_quiz(raw:str)->list:
    m=re.search(r"\[.*]", strip_fence(raw), re.S)
    if not m: return []
    try: arr=json.loads(m.group())
    except json.JSONDecodeError: return []
    quiz=[]
    for it in arr:
        if isinstance(it,str):
            try: it=json.loads(it)
            except: continue
        if "answer" in it and "correct_answer" not in it:
            it["correct_answer"]=it.pop("answer")
        if not {"question","options","correct_answer"}.issubset(it.keys()): continue
        opts=it["options"][:]
        if len(opts)!=4: continue
        if isinstance(it["correct_answer"],int):
            try: correct_txt=opts[it["correct_answer"]-1]
            except: continue
        else:
            correct_txt=str(it["correct_answer"]).strip()
        random.shuffle(opts)
        if correct_txt not in opts: opts[0]=correct_txt
        quiz.append({"question":it["question"],"options":opts,"correct_answer":opts.index(correct_txt)+1})
    return quiz if len(quiz)==5 else []

# ───── 난이도 파라미터 ─────
def level_params(level:str):
    if level=="쉬움": return dict(temp=0.25, explain_len=900, debate_rounds=4, language="아주 쉬운 말", penalties=False)
    if level=="심화": return dict(temp=0.5, explain_len=1700, debate_rounds=6, language="정확하고 논리적인 말", penalties=True)
    return dict(temp=0.35, explain_len=1300, debate_rounds=6, language="친절한 말", penalties=False)

# ───── Intro 이미지 도우미(현재보다 70%로 축소 표시) ─────
def load_intro_path():
    for name in ["asset/intro.png","asset/intro.jpg","asset/intro.jpeg","asset/intro.webp"]:
        if os.path.exists(name): return name
    return None
def render_img_percent(path:str, percent:float=0.7):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    st.markdown(
        f'<p style="text-align:center;"><img src="data:{mime};base64,{b64}" style="width:{int(percent*100)}%; border-radius:12px;"/></p>',
        unsafe_allow_html=True
    )

# ───── 토론 주제 추천(검증) ─────
BANNED_TOPIC_WORDS = ["정치","경제","정책","규제","외교","국제","윤리","윤리적","형이상학","자본","노동시장","범죄율","통계","세금","제도"]
def valid_topic(s:str)->bool:
    s=s.strip()
    if any(w in s for w in BANNED_TOPIC_WORDS): return False
    return s.endswith("해야 한다.") and 8 <= len(s) <= 28 and not contains_bad_language(s) and re.fullmatch(r"[가-힣0-9\s\.\,\(\)]+", s) is not None
def recommend_topics(title, syn, level, tries=2):
    prompt = (
        f"아래 줄거리만 근거로 **초등학생 {level} 수준**의 찬반 토론 주제 3개를 **JSON 배열**로만 출력하세요.\n"
        "모든 항목은 '…해야 한다.'로 끝나는 간단한 평서문이어야 합니다.\n"
        "주제는 주인공의 선택/친구/도움/약속/규칙/정직/용기/노력과 휴식/자연 보호 등 책의 **주제에서 파생**되어야 합니다.\n"
        "어려운 사회·정치·경제 용어 금지. 각 항목 8~28자.\n\n"
        f"책 제목: {title}\n줄거리:\n{syn}"
    )
    for _ in range(tries):
        raw = gpt([{"role":"user","content":prompt}],0.25,360)
        try: arr=json.loads(strip_fence(raw)); cand=[clean_html(x) for x in arr if isinstance(x,str)]
        except: cand=[]
        cand=[t.strip() for t in cand if valid_topic(t)]
        cand=list(dict.fromkeys(cand))[:3]
        if len(cand)==3: return cand
    return ["미래를 위해 미리 준비해야 한다.","힘든 친구를 도와줘야 한다.","자연을 아껴야 한다."]

# ───── PAGE 1 : 책검색 & 표지대화 ─────
def page_book():
    st.markdown('<span class="badge">난이도를 선택하세요 (모든 활동에 적용)</span>', unsafe_allow_html=True)
    level = st.selectbox("난이도", ["쉬움","기본","심화"], index=["쉬움","기본","심화"].index(st.session_state.get("level","기본")))
    st.session_state.level = level

    intro_path = load_intro_path()
    if intro_path:
        l, c, r = st.columns([0.15,0.70,0.15])  # 중앙 70% 컬럼
        with c: render_img_percent(intro_path, 0.70)  # 그 안에서 다시 70%

    st.header("📘 1) 책검색 및 표지대화")

    if st.sidebar.button("페이지 초기화"): st.session_state.clear(); st.rerun()

    q=st.text_input("책 제목·키워드")
    if st.button("🔍 검색") and q.strip():
        result = nv_search(q.strip())
        if not result: st.warning("검색 결과가 없거나(또는 안전 필터에 의해) 숨김 처리되었습니다.")
        st.session_state.search=result

    if bs:=st.session_state.get("search"):
        _, sel=st.selectbox("책 선택",
                            [(f"{clean_html(b['title'])} | {clean_html(b['author'])}",b) for b in bs],
                            format_func=lambda x:x[0])
        if st.button("✅ 선택"):
            st.session_state.selected_book=sel
            title=clean_html(sel["title"])
            base_syn = synopsis(title,sel)
            st.session_state.synopsis=elem_syn(title, base_syn, st.session_state.level)
            st.success("책 선택 완료!")

    if bk:=st.session_state.get("selected_book"):
        title=clean_html(bk["title"]); cover=bk["image"]; syn=st.session_state.synopsis
        st.subheader("📖 줄거리"); st.write(syn or "(줄거리 없음)")
        lc,rc=st.columns([1,1])
        with lc: st.image(cover,caption=title,use_container_width=True)
        with rc:
            st.markdown("### 🖼️ 표지 챗봇 (독서 전 활동)")
            if "chat" not in st.session_state:
                st.session_state.chat=[
                    {"role":"system","content":
                        f"너는 초등 대상 책 표지에 대해 대화하는 챗봇입니다. 난이도:{st.session_state.level}. "
                        f"{level_params(st.session_state.level)['language']}로, 학생이 표지를 보고 내용과 인물, 사건을 예측하도록 1번에 한 질문씩 던져요."},
                    {"role":"user","content":[{"type":"text","text":"표지입니다."},
                                              {"type":"image_url","image_url":{"url":to_data_url(cover)}}]},
                    {"role":"assistant","content":"책 표지에서 가장 먼저 보이는 것은 무엇인가요?"}]
            for m in st.session_state.chat:
                if m["role"]=="assistant": st.chat_message("assistant").write(m["content"])
                elif m["role"]=="user" and isinstance(m["content"],str):
                    st.chat_message("user").write(m["content"])
            if u:=st.chat_input("답/질문 입력…"):
                if contains_bad_language(u):
                    st.warning("바르고 고운말을 사용해 주세요. 아래처럼 바꿔 볼까요?")
                    st.info(rewrite_polite(u))
                else:
                    st.session_state.chat.append({"role":"user","content":u})
                    rsp=gpt(st.session_state.chat,level_params(st.session_state.level)['temp'],400)
                    st.session_state.chat.append({"role":"assistant","content":rsp}); st.rerun()

        if st.button("다음 단계 ▶ 2) 단어 알아보기"):
            st.session_state.current_page="단어 알아보기"; st.rerun()

# ───── PAGE 2 : 단어 알아보기 ─────
def page_vocab():
    st.header("🧩 2) 단어 알아보기")
    if "selected_book" not in st.session_state:
        st.info("책을 먼저 선택해주세요."); 
        if st.button("◀ 이전 (1)"): st.session_state.current_page="책 검색"; st.rerun()
        return

    title=clean_html(st.session_state.selected_book["title"])
    st.markdown(f"**책 제목:** {title}  &nbsp;&nbsp; <span class='badge'>난이도: {st.session_state.level}</span>", unsafe_allow_html=True)

    word = st.text_input("궁금한 단어를 입력하세요")
    if st.button("🔎 단어 설명 보기"):
        if not word.strip(): st.warning("단어를 입력해주세요.")
        elif contains_bad_language(word):
            st.warning("이 프로그램은 초등학생을 위한 공간이에요. 바르고 고운말을 사용해 주세요 😊")
            st.info(f"예시 표현: {rewrite_polite(word)}")
        else:
            req = (f"초등학생 {st.session_state.level} 수준으로 '{word}'를 설명해줘. "
                   f"1) 쉬운 뜻 1줄  2) 사용 예시 2가지(각 1문장). 어려운 한자어는 쉬운 말로.")
            st.session_state.vocab_manual = gpt([{"role":"user","content":req}],0.3,380)

    if vm:=st.session_state.get("vocab_manual"):
        st.markdown("#### 뜻과 예시"); st.write(vm)

    if st.button("다음 단계 ▶ 3) 독서 퀴즈"):
        st.session_state.current_page="독서 퀴즈"; st.rerun()

# ───── PAGE 3 : 퀴즈 ─────
def page_quiz():
    st.header("📝 3) 독서 퀴즈")
    if "selected_book" not in st.session_state: 
        st.info("책을 먼저 선택해주세요."); 
        if st.button("◀ 이전 (1)"): st.session_state.current_page="책 검색"; st.rerun()
        return
    if st.sidebar.button("퀴즈 초기화"): st.session_state.pop("quiz",None); st.session_state.pop("answers",None); st.rerun()

    title=clean_html(st.session_state.selected_book["title"])
    syn=st.session_state.synopsis
    st.markdown(f"**책 제목:** {title}  &nbsp;&nbsp; <span class='badge'>난이도: {st.session_state.level}</span>", unsafe_allow_html=True)

    lv = st.session_state.level; lvp = level_params(lv)

    if "quiz" not in st.session_state and st.button("🧠 퀴즈 생성"):
        style = {"쉬움":"아주 쉬운 어휘, 보기 중 1개는 명확한 오답, 지문 그대로 묻기",
                 "기본":"핵심 사건 이해 중심, 보기 난이도 균형",
                 "심화":"추론/관계 파악, 함정 보기 1개 포함"}[lv]
        raw = gpt([{"role":"user","content":
            f"책 '{title}'의 줄거리를 바탕으로 5개 4지선다 퀴즈를 JSON 배열로만 출력. "
            f"'question','options'(4개),'correct_answer'(1~4) 키 사용. "
            f"난이도:{lv}, 스타일:{style}. 정답 번호 분포는 고르게.\n\n줄거리:\n{syn}"}],
            lvp['temp'], 900)
        q=make_quiz(raw)
        if q: st.session_state.quiz=q
        else: st.error("형식 오류, 다시 생성"); st.code(raw)

    if q:=st.session_state.get("quiz"):
        if "answers" not in st.session_state: st.session_state.answers={}
        for i,qa in enumerate(q):
            st.markdown(f"**문제 {i+1}.** {qa['question']}")
            pick=st.radio("",qa["options"],index=None,key=f"ans{i}")
            if pick is not None: st.session_state.answers[i]=qa["options"].index(pick)+1
            elif i in st.session_state.answers: del st.session_state.answers[i]

        if st.button("📊 채점"):
            miss=[i+1 for i in range(5) if i not in st.session_state.answers]
            if miss: st.error(f"{miss}번 문제 선택 안함"); return
            correct=[st.session_state.answers[i]==q[i]["correct_answer"] for i in range(5)]
            score=sum(correct)*20
            st.subheader("결과")
            for i,ok in enumerate(correct,1):
                st.write(f"문제 {i}: {'⭕' if ok else '❌'} (정답: {q[i-1]['options'][q[i-1]['correct_answer']-1]})")
            st.write(f"**총점: {score} / 100**")

            guide = "틀린 문항은 왜 틀렸는지 아주 쉽게" if lv=="쉬움" else ("근거 문장과 함께" if lv=="심화" else "핵심 이유 중심으로")
            explain=gpt([{"role":"user","content":
                f"다음 JSON으로 각 문항 해설과 총평을 한국어로 작성. 학생 난이도:{lv}. "
                f"{guide} 설명.\n"+json.dumps({"quiz":q,"student_answers":st.session_state.answers},ensure_ascii=False)}],
                lvp['temp'], lvp['explain_len'])
            st.write(explain)

    if st.button("다음 단계 ▶ 4) 독서 토론"):
        st.session_state.current_page="독서 토론"; st.rerun()

# ───── PAGE 4 : 토론 ─────
def page_discussion():
    st.header("⚖️ 4) 독서 토론")
    if "selected_book" not in st.session_state:
        st.info("책을 먼저 선택해주세요."); 
        if st.button("◀ 이전 (1)"): st.session_state.current_page="책 검색"; st.rerun()
        return
    if st.sidebar.button("토론 초기화"):
        for k in ("debate_started","debate_round","debate_chat","debate_topic",
                  "debate_eval","user_side","bot_side","topics","topic_choice",
                  "score_json","user_feedback_text"): st.session_state.pop(k,None); st.rerun()

    title=clean_html(st.session_state.selected_book["title"])
    syn=st.session_state.synopsis
    st.markdown(f"**책 제목:** {title}  &nbsp;&nbsp; <span class='badge'>난이도: {st.session_state.level}</span>", unsafe_allow_html=True)

    lv = st.session_state.level; lvp = level_params(lv)

    # 추천 주제
    if st.button("🎯 토론 주제 추천 3가지"):
        st.session_state.topics = recommend_topics(title, syn, lv)

    if tp:=st.session_state.get("topics"):
        st.subheader("추천 주제 선택")
        choice = st.radio("토론 주제", tp+["(직접 입력)"], index=0, key="topic_choice")
    else:
        choice = st.radio("토론 주제", ["(직접 입력)"], index=0, key="topic_choice")

    topic = st.text_input("직접 입력", value=st.session_state.get("debate_topic","")) if choice=="(직접 입력)" else choice
    side=st.radio("당신은?",("찬성","반대"))
    btn1, btn2 = st.columns([1,1])
    with btn1:
        start_clicked = st.button("🚀 토론 시작")
    with btn2:
        if st.button("다음 단계 ▶ 5) 독서감상문 피드백"):
            st.session_state.current_page="독서 감상문 피드백"; st.rerun()

    if start_clicked:
        if not topic or not topic.strip(): st.warning("토론 주제를 입력하거나 선택해주세요.")
        else:
            rounds = lvp['debate_rounds']; order = {4:[1,2,3,4], 6:[1,2,3,4,5,6]}[rounds]
            st.session_state.update({
                "debate_started":True,"debate_round":1,"debate_topic":topic,
                "user_side":side,"bot_side":"반대" if side=="찬성" else "찬성",
                "debate_order":order,
                "debate_chat":[{"role":"system","content":
                    f"너는 초등 독서토론 진행자. 모든 발언은 반드시 책의 줄거리 내용을 근거로 해야 한다. "
                    f"난이도:{lv}, 어조:{lvp['language']}. "
                    f"주제 '{topic}'. 1찬성입론 2반대입론 3찬성반론 4반대반론"
                    + ("" if len(order)==4 else " 5찬성최후 6반대최후")
                    + f". 토론 근거는 반드시 다음 줄거리에서만 가져온다:\n{syn[:1200]}"}]
            }); st.rerun()

    if st.session_state.get("debate_started"):
        lbl_map={1:"찬성측 입론",2:"반대측 입론",3:"찬성측 반론",4:"반대측 반론",5:"찬성측 최후 변론",6:"반대측 최후 변론"}
        for m in st.session_state.debate_chat:
            if m["role"]=="assistant": st.chat_message("assistant").write(str(m["content"]))
            elif m["role"]=="user":   st.chat_message("user").write(str(m["content"]))

        rd=st.session_state.debate_round; order = st.session_state.debate_order
        if rd<=len(order):
            step = order[rd-1]
            st.markdown(f"### 현재: {lbl_map[step]}")
            user_turn=((step%2==1 and st.session_state.user_side=="찬성") or (step%2==0 and st.session_state.user_side=="반대"))
            if user_turn:
                txt=st.chat_input("내 발언")
                if txt:
                    if contains_bad_language(txt):
                        st.warning("바르고 고운말을 사용해 주세요. 아래처럼 바꿔 볼까요?")
                        st.info(rewrite_polite(txt))
                    else:
                        st.session_state.debate_chat.append({"role":"user","content":f"[{lbl_map[step]}] {txt}"})
                        st.session_state.debate_round+=1; st.rerun()
            else:
                convo=st.session_state.debate_chat+[{"role":"user","content":f"[{lbl_map[step]}]"}]
                bot=gpt(convo,level_params(st.session_state.level)['temp'],420)
                st.session_state.debate_chat.append({"role":"assistant","content":bot})
                st.session_state.debate_round+=1; st.rerun()
        else:
            # ── 토론 종료: (A) 점수 산정(100점), (B) '내 발언' 기준 서술형 피드백
            if "debate_eval" not in st.session_state:
                # A) 점수 JSON
                transcript = []
                for m in st.session_state.debate_chat:
                    if m["role"]=="user": transcript.append(f"STUDENT({st.session_state.user_side}): {m['content']}")
                    elif m["role"]=="assistant": transcript.append(f"BOT({st.session_state.bot_side}): {m['content']}")
                score_prompt = (
                    "아래는 초등학생과 챗봇의 찬반 토론 대화입니다.\n"
                    "각 측(찬성/반대)에 대해 다음 5가지 기준을 0~20점으로 채점하고, 합계 100점 만점으로 총점을 계산하세요.\n"
                    "기준: 1) 줄거리·주요 내용 이해  2) 생각을 분명히 말함(책과 연결)  3) 근거 제시(내용/경험)  4) 질문에 답하고 생각 잇기  5) 새로운 질문/깊이 있는 사고\n"
                    "반드시 실제로 **그 측이 말한 내용만** 반영합니다. 학생(STUDENT)은 "
                    f"'{st.session_state.user_side}' 측이고, BOT은 '{st.session_state.bot_side}' 측입니다.\n"
                    "JSON만 출력:\n"
                    "{\"pro\":{\"criteria_scores\":[..5개..],\"total\":정수,\"summary\":\"한줄\"},"
                    "\"con\":{\"criteria_scores\":[..5개..],\"total\":정수,\"summary\":\"한줄\"},"
                    "\"winner\":\"찬성|반대\"}"
                )
                res_score = gpt([{"role":"user","content":"\n".join(transcript)+"\n\n"+score_prompt}],0.2,800)
                try: st.session_state.score_json = json.loads(strip_fence(res_score))
                except: st.session_state.score_json = {"pro":{"total":0},"con":{"total":0},"winner":"-"}

                # B) '내 발언' 기준 서술형 피드백
                my_lines = [m["content"] for m in st.session_state.debate_chat if m["role"]=="user" and "[" in m["content"]]
                other_lines = [m["content"] for m in st.session_state.debate_chat if m["role"]=="assistant"]
                fb_prompt = (
                    f"너는 초등학생을 돕는 토론 코치야. 아래 '학생 발언'만 근거로 학생에게 서술형 피드백을 써줘."
                    "챗봇 발언(상대 측)은 참고만 하고, 학생이 말하지 않은 내용은 절대 학생에게 돌리지 마.\n"
                    "구성: ① 전체 총평(3~5문장) ② 잘한 점(3가지, 이유 포함) ③ 더 나아질 점(2~3가지, 구체적 방법) ④ 다음 토론 팁 2~3가지(행동 문장). "
                    "어려운 말은 쉬운 말로.\n\n"
                    f"[학생 측: {st.session_state.user_side}] 학생 발언:\n" + "\n".join(my_lines[:50]) +
                    "\n\n(참고) 상대 발언:\n" + "\n".join(other_lines[:50]) +
                    "\n\n토론은 반드시 이 줄거리를 바탕으로 진행된 것으로 피드백을 연결해 줘:\n" + st.session_state.synopsis[:1200]
                )
                st.session_state.user_feedback_text = gpt([{"role":"user","content":fb_prompt}],0.3,1200)

                st.session_state.debate_eval=True; st.rerun()
            else:
                st.subheader("토론 평가")
                score = st.session_state.get("score_json",{})
                if score:
                    st.write(f"**점수 요약** · 찬성: **{score.get('pro',{}).get('total','-')}점**, "
                             f"반대: **{score.get('con',{}).get('total','-')}점**  → **승리: {score.get('winner','-')}**")
                st.markdown("**내 발언 기준 피드백**")
                st.write(st.session_state.get("user_feedback_text",""))

# ───── PAGE 5 : 감상문 피드백 ─────
def page_feedback():
    st.header("🎤 5) 독서감상문 피드백")
    if st.sidebar.button("피드백 초기화"): st.session_state.pop("essay",""); st.session_state.pop("ocr_file",""); st.rerun()

    if st.session_state.get("selected_book"):
        title=clean_html(st.session_state.selected_book["title"]); syn=st.session_state.synopsis
        st.markdown(f"**책:** {title}  &nbsp;&nbsp; <span class='badge'>난이도: {st.session_state.level}</span>", unsafe_allow_html=True)
    else: title="제목 없음"; syn=""

    up=st.file_uploader("손글씨 사진 업로드",type=["png","jpg","jpeg"])
    if up and st.session_state.get("ocr_file")!=up.name:
        st.session_state.essay=nv_ocr(up.read())
        st.session_state.ocr_file=up.name; st.rerun()

    essay=st.text_area("감상문 입력 또는 OCR 결과", value=st.session_state.get("essay",""), key="essay", height=240)

    if st.button("🧭 피드백 받기"):
        if not essay.strip(): st.error("감상문을 입력하거나 업로드하세요"); return
        depth = "간단히" if st.session_state.level=="쉬움" else ("충분히 자세히" if st.session_state.level=="기본" else "구체적 근거와 함께")
        fb_prompt = (
            "너는 초등학생 글쓰기 코치야. 학생의 감상문을 **아래 책의 줄거리**와 비교해서, "
            "줄거리와 맞는 내용은 칭찬하고 다른 내용은 사실에 맞게 부드럽게 바로잡아 줘. "
            "점수/등급/일치도 같은 수치는 말하지 마.\n"
            "출력 구조:\n"
            "1) 내용 피드백: 책 줄거리와 얼마나 잘 연결했는지, 틀린 부분이 있다면 어떤 점을 이렇게 고치면 좋은지.\n"
            "2) 표현·구성 피드백: 문장, 접속어, 어휘, 맞춤법에서 잘한 점과 고칠 점.\n"
            f"3) 수정 예시: 학생 글 전체를 {depth}로 다시 써주되, 반드시 선택한 책의 줄거리 내용을 바르게 반영.\n\n"
            f"선택 책 제목:\n{title}\n\n선택 책 줄거리:\n{syn}\n\n학생 감상문:\n{essay}"
        )
        fb=gpt([{"role":"user","content":fb_prompt}],level_params(st.session_state.level)['temp'],2300)
        st.subheader("피드백 결과"); st.write(fb)

    st.markdown("---")
    try: st.link_button("🌐 독서감상문 공유", "http://wwww.example.com")
    except Exception: st.markdown('<a class="linklike-btn" href="http://wwww.example.com" target="_blank">🌐 독서감상문 공유</a>', unsafe_allow_html=True)

# ───── MAIN ─────
def main():
    st.set_page_config("북클라이밍","📚",layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.title("북클라이밍: 독서의 정상에 도전하라")

    if "current_page" not in st.session_state: st.session_state.current_page="책 검색"
    if "level" not in st.session_state: st.session_state.level="기본"

    with st.sidebar:
        st.markdown("### 메뉴")
        menu_labels = {
            "책 검색":"📘 1) 책검색 및 표지대화",
            "단어 알아보기":"🧩 2) 단어 알아보기",
            "독서 퀴즈":"📝 3) 독서 퀴즈",
            "독서 토론":"⚖️ 4) 독서 토론",
            "독서 감상문 피드백":"🎤 5) 독서감상문 피드백"
        }
        st.markdown('<div class="sidebar-radio">', unsafe_allow_html=True)
        sel = st.radio("", list(menu_labels.keys()),
            format_func=lambda k: menu_labels[k],
            index=list(menu_labels).index(st.session_state.current_page),
            label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        st.session_state.current_page = sel
        if st.button("전체 초기화"): st.session_state.clear(); st.rerun()

    pages={
        "책 검색":page_book,
        "단어 알아보기":page_vocab,
        "독서 퀴즈":page_quiz,
        "독서 토론":page_discussion,
        "독서 감상문 피드백":page_feedback
    }
    pages[sel]()

if __name__=="__main__":
    main()
